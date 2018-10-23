import asyncio
import json

from insanic.conf import settings

from aio_pika import DeliveryMode, Message, ExchangeType

from .connections import RabbitMQConnectionHandler


def make_pika_message(message, is_persistent=True):
    message = json.dumps(message).encode('utf8')
    delivery_mode = None

    if is_persistent:
        delivery_mode = DeliveryMode.PERSISTENT

    message = Message(
        message,
        delivery_mode=delivery_mode
    )

    return message


def get_dict_from_pika_msg(message):
    return json.loads(message.body.decode('utf8'))


async def fire_a_msg_via_rabbit(routing_key, message: dict, exchange_name=settings.SERVICE_NAME):
    channel = RabbitMQConnectionHandler.channel()

    exchange = await channel.declare_exchange(
        exchange_name, ExchangeType.TOPIC, durable=True
    )

    message = make_pika_message(message)

    await exchange.publish(
        message, routing_key=routing_key
    )


# async def fire_ip(message, routing_key="userip"):
#     message = make_pika_message(message)
#     channel = RabbitMQConnectionHandler.channel()
#
#     await channel.default_exchange.publish(
#         message,
#         routing_key=routing_key
#     )
#
#     RabbitMQConnectionHandler.logger('info', f" Sent {message.body}")
