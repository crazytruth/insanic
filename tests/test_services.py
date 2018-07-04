import aiohttp
import aiotask_context
import asyncio
import jwt
import uvloop
import pytest
import random
import uuid
import ujson

from aioresponses import aioresponses
from sanic.request import File
from sanic.response import json

from insanic import status
from insanic.authentication import handlers
from insanic.conf import settings
from insanic.exceptions import ServiceTimeoutError, APIException
from insanic.models import User, UserLevels, AnonymousRequestService, AnonymousUser
from insanic.permissions import AllowAny
from insanic.services import ServiceRegistry, Service
from insanic.services.response import InsanicResponse
from insanic.views import InsanicView


def test_image_file():
    with open('insanic.png', 'rb') as f:
        contents = f
    return contents


settings.TRACING_ENABLED = False

class TestServiceRegistry:

    @pytest.fixture(autouse=True)
    def initialize_service_registry(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_CONNECTIONS", ["test1"])
        ServiceRegistry.reset()
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

    async def test_init(self):
        assert self.service._registry is ServiceRegistry()
        assert self.service._session is None

        auth_token = self.service.service_auth_token
        assert isinstance(auth_token, str)

    def test_service_name(self):
        assert self.service.service_name == self.service_name

    # @pytest.mark.skip(reason="SERVICE_LIST is now deprecated")
    # def test_service_spec(self, monkeypatch):
    #     assert self.service._service_spec() == {}
    #
    #     with pytest.raises(ServiceUnavailable503Error):
    #         self.service._service_spec(True)
    #
    #     monkeypatch.setattr(settings, "SERVICE_LIST", {self.service_name: self.service_spec})
    #
    #     assert self.service._service_spec() == self.service_spec
    #     assert self.service.schema == self.service_spec['schema']
    #     assert self.service.host == self.service_spec['host']
    #     assert self.service.port == self.service_spec['external_service_port']
    #
    #     url = self.service.url
    #     assert isinstance(url, URL)
    #     assert url.scheme == self.service_spec['schema']
    #     assert url.host == self.service_spec['host']
    #     assert url.port == self.service_spec['external_service_port']
    #     assert url.path == "/api/v1/"
    #
    #     assert isinstance(self.service.session, aiohttp.ClientSession)

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

            return mock_response, mock_status_code

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

    def test_http_dispatch_request_timeout(self, monkeypatch):

        async def _mock_dispatch(*args, **kwargs):
            assert "request_timeout" in kwargs
            return {"request_timeout": kwargs.get('request_timeout')}, 200

        monkeypatch.setattr(self.service, '_dispatch', _mock_dispatch)

        loop = uvloop.new_event_loop()

        response = loop.run_until_complete(self.service.http_dispatch('GET', '/'))
        assert response['request_timeout'] is None

        loop = uvloop.new_event_loop()

        response = loop.run_until_complete(
            self.service.http_dispatch('POST', '/', payload={"a": "b"}, request_timeout=10))
        assert response['request_timeout'] is 10

    def test_http_dispatch_dispatch_fetch_request_timeout(self, monkeypatch):

        async def _mock_dispatch_fetch(*args, **kwargs):
            assert "request_timeout" in kwargs

            class MockResponse:
                status = 200

                async def json(self, *args, **method_kwargs):
                    return {"request_timeout": kwargs['request_timeout']}

            return MockResponse()

        monkeypatch.setattr(self.service, '_dispatch_fetch', _mock_dispatch_fetch)

        loop = uvloop.new_event_loop()

        response = loop.run_until_complete(
            self.service.http_dispatch('PUT', '/', payload={"a": "b"}))
        assert response['request_timeout'] == None

        loop = uvloop.new_event_loop()

        response = loop.run_until_complete(
            self.service.http_dispatch('POST', '/', payload={"a": "b"}, request_timeout=10))
        assert response['request_timeout'] == 10

    def test_http_dispatch_catch_timeout(self, monkeypatch):

        async def _mock_dispatch_fetch(*args, **kwargs):
            await asyncio.sleep(2)
            return {"status": "OK"}

        monkeypatch.setattr(self.service.session._connector, 'connect', _mock_dispatch_fetch)

        loop = asyncio.get_event_loop()

        with pytest.raises(ServiceTimeoutError):
            response = loop.run_until_complete(
                self.service.http_dispatch('GET', '/'))

    @pytest.mark.parametrize("payload,files,headers, expect_content_type", (
            ({"a": "b"}, {}, {}, 'application/json'),
            ({"a": "b"}, {}, {"content-type": "multipart/form-data"}, "multipart/form-data"),
            ({}, {"image": open('insanic.png', 'rb')}, {}, 'multipart/form-data'),
            ({}, {"image": open('insanic.png', 'rb')}, {"content-type": "multipart/form-data"}, 'multipart/form-data'),
            ({}, {"image": open('insanic.png', 'rb')}, {"Content-Type": "multipart/form-data"}, 'multipart/form-data'),
            ({}, {"image": open('insanic.png', 'rb')}, {"content-type": "application/json"}, 'application/json'),
            ({}, {"image": open('insanic.png', 'rb')}, {"Content-type": "application/json"}, 'application/json'),
    ))
    def test_http_dispatch_aiohttp_request_object_headers(self, monkeypatch, payload, files, headers,
                                                          expect_content_type):

        async def _mock_dispatch_fetch(method, request, *args, **kwargs):
            class MockResponse:
                status = 200

                async def json(self, *args, **kwargs):
                    return {"content-type": request.headers.get('Content-Type')}

            lower_headers = {k.lower(): v for k, v in request.headers.items()}

            assert "content-type" in lower_headers.keys()
            assert "accept" in lower_headers.keys()

            assert lower_headers['content-type'].startswith(expect_content_type)
            return MockResponse()

        monkeypatch.setattr(self.service, '_dispatch_fetch', _mock_dispatch_fetch)

        loop = uvloop.new_event_loop()

        response = loop.run_until_complete(
            self.service.http_dispatch('GET', '/', payload=payload, files=files, headers=headers))
        assert expect_content_type in response['content-type']

        loop = uvloop.new_event_loop()

        response = loop.run_until_complete(
            self.service.http_dispatch('POST', '/', payload={"a": "b"}, files=files, headers=headers))
        assert expect_content_type in response['content-type']

    @pytest.mark.parametrize("response_code", [k for k in status.REVERSE_STATUS if k >= 400])
    def test_http_dispatch_raise_for_status(self, response_code):
        """
        raise for different types of response codes

        :param monkeypatch:
        :return:
        """

        loop = uvloop.new_event_loop()

        with aioresponses() as m:
            m.get('http://test:8000/', status=response_code, payload={"hello": "hi"},
                  response_class=InsanicResponse)

            with pytest.raises(APIException):
                try:
                    response = loop.run_until_complete(
                        self.service.http_dispatch('GET', '/',
                                                   payload={}, files={}, headers={},
                                                   propagate_error=True))
                except APIException as e:
                    assert e.status_code == response_code
                    raise e

    # @pytest.mark.parametrize("raise_exception", (
    #     aiohttp.client_exceptions.ClientError,
    #     aiohttp.client_exceptions.ClientResponseError,
    #     aiohttp.client_exceptions.ContentTypeError,
    #     aiohttp.client_exceptions.ClientHttpProxyError,
    #     aiohttp.client_exceptions.ClientConnectionError,
    #     aiohttp.client_exceptions.ClientOSError,
    #     aiohttp.client_exceptions.ClientConnectorError,
    #     aiohttp.client_exceptions.ServerConnectionError,
    #     aiohttp.client_exceptions.ServerDisconnectedError,
    #     aiohttp.client_exceptions.ServerTimeoutError,
    #     aiohttp.client_exceptions.ClientPayloadError,
    #     aiohttp.client_exceptions.InvalidURL
    # ))
    # def test_http_dispatch_raise_for_exception(self, raise_exception):
    #     """
    #
    #
    #     :param monkeypatch:
    #     :return:
    #     """
    #
    #     from aioresponses import aioresponses
    #
    #     loop = uvloop.new_event_loop()
    #
    #     with aioresponses() as m:
    #         exec = raise_exception("{}", [])
    #         m.get('http://test:8000/a', exception=exec, response_class=InsanicResponse)
    #
    #         with pytest.raises(APIException):
    #             try:
    #                 response = loop.run_until_complete(
    #                     self.service.http_dispatch('GET', '/a',
    #                                                payload={}, files={}, headers={},
    #                                                propagate_error=True))
    #             except APIException as e:
    #                 assert e
    #                 raise e


    @pytest.mark.parametrize("extra_headers", ({}, {"content-length": 4}))
    async def test_prepare_headers(self, extra_headers, loop):
        aiotask_context.set(settings.TASK_CONTEXT_REQUEST_USER, {"some": "user"})

        headers = self.service._prepare_headers(extra_headers)

        required_headers = ["date", "authorization"]

        for h in required_headers:
            assert h in headers.keys()

        for h in self.service.remove_headers:
            assert h not in headers.keys()

        assert headers['authorization'].startswith("MSA")
        assert headers['authorization'].endswith(self.service.service_auth_token)
        assert len(headers['authorization'].split(' ')) == 2

    @pytest.mark.parametrize('payload,files,expected_type', (
            ({}, {}, aiohttp.JsonPayload),
            ({"a": "b"}, {}, aiohttp.JsonPayload),
            ({}, {"image": open("insanic.png", "rb")}, aiohttp.FormData),
            ({"a": "b"}, {"image": open("insanic.png", "rb")}, aiohttp.FormData),
            ({}, {"image": File('image/png', open("insanic.png", "rb").read(1024), "insanic.png")},
             aiohttp.FormData),
            ({"a": "b"}, {"image": File('image/png', open("insanic.png", "rb").read(1024), "insanic.png")},
             aiohttp.FormData),
    ))
    async def test_prepare_body(self, payload, files, expected_type):
        headers = self.service._prepare_headers({}, files)

        body = self.service._prepare_body(headers, payload, files)

        assert isinstance(body, expected_type)

        if expected_type == aiohttp.JsonPayload:
            value = ujson.loads(body._value.decode())
            assert value == payload
        elif expected_type == aiohttp.FormData:
            assert body.is_multipart is True

    async def test_prepare_body_error_duplicate_keys_in_payload_and_files(self):
        payload = {"a": "b"}
        files = {"a": open("insanic.png", "rb")}

        headers = self.service._prepare_headers({}, files)

        with pytest.raises(RuntimeError):
            try:
                self.service._prepare_body(headers, payload, files)
            except RuntimeError as e:
                assert e.args[0].startswith("CONFLICT ERROR:")
                raise

    @pytest.mark.parametrize("files", (
            {"i": "string"},
            {"i": b"bytes"},
            {"i": 1},
            {"i": 1.0},
            {"i": open("insanic.png", 'rb').read(1024)}
    ))
    async def test_prepare_body_error_invalid_file_format(self, files):
        payload = {"a": "b"}
        headers = self.service._prepare_headers({}, files)

        with pytest.raises(RuntimeError):
            try:
                self.service._prepare_body(headers, payload, files)
            except RuntimeError as e:
                assert e.args[0].startswith("INVALID FILE")
                raise

    async def test_lower_case_headers(self):
        headers = self.service._prepare_headers({})

        for k in headers:
            assert k.islower()

class TestAioHttpCompatibility:

    def test_client_response_error(self):
        error = aiohttp.client_exceptions.ClientResponseError("a", "b")

        assert hasattr(error, "code")


class TestRequestTaskContext:

    @pytest.fixture()
    def test_user(self):
        test_user_id = 'a6454e643f7f4e8889b7085c466548d4'
        return User(id=uuid.UUID(test_user_id).hex, level=UserLevels.STAFF,
                    is_authenticated=True)

    def test_task_context_service_after_authentication(self, insanic_application, test_user,
                                                       test_service_token_factory):
        import aiotask_context

        token = test_service_token_factory(test_user)

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

        insanic_application.add_route(TokenView.as_view(), '/')
        request, response = insanic_application.test_client.get('/', headers={"Authorization": token})

        assert response.status == 200

    def test_task_context_service_after_authentication_lower_case(self, insanic_application, test_user,
                                                       test_service_token_factory):
        import aiotask_context

        token = test_service_token_factory(test_user)

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

        insanic_application.add_route(TokenView.as_view(), '/')
        request, response = insanic_application.test_client.get('/', headers={"authorization": token})

        assert response.status == 200

    def test_task_context_user_after_authentication(self, insanic_application, test_user, test_user_token_factory):
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

        insanic_application.add_route(TokenView.as_view(), '/')
        request, response = insanic_application.test_client.get('/', headers={"Authorization": token})

        assert response.status == 200

    async def test_task_context_service_multiple_after_authentication(self, insanic_application,
                                                                      test_client,
                                                                      test_service_token_factory):
        import aiotask_context
        import asyncio

        class TokenView(InsanicView):

            async def get(self, request, *args, **kwargs):
                user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                assert user is not None

                request_user = await request.user
                assert user == dict(request_user)

                payload = handlers.jwt_decode_handler(request.auth)
                assert "user" in payload
                assert user == dict(request_user) == payload['user']

                return json({"user": user})

        insanic_application.add_route(TokenView.as_view(), '/')

        client = await test_client(insanic_application)
        #
        # insanic_application.run(host='127.0.0.1', port=unused_port)
        requests = []
        for i in range(10):
            user = User(id=i, level=UserLevels.STAFF,
                        is_authenticated=True)

            token = test_service_token_factory(user)
            requests.append(client.get('/', headers={"Authorization": token}))

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            assert r.status == 200

            resp = await r.json()
            assert resp['user']['id'] == i

    async def test_task_context_user_multiple_after_authentication(self, insanic_application, monkeypatch,
                                                                   test_client,
                                                                   test_user_token_factory):
        import aiotask_context
        import asyncio
        # monkeypatch.setattr(settings, "SWARM_SERVICE_LIST", {"userip": {"host": "manager.msa.swarm", "port": 8016}}, False)

        class TokenView(InsanicView):

            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                request_user = await request.user
                payload = handlers.jwt_decode_handler(request.auth)

                assert context_user is not None

                user_id = payload.pop('user_id')
                assert context_user == dict(request_user) == dict(User(id=user_id, is_authenticated=True, **payload))

                service = await request.service

                assert service is not None
                assert service == AnonymousRequestService

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), '/')

        client = await test_client(insanic_application)
        #
        # insanic_application.run(host='127.0.0.1', port=unused_port)
        users = []
        requests = []
        for i in range(10):
            user, token = test_user_token_factory(level=UserLevels.STAFF, return_with_user=True)
            requests.append(client.get('/', headers={"Authorization": token}))
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp['user']['id'] == users[i].id

    async def test_task_context_user_http_dispatch_injection(self, insanic_application,
                                                             test_client,
                                                             test_user_token_factory):
        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service('userip')

        class TokenView(InsanicView):

            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                request_user = await request.user
                payload = handlers.jwt_decode_handler(request.auth)

                token = UserIPService.service_auth_token
                assert token is not None

                service_payload = jwt.decode(
                    token,
                    settings.SERVICE_TOKEN_KEY,
                    verify=False,
                    algorithms=[settings.JWT_SERVICE_AUTH['JWT_ALGORITHM']]
                )

                assert service_payload['user'] == dict(request_user) == context_user

                inject_headers = UserIPService._prepare_headers({})

                assert "authorization" in inject_headers
                assert token == inject_headers['authorization'].split()[-1]

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), '/')

        client = await test_client(insanic_application)
        #
        # insanic_application.run(host='127.0.0.1', port=unused_port)
        users = []
        requests = []
        for i in range(10):
            user, token = test_user_token_factory(level=UserLevels.STAFF, return_with_user=True)
            requests.append(client.get('/', headers={"Authorization": token}))
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp['user']['id'] == users[i].id

    async def test_task_context_service_http_dispatch_injection(self, insanic_application,
                                                                test_client,
                                                                test_service_token_factory):
        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service('userip')

        class TokenView(InsanicView):

            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                request_user = await request.user
                payload = handlers.jwt_decode_handler(request.auth)

                token = UserIPService.service_auth_token
                assert token is not None

                service_payload = jwt.decode(
                    token,
                    settings.SERVICE_TOKEN_KEY,
                    verify=False,
                    algorithms=[settings.JWT_SERVICE_AUTH['JWT_ALGORITHM']]
                )

                assert service_payload['user'] == dict(request_user) == context_user

                inject_headers = UserIPService._prepare_headers({})

                assert "authorization" in inject_headers
                assert token == inject_headers['authorization'].split()[-1]

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), '/')

        client = await test_client(insanic_application)

        users = []
        requests = []

        for i in range(10):
            user = User(id=i, level=UserLevels.STAFF,
                        is_authenticated=True)

            token = test_service_token_factory(user)
            requests.append(client.get('/', headers={"Authorization": token}))
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp['user']['id'] == users[i].id

    async def test_task_context_service_anonymous_http_dispatch_injection(self, insanic_application,
                                                                          test_client,
                                                                          test_service_token_factory):
        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service('userip')

        class TokenView(InsanicView):
            permission_classes = [AllowAny, ]

            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                request_user = await request.user
                payload = handlers.jwt_decode_handler(request.auth)

                token = UserIPService.service_auth_token
                assert token is not None

                service_payload = jwt.decode(
                    token,
                    settings.SERVICE_TOKEN_KEY,
                    verify=False,
                    algorithms=[settings.JWT_SERVICE_AUTH['JWT_ALGORITHM']]
                )

                assert service_payload['user'] == dict(request_user) == context_user

                inject_headers = UserIPService._prepare_headers({})

                assert "authorization" in inject_headers
                assert token == inject_headers['authorization'].split()[-1]

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), '/')

        client = await test_client(insanic_application)

        users = []
        requests = []

        for i in range(10):
            user = AnonymousUser
            token = test_service_token_factory(user)
            requests.append(client.get('/', headers={"Authorization": token}))
            users.append(user)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp['user']['id'] == users[i].id

    async def test_task_context_anonymous_user_http_dispatch_injection(self, insanic_application,
                                                                       test_client,
                                                                       test_user_token_factory):
        import aiotask_context
        import asyncio
        from insanic.loading import get_service

        UserIPService = get_service('userip')

        class TokenView(InsanicView):
            permission_classes = [AllowAny, ]

            async def get(self, request, *args, **kwargs):
                context_user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER)
                request_user = await request.user
                assert request.auth is None

                token = UserIPService.service_auth_token
                assert token is not None

                service_payload = jwt.decode(
                    token,
                    settings.SERVICE_TOKEN_KEY,
                    verify=False,
                    algorithms=[settings.JWT_SERVICE_AUTH['JWT_ALGORITHM']]
                )

                assert service_payload['user'] == dict(request_user) == context_user

                inject_headers = UserIPService._prepare_headers({})

                assert "authorization" in inject_headers
                assert token == inject_headers['authorization'].split()[-1]

                return json({"user": dict(request_user)})

        insanic_application.add_route(TokenView.as_view(), '/')

        client = await test_client(insanic_application)
        #
        # insanic_application.run(host='127.0.0.1', port=unused_port)
        users = []
        requests = []
        for i in range(10):
            requests.append(client.get('/'))
            users.append(AnonymousUser)

        responses = await asyncio.gather(*requests)

        for i in range(10):
            r = responses[i]
            resp = await r.json()
            assert r.status == 200, resp

            assert resp['user']['id'] == users[i].id
