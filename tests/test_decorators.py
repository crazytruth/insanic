import datetime
import time

import pytest

from insanic.authentication import ServiceJWTAuthentication
from insanic.services import Service

from sanic.response import json as json_response

from insanic import status
from insanic.decorators import deprecate
from insanic.views import InsanicView


class TestDeprecationDecorator:
    @pytest.fixture(autouse=True)
    def reset_last_call(self):
        yield
        deprecate.last_call = {}

    def test_deprecate_method(self, insanic_application, caplog):
        class DeprecatedView(InsanicView):
            authentication_classes = []
            permission_classes = []

            @deprecate(at=datetime.datetime.utcnow(), ttl=1)
            async def get(self, request, *args, **kwargs):
                return json_response({})

        insanic_application.add_route(DeprecatedView.as_view(), "/dep")

        request, response = insanic_application.test_client.get("/dep")

        assert response.status == status.HTTP_200_OK

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        insanic_application.test_client.get("/dep")

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        time.sleep(2)

        insanic_application.test_client.get("/dep")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 2
        )

    def test_deprecate_function(self, insanic_application, caplog):
        @insanic_application.route("/dep")
        @deprecate(at=datetime.datetime.utcnow(), ttl=1)
        async def deprecated_get(request, *args, **kwargs):
            return json_response({})

        request, response = insanic_application.test_client.get("/dep")

        assert response.status == status.HTTP_200_OK

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        insanic_application.test_client.get("/dep")

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        time.sleep(2)

        insanic_application.test_client.get("/dep")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 2
        )

    def test_deprecate_class(self, insanic_application, caplog):
        @deprecate(at=datetime.datetime.utcnow(), ttl=1)
        class DeprecatedView(InsanicView):
            authentication_classes = []
            permission_classes = []

            async def get(self, request, *args, **kwargs):
                return json_response({})

        insanic_application.add_route(DeprecatedView.as_view(), "/dep")

        request, response = insanic_application.test_client.get("/dep")

        assert response.status == status.HTTP_200_OK

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        insanic_application.test_client.get("/dep")

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        time.sleep(2)

        insanic_application.test_client.get("/dep")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 2
        )

    def test_deprecate_add_route(self, insanic_application, caplog):
        class DeprecatedView(InsanicView):
            authentication_classes = []
            permission_classes = []

            async def get(self, request, *args, **kwargs):
                return json_response({})

        deprecation_policy = deprecate(at=datetime.datetime.utcnow(), ttl=1)

        insanic_application.add_route(
            deprecation_policy(DeprecatedView).as_view(), "/dep"
        )

        request, response = insanic_application.test_client.get("/dep")

        assert response.status == status.HTTP_200_OK

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        insanic_application.test_client.get("/dep")

        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        time.sleep(2)

        insanic_application.test_client.get("/dep")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 2
        )

    def test_dynamic_routes(self, insanic_application, caplog):
        @deprecate(at=datetime.datetime.utcnow(), ttl=1)
        class DeprecatedView(InsanicView):
            authentication_classes = []
            permission_classes = []

            async def get(self, request, *args, **kwargs):
                return json_response({})

            async def post(self, request, *args, **kwargs):
                return json_response({})

        insanic_application.add_route(DeprecatedView.as_view(), "/dep/<id:int>")

        request, response = insanic_application.test_client.get("/dep/1")
        assert response.status == status.HTTP_200_OK
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        request, response = insanic_application.test_client.get("/dep/112")
        assert response.status == status.HTTP_200_OK
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 1
        )

        insanic_application.test_client.post("/dep/2")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 2
        )
        insanic_application.test_client.post("/dep/4")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 2
        )

        time.sleep(2)

        insanic_application.test_client.get("/dep/3")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 3
        )
        insanic_application.test_client.post("/dep/6")
        assert (
            len([log for log in caplog.records if log.levelname == "WARNING"])
            == 4
        )

    @pytest.fixture()
    def run_server(self, insanic_application, test_server, loop):
        class DeprecatedMethodView(InsanicView):
            authentication_classes = [
                ServiceJWTAuthentication,
            ]
            permission_classes = []

            @deprecate(at=datetime.datetime.utcnow(), ttl=5)
            async def get(self, request, *args, **kwargs):
                return json_response({})

            async def post(self, request, *args, **kwargs):
                return json_response({})

        @deprecate(at=datetime.datetime.utcnow(), ttl=1)
        class DeprecatedClassView(InsanicView):
            authentication_classes = [
                ServiceJWTAuthentication,
            ]
            permission_classes = []

            async def get(self, request, *args, **kwargs):
                return json_response({})

            async def post(self, request, *args, **kwargs):
                return json_response({})

        insanic_application.add_route(
            DeprecatedMethodView.as_view(), "/method/<id:int>"
        )
        insanic_application.add_route(
            DeprecatedClassView.as_view(), "/class/<id:int>"
        )

        return loop.run_until_complete(
            test_server(insanic_application, host="0.0.0.0")
        )

    async def test_from_different_services(
        self, insanic_application, caplog, run_server
    ):

        service_1 = Service("test")
        service_1.host = "127.0.0.1"
        service_1.port = run_server.port

        await service_1.http_dispatch("GET", "/method/222")
        await service_1.http_dispatch("GET", "/method/222")
        await service_1.http_dispatch("GET", "/method/222")

        warning_count = 0
        for m in caplog.messages:
            if m.startswith("[DEPRECATION WARNING]"):
                assert m.startswith(
                    "[DEPRECATION WARNING] For maintainers of @TEST! GET "
                )
                warning_count += 1

        assert warning_count == 1

        await service_1.http_dispatch("GET", "/class/111")
        await service_1.http_dispatch("GET", "/class/111")
        await service_1.http_dispatch("GET", "/class/111")

        warning_count = 0
        for m in caplog.messages:
            if m.startswith("[DEPRECATION WARNING]"):
                assert m.startswith(
                    "[DEPRECATION WARNING] For maintainers of @TEST! GET "
                )
                warning_count += 1

        assert warning_count == 2

        await service_1.http_dispatch("POST", "/class/111")
        await service_1.http_dispatch("POST", "/class/111")
        await service_1.http_dispatch("POST", "/class/111")

        warning_count = 0
        for m in caplog.messages:
            if m.startswith("[DEPRECATION WARNING]"):
                assert m.startswith(
                    "[DEPRECATION WARNING] For maintainers of @TEST! "
                )
                warning_count += 1

        assert warning_count == 3
