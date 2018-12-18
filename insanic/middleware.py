import asyncio

import aiotask_context

from insanic.conf import settings
from insanic.log import logger
from insanic.rabbitmq.connections import RabbitMQConnectionHandler


def request_middleware(request):
    aiotask_context.set(settings.TASK_CONTEXT_CORRELATION_ID,
                        request.id)


async def response_userip_middleware(request, response):

    try:
        user = await request.user
        service = await request.service
        service_name = settings.SERVICE_NAME
    except Exception:
        if settings.LOG_IP_FAIL_TYPE == "soft":
            pass
        else:
            raise
    else:
        if user.is_authenticated and not service.is_authenticated and service_name != 'userip':
            try:
                if not request.client_ip:
                    logger.warn(f"warning: client_ip value is None\n"
                                f"requester's ip: {request.ip}\n"
                                f"requester's headers: {request.headers}")
                    return

                message = {'user_id': user.id, 'ip_addr': request.client_ip}
                asyncio.ensure_future(fire_message_to_rabbitmq(message))

                if settings.MMT_ENV == "test":
                    response.headers["userip"] = "fired"

            except:
                pass


async def fire_message_to_rabbitmq(message):
    exchange_name = 'userip'
    routing_key = 'userip.create'

    rabbit = RabbitMQConnectionHandler.instance()
    await rabbit.produce_message(routing_key=routing_key, message=message, exchange_name=exchange_name)
    logger.info(f'message fired: {message}')
