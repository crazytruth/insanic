"""
Copyright (c) 2016-present Sanic Community

Modified for framework usage
"""

import os
import string
from asyncio import Protocol
from socket import socket
from ssl import SSLContext
from typing import Optional, Union, Type, Any

from sanic import Sanic

from insanic import __version__
from insanic.adapters import match_signature
from insanic.conf import settings
from insanic.exceptions import ImproperlyConfigured
from insanic.functional import empty
from insanic.handlers import ErrorHandler
from insanic.metrics import InsanicMetrics
from insanic.monitor import blueprint_monitor
from insanic.log import get_logging_config, error_logger, logger
from insanic.protocol import InsanicHttpProtocol
from insanic.router import InsanicRouter
from insanic.scopes import get_my_ip

LISTENER_TYPES = (
    "before_server_start",
    "after_server_start",
    "before_server_stop",
    "after_server_stop",
)
MIDDLEWARE_TYPES = ("request", "response")


class Insanic(Sanic):

    metrics = empty
    initialized_plugins = {}

    def __init__(self, name, router=None, error_handler=None, app_config=()):

        router = router or InsanicRouter()
        error_handler = error_handler or ErrorHandler()

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
        super().__init__(
            name,
            router,
            error_handler,
            strict_slashes=True,
            log_config=get_logging_config(),
            request_class=Request,
        )

        self.config = settings
        settings.SERVICE_NAME = service_name

        from insanic import listeners

        for module_name in dir(listeners):
            for listener in LISTENER_TYPES:
                if module_name.startswith(listener):
                    self.listeners[listener].append(
                        getattr(listeners, module_name)
                    )

        from insanic import middleware

        for module_name in dir(middleware):
            for m in MIDDLEWARE_TYPES:
                if module_name.startswith(m):
                    self.register_middleware(
                        getattr(middleware, module_name), attach_to=m
                    )

        self.blueprint(
            blueprint_monitor, url_prefix=f"/{settings.SERVICE_NAME}"
        )

        def _service_version():
            import importlib

            try:
                return importlib.import_module(
                    f"{settings.SERVICE_NAME}"
                ).__version__

            except (ImportError, AttributeError):
                error_logger.critical(
                    "Please put `__version__ = 'X.X.X'`in your __init__.py"
                )
                if settings.MMT_ENV == "test":
                    return "0.0.0.dev0"
                else:
                    raise

        service_version = _service_version()
        settings.SERVICE_VERSION = service_version
        logger.debug(
            f"{settings.SERVICE_NAME} v{settings.SERVICE_VERSION} service loaded."
        )

        self.metrics = InsanicMetrics
        self.metrics.META.info(
            {
                "service": service_name,
                "service_version": service_version,
                "status": "OK",
                "insanic_version": __version__,
                "ip": get_my_ip(),
            }
        )

        self.initialized_plugins = {}

    def verify_plugin_requirements(self):
        """
        Checks if the required plugins set in `REQUIRED_PLUGINS` have been
        installed and initialized.

        :return:
        """

        for plugin in self.config.REQUIRED_PLUGINS:
            if plugin not in self.initialized_plugins.keys():
                raise ImproperlyConfigured(
                    f"{plugin} is defined in `REQUIRED_PLUGINS` in this "
                    f"environment but has not been initialized."
                )

    def plugin_initialized(self, plugin_name, instance):
        self.initialized_plugins.update({plugin_name: instance})

    def run(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        *,
        debug: bool = False,
        ssl: Union[dict, SSLContext, None] = None,
        sock: Optional[socket] = None,
        workers: int = 1,
        protocol: Optional[Type[Protocol]] = InsanicHttpProtocol,
        backlog: int = 65535,
        stop_event: Any = None,
        register_sys_signals: bool = True,
        access_log: Optional[bool] = True,
        # for sanic>20.6
        auto_reload: Optional[bool] = None,
        unix: Optional[str] = None,
        **kwargs,
    ):
        """Run the HTTP Server and listen until keyboard interrupt or term
        signal. On termination, drain connections before closing.

        :param host: Address to host on
        :type host: str
        :param port: Port to host on
        :type port: int
        :param debug: Enables debug output (slows server)
        :type debug: bool
        :param auto_reload: Reload app whenever its source code is changed.
                            Enabled by default in debug mode.
        :type auto_relaod: bool
        :param ssl: SSLContext, or location of certificate and key
                    for SSL encryption of worker(s)
        :type ssl: SSLContext or dict
        :param sock: Socket for the server to accept connections from
        :type sock: socket
        :param workers: Number of processes received before it is respected
        :type workers: int
        :param protocol: Subclass of asyncio Protocol class
        :type protocol: type[Protocol]
        :param backlog: a number of unaccepted connections that the system
                        will allow before refusing new connections
        :type backlog: int
        :param stop_event: event to be triggered
                           before stopping the app - deprecated
        :type stop_event: None
        :param register_sys_signals: Register SIG* events
        :type register_sys_signals: bool
        :param access_log: Enables writing access logs (slows server)
        :type access_log: bool
        :param unix: Unix socket to listen on instead of TCP port
        :type unix: str
        :return: Nothing
        """

        logger.info(f"ATTEMPTING TO RUN INSANIC ON {host}:{port}")
        signature = match_signature(
            super(self.__class__, self).run,
            host=host,
            port=port,
            debug=debug,
            ssl=ssl,
            sock=sock,
            workers=workers,
            protocol=protocol,
            backlog=backlog,
            stop_event=stop_event,
            register_sys_signals=register_sys_signals,
            access_log=access_log,
            auto_reload=auto_reload,
            unix=unix,
            **kwargs,
        )

        super().run(**signature)

    def _helper(
        self,
        host=None,
        port=None,
        debug=False,
        ssl=None,
        sock=None,
        workers=1,
        loop=None,
        protocol=InsanicHttpProtocol,
        backlog=100,
        stop_event=None,
        register_sys_signals=True,
        run_async=False,
        auto_reload=False,
        **kwargs,
    ):

        if port:
            settings.SERVICE_PORT = port

        try:
            workers = int(os.environ.get("INSANIC_WORKERS", workers))
        except ValueError:
            workers = workers

        settings.WORKERS = workers

        signature = match_signature(
            super(self.__class__, self)._helper,
            host=host,
            port=port,
            debug=debug,
            ssl=ssl,
            sock=sock,
            workers=workers,
            loop=loop,
            protocol=protocol,
            backlog=backlog,
            stop_event=stop_event,
            register_sys_signals=register_sys_signals,
            run_async=run_async,
            auto_reload=auto_reload,
            **kwargs,
        )

        server_settings = super()._helper(**signature)
        return server_settings
