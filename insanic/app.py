from sanic import Sanic
from sanic_useragent import SanicUserAgent

from peewee_async import PooledMySQLDatabase

from insanic.handlers import ErrorHandler
from incendiary import redis
from insanic.monitor import blueprint_monitor
from insanic.log import LOGGING
from insanic.protocol import InsanicHttpProtocol
from insanic.tracer import InsanicTracer, IncendiaryTracer

from insanic.utils import attach_middleware

LISTENER_TYPES = ("before_server_start", "after_server_start", "before_server_stop", "after_server_stop")

class Insanic(Sanic):
    database = None

    def __init__(self, name, router=None, error_handler=None, app_config=()):

        if error_handler is None:
            error_handler = ErrorHandler()

        from insanic.conf import settings

        for c in app_config:
            try:
                settings.from_pyfile(c)
            except TypeError:
                settings.from_object(c)
            except FileNotFoundError:
                pass


        super().__init__(name, router, error_handler, log_config=LOGGING)

        self.config = settings

        SanicUserAgent.init_app(self)
        attach_middleware(self)

        self.database = PooledMySQLDatabase(None)

        from insanic import listeners
        for module_name in dir(listeners):
            for l in LISTENER_TYPES:
                if module_name.startswith(l):
                    self.listeners[l].append(getattr(listeners, module_name))

        incendiary_tracer = IncendiaryTracer(service_name=self.config['SERVICE_NAME'],
                                             verbosity=2 if self.config['MMT_ENV'] == "local" else 0)
        self.tracer = InsanicTracer(incendiary_tracer, True, self, ['args', 'body',' content_type', 'cookies', 'data',
                                                                    'host', 'ip', 'method', 'path', 'scheme', 'url'])
        # redis.init_tracing(incendiary_tracer)
        # # self.database.set_allow_sync(False)

        # add blueprint for monitor endpoints
        self.blueprint(blueprint_monitor)

    def _helper(self, **kwargs):
        """Helper function used by `run` and `create_server`."""
        server_settings = super()._helper(**kwargs)
        server_settings['protocol'] = InsanicHttpProtocol
        server_settings['request_timeout'] = 60
        return server_settings


