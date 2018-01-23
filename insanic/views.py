import logging

from inspect import isawaitable

from sanic.views import HTTPMethodView
from sanic.response import json, HTTPResponse, BaseHTTPResponse

from insanic import authentication, exceptions, permissions, status
from insanic.functional import cached_property
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes

logger = logging.getLogger('blowed.up')

def exception_handler(request, exc):
    """
    Returns the response that should be used for any given exception.

    By default we handle the REST framework `APIException`, and also
    Django's built-in `ValidationError`, `Http404` and `PermissionDenied`
    exceptions.

    Any unhandled exceptions may return `None`, which will cause a 500 error
    to be raised.
    """
    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait

        if isinstance(exc.detail, (list, dict)):
            data = exc.detail
        else:
            data = {'detail': exc.detail}

        return HTTPResponse(data, status=exc.status_code, headers=headers)
    elif isinstance(exc, exceptions.PermissionDenied):
        data = {'detail': 'Permission denied'}
        return HTTPResponse(data, status=status.HTTP_403_FORBIDDEN)
    else:
        logger.error('Internal Server Error: %s', request.path, exc_info=exc,
                     extra={
                         'status_code': 500,
                         'request': request
                     }
                     )

    # Note: Unhandled exceptions will raise a 500 error.
    return None

class MMTBaseView(HTTPMethodView):
    http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = []
    authentication_classes = [authentication.JSONWebTokenAuthentication,]


    def key(self, key, **kwargs):

        kwargs = {k:(v.decode() if isinstance(v, bytes) else v) for k,v in kwargs.items()}

        try:
            return ":".join([self._key[key].format(**kwargs)])
        except KeyError:
            raise KeyError("{0} key doesn't exist.".format(key))

    def get_fields(self):
        # fields = None means all
        fields = None
        if "fields" in self.request.query_params:
            fields = [f.strip() for f in self.request.query_params.get('fields').split(',') if f]
            if len(fields) == 0:
                fields = None
        return fields

    def _allowed_methods(self):
        return [m.upper() for m in self.http_method_names if hasattr(self, m)]

    @property
    def allowed_methods(self):
        """
        Wrap Django's private `_allowed_methods` interface in a public property.
        """
        return self._allowed_methods()

    @property
    def default_response_headers(self):
        headers = {
            'Allow': ', '.join(self.allowed_methods),
        }
        return headers

    @property
    def route(self):


        return ""

    def _get_device_info(self, ua):

        ua_os = ua.os
        ua_device = ua.device

        device = {}
        device['device_type'] = getattr(ua_os, "family")
        device['device_model'] = getattr(ua_device, "family")
        device['system_version'] = getattr(ua_os, "version_string")
        device['application_version'] = ua.ua_string.split(' ', 1)[0]

        return device

    def http_method_not_allowed(self, request, *args, **kwargs):
        """
        If `request.method` does not correspond to a handler method,
        determine what kind of exception to raise.
        """
        raise json({}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    async def perform_authentication(self, request):
        """
        Perform authentication on the incoming request.

        Note that if you override this and simply 'pass', then authentication
        will instead be performed lazily, the first time either
        `request.user` or `request.auth` is accessed.
        """
        await request.user

    async def check_permissions(self, request):
        """
        Check if the request should be permitted.
        Raises an appropriate exception if the request is not permitted.
        """
        for permission in self.get_permissions():
            if not await permission.has_permission(request, self):
                self.permission_denied(request)

    async def check_object_permissions(self, request, obj):
        """
        Check if the request should be permitted for a given object.
        Raises an appropriate exception if the request is not permitted.
        """
        for permission in self.get_permissions():
            if not await permission.has_object_permission(request, self, obj):
                self.permission_denied(
                    request, message=getattr(permission, 'message', None)
                )


    def permission_denied(self, request, message=None):
        """
        If request is not permitted, determine what kind of exception to raise.
        """
        if not request.successful_authenticator:
            raise exceptions.NotAuthenticated(error_code=GlobalErrorCodes.authentication_credentials_missing)
        raise exceptions.PermissionDenied(message, error_code=GlobalErrorCodes.permission_denied)

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        return [permission() for permission in self.permission_classes]

    def get_throttles(self):
        """
        Instantiates and returns the list of throttles that this view uses.
        """
        return [throttle() for throttle in self.throttle_classes]


    def throttled(self, request, wait):
        """
        If request is throttled, determine what kind of exception to raise.
        """
        raise exceptions.Throttled(wait)

    def check_throttles(self, request):
        """
        Check if request should be throttled.
        Raises an appropriate exception if the request is throttled.
        """
        for throttle in self.get_throttles():
            if not throttle.allow_request(request, self):
                self.throttled(request, throttle.wait())

    def initial(self, request, *args, **kwargs):
        """
        Runs anything that needs to occur prior to calling the method handler.
        """

        # Ensure that the incoming request is permitted
        self.perform_authentication(request)
        self.check_permissions(request)
        self.check_throttles(request)

    def get_authenticators(self):
        """
        Instantiates and returns the list of authenticators that this view can use.
        """
        return [auth() for auth in self.authentication_classes]

    def get_authenticate_header(self, request):
        """
        If a request is unauthenticated, determine the WWW-Authenticate
        header to use for 401 responses, if any.
        """
        authenticators = self.get_authenticators()
        if authenticators:
            return authenticators[0].authenticate_header(request)

    def handle_exception(self, exc):
        """
        Handle any exception that occurs, by returning an appropriate response,
        or re-raising the error.
        """
        if isinstance(exc, (exceptions.NotAuthenticated,
                            exceptions.AuthenticationFailed)):
            # WWW-Authenticate header for 401 responses, else coerce to 403
            auth_header = self.get_authenticate_header(self.request)

            if auth_header:
                exc.auth_header = auth_header
            else:
                exc.status_code = status.HTTP_403_FORBIDDEN

        response = exception_handler(exc)

        if response is None:
            raise

        response.exception = True
        return response

    async def convert_keywords(self):
        pass

    async def dispatch_request(self, request, *args, **kwargs):
        """
        `.dispatch()` is pretty much the same as Django's regular dispatch,
        but with extra hooks for startup, finalize, and exception handling.
        """
        self.args = args
        self.kwargs = kwargs
        self.request = request
        self.request.authenticators = self.get_authenticators()
        self.headers = self.default_response_headers  # deprecate?

        await self.convert_keywords()
        await self.perform_authentication(self.request)

        await self.check_permissions(self.request)
        self.check_throttles(self.request)

        # Get the appropriate handler method
        if self.request.method.lower() in self.http_method_names:
            handler = getattr(self, self.request.method.lower(),
                              self.http_method_not_allowed)
        else:
            handler = self.http_method_not_allowed

        required_params = getattr(self, "{0}_params".format(self.request.method.lower()), [])
        data = {}
        if len(required_params):

            body_data = self.request.data

            if body_data is None:
                data.update({"is_valid": False})
            else:
                for p in required_params:
                    data.update({p: body_data.get(p, None)})

        if None not in data.values():
            response = handler(self.request, data, *self.args, **self.kwargs)
        else:
            missing_parameters = [p for p, v in data.items() if v is None]
            msg = "Must include '"
            if len(missing_parameters) == 1:
                msg += missing_parameters[0]
            elif len(missing_parameters) > 1:
                msg += "', '".join(required_params[:-1])
                msg = "' and '" .join([msg, required_params[-1]])

            msg += "'."

            raise exceptions.BadRequest(msg, GlobalErrorCodes.invalid_usage)

        if isawaitable(response):
            response = await response

        self.response = self.finalize_response(self.request, response, *self.args, **self.kwargs)
        return self.response


    def finalize_response(self, request, response, *args, **kwargs):
        """
        Returns the final response object.
        """
        # Make the error obvious if a proper response is not returned


        assert isinstance(response, BaseHTTPResponse), (
            'Expected a `Response`, `HttpResponse` or `HttpStreamingResponse` '
            'to be returned from the view, but received a `%s`'
            % type(response)
        )

        response.headers.update(self.headers)

        return response



class ServiceOptions(MMTBaseView):
    permission_classes = []
    authentication_classes = []
