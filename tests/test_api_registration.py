import aiohttp
import pytest
import requests
import uuid
from ujson import loads as jsonloads

from yarl import URL

from sanic.response import json

from choices import UserLevels
from insanic import Insanic
from insanic.authentication import JSONWebTokenAuthentication
from insanic.conf import settings
from insanic.permissions import AllowAny, IsAuthenticated
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
        monkeypatch.setattr(settings, "KONG_HOST", 'kong.msa.swarm')
        monkeypatch.setattr(settings, "KONG_ADMIN_PORT", 18001)
        monkeypatch.setattr(settings, "KONG_PLUGIN", {"JSONWebTokenAuthentication": "jwt"})
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

    @pytest.fixture(scope="function")
    def kong_jwt_test_fixture(self):
        temp_consumer_id = uuid.uuid1().hex

        yield temp_consumer_id

        kong_base_url = self.gateway.kong_base_url

        # Delete jwts
        resp = requests.get(kong_base_url.with_path(f'/consumers/{temp_consumer_id}/jwt/'))
        body = jsonloads(resp.text)
        for r in body.get('data', []):
            jwt_id = r['id']
            requests.delete(kong_base_url.with_path(f'/consumers/{temp_consumer_id}/jwt/{jwt_id}/'))

        # Delete consumer
        requests.delete(kong_base_url.with_path(f'/consumers/{temp_consumer_id}/'))

    @pytest.fixture()
    def insanic_application(self, monkeypatch, insanic_application, unused_port):
        monkeypatch.setattr(insanic_application, "_port", unused_port, raising=False)
        return insanic_application

    def test_init_assert(self):

        assert isinstance(self.gateway.kong_base_url, URL)
        assert URL(self.gateway.kong_base_url)
        assert self.gateway.machine_id is not None
        assert isinstance(self.gateway.machine_id, str)

    def test_kong_service_name(self):
        ksn = self.gateway.kong_service_name

        sn, e, mi = ksn.split('.')

        assert sn == self.gateway.service_name.lower()
        assert e == self.gateway.environment.lower()
        assert mi == self.gateway.machine_id.lower()

    # def test_service_spec(self, monkeypatch):
    #     monkeypatch.setattr(settings._wrapped, "SERVICE_LIST", {}, raising=False)
    #
    #     sl = self.gateway.service_spec
    #
    #     assert self.gateway._service_spec == sl
    #
    #     service_spec = {"a": "b"}
    #     monkeypatch.setattr(settings._wrapped, "SERVICE_LIST", {"insanic": service_spec}, raising=False)
    #     self.gateway._service_spec = None
    #
    #     sl = self.gateway.service_spec
    #     assert self.gateway._service_spec == service_spec

    def test_routes_with_jwt_auth_and_allow_any(self, monkeypatch, insanic_application, test_user_token_factory):
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", [], raising=False)

        class MockView(InsanicView):
            authentication_classes = [JSONWebTokenAuthentication]
            permission_classes = [AllowAny]

            @public_facing
            async def get(self, request, *args, **kwargs):
                return json({'anonymous_header': request.headers.get('x-anonymous-consumer') == 'true',
                             'user_type': (await request.user).__class__.__name__}, status=202)

        route = "/test/"

        insanic_application.add_route(MockView.as_view(), route)

        # Test without token
        request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}')

        assert response.status == 202
        assert response.json == {'anonymous_header': True, 'user_type': '_AnonymousUser'}

        # Test with token
        token = test_user_token_factory(email='test@tester.cc', level=UserLevels.ACTIVE)
        request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}',
                                                                headers={'Authorization': f"{token}"})

        assert response.status == 202
        assert response.json == {'anonymous_header': False, 'user_type': 'User'}

        # Test with banned user
        token = test_user_token_factory(email='test_banned@tester.cc', level=UserLevels.BANNED)
        request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}',
                                                                headers={'Authorization': f"{token}"})

        assert response.status == 401

    def test_routes_with_jwt_auth_and_is_authenticated(self, monkeypatch, insanic_application, test_user_token_factory):
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", [], raising=False)

        class MockView(InsanicView):
            authentication_classes = [JSONWebTokenAuthentication]
            permission_classes = [IsAuthenticated]

            @public_facing
            async def get(self, request, *args, **kwargs):
                return json({'test': 'success'}, status=202)

        route = "/test/"

        insanic_application.add_route(MockView.as_view(), route)

        # Test without token
        request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}')

        assert response.status == 401

        # Test with token
        token = test_user_token_factory(email='test@tester.cc', level=UserLevels.ACTIVE)
        request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}',
                                                                headers={'Authorization': f"{token}"})

        assert response.status == 202
        assert response.json == {'test': 'success'}

        # Test with banned user
        token = test_user_token_factory(email='test_banned@tester.cc', level=UserLevels.BANNED)
        request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}',
                                                                headers={'Authorization': f"{token}"})

        assert response.status == 401

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

    @pytest.mark.parametrize("routes_prefix", [r.replace("public", "prefix") for r in ROUTES])
    @pytest.mark.parametrize("routes_suffix", [r.replace("public", "suffix") for r in ROUTES])
    async def test_routes_with_jwt_plugin_enabled(self, monkeypatch, insanic_application, kong_jwt_test_fixture,
                                                  routes_prefix, routes_suffix):
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", ['test.mmt.local'], raising=False)

        class MockView(InsanicView):
            authentication_classes = [JSONWebTokenAuthentication]

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        route = f"{routes_prefix}{routes_suffix}".replace("//", "/")

        insanic_application.add_route(MockView.as_view(), route)

        async with self.gateway as gw:
            await gw.register_service(insanic_application)
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            await gw.register_routes(insanic_application)

            session = gw.session

            # Create a Kong consumer
            req_payload = {'username': kong_jwt_test_fixture}
            async with session.post(
                    f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/consumers/", json=req_payload
            ) as resp:
                result = await resp.json()

                assert "username" in result
                assert result['username'] == req_payload['username']

            consumer_id = result['id']

            # Create JWT credentials for user
            async with session.post(
                    f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/consumers/{req_payload['username']}/jwt/",
                    json={}
            ) as resp:
                result = await resp.json()

                assert result['consumer_id'] == consumer_id
                assert all(key in result for key in ('created_at', 'id', 'algorithm', 'key', 'secret', 'consumer_id'))

            await gw.deregister_routes()
            await gw.deregister_service()

    @pytest.mark.parametrize("routes_prefix", [r.replace("public", "prefix") for r in ROUTES])
    @pytest.mark.parametrize("routes_suffix", [r.replace("public", "suffix") for r in ROUTES])
    async def test_deregister_routes_with_disabling_plugins(self, monkeypatch, insanic_application,
                                                            routes_prefix, routes_suffix):
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", ['test.msa.local'], raising=False)

        class MockView(InsanicView):
            authentication_classes = [JSONWebTokenAuthentication]
            permission_classes = []

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        route = f"{routes_prefix}{routes_suffix}".replace("//", "/")

        insanic_application.add_route(MockView.as_view(), route)

        async with self.gateway as gw:
            await gw.register_service(insanic_application)
            await gw.register_routes(insanic_application)

            session = gw.session

            # Get routes id - Only one route should be available.
            route_id = list(gw.routes.keys())[0]

            async with session.get(
                    f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/plugins?route_id={route_id}"
            ) as resp:
                result = await resp.json()

                # Test if plugins were successfully enabled for this route
                assert resp.status == 200
                assert 'data' in result
                assert any(d['name'] == 'jwt' for d in result['data'])

            await gw.deregister_routes()
            await gw.deregister_service()

            async with session.get(
                    f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/plugins?route_id={route_id}"
            ) as resp:
                result = await resp.json()

                # Test if plugins were successfully disabled for this route
                assert resp.status == 200
                assert 'total' in result and result['total'] == 0
                assert 'data' in result and not result['data']

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
