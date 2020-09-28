import inspect
from typing import Optional, Callable

from sanic.views import HTTPMethodView
from functools import wraps

from insanic.conf import settings

from insanic.exceptions import ImproperlyConfigured
from insanic.log import logger
from insanic.request import Request
from insanic.utils import datetime
from insanic.utils.datetime import (
    timestamp_seconds_to_datetime,
    get_utc_timestamp,
    get_utc_datetime,
)


class deprecate:
    """
    emits a warning if an request is made to the decorated method/path
    :param at: datetime object or timestamp
    :param ttl: (default 1 day) the frequency at which the warning messages will be logged
    """

    last_call = {}

    def __init__(
        self, *, at: [datetime.datetime, int], ttl: Optional[int] = None
    ) -> None:

        if isinstance(at, datetime.datetime):
            ts = datetime.datetime.timestamp(at)
            at = at.replace(tzinfo=datetime.timezone.utc)
        else:
            ts = at
            at = timestamp_seconds_to_datetime(ts)

        ttl = ttl or settings.DEPRECATION_WARNING_FREQUENCY

        self.dt = at
        self.ts = ts
        self.ttl = ttl

    def __call__(self, func_or_cls: [HTTPMethodView, Callable]):
        @wraps(func_or_cls)
        def wrapper(*args, **kwargs):

            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            view_response = func_or_cls(*args, **kwargs)

            if request:
                now = get_utc_timestamp()

                request_service = (
                    f"@{request.service.request_service.upper() or 'FE'}"
                )
                request_type = f"{request.method} {request.uri_template}"
                key = (request_service, request.method, request.uri_template)

                if key not in self.last_call:
                    self.last_call[key] = now - self.ttl

                if self.last_call[key] + self.ttl <= now:
                    logger.warning(
                        f"[DEPRECATION WARNING] For maintainers of {request_service}! "
                        f"{request_type} will be deprecated on {self.dt}. "
                        f"You have {get_utc_datetime() - self.dt} left!"
                    )
                    self.last_call[key] = now

            return view_response

        if inspect.isclass(func_or_cls):
            if issubclass(func_or_cls, HTTPMethodView):
                for m in func_or_cls.http_method_names:
                    handler = getattr(func_or_cls, m.lower(), None)
                    if handler is None:
                        continue

                    setattr(func_or_cls, m.lower(), self.__call__(handler))

                return func_or_cls
            else:
                raise ImproperlyConfigured(
                    "Must wrap a HTTPMethodView subclass."
                )
        else:
            return wrapper
