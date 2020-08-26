import asyncio
import psutil
import time

from prometheus_client import CONTENT_TYPE_LATEST, core
from prometheus_client.exposition import generate_latest

from sanic import Blueprint
from sanic.response import json, raw

from insanic import __version__
from insanic.conf import settings
from insanic.exceptions import APIException
from insanic.loading import get_service
from insanic.scopes import get_my_ip
from insanic.status import HTTP_200_OK
from insanic.views import InsanicView

blueprint_monitor = Blueprint("monitor", strict_slashes=True)


# A service has an health check API endpoint (e.g. HTTP /health) that returns the health of the service.
# The API endpoint handler performs various checks, such as
#
# the status of the connections to the infrastructure services used by the service instance
# the status of the host, e.g. disk space
# application specific logic

PING_ENDPOINT = "/ping/"
HEALTH_ENDPOINT = "/health/"
METRICS_ENDPOINT = "/metrics/"

MONITOR_ENDPOINTS = (PING_ENDPOINT, HEALTH_ENDPOINT, METRICS_ENDPOINT)


async def response_time(func, *args, **kwargs):
    start = time.time()
    try:
        response, status_code = await func(*args, **kwargs)
    except APIException as e:
        response = e.__dict__()
        status_code = e.status_code

    return {
        "response": response,
        "status_code": status_code,
        "request_time": f"{int((time.time()-start) * 1000)} ms",
    }


class PingPongView(InsanicView):
    authentication_classes = []
    permission_classes = []

    async def get(self, request, *args, **kwargs):
        start = time.time()
        try:
            depth = int(request.query_params.get("depth", 0))
        except ValueError:
            depth = 0

        if depth and len(settings.SERVICE_CONNECTIONS) > 0:
            ping_tasks = {}
            ping_responses = {}

            for s in settings.SERVICE_CONNECTIONS:
                try:
                    service = get_service(s)
                except RuntimeError as e:
                    ping_responses.update({s: {"error": e.args[0]}})
                else:
                    ping_tasks.update(
                        {
                            s: asyncio.ensure_future(
                                response_time(
                                    service.dispatch,
                                    "GET",
                                    f"/{s}/ping/",
                                    query_params={"depth": depth - 1},
                                    include_status_code=True,
                                )
                            )
                        }
                    )
            await asyncio.gather(*ping_tasks.values())
            for k, v in ping_tasks.items():
                ping_responses.update({k: v.result()})
            resp = ping_responses
        else:
            resp = "pong"

        return json(
            {
                "response": resp,
                "process_time": f"{int((time.time()-start) * 1000)} ms",
            }
        )


blueprint_monitor.add_route(
    PingPongView.as_view(), PING_ENDPOINT, methods=["GET"], strict_slashes=True,
)


@blueprint_monitor.route(HEALTH_ENDPOINT)
def health_check(request):
    return json(
        {
            "service": settings.SERVICE_NAME,
            "service_version": settings.SERVICE_VERSION,
            "status": "OK",
            "insanic_version": __version__,
            "ip": get_my_ip(),
        },
        status=HTTP_200_OK,
    )


@blueprint_monitor.route(METRICS_ENDPOINT, methods=("GET",))
def metrics(request):

    p = psutil.Process()

    total_task_count = 0
    active_task_count = 0
    for task in asyncio.Task.all_tasks():
        total_task_count += 1
        if not task.done():
            active_task_count += 1

    request.app.metrics.TOTAL_TASK_COUNT.set(total_task_count)
    request.app.metrics.ACTIVE_TASK_COUNT.set(active_task_count)
    request.app.metrics.PROC_RSS_MEM_BYTES.set(p.memory_info().rss)
    request.app.metrics.PROC_RSS_MEM_PERC.set(p.memory_percent())
    request.app.metrics.PROC_CPU_PERC.set(p.cpu_percent())

    if request.query_string == "json":
        return json(
            {
                "total_task_count": total_task_count,
                "active_task_count": active_task_count,
                "request_count": _get_value_from_metric(
                    request.app.metrics.REQUEST_COUNT
                ),
                "proc_rss_mem_bytes": _get_value_from_metric(
                    request.app.metrics.PROC_RSS_MEM_BYTES
                ),
                "proc_rss_mem_perc": _get_value_from_metric(
                    request.app.metrics.PROC_RSS_MEM_PERC
                ),
                "proc_cpu_perc": _get_value_from_metric(
                    request.app.metrics.PROC_CPU_PERC
                ),
                "timestamp": time.time(),
            }
        )
    else:
        return raw(
            generate_latest(core.REGISTRY), content_type=CONTENT_TYPE_LATEST
        )


def _get_value_from_metric(metric):
    return metric._value.get()
