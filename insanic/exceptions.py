import math
from sanic.exceptions import SanicException
from .errors import GlobalErrorCodes
from . import status

class APIException(SanicException):
    """
    Base class for REST framework exceptions.
    Subclasses should provide `.status_code` and `.default_detail` properties.
    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = 'An unknown error occurred'
    error_code = GlobalErrorCodes.unknown_error

    def __init__(self, detail=None, error_code=None, status_code=None):
        if detail is not None:
            self.detail = detail
        else:
            self.detail = self.default_detail

        if status_code is not None:
            self.status_code = status_code

        self.error_code = error_code

        super().__init__(detail, self.status_code)

    def __str__(self):
        return self.detail

class ParseError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = 'Malformed request.'

class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Bad request."

class InvalidUsage(APIException):
    status_code = status.HTTP_400_BAD_REQUEST

class ValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Validation Error"

class NotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    default_detail = 'Not found.'


class AuthenticationFailed(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Incorrect authentication credentials.'


class NotAuthenticated(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    default_detail = 'Authentication credentials were not provided.'


class PermissionDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = 'You do not have permission to perform this action.'


class MethodNotAllowed(APIException):
    status_code = status.HTTP_405_METHOD_NOT_ALLOWED
    default_detail = "Method '%s' not allowed."

    def __init__(self, method, detail=None):
        if detail is not None:
            self.detail = detail
        else:
            self.detail = self.default_detail % method


class NotAcceptable(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    default_detail = 'Could not satisfy the request Accept header'


class UnsupportedMediaType(APIException):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    detail = "Unsupported media type '%s' in request."
    default_detail = "Unsupported media type."

    def __init__(self, media_type, detail=None):
        if detail is not None:
            self.detail = detail
        else:
            self.detail = self.detail % media_type


class Throttled(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = 'Request was throttled.'
    extra_detail = ('Expected available in %(wait)d second.',
        'Expected available in %(wait)d seconds.')

    def __init__(self, wait=None, detail=None):
        if detail is not None:
            self.detail = detail
        else:
            self.detail = self.default_detail

        if wait is None:
            self.wait = None
        else:
            self.wait = math.ceil(wait)
            if self.wait is 1:
                self.detail += ' ' + (self.extra_detail[0] % {'wait': self.wait})
            else:
                self.detail += ' ' + (self.extra_detail[1] % {'wait': self.wait})

class FieldError(Exception):
    """Some kind of problem with a model field."""
    pass


class RawPostDataException(Exception):
    """
    You cannot access raw_post_data from a request that has
    multipart/* POST data if it has been accessed via POST,
    FILES, etc..
    """
    pass

class ServiceUnavailable503Error(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service unavailable."

class UnprocessableEntity422Error(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_detail = "Unprocessable Entity"