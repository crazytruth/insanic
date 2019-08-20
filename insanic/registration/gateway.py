import aiohttp
import logging

from aiohttp.client_exceptions import ClientConnectorError
from functools import wraps
from multiprocessing import current_process
from packaging import version
from urllib.error import URLError

from insanic.conf import settings
from insanic.log import logger


def http_session_manager(f):
    @wraps(f)
    async def wrapper(self, *args, **kwargs):

        session = kwargs.get('session', None)

        _session = session or self.session

        if _session is None:
            _session = session = aiohttp.ClientSession()

        kwargs.update({"session": _session})

        await f(self, *args, **kwargs)

        if session is not None and self.session != session:
            await session.close()

    return wrapper


def normalize_url_for_kong(url):
    if url.startswith('^'):
        url = url[1:]

    return url


class BaseGateway:

    def __init__(self):
        self._enabled = None
        self.routes = {}
        self.session = None
        self.is_context_session = False

    # @property
    # def enabled(self):
    #     if self._enabled is None:
    #         self._enabled = settings.GATEWAY_REGISTRATION_ENABLED
    #     return self._enabled

    @property
    def app(self):
        if self._app is None:
            raise RuntimeError("app is not set for this gateway.")
        return self._app

    @app.setter
    def app(self, value):
        self._app = value

    @property
    def service_version(self):
        v = version.parse(settings.SERVICE_VERSION)
        if not hasattr(v, "release"):
            v = v._version

        return ".".join([str(i) for i in v.release[:3]])

    def logger_create_message(self, module, message):
        namespace = self.__class__.__name__.upper().replace("GATEWAY", "")
        return f"[{namespace}][{module.upper()}] {message}"

    def logger(self, level, message, module="GENERAL", *args, **kwargs):
        if not isinstance(level, int):
            log_level = logging._nameToLevel.get(level.upper(), None)

            if log_level is None:
                if logger.raiseExceptions:
                    raise TypeError(
                        "Unable to resolve level. Must be one of {}.".format(", ".join(logging._nameToLevel.keys())))
                else:
                    return
        else:
            log_level = level

        message = self.logger_create_message(module, message)
        logger.log(log_level, message, *args, **kwargs)

    def logger_service(self, level, message, *args, **kwargs):
        self.logger(level, message, "SERVICE", *args, **kwargs)

    def logger_route(self, level, message, *args, **kwargs):
        self.logger(level, message, "ROUTE", *args, **kwargs)

    def logger_upstream(self, level, message, *args, **kwargs):
        self.logger(level, message, "UPSTREAM", *args, **kwargs)

    def logger_target(self, level, message, *args, **kwargs):
        self.logger(level, message, "TARGET", *args, **kwargs)

    @property
    def enabled(self):
        _cp = current_process()

        if _cp.name == "MainProcess":
            return settings.GATEWAY_REGISTRATION_ENABLED
        elif _cp.name.startswith("Process-"):
            return settings.GATEWAY_REGISTRATION_ENABLED and _cp.name.replace("Process-", "") == "1"
        else:
            raise RuntimeError("Unable to resolve process name.")

    def _register(self):
        raise NotImplementedError(".register() must be overridden.")  # pragma: no cover

    def _deregister(self):
        raise NotImplementedError(".deregister() must be overridden.")  # pragma: no cover

    def register(self, app):
        self.app = app
        if self.enabled:
            try:
                self._register()
            except (ClientConnectorError, URLError):
                if settings.MMT_ENV in settings.KONG_FAIL_SOFT_ENVIRONMENTS:
                    self.logger_route('info', "Connection to gateway has failed. Soft failing registration.")
                elif settings.DEBUG:
                    self.logger_route('info', "Passing kong registration because debug mode!")
                else:
                    raise

    def deregister(self):
        """
        deregister is implemented as synchronous because we need to guarantee the clean up from kong.
        Making this async created problems where remaining tasks wouldn't be awaited for.
        """
        if self.enabled:
            try:
                result = self._deregister()
            except ClientConnectorError:
                if settings.MMT_ENV in settings.KONG_FAIL_SOFT_ENVIRONMENTS:
                    self.logger_route('info', "Connection to gateway has failed. Soft failing registration.")
                else:
                    raise

    # async def __aenter__(self):
    #     if self.session is None or (hasattr(self.session, 'closed') and self.session.closed):
    #         self.session = aiohttp.ClientSession()
    #         self.is_context_session = True
    #     return self
    #
    # async def __aexit__(self, exc_type, exc_val, exc_tb):
    #     if self.is_context_session:
    #         await self.session.close()
    #         self.is_context_session = False
    #         self.session = None
