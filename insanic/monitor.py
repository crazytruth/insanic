from sanic import Blueprint
from sanic.response import json

from insanic import __version__
from insanic.conf import settings
from insanic.status import HTTP_200_OK

blueprint_monitor = Blueprint('monitor')

@blueprint_monitor.route('health')
def health_check(request):
    return json({
        "service": settings.SERVICE_NAME,
        "status": "OK",
        "insanic_version": __version__
    }, status=HTTP_200_OK)

