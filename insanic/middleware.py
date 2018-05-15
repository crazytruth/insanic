import asyncio

from insanic.conf import settings
from insanic.loading import get_service


async def request_middleware(request):
    pass

async def response_middleware(request, response):
    pass

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
            await UseripService.http_dispatch(
                'POST', '/api/v1/ip', include_status_code=True, payload={'user_id': user.id, 'ip_addr': request.ip}
            )
            # If userip service is called, It attaches userip key in its header.
            if settings.MMT_ENV == "test":
                response.headers["userip"] = "fired"
