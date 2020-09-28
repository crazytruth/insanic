# Copyright © 2011-present, Encode OSS Ltd. All rights reserved.
#
# Copied and modified a lot of Request object methods for framework usage


import aiotask_context
import time
import uuid

from typing import Iterable

from multidict import CIMultiDict
from sanic.exceptions import InvalidUsage
from sanic.request import (
    Request as SanicRequest,
    RequestParameters,
)

from insanic import exceptions
from insanic.conf import settings
from insanic.functional import empty
from insanic.models import User, RequestService


DEFAULT_HTTP_CONTENT_TYPE = "application/octet-stream"


def _hasattr(obj, name):
    return not getattr(obj, name) is empty


class Request(SanicRequest):

    __slots__ = (
        "app",
        "headers",
        "version",
        "method",
        "_cookies",
        "transport",
        "body",
        "parsed_json",
        "parsed_args",
        "parsed_form",
        "parsed_files",
        "_ip",
        "_parsed_url",
        "uri_template",
        "stream",
        "_remote_addr",
        "authenticators",
        "parsed_data",
        "_stream",
        "_authenticator",
        "_user",
        "_auth",
        "_request_time",
        "_service",
        "_id",
    )

    def __init__(
        self,
        url_bytes: bytes,
        headers: CIMultiDict,
        version: str,
        method: str,
        transport,
        app,
        authenticators: Iterable = None,
    ):
        """
        Wrapper allowing to enhance a standard `HttpRequest` instance.


        :param url_bytes:
        :param headers: should be an instance of CIMultiDict
        :param version:
        :param method:
        :param transport:
        :param app:
        :param authenticators:
        """

        super().__init__(url_bytes, headers, version, method, transport, app)

        self._request_time = int(time.time() * 1000000)
        self._id = empty
        self.authenticators = authenticators or ()

    @property
    def id(self) -> str:
        """
        Gets a unique request id from either the header with
        :code:`REQUEST_ID_HEADER_FIELD` config,
        or generates it's own unique request id.
        """
        if self._id is empty:
            self._id = self.headers.get(
                settings.REQUEST_ID_HEADER_FIELD,
                f"I-{uuid.uuid4()}-{self._request_time}",
            )
        return self._id

    @property
    def query_params(self) -> dict:
        """
        More semantically correct name for request.GET.
        """
        return self.args

    @property
    def user(self) -> User:
        """
        Returns the user associated with the current request, as authenticated
        by the authentication classes provided to the request.
        """
        if not hasattr(self, "_user"):
            self._authenticate()
        return self._user

    @user.setter
    def user(self, value: User) -> None:
        """
        Sets the user on the current request. This is necessary to maintain
        compatibility with insanic.auth where the user property is
        set in the login and logout functions.

        Note that we also set the user on the task to give user context to any child tasks.
        """

        self._user = value
        aiotask_context.set(settings.TASK_CONTEXT_REQUEST_USER, dict(value))

    @property
    def service(self) -> RequestService:
        """
        Returns the service associated with the current request, as authenticated
        by the authentication classes provided to the request.
        """
        if not hasattr(self, "_service"):
            self._authenticate()
        return self._service

    @service.setter
    def service(self, value: RequestService) -> None:
        """
        Sets the service that send the request on the current request.

        :param value:
        :return:
        """
        self._service = value

    @property
    def auth(self):
        """
        Returns any non-user authentication information associated with the
        request, such as an authentication token.

        :rtype: :code:`BaseAuthentication`
        """
        if not hasattr(self, "_auth"):
            self._authenticate()
        return self._auth

    @auth.setter
    def auth(self, value) -> None:
        """
        Sets any non-user authentication information associated with the
        request, such as an authentication token.

        :param value: :code:`BaseAuthentication`
        """
        self._auth = value

    @property
    def successful_authenticator(self):
        """
        Return the instance of the authentication instance class that was used
        to authenticate the request, or `None`.

        :rtype: :code:`BaseAuthentication`
        """
        if not hasattr(self, "_authenticator"):
            self._authenticate()
        return self._authenticator

    @property
    def data(self) -> RequestParameters:
        """
        A single interface for getting the body of the request
        without needing to know the content type of the request.
        From django-rest-framework.
        """
        if not _hasattr(self, "parsed_data"):
            try:
                self.parsed_data = self.json
            except InvalidUsage:
                self.parsed_data = self.form
            finally:
                if self.parsed_files:
                    for k in self.parsed_files.keys():
                        v = self.parsed_files.getlist(k)
                        self.parsed_data.update({k: v})
        return self.parsed_data

    def _authenticate(self) -> None:
        """
        Attempt to authenticate the request using each authentication instance
        in turn.
        Returns a three-tuple of (authenticator, user, authtoken).
        """
        for authenticator in self.authenticators:
            try:
                user_auth_tuple = authenticator.authenticate(request=self)
            except exceptions.APIException:
                self._not_authenticated()
                raise

            if user_auth_tuple is not None:
                self._authenticator = authenticator
                # self.user_auth = user_auth_tuple
                self.user, self.service, self.auth = user_auth_tuple

                return

        self._not_authenticated()

    def _not_authenticated(self) -> None:
        """
        Set authenticator, user & authtoken representing an unauthenticated request.

        Defaults are None, AnonymousUser & None.
        """
        from insanic.models import AnonymousUser, AnonymousRequestService

        self._authenticator = None
        self.user = AnonymousUser
        self.service = AnonymousRequestService
        self.auth = None
