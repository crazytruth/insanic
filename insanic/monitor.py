from sanic import Blueprint
from sanic.response import json

from insanic import __version__
from insanic.conf import settings
from insanic.status import HTTP_200_OK

blueprint_monitor = Blueprint('monitor')

#
# A service has an health check API endpoint (e.g. HTTP /health) that returns the health of the service.
# The API endpoint handler performs various checks, such as
#
# the status of the connections to the infrastructure services used by the service instance
# the status of the host, e.g. disk space
# application specific logic
@blueprint_monitor.route('health')
def health_check(request):
    return json({
        "service": settings.SERVICE_NAME,
        "status": "OK",
        "insanic_version": __version__
    }, status=HTTP_200_OK)

