import pytest
import uuid
import ujson as json

from sanic.response import json as json_response

from insanic import status
from insanic.app import Insanic
from insanic.errors import GlobalErrorCodes
from insanic.exceptions import BadRequest
from insanic.views import InsanicView


class TestLogFormats:
    @pytest.mark.parametrize("log_type", ("json", "access",))
    @pytest.mark.parametrize(
        "endpoint,request_path,response_meta",
        (
            ("/log", "/log", {"a": "b"}),
            (
                "/log/<user_id:[0-9a-fA-F]{32}>",
                f"/log/{uuid.uuid4().hex}",
                {"a": "b"},
            ),
            ("/exception", "/exception", RuntimeError("help")),
            ("/exception/<id>", "/exception/aa", RuntimeError("help")),
            (
                "/apiexception/<id>",
                "/apiexception/aa",
                BadRequest(description="bad request help"),
            ),
        ),
    )
    def test_log_json(
        self,
        log_type,
        monkeypatch,
        caplog,
        endpoint,
        request_path,
        response_meta,
    ):
        """
        test added for 0.6.8.  Added `error_code`, `method`, `path`, `view` in json formatters
        """
        monkeypatch.setenv("LOG_TYPE", log_type)
        app = Insanic("test")

        class NoAuthPermView(InsanicView):
            authentication_classes = []
            permission_classes = []

        class MockView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                if isinstance(response_meta, Exception):
                    raise response_meta
                else:
                    return json_response(
                        response_meta,
                        status=status.HTTP_203_NON_AUTHORITATIVE_INFORMATION,
                    )

        app.add_route(MockView.as_view(), endpoint)

        app.test_client.get(request_path)
        for r in caplog.records:
            if r.name == "sanic.access":
                assert hasattr(r, "error_code_value")
                assert hasattr(r, "error_code_name")
                if isinstance(response_meta, Exception):
                    assert (
                        r.error_code_value
                        == getattr(
                            response_meta,
                            "error_code_value",
                            GlobalErrorCodes.unknown_error,
                        ).value
                    )
                    assert r.error_code_name.endswith(
                        getattr(
                            response_meta,
                            "error_code_name",
                            GlobalErrorCodes.unknown_error,
                        ).name
                    )
                else:
                    assert r.error_code_value is None
                    assert r.error_code_name is None

                assert hasattr(r, "method")
                assert r.method == "GET"

                assert hasattr(r, "path")
                assert r.path == request_path

                assert hasattr(r, "uri_template")
                assert r.uri_template == endpoint

    @pytest.mark.parametrize(
        "exc,expected_message",
        (
            (Exception, "<class 'Exception'>"),
            (ValueError, "<class 'ValueError'>"),
            (ValueError("asd"), "asd"),
            (BadRequest, "<class 'insanic.exceptions.BadRequest'>"),
            (BadRequest("bad"), "bad"),
        ),
    )
    def test_exception_logging(
        self, exc, expected_message, capsys, monkeypatch
    ):
        monkeypatch.setenv("LOG_TYPE", "json")
        Insanic("test")
        from insanic.log import error_logger

        error_logger.exception(exc)

        out, err = capsys.readouterr()
        print(err)

        logs = [json.loads(m) for m in err.strip().split("\n")]

        assert logs[-1]["message"] == expected_message
