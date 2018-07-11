import asyncio
import aiotask_context

from insanic.conf import settings
from insanic.loading import get_service


def request_middleware(request):
    aiotask_context.set(settings.TASK_CONTEXT_CORRELATION_ID,
                        request.headers.get(settings.REQUEST_ID_HEADER_FIELD, "unknown"))

async def response_userip_middleware(request, response):

    try:
        user = await request.user
        service = await request.service
        service_name = settings.SERVICE_NAME
    except Exception:
        if settings.MMT_ENV == "production":
            pass
        else:
            raise
    else:
        if user.is_authenticated and not service.is_authenticated and service_name != 'userip':
            UseripService = get_service('userip')

            try:
                asyncio.ensure_future(UseripService.http_dispatch(
                    'POST', '/api/v1/ip/', include_status_code=True, payload={'user_id': user.id, 'ip_addr': request.ip}
                ))
            except:
                pass
            else:
                # If userip service is called, It attaches userip key in its header.
                if settings.MMT_ENV == "test":
                    response.headers["userip"] = "fired"
