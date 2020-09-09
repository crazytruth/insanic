"""
Copyright (c) 2016-present Sanic Community

Modified for framework usage
"""

from asyncio import Protocol
from socket import socket
from ssl import SSLContext
from typing import Optional, Union, Type, Any, Iterable

from sanic import Sanic

from insanic import __version__
from insanic.adapters import match_signature
from insanic.conf import settings
from insanic.exceptions import ImproperlyConfigured
from insanic.functional import empty
from insanic.handlers import ErrorHandler
from insanic.metrics import InsanicMetrics
from insanic.monitor import blueprint_monitor
from insanic.log import get_logging_config, logger
from insanic.protocol import InsanicHttpProtocol
from insanic.request import Request
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

    def __init__(
        self,
        name: str,
        router: Optional[InsanicRouter] = None,
        error_handler: Optional[ErrorHandler] = None,
        load_env: bool = True,
        request_class: Optional[Request] = None,
        strict_slashes: bool = True,
        log_config: Optional[dict] = None,
        configure_logging: bool = True,
        # insanic specific arguments
        *,
        app_config: Iterable[Union[str, object]] = (),
        version: Optional[str] = None,
        initialize_insanic_listeners: bool = True,
        initialize_insanic_middlewares: bool = True,
        attach_monitor_endpoints: bool = True,
    ) -> None:
        """
        Initialize Insanic Application.

        :param name:
        :param router:
        :param error_handler:
        :param load_env:
        :param request_class:
        :param strict_slashes:
        :param log_config:
        :param configure_logging:
        :param app_config: order matters! Any configs later in the
                iterable will overwrite previous set settings
        :param version:
        :param initialize_insanic_listeners:
        :param initialize_insanic_middlewares:
        :param attach_monitor_endpoints:
        """
        router = router or InsanicRouter()
        error_handler = error_handler or ErrorHandler()
        request_class = request_class or Request
        log_config = log_config or get_logging_config()

        super().__init__(
            name=name,
            router=router,
            error_handler=error_handler,
            load_env=load_env,
            request_class=request_class,
            strict_slashes=strict_slashes,
            log_config=log_config,
            configure_logging=configure_logging,
        )

        self.initialized_plugins = {}

        for c in app_config:
            settings.from_object(c)

        settings.SERVICE_NAME = name
        self.configure_version(version)

        # replace sanic's config with insanic's config
        self.config = settings
        if initialize_insanic_listeners:
            self.initialize_listeners()
        if initialize_insanic_middlewares:
            self.initialize_middleware()
        if attach_monitor_endpoints:
            self.blueprint(
                blueprint_monitor, url_prefix=f"/{settings.SERVICE_NAME}"
            )
            self.metrics = InsanicMetrics
            self.metrics.META.info(
                {
                    "service": name,
                    "application_version": settings.APPLICATION_VERSION,
                    "status": "OK",
                    "insanic_version": __version__,
                    "ip": get_my_ip(),
                }
            )

        logger.debug(
            f"{settings.SERVICE_NAME} v{settings.APPLICATION_VERSION} service loaded."
        )

    def configure_version(self, version: str) -> None:
        """
        Configures the application version and sets the
        version on settings. This is especially
        necessary for microservices.

        Precedence
        1. `version` argument
        2. APPLICATION_VERSION in settings
        3. defaults to `UNKNOWN`

        :param version: version of the service or application
        :return:
        """

        if (
            settings.ENFORCE_APPLICATION_VERSION
            and version is None
            and settings.APPLICATION_VERSION is None
        ):
            raise ImproperlyConfigured(
                "`version` must be included. Either set "
                "`ENFORCE_APPLICATION_VERSION` to False or include "
                "`version` when initializing Insanic. Or just include "
                "`APPLICATION_VERSION` in your config.`"
            )
        settings.APPLICATION_VERSION = (
            version or settings.APPLICATION_VERSION or "UNKNOWN"
        )

    def initialize_listeners(self) -> None:
        """
        Initializes the default listeners for insanic.

        :return:
        """

        from insanic import listeners

        for module_name in dir(listeners):
            for listener in LISTENER_TYPES:
                if module_name.startswith(listener):
                    self.register_listener(
                        getattr(listeners, module_name), listener
                    )

    def initialize_middleware(self) -> None:
        """
        Initializes default middlewares for insanic.

        :return:
        """
        from insanic import middleware

        for module_name in dir(middleware):
            for m in MIDDLEWARE_TYPES:
                if module_name.startswith(m):
                    self.register_middleware(
                        getattr(middleware, module_name), attach_to=m
                    )

    def verify_plugin_requirements(self) -> None:
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

    def plugin_initialized(self, plugin_name: str, instance: Any) -> None:
        """
        Interface to attach plugin for plugin developers to use.
        After initialization of plugin, call this!

        >>> app.plugin_initialized('name_of_plugin', self)

        :param plugin_name:
        :param instance:
        :return:
        """
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

        Insanic overrides this because we want to use `InsanicHttpProtocol`
        instead of Sanic's HttpProtocol.

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

        # need to do this here because port could change
        settings.SERVICE_PORT = server_settings.get("port")

        return server_settings
