import ujson as json
import urllib.request
import urllib.parse
import urllib.error

from yarl import URL

from insanic import status
from insanic.conf import settings
from insanic.scopes import get_my_ip
from insanic.registration.gateway import BaseGateway, normalize_url_for_kong
from .fixtures import UPSTREAM_OBJECT


def urlopen(request, data=None):
    request.add_header("Content-Type", "application/json")

    params = {
        "url": request
    }
    if data is not None:
        params.update({"data": json.dumps(data).encode()})

    response = urllib.request.urlopen(**params)
    response_body = response.read().decode()

    if response_body:
        response_body = json.loads(response_body)

    return response_body


class Route(dict):

    def __init__(self, *, methods, id=None, protocols=None, hosts=None,
                 paths=None, regex_priority=None, strip_path=False,
                 preserve_host=False, **kwargs):
        super().__init__()
        self['methods'] = sorted(methods)

        if protocols is None:
            protocols = ['http', 'https']
        self['protocols'] = sorted(protocols)

        if hosts is None:
            hosts = sorted(settings.ALLOWED_HOSTS)
        self['hosts'] = hosts

        if not isinstance(paths, (list, set, tuple)):
            paths = [paths]
        else:
            paths = sorted(paths)
        self['paths'] = paths

        if regex_priority is None:
            regex_priority = settings.KONG_ROUTE_REGEX_PRIORITY.get(settings.MMT_ENV, 10)
        self['regex_priority'] = regex_priority

        self['strip_path'] = strip_path
        self['preserve_host'] = preserve_host

        self['id'] = id

    def update_service_id(self, service_id):
        self['service'] = {"id": service_id}

    compare_fields = ['methods', 'protocols', 'hosts', 'paths', 'regex_priority', 'strip_path', 'preserve_host']

    def __eq__(self, other):

        try:
            for k in self.compare_fields:
                if self[k] != other[k]:
                    return False
            else:
                return True
        except KeyError:
            return False

        # return (self.methods, self.protocols, self.hosts, self.paths,
        #         self.regex_priority, self.strip_path, self.preserve_host) == \
        #        (other.methods, other.protocols, other.hosts, other.paths,
        #         other.regex_priority, other.strip_path, other.preserve_host)


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
        return f"{self.environment.lower()}-{self.service_name.lower()}"

    @property
    def kong_service_host(self):
        return f"{self.kong_service_name}-{self.service_version}"

    @property
    def target(self):
        return f"{get_my_ip()}:{self.app._port}"

    @property
    def service(self):
        return self._service

    @service.setter
    def service(self, value):
        self._service = value
        self.service_id = value['id']

    @property
    def service_id(self):
        return self.registered_instance.get(self.SERVICES_RESOURCE, None)

    @service_id.setter
    def service_id(self, value):
        if value is None and self.SERVICES_RESOURCE in self.registered_instance:
            del self.registered_instance[self.SERVICES_RESOURCE]
        else:
            self.registered_instance[self.SERVICES_RESOURCE] = value

    @property
    def upstream_id(self):
        return self.registered_instance.get(self.UPSTREAMS_RESOURCE, None)

    @upstream_id.setter
    def upstream_id(self, value):
        if value is None and self.UPSTREAMS_RESOURCE in self.registered_instance:
            del self.registered_instance[self.UPSTREAMS_RESOURCE]
        else:
            self.registered_instance[self.UPSTREAMS_RESOURCE] = value

    @property
    def target_id(self):
        return self.registered_instance.get(self.TARGETS_RESOURCE, None)

    @target_id.setter
    def target_id(self, value):
        if value is None and self.TARGETS_RESOURCE in self.registered_instance:
            del self.registered_instance[self.TARGETS_RESOURCE]
        else:
            self.registered_instance[self.TARGETS_RESOURCE] = value

    def _register(self):
        try:
            self.register_upstream()
            self.register_target()
            self.register_service()
            self.register_routes()

            self.update_service_host()

        except urllib.error.HTTPError:
            self._deregister()
            raise

    def _deregister(self):
        self.deregister_target()
        # self.deregister_upstream()
        # self.deregister_routes()
        # self.deregister_service()

    @property
    def service_data(self):
        return {
            "name": self.kong_service_name,
            "protocol": "http",
            "host": self.kong_service_host,
            "port": int(self.app._port)
        }

    def register_service(self):
        if self.enabled:
            req = urllib.request.Request(
                str(self.kong_base_url.with_path(f"/{self.SERVICES_RESOURCE}/{self.kong_service_name}"))
            )

            try:
                kong_service_data = urlopen(req)
                success_message = "Already Registered Service {kong_service_name} as {service_id}"
            except urllib.error.HTTPError as e:
                service_data = self.service_data.copy()
                post_request = urllib.request.Request(
                    str(self.kong_base_url.with_path(f'/{self.SERVICES_RESOURCE}/')),
                    method="POST"
                )
                try:
                    kong_service_data = urlopen(post_request, service_data)
                    success_message = "Registered service {kong_service_name} as {service_id}"
                except urllib.error.HTTPError as e:
                    self.logger_service("critical",
                                        f"FAILED: registered service {self.kong_service_name}: {e.reason}")
                    raise

            self.service = kong_service_data
            self.logger_service("debug", success_message.format(kong_service_name=self.kong_service_name,
                                                                service_id=self.service_id))

    def update_service_host(self):
        if self.enabled:
            if self.service['host'] != self.kong_service_host:
                healthy_base_url = self.kong_base_url.with_path(
                    f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/health/")

                for _ in range(3):
                    for d in self._list_resources(healthy_base_url):
                        if d['health'] == "HEALTHY":
                            break
                    else:
                        import time
                        time.sleep(5)
                        continue
                    break
                else:
                    msg = f"FAILED: update service {self.kong_service_name} because no healthy nodes."
                    self.logger_service("critical", msg)
                    raise EnvironmentError(msg)

                patch_req = urllib.request.Request(
                    str(self.kong_base_url.with_path(f"/{self.SERVICES_RESOURCE}/{self.kong_service_name}")),
                    method='PATCH'
                )

                try:
                    service_data = self.service_data
                    kong_service_data = urlopen(patch_req, service_data)
                except urllib.error.HTTPError as e:
                    self.logger_service("critical",
                                        f"FAILED: update service {self.kong_service_name}: {e.reason}")
                    raise
                else:
                    self.logger_service("debug",
                                        "Updated service {kong_service_name} to {service_data}".format(
                                            kong_service_name=self.kong_service_name,
                                            service_data=kong_service_data))



    def _deregister_resource(self, resource_type, resource_id, path):

        req = urllib.request.Request(
            str(self.kong_base_url.with_path(path)),
            method='DELETE'
        )

        try:
            response = urlopen(req)
            self.logger("debug", f"Deregistered `{resource_type.lower()}`: {resource_id}")
            try:
                del self.registered_instance[resource_type]
            except KeyError:
                pass
        except urllib.error.HTTPError as e:
            self.logger("critical", f"Problem occurred when deregistering `{resource_type.lower()}`: {e.reason}",
                        resource_type.upper())

    def deregister_target(self):
        if self.TARGETS_RESOURCE in self.registered_instance and self.enabled:
            self._deregister_resource(
                self.TARGETS_RESOURCE,
                self.target_id,
                f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/{self.TARGETS_RESOURCE}/{self.target_id}"
            )
        else:
            self.logger_target("debug", "This instance did not register a target.")

    def deregister_service(self):
        if self.SERVICES_RESOURCE in self.registered_instance:
            self._deregister_resource(
                self.SERVICES_RESOURCE,
                self.service_id,
                f"/services/{self.service_id}"
            )
        else:
            self.logger_service("debug", "This instance did not register a service.")

    def deregister_upstream(self):
        if self.UPSTREAMS_RESOURCE in self.registered_instance:
            self._deregister_resource(
                self.UPSTREAMS_RESOURCE,
                self.upstream_id,
                f"/{self.UPSTREAMS_RESOURCE}/{self.registered_instance[self.UPSTREAMS_RESOURCE]}"
            )
        else:
            self.logger_upstream("debug", "This instance did not register an upstream.")

    @property
    def upstream_object(self):
        upstream = UPSTREAM_OBJECT.copy()
        upstream['name'] = self.kong_service_host
        upstream['healthchecks']['active']['http_path'] = f"/{settings.SERVICE_NAME}/health/"
        upstream['healthchecks']['active']['healthy']['http_statuses'] = [status.HTTP_200_OK]
        return upstream

    def register_upstream(self):
        if self.enabled:
            req = urllib.request.Request(
                str(self.kong_base_url.with_path(f"/{self.UPSTREAMS_RESOURCE}/{self.kong_service_host}")),
                method='GET'
            )

            try:
                kong_upstream_data = urlopen(req)
                message = "Already Registered Upstream {kong_service_host} as {upstream_id}"
            except urllib.error.HTTPError:
                upstream_data = self.upstream_object

                post_request = urllib.request.Request(
                    str(self.kong_base_url.with_path(f'/{self.UPSTREAMS_RESOURCE}/')),
                    method='POST',
                )
                try:
                    kong_upstream_data = urlopen(post_request, upstream_data)
                    message = "Registered upstream {kong_service_host} as {upstream_id}"
                    self.registered_instance[self.UPSTREAMS_RESOURCE] = kong_upstream_data['id']
                except urllib.error.HTTPError as e:
                    kong_upstream_data = e.read().decode()
                    self.logger_upstream("critical",
                                         f"FAILED: registering upstream {self.kong_service_host}: {kong_upstream_data}")
                    raise

            self.upstream_id = kong_upstream_data['id']
            self.logger_upstream("debug",
                                 message.format(kong_service_host=self.kong_service_host,
                                                upstream_id=self.upstream_id))

    def force_target_healthy(self):
        if self.target_id and self.upstream_id:
            req = urllib.request.Request(
                str(self.kong_base_url.with_path(
                    f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/{self.TARGETS_RESOURCE}/{self.target_id}/healthy"
                )),
                method='POST'
            )

            try:
                kong_target_response = urlopen(req, {})
                self.logger_target("debug", f"Forced healthy: {self.target_id}")
            except urllib.error.HTTPError as e:
                kong_target_response = e.read().decode()
                self.logger_target("debug", f"Failed to force healthy {self.target_id}: {kong_target_response}")
        else:
            self.logger_target("debug", f"Unable to force healthy because need both target and upstream_id: "
                                        f"target: {self.target_id} upstream_id: {self.upstream_id}")

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

    def _list_resources(self, base_url):

        next_url = base_url

        while next_url is not None:
            request = urllib.request.Request(
                next_url,
                method='GET'
            )
            response = urlopen(request)
            for r in response.get('data', []):
                yield r

            offset = response.get('offset', None)
            if offset is None:
                next_url = None
            else:
                next_url = base_url.with_query({"offset": offset})

    def register_target(self):
        if self.enabled and self.upstream_id is not None:

            upstream_targets_url = self.kong_base_url.with_path(
                f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/{self.TARGETS_RESOURCE}/")

            targets = self._list_resources(upstream_targets_url)

            #     search for current ip
            target = self.target
            for t in targets:
                if t['target'] == target:
                    target_id = t['id']
                    message = "Already Registered Target {target} as {target_id} for {service_host}"
                    break
            else:
                target_object = {
                    "target": target
                }
                target_post_request = urllib.request.Request(
                    str(self.kong_base_url.with_path(
                        f"/{self.UPSTREAMS_RESOURCE}/{self.upstream_id}/{self.TARGETS_RESOURCE}")),
                    method="POST"
                )

                try:
                    kong_target_response = urlopen(target_post_request, target_object)
                    target_id = kong_target_response['id']
                    message = "Registered Target {target} as {target_id} for {service_host}"
                except urllib.error.HTTPError:
                    self.logger_target("critical",
                                       f"FAILED: registering target {target}: {kong_target_response}")
                    raise

            self.target_id = target_id
            self.logger_target("debug",
                               message.format(target=target, target_id=self.target_id,
                                              service_host=self.kong_service_host))

    def remove_duplicate_route(self, route):
        """
        removes duplicate routes

        :param route:
        :type route: dict with route data
        :return:
        """
        delete_request = urllib.request.Request(
            str(self.kong_base_url.with_path(
                f"/{self.SERVICES_RESOURCE}/{self.service_id}/{self.ROUTES_RESOURCE}/{route['id']}"),
            ),
            method="DELETE"
        )
        try:
            urlopen(delete_request)
            self.logger_route("debug", f"Duplicate route deleted: {route['id']}")
        except urllib.error.HTTPError:
            self.logger_route("critical", f"Failed to delete duplicate route : {route['id']}")

    def register_routes(self):
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
                routes = self._list_resources(list_service_routes_url)
                registered_routes = []
                for r in routes:
                    if r not in registered_routes:
                        registered_routes.append(r)
                    else:
                        self.remove_duplicate_route(r)

                for url, route_info in public_routes.items():
                    path = normalize_url_for_kong(url)
                    route_data = Route(paths=path, methods=route_info['public_methods'])

                    for rr in registered_routes:
                        if rr == route_data:
                            message = f"Already Registered Route {path} as {route_data['id']} on {self.kong_service_name}."
                            self.routes.update({route_data['id']: route_data})
                            self.logger_route("debug", message)
                            break
                    else:
                        route_data.update_service_id(self.service_id)
                        post_request = urllib.request.Request(
                            str(self.kong_base_url.with_path(f'/{self.ROUTES_RESOURCE}/')),
                            method='POST'
                        )

                        try:
                            route_response = urlopen(post_request, route_data)
                            self.enable_plugins(route_info, route_response, route_data)
                        except urllib.error.HTTPError as e:
                            resp = e.read().decode()
                            self.logger_route("critical",
                                              f"FAILED registering route {route_data['paths']} "
                                              f"on {self.kong_service_name}: {resp}")
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
                self.logger_route("debug", "No Public routes found.")
                self.deregister_service()
        else:
            raise RuntimeError(
                self.logger_create_message("routes", "Need to register service before registering routes!"))

    def deregister_routes(self):

        # asyncio gather seems unstable
        if self.ROUTES_RESOURCE in self.registered_instance:

            routes = self.registered_instance[self.ROUTES_RESOURCE][:]
            for r in routes:
                self.disable_plugins(r)

                delete_request = urllib.request.Request(
                    str(self.kong_base_url.with_path(f'/routes/{r}')),
                    method='DELETE'
                )

                try:
                    urlopen(delete_request)
                except urllib.error.HTTPError as e:
                    resp = e.read().decode()
                    self.logger_route("critical",
                                      f"FAILED deregistering route {r} "
                                      f"on {self.kong_service_name}: {resp}")
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

    def enable_plugins(self, route_info, route_resp, route_data):
        # attach plugins
        for plugin in route_info['plugins']:
            payload = {"name": plugin}

            # If 'jwt' plugin should be enabled, then should provide anonymous consumer id.
            if plugin == 'jwt':
                get_request = urllib.request.Request(
                    str(self.kong_base_url.with_path(f"/{self.CONSUMERS_RESOURCE}/anonymous/")),
                    method='GET'
                )

                try:
                    response = urlopen(get_request)
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        post_request = urllib.request.Request(
                            str(self.kong_base_url.with_path(f"/{self.CONSUMERS_RESOURCE}/")),
                            data={'username': 'anonymous'}
                        )

                        try:
                            response = urlopen(post_request)
                        except urllib.error.HTTPError as e:
                            resp = e.read().decode()
                            self.logger_route("critical", f"FAILED creating anonymous consumer: {resp}")
                            raise
                        else:
                            self.logger_route("info",
                                              f"Consumer {post_request['id']} was created as anonymous user "
                                              f"by {self.kong_service_name}")
                    else:
                        resp = e.read().decode()
                        self.logger_route("critical", f"FAILED creating anonymous consumer: {resp}")
                        raise

                payload.update({
                    'config.anonymous': response['id'],
                    'config.claims_to_verify': 'exp'
                })

            plugin_post_request = urllib.request.Request(
                str(self.kong_base_url.with_path(
                    f"/{self.ROUTES_RESOURCE}/{route_resp['id']}/{self.PLUGINS_RESOURCE}/")),
                method="POST"
            )

            try:
                urlopen(plugin_post_request, payload)
            except urllib.error.HTTPError:
                self.logger_route("critical",
                                  f"FAILED "
                                  f"enabling {plugin} plugin for route {route_data['paths']} "
                                  f"on {self.kong_service_name}: {route_resp['id']}")
                raise
            else:
                self.logger_route("debug",
                                  f"Enabled {plugin} plugin for route {route_resp['paths']}"
                                  f" as {route_resp['id']} on {self.kong_service_name}")

    def disable_plugins(self, route_id):
        plugins = []
        base_url = self.kong_base_url.with_path(f"/plugins").with_query({'route_id': route_id})

        plugins = self._list_resources(base_url)

        for p in plugins:
            delete_request = urllib.request.Request(
                str(self.kong_base_url.with_path(f"/plugins/{p['id']}")),
                method='DELETE'
            )
            try:
                urlopen(delete_request)
            except urllib.error.HTTPError as e:
                resp = e.read().decode()
                self.logger_route("critical", f"FAILED disabling plugin: {p} on {self.kong_service_name} "
                                              f"with status_code {e.code}: {resp}")
            else:
                self.logger_route("debug", f"Plugin disabled: {p['name']} on {self.kong_service_name}")

gateway = KongGateway()
