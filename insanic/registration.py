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


class BaseGateway:

    def __init__(self):
        self.service_id = None
        self.route_ids = []
        self.session = None

    async def register_service(self, app, *, session):
        """
        Registers the service with api gateway
        """
        raise NotImplementedError(".register_service() must be overridden.")  # pragma: no cover

    async def register_routes(self, app, *, session):
        """
        Registers the service with api gateway
        """
        raise NotImplementedError(".register_routes() must be overridden.")  # pragma: no cover

    async def deregister_service(self, *, session):
        """
        Deregisters the service with api gateway
        """
        raise NotImplementedError(".deregister_service() must be overridden.")  # pragma: no cover

    async def deregister_routes(self, *, session):
        """
        Deregisters the service with api gateway
        """
        raise NotImplementedError(".deregister_routes() must be overridden.")  # pragma: no cover

    async def register(self, app):
        await self.register_service(app)
        await self.register_routes(app)

    async def deregister(self):
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
        self.kong_services_url = self.kong_base_url.with_path('/services/')
        self.kong_routes_url = self.kong_base_url.with_path('/routes/')

        self.service_name = settings.SERVICE_NAME
        self.service_spec = settings.SERVICE_LIST.get(self.service_name, {})
        self.kong_service_name = f"{self.service_name}.{settings.MMT_ENV}.{get_machine_id()}"

    @http_session_manager
    async def register_service(self, app, *, session):

        try:
            async with session.get(self.kong_base_url.with_path(f"/services/{self.kong_service_name}")) as resp:
                resp.raise_for_status()
                kong_service_data = await resp.json()
        except aiohttp.ClientResponseError:
            service_data = {
                "name": self.kong_service_name,
                "protocol": "http",
                "host": self.service_spec.get("host", f"mmt-server-{self.service_name}") if is_docker \
                    else get_my_ip(),
                "port": self.service_spec.get("internal_service_port", app._port) if is_docker \
                    else app._port
            }

            async with session.post(self.kong_services_url, json=service_data) as resp:
                resp.raise_for_status()
                kong_service_data = await resp.json()

        self.service_id = kong_service_data['id']

        logger.debug(f"[KONG][SERVICES] Registered service {self.kong_service_name} as {self.service_id}")

    @http_session_manager
    async def register_routes(self, app, *, session):
        if self.service_id is not None:
            route_requests = []
            for url, methods in app.public_routes().items():
                route_data = {
                    "protocols": ["http", "https"],
                    "methods": methods,
                    "hosts": settings.ALLOWED_HOSTS,
                    "paths": [url[:-1] if url.endswith('/') else url],
                    "service": {"id": self.service_id},
                    "strip_path": False,
                    "regex_priority": 10
                }
                route_requests.append(session.post(self.kong_routes_url, json=route_data))

            if route_requests:
                route_responses = await asyncio.gather(*route_requests)
                for r in route_responses:
                    r.raise_for_status()
                    route_response = await r.json()
                    logger.debug(f"[KONG][ROUTES] Registered route {route_response['paths']} as "
                                 f"{route_response['id']} on {self.kong_service_name}")
            else:
                logger.debug(f"[KONG][ROUTES] No Public routes found.")
                await self.deregister_service(session=session)
        else:
            raise RuntimeError("[KONG][ROUTES] Need to register service before registering routes!")

    @http_session_manager
    async def deregister_service(self, *, session):
        if len(self.route_ids) == 0:
            if self.service_id is not None:
                async with session.delete(self.kong_base_url.with_path(f"/services/{self.service_id}")) as resp:
                    if resp.status == 204:
                        logger.debug(f"[KONG][SERVICES] Deregistered service {self.service_id}")
                        self.service_id = None
                    else:
                        body = await resp.json()

                        logger.critical(f"[KONG][SERVICES] FAILED Deregistering service {self.service_id}: {body}")
            else:
                logger.debug(f"[KONG][SERVICES] {self.kong_service_name} has already been deregistered.")
        else:
            raise RuntimeError("[KONG][SERVICES] Need to deregister routes before deregistering services!")

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
                if r.status == 204:
                    try:
                        self.route_ids.remove(rid)
                    except ValueError:
                        pass
                    logger.debug(f"[KONG][ROUTES] Deregistered route {rid}.")
                else:
                    body = await r.json()
                    logger.critical(f"[KONG][ROUTES] FAILED Deregistering route {rid}: {body}")

        else:
            logger.debug(f"[KONG][ROUTES] No routes to deregister.")


gateway = KongGateway()
