from sanic import Sanic
from sanic_useragent import SanicUserAgent

from insanic.functional import empty
from insanic.handlers import ErrorHandler
from insanic.monitor import blueprint_monitor
from insanic.log import get_logging_config, error_logger
from insanic.protocol import InsanicHttpProtocol

from insanic.tracing import InsanicTracer

LISTENER_TYPES = ("before_server_start", "after_server_start", "before_server_stop", "after_server_stop")
MIDDLEWARE_TYPES = ('request', 'response')


class Insanic(Sanic):
    database = None
    _public_routes = empty

    def __init__(self, name, router=None, error_handler=None, app_config=()):

        if error_handler is None:
            error_handler = ErrorHandler()

        from insanic.conf import settings
        self.version = ""

        for c in app_config:
            try:
                settings.from_pyfile(c)
            except TypeError:
                settings.from_object(c)
            except FileNotFoundError:
                pass

        from insanic.request import Request
        super().__init__(name, router, error_handler, strict_slashes=True, log_config=get_logging_config(),
                         request_class=Request)

        self.config = settings
        settings.SERVICE_NAME = name.split('.', 1)[0]

        from insanic import listeners
        for module_name in dir(listeners):
            for l in LISTENER_TYPES:
                if module_name.startswith(l):
                    self.listeners[l].append(getattr(listeners, module_name))

        from insanic import middleware
        for module_name in dir(middleware):
            for m in MIDDLEWARE_TYPES:
                if module_name.startswith(m):
                    self.register_middleware(getattr(middleware, module_name), attach_to=m)

        self.blueprint(blueprint_monitor, url_prefix=f"/{name}")

    def run(self, host=None, port=None, debug=False, ssl=None,
            sock=None, workers=1, protocol=None,
            backlog=100, stop_event=None, register_sys_signals=True,
            access_log=True):
        SanicUserAgent.init_app(self)
        InsanicTracer.init_app(self)

        try:
            from infuse import Infuse
            Infuse.init_app(self)
        except (ImportError, ModuleNotFoundError):
            if self.config.get("MMT_ENV") == "production":
                error_logger.critical("[Infuse] is required for production deployment.")
                raise

        if protocol is None:
            protocol = InsanicHttpProtocol

        self._port = port

        super().run(host, port, debug, ssl, sock, workers, protocol,
                    backlog, stop_event, register_sys_signals,
                    access_log)

    def public_routes(self):
        if self._public_routes is empty:
            _public_routes = {}

            for url, route in self.router.routes_all.items():
                for method in route.methods:
                    if hasattr(route.handler, 'view_class'):
                        _handler = getattr(route.handler.view_class, method.lower())
                    else:
                        _handler = route.handler

                    if hasattr(_handler, "scope") and _handler.scope == "public":
                        # if method is decorated with public_facing, add to kong routes
                        if route.pattern.pattern not in _public_routes:
                            _public_routes[route.pattern.pattern] = []
                        _public_routes[route.pattern.pattern].append(method.upper())
            self._public_routes = _public_routes
        return self._public_routes
