import asyncio
import logging

from aio_pika import connect

from insanic.log import rabbitmq_logger


class RabbitMQConnectionHandler:
    """
    Singleton RabbitMQ Instance
    """

    __instance = None
    _conn = None
    _channel = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            cls.__instance = super().__new__(cls)

        return cls.__instance

    @classmethod
    def logger(cls, level, message, *args, **kwargs):
        if not isinstance(level, int):
            log_level = logging._nameToLevel.get(level.upper(), None)

            if log_level is None:

                if rabbitmq_logger.raiseExceptions:
                    raise TypeError(
                        "Unable to resolve level. Must be one of {}.".format(", ".join(logging._nameToLevel.keys())))
                else:
                    return
        else:
            log_level = level

        message = message if message.startswith('[RABBIT]') else f"[RABBIT] {message}"

        rabbitmq_logger.log(log_level, message, *args, **kwargs)

    @classmethod
    def instance(cls):
        return cls.__instance

    @classmethod
    async def disconnect(cls):
        if cls.__instance is not None:
            cls.logger('info', f"[RABBIT] Closing RabbitMQ connection.")
            await cls.__instance._conn.close()
            cls.logger('info', f"[RABBIT] Closed RabbitMQ connection.")
            cls.__instance._conn = None
            cls.__instance._channel = None
        else:
            cls.logger('info', f"[RABBIT] There is no RabbitMQ connection.")

    async def connect(self, rabbitmq_username, rabbitmq_password, host, port=5672, loop=None):
        """
        :param rabbitmq_username: username of RabbitMQ
        :param rabbitmq_password: password of RabbitMQ
        :param host: host of rabbitmq cluster
        :param port: port of rabbitmq cluster
        :param loop: event loop instance, if none gets from asyncio
        :return:
        """
        if loop is None:
            loop = asyncio.get_event_loop()

        if self._conn:
            raise AssertionError("RabbitMQ connection has already been initialized.")

        self._conn = await connect(
            f"amqp://{rabbitmq_username}:{rabbitmq_password}@{host}:{port}/", loop=loop
        )
        self._channel = await self._conn.channel()


