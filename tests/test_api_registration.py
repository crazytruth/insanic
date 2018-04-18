import aiohttp
import pytest
import requests
import uuid
from ujson import loads as jsonloads

from yarl import URL

from sanic.response import json
from insanic import Insanic
from insanic.conf import settings
from insanic.scopes import public_facing
from insanic.views import InsanicView

from .conftest_constants import ROUTES


class TestBaseGateway:

    @pytest.fixture(autouse=True)
    def base_gateway(self, monkeypatch):
        from insanic.registration import BaseGateway
        monkeypatch.setattr(settings, "GATEWAY_REGISTRATION_ENABLED", True)

        self.gateway = BaseGateway()

    @pytest.mark.parametrize("method, params", (
            ("register_service", {"app": None, "session": None}),
            ("register_routes", {"app": None, "session": None}),
            ("deregister_service", {"session": None}),
            ("deregister_routes", {"session": None}),
            ("register", {"app": None}),
            ("deregister", {})))
    async def test_not_implemented_errors(self, method, params):
        with pytest.raises(NotImplementedError):
            async with self.gateway as gw:
                test_method = getattr(gw, method)
                await test_method(**params)

    async def test_context_manager(self):
        assert self.gateway.session is None

        async with self.gateway as gw:
            assert gw.session is not None
            assert self.gateway.session is not None
            assert isinstance(gw.session, aiohttp.ClientSession)

        assert self.gateway.session.closed is True


class TestKongGateway:

    @pytest.fixture(autouse=True)
    def kong_gateway(self, monkeypatch):
        monkeypatch.setattr(settings, "GATEWAY_REGISTRATION_ENABLED", True)
        monkeypatch.setattr(settings, "KONG_HOST", 'kong.msa.local')
        monkeypatch.setattr(settings, "KONG_PORT", 18001)
        from insanic.registration import KongGateway
        self.gateway = KongGateway()

    @pytest.fixture(autouse=True)
    def kong_server_clean_up(self):

        yield

        kong_base_url = self.gateway.kong_base_url
        resp = requests.get(kong_base_url.with_path('/services'))
        body = jsonloads(resp.text)
        service_ids = [r['id'] for r in body.get('data', []) if "test" == r['name'].split('.')[1]]

        for sid in service_ids:
            resp = requests.get(kong_base_url.with_path(f'/services/{sid}/routes'))
            body = jsonloads(resp.text)

            for r in body.get('data', []):
                requests.delete(kong_base_url.with_path(f'/routes/{r["id"]}'))

        for r in service_ids:
            requests.delete(kong_base_url.with_path(f'/services/{r}'))

    @pytest.fixture()
    def insanic_application(self, monkeypatch, insanic_application, unused_port):
        monkeypatch.setattr(insanic_application, "_port", unused_port, raising=False)
        return insanic_application

    def test_init_assert(self):

        assert isinstance(self.gateway.kong_base_url, URL)
        assert URL(self.gateway.kong_base_url)
        assert self.gateway._service_spec is None
        assert self.gateway.machine_id is not None
        assert isinstance(self.gateway.machine_id, str)

    def test_kong_service_name(self):

        ksn = self.gateway.kong_service_name

        sn, e, mi = ksn.split('.')

        assert sn == self.gateway.service_name.lower()
        assert e == self.gateway.environment.lower()
        assert mi == self.gateway.machine_id.lower()

    def test_service_spec(self, monkeypatch):
        monkeypatch.setattr(settings._wrapped, "SERVICE_LIST", {}, raising=False)

        sl = self.gateway.service_spec

        assert self.gateway._service_spec == sl

        service_spec = {"a": "b"}
        monkeypatch.setattr(settings._wrapped, "SERVICE_LIST", {"insanic": service_spec}, raising=False)
        self.gateway._service_spec = None

        sl = self.gateway.service_spec
        assert self.gateway._service_spec == service_spec

    async def test_register_service_idempotence(self, monkeypatch, insanic_application):

        async with self.gateway as gw:
            await gw.register_service(insanic_application)
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            sid = self.gateway.service_id

            await gw.register_service(insanic_application)
            assert sid == gw.service_id

            await gw.register_service(insanic_application)
            assert sid == gw.service_id

    async def test_register_routes_but_no_routes(self, monkeypatch, insanic_application):
        '''
        no routes added to insanic application so will not fire to kong

        :param monkeypatch:
        :param insanic_application:
        :param unused_port:
        :param kong_get_service_detail_200:
        :return:
        '''
        async with self.gateway as gw:
            await gw.register_service(insanic_application)
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            # this will trigger deregister service because there aren't any public routes
            await gw.register_routes(insanic_application)

            assert self.gateway.service_id is None

    @pytest.mark.parametrize("routes_prefix", [r.replace("public", "prefix") for r in ROUTES])
    @pytest.mark.parametrize("routes_suffix", [r.replace("public", "suffix") for r in ROUTES])
    async def test_register_routes_with_public_facing(self, monkeypatch, insanic_application,
                                                      routes_prefix, routes_suffix):

        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", ['test.mmt.local'], raising=False)

        class MockView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        route = f"{routes_prefix}{routes_suffix}".replace("//", "/")

        insanic_application.add_route(MockView.as_view(), route)

        from insanic.registration import normalize_url_for_kong
        async with self.gateway as gw:
            await gw.register_service(insanic_application)
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            await gw.register_routes(insanic_application)

            assert len(gw.routes) == 1
            assert [normalize_url_for_kong(r) for r in insanic_application.public_routes().keys()] in [r['paths'] for r
                                                                                                       in
                                                                                                       gw.routes.values()]
            assert ["GET"] in [r['methods'] for r in gw.routes.values()]

            # deregistration flow
            await gw.deregister_routes()
            assert len(gw.routes) == 0
            await gw.deregister_service()
            assert gw.service_id is None

    async def test_register_routes_without_register_service(self, monkeypatch, insanic_application):

        with pytest.raises(RuntimeError):
            async with self.gateway as gw:
                await gw.register_routes(insanic_application)

    async def test_deregister_routes_but_with_route_leftover_from_last_run(self, monkeypatch, insanic_application):

        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", ['test.mmt.local'], raising=False)

        class MockView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        insanic_application.add_route(MockView.as_view(), "/hello")

        async with self.gateway as gw:
            await gw.register_service(insanic_application)
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            await gw.register_routes(insanic_application)

            gw.routes = {}

            await gw.deregister_routes()

            assert gw.routes == {}

    async def test_deregister_routes_with_no_routes(self, insanic_application, caplog):
        async with self.gateway as gw:
            await gw.register_service(insanic_application)
            await gw.deregister_routes()

            assert caplog.records[-1].message.endswith("No routes to deregister.")

    async def test_deregister_service_without_register(self, caplog):
        async with self.gateway as gw:
            await gw.deregister_service()

            assert caplog.records[-1].message.endswith("has already been deregistered.")

    async def test_full_register_deregister(self, monkeypatch, insanic_application):

        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", ['test.mmt.local'], raising=False)

        class MockView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        insanic_application.add_route(MockView.as_view(), '/hello')

        async with self.gateway as gw:
            await gw.register(insanic_application)
            await gw.deregister()

            # assert clean up
            kong_base_url = self.gateway.kong_base_url
            resp = requests.get(kong_base_url.with_path('/services'))
            body = jsonloads(resp.text)
            service_ids = []
            for r in body.get('data', []):
                app, env, mid = r['name'].split('.')
                if env == "test" and app == "insanic":
                    service_ids.append(r['id'])

            assert len(service_ids) == 0

    async def test_http_session_manager(self, insanic_application):
        assert self.gateway.session is None
        await self.gateway.register(insanic_application)
        assert self.gateway.session is None
