import pytest
import uuid

from insanic import scopes, status
from insanic.app import Insanic
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.exceptions import BadRequest
from insanic.responses import json_response
from insanic.views import InsanicView


class TestLogFormats:

    # @pytest.fixture
    # def insanic_application(selfa, monkeypatch):
    #     monkeypatch.setattr(scopes, 'is_docker', True)
    #     app = Insanic('test')
    #
    #     class NoAuthPermView(InsanicView):
    #         authentication_classes = []
    #         permission_classes = []
    #
    #     class MockView(NoAuthPermView):
    #         async def get(self, request, *args, **kwargs):
    #             return json_response({}, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)
    #
    #     app.add_route(MockView.as_view(), '/log/<user_id:[0-9a-fA-F]{32}>')
    #
    #
    #     yield app
    # #
    # @pytest.fixture
    # def insanic_server(self, loop, insanic_application, test_server, monkeypatch):
    #     monkeypatch.setattr(settings, 'GRPC_PORT_DELTA', 1)
    #     return loop.run_until_complete(test_server(insanic_application))

    @pytest.mark.parametrize(
        "is_json_log",
        (
                True,
                False,
        )
    )
    @pytest.mark.parametrize(
        "endpoint,request_path,response_meta",
        (
                ("/log", "/log", {"a": "b"}),
                ('/log/<user_id:[0-9a-fA-F]{32}>', f'/log/{uuid.uuid4().hex}', {"a": "b"}),
                ("/exception", "/exception", RuntimeError("help")),
                ("/exception/<id>", "/exception/aa", RuntimeError("help")),
                ("/apiexception/<id>", "/apiexception/aa", BadRequest(description="bad request help")),
        )
    )
    def test_log_json(self, is_json_log, monkeypatch, caplog, endpoint, request_path, response_meta):
        """
        test added for 0.6.8.  Added `error_code`, `method`, `path`, `view` in json formatters
        """
        monkeypatch.setattr(scopes, 'is_docker', is_json_log)
        app = Insanic('test')

        class NoAuthPermView(InsanicView):
            authentication_classes = []
            permission_classes = []

        class MockView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                if isinstance(response_meta, Exception):
                    raise response_meta
                else:
                    return json_response(response_meta, status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION)

        app.add_route(MockView.as_view(), endpoint)

        resp = app.test_client.get(request_path)
        for r in caplog.records:
            if r.name == 'sanic.access':
                assert hasattr(r, 'error_code_value')
                assert hasattr(r, 'error_code_name')
                if isinstance(response_meta, Exception):
                    assert r.error_code_value == getattr(response_meta, 'error_code_value',
                                                         GlobalErrorCodes.unknown_error).value
                    assert r.error_code_name.endswith(getattr(response_meta, 'error_code_name',
                                                              GlobalErrorCodes.unknown_error).name)
                else:
                    assert r.error_code_value == None
                    assert r.error_code_name == None

                assert hasattr(r, 'method')
                assert r.method == "GET"

                assert hasattr(r, 'path')
                assert r.path == request_path

                assert hasattr(r, 'uri_template')
                assert r.uri_template == endpoint
