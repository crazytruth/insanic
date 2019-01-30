import asyncio
import logging

# from grpclib.server import Server
from grpclib.health.check import ServiceStatus
from grpclib.health.service import Health

from insanic.conf import settings
from insanic.grpc.dispatch.server import DispatchServer
from insanic.log import grpc_logger, logger
from insanic.utils import load_class

from .handlers import Server




class GRPCServer:
    """
    Singleton GRPCServer Instance
    """
    __instance = None
    _grpc_server = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)
        return cls.__instance

    @classmethod
    def instance(cls):
        return cls.__instance

    @classmethod
    async def stop(cls):
        if cls.__instance is not None:
            cls.logger('info', f"[GRPC] Closing GRPC.")
            if cls.__instance._grpc_server is not None:
                cls.__instance._grpc_server.close()
                await cls.__instance._grpc_server.wait_closed()
            cls.logger('info', f"[GRPC] Closed GRPC.")
            cls.__instance._grpc_server = None

    @classmethod
    def logger(cls, level, message, *args, **kwargs):
        """

        :param level: either int or case insensitive string representation of log level
            possible inputs: info, debug, CRITICAL, FATAL, ERROR, WARN, WARNING
        :param message:
        :param args:
        :param kwargs:
        :return:
        """
        if not isinstance(level, int):
            log_level = logging._nameToLevel.get(level.upper(), None)

            if log_level is None:
                if grpc_logger.raiseExceptions:
                    raise TypeError(
                        "Unable to resolve level. Must be one of {}.".format(", ".join(logging._nameToLevel.keys())))
                else:
                    return
        else:
            log_level = level

        message = message if message.startswith('[GRPC]') else f"[GRPC] {message}"

        grpc_logger.log(log_level, message, *args, **kwargs)

    def __init__(self, app, loop=None):
        """
        Initialize a singleton grpc server

        :param grpc_services: list if initialized grpc services
        :param loop: event loop instance, if none gets from asyncio
        """
        if self._grpc_server is not None:
            raise AssertionError("GRPC Server has already been initialized.")

        loop = loop or asyncio.get_event_loop()

        servers = [DispatchServer(app)]
        for s in settings.GRPC_SERVER:
            if isinstance(s, str):
                klass = load_class(s)
            else:
                klass = s

            servers.append(klass())
            logger.info(f"[GRPC] Preparing to load {klass.__module__}.{klass.__name__} for GRPC serving.")

        self.health = {s: [ServiceStatus(loop=loop)] for s in servers}
        self._grpc_server = Server(servers + [Health(self.health)], loop=loop)

    async def start(self, host, port, reuse_port=True, reuse_address=True):
        """
        Start the grpc server

        :param host: host to serve grpc on
        :param port: port to serve grpc on
        :param reuse_port:
        :param reuse_address:
        :return:
        """
        self._host = host
        self._port = port

        await self._grpc_server.start(host=host, port=port, reuse_port=reuse_port, reuse_address=reuse_address)
        self.logger('info', f"[GRPC] Serving GRPC from {host}:{port}")

    def set_status(self, status):
        """
        Sets the status of the grpc services

        :param status: Status of the grpc service True: healthy, False: Not healthy, None: unknow
        :return:
        """
        for _, checks in self.health.items():
            for c in checks:
                if isinstance(c, ServiceStatus):
                    c.set(status)
