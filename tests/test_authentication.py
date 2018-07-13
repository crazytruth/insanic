import pytest
import uuid

import requests

from sanic.response import json

from insanic import status, Insanic
from insanic.authentication import BaseAuthentication, JSONWebTokenAuthentication, \
    HardJSONWebTokenAuthentication, handlers, ServiceJWTAuthentication
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.models import User, to_header_value, AnonymousUser
from insanic.scopes import public_facing
from insanic.views import InsanicView



@pytest.fixture
def kong_gateway(monkeypatch):
    monkeypatch.setattr(settings, "GATEWAY_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "KONG_HOST", 'kong.msa.swarm')
    monkeypatch.setattr(settings, "KONG_ADMIN_PORT", 18001)
    from insanic.registration import KongGateway

    return KongGateway()


@pytest.fixture
def user_token_factory(kong_gateway):
    gateway = kong_gateway
    created_test_user_ids = set()

    def factory(id=uuid.uuid4(), *, level, **kwargs):
        user = User(id=id.hex, level=level)
        created_test_user_ids.add(user.id)

        # Create test consumer
        requests.post(gateway.kong_base_url.with_path(f'/consumers/'),
                      json={'username': user.id})

        # Generate JWT information
        response = requests.post(
            gateway.kong_base_url.with_path(f'/consumers/{user.id}/jwt/')
        )
        response.raise_for_status()

        token_data = response.json()

        payload = handlers.jwt_payload_handler(user, token_data['key'])
        token = handlers.jwt_encode_handler(payload, token_data['secret'], token_data['algorithm'])

        return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], token])

    yield factory

    for user_id in created_test_user_ids:
        # Delete JWTs
        response = requests.get(gateway.kong_base_url.with_path(f'/consumers/{user_id}/jwt/'))
        response.raise_for_status()

        jwt_ids = (response.json())['data']
        for jwt in jwt_ids:
            response = requests.delete(gateway.kong_base_url.with_path(f"/consumers/{user_id}/jwt/{jwt['id']}/"))
            response.raise_for_status()

        # Delete test consumer
        response = requests.delete(gateway.kong_base_url.with_path(f"/consumers/{user_id}/"))
        response.raise_for_status()


@pytest.fixture
def jwt_data_getter(kong_gateway):
    gateway = kong_gateway

    created_test_user_ids = set()

    def factory(user):
        created_test_user_ids.add(user.id)

        # Create test consumer
        requests.post(gateway.kong_base_url.with_path(f'/consumers/'),
                      json={'username': user.id})

        # Generate JWT information
        response = requests.post(
            gateway.kong_base_url.with_path(f'/consumers/{user.id}/jwt/')
        )
        response.raise_for_status()

        token_data = response.json()

        return token_data

    yield factory

    for user_id in created_test_user_ids:
        # Delete JWTs
        response = requests.get(gateway.kong_base_url.with_path(f'/consumers/{user_id}/jwt/'))
        response.raise_for_status()

        jwt_ids = (response.json())['data']
        for jwt in jwt_ids:
            response = requests.delete(gateway.kong_base_url.with_path(f"/consumers/{user_id}/jwt/{jwt['id']}/"))
            response.raise_for_status()

        # Delete test consumer
        response = requests.delete(gateway.kong_base_url.with_path(f"/consumers/{user_id}/"))
        response.raise_for_status()


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

    @staticmethod
    def _deregister_routes(app, loop):
        from insanic.registration import gateway
        gateway.deregister_routes()


    @pytest.fixture(autouse=True)
    def monkeypatch_gateway_session(self, monkeypatch):
        from insanic.registration import gateway
        from yarl import URL
        monkeypatch.setattr(gateway, "_kong_base_url", URL("http://kong.msa.swarm:18001"))

    def monkeypatch_get_user(self, monkeypatch, authentication_class, user):
        async def mock_get_user(self, user_id):
            if user_id == user.id:
                return {"id": user.id, "level": user.level}

        monkeypatch.setattr(authentication_class, "get_user", mock_get_user, raising=False)

    def _create_app_with_authentication(self, authentication_class):
        app = Insanic('test')

        class TokenView(InsanicView):
            authentication_classes = (authentication_class,)

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        app.add_route(TokenView.as_view(), '/')
        app.listeners["before_server_stop"].insert(0, self._deregister_routes)
        return app

    def test_jwt_token_authentication_user_not_active(self, monkeypatch, authentication_class, test_user_token_factory):
        app = self._create_app_with_authentication(authentication_class)
        user, token = test_user_token_factory(level=UserLevels.DEACTIVATED,
                                              return_with_user=True)

        self.monkeypatch_get_user(monkeypatch, authentication_class, user)

        request, response = app.test_client.get(
            '/',
            headers={
                "Authorization": token,
                "x-consumer-username": user.id,
            }
        )

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.inactive_user
        assert "User account is disabled." in response.json['description']

    def test_jwt_token_authentication_success(self, monkeypatch, authentication_class, user_token_factory):
        app = self._create_app_with_authentication(authentication_class)

        user_id = uuid.uuid4()
        level = UserLevels.ACTIVE
        token = user_token_factory(id=user_id, level=level)

        self.monkeypatch_get_user(monkeypatch, authentication_class, User(id=user_id.hex, level=level))

        request, response = app.test_client.get(
            '/',
            headers={
                "Authorization": token,
                "x-consumer-username": user_id.hex,
            }
        )

        assert response.status == status.HTTP_200_OK


class TestServiceJWTAuthentication:

    @pytest.fixture()
    def auth(self):
        return ServiceJWTAuthentication()

    def test_service_auth(self, auth):
        assert auth.auth_header_prefix == settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX'].lower()

    def test_decode_jwt(self, auth, test_service_token_factory):
        test_user_id = 'a6454e643f7f4e8889b7085c466548d4'
        test_user = User(id=uuid.UUID(test_user_id).hex, level=UserLevels.STAFF,
                         is_authenticated=True)

        token = test_service_token_factory()
        assert token is not None
        assert token.split()[0].lower() == settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX'].lower()

        # payload = handlers.jwt_service_decode_handler(token.split()[1])
        # assert "user" in payload
        # assert payload['user'] == dict(test_user)

    async def test_authenticate_credentials_no_user_header(self, auth, test_service_token_factory):
        test_user_id = 'a6454e643f7f4e8889b7085c466548d4'
        test_user = User(id=uuid.UUID(test_user_id).hex, level=UserLevels.STAFF,
                         is_authenticated=1)
        token = test_service_token_factory()
        payload = handlers.jwt_service_decode_handler(token.split()[1])

        class MockRequest:
            @property
            def headers(self):
                return {}

        user, service = await auth.authenticate_credentials(MockRequest(), payload)

        assert dict(user) == dict(AnonymousUser)

    async def test_authenticate_credentials_with_user_header(self, auth, test_service_token_factory):
        test_user_id = 'a6454e643f7f4e8889b7085c466548d4'
        test_user = User(id=uuid.UUID(test_user_id).hex, level=UserLevels.STAFF,
                         is_authenticated=1)
        token = test_service_token_factory()
        payload = handlers.jwt_service_decode_handler(token.split()[1])

        class MockRequest:
            @property
            def headers(self):
                return {settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(test_user)}

        user, service = await auth.authenticate_credentials(MockRequest(), payload)
        assert dict(user) == dict(test_user)
