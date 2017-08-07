from sanic import Sanic
from sanic_useragent import SanicUserAgent

from pathlib import Path
from peewee_async import PooledMySQLDatabase

from insanic.conf import settings
from insanic.connections import connect_database, close_database
from insanic.handlers import ErrorHandler
from insanic.log import LOGGING
from insanic.protocol import InsanicHttpProtocol
from insanic.tracer import InsanicTracer, IncendiaryTracer
from insanic.utils import attach_middleware



class Insanic(Sanic):
    database = None

    def __init__(self, name, router=None, error_handler=None, app_config=()):

        if error_handler is None:
            error_handler = ErrorHandler()

        for c in app_config:
            try:
                settings.from_pyfile(c)
            except TypeError:
                settings.from_object(c)
            except FileNotFoundError:
                pass


        super().__init__(name, router, error_handler, log_config=LOGGING)
        # super().__init__(name, router, error_handler)
        self.config = settings
        #
        # for c in app_config:
        #     try:
        #         self.config.from_pyfile(c)
        #     except TypeError:
        #         self.config.from_object(c)
        #     except FileNotFoundError:
        #         pass

        SanicUserAgent.init_app(self)
        attach_middleware(self)

        self.database = PooledMySQLDatabase(None)

        self.listeners['after_server_start'].append(connect_database)
        self.listeners['before_server_stop'].append(close_database)

        #
        incendiary_tracer = IncendiaryTracer(service_name=self.config['SERVICE_NAME'],
                                             verbosity=2 if self.config['MMT_ENV'] == "local" else 0)
        self.tracer = InsanicTracer(incendiary_tracer, True, self, ['args', 'body',' content_type', 'cookies', 'data',
                                                                    'host', 'ip', 'method', 'path', 'scheme', 'url'])
        # # self.database.set_allow_sync(False)

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
        try:
            with open(Path(CURRENT_DIR, 'VERSION')) as f:
                insanic_version = f.read().strip()
        except:
            return "unknown"

    return insanic_version

