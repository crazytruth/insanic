import aiohttp
import asyncio
import logging

from aiohttp.client_exceptions import ClientConnectorError
from multiprocessing import current_process
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
        self._enabled = settings.GATEWAY_REGISTRATION_ENABLED
        self.routes = {}
        self.service_id = None
        self.session = None

    def logger_create_message(self, module, message):
        namespace = self.__class__.__name__.upper().replace("GATEWAY", "")
        return f"[{namespace}][{module.upper()}] {message}"

    def logger(self, level, message, module="GENERAL", *args, **kwargs):
        if not isinstance(level, int):
            log_level = logging._nameToLevel.get(level.upper(), None)

            if log_level is None:
                if logger.raiseExceptions:
                    raise TypeError(
                        "Unable to resolve level. Must be one of {}.".format(", ".join(logging._nameToLevel.keys())))
                else:
                    return
        else:
            log_level = level

        message = self.logger_create_message(module, message)
        logger.log(log_level, message, *args, **kwargs)

    def logger_service(self, level, message, *args, **kwargs):
        self.logger(level, message, "SERVICE", *args, **kwargs)

    def logger_route(self, level, message, *args, **kwargs):
        self.logger(level, message, "ROUTE", *args, **kwargs)

    @property
    def enabled(self):
        _cp = current_process()

        if _cp.name == "MainProcess":
            return self._enabled
        elif _cp.name.startswith("Process-"):
            return self._enabled and _cp.name.replace("Process-", "") == "1"
        else:
            raise RuntimeError("Unable to resolve process name.")

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
            try:
                await self.register_service(app)
                await self.register_routes(app)
            except ClientConnectorError:
                if settings.MMT_ENV in settings.KONG_FAIL_SOFT_ENVIRONMENTS:
                    self.logger_route('info', "Connection to kong has failed. Soft failing registration.")
                else:
                    raise


    async def deregister(self):
        if self.enabled:
            try:
                await self.deregister_routes()
                await self.deregister_service()
            except ClientConnectorError:
                if settings.MMT_ENV in settings.KONG_FAIL_SOFT_ENVIRONMENTS:
                    self.logger_route('info', "Connection to kong has failed. Soft failing registration.")
                else:
                    raise

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

            self.logger_service("debug", f"Registered service {self.kong_service_name} as {self.service_id}")

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
    #                     self.logger_route("critical",
    #                                       f"FAILED registering route {route_data_list[i]['paths']} "
    #                                       f"on {self.kong_service_name}: {route_response}")
    #                     raise
    #
    #                 self.routes.update({route_response['id']: route_response})
    #                 self.logger_route("debug",
    #                                   f"Registered route {route_response['paths']} as "
    #                                   f"{route_response['id']} on {self.kong_service_name}")
    #         else:
    #             self.logger_route("debug", "No Public routes found.")
    #             await self.deregister_service(session=session)
    #     else:
    #         raise RuntimeError(
    #             self.logger_create_message("routes", "Need to register service before registering routes!"))

    async def enable_plugins(self, session, route_info, route_resp, route_data):
        # attach plugins
        for plugin in route_info['plugins']:
            # If 'jwt' plugin should be enabled, then should provide anonymous consumer id.
            if plugin == 'jwt':
                async with session.get(self.kong_base_url.with_path("/consumers/anonymous/")) as resp:
                    # If anonymous consumer does not exist, make one.
                    if resp.status == 404:
                        async with session.post(self.kong_base_url.with_path("/consumers/"),
                                                json={'username': 'anonymous'}) as create_resp:
                            # overwrite get response
                            resp = create_resp
                            result = await create_resp.json()

                            try:
                                resp.raise_for_status()
                            except aiohttp.ClientResponseError:
                                self.logger_route("critical", f"FAILED creating anonymous consumer "
                                                              f"by {self.kong_service_name}")
                            else:
                                self.logger_route("info",
                                                  f"Consumer {result['id']} was created as anonymous user "
                                                  f"by {self.kong_service_name}")

                    result = await resp.json()
                    payload = {'name': 'jwt', 'config.anonymous': result['id']}

                    # Error check if there was an error on request to enable jwt plugin
                    try:
                        resp.raise_for_status()
                    except aiohttp.ClientResponseError:
                        self.logger_route("critical",
                                          f"FAILED "
                                          f"enabling jwt plugin for route {route_data['paths']} "
                                          f"on {self.kong_service_name}: {route_resp['id']}")
                        raise
                    else:
                        self.logger_route("debug",
                                          f"Enabled jwt plugin for route {route_resp['paths']}"
                                          f" as {route_resp['id']} on {self.kong_service_name}")

            else:
                payload = {'name': plugin}

            async with session.post(self.kong_base_url.with_path(
                    f"/routes/{route_resp['id']}/plugins/"), json=payload) as resp:
                await resp.json()

                try:
                    resp.raise_for_status()
                except aiohttp.ClientResponseError:
                    self.logger_route("critical",
                                      f"FAILED "
                                      f"enabling {plugin} plugin for route {route_data['paths']} "
                                      f"on {self.kong_service_name}: {route_resp['id']}")
                    raise
                else:
                    self.logger_route("debug",
                                      f"Enabled {plugin} plugin for route {route_resp['paths']}"
                                      f" as {route_resp['id']} on {self.kong_service_name}")

    @http_session_manager
    async def register_routes(self, app, *, session):
        '''
        register routes one by one
        :param app:
        :param session:
        :return:
        '''

        if self.service_id is not None:
            public_routes = app.public_routes()

            if len(public_routes) > 0:
                for url, route_info in public_routes.items():
                    route_data = {
                        "protocols": ["http", "https"],
                        "methods": route_info['public_methods'],
                        "hosts": settings.ALLOWED_HOSTS,
                        "paths": [normalize_url_for_kong(url)],
                        "service": {"id": self.service_id},
                        "strip_path": False,
                        "regex_priority": settings.KONG_ROUTE_REGEX_PRIORITY.get(settings.MMT_ENV, 10)
                    }

                    async with session.post(self.kong_base_url.with_path('/routes/'), json=route_data) as resp:
                        route_response = await resp.json()
                        try:
                            resp.raise_for_status()
                            await self.enable_plugins(session, route_info, route_response, route_data)
                        except aiohttp.ClientResponseError:
                            self.logger_route("critical",
                                              f"FAILED registering route {route_data['paths']} "
                                              f"on {self.kong_service_name}: {route_response}")
                            raise
                        else:
                            self.routes.update({route_response['id']: route_response})

                            self.logger_route("debug",
                                              f"Registered route {route_response['paths']} as "
                                              f"{route_response['id']} on {self.kong_service_name}")
            else:
                self.logger_route("debug", "No Public routes found.")
                await self.deregister_service(session=session)
        else:
            raise RuntimeError(
                self.logger_create_message("routes", "Need to register service before registering routes!"))

    @http_session_manager
    async def deregister_service(self, *, session):
        if self.service_id is not None:
            async with session.delete(self.kong_base_url.with_path(f"/services/{self.service_id}")):
                self.logger_service("debug", f"Deregistered service {self.service_id}")
                self.service_id = None
        else:
            self.logger_service("debug", f"{self.kong_service_name} has already been deregistered.")

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
                self.logger_route('debug', "Deregistered route {rid}.")
        else:
            self.logger_route('debug', "No routes to deregister.")


gateway = KongGateway()
