from sanic.log import log
from sanic.response import json, html
from sanic.handlers import ErrorHandler as SanicErrorHandler, format_exc, SanicException, INTERNAL_SERVER_ERROR_HTML

from insanic import status
from insanic.errors import GlobalErrorCodes

INTERNAL_SERVER_ERROR_JSON = {
  "message": "Server Error",
  "description": "Something has blown up really bad. Somebody should be notified?",
  "error_code": {
      "name": "unknown_error",
      "value": 99999
  }
}


class ErrorHandler(SanicErrorHandler):

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
            self.log(format_exc())
            if self.debug:
                url = getattr(request, 'path', 'unknown')
                response_message = (
                    'Exception raised in exception handler "{}" '
                    'for uri: "{}"\n{}').format(
                    handler.__name__, url, format_exc())
                log.error(response_message)
                return json(response_message, status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return json('An error occurred while handling an error', status.HTTP_500_INTERNAL_SERVER_ERROR)
        return response


    def default(self, request, exception):
        self.log(format_exc())
        if issubclass(type(exception), SanicException):
            return json(
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
            log.error(response_message)
            return html(html_output, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            return json(INTERNAL_SERVER_ERROR_JSON, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
