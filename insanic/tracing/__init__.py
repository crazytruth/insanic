import importlib
import socket

from insanic.conf import settings
from insanic.log import logger
from insanic.tracing.tracer import InsanicXRayMiddleware
from insanic.tracing.sampling import Sampler

from aws_xray_sdk.core import patch

class InsanicTracer:

    @classmethod
    def _handle_error(cls, app, messages):
        error_message = "Tracing was not initialized because: " + ', '.join(messages)

        # if app.config.get('MMT_ENV', 'local') not in app.config.TRACING['FAIL_SOFT_ENVIRONMENTS'] \
        #         and app.config.TRACING_REQUIRED:
        if not app.config.TRACING_SOFT_FAIL and app.config.TRACING_REQUIRED:
            logger.critical(error_message)
            raise EnvironmentError(error_message)
        else:
            logger.warn(error_message)

    @classmethod
    def _check_prerequisites(cls, app):
        messages = []

        if importlib.util.find_spec('aws_xray_sdk') is None:
            messages.append('Tracing dependency [aws_xray_sdk] was not found!')

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            socket.gethostbyname(app.config.TRACING_HOST)
            sock.settimeout(1)
            if sock.connect_ex((app.config.TRACING_HOST, int(app.config.TRACING_PORT))) != 0:
                messages.append(
                    f"Could not connect to port on [{app.config.TRACING_HOST}:{app.config.TRACING_PORT}].")
        except socket.gaierror:
            messages.append(f"Could not resolve host [{app.config.TRACING_HOST}].")
        except Exception:
            messages.append(f"Could not connect to [{app.config.TRACING_HOST}:{app.config.TRACING_PORT}].")
        finally:
            sock.close()
        return messages

    @classmethod
    def init_app(cls, app):
        # checks to see if tracing can be enabled

        if app.config.TRACING_ENABLED:
            messages = cls._check_prerequisites(app)
            if len(messages) == 0:
                if not hasattr(app, 'tracer'):
                    @app.listener('after_server_start')
                    async def after_server_start_start_tracing(app, loop=None, **kwargs):
                        app.tracer = InsanicXRayMiddleware(app, loop)

                    patch(("aiobotocore", "pynamodb"))

                app.sampler = Sampler(app)
            else:
                cls._handle_error(app, messages)
                settings.TRACING_ENABLED = False
