import aiotask_context

from insanic.conf import settings


def request_middleware(request):
    request.app.metrics['request_count'].inc()
    aiotask_context.set(settings.TASK_CONTEXT_CORRELATION_ID,
                        request.id)
