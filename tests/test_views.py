import pytest
import uuid

from sanic.response import json
from insanic import Insanic, authentication, permissions, status
from insanic.authentication import UserLevels
from insanic.errors import GlobalErrorCodes
from insanic.views import InsanicView
from insanic.models import User


@pytest.fixture(scope="session")
def test_user_token_factory():
    from insanic.conf import settings
    from insanic.authentication import handlers

    def factory(id=uuid.uuid4(), *, email, level):
        user = User(**{"id": id.hex, 'email': email, 'level': level})
        payload = handlers.jwt_payload_handler(user)
        return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], handlers.jwt_encode_handler(payload)])

    return factory


def test_view_allowed_methods():
    class TestView(InsanicView):
        def patch(self, request):
            return

    view = TestView()

    assert view.allowed_methods == ['PATCH']


def test_view_default_response_headers():
    class TestView(InsanicView):
        def patch(self, request):
            return

    view = TestView()

    assert view.default_response_headers == {"Allow": "PATCH"}


def test_view_invalid_method():
    app = Insanic('test')
    response_body = {"insanic": "Gotta go insanely fast!"}

    class DummyView(InsanicView):
        authentication_classes = ()
        permission_classes = ()

        def get(self, request):
            return json(response_body)

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.post('/')

    assert response.status == status.HTTP_405_METHOD_NOT_ALLOWED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.method_not_allowed


def test_view_only_json_authentication():
    app = Insanic('test')

    class DummyView(InsanicView):
        authentication_classes = (authentication.JSONWebTokenAuthentication,)

        def get(self, request):
            return json({})

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.get('/')

    assert response.status == status.HTTP_401_UNAUTHORIZED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.authentication_credentials_missing


def test_view_permission(test_user_token_factory):
    app = Insanic('test')
    response_body = {"insanic": "Gotta go insanely fast!"}

    class DummyView(InsanicView):
        authentication_classes = (authentication.JSONWebTokenAuthentication,)
        permission_classes = (permissions.IsAuthenticated,)

        def get(self, request):
            return json(response_body)

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.get('/')

    assert response.status == status.HTTP_401_UNAUTHORIZED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.authentication_credentials_missing

    request, response = app.test_client.get('/', headers={"Authorization": "Bearer lalfjafafa"})

    assert response.status == status.HTTP_401_UNAUTHORIZED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.authentication_credentials_missing

    request, response = app.test_client.get('/', headers={
        "Authorization": test_user_token_factory(email="test@mmt.com", level=UserLevels.BANNED)})

    assert response.status == status.HTTP_401_UNAUTHORIZED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.inactive_user

    request, response = app.test_client.get('/', headers={
        "Authorization": test_user_token_factory(email="test@mmt.com", level=UserLevels.DEACTIVATED)})

    assert response.status == status.HTTP_401_UNAUTHORIZED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.inactive_user

    request, response = app.test_client.get('/', headers={
        "Authorization": test_user_token_factory(email="test@mmt.com", level=UserLevels.ACTIVE)})

    assert response.status == status.HTTP_200_OK
    assert response.json == response_body

    request, response = app.test_client.get('/', headers={
        "Authorization": test_user_token_factory(email="test@mmt.com", level=UserLevels.STAFF)})

    assert response.status == status.HTTP_200_OK
    assert response.json == response_body


@pytest.mark.parametrize('user_level', range(UserLevels.ACTIVE, UserLevels.STAFF, 10))
def test_permission_denied(test_user_token_factory, user_level):
    app = Insanic('test')
    response_body = {"insanic": "Gotta go insanely fast!"}

    class DummyView(InsanicView):
        authentication_classes = (authentication.JSONWebTokenAuthentication,)
        permission_classes = (permissions.IsAdminUser,)

        def get(self, request):
            return json(response_body)

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.get('/', headers={
        "Authorization": test_user_token_factory(email="test@mmt.com", level=user_level)})

    assert response.status == status.HTTP_403_FORBIDDEN
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.permission_denied


@pytest.mark.parametrize('user_level', range(UserLevels.STAFF, UserLevels.STAFF + 100, 10))
def test_is_admin(test_user_token_factory, user_level):
    app = Insanic('test')
    response_body = {"insanic": "Gotta go insanely fast!"}

    class DummyView(InsanicView):
        authentication_classes = (authentication.JSONWebTokenAuthentication,)
        permission_classes = (permissions.IsAdminUser,)

        def get(self, request):
            return json(response_body)

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.get('/', headers={
        "Authorization": test_user_token_factory(email="test@mmt.com", level=user_level)})

    assert response.status == status.HTTP_200_OK
    assert response.json == response_body


def test_throttle():
    app = Insanic('test')
    wait_time = 1000

    from insanic.throttles import BaseThrottle
    class ForceThrottle(BaseThrottle):
        async def allow_request(self, *args, **kwargs):
            return False

        def wait(self, *args, **kwargs):
            return wait_time

    class DummyView(InsanicView):
        authentication_classes = ()
        permission_classes = ()
        throttle_classes = (ForceThrottle,)

        def get(self, request):
            return json({"hello": "bye"})

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.get('/')

    assert response.status == status.HTTP_429_TOO_MANY_REQUESTS
    assert str(wait_time) in response.json['description']
