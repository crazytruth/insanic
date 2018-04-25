from insanic.conf import settings
from insanic.loading import get_service
from insanic.log import logger

async def request_middleware(request):
    pass

async def response_middleware(request, response):
    pass

async def response_userip_middleware(request, response):
    user = await request.user
    service = await request.service
    service_name = settings.SERVICE_NAME

    if user.is_authenticated and not service.is_authenticated and service_name != 'userip':
        UseripService = get_service('userip')
        _, status_code = await UseripService.http_dispatch(
            'POST', '/api/v1/ip', include_status_code=True, payload={'user_id':user.id, 'ip_addr':request.ip}
        )
        # If userip service is called, It attaches userip key in its header.
        response.headers["userip"] = "fired"

        if status_code != 201:
            logger.log('info', 'Saving IP history has failed.')