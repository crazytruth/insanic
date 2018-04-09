import aiohttp
import uvloop
import pytest
import random

from yarl import URL

from insanic.conf import settings
from insanic.exceptions import ServiceUnavailable503Error
from insanic.services import ServiceRegistry, Service


class TestServiceRegistry:

    @pytest.fixture(autouse=True)
    def initialize_service_registry(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_CONNECTIONS", ["test1"])
        self.registry = ServiceRegistry()

    def test_singleton(self):
        new_registry = ServiceRegistry()
        assert self.registry is new_registry

    def test_set_item(self):
        with pytest.raises(RuntimeError):
            self.registry['some_service'] = {}

    def test_get_item(self):
        service = self.registry['test1']

        assert isinstance(service, Service)
        assert service.service_name == "test1"

        with pytest.raises(RuntimeError):
            s = self.registry['test2']


class TestServiceClass:
    service_name = "test"
    service_spec = {
        "schema": "test-schema",
        "host": "test-host",
        "internal_service_port": random.randint(1000, 2000),
        "external_service_port": random.randint(2000, 3000),
    }

    @pytest.fixture(autouse=True)
    def initialize_service(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_LIST", {}, raising=False)
        self.service = Service(self.service_name)

    def test_init(self):
        assert self.service._registry is ServiceRegistry()
        assert self.service._session is None

        auth_token = self.service._service_auth_token
        assert isinstance(auth_token, str)

    def test_service_name(self):
        assert self.service.service_name == self.service_name

    def test_service_spec(self, monkeypatch):
        assert self.service._service_spec() == {}

        with pytest.raises(ServiceUnavailable503Error):
            self.service._service_spec(True)

        monkeypatch.setattr(settings, "SERVICE_LIST", {self.service_name: self.service_spec})

        assert self.service._service_spec() == self.service_spec
        assert self.service.schema == self.service_spec['schema']
        assert self.service.host == self.service_spec['host']
        assert self.service.port == self.service_spec['external_service_port']

        url = self.service.url
        assert isinstance(url, URL)
        assert url.scheme == self.service_spec['schema']
        assert url.host == self.service_spec['host']
        assert url.port == self.service_spec['external_service_port']
        assert url.path == "/api/v1/"

        assert isinstance(self.service.session, aiohttp.ClientSession)

    def test_url_constructor(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_LIST", {self.service_name: self.service_spec})

        test_endpoint = "/api/v1/insanic"
        url = self.service._construct_url(test_endpoint)

        assert url.path == test_endpoint

        test_query_params = {"a": "b"}
        url = self.service._construct_url(test_endpoint, query_params=test_query_params)
        assert url.path == test_endpoint
        assert url.query == test_query_params

    def test_http_dispatch(self, monkeypatch):

        mock_response = {"a": "b"}
        mock_status_code = random.randint(200, 300)

        async def _mock_dispatch(*args, **kwargs):
            class MockResponse:
                async def text(self):
                    import ujson as json
                    return json.dumps(mock_response)

            return MockResponse(), mock_status_code

        monkeypatch.setattr(self.service, '_dispatch', _mock_dispatch)

        loop = uvloop.new_event_loop()
        with pytest.raises(ValueError):
            loop.run_until_complete(self.service.http_dispatch("GETS", "/"))

        loop = uvloop.new_event_loop()
        response = loop.run_until_complete(self.service.http_dispatch('GET', '/'))
        assert response == mock_response

        loop = uvloop.new_event_loop()
        response, status_code = loop.run_until_complete(
            self.service.http_dispatch('GET', '/', include_status_code=True))
        assert response == mock_response
        assert status_code == mock_status_code

    @pytest.mark.parametrize("extra_headers", ({}, {"content-length": 4}))
    def test_prepare_headers(self, extra_headers):
        headers = self.service._prepare_headers(extra_headers)

        required_headers = ["Accept", "Content-Type", "Date", "MMT-Authorization"]

        for h in required_headers:
            assert h in headers.keys()

        for h in self.service.remove_headers:
            assert h not in headers.keys()

        assert headers['MMT-Authorization'].startswith("MSA")
        assert headers['MMT-Authorization'].endswith(self.service._service_auth_token)
        assert len(headers['MMT-Authorization'].split(' ')) == 2
