from sanic import Sanic
from sanic_useragent import SanicUserAgent

from peewee_async import PooledMySQLDatabase

try:
    import config
except ImportError:
    config = {}

try:
    import instance
except ImportError:
    instance = {}

from .conf import settings
from .handlers import ErrorHandler
from .utils import attach_middleware

class Insanic(Sanic):

    def __init__(self, name, router=None, error_handler=None, app_config=()):

        if error_handler is None:
            error_handler = ErrorHandler()

        super().__init__(name, router, error_handler)
        self.config = settings

        SanicUserAgent.init_app(self)
        attach_middleware(self)

        self.config.from_object(config)
        self.config.from_object(instance)

        for c in app_config:
            try:
                self.config.from_pyfile(c)
            except TypeError:
                self.config.from_object(c)

        self.database = PooledMySQLDatabase(self.config['MYSQL_DATABASE'],
                                            host=self.config['MYSQL_HOST'],
                                            port=self.config['MYSQL_PORT'],
                                            user=self.config['MYSQL_USER'],
                                            password=self.config['MYSQL_PWD'],
                                            min_connections=5, max_connections=10)
#
#
# apps = {}
#
# def get_app(service):
#     if service in apps:
#         return apps[service]
#
#     app = Sanic(__name__, error_handler=ErrorHandler())
#
#     SanicUserAgent.init_app(app)
#     attach_middleware(app)
#
#     app.config.from_object(config)
#     app.config.from_object(instance)
#
#     apps[service] = app
#     return apps[service]
