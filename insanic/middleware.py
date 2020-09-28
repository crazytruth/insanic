import aiotask_context

from insanic.conf import settings


def request_middleware(request) -> None:
    """
    Request middleware that runs on all requests. Tracks the
    request count and sets a correlation id to the asyncio task
    if included in the headers.

    :param request: The Request object.
    """
    try:
        request.app.metrics.REQUEST_COUNT.inc()
    except AttributeError:  # pragma: no cover
        pass
    aiotask_context.set(settings.TASK_CONTEXT_CORRELATION_ID, request.id)
