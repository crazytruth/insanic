import logging

from sanic import exceptions as sanic_exceptions
from sanic.response import json, html
from sanic.handlers import ErrorHandler as SanicErrorHandler, format_exc, SanicException, INTERNAL_SERVER_ERROR_HTML

from insanic import exceptions, status
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.log import error_logger

INTERNAL_SERVER_ERROR_JSON = {
  "message": "Server Error",
  "description": "Something has blown up really bad. Somebody should be notified?",
  "error_code": {
      "name": "unknown_error",
      "value": 99999
  }
}


class ErrorHandler(SanicErrorHandler):

    def __init__(self):
        super().__init__()
        self.add(sanic_exceptions.SanicException, self.sanic_exception_handler)

    def sanic_exception_handler(self, request, exception):

        if hasattr(exceptions, f"Sanic{exception.__class__.__name__}"):
            exception = getattr(exceptions, f"Sanic{exception.__class__.__name__}")(exception.args[0],
                                                                                    status_code=exception.status_code)


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

                url = getattr(request, 'path', 'unknown')
                response_message = (
                    'Exception raised in exception handler "{}" '
                    'for uri: "{}"\n{}').format(
                    handler.__name__, url, format_exc())
                error_logger.error(response_message)
                return self.handle_uncaught_exception(request, exception, response_message)
            else:
                return self.handle_uncaught_exception(request, exception)
        response.exception = exception
        return response


    def default(self, request, exception):
        if settings.DEBUG:
            self.log(format_exc())
        if issubclass(type(exception), exceptions.APIException):
            response = json(
                {"message": getattr(exception, 'default_detail', status.REVERSE_STATUS[exception.status_code]),
                 "description": getattr(exception, 'detail', exception.args[0]),
                 "error_code": getattr(exception, 'error_code', GlobalErrorCodes.unknown_error)},
                status=getattr(exception, 'status_code', status.HTTP_500_INTERNAL_SERVER_ERROR),
                headers=getattr(exception, 'headers', dict())
            )
        elif self.debug:
            html_output = self._render_traceback_html(exception, request)

            response_message = (
                'Exception occurred while handling uri: "{}"\n{}'.format(
                    request.path, format_exc()))
            error_logger.error(response_message)
            response = html(html_output, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            response = self.handle_uncaught_exception(request, exception)

        return response


    def handle_uncaught_exception(self, request, exception, custom_message=INTERNAL_SERVER_ERROR_JSON):

        return json(custom_message, status.HTTP_500_INTERNAL_SERVER_ERROR)