import ujson as json

from sanic import exceptions as sanic_exceptions
from sanic.handlers import (
    ErrorHandler as SanicErrorHandler,
    format_exc,
    SanicException,
)

from insanic import exceptions, status
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.log import error_logger
from insanic.responses import json_response
from insanic.utils import _unpack_enum_error_message


INTERNAL_SERVER_ERROR_JSON = {
    "message": "Server Error",
    "description": "Something has blown up really bad. Somebody should be notified?",
    "error_code": _unpack_enum_error_message(GlobalErrorCodes.unknown_error),
}


class ErrorHandler(SanicErrorHandler):
    def __init__(self):
        super().__init__()
        self.add(sanic_exceptions.SanicException, self.sanic_exception_handler)
        self.add(exceptions.NotAuthenticated, self.not_authenticated_handler)
        self.add(
            exceptions.AuthenticationFailed, self.not_authenticated_handler
        )

    def sanic_exception_handler(self, request, exception):

        if hasattr(exceptions, f"Sanic{exception.__class__.__name__}"):
            insanic_exception = getattr(
                exceptions, f"Sanic{exception.__class__.__name__}"
            )(exception.args[0], status_code=exception.status_code)
            if hasattr(exception, "headers"):
                insanic_exception.headers = exception.headers
            exception = insanic_exception

        return self.default(request, exception)

    def not_authenticated_handler(self, request, exception):

        auth_header = self.get_authenticate_header(request)

        if auth_header:
            exception.auth_header = auth_header
        # else:
        #     exception.status_code = status.HTTP_403_FORBIDDEN

        return self.default(request, exception)

    def response(self, request, exception):
        """Fetches and executes an exception handler and returns a response
        object

        :param request: Request
        :param exception: Exception to handle
        :return: Response object
        """
        # handler = self.handlers.get(type(exception), self.default)
        handler = self.lookup(exception)
        response = None
        try:
            if handler:
                response = handler(request=request, exception=exception)
            if response is None:
                response = self.default(request=request, exception=exception)
        except Exception:
            exc = format_exc()
            self.log(exc)
            if self.debug:

                url = getattr(request, "path", "unknown")
                response_message = (
                    'Exception raised in exception handler "{}" '
                    'for uri: "{}"\n{}'
                ).format(handler.__name__, url, format_exc())
                error_logger.critical(response_message)
                return self.handle_uncaught_exception(
                    request, exception, response_message
                )
            else:
                return self.handle_uncaught_exception(request, exception)
        response.exception = exception
        response.error_code = json.loads(response.body)["error_code"]

        return response

    def default(self, request, exception):
        if settings.DEBUG:
            self.log(format_exc())
        if issubclass(type(exception), exceptions.APIException):
            headers = {}
            if getattr(exception, "auth_header", None):
                headers["WWW-Authenticate"] = exception.auth_header
            if getattr(exception, "wait", None):
                headers["Retry-After"] = "%d" % exception.wait
            if getattr(exception, "headers", None):
                for k, v in exception.headers.items():
                    if k.lower() == "content-length":
                        continue

                    headers.update({k: v})

            response = json_response(
                {
                    "message": getattr(
                        exception,
                        "message",
                        status.REVERSE_STATUS[exception.status_code],
                    ),
                    "description": getattr(
                        exception, "description", exception.args[0]
                    ),
                    "error_code": _unpack_enum_error_message(
                        getattr(
                            exception,
                            "error_code",
                            GlobalErrorCodes.unknown_error,
                        )
                    ),
                },
                status=getattr(
                    exception,
                    "status_code",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                ),
                headers=headers,
            )
        elif issubclass(type(exception), SanicException):
            # if this error is raised then, need to specify an api exeception
            response = json_response(
                {
                    "message": status.REVERSE_STATUS[exception.status_code],
                    "description": getattr(
                        exception, "description", exception.args[0]
                    ),
                    "error_code": _unpack_enum_error_message(
                        getattr(
                            exception,
                            "error_code",
                            GlobalErrorCodes.error_unspecified,
                        )
                    ),
                },
                status=getattr(
                    exception,
                    "status_code",
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                ),
                headers=getattr(exception, "headers", {}),
            )
        else:
            response = self.handle_uncaught_exception(request, exception)

        return response

    def handle_uncaught_exception(
        self, request, exception, custom_message=INTERNAL_SERVER_ERROR_JSON
    ):

        return json_response(
            custom_message, status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    def get_authenticate_header(self, request):
        """
        If a request is unauthenticated, determine the WWW-Authenticate
        header to use for 401 responses, if any.
        """
        authenticators = request.authenticators
        if authenticators:
            return request.authenticators[0].authenticate_header(request)
