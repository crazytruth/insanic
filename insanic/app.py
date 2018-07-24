import os
import string

from sanic import Sanic
from sanic.views import CompositionView
from sanic_useragent import SanicUserAgent

from insanic.conf import settings
from insanic.functional import empty
from insanic.handlers import ErrorHandler
from insanic.monitor import blueprint_monitor
from insanic.log import get_logging_config, error_logger, logger
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

        service_name = ""

        for c in name:
            if c in string.ascii_lowercase:
                service_name += c
            else:
                break
        super().__init__(name, router, error_handler, strict_slashes=True, log_config=get_logging_config(),
                         request_class=Request)

        self.config = settings
        settings.SERVICE_NAME = service_name


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

        self.blueprint(blueprint_monitor, url_prefix=f"/{settings.SERVICE_NAME}")

        def _service_version():
            import importlib
            try:
                return importlib.import_module(f'{settings.SERVICE_NAME}').__version__

            except (ModuleNotFoundError, ImportError, AttributeError):
                error_logger.critical("Please put `__version__ = 'X.X.X'`in your __init__.py")
                if settings.MMT_ENV == "test":
                    return "0.0.0.dev0"
                else:
                    raise

        settings.SERVICE_VERSION = _service_version()
        logger.info(f"{settings.SERVICE_NAME} v{settings.SERVICE_VERSION} service loaded.")
        self.attach_plugins()

    def attach_plugins(self):
        SanicUserAgent.init_app(self)
        InsanicTracer.init_app(self)

        try:
            from infuse import Infuse
            Infuse.init_app(self)
            logger.info("[INFUSE] hooked and good to go!")
        except (ImportError, ModuleNotFoundError) as e:
            if self.config.get("MMT_ENV") == "production":
                error_logger.critical("[INFUSE] Infuse is required for production deployment.")
                raise
            else:
                error_logger.info(f"[INFUSE] proceeding without infuse. {e.msg}")

    def _helper(self, host=None, port=None, debug=False,
                ssl=None, sock=None, workers=1, loop=None,
                protocol=InsanicHttpProtocol, backlog=100, stop_event=None,
                register_sys_signals=True, run_async=False, access_log=True):

        protocol = InsanicHttpProtocol

        try:
            self._port = int(port)
        except TypeError:
            self._port = 8000

        try:
            workers = int(os.environ.get('INSANIC_WORKERS', workers))
        except ValueError:
            workers = workers

        settings.WORKERS = workers

        server_settings = super()._helper(host, port, debug, ssl, sock, workers, loop,
                                          protocol, backlog, stop_event,
                                          register_sys_signals, run_async, access_log)
        return server_settings

    def public_routes(self):
        if self._public_routes is empty:
            _public_routes = {}

            for url, route in self.router.routes_all.items():
                for method in route.methods:
                    if hasattr(route.handler, 'view_class'):
                        _handler = getattr(route.handler.view_class, method.lower())
                    elif isinstance(route.handler, CompositionView):
                        _handler = route.handler.handlers[method.upper()].view_class
                        _handler = getattr(_handler, method.lower())
                    else:
                        _handler = route.handler

                    if hasattr(_handler, "scope") and _handler.scope == "public":
                        # if method is decorated with public_facing, add to kong routes
                        if route.pattern.pattern not in _public_routes:
                            _public_routes[route.pattern.pattern] = {'public_methods': [], 'plugins': set()}
                        _public_routes[route.pattern.pattern]['public_methods'].append(method.upper())

                # If route has been added to kong, enable some plugins
                if hasattr(route.handler, 'view_class') and route.pattern.pattern in _public_routes:
                    for ac in route.handler.view_class.authentication_classes:
                        plugin = settings.KONG_PLUGIN.get(ac.__name__)
                        if plugin:
                            _public_routes[route.pattern.pattern]['plugins'].add(plugin)

            self._public_routes = _public_routes
        return self._public_routes
