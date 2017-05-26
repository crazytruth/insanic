from sanic import Sanic
from sanic_useragent import SanicUserAgent

from pathlib import Path
from peewee_async import PooledMySQLDatabase

from insanic.conf import settings
from insanic.connections import connect_database, close_database
from insanic.handlers import ErrorHandler
from insanic.protocol import InsanicHttpProtocol
from insanic.utils import attach_middleware
from insanic.utils.log import LOGGING


class Insanic(Sanic):
    database = None

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

        self.database = PooledMySQLDatabase(self.config['WEB_MYSQL_DATABASE'],
                                            host=self.config['WEB_MYSQL_HOST'],
                                            port=self.config['WEB_MYSQL_PORT'],
                                            user=self.config['WEB_MYSQL_USER'],
                                            password=self.config['WEB_MYSQL_PASS'],
                                            min_connections=5, max_connections=10, charset='utf8', use_unicode=True)

        self.listeners['after_server_start'].append(connect_database)
        self.listeners['before_server_stop'].append(close_database)
        # self.database.set_allow_sync(False)

    def _helper(self, **kwargs):
        """Helper function used by `run` and `create_server`."""
        server_settings = super()._helper(**kwargs)
        server_settings['protocol'] = InsanicHttpProtocol
        return server_settings


CURRENT_DIR = Path(__file__).parent.parent
insanic_version = None

def get_insanic_version():

    global insanic_version
    if insanic_version is None:

        with open(Path(CURRENT_DIR, 'VERSION')) as f:
            insanic_version = f.read().strip()

    return insanic_version

