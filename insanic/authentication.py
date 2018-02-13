"""
Provides various authentication policies.
"""
import jwt

from insanic import exceptions
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.loading import get_service
from insanic.request import Request
from insanic.utils.jwt import jwt_decode_handler, jwt_get_username_from_payload_handler, jwt_get_user_id_from_payload_handler

try:
    from user.models import LegacyUserModel

except ImportError:
    pass

UserView = None
UNUSABLE_PASSWORD_PREFIX = '!'

def get_authorization_header(request):
    """
    Return request's 'Authorization:' header, as a bytestring.

    Hide some test client ickyness where the header can be unicode.
    """
    auth = request.headers.get('authorization', b'')
    return auth

class BaseAuthentication(object):
    """
    All authentication classes should extend BaseAuthentication.
    """

    async def authenticate(self, **credentials):
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

    async def authenticate(self, request):
        """
        Returns a two-tuple of `User` and token if a valid signature has been
        supplied using JWT-based authentication.  Otherwise returns `None`.
        """
        jwt_value = self.get_jwt_value(request)
        if jwt_value is None:
            return None

        try:
            payload = jwt_decode_handler(jwt_value)
        except jwt.ExpiredSignature:
            msg = 'Signature has expired.'
            raise exceptions.AuthenticationFailed(msg, GlobalErrorCodes.signature_expired)
        except jwt.DecodeError:
            msg = 'Error decoding signature.'
            raise exceptions.AuthenticationFailed(msg, GlobalErrorCodes.signature_not_decodable)
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed(error_code=GlobalErrorCodes.invalid_token)

        user = await self.authenticate_credentials(request, payload)

        return (user, jwt_value)


    def get_user_view(self, request, user_id):
        global UserView
        if UserView is None:
            uri, route = request.app.router.find_route_by_view_name('user.UserView')
            UserView = route[0].view_class
        return UserView


class JSONWebTokenAuthentication(BaseJSONWebTokenAuthentication):
    """
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string specified in the setting
    `JWT_AUTH_HEADER_PREFIX`. For example:

        Authorization: JWT eyJhbGciOiAiSFMyNTYiLCAidHlwIj
    """
    www_authenticate_realm = 'api'

    def get_jwt_value(self, request):
        auth = get_authorization_header(request).split()
        auth_header_prefix = settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'].lower()

        if not auth or str(auth[0].lower()) != auth_header_prefix:
            return None

        if len(auth) == 1:
            msg = 'Invalid Authorization header. No credentials provided.'
            raise exceptions.AuthenticationFailed(msg, GlobalErrorCodes.invalid_authorization_header)
        elif len(auth) > 2:
            msg = 'Invalid Authorization header. Credentials string should not contain spaces.'
            raise exceptions.AuthenticationFailed(msg, GlobalErrorCodes.invalid_authorization_header)

        return auth[1]

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        return '{0} realm="{1}"'.format(request.app.config.JWT_AUTH_HEADER_PREFIX, self.www_authenticate_realm)

    async def authenticate_credentails(self, request, payload):
        return payload


class JSONWebTokenAuthentication(JSONWebTokenAuthentication):
    async def authenticate_credentials(self, request, payload):
        """
        Returns an active user that matches the payload's user id and email.
        """
        # TODO: this get user model stuff
        # User = get_user_model()
        # username = jwt_get_username_from_payload_handler(payload)
        # user_id = jwt_get_user_id_from_payload_handler(payload)
        #
        # if not user_id:
        #     msg = 'Invalid payload.'
        #     raise exceptions.AuthenticationFailed(msg, GlobalErrorCodes.invalid_payload)
        #
        # # if user service just lookup
        # # else go ask user service
        # if settings.SERVICE_NAME == "user":
        #
        #     try:
        #         dummy_request = Request(request.url.encode(), {}, "1.1", "GET", request.transport)
        #         dummy_request.app = request.app
        #         view = self.get_user_view(request, user_id)()
        #         view.set_for_authentication(dummy_request, {"user_id": user_id})
        #         user = await view._get_object()
        #     except LegacyUserModel.DoesNotExist:
        #         msg = 'Invalid signature.'
        #         raise exceptions.AuthenticationFailed(msg, GlobalErrorCodes.invalid_signature)
        # else:
        #     user_service = get_service('user')
        #     user = await user_service.http_dispatch("GET", "/api/v1/user/self", request,
        #                                             query_params={"fields": "id,username,email,is_active,is_ban,is_superuser,locale,version,password,is_authenticated"},
        #                                             headers=request.headers)
        #
        # if not user.get('is_active'):
        #     msg = 'User account is disabled.'
        #     raise exceptions.AuthenticationFailed(msg, GlobalErrorCodes.unknown_error)

        return payload
