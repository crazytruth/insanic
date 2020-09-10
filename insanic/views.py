"""
Copyright © 2011-present, Encode OSS Ltd. All rights reserved.

Modified for framework usage.
"""

import asyncio
from inspect import isawaitable

from sanic.views import HTTPMethodView

from insanic import authentication, exceptions, permissions
from insanic.errors import GlobalErrorCodes


class InsanicView(HTTPMethodView):
    http_method_names = [
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "trace",
    ]

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = []
    authentication_classes = [
        authentication.JSONWebTokenAuthentication,
    ]

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
            "Allow": ", ".join(self.allowed_methods),
        }
        return headers

    def perform_authentication(self, request):
        """
        Perform authentication on the incoming request.

        Note that if you override this and simply 'pass', then authentication
        will instead be performed lazily, the first time either
        `request.user` or `request.auth` is accessed.
        """
        request.user

    def check_permissions(self, request):
        """
        Check if the request should be permitted.
        Raises an appropriate exception if the request is not permitted.
        """
        for permission in self.get_permissions():
            if not permission.has_permission(request, self):
                self.permission_denied(request)

    def permission_denied(self, request, message=None):
        """
        If request is not permitted, determine what kind of exception to raise.
        """
        if not request.successful_authenticator:
            raise exceptions.NotAuthenticated(
                error_code=GlobalErrorCodes.authentication_credentials_missing
            )
        raise exceptions.PermissionDenied(
            message, error_code=GlobalErrorCodes.permission_denied
        )

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

    async def check_throttles(self, request):
        """
        Check if request should be throttled.
        Raises an appropriate exception if the request is throttled.
        """
        throttles = self.get_throttles()
        throttle_results = await asyncio.gather(
            *[t.allow_request(request, self) for t in throttles]
        )

        if not all(throttle_results):
            for i in range(len(throttles)):
                if not throttle_results[i]:
                    self.throttled(request, throttles[i].wait())

    def get_authenticators(self):
        """
        Instantiates and returns the list of authenticators that this view can use.
        """
        return [authentication.ServiceJWTAuthentication()] + [
            auth() for auth in self.authentication_classes
        ]

    async def convert_keywords(self):
        pass

    async def prepare_http(self, request, *args, **kwargs):
        """
        `.dispatch()` is pretty much the same as Django's regular dispatch,
        but with extra hooks for startup, finalize, and exception handling.
        """

        self.request.authenticators = self.get_authenticators()
        self.headers = self.default_response_headers  # deprecate?

        await self.convert_keywords()
        self.perform_authentication(self.request)
        self.check_permissions(self.request)
        await self.check_throttles(self.request)

    async def dispatch_request(self, request, *args, **kwargs):
        """
        `.dispatch()` is pretty much the same as Django's regular dispatch,
        but with extra hooks for startup, finalize, and exception handling.
        """
        self.args = args
        self.kwargs = kwargs
        self.request = request

        await self.prepare_http(request, *args, **kwargs)

        # Get the appropriate handler method
        response = super().dispatch_request(request, *args, **kwargs)

        if isawaitable(response):
            response = await response
        return response
