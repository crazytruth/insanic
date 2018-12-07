import aiotask_context

from insanic.conf import settings
from insanic.models import AnonymousUser


def context_user():
    default = dict(AnonymousUser)
    try:
        user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER, default)
    except AttributeError:
        user = default
    return user


def context_correlation_id():
    try:
        correlation_id = aiotask_context.get(settings.TASK_CONTEXT_CORRELATION_ID, "unknown")
    except AttributeError:
        correlation_id = "not set"
    return correlation_id
