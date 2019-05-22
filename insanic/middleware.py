import aiotask_context

from insanic.conf import settings
from insanic.log import logger


def request_middleware(request):
    request.app.metrics['request_count'].inc()
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
                if not request.remote_addr:
                    logger.warn(f"warning: remote_addr value is None\n"
                                f"requester's ip: {request.remote_addr}\n"
                                f"requester's headers: {request.headers}")
                    return

                message = {'user_id': user.id, 'ip_addr': request.remote_addr}
                # asyncio.ensure_future(fire_message_to_rabbitmq(message))

                if settings.MMT_ENV == "test":
                    response.headers["userip"] = "fired"

            except:
                pass

