from sanic import Sanic
from sanic_useragent import SanicUserAgent

from insanic.handlers import ErrorHandler
from insanic.monitor import blueprint_monitor
from insanic.log import get_logging_config, error_logger
from insanic.protocol import InsanicHttpProtocol

from insanic.tracing import InsanicTracer

LISTENER_TYPES = ("before_server_start", "after_server_start", "before_server_stop", "after_server_stop")
MIDDLEWARE_TYPES = ('request', 'response')


class Insanic(Sanic):
    database = None

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
        settings.SERVICE_NAME = name

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

        self.blueprint(blueprint_monitor)

    def run(self, *args, **kwargs):
        SanicUserAgent.init_app(self)
        InsanicTracer.init_app(self)

        try:
            from infuse import Infuse
            Infuse.init_app(self)
        except (ImportError, ModuleNotFoundError):
            if self.config.get("MMT_ENV") == "production":
                error_logger.critical("[Infuse] is required for production deployment.")
                raise

        if "protocol" not in kwargs:
            kwargs.update({"protocol": InsanicHttpProtocol})

        super().run(*args, **kwargs)
