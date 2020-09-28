import pytest
import uuid

from sanic.response import json

from insanic import status, Insanic
from insanic.authentication import (
    BaseAuthentication,
    JSONWebTokenAuthentication,
    handlers,
    ServiceJWTAuthentication,
)
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.models import User, to_header_value, AnonymousUser
from insanic.scopes import public_facing
from insanic.views import InsanicView


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

    insanic_application.add_route(BreakView.as_view(), "/")

    request, response = insanic_application.test_client.get("/")

    assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.parametrize("authentication_class", [JSONWebTokenAuthentication])
class TestAuthentication:
    def monkeypatch_get_user(self, monkeypatch, authentication_class, user):
        async def mock_get_user(self, user_id):
            if user_id == user.id:
                return {"id": user.id, "level": user.level}

        monkeypatch.setattr(
            authentication_class, "get_user", mock_get_user, raising=False
        )

    def _create_app_with_authentication(self, authentication_class):
        app = Insanic("test")

        class TokenView(InsanicView):
            authentication_classes = (authentication_class,)

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        app.add_route(TokenView.as_view(), "/")
        return app

    def test_jwt_token_authentication_user_not_active(
        self, monkeypatch, authentication_class, test_user_token_factory
    ):
        app = self._create_app_with_authentication(authentication_class)
        user, token = test_user_token_factory(
            level=UserLevels.DEACTIVATED, return_with_user=True
        )

        self.monkeypatch_get_user(monkeypatch, authentication_class, user)

        request, response = app.test_client.get(
            "/",
            headers={"Authorization": token, "x-consumer-username": user.id},
        )

        assert response.status == status.HTTP_401_UNAUTHORIZED
        assert (
            GlobalErrorCodes(response.json["error_code"]["value"])
            == GlobalErrorCodes.inactive_user
        )
        assert "User account is disabled." in response.json["description"]

    def test_jwt_token_authentication_success(
        self, monkeypatch, authentication_class, test_user_token_factory
    ):
        app = self._create_app_with_authentication(authentication_class)

        user_id = uuid.uuid4()
        level = UserLevels.ACTIVE
        token = test_user_token_factory(id=user_id.hex, level=level)

        self.monkeypatch_get_user(
            monkeypatch,
            authentication_class,
            User(id=user_id.hex, level=level),
        )

        request, response = app.test_client.get(
            "/",
            headers={
                "Authorization": token,
                "x-consumer-username": user_id.hex,
            },
        )

        assert response.status == status.HTTP_200_OK


class TestServiceJWTAuthentication:
    @pytest.fixture()
    def auth(self):
        return ServiceJWTAuthentication()

    def test_service_auth(self, auth):
        assert (
            auth.auth_header_prefix
            == settings.JWT_SERVICE_AUTH_AUTH_HEADER_PREFIX.lower()
        )

    def test_decode_jwt(self, auth, test_service_token_factory):

        token = test_service_token_factory()
        assert token is not None
        assert (
            token.split()[0].lower()
            == settings.JWT_SERVICE_AUTH_AUTH_HEADER_PREFIX.lower()
        )

        # payload = handlers.jwt_service_decode_handler(token.split()[1])
        # assert "user" in payload

    async def test_authenticate_credentials_no_user_header(
        self, auth, test_service_token_factory
    ):
        token = test_service_token_factory()
        payload = handlers.jwt_service_decode_handler(token.split()[1])

        class MockRequest:
            @property
            def headers(self):
                return {}

        user, service = auth.authenticate_credentials(MockRequest(), payload)

        assert dict(user) == dict(AnonymousUser)

    async def test_authenticate_credentials_with_user_header(
        self, auth, test_service_token_factory
    ):
        test_user_id = "a6454e643f7f4e8889b7085c466548d4"
        test_user = User(
            id=uuid.UUID(test_user_id).hex,
            level=UserLevels.STAFF,
            is_authenticated=1,
        )
        token = test_service_token_factory()
        payload = handlers.jwt_service_decode_handler(token.split()[1])

        class MockRequest:
            @property
            def headers(self):
                return {
                    settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(
                        test_user
                    )
                }

        user, service = auth.authenticate_credentials(MockRequest(), payload)
        assert dict(user) == dict(test_user)
