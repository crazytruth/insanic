from insanic import Insanic
from insanic.authentication import JSONWebTokenAuthentication, handlers
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.testing.helpers import MockService
from insanic.views import InsanicView
from sanic.response import json
import pytest




@pytest.mark.parametrize("service_name, has_token, has_service_token, has_x_forwarded_for, expected",[
    ("test", True, False, True, 'fired'), # Successful scenario
    ("userip", True, False, True, None),  # Failed scenario : userip calls itself
    ("test", True, True, True, None),     # Failed scenario : the request is from a service
    ("test", False, True, True, None),    # Failed scenario : user is not authenticated user
    ("test", True, False, False, None)    # Failed scenario : x-fowarded-for does not exist in the headers
])
def test_userip_middleware(service_name, has_token, has_service_token, has_x_forwarded_for, expected,
                         test_user_token_factory, test_service_token_factory, monkeypatch):

    MockService.register_mock_dispatch('POST', "/api/v1/ip", {}, 201)
    monkeypatch.setattr('insanic.services.Service.http_dispatch', MockService.mock_dispatch)
    app = Insanic(service_name)
    headers = {}

    if has_token:
        user, token = test_user_token_factory(level=UserLevels.ACTIVE, return_with_user=True)
        headers = {"Authorization": token, 'x-consumer-username': user.id}

    if has_service_token:
        service_token = test_service_token_factory()
        headers.update({"Authorization": service_token})

    if has_x_forwarded_for:
        headers.update({"x-forwarded-for": '59.10.109.21, 52.78.247.162, 20.2.131.209'})

    class TestView(InsanicView):
        permission_classes = []
        authentication_classes = [JSONWebTokenAuthentication]

        async def get(self, request, *args, **kwargs):
            return json({}, status=200)

    app.add_route(TestView.as_view(), '/')
    request, response = app.test_client.get('/', headers=headers)

    # If it calls the Userip service in middleware, It attaches userip in its response's header.
    assert response.headers.get('userip', None) == expected
