import asyncio
import json

from aio_pika import DeliveryMode, Message

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


async def fire_ip(message, routing_key="userip"):
    message = make_pika_message(message)
    channel = RabbitMQConnectionHandler.channel()

    await channel.default_exchange.publish(
        message,
        routing_key=routing_key
    )

    RabbitMQConnectionHandler.logger('info', f" Sent {message.body}")
