import asyncio
import sys
from sanic import Sanic
from sanic.config import LOGGING
from sanic_useragent import SanicUserAgent

from peewee_async import PooledMySQLDatabase

from insanic.conf import settings
from insanic.connections import connect_database, close_database
from insanic.handlers import ErrorHandler
from insanic.protocol import InsanicHttpProtocol
from insanic.utils import attach_middleware

LOGGING['handlers']['accessTimedRotatingFile']['filename'] = "/tmp/access.log"
LOGGING['handlers']['errorTimedRotatingFile']['filename'] = "/tmp/error.log"
LOGGING['formatters'].update({"threads": {
    'format': '%(asctime)s - (%(name)s)[%(levelname)s]: %(threadName)10s %(name)18s: %(message)s',
    'datefmt': '%Y-%m-%d %H:%M:%S'
}})
LOGGING['handlers'].update({'threads_internal': {
    'class': 'logging.StreamHandler',
    'filters': ['accessFilter'],
    'formatter': 'threads',
    'stream': sys.stderr
}})
LOGGING['loggers'].update({"threads": {
    'level': 'DEBUG',
    'handlers': ['threads_internal']
}
})


class Insanic(Sanic):

    def __init__(self, name, router=None, error_handler=None, app_config=()):

        if error_handler is None:
            error_handler = ErrorHandler()

        super().__init__(name, router, error_handler, log_config=LOGGING)
        self.config = settings

        for c in app_config:
            try:
                self.config.from_pyfile(c)
            except TypeError:
                self.config.from_object(c)
            except FileNotFoundError:
                pass

        SanicUserAgent.init_app(self)
        attach_middleware(self)

        # self.database = PooledMySQLDatabase(self.config['WEB_MYSQL_DATABASE'],
        #                                     host=self.config['WEB_MYSQL_HOST'],
        #                                     port=self.config['WEB_MYSQL_PORT'],
        #                                     user=self.config['WEB_MYSQL_USER'],
        #                                     password=self.config['WEB_MYSQL_PWD'],
        #                                     min_connections=5, max_connections=10, charset='utf8', use_unicode=True)

        self.listeners['after_server_start'].append(connect_database)
        self.listeners['before_server_stop'].append(close_database)
        # self.database.set_allow_sync(False)

    def _helper(self, **kwargs):
        """Helper function used by `run` and `create_server`."""
        server_settings = super()._helper(**kwargs)
        server_settings['protocol'] = InsanicHttpProtocol
        return server_settings
