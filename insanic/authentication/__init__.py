# Copyright © 2011-present, Encode OSS Ltd. All rights reserved.
#
# Modified for framework use.
# Provides various authentication policies.

from typing import Union

import jwt

from insanic import exceptions
from insanic.authentication import handlers
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.models import User, RequestService, AnonymousRequestService
from insanic.request import Request

UNUSABLE_PASSWORD_PREFIX = "!"


def get_authorization_header(request, header="authorization"):
    """
    Return request's 'Authorization:' header, as a bytestring.

    Hide some test client ickyness where the header can be unicode.
    """
    auth = request.headers.get(header, b"")
    return auth


class BaseAuthentication(object):
    """
    All authentication classes should extend BaseAuthentication.
    """

    def authenticate(self, **credentials):
        """
        Authenticate the request and return a two-tuple of (user, token).
        """
        raise NotImplementedError(".authenticate() must be overridden.")

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        pass


class BaseJSONWebTokenAuthentication(BaseAuthentication):
    """
    Token based authentication using the JSON Web Token standard.
    """

    def decode_jwt(self, **kwargs) -> dict:
        """
        decodes token with arguments

        :param kwargs:
        :return:
        """
        return handlers.jwt_decode_handler(**kwargs)

    def get_jwt_value(self, request: Request) -> Union[dict, None]:
        """


        :param request:
        :return:
        """
        auth = get_authorization_header(request).split()

        if not auth or str(auth[0].lower()) != self.auth_header_prefix:
            return None

        if len(auth) == 1:
            msg = "Invalid Authorization header. No credentials provided."
            raise exceptions.AuthenticationFailed(
                msg, error_code=GlobalErrorCodes.invalid_authorization_header
            )
        elif len(auth) > 2:
            msg = "Invalid Authorization header. Credentials string should not contain spaces."
            raise exceptions.AuthenticationFailed(
                msg, error_code=GlobalErrorCodes.invalid_authorization_header
            )

        return {"token": auth[1], "verify": settings.JWT_AUTH_VERIFY}

    def try_decode_jwt(self, **jwt_value):
        try:
            payload = self.decode_jwt(**jwt_value)
        except jwt.DecodeError:
            msg = "Error decoding signature."
            raise exceptions.AuthenticationFailed(
                msg, error_code=GlobalErrorCodes.signature_not_decodable
            )
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed(
                error_code=GlobalErrorCodes.invalid_token
            )
        return payload

    def get_consumer_header(self, request, header="x-consumer-username"):
        """
        Gets request's consumer's id which Kong attached.
        """

        user_id = request.headers.get(header, "anonymous")

        if (
            user_id == "anonymous"
            and request.headers.get("x-anonymous-consumer", None) == "true"
        ):
            return None

        return user_id

    def authenticate_credentials(self, request, payload):
        """
        Returns an active user that matches the payload's user id and email.
        """
        raise NotImplementedError(
            ".authenticate_credentials() must be overridden."
        )  # pragma: no cover

    def authenticate(self, request):
        """
        Returns a two-tuple of `User` and token if a valid signature has been
        supplied using JWT-based authentication.  Otherwise returns `None`.
        """
        jwt_value = self.get_jwt_value(request)

        if jwt_value is None or not self.get_consumer_header(request):
            return None

        payload = self.try_decode_jwt(**jwt_value)
        user, service = self.authenticate_credentials(request, payload)

        return user, service, jwt_value["token"]


class JSONWebTokenAuthentication(BaseJSONWebTokenAuthentication):
    """
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string specified in the setting
    `JWT_AUTH_HEADER_PREFIX`. For example:

        Authorization: JWT eyJhbGciOiAiSFMyNTYiLCAidHlwIj
    """

    www_authenticate_realm = "api"

    @property
    def auth_header_prefix(self):
        return settings.JWT_AUTH_AUTH_HEADER_PREFIX.lower()

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        return '{0} realm="{1}"'.format(
            self.auth_header_prefix, self.www_authenticate_realm
        )

    def authenticate_credentials(self, request, payload):
        user_id = payload.pop("id", payload.get("user_id"))

        user = User(id=user_id, is_authenticated=True, **payload)

        if not user.is_active:
            msg = "User account is disabled."
            raise exceptions.AuthenticationFailed(
                msg, error_code=GlobalErrorCodes.inactive_user
            )

        return user, AnonymousRequestService


class ServiceJWTAuthentication(BaseJSONWebTokenAuthentication):
    www_authenticate_realm = "api"

    @property
    def auth_header_prefix(self):
        return settings.JWT_SERVICE_AUTH_AUTH_HEADER_PREFIX.lower()

    def decode_jwt(self, **kwargs):
        token = kwargs.pop("token")
        return handlers.jwt_service_decode_handler(token)

    def authenticate_credentials(self, request, payload):

        user_params = {"id": "", "level": -1}

        for f in request.headers.get(
            settings.INTERNAL_REQUEST_USER_HEADER, ""
        ).split(";"):
            if f:
                k, v = f.split("=")
                user_params.update({k: v})

        user = User(**user_params)

        service = RequestService(is_authenticated=True, **payload)

        if not service.is_valid:
            msg = f"Invalid request to {settings.SERVICE_NAME}."
            raise exceptions.AuthenticationFailed(
                msg, error_code=GlobalErrorCodes.invalid_service_token
            )

        return user, service
