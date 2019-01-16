import asyncio
import aiotask_context
import pytest
import time
import uuid

from insanic import status, permissions, authentication
from insanic.app import Insanic
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.exceptions import RequestTimeoutError, APIException
from insanic.grpc.server import GRPCServer
from insanic.models import User, AnonymousUser
from insanic.responses import json_response
from insanic.services import Service
from insanic.views import InsanicView


class TestGRPCServiceClass:
    mock_response = {'method': "GET"}
    mock_status = 202

    @pytest.fixture
    def insanic_application(selfa):
        app = Insanic('test')

        class NoAuthPermView(InsanicView):
            authentication_classes = []
            permission_classes = []

        class MockView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                return json_response(selfa.mock_response, status=selfa.mock_status)

        class TimeOutView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                await asyncio.sleep(2)
                return json_response(selfa.mock_response, status=selfa.mock_status)

        class EchoView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                return json_response({"payload": request.json, "files": {k: len(v) for k, v in request.files.items()}})

        class ReturnResponseCodeView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                sc = request.data.get('status_code', 100)
                raise APIException("Raise error", error_code=GlobalErrorCodes.error_unspecified, status_code=sc)

        class DynamicRouteView(NoAuthPermView):
            async def get(self, request, id, *args, **kwargs):
                return json_response({"id": id})

        class TaskContextView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                # import aiotask_context
                user = await request.user
                correlation_id = aiotask_context.get(settings.TASK_CONTEXT_CORRELATION_ID)
                return json_response(
                    {"context_user": dict(user), "correlation_id": correlation_id, "request_id": request.id})

        class AllMethodsView(NoAuthPermView):
            async def get(self, request, *args, **kwargs):
                return json_response({"method": "get"})

            async def put(self, request, *args, **kwargs):
                return json_response({"method": "put"})

            async def post(self, request, *args, **kwargs):
                return json_response({"method": "post"})

            async def patch(self, request, *args, **kwargs):
                return json_response({"method": "patch"})

            async def delete(self, request, *args, **kwargs):
                return json_response({"method": "delete"})

        class AdminOnlyView(InsanicView):
            authentication_classes = [authentication.JSONWebTokenAuthentication, ]
            permission_classes = [permissions.IsAdminUser, ]

            async def get(self, request, *args, **kwargs):
                return json_response({"admin": "only"})

        app.add_route(MockView.as_view(), '/')
        app.add_route(TimeOutView.as_view(), '/timeout')
        app.add_route(EchoView.as_view(), '/echo')
        app.add_route(ReturnResponseCodeView.as_view(), '/raise')
        app.add_route(DynamicRouteView.as_view(), '/dynamic/<id>')
        app.add_route(TaskContextView.as_view(), '/context')
        app.add_route(AllMethodsView.as_view(), '/methods')
        app.add_route(AdminOnlyView.as_view(), '/admin')

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
        monkeypatch.setattr(Service, 'host', '127.0.0.1')
        monkeypatch.setattr(Service, 'port', insanic_server.port)
        test_service = Service('test')
        test_service._grpc_client_package = None

        monkeypatch.setattr(test_service, '_status', 1)
        monkeypatch.setattr(test_service, '_status_check', time.monotonic())

        yield test_service


    async def test_dispatch(self, service_instance):
        response = await service_instance.grpc_dispatch('GET', '/')

        assert response == self.mock_response

        with pytest.raises(ValueError):
            await service_instance.grpc_dispatch('GETS', '/')

        response, status_code = await service_instance.grpc_dispatch('GET', '/', include_status_code=True)

        assert response == self.mock_response
        assert status_code == self.mock_status

    async def test_dispatch_request_timeout(self, service_instance):

        response = await service_instance.grpc_dispatch('GET', '/timeout', request_timeout=3)
        assert response == self.mock_response

        with pytest.raises(RequestTimeoutError):
            response, status_code = await service_instance.grpc_dispatch('GET', '/timeout',
                                                                         request_timeout=1,
                                                                         include_status_code=True)

    @pytest.mark.parametrize("payload,files,headers", (
            ({"a": "b"}, {}, {}),
            ({"a": "b"}, {}, {"content-type": "multipart/form-data"}),
            ({}, {"image": open('insanic.png', 'rb')}, {}),
            ({}, {"image": [open('insanic.png', 'rb')]}, {}),
            ({}, {"image": [open('insanic.png', 'rb'), open('insanic.png', 'rb')]}, {}),
            ({}, {"image": open('insanic.png', 'rb')}, {"content-type": "multipart/form-data"}),
            ({}, {"image": open('insanic.png', 'rb')}, {"Content-Type": "multipart/form-data"}),
            ({}, {"image": open('insanic.png', 'rb')}, {"content-type": "application/json"}),
            ({}, {"image": open('insanic.png', 'rb')}, {"Content-type": "application/json"}),
    ))
    async def test_dispatch_request_object_headers(self, service_instance, payload, files, headers):

        response = await service_instance.grpc_dispatch('GET', '/echo', payload=payload, files=files, headers=headers)

        assert response['payload'] == payload
        assert response['files'] == {k: len(v) if isinstance(v, list) else 1 for k, v in files.items()}

    @pytest.mark.parametrize("response_code", [k for k in status.REVERSE_STATUS if k >= 400])
    async def test_dispatch_raise_for_status(self, service_instance, response_code):
        """
        raise for different types of response codes

        :param monkeypatch:
        :return:
        """
        with pytest.raises(APIException):
            try:
                response = await service_instance.grpc_dispatch('GET', '/raise',
                                                                payload={"status_code": response_code},
                                                                propagate_error=True)
            except APIException as e:
                assert e.status_code == response_code
                raise e

    @pytest.mark.parametrize("response_code", [k for k in status.REVERSE_STATUS if k >= 400])
    async def test_dispatch_return_error(self, service_instance, response_code):
        """
        return error for different types of response codes

        :param monkeypatch:
        :return:
        """
        response, status = await service_instance.grpc_dispatch('GET', '/raise',
                                                                payload={"status_code": response_code},
                                                                propagate_error=False,
                                                                include_status_code=True)

        assert status == response_code

    async def test_route_not_found(self, service_instance):
        response, status_code = await service_instance.grpc_dispatch('GET', '/doesntexist', include_status_code=True)
        assert status_code == 404

    async def test_dynamic_route(self, service_instance):
        random_id = uuid.uuid4()

        response, status_code = await service_instance.grpc_dispatch('GET', f'/dynamic/{random_id}',
                                                                     include_status_code=True)

        assert response['id'] == str(random_id)
        assert status_code == status.HTTP_200_OK

    @pytest.mark.parametrize("method", ("GET", "PUT", "PATCH", "POST", "DELETE"))
    async def test_methods(self, service_instance, method):
        response, status_code = await service_instance.grpc_dispatch(method.upper(), f'/methods',
                                                                     include_status_code=True)
        assert response['method'].upper() == method.upper()

    async def test_invalid_method(self, service_instance):
        with pytest.raises(ValueError):
            await service_instance.grpc_dispatch("INSANIC", f'/method',
                                                 include_status_code=True)

    async def test_no_permission_check(self, service_instance):
        response, status_code = await service_instance.grpc_dispatch("GET", f'/admin',
                                                                     include_status_code=True)
        assert status_code == status.HTTP_200_OK
        assert response['admin'] == "only"

    async def test_request_context_user(self, service_instance):
        context_user = dict(User(id=uuid.uuid4().hex, level=UserLevels.STAFF, is_authenticated=True))
        aiotask_context.set(settings.TASK_CONTEXT_REQUEST_USER, context_user)
        response, status_code = await service_instance.grpc_dispatch('GET', '/context', include_status_code=True)
        assert response['context_user'] == context_user

    async def test_request_context_user_anonymous(self, service_instance):
        aiotask_context.set(settings.TASK_CONTEXT_REQUEST_USER, dict(AnonymousUser))
        response, status_code = await service_instance.grpc_dispatch('GET', '/context', include_status_code=True)
        assert response['context_user'] == dict(AnonymousUser)

    async def test_request_context_request_id(self, service_instance):
        request_id = uuid.uuid4().hex
        aiotask_context.set(settings.TASK_CONTEXT_CORRELATION_ID, request_id)
        response, status_code = await service_instance.grpc_dispatch('GET', '/context', include_status_code=True)
        assert response['correlation_id'] == request_id == response['request_id']

    def test_grpc_packages_searched_only_once(self, service_instance, monkeypatch):
        # already initialized at this point because of service_instance init call

        def mock_search(cls, *args, **kwargs):
            cls._grpc_client_packages = "Shouldn't Be Here"

        monkeypatch.setattr(Service, '_search_grpc_packages', mock_search)

        test_service = Service('something_else')
        service_instance.search_grpc_packages()
        assert test_service._grpc_client_packages is not None
        assert test_service._grpc_client_packages != "Shouldn't Be Here"
        assert service_instance._grpc_client_packages is test_service._grpc_client_packages


class TestClientStubs:

    @pytest.fixture
    def insanic_application(self, monkeypatch):

        from grpc_test_monkey.monkey_grpc import ApeServiceBase
        from grpc_test_monkey.monkey_pb2 import ApeMonkeyResponse

        class TestApeService(ApeServiceBase):
            async def ApeMonkey(self, stream):
                request = await stream.recv_message()
                response = ApeMonkeyResponse(id=int(request.id))
                await stream.send_message(response)

        monkeypatch.setattr(settings, 'GRPC_SERVER', [TestApeService, ])
        app = Insanic('test')

        yield app

    @pytest.fixture
    def insanic_server(self, loop, insanic_application, test_server, monkeypatch):
        monkeypatch.setattr(settings, 'GRPC_PORT_DELTA', 1)

        return loop.run_until_complete(test_server(insanic_application))

    async def test_grpc_context_manager(self, monkeypatch, insanic_server):
        monkeypatch.setattr(Service, 'host', '127.0.0.1')
        monkeypatch.setattr(Service, 'port', insanic_server.port)
        service_instance = Service('test')

        some_id = "192839"

        async with service_instance.grpc(namespace='monkey', service_method='ApeMonkey') as stub:
            try:
                r = await stub(id=some_id)
            except Exception as e:
                raise e

            assert r.id == int(some_id)
