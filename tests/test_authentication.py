import pytest
import uuid

from sanic.response import json

from insanic import status, Insanic
from insanic.authentication import BaseAuthentication, JSONWebTokenAuthentication, \
    HardJSONWebTokenAuthentication, handlers
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.models import User
from insanic.views import InsanicView


@pytest.fixture(scope="session")
def user_token_factory():
    def factory(id=uuid.uuid4(), *, email, level):
        user = User(**{"id": id.hex, 'email': email, 'level': level})
        payload = handlers.jwt_payload_handler(user)
        return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], handlers.jwt_encode_handler(payload)])

    return factory


def test_base_authentication(loop):
    auth = BaseAuthentication()

    auth_header = auth.authenticate_header(object())
    assert auth_header is None

    with pytest.raises(NotImplementedError):
        loop.run_until_complete(auth.authenticate())


def test_base_authentication_on_view(insanic_application):
    class BreakView(InsanicView):
        authentication_classes = (BaseAuthentication,)

        def get(self, request, *args, **kwargs):
            return json({})

    insanic_application.add_route(BreakView.as_view(), '/')

    request, response = insanic_application.test_client.get('/')

    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.parametrize('authentication_class', [JSONWebTokenAuthentication,
                                                  HardJSONWebTokenAuthentication])
class TestAuthentication():

    def _create_app_with_authentication(self, authentication_class):
        app = Insanic('test')

        class TokenView(InsanicView):
            authentication_classes = (authentication_class,)

            def get(self, request, *args, **kwargs):
                return json({})

        app.add_route(TokenView.as_view(), '/')
        return app

    def test_jwt_token_authentication_missing(self, authentication_class):
        app = self._create_app_with_authentication(authentication_class)

        request, response = app.test_client.get('/')

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(
            response.json['error_code']['value']) == GlobalErrorCodes.authentication_credentials_missing

    def test_jwt_token_authenticate_invalid_prefix(self, authentication_class, user_token_factory):
        app = self._create_app_with_authentication(authentication_class)

        prefix, token = user_token_factory(email="test@test.test", level=UserLevels.ACTIVE).split(' ')

        request, response = app.test_client.get('/', headers={"Authorization": f"JWT {token}"})

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(
            response.json['error_code']['value']) == GlobalErrorCodes.authentication_credentials_missing

    def test_jwt_token_authentication_without_type(self, authentication_class, user_token_factory):
        app = self._create_app_with_authentication(authentication_class)
        prefix, token = user_token_factory(email="test@test.test", level=UserLevels.ACTIVE).split(' ')

        request, response = app.test_client.get('/', headers={"Authorization": f"MMT"})

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.invalid_authorization_header
        assert "No credentials provided." in response.json['description']

    def test_jwt_token_authentication_token_spaces(self, authentication_class, user_token_factory):
        app = self._create_app_with_authentication(authentication_class)
        prefix, token = user_token_factory(email="test@test.test", level=UserLevels.ACTIVE).split(' ')

        request, response = app.test_client.get('/', headers={"Authorization": f"MMT {token} Breakit"})

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.invalid_authorization_header
        assert "Credentials string should not contain spaces." in response.json['description']

    def test_jwt_token_authentication_expired_token(self, authentication_class, monkeypatch):
        app = self._create_app_with_authentication(authentication_class)
        from datetime import timedelta
        monkeypatch.setitem(settings.JWT_AUTH, 'JWT_EXPIRATION_DELTA', timedelta(seconds=-10))

        user = User(**{"id": uuid.uuid4().hex, 'email': 'test@test.test', 'level': UserLevels.ACTIVE})
        payload = handlers.jwt_payload_handler(user)
        token = handlers.jwt_encode_handler(payload)

        request, response = app.test_client.get('/', headers={"Authorization": f"MMT {token}"})

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.signature_expired
        assert "Signature has expired." in response.json['description']

    def test_jwt_token_authentication_error_decode_signature(self, authentication_class, monkeypatch):
        app = self._create_app_with_authentication(authentication_class)
        user = User(**{"id": uuid.uuid4().hex, 'email': 'test@test.test', 'level': UserLevels.ACTIVE})
        payload = handlers.jwt_payload_handler(user)
        token = handlers.jwt_encode_handler(payload)

        monkeypatch.setitem(settings.JWT_AUTH, 'JWT_PUBLIC_KEY', uuid.uuid4().hex)

        request, response = app.test_client.get('/', headers={"Authorization": f"MMT {token}"})

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.signature_not_decodable
        assert "Error decoding signature." in response.json['description']

    def test_jwt_token_authentication_invalid_token(self, authentication_class, monkeypatch):
        app = self._create_app_with_authentication(authentication_class)
        user = User(**{"id": uuid.uuid4().hex, 'email': 'test@test.test', 'level': UserLevels.ACTIVE})
        payload = handlers.jwt_payload_handler(user)
        token = handlers.jwt_encode_handler(payload)

        monkeypatch.setitem(settings.JWT_AUTH, 'JWT_AUDIENCE', '.test.com')

        request, response = app.test_client.get('/', headers={"Authorization": f"MMT {token}"})

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.invalid_token
        assert "Incorrect authentication credentials." in response.json['description']

    def test_jwt_token_authentication_user_not_active(self, authentication_class):
        app = self._create_app_with_authentication(authentication_class)
        user = User(**{"id": uuid.uuid4().hex, 'email': 'test@test.test', 'level': UserLevels.DEACTIVATED})
        payload = handlers.jwt_payload_handler(user)
        token = handlers.jwt_encode_handler(payload)

        request, response = app.test_client.get('/', headers={"Authorization": f"MMT {token}"})

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.inactive_user
        assert "User account is disabled." in response.json['description']

    def test_jwt_token_authentication_success(self, authentication_class, user_token_factory):
        app = self._create_app_with_authentication(authentication_class)

        token = user_token_factory(email="test@test.test", level=UserLevels.ACTIVE)

        request, response = app.test_client.get('/', headers={"Authorization": token})

        assert response.status == status.HTTP_200_OK
