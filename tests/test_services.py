import pytest
import time
import uuid

from insanic.app import Insanic
from insanic.conf import settings
from insanic.exceptions import ServiceUnavailable503Error, BadRequest
from insanic.services import Service

HTTP_RESPONSE = 'http'


class TestServiceDispatch:

    @pytest.fixture
    def insanic_application(self):
        app = Insanic('test')

        yield app

    @pytest.fixture
    def insanic_server(self, loop, insanic_application, test_server, monkeypatch):

        return loop.run_until_complete(test_server(insanic_application))

    @pytest.fixture(autouse=True)
    def initialize_service(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_LIST", {}, raising=False)

    @pytest.fixture
    def service_instance(self, monkeypatch, insanic_server):
        test_service = Service('test')

        monkeypatch.setattr(test_service, 'host', '127.0.0.1')
        monkeypatch.setattr(test_service, 'port', insanic_server.port)
        monkeypatch.setattr(test_service, '_status', 1)
        monkeypatch.setattr(test_service, '_status_check', time.monotonic())

        async def mock_http_dispatch(*args, **kwargs):
            return HTTP_RESPONSE

        async def mock_health_status():
            return True

        monkeypatch.setattr(test_service, 'health_status', mock_health_status)

        monkeypatch.setattr(test_service, 'http_dispatch', mock_http_dispatch)

        return test_service
