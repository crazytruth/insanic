"""
Provides various authentication policies.
"""
import aiohttp
import jwt


from insanic import exceptions
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.log import error_logger
from insanic.registration import gateway

from insanic.authentication import handlers
from insanic.models import User, RequestService, AnonymousUser, AnonymousRequestService

UNUSABLE_PASSWORD_PREFIX = '!'


def get_authorization_header(request, header='authorization'):
    """
    Return request's 'Authorization:' header, as a bytestring.

    Hide some test client ickyness where the header can be unicode.
    """
    auth = request.headers.get(header, b'')
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

    def decode_jwt(self, **kwargs):
        return handlers.jwt_decode_handler(**kwargs)

    def get_jwt_value(self, request):
        auth = get_authorization_header(request).split()

        if not auth or str(auth[0].lower()) != self.auth_header_prefix:
            return None

        if len(auth) == 1:
            msg = 'Invalid Authorization header. No credentials provided.'
            raise exceptions.AuthenticationFailed(msg,
                                                  error_code=GlobalErrorCodes.invalid_authorization_header)
        elif len(auth) > 2:
            msg = 'Invalid Authorization header. Credentials string should not contain spaces.'
            raise exceptions.AuthenticationFailed(msg,
                                                  error_code=GlobalErrorCodes.invalid_authorization_header)

        return {"token": auth[1], "verify": False}

    def try_decode_jwt(self, **jwt_value):
        try:
            payload = self.decode_jwt(**jwt_value)
        except jwt.DecodeError:
            msg = 'Error decoding signature.'
            raise exceptions.AuthenticationFailed(msg,
                                                  error_code=GlobalErrorCodes.signature_not_decodable)
        except jwt.InvalidTokenError:
            raise exceptions.AuthenticationFailed(error_code=GlobalErrorCodes.invalid_token)
        return payload


    def get_consumer_header(self, request, header='x-consumer-username'):
        """
        Gets request's consumer's id which Kong attached.
        """

        user_id = request.headers.get(header, 'anonymous')

        if user_id == 'anonymous' and request.headers.get('x-anonymous-consumer', None) == 'true':
            return None

        return user_id

    async def authenticate_credentials(self, request, payload):
        """
        Returns an active user that matches the payload's user id and email.
        """
        raise NotImplementedError(".authenticate_credentials() must be overridden.")  # pragma: no cover

    async def authenticate(self, request):
        """
        Returns a two-tuple of `User` and token if a valid signature has been
        supplied using JWT-based authentication.  Otherwise returns `None`.
        """
        jwt_value = self.get_jwt_value(request)

        if jwt_value is None or not self.get_consumer_header(request):
            return None

        payload = self.try_decode_jwt(**jwt_value)
        user, service = await self.authenticate_credentials(request, payload)

        return user, service, jwt_value['token']


class JSONWebTokenAuthentication(BaseJSONWebTokenAuthentication):
    """
    Clients should authenticate by passing the token key in the "Authorization"
    HTTP header, prepended with the string specified in the setting
    `JWT_AUTH_HEADER_PREFIX`. For example:

        Authorization: JWT eyJhbGciOiAiSFMyNTYiLCAidHlwIj
    """
    www_authenticate_realm = 'api'

    @property
    def auth_header_prefix(self):
        return settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'].lower()

    def authenticate_header(self, request):
        """
        Return a string to be used as the value of the `WWW-Authenticate`
        header in a `401 Unauthenticated` response, or `None` if the
        authentication scheme should return `403 Permission Denied` responses.
        """
        return '{0} realm="{1}"'.format(self.auth_header_prefix, self.www_authenticate_realm)

    async def authenticate_credentials(self, request, payload):
        user_id = payload.pop('id', payload.get('user_id'))

        user = User(id=user_id, is_authenticated=True, **payload)

        if not user.is_active:
            msg = 'User account is disabled.'
            raise exceptions.AuthenticationFailed(msg,
                                                  error_code=GlobalErrorCodes.inactive_user)

        return user, AnonymousRequestService


class ServiceJWTAuthentication(BaseJSONWebTokenAuthentication):
    www_authenticate_realm = "api"

    @property
    def auth_header_prefix(self):
        return settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX'].lower()

    def decode_jwt(self, **kwargs):
        token = kwargs.pop('token')
        return handlers.jwt_service_decode_handler(token)

    async def authenticate_credentials(self, request, payload):
        user = User(**payload.pop('user', AnonymousUser))

        service = RequestService(is_authenticated=True, **payload)

        if not service.is_valid:
            msg = f"Invalid request to {settings.SERVICE_NAME}."
            raise exceptions.AuthenticationFailed(msg,
                                                  error_code=GlobalErrorCodes.invalid_service_token)

        return user, service


class HardJSONWebTokenAuthentication(JSONWebTokenAuthentication):

    def __init__(self):
        super().__init__()
        self._user_service = None

    @property
    def user_service(self):
        if self._user_service is None:
            from insanic.loading import get_service
            self._user_service = get_service('user')
        return self._user_service

    def try_decode_jwt(self, **jwt_value):
        try:
            return self.decode_jwt(**jwt_value)
        except jwt.DecodeError:
            msg = 'Error decoding signature.'
            raise exceptions.AuthenticationFailed(msg,
                                                  error_code=GlobalErrorCodes.signature_not_decodable)

    async def authenticate(self, request):
        """
        Returns a two-tuple of `User` and token if a valid signature has been
        supplied using JWT-based authentication.  Otherwise returns `None`.
        """

        jwt_value_generator = self.get_jwt_value(request)
        consumer_header = self.get_consumer_header(request)

        exec = exceptions.AuthenticationFailed(error_code=GlobalErrorCodes.invalid_token)
        #
        async for jwt_value in jwt_value_generator:

            if jwt_value is None or not consumer_header:
                return None

            try:
                payload = self.try_decode_jwt(**jwt_value)
            except jwt.InvalidTokenError:
                # exec = exceptions.AuthenticationFailed(error_code=GlobalErrorCodes.invalid_token)
                pass
            else:
                user, service = await self.authenticate_credentials(request, payload)
                break
        else:
            raise exec

        return user, service, jwt_value

    async def get_jwt_value(self, request):
        """
        gets values for decoding jwt and verifing
        :param request:
        :return: list of dict
        """
        jwt_auth = super().get_jwt_value(request)
        jwt_auth["verify"] = True
        jwt_auth['key'] = ""  # from kong

        consumer_id = self.get_consumer_header(request)

        next_url = gateway.kong_base_url.with_path(f'/consumers/{consumer_id}/jwt')

        while next_url:
            response = await self.get_jwt_from_kong(next_url)
            for j in response['data']:
                jwt_auth.update({"key": j['secret']})
                jwt_auth.update({"issuer": j['key']})
                yield jwt_auth

            next_url = response.get('next', None)

    async def get_jwt_from_kong(self, next_url):
        async with gateway.session.get(next_url) as resp:
            try:
                response = await resp.json()
                resp.raise_for_status()
            except aiohttp.client_exceptions.ClientError as e:
                error_logger.critical(f"Error Response from KONG: [{resp.status}] {response}")
                raise exceptions.ServiceUnavailable503Error("Gateway is unavailable for authentication.")
            except Exception as e:
                error_logger.critical(f"Something went wrong with KONG: {e.args[0]}")
                raise exceptions.APIException("Something when wrong with gateway authentication.")
            else:
                return response


    async def get_user(self, user_id):
        """
        get user from user service.  This was extracted as its own function so that user service can
        override to hit db without sending a request to itself.

        :param user_id:
        :return:  ex. {"id": "", "level": ""}
        :rtype dict:
        """
        return await self.user_service.http_dispatch('GET', f'/api/v2/users/{user_id}/',
                                                     query_params={"query_type": "id",
                                                                   "include": "id,level"},
                                                     propagate_error=True)

    async def authenticate_credentials(self, request, payload):
        """
        Returns an active user that matches the payload's user id and email.
        """
        # call user service and get data
        user_id = payload['user_id']

        user_data = await self.get_user(user_id)

        return await super().authenticate_credentials(request, user_data)





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
        # if settings.SERVICE_NAME == "user":x
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
