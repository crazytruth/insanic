from insanic import Insanic
from insanic.authentication import JSONWebTokenAuthentication, handlers
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.testing.helpers import MockService
from insanic.views import InsanicView
from sanic.response import json
import pytest


@pytest.fixture(scope="function")
def test_service_token_factory():
    class MockService:
        service_name = 'test'

    def factory():
        # source, aud, source_ip, destination_version, is_authenticated):
        service = MockService()
        payload = handlers.jwt_service_payload_handler(service)
        return " ".join([settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX'], handlers.jwt_service_encode_handler(payload)])
    return factory

@pytest.mark.parametrize("service_name, has_token, has_service_token, expected",[
    ("test", True, False, 'fired'), # Successful scenario
    ("userip", True, False, None),  # Failed scenario : userip calls itself
    ("test", True, True, None),     # Failed scenario : the request is from a service
    ("test", False, True, None),    # Failed scenario : user is not authenticated user
])
def test_success_senario(service_name, has_token, has_service_token, expected,
                         test_user_token_factory, test_service_token_factory, monkeypatch):

    MockService.register_mock_dispatch('POST', "/api/v1/ip", {}, 201)
    monkeypatch.setattr('insanic.services.Service.http_dispatch', MockService.mock_dispatch)
    app = Insanic(service_name)
    headers = {}

    if has_token:
        token = test_user_token_factory(email="test", level=UserLevels.ACTIVE)
        headers = {"Authorization": token}

    if has_service_token:
        service_token = test_service_token_factory()
        headers.update({"MMT-Authorization": service_token})

    class TestView(InsanicView):
        permission_classes = []
        authentication_classes = [JSONWebTokenAuthentication]

        async def get(self, request, *args, **kwargs):
            return json({}, status=200)

    app.add_route(TestView.as_view(), '/')
    request, response = app.test_client.get('/', headers=headers)

    # If it calls the Userip service in middleware, It attaches userip in its response's header.
    assert response.headers.get('userip', None) == expected
