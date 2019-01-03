import asyncio
import pytest

from grpclib.client import Channel
from grpclib.health.v1.health_pb2 import HealthCheckRequest
from grpclib.health.v1.health_grpc import HealthStub

from insanic.app import Insanic
from insanic.grpc.server import GRPCServer


class StubHelper:
    def channel(self, host, port):
        return Channel(host=host, port=port, loop=asyncio.get_event_loop())

    def health_stub(self, host, port):
        return HealthStub(self.channel(host, port))

    def health_check_request(self, service_name):
        return HealthCheckRequest(service=service_name)


class TestGRPCServerClass(StubHelper):

    @pytest.fixture(autouse=True)
    def clean_up(self):
        yield
        GRPCServer._GRPCServer__instance = None
        GRPCServer._grpc_server = None

    def test_singleton(self):
        grpc = GRPCServer([])

        with pytest.raises(AssertionError):
            GRPCServer([])

        assert grpc is GRPCServer._GRPCServer__instance

    async def test_server_start_stop(self, unused_port):
        grpc = GRPCServer([])
        host = '127.0.0.1'
        await grpc.start(host, unused_port)
        assert grpc._grpc_server._server is not None
        await grpc.stop()
        assert grpc._grpc_server is None


class TestGRPCInsanicServer(StubHelper):

    @pytest.fixture
    def insanic_application(self):
        app = Insanic('test')
        yield app

    @pytest.fixture
    def insanic_server(self, loop, insanic_application, test_server):
        return loop.run_until_complete(test_server(insanic_application))

    async def test_start_stop_listeners(self, insanic_server):
        with pytest.raises(AssertionError):
            GRPCServer([])

        grpc = GRPCServer.instance()

        request = HealthCheckRequest(service="insanic.v1.Dispatch")
        health = await self.health_stub(insanic_server.host, grpc._port).Check(request, timeout=10)

        assert health.status is 1
