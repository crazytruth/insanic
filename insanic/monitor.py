from sanic import Blueprint
from sanic.response import json

from insanic.conf import settings
from insanic.status import HTTP_200_OK

blueprint_monitor = Blueprint('monitor')

@blueprint_monitor.route('health')
def health_check(request):
    return json({
        "service": settings.SERVICE_NAME,
        "status": "OK"
    }, status=HTTP_200_OK)

