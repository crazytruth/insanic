import aiohttp
import asyncio
from yarl import URL

from insanic.conf import settings
from insanic.log import logger
from insanic.scopes import is_docker, get_machine_id
from insanic.utils import get_my_ip


def http_session_manager(f):
    async def wrapper(self, *args, **kwargs):

        session = kwargs.get('session', None)

        _session = session or self.session

        if _session is None:
            _session = session = aiohttp.ClientSession()

        kwargs.update({"session": _session})

        await f(self, *args, **kwargs)

        if session is not None:
            await session.close()

    return wrapper


def normalize_url_for_kong(url):
    if url.startswith('^'):
        url = url[1:]

    return url


class BaseGateway:

    def __init__(self):
        self.enabled = settings.GATEWAY_REGISTRATION_ENABLED
        self.routes = {}
        self.service_id = None
        self.session = None

    @http_session_manager
    async def register_service(self, app, *, session):
        """
        Registers the service with api gateway
        """
        raise NotImplementedError(".register_service() must be overridden.")  # pragma: no cover

    @http_session_manager
    async def register_routes(self, app, *, session):
        """
        Registers the service with api gateway
        """
        raise NotImplementedError(".register_routes() must be overridden.")  # pragma: no cover

    @http_session_manager
    async def deregister_service(self, *, session):
        """
        Deregisters the service with api gateway
        """
        raise NotImplementedError(".deregister_service() must be overridden.")  # pragma: no cover

    @http_session_manager
    async def deregister_routes(self, *, session):
        """
        Deregisters the service with api gateway
        """
        raise NotImplementedError(".deregister_routes() must be overridden.")  # pragma: no cover

    async def register(self, app):
        if self.enabled:
            await self.register_service(app)
            await self.register_routes(app)

    async def deregister(self):
        if self.enabled:
            await self.deregister_routes()
            await self.deregister_service()

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()


class KongGateway(BaseGateway):

    def __init__(self):
        super().__init__()
        self.kong_base_url = URL(f"http://{settings.KONG_HOST}:{settings.KONG_PORT}")

        self.service_name = settings.SERVICE_NAME
        self._service_spec = None
        self.machine_id = get_machine_id()

    @property
    def service_spec(self):
        if self._service_spec is None:
            self._service_spec = settings.SERVICE_LIST.get(self.service_name, {})
        return self._service_spec

    @property
    def environment(self):
        return settings.MMT_ENV

    @property
    def kong_service_name(self):
        return f"{self.service_name.lower()}.{self.environment.lower()}.{self.machine_id.lower()}"

    @http_session_manager
    async def register_service(self, app, *, session):
        if self.enabled:
            try:
                async with session.get(self.kong_base_url.with_path(f"/services/{self.kong_service_name}")) as resp:
                    resp.raise_for_status()
                    kong_service_data = await resp.json()
            except aiohttp.ClientResponseError:
                service_data = {
                    "name": self.kong_service_name,
                    "protocol": "http",
                    "host": self.service_spec.get("host",
                                                  f"mmt-server-{self.service_name}") if is_docker else get_my_ip(),
                    "port": self.service_spec.get("internal_service_port", app._port) if is_docker else app._port
                }

                async with session.post(self.kong_base_url.with_path('/services/'), json=service_data) as resp:
                    resp.raise_for_status()
                    kong_service_data = await resp.json()

            self.service_id = kong_service_data['id']

            logger.debug(f"[KONG][SERVICES] Registered service {self.kong_service_name} as {self.service_id}")

    # @http_session_manager
    # async def register_routes(self, app, *, session):
    #     if self.service_id is not None:
    #         route_requests = []
    #         route_data_list = []
    #         for url, methods in app.public_routes().items():
    #             route_data = {
    #                 "protocols": ["http", "https"],
    #                 "methods": methods,
    #                 "hosts": settings.ALLOWED_HOSTS,
    #                 "paths": [normalize_url_for_kong(url)],
    #                 "service": {"id": self.service_id},
    #                 "strip_path": False,
    #                 "regex_priority": 10
    #             }
    #             route_requests.append(session.post(self.kong_base_url.with_path('/routes/'), json=route_data))
    #             route_data_list.append(route_data)
    #
    #         if route_requests:
    #             route_responses = await asyncio.gather(*route_requests)
    #             for i in range(len(route_responses)):
    #                 r = route_responses[i]
    #                 route_response = await r.json()
    #                 try:
    #                     r.raise_for_status()
    #                 except aiohttp.ClientResponseError:  # pragma: no cover
    #                     logger.critical(f"[KONG][ROUTES] FAILED registering route {route_data_list[i]['paths']} "
    #                                     f"on {self.kong_service_name}: {route_response}")
    #                     raise
    #
    #                 self.routes.update({route_response['id']: route_response})
    #                 logger.debug(f"[KONG][ROUTES] Registered route {route_response['paths']} as "
    #                              f"{route_response['id']} on {self.kong_service_name}")
    #         else:
    #             logger.debug(f"[KONG][ROUTES] No Public routes found.")
    #             await self.deregister_service(session=session)
    #     else:
    #         raise RuntimeError("[KONG][ROUTES] Need to register service before registering routes!")

    @http_session_manager
    async def register_routes(self, app, *, session):
        '''
        register routes one by one
        :param app:
        :param session:
        :return:
        '''

        if self.service_id is not None:
            route_data_list = []
            public_routes = app.public_routes()

            if len(public_routes) > 0:
                for url, methods in public_routes.items():
                    route_data = {
                        "protocols": ["http", "https"],
                        "methods": methods,
                        "hosts": settings.ALLOWED_HOSTS,
                        "paths": [normalize_url_for_kong(url)],
                        "service": {"id": self.service_id},
                        "strip_path": False,
                        "regex_priority": 10
                    }

                    async with session.post(self.kong_base_url.with_path('/routes/'), json=route_data) as resp:
                        route_response = await resp.json()

                        try:
                            resp.raise_for_status()
                        except aiohttp.ClientResponseError:
                            logger.critical(f"[KONG][ROUTES] FAILED registering route {route_data_list[i]['paths']} "
                                            f"on {self.kong_service_name}: {route_response}")
                            raise
                        else:
                            self.routes.update({route_response['id']: route_response})
                            logger.debug(f"[KONG][ROUTES] Registered route {route_response['paths']} as "
                                         f"{route_response['id']} on {self.kong_service_name}")
            else:
                logger.debug(f"[KONG][ROUTES] No Public routes found.")
                await self.deregister_service(session=session)
        else:
            raise RuntimeError("[KONG][ROUTES] Need to register service before registering routes!")

    @http_session_manager
    async def deregister_service(self, *, session):
        if self.service_id is not None:
            async with session.delete(self.kong_base_url.with_path(f"/services/{self.service_id}")):
                logger.debug(f"[KONG][SERVICES] Deregistered service {self.service_id}")
                self.service_id = None
        else:
            logger.debug(f"[KONG][SERVICES] {self.kong_service_name} has already been deregistered.")

    @http_session_manager
    async def deregister_routes(self, *, session):

        routes = []
        next_url = self.kong_base_url.with_path(f"/services/{self.service_id}/routes")
        while next_url is not None:
            async with session.get(self.kong_base_url.with_path(f"/services/{self.kong_service_name}/routes")) as resp:
                body = await resp.json()
                routes.extend([r['id'] for r in body.get('data', [])])
                next_url = body.get('next', None)

        delete_route_requests = [session.delete(self.kong_base_url.with_path(f'/routes/{r}'))
                                 for r in routes]

        # asyncio gather
        if delete_route_requests:
            delete_route_responses = await asyncio.gather(*delete_route_requests)

            for r in delete_route_responses:
                rid = str(r.url).split('/')[-1]

                try:
                    del self.routes[rid]
                except KeyError:
                    pass
                logger.debug(f"[KONG][ROUTES] Deregistered route {rid}.")
        else:
            logger.debug(f"[KONG][ROUTES] No routes to deregister.")


gateway = KongGateway()
