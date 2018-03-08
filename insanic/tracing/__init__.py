import importlib
import socket

from insanic.log import logger
from insanic.tracing.tracer import InsanicXRayMiddleware
from insanic.tracing.sampling import Sampler

class InsanicTracer:

    @classmethod
    def _handle_error(cls, app, messages):
        error_message = "Tracing was not initialized because: " + ', '.join(messages)

        if app.config.get('MMT_ENV', 'local') not in app.config.TRACING['FAIL_SOFT_ENVIRONMENTS'] \
                and app.config.TRACING['REQUIRED']:
            logger.critical(error_message)
            raise EnvironmentError(error_message)
        else:
            logger.warn(error_message)

    @classmethod
    def _check_prerequisites(cls, app):
        messages = []

        if importlib.util.find_spec('aws_xray_sdk') is None:
            messages.append('Tracing dependency [aws_xray_sdk] was not found!')

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            socket.gethostbyname(app.config.TRACING['HOST'])
            sock.settimeout(1)
            if sock.connect_ex((app.config.TRACING['HOST'], app.config.TRACING['PORT'])) != 0:
                messages.append(
                    f"Could not connect to port on [{app.config.TRACING['HOST']}:{app.config.TRACING['PORT']}].")
        except socket.gaierror:
            messages.append(f"Could not resolve host [{app.config.TRACING['HOST']}].")
        except Exception:
            messages.append(f"Could not connect to [{app.config.TRACING['HOST']}:{app.config.TRACING['PORT']}].")
        finally:
            sock.close()
        return messages

    @classmethod
    def init_app(cls, app):
        # checks to see if tracing can be enabled

        if app.config.TRACING['ENABLED']:
            messages = cls._check_prerequisites(app)
            if len(messages) == 0:
                @app.listener('after_server_start')
                async def after_server_start_start_tracing(app, loop=None, **kwargs):
                    app.tracer = InsanicXRayMiddleware(app, loop)

                app.sampler = Sampler(app)
            else:
                cls._handle_error(app, messages)
