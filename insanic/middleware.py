import aiotask_context

from insanic.conf import settings


def request_middleware(request):
    try:
        request.app.metrics.REQUEST_COUNT.inc()
    except AttributeError:
        pass
    aiotask_context.set(settings.TASK_CONTEXT_CORRELATION_ID, request.id)
