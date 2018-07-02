import aiohttp

from yarl import URL

from insanic import status
from insanic.conf import settings
from insanic.scopes import get_my_ip
from insanic.registration.gateway import BaseGateway, http_session_manager, normalize_url_for_kong
from .fixtures import UPSTREAM_OBJECT


class KongGateway(BaseGateway):
    SERVICES_RESOURCE = "services"
    ROUTES_RESOURCE = "routes"
    CONSUMERS_RESOURCE = "consumers"
    PLUGINS_RESOURCE = "plugins"
    UPSTREAMS_RESOURCE = "upstreams"
    TARGETS_RESOURCE = "targets"

    def __init__(self):
        super().__init__()
        self._kong_base_url = None
        self._service_name = None
        self._app = None
        self.registered_instance = {}

    @property
    def kong_base_url(self):
        if self._kong_base_url is None:
            self._kong_base_url = URL(f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}")
        return self._kong_base_url

    @property
    def service_name(self):
        if self._service_name is None:
            self._service_name = settings.SERVICE_NAME
        return self._service_name

    @property
    def route_compare_fields(self):
        return ['protocols', 'methods', 'hosts', 'regex_priority', 'strip_path', 'preserve_host', 'paths']

    @property
    def environment(self):
        return settings.MMT_ENV

    @property
    def kong_service_name(self):
        return f"{self.environment.lower()}-{self.service_name.lower()}-{self.service_version}"

    @property
    def service_host(self):
        return settings.SERVICE_GLOBAL_HOST_TEMPLATE.format(self.service_name)

    @property
    async def target(self):
        return f"{get_my_ip()}:{self.app._port}"

    @http_session_manager
    async def _register(self, *, session):
        await self.register_service()
        await self.register_routes()
        await self.register_upstream()
        await self.register_target()

    @http_session_manager
    async def _deregister(self, *, session):
        await self.deregister_target()
        # await self.deregister_upstream()
        # await self.deregister_routes()
        # await self.deregister_service()

    @http_session_manager
    async def register_service(self, *, session):
        if self.enabled:
            try:
                async with session.get(
                        self.kong_base_url.with_path(f"/{self.SERVICES_RESOURCE}/{self.kong_service_name}")) as resp:
                    resp.raise_for_status()
                    kong_service_data = await resp.json()
                success_message = "Already Registered Service {kong_service_name} as {service_id}"
            except aiohttp.ClientResponseError:
                service_data = {
                    "name": self.kong_service_name,
                    "protocol": "http",
                    "host": self.kong_service_name,
                    "port": int(self.app._port)
                }

                async with session.post(self.kong_base_url.with_path(f'/{self.SERVICES_RESOURCE}/'),
                                        json=service_data) as resp:
                    kong_service_data = await resp.json()
                    try:
                        resp.raise_for_status()
                        success_message = "Registered service {kong_service_name} as {service_id}"
                        self.registered_instance[self.SERVICES_RESOURCE] = kong_service_data['id']
                    except aiohttp.client_exceptions.ClientResponseError:  # pragma: no cover
                        self.logger_service("critical",
                                            f"FAILED: registered service {self.kong_service_name}: {kong_service_data}")
                        raise

            self.service_id = kong_service_data['id']
            self.logger_service("debug", success_message.format(kong_service_name=self.kong_service_name,
                                                                service_id=self.service_id))

    @http_session_manager
    async def deregister_service(self, *, session):
        if self.SERVICES_RESOURCE in self.registered_instance:
            async with session.delete(
                    self.kong_base_url.with_path(f"/services/{self.registered_instance[self.SERVICES_RESOURCE]}")
            ) as resp:
                resp.raise_for_status()
                self.logger_service("debug", f"Deregistered service {self.registered_instance[self.SERVICES_RESOURCE]}")
                self.service_id = None
                del self.registered_instance[self.SERVICES_RESOURCE]
        else:
            self.service_id = None
            self.logger_service("debug", "This instance did not register a service.")

    @property
    def upstream_object(self):
        upstream = UPSTREAM_OBJECT.copy()
        upstream['name'] = self.kong_service_name
        upstream['healthchecks']['active']['http_path'] = f"/{settings.SERVICE_NAME}/health/"
        upstream['healthchecks']['active']['healthy']['http_statuses'] = [status.HTTP_200_OK]
        return upstream

    @http_session_manager
    async def register_upstream(self, *, session):
        if self.enabled and self.service_id is not None:
            try:
                async with session.get(
                        self.kong_base_url.with_path(f"/{self.UPSTREAMS_RESOURCE}/{self.kong_service_name}")) as resp:
                    resp.raise_for_status()
                    kong_upstream_data = await resp.json()
                    message = "Already Registered Upstream {kong_service_name} as {upstream_id}"
            except aiohttp.ClientResponseError:
                # object reference
                # https://getkong.org/docs/0.13.x/admin-api/#endpoint

                upstream_data = self.upstream_object
                async with session.post(self.kong_base_url.with_path(f'/{self.UPSTREAMS_RESOURCE}/'),
                                        json=upstream_data) as resp:
                    kong_upstream_data = await resp.json()
                    try:
                        resp.raise_for_status()
                        message = "Registered upstream {kong_service_name} as {upstream_id}"
                        self.registered_instance[self.UPSTREAMS_RESOURCE] = kong_upstream_data['id']
                    except aiohttp.client_exceptions.ClientResponseError:  # pragma: no cover
                        self.logger_upstream("critical",
                                             f"FAILED: registering upstream {self.kong_service_name}: {kong_upstream_data}")
                        raise

            self.upstream_id = kong_upstream_data['id']
            self.logger_upstream("debug",
                                 message.format(kong_service_name=self.kong_service_name, upstream_id=self.upstream_id))

    @http_session_manager
    async def deregister_upstream(self, *, session):
        if self.UPSTREAMS_RESOURCE in self.registered_instance:
            async with session.delete(
                    self.kong_base_url.with_path(
                        f"/{self.UPSTREAMS_RESOURCE}/{self.registered_instance[self.UPSTREAMS_RESOURCE]}")
            ) as resp:
                resp.raise_for_status()
                self.logger_upstream("debug",
                                     f"Deregistered upstream {self.registered_instance[self.UPSTREAMS_RESOURCE]}")
                self.upstream_id = None
                del self.registered_instance[self.UPSTREAMS_RESOURCE]
        else:
            self.upstream_id = None
            self.logger_upstream("debug", "This instance did not register an upstream.")

    @http_session_manager
    async def register_target(self, *, session):
        if self.enabled and hasattr(self, 'upstream_id') and self.upstream_id is not None:

            next_url = self.kong_base_url.with_path(
                f"/{self.UPSTREAMS_RESOURCE}/{self.kong_service_name}/{self.TARGETS_RESOURCE}/")

            targets = []
            while next_url is not None:
                async with session.get(next_url) as resp:
                    target_data = await resp.json()
                    if len(target_data['data']) is 0 or len(targets) is target_data['total']:
                        break
                    targets.extend(target_data['data'])
                    next_url = next_url.with_query({"offset": len(targets)})

            #     search for current ip
            target_id = None
            target = await self.target
            for t in targets:
                if t['target'] == target:
                    target_id = t['id']
                    message = "Already Registered Target {target} as {target_id} for {service_host}"
                    break
            else:
                target_object = {
                    "target": target
                }
                async with session.post(self.kong_base_url.with_path(
                        f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/{self.TARGETS_RESOURCE}"),
                        data=target_object) as resp:
                    kong_target_response = await resp.json()
                    try:
                        resp.raise_for_status()
                        target_id = kong_target_response['id']
                        message = "Registered Target {target} as {target_id} for {service_host}"
                        self.registered_instance[self.TARGETS_RESOURCE] = target_id
                    except aiohttp.client_exceptions.ClientResponseError:  # pragma: no cover
                        self.logger_target("critical",
                                           f"FAILED: registering target {target}: {kong_target_response}")
                        raise

            self.target_id = target_id
            self.logger_target("debug",
                               message.format(target=target, target_id=self.target_id,
                                              service_host=self.kong_service_name))

    @http_session_manager
    async def deregister_target(self, *, session):
        if self.TARGETS_RESOURCE in self.registered_instance:
            async with session.delete(
                    self.kong_base_url.with_path(
                        f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/{self.TARGETS_RESOURCE}/{self.registered_instance[self.TARGETS_RESOURCE]}"
                    )
            ) as resp:
                resp.raise_for_status()
                self.logger_target("debug", f"Deregistered target {self.registered_instance[self.TARGETS_RESOURCE]}")
                self.target_id = None
                del self.registered_instance[self.TARGETS_RESOURCE]
        else:
            self.target_id = None
            self.logger_target("debug", "This instance did not register a target.")

    @http_session_manager
    async def force_target_healthy(self, *, session):
        if self.target_id and self.upstream_id:
            async with session.post(
                    self.kong_base_url.with_path(
                        f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/{self.TARGETS_RESOURCE}/{self.target_id}/healthy"
                    ),
                    json={},

            ) as resp:
                kong_target_response = await resp.text()
                try:

                    resp.raise_for_status()
                    self.logger_target("debug", f"Forced healthy: {self.target_id}")
                except aiohttp.client_exceptions.ClientResponseError:
                    self.logger_target("debug", f"Failed to force healthy {self.target_id}: {kong_target_response}")

    def change_detected(self, route1, route2, compare_fields):
        """
        compares

        :param route1:
        :param route2:
        :param compare_fields:
        :type route1: dict
        :type route2: dict
        :type compare_fields: list
        :return:
        :rtype: bool
        """
        for c in compare_fields:
            if isinstance(route1[c], list):
                if sorted(route1[c]) != sorted(route2.get(c, [])):
                    return True
            else:
                if route1[c] != route2.get(c):
                    return True
        return False
        #
        # diff = r1.items() & r2.items()
        # return len(diff) != 0

    def _route_object(self, path, methods):
        return {
            "protocols": ["http", "https"],
            "methods": methods,
            "hosts": settings.ALLOWED_HOSTS,
            "paths": [path],
            "service": {"id": self.service_id},
            "strip_path": False,
            "preserve_host": False,
            "regex_priority": settings.KONG_ROUTE_REGEX_PRIORITY.get(settings.MMT_ENV, 10)
        }


    @http_session_manager
    async def register_routes(self, *, session):
        '''
        register routes one by one. if public_route gathered by app and routes registered in kong differs,
        sync public_routes gathered by app

        :param app:
        :param session:
        :return:
        '''

        if self.service_id is not None:
            public_routes = self.app.public_routes()

            if len(public_routes) > 0:

                list_service_routes_url = self.kong_base_url. \
                    with_path(f"/{self.SERVICES_RESOURCE}/{self.service_id}/{self.ROUTES_RESOURCE}")
                async with session.get(list_service_routes_url) as resp:
                    response = await resp.json()
                    resp.raise_for_status()

                registered_routes = {p: r for r in response.get('data', []) for p in r.get('paths', [])}

                for url, route_info in public_routes.items():
                    path = normalize_url_for_kong(url)
                    route_data = self._route_object(path, route_info['public_methods'])
                    registered_route = registered_routes.get(path, {})

                    if self.change_detected(route_data, registered_route,
                                            self.route_compare_fields):

                        async with session.post(self.kong_base_url.with_path(f'/{self.ROUTES_RESOURCE}/'),
                                                json=route_data) as resp:
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
                                if self.ROUTES_RESOURCE not in self.registered_instance:
                                    self.registered_instance[self.ROUTES_RESOURCE] = []
                                self.registered_instance[self.ROUTES_RESOURCE].append(route_response['id'])
                                self.logger_route("debug",
                                                  f"Registered route {route_response['paths']} as "
                                                  f"{route_response['id']} on {self.kong_service_name}")
                    else:
                        message = f"Already Registered Route {path} as {registered_route['id']} on {self.kong_service_name}."
                        self.routes.update({registered_route['id']: registered_route})
                        self.logger_route("debug", message)
            else:
                self.logger_route("debug", "No Public routes found.")
                await self.deregister_service(session=session)
        else:
            raise RuntimeError(
                self.logger_create_message("routes", "Need to register service before registering routes!"))

    @http_session_manager
    async def deregister_routes(self, *, session):

        # asyncio gather seems unstable
        if self.ROUTES_RESOURCE in self.registered_instance:

            routes = self.registered_instance[self.ROUTES_RESOURCE][:]
            for r in routes:
                await self.disable_plugins(session, r)
                async with session.delete(self.kong_base_url.with_path(f'/routes/{r}')) as resp:
                    try:
                        resp.raise_for_status()
                    except aiohttp.ClientResponseError:
                        route_response = await resp.json()
                        self.logger_route("critical",
                                          f"FAILED deregistering route {r} "
                                          f"on {self.kong_service_name}: {route_response}")
                        continue
                    else:
                        try:
                            self.registered_instance[self.ROUTES_RESOURCE].remove(r)
                            del self.routes[r]
                        except KeyError:
                            pass
                        self.logger_route("debug",
                                          f"Deregistered route {r} on {self.kong_service_name}")
        else:
            self.logger_route('debug', "This instance did not register any routes.")

    async def enable_plugins(self, session, route_info, route_resp, route_data):
        # attach plugins
        for plugin in route_info['plugins']:
            # If 'jwt' plugin should be enabled, then should provide anonymous consumer id.
            if plugin == 'jwt':
                async with session.get(self.kong_base_url.with_path(f"/{self.CONSUMERS_RESOURCE}/anonymous/")) as resp:
                    # If anonymous consumer does not exist, make one.
                    if resp.status == 404:
                        async with session.post(self.kong_base_url.with_path(f"/{self.CONSUMERS_RESOURCE}/"),
                                                json={'username': 'anonymous'}) as create_resp:
                            # overwrite get response
                            resp = create_resp
                            result = await resp.json()

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
                    payload = {'name': 'jwt',
                               'config.anonymous': result['id'],
                               'config.claims_to_verify': 'exp'}

                    # Error check if there was an error on request to enable jwt plugin
                    try:
                        resp.raise_for_status()
                    except aiohttp.ClientResponseError:
                        self.logger_route("critical",
                                          f"FAILED "
                                          f"getting anonymous user with status_code: {resp.status} "
                                          f"on {self.kong_service_name}")
                        raise

            else:
                payload = {'name': plugin}

            async with session.post(self.kong_base_url.with_path(
                    f"/{self.ROUTES_RESOURCE}/{route_resp['id']}/{self.PLUGINS_RESOURCE}/"), json=payload) as resp:
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

    async def disable_plugins(self, session, route_id):
        plugins = []
        next_url = self.kong_base_url.with_path(f"/plugins").with_query({'route_id': route_id})

        # Get plugins which are enabled for this route
        while next_url is not None:
            async with session.get(next_url) as resp:
                # If no plugins enabled for this route, just skip
                if resp.status == 404:
                    return
                else:
                    body = await resp.json()
                    plugins.extend([r['id'] for r in body.get('data', [])])
                    next_url = body.get('next', None)

            # Delete plugins
            if plugins:
                for p in plugins:
                    async with session.delete(self.kong_base_url.with_path(f"/plugins/{p}")) as delete_resp:
                        try:
                            delete_resp.raise_for_status()
                        except aiohttp.ClientResponseError:
                            self.logger_route("critical", f"FAILED disabling plugin: {p} on {self.kong_service_name} "
                                                          f"with status_code: {delete_resp.status}")


gateway = KongGateway()
