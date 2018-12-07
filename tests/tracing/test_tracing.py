import aiohttp
import pytest
import logging
import requests

from insanic.app import Insanic
from insanic.conf import settings
from insanic.tracing import InsanicTracer
from insanic.responses import json_response
from insanic.services import Service
from insanic.views import InsanicView

logger = logging.getLogger(__name__)


def _mock_check_prerequisites(*args, **kwargs):
    return []


class TestTracing:

    @pytest.fixture
    def insanic_application(self, monkeypatch):

        monkeypatch.setattr(InsanicTracer, "_check_prerequisites", _mock_check_prerequisites)

        return Insanic('test')

    def test_tracing_initialization(self, insanic_application):

        assert hasattr(insanic_application, "tracer")
        assert insanic_application.tracer is not None
        assert hasattr(insanic_application, "sampler")
        assert insanic_application.sampler is not None

    async def test_tracing_enabled_false(self, sanic_test_server, monkeypatch):
        monkeypatch.setattr(settings._wrapped, 'TRACING_ENABLED', False, raising=False)
        monkeypatch.setattr(settings, "SERVICE_LIST", {}, raising=False)
        session = aiohttp.ClientSession()

        flag = 0
        for i in range(10):
            url = f"http://127.0.0.1:{sanic_test_server.port}/trace?expected_sample={flag}"
            async with session.request('GET', url) as resp:
                await resp.read()
                resp.raise_for_status()

                assert resp.status == 202, resp.text

    @pytest.fixture()
    def sanic_test_server(self, loop, test_server, sanic_test_server_2, monkeypatch):
        sr = {
            "version": 1,
            "rules": [],
            "default": {
                "fixed_target": 1,
                "rate": 0
            }
        }
        monkeypatch.setattr(settings._wrapped, 'SAMPLING_RULES', sr, raising=False)
        monkeypatch.setattr(settings._wrapped, 'TRACING_ENABLED', True, raising=False)
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", [], raising=False)
        monkeypatch.setattr(settings._wrapped, "GRPC_SERVE", False, raising=False)
        monkeypatch.setattr(InsanicTracer, "_check_prerequisites", _mock_check_prerequisites)

        insanic_application = Insanic('test')

        class MockView(InsanicView):
            authentication_classes = []
            permission_classes = []

            async def get(self, request, *args, **kwargs):
                assert request.segment.sampled is bool(int(request.query_params.get('expected_sample')))
                assert request.segment.in_progress is True

                return json_response({}, status=202)

        class MockInterServiceView(InsanicView):
            authentication_classes = []
            permission_classes = []

            async def get(self, request, *args, **kwargs):
                expected_sample = bool(int(request.query_params.get('expected_sample')))
                try:
                    assert request.segment.sampled is expected_sample
                    assert request.segment.in_progress is True
                except AssertionError as e:
                    logger.exception("assertion error")
                    raise

                service = Service('test')
                monkeypatch.setattr(service, "host", "127.0.0.1")
                monkeypatch.setattr(service, "port", sanic_test_server_2.port)

                resp, status = await service.http_dispatch('GET', f'/trace_2',
                                                           query_params={"expected_sample": int(expected_sample)},
                                                           include_status_code=True)
                assert status == 201
                assert resp == {"i am": "service_2"}, resp

                return json_response({}, status=202)

        insanic_application.add_route(MockView.as_view(), '/trace')
        insanic_application.add_route(MockInterServiceView.as_view(), '/trace_1')

        return loop.run_until_complete(test_server(insanic_application, host='0.0.0.0'))

    @pytest.fixture()
    def sanic_test_server_2(self, loop, test_server, monkeypatch):
        sr = {
            "version": 1,
            "rules": [],
            "default": {
                "fixed_target": 1,
                "rate": 0
            }
        }
        monkeypatch.setattr(settings._wrapped, 'SAMPLING_RATE', sr, raising=False)
        monkeypatch.setattr(settings._wrapped, 'TRACING_ENABLED', False, raising=False)
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", [], raising=False)
        monkeypatch.setattr(settings._wrapped, "GRPC_SERVE", False, raising=False)
        monkeypatch.setattr(InsanicTracer, "_check_prerequisites", _mock_check_prerequisites)

        insanic_application = Insanic('test')

        class MockView(InsanicView):
            authentication_classes = []
            permission_classes = []

            async def get(self, request, *args, **kwargs):
                assert request.segment.sampled is bool(int(request.query_params.get('expected_sample')))
                assert request.segment.in_progress is True

                return json_response({"i am": "service_2"}, status=201)

        insanic_application.add_route(MockView.as_view(), '/trace_2')

        return loop.run_until_complete(test_server(insanic_application, host='0.0.0.0'))

    async def test_trace_middleware(self, sanic_test_server, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_LIST", {}, raising=False)
        session = aiohttp.ClientSession()

        flag = 1
        for i in range(10):
            url = f"http://127.0.0.1:{sanic_test_server.port}/trace?expected_sample={flag}"
            async with session.request('GET', url) as resp:
                await resp.read()
                resp.raise_for_status()

                assert resp.status == 202, resp.text

                if flag is 1:
                    flag = 0

    async def test_trace_middleware_interservice(self, sanic_test_server, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_LIST", {}, raising=False)
        session = aiohttp.ClientSession()

        flag = 1
        for i in range(10):
            url = f"http://127.0.0.1:{sanic_test_server.port}/trace_1?expected_sample={flag}"
            async with session.request('GET', url) as resp:
                await resp.read()
                resp.raise_for_status()

                assert resp.status == 202, resp.text

                if flag is 1:
                    flag = 0
