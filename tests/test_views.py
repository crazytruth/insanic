import pytest
from insanic.conf import settings

from sanic.exceptions import _sanic_exceptions
from sanic.response import json
from insanic import Insanic, authentication, permissions, status
from insanic.choices import UserLevels
from insanic.errors import GlobalErrorCodes
from insanic.views import InsanicView


@pytest.fixture(autouse=True)
def kong_gateway(monkeypatch):
    monkeypatch.setattr(settings, "GATEWAY_REGISTRATION_ENABLED", True)
    monkeypatch.setattr(settings, "KONG_HOST", 'kong.msa.swarm')
    monkeypatch.setattr(settings, "KONG_ADMIN_PORT", 18001)
    monkeypatch.setattr(settings, "KONG_PLUGIN", {"JSONWebTokenAuthentication": "jwt"})


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


def test_not_found():
    app = Insanic('test')

    class DummyView(InsanicView):
        authentication_classes = ()

        def get(self, request):
            return json({})

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.get('/aaaa')

    assert response.status == status.HTTP_404_NOT_FOUND


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
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.signature_not_decodable

    user, token = test_user_token_factory(level=UserLevels.BANNED, return_with_user=True)
    request, response = app.test_client.get('/', headers={
        "Authorization": token, 'x-consumer-username': user.id})

    assert response.status == status.HTTP_401_UNAUTHORIZED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.inactive_user

    user, token = test_user_token_factory(level=UserLevels.DEACTIVATED, return_with_user=True)
    request, response = app.test_client.get('/', headers={
        "Authorization": token, 'x-consumer-username': user.id})

    assert response.status == status.HTTP_401_UNAUTHORIZED
    assert GlobalErrorCodes(response.json['error_code']['value']) == GlobalErrorCodes.inactive_user

    user, token = test_user_token_factory(level=UserLevels.ACTIVE, return_with_user=True)
    request, response = app.test_client.get('/', headers={
        "Authorization": token, 'x-consumer-username': user.id})

    assert response.status == status.HTTP_200_OK
    assert response.json == response_body

    user, token = test_user_token_factory(level=UserLevels.STAFF, return_with_user=True)
    request, response = app.test_client.get('/', headers={
        "Authorization": token, 'x-consumer-username': user.id})

    assert response.status == status.HTTP_200_OK
    assert response.json == response_body


@pytest.mark.parametrize('user_level', range(UserLevels.ACTIVE, UserLevels.STAFF, 10))
def test_permission_denied(test_user_token_factory, user_level, monkeypatch):
    app = Insanic('test')
    response_body = {"insanic": "Gotta go insanely fast!"}

    class DummyView(InsanicView):
        authentication_classes = (authentication.JSONWebTokenAuthentication,)
        permission_classes = (permissions.IsAdminUser,)

        def get(self, request):
            return json(response_body)

    app.add_route(DummyView.as_view(), '/')

    user, token = test_user_token_factory(level=user_level, return_with_user=True)

    request, response = app.test_client.get('/', headers={
        "Authorization": token, 'x-consumer-username': user.id})

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

    user, token = test_user_token_factory(level=user_level, return_with_user=True)

    request, response = app.test_client.get('/', headers={
        "Authorization": token, 'x-consumer-username': user.id})

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


@pytest.mark.parametrize("sanic_exception", _sanic_exceptions.values())
def test_sanic_error_handling(sanic_exception):
    app = Insanic('test')

    class ContentRange:
        total = 120

    if sanic_exception.status_code == 416:
        raised_exception = sanic_exception("a", ContentRange())
    elif sanic_exception.status_code == 405:
        raised_exception = sanic_exception("a", 'HEAD', ['GET'])
    else:
        raised_exception = sanic_exception("a")

    class DummyView(InsanicView):
        authentication_classes = ()
        permission_classes = ()

        def get(self, request):
            raise raised_exception

    app.add_route(DummyView.as_view(), '/')

    request, response = app.test_client.get('/')

    assert response.status == raised_exception.status_code
    assert response.json['description'] == "a"

    if hasattr(raised_exception, "headers"):
        for k, v in raised_exception.headers.items():
            if raised_exception.status_code == 405 and k.lower() == 'content-length':
                continue

            assert k in response.headers.keys()
            assert str(v) == response.headers[k]
