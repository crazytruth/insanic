import asyncio
import logging
import ujson as json

from aio_pika import connect_robust
from aio_pika import DeliveryMode, Message, ExchangeType

from insanic.conf import settings
from insanic.services.utils import context_user, context_correlation_id
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
    def channel(cls):
        return cls.__instance._channel

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

    @staticmethod
    def make_pika_message(message: dict, is_persistent=True):

        message.update({
            "request_id": context_correlation_id(),
            "user": context_user(),
        })

        message = json.dumps(message).encode('utf8')
        delivery_mode = None

        if is_persistent:
            delivery_mode = DeliveryMode.PERSISTENT

        message = Message(
            message,
            delivery_mode=delivery_mode
        )

        return message

    @staticmethod
    def get_dict_from_pika_msg(message):
        return json.loads(message.body.decode('utf8'))

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

        self._conn = await connect_robust(
            f"amqp://{rabbitmq_username}:{rabbitmq_password}@{host}:{port}/", loop=loop
        )
        self.logger('info', f"[RABBIT] Rabbit is connected from {host}:{port}")
        self._channel = await self._conn.channel()

    async def consume_queue(self, exchange_name, queue_name, routing_keys: [], callback, prefetch_count=1):
        await self._channel.set_qos(prefetch_count)

        exchange = await self._channel.declare_exchange(
            exchange_name, ExchangeType.TOPIC, durable=True
        )

        queue = await self._channel.declare_queue(
            queue_name, durable=True
        )

        for routing_key in routing_keys:
            await queue.bind(exchange, routing_key=routing_key)

        await queue.consume(callback=callback)

    async def produce_message(self, routing_key, message: dict, exchange_name=settings.SERVICE_NAME):
        channel = self._channel
        exchange = await channel.declare_exchange(
            exchange_name,
            ExchangeType.TOPIC,
            durable=True
        )
        message = self.make_pika_message(message)

        await exchange.publish(
            message, routing_key=routing_key
        )
