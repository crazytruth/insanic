import asyncio
import json

import aiotask_context
from aio_pika.exceptions import AMQPError

from insanic.conf import settings
from insanic.rabbitmq.helpers import fire_ip
from insanic.loading import get_service
from insanic.log import logger


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
            UseripService = get_service('userip')

            try:
                if request.client_ip:
                    asyncio.ensure_future(UseripService.http_dispatch(
                        'POST', '/api/v1/ip/',
                        include_status_code=True,
                        payload={'user_id': user.id, 'ip_addr': request.client_ip}
                    ))

                    if settings.MMT_ENV == "test":
                        response.headers["userip"] = "fired"
                else:
                    logger.warn(json.dumps({
                        'warning' : 'client_ip value is None.',
                        "requester's ip": request.ip,
                        "requester's headers": request.headers
                    }))
            except:
                pass
