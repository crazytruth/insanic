import pytest

from insanic.app import Insanic
from insanic.conf import settings
from insanic.services import Service
from insanic.services.grpc import GRPCServingStatus


class TestGRPCHealth:

    @pytest.fixture
    def insanic_application(selfa):
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
    def service_instance(self, monkeypatch, insanic_server):
        test_service = Service('test')

        monkeypatch.setattr(test_service, 'host', '127.0.0.1')
        monkeypatch.setattr(test_service, 'port', insanic_server.port)
        # monkeypatch.setattr(test_service, '_status', 1)
        # monkeypatch.setattr(test_service, '_status_check', time.monotonic())

        return test_service

    async def test_health_checks(self, insanic_server, service_instance):
        assert service_instance.status is None
        assert service_instance._status_check is 0
        await service_instance.health_check()
        assert service_instance.status == GRPCServingStatus.SERVING
