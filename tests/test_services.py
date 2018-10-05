import pytest
import time
import uuid

from insanic.app import Insanic
from insanic.conf import settings
from insanic.exceptions import ServiceUnavailable503Error
from insanic.grpc.server import GRPCServer
from insanic.services import Service

GRPC_RESPONSE = 'grpc'
HTTP_RESPONSE = 'http'


class TestServiceDispatch:

    @pytest.fixture
    def insanic_application(self):
        app = Insanic('test')

        yield app

    @pytest.fixture
    def insanic_server(self, loop, insanic_application, test_server, monkeypatch):
        monkeypatch.setattr(settings, 'GRPC_PORT_DELTA', 1)

        return loop.run_until_complete(test_server(insanic_application))

    @pytest.fixture(autouse=True)
    def initialize_service(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_LIST", {}, raising=False)

    @pytest.fixture
    def grpc_instance(self, monkeypatch):
        return GRPCServer.instance()

    @pytest.fixture
    def service_instance(self, monkeypatch, insanic_server):
        test_service = Service('test')

        monkeypatch.setattr(test_service, 'host', '127.0.0.1')
        monkeypatch.setattr(test_service, 'port', insanic_server.port)
        monkeypatch.setattr(test_service, '_status', 1)
        monkeypatch.setattr(test_service, '_status_check', time.monotonic())

        async def mock_grpc_dispatch(*args, **kwargs):
            return GRPC_RESPONSE

        async def mock_http_dispatch(*args, **kwargs):
            return HTTP_RESPONSE

        async def mock_health_status():
            return True

        monkeypatch.setattr(test_service, 'health_status', mock_health_status)

        monkeypatch.setattr(test_service, 'grpc_dispatch', mock_grpc_dispatch)
        monkeypatch.setattr(test_service, 'http_dispatch', mock_http_dispatch)

        return test_service

    async def test_dispatch_grpc_health_is_serving(self, service_instance):
        response = await service_instance.dispatch('GET', '/')

        assert response == GRPC_RESPONSE

    async def test_dispatch_connection_error(self, service_instance, monkeypatch):
        async def mock_grpc_dispatch_connection_error(*args, **kwargs):
            raise ConnectionRefusedError

        monkeypatch.setattr(service_instance, 'grpc_dispatch', mock_grpc_dispatch_connection_error)

        response = await service_instance.dispatch('GET', '/')
        assert response == HTTP_RESPONSE

    async def test_dispatch_unknown_grpc_error(self, service_instance, monkeypatch, caplog):
        async def mock_grpc_dispatch_connection_error(*args, **kwargs):
            raise NotImplementedError

        monkeypatch.setattr(service_instance, 'grpc_dispatch', mock_grpc_dispatch_connection_error)

        response = await service_instance.dispatch('GET', '/')
        assert response == HTTP_RESPONSE
        assert caplog.records[0].message == "Error with grpc"

    async def test_dispatch_grpc_http_error(self, service_instance, monkeypatch):
        async def mock_grpc_dispatch_connection_error(*args, **kwargs):
            raise NotImplementedError

        async def mock_http_dispatch_error(*args, **kwargs):
            return None

        monkeypatch.setattr(service_instance, 'grpc_dispatch', mock_grpc_dispatch_connection_error)
        monkeypatch.setattr(service_instance, 'http_dispatch', mock_http_dispatch_error)

        with pytest.raises(ServiceUnavailable503Error):
            await service_instance.dispatch('GET', '/')
