import asyncio
import pytest

from aio_pika import IncomingMessage

from insanic.rabbitmq.connections import RabbitMQConnectionHandler
from insanic.rabbitmq.helpers import fire_a_msg_via_rabbit, get_dict_from_pika_msg

RABBITMQ_USERNAME = "guest"
RABBITMQ_PASSWORD = "guest"


class TestRabbitMQConnectionHandlerClass:

    @pytest.fixture(autouse=True)
    def clean_up(self):
        RabbitMQConnectionHandler.__instance = None
        RabbitMQConnectionHandler._conn = None
        RabbitMQConnectionHandler._channel = None

    def test_singleton(self):
        rabbit = RabbitMQConnectionHandler()
        rabbit2 = RabbitMQConnectionHandler()

        assert rabbit is RabbitMQConnectionHandler.instance()
        assert rabbit is rabbit2

    async def test_server_start_stop(self, rabbitmq_proc):
        rabbit = RabbitMQConnectionHandler()
        await rabbit.connect(
            rabbitmq_username=RABBITMQ_USERNAME, rabbitmq_password=RABBITMQ_PASSWORD,
            host=rabbitmq_proc.host, port=rabbitmq_proc.port)
        assert RabbitMQConnectionHandler.channel() is not None
        await rabbit.disconnect()
        assert RabbitMQConnectionHandler.channel() is None


class TestRabbitMQFireMessage:

    async def test_fire_a_msg_and_consume_message(self, rabbitmq_proc):
        rabbit = RabbitMQConnectionHandler()
        exchange_name = "test"
        queue_name = "test"
        routing_key = "test"
        routing_keys = [routing_key]
        message = {"id": "test"}
        message_2 = {"id": "test2"}

        result = None

        def on_message(incoming_message: IncomingMessage):
            with incoming_message.process():
                incoming_message_body_as_dict = get_dict_from_pika_msg(incoming_message)
                nonlocal result
                result = incoming_message_body_as_dict

        await rabbit.connect(
            rabbitmq_username=RABBITMQ_USERNAME, rabbitmq_password=RABBITMQ_PASSWORD,
            host=rabbitmq_proc.host, port=rabbitmq_proc.port)

        await rabbit.consume_queue(
            exchange_name=exchange_name, queue_name=queue_name, routing_keys=routing_keys, callback=on_message)

        await fire_a_msg_via_rabbit(
            routing_key=routing_key,
            exchange_name=exchange_name,
            message=message)

        assert result == message

        await fire_a_msg_via_rabbit(
            routing_key=routing_key,
            exchange_name=exchange_name,
            message=message_2)

        assert result != message

        await RabbitMQConnectionHandler.disconnect()
