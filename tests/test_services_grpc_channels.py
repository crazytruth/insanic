import time
import pytest

from insanic.app import Insanic
from insanic.conf import settings
from insanic.services import Service
from insanic.services.grpc import ChannelManager, Channel


class TestChannelManager:
    @pytest.fixture
    def insanic_application(selfa):
        app = Insanic('test')

        yield app

    @pytest.fixture
    def service_instance(self, monkeypatch, insanic_server):
        monkeypatch.setattr(Service, 'host', '127.0.0.1')
        monkeypatch.setattr(Service, 'port', insanic_server.port)
        test_service = Service('test')

        monkeypatch.setattr(test_service, '_status', 1)
        monkeypatch.setattr(test_service, '_status_check', time.monotonic())

        return test_service

    @pytest.fixture
    def insanic_server(self, loop, insanic_application, test_server, monkeypatch):
        monkeypatch.setattr(settings, 'GRPC_PORT_DELTA', 1)

        return loop.run_until_complete(test_server(insanic_application))

    @pytest.fixture
    def channel_manager(self, service_instance):
        return ChannelManager(service_instance.host, service_instance.port)

    def test_init(self, service_instance, channel_manager):
        assert channel_manager._channel is None
        assert channel_manager.host == service_instance.host
        assert channel_manager.port == service_instance.port

    def test_add_channel(self, service_instance, channel_manager):
        channel_manager.add_channel(service_instance.host, service_instance.port)

        assert len(channel_manager._channel) is 1
        channel = channel_manager._channel[service_instance.host]
        assert channel._host == service_instance.host
        assert channel._port == service_instance.port

        channel_manager.add_channel('127.0.0.2', 9999)
        assert len(channel_manager._channel) is 2
        assert channel_manager._channel['127.0.0.2'] is not None

    def test_remove_channel(self, service_instance, channel_manager):
        channel_manager.add_channel(service_instance.host, service_instance.port)

        assert len(channel_manager._channel) is 1

        fake_channel = "fake"

        channel_manager.remove_channel(fake_channel)

        channel = channel_manager._channel[service_instance.host]
        channel_manager.remove_channel(channel)
        assert len(channel_manager._channel) is 0

    def test_close_all(self, service_instance, channel_manager):

        channel_manager.close_all()

        channel_count = 5

        for i in range(channel_count):
            channel_manager.add_channel(f'127.0.0.{i}', service_instance.port)

        assert len(channel_manager._channel) == channel_count

        channel_manager.close_all()

        assert len(channel_manager._channel) == 0

    @pytest.mark.parametrize("host", ("127.0.0.1", 'localhost', 'www.google.com'))
    async def test_get_channel(self, service_instance, host):

        channel_manager = ChannelManager(host, service_instance.port)
        channel = await channel_manager.get_channel()

        assert len(channel_manager._channel) > 0
        assert channel in channel_manager._channel.values()
        assert isinstance(channel, Channel)

    async def test_host_resolve(self, service_instance, channel_manager, monkeypatch):

        ttl = 60

        async def mock_query(host, type):
            from pycares import ares_query_simple_result
            return [ares_query_simple_result(('192.168.2.254', ttl)),
                    ares_query_simple_result(('192.168.2.251', ttl))]

        monkeypatch.setattr(channel_manager._resolver, 'query', mock_query)

        channel_manager.host = "test.local"

        await channel_manager.resolve_host()
        assert len(channel_manager._channel) == 2
        assert time.monotonic() + ttl - 1 < channel_manager._channel_update_time < time.monotonic() + ttl + 1

        channel = await channel_manager.get_channel()
        assert channel in channel_manager._channel.values()

    async def test_resolve_periodically(self, channel_manager, monkeypatch):
        ttl = 2

        class mock_query:
            call_count = 0

            async def __call__(self, host, type):
                self.call_count += 1
                from pycares import ares_query_simple_result
                return [ares_query_simple_result(('192.168.2.254', ttl)),
                        ares_query_simple_result(('192.168.2.251', ttl))]

        mock_query_object = mock_query()

        monkeypatch.setattr(channel_manager._resolver, 'query', mock_query_object)

        channel_manager.host = "test.local"

        channel = await channel_manager.get_channel()
        assert mock_query_object.call_count == 1
        channel = await channel_manager.get_channel()
        assert mock_query_object.call_count == 1

        time.sleep(2)
        channel = await channel_manager.get_channel()
        assert mock_query_object.call_count == 2

    async def test_load_balance(self, channel_manager, monkeypatch):
        ttl = 2

        class mock_query:
            call_count = 0

            async def __call__(self, host, type):
                self.call_count += 1
                from pycares import ares_query_simple_result
                return [ares_query_simple_result(('192.168.2.254', ttl)),
                        ares_query_simple_result(('192.168.2.251', ttl))]

        mock_query_object = mock_query()

        monkeypatch.setattr(channel_manager._resolver, 'query', mock_query_object)

        channel_manager.host = "test.local"

        tracking = {}

        iterations = 1000
        for i in range(iterations):
            channel = await channel_manager.get_channel()

            if channel not in tracking:
                tracking[channel] = 0

            tracking[channel] += 1

        assert len(tracking) == 2
        assert sum(tracking.values()) == iterations

        half_iterations = iterations / 2
        half_iterations_tenth = half_iterations / 10
        assert all([half_iterations - half_iterations_tenth < count < half_iterations + half_iterations_tenth
                    for c, count in tracking.items()])
