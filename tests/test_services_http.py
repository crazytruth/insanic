import importlib

import aiotask_context
import asyncio

import httpx
import jwt
import uvloop
import pytest
import random
import respx
import uuid
import ujson

from httpx.config import UNSET
from sanic.response import json

from insanic import status
from insanic.adapters import match_signature
from insanic.authentication import handlers
from insanic.conf import settings
from insanic.exceptions import ResponseTimeoutError, APIException
from insanic.models import (
    User,
    UserLevels,
    AnonymousRequestService,
    AnonymousUser,
    to_header_value,
)
from insanic.permissions import AllowAny
from insanic.services import Service
from insanic.services.adapters import TransportError, HTTPStatusError
from insanic.services.registry import LazyServiceRegistry
from insanic.views import InsanicView

IMAGE_PATH = "artwork/insanic.png"

dispatch_tests = pytest.mark.parametrize("dispatch_type", ["http_dispatch"])


def httpx_exceptions():
    from insanic.services.adapters import IS_HTTPX_VERSION_0_14

    if IS_HTTPX_VERSION_0_14:
        module_name = "httpx._exceptions"
    else:
        module_name = "httpx.exceptions"

    exceptions_module = importlib.import_module(module_name)

    exceptions = []

    for exc in dir(exceptions_module):
        possible_exception = getattr(exceptions_module, exc)
        try:
            if issubclass(possible_exception, Exception):
                exceptions.append(possible_exception)
        except TypeError:
            pass

    return exceptions


def test_image_file():
    with open(IMAGE_PATH, "rb") as f:
        contents = f
    return contents


settings.TRACING_ENABLED = False


class TestServiceRegistry:
    @pytest.fixture(autouse=True)
    def initialize_service_registry(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_CONNECTIONS", ["test1"])
        self.registry = LazyServiceRegistry()

    def test_set_item(self):
        with pytest.raises(TypeError):
            self.registry["some_service"] = {}

    def test_get_item(self):
        service = self.registry["test1"]

        assert isinstance(service, Service)
        assert service.service_name == "test1"

        with pytest.raises(RuntimeError):
            self.registry["test2"]

    def test_repr(self):
        self.registry.reset()

        assert repr(self.registry).endswith("[Unevaluated]")
        len(self.registry)

        assert repr(self.registry).endswith("ServiceRegistry")


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

    async def run_dispatch(self, *args, **kwargs):
        return await self.service.http_dispatch(*args, **kwargs)

    async def test_init(self):

        auth_token = self.service.service_token
        assert isinstance(auth_token, str)

    def test_service_name(self):
        assert self.service.service_name == self.service_name

    def test_url_constructor(self, monkeypatch):
        monkeypatch.setattr(
            settings, "SERVICE_LIST", {self.service_name: self.service_spec}
        )

        test_endpoint = "/api/v1/insanic"
        url = self.service.client.merge_url(test_endpoint)

        assert url.path == test_endpoint

        test_query_params = {"a": "b"}
        query_params = self.service.client.merge_queryparams(test_query_params)
        url = self.service.client.merge_url(f"{test_endpoint}")

        assert url.path == test_endpoint
        assert dict(query_params) == test_query_params

    def test_dispatch(self):
        mock_response = {"a": "b"}
        mock_status_code = random.randint(200, 300)

        with respx.mock:
            respx.request(
                method="GET",
                url=f"http://{self.service.url.host}:{self.service.url.port}/",
                status_code=mock_status_code,
                content=mock_response,
            )
            respx.request(
                method="GET",
                url=f"http://{self.service.url.host}:{self.service.url.port}/",
                status_code=mock_status_code,
                content=mock_response,
            )

            loop = uvloop.new_event_loop()
            with pytest.raises(ValueError):
                loop.run_until_complete(self.service.http_dispatch("GETS", "/"))

            loop = uvloop.new_event_loop()
            asyncio.set_event_loop(loop)
            fut = self.run_dispatch("GET", "/")
            response = loop.run_until_complete(fut)
            assert response == mock_response

            loop = uvloop.new_event_loop()
            asyncio.set_event_loop(loop)
            response, status_code = loop.run_until_complete(
                self.run_dispatch("GET", "/", include_status_code=True)
            )
            assert response == mock_response
            assert status_code == mock_status_code

    def test_dispatch_response_timeout(self, monkeypatch):
        async def _mock_dispatch(*args, **kwargs):
            assert "response_timeout" in kwargs
            return {"response_timeout": kwargs.get("response_timeout")}

        monkeypatch.setattr(self.service, "_dispatch_future", _mock_dispatch)

        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(self.run_dispatch("GET", "/"))
        assert response["response_timeout"] is UNSET

        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(
            self.run_dispatch(
                "POST", "/", payload={"a": "b"}, response_timeout=10
            )
        )
        assert response["response_timeout"] == 10

    def test_dispatch_dispatch_fetch_response_timeout(self, monkeypatch):
        async def _mock_dispatch_fetch(*args, **kwargs):
            # assert "timeout" in kwargs

            class MockResponse:
                status = 200

                def json(self, *args, **method_kwargs):
                    return {"response_timeout": kwargs.get("timeout", None)}

                async def text(self, *args, **method_kwargs):

                    timeout = kwargs.get("timeout", None)
                    if timeout:
                        import attr

                        timeout = attr.asdict(timeout)

                    return ujson.dumps({"response_timeout": timeout})

            return MockResponse()

        monkeypatch.setattr(
            self.service, "_dispatch_send", _mock_dispatch_fetch
        )

        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)

        response = loop.run_until_complete(
            self.run_dispatch("PUT", "/", payload={"a": "b"})
        )
        assert response["response_timeout"] is UNSET

        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)

        response = loop.run_until_complete(
            self.run_dispatch(
                "POST", "/", payload={"a": "b"}, response_timeout=10
            )
        )
        assert response["response_timeout"] == 10

    async def test_dispatch_catch_connection_timeout(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_TIMEOUT_TOTAL", 1.0)
        self.service._client = None

        async def _mock_open_connection(*args, **kwargs):
            await asyncio.sleep(settings.SERVICE_TIMEOUT_TOTAL + 10)

            return '{"status": "OK"}'

        monkeypatch.setattr("asyncio.open_connection", _mock_open_connection)

        with pytest.raises(ResponseTimeoutError):
            await self.service.http_dispatch("GET", "/")

    @pytest.fixture
    def sanic_test_server(
        self, loop, insanic_application, test_server, monkeypatch
    ):
        monkeypatch.setattr(
            settings._wrapped, "ALLOWED_HOSTS", [], raising=False
        )

        class MockView(InsanicView):
            authentication_classes = []
            permission_classes = [AllowAny]

            async def post(self, request, *args, **kwargs):
                return json(
                    {
                        "data": list(request.data.keys()),
                        "files": list(request.files.keys()),
                    },
                    status=202,
                )

        insanic_application.add_route(MockView.as_view(), "/multi")

        return loop.run_until_complete(
            test_server(insanic_application, host="0.0.0.0")
        )

    @pytest.mark.parametrize(
        "response_code", [k for k in status.REVERSE_STATUS if k >= 400]
    )
    def test_dispatch_raise_for_status(self, response_code):
        """
        raise for different types of response codes

        :param monkeypatch:
        :return:
        """

        loop = uvloop.new_event_loop()
        asyncio.set_event_loop(loop)

        with respx.mock:
            respx.get(
                "http://test:8000/",
                status_code=response_code,
                content={"hello": "hi"},
            )

            with pytest.raises(APIException):
                try:
                    loop.run_until_complete(
                        self.run_dispatch(
                            "GET",
                            "/",
                            payload={},
                            files={},
                            headers={},
                            propagate_error=True,
                        )
                    )
                except APIException as e:
                    assert e.status_code == response_code
                    raise e

    @pytest.mark.parametrize("extra_headers", ({}, {"content-length": 4}))
    async def test_inject_headers(self, extra_headers, loop):
        aiotask_context.set(
            settings.TASK_CONTEXT_REQUEST_USER, {"some": "user"}
        )

        headers = self.service._inject_headers(extra_headers)

        required_headers = [
            "date",
            "x-insanic-request-user",
            "x-insanic-request-id",
        ]

        for h in required_headers:
            assert h in headers.keys()

    @pytest.mark.parametrize(
        "exception",
        (
            TransportError("hello"),
            HTTPStatusError("request", request="request", response="response"),
            ConnectionResetError(),
        ),
    )
    @pytest.mark.parametrize(
        "method, retry_count, expected_attempts",
        (
            ("GET", None, 3),
            ("POST", None, 1),
            ("GET", 2, 3),
            ("PATCH", 4, 1),
            ("GET", 10, 5),
        ),
    )
    async def test_retry_fetch(
        self, monkeypatch, exception, method, retry_count, expected_attempts
    ):
        retry = []

        def raise_error(*args, **kwargs):
            retry.append(True)
            raise exception

        class MockRequest:  # noqa:
            def __init__(self):
                self.method = method

        monkeypatch.setattr(self.service.client, "send", raise_error)

        with pytest.raises(exception.__class__):
            await self.service._dispatch_send(
                MockRequest(), retry_count=retry_count
            )

        assert len(retry) == expected_attempts


class TestServiceClassErrorPropagations:
    async def dispatch_wrapper(self, method, path):
        Service._session = None
        service = Service("test")

        return await service.http_dispatch(
            method,
            path,
            payload={},
            files={},
            headers={},
            propagate_error=True,
        )

    def test_dispatch_actual_internal_server_error(self):
        """
        raise for actual 500 error

        :param monkeypatch:
        :return:
        """

        loop = uvloop.new_event_loop()

        with pytest.raises(APIException):
            try:
                loop.run_until_complete(self.dispatch_wrapper("GET", "/"))
            except APIException as e:
                assert e.status_code == 503
                raise e

    @pytest.mark.parametrize(
        "exception_class",
        (
            # TransportError("transport error!"),
            # HTTPStatusError("message", request="request", response="response"),
            *httpx_exceptions(),
        ),
    )
    def test_http_dispatch_raise_for_httpx_exception(self, exception_class):
        """


        :param monkeypatch:
        :return:
        """

        loop = uvloop.new_event_loop()

        response_signature = match_signature(
            httpx.Response,
            status_code=200,
            content=b"help me too!",
            request=httpx.Request("GET", "http://example.com/"),
        )

        raise_exception = exception_class(
            "help!",
            request=httpx.Request("GET", "http://example.com/"),
            response=httpx.Response(**response_signature),
        )

        with respx.mock:
            respx.get("http://test:8000/a", content=raise_exception)

            with pytest.raises(APIException):
                try:
                    loop.run_until_complete(self.dispatch_wrapper("GET", "/a"))
                except APIException as e:
                    assert e
                    raise e


class TestRequestTaskContext:
    @pytest.fixture()
    def test_user(self):
        test_user_id = "a6454e643f7f4e8889b7085c466548d4"
        return User(
            id=uuid.UUID(test_user_id).hex,
            level=UserLevels.STAFF,
            is_authenticated=True,
        )

    def test_task_context_service_after_authentication(
        self, insanic_application, test_user, test_service_token_factory
    ):
        import aiotask_context

        token = test_service_token_factory()

        class TokenView(InsanicView):
            async def get(self, request, *args, **kwargs):
                user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                assert user is not None
                assert user == dict(test_user)
                request_user = await request.user
                assert user == dict(request_user)

                service = await request.service
                assert service.request_service == "test"

                return json({"hi": "hello"})

        insanic_application.add_route(TokenView.as_view(), "/")
        request, response = insanic_application.test_client.get(
            "/",
            headers={
                "Authorization": token,
                settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(
                    test_user
                ),
            },
        )

        assert response.status == 200

    def test_task_context_service_after_authentication_lower_case(
        self, insanic_application, test_user, test_service_token_factory
    ):
        import aiotask_context

        token = test_service_token_factory()

        class TokenView(InsanicView):
            async def get(self, request, *args, **kwargs):
                user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                assert user is not None
                assert user == dict(test_user)
                request_user = await request.user
                assert user == dict(request_user)

                service = await request.service
                assert service.request_service == "test"

                return json({"hi": "hello"})

        insanic_application.add_route(TokenView.as_view(), "/")
        request, response = insanic_application.test_client.get(
            "/",
            headers={
                "authorization": token,
                settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(
                    test_user
                ),
            },
        )

        assert response.status == 200

    def test_task_context_user_after_authentication(
        self, insanic_application, test_user, test_user_token_factory
    ):
        import aiotask_context

        token = test_user_token_factory(id=test_user.id, level=test_user.level)

        class TokenView(InsanicView):
            async def get(self, request, *args, **kwargs):
                user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                assert user is not None
                assert user == dict(test_user)
                request_user = await request.user
                assert user == dict(request_user)

                service = await request.service
                assert str(service).startswith("AnonymousService")

                return json({"hi": "hello"})

        insanic_application.add_route(TokenView.as_view(), "/")
        request, response = insanic_application.test_client.get(
            "/",
            headers={
                "Authorization": token,
                settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(
                    test_user
                ),
            },
        )

        assert response.status == 200

    async def test_task_context_service_multiple_after_authentication(
        self, insanic_application, test_client, test_service_token_factory
    ):
        import aiotask_context
        import asyncio

        class TokenView(InsanicView):
            async def get(self, request, *args, **kwargs):
                user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                assert user is not None

                request_user = await request.user
                assert user == dict(request_user)

                payload = handlers.jwt_decode_handler(request.auth)
                assert "user" not in payload
                assert user == dict(request_user)

                return json({"user": user})

        insanic_application.add_route(TokenView.as_view(), "/")

        client = await test_client(insanic_application)
        #
        # insanic_application.run(host='127.0.0.1', port=unused_port)
        requests = []
        for i in range(10):
            user = User(id=i, level=UserLevels.STAFF, is_authenticated=True)

            token = test_service_token_factory()
            requests.append(
                client.get(
                    "/",
                    headers={
                        "Authorization": token,
                        settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(
                            user
                        ),
                    },
                )
            )

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            assert r.status == 200

            resp = await r.json()
            assert resp["user"]["id"] == str(i)

    @dispatch_tests
    async def test_task_context_user_dispatch_injection(
        self,
        insanic_application,
        test_client,
        test_user_token_factory,
        monkeypatch,
        dispatch_type,
    ):
        monkeypatch.setattr(settings, "SERVICE_CONNECTIONS", ["userip"])

        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service("userip")

        class TokenView(InsanicView):
            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(
                    settings.TASK_CONTEXT_REQUEST_USER
                )
                request_user = await request.user
                handlers.jwt_decode_handler(request.auth)

                token = UserIPService.service_token
                assert token is not None

                jwt.decode(
                    token,
                    settings.SERVICE_TOKEN_KEY,
                    verify=False,
                    algorithms=[settings.JWT_SERVICE_AUTH["JWT_ALGORITHM"]],
                )

                assert dict(request_user) == context_user

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), "/")

        client = await test_client(insanic_application)

        users = []
        requests = []
        for _ in range(10):
            user, token = test_user_token_factory(
                level=UserLevels.STAFF, return_with_user=True
            )
            requests.append(client.get("/", headers={"Authorization": token}))
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp["user"]["id"] == users[i].id

    async def test_task_context_user_multiple_after_authentication(
        self, insanic_application, test_client, test_user_token_factory,
    ):
        import aiotask_context
        import asyncio

        class TokenView(InsanicView):
            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(
                    settings.TASK_CONTEXT_REQUEST_USER
                )
                request_user = await request.user
                payload = handlers.jwt_decode_handler(request.auth)

                assert context_user is not None

                payload.pop("user_id")
                assert context_user == dict(request_user)

                service = await request.service

                assert service is not None
                assert service == AnonymousRequestService

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), "/")

        client = await test_client(insanic_application)
        #
        # insanic_application.run(host='127.0.0.1', port=unused_port)
        users = []
        requests = []
        for _ in range(10):
            user, token = test_user_token_factory(
                level=UserLevels.STAFF, return_with_user=True
            )
            requests.append(client.get("/", headers={"Authorization": token}))
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp["user"]["id"] == users[i].id

    async def test_task_context_service_http_dispatch_injection(
        self, insanic_application, test_client, test_service_token_factory
    ):
        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service("userip")

        class TokenView(InsanicView):
            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(
                    settings.TASK_CONTEXT_REQUEST_USER
                )
                request_user = await request.user
                handlers.jwt_decode_handler(request.auth)

                token = UserIPService.service_token
                assert token is not None

                assert dict(request_user) == context_user
                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), "/")

        client = await test_client(insanic_application)

        users = []
        requests = []

        for i in range(10):
            user = User(id=i, level=UserLevels.STAFF, is_authenticated=True)

            token = test_service_token_factory()
            requests.append(
                client.get(
                    "/",
                    headers={
                        "Authorization": token,
                        settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(
                            user
                        ),
                    },
                )
            )
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp["user"]["id"] == str(users[i].id)

    async def test_task_context_service_anonymous_http_dispatch_injection(
        self, insanic_application, test_client, test_service_token_factory
    ):
        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service("userip")

        class TokenView(InsanicView):
            permission_classes = [
                AllowAny,
            ]

            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(
                    settings.TASK_CONTEXT_REQUEST_USER
                )
                request_user = await request.user
                handlers.jwt_decode_handler(request.auth)

                token = UserIPService.service_token
                assert token is not None

                jwt.decode(
                    token,
                    settings.SERVICE_TOKEN_KEY,
                    verify=False,
                    algorithms=[settings.JWT_SERVICE_AUTH["JWT_ALGORITHM"]],
                )

                assert dict(request_user) == context_user
                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), "/")

        client = await test_client(insanic_application)

        users = []
        requests = []

        for _ in range(10):
            user = AnonymousUser
            token = test_service_token_factory()
            requests.append(
                client.get(
                    "/",
                    headers={
                        "Authorization": token,
                        settings.INTERNAL_REQUEST_USER_HEADER: to_header_value(
                            user
                        ),
                    },
                )
            )
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp["user"]["id"] == users[i].id

    async def test_task_context_anonymous_user_http_dispatch_injection(
        self, insanic_application, test_client, test_user_token_factory
    ):
        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service("userip")

        class TokenView(InsanicView):
            permission_classes = [
                AllowAny,
            ]

            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(
                    settings.TASK_CONTEXT_REQUEST_USER
                )
                request_user = await request.user
                assert request.auth is None

                token = UserIPService.service_token
                assert token is not None

                jwt.decode(
                    token,
                    settings.SERVICE_TOKEN_KEY,
                    verify=False,
                    algorithms=[settings.JWT_SERVICE_AUTH["JWT_ALGORITHM"]],
                )

                assert dict(request_user) == context_user

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), "/")

        client = await test_client(insanic_application)
        #
        # insanic_application.run(host='127.0.0.1', port=unused_port)
        users = []
        requests = []
        for _ in range(10):
            requests.append(client.get("/"))
            users.append(AnonymousUser)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp["user"]["id"] == str(users[i].id)
