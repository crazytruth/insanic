import math
from insanic.errors import GlobalErrorCodes
from insanic import status


class ImproperlyConfigured(Exception):
    """Insanic is somehow improperly configured"""
    pass


class APIException(Exception):
    """
    Base class for REST framework exceptions.
    Subclasses should provide `.status_code`, `.error_code` and `.message`  properties.
    rename
        default_detail -> message
        detail -> description

    """
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    message = 'An unknown error occurred'
    error_code = GlobalErrorCodes.unknown_error
    i18n = False

    def __init__(self, description=None, *, error_code=None, status_code=None):
        if description is not None:
            self.description = description
        else:
            self.description = self.message

        if status_code is not None:
            self.status_code = status_code

        if error_code is not None:
            self.error_code = error_code

        super().__init__(description, self.status_code)

    def __str__(self):
        return self.description

    def __repr__(self):
        self.__str__()


class ParseError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    message = 'Malformed request.'


class BadRequest(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Bad request."


class InvalidUsage(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    message = 'Invalid Usage'


class ValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Validation Error"


class NotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    message = 'Not found.'


class AuthenticationFailed(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = 'Incorrect authentication credentials.'


class ServiceAuthenticationFailed(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = 'Incorrect authentication credentials from service.'


class NotAuthenticated(APIException):
    status_code = status.HTTP_401_UNAUTHORIZED
    message = 'Authentication credentials were not provided.'


class PermissionDenied(APIException):
    status_code = status.HTTP_403_FORBIDDEN
    message = 'You do not have permission to perform this action.'


class MethodNotAllowed(APIException):
    status_code = status.HTTP_405_METHOD_NOT_ALLOWED
    message = "Method '%s' not allowed."
    error_code = GlobalErrorCodes.method_not_allowed

    def __init__(self, method, description=None):
        if description is not None:
            self.description = description
        else:
            self.description = self.message % method


class NotAcceptable(APIException):
    status_code = status.HTTP_406_NOT_ACCEPTABLE
    message = 'Could not satisfy the request Accept header'


class UnsupportedMediaType(APIException):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    description = "Unsupported media type '%s' in request."
    message = "Unsupported media type."

    def __init__(self, media_type, description=None):
        if description is not None:
            self.description = description
        else:
            self.description = self.description % media_type


class Throttled(APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    message = 'Request was throttled.'
    extra_detail = ('Expected available in %(wait)d second.',
                    'Expected available in %(wait)d seconds.')
    error_code = GlobalErrorCodes.throttled

    def __init__(self, wait=None, description=None):
        if description is not None:
            self.description = description
        else:
            self.description = self.message

        if wait is None:
            self.wait = None
        else:
            self.wait = math.ceil(wait)
            if self.wait is 1:
                self.description += ' ' + (self.extra_detail[0] % {'wait': self.wait})
            else:
                self.description += ' ' + (self.extra_detail[1] % {'wait': self.wait})


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
    message = "Service unavailable."


class UnprocessableEntity422Error(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    message = "Unprocessable Entity"


class SanicInvalidUsage(InvalidUsage):
    def __init__(self, description=None, status_code=None):
        self.status_code = status_code
        super().__init__(description)
        if status_code == status.HTTP_405_METHOD_NOT_ALLOWED:
            self.error_code = GlobalErrorCodes.method_not_allowed


class SanicNotFound(APIException):
    status_code = status.HTTP_404_NOT_FOUND
    message = "Not Found"
