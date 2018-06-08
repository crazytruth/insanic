import aiohttp
import pytest
import requests
import uuid
from ujson import loads as jsonloads

from yarl import URL

from sanic import testing
from sanic.response import json

from insanic.authentication import JSONWebTokenAuthentication
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.permissions import AllowAny, IsAuthenticated
from insanic.scopes import public_facing
from insanic.views import InsanicView
from insanic.registration import gateway

from .conftest_constants import ROUTES


class TestBaseGateway:

    @pytest.fixture(autouse=True)
    def base_gateway(self, monkeypatch):
        from insanic.registration import BaseGateway
        monkeypatch.setattr(settings, "GATEWAY_REGISTRATION_ENABLED", True)

        self.gateway = BaseGateway()

    @pytest.mark.parametrize("method, params", (
            ("_register", {"session": None}),
            ("_deregister", {"session": None}),
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


gw = None

class TestKongGateway:

    @pytest.fixture(autouse=True)
    def kong_gateway(self, monkeypatch, session_id):
        monkeypatch.setattr(settings, "GATEWAY_REGISTRATION_ENABLED", True)
        monkeypatch.setattr(settings, "KONG_HOST", 'kong.msa.swarm')
        monkeypatch.setattr(settings, "KONG_ADMIN_PORT", 18001)
        monkeypatch.setattr(settings, "KONG_PLUGIN", {"JSONWebTokenAuthentication": "jwt"})
        from insanic.registration import KongGateway

        monkeypatch.setattr(KongGateway, "service_version", session_id, raising=False)
        self.gateway = KongGateway()
        global gw
        gw = self.gateway
        yield

    @pytest.fixture(autouse=True, scope="module")
    def kong_clean_up(self):

        yield
        global gw

        kong_base_url = gw.kong_base_url
        resp = requests.get(kong_base_url.with_path('/services'))
        body = jsonloads(resp.text)
        service_ids = [r['id'] for r in body.get('data', []) if "test" in r['name']]

        for sid in service_ids:
            # delete associated routes
            resp = requests.get(kong_base_url.with_path(f'/services/{sid}/routes'))
            body = jsonloads(resp.text)

            for r in body.get('data', []):
                requests.delete(kong_base_url.with_path(f'/routes/{r["id"]}'))

        # delete associated upstream
        resp = requests.get(kong_base_url.with_path('/upstreams'))
        body = jsonloads(resp.text)
        upstream_ids = [r['id'] for r in body.get('data', []) if "test" in r['name']]

        for uid in upstream_ids:
            resp = requests.get(kong_base_url.with_path(f'/upstreams/{uid}/targets/all/'))

            body = jsonloads(resp.text)
            for r in body.get('data', []):
                requests.delete(kong_base_url.with_path(f'/upstreams/{uid}/targets/{r["id"]}'))

            requests.delete(kong_base_url.with_path(f'/upstreams/{uid}/'))

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


    def test_kong_service_name(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_VERSION", "0.0.0", raising=False)

        ksn = self.gateway.kong_service_name

        sn, e, mi = ksn.split('-')

        assert sn == self.gateway.environment.lower()
        assert e == self.gateway.service_name.lower()
        assert mi == self.gateway.service_version.lower()

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

    def test_routes_with_jwt_auth_and_allow_any(self, monkeypatch, insanic_application, test_user_token_factory,
                                                function_session_id):
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", [], raising=False)
        monkeypatch.setattr(gateway, "_enabled", True)
        monkeypatch.setattr(gateway, "kong_base_url", URL(f"http://{settings.KONG_HOST}:18001"))
        monkeypatch.setattr(testing, "HOST", "0.0.0.0")

        class MockView(InsanicView):
            authentication_classes = [JSONWebTokenAuthentication]
            permission_classes = [AllowAny]

            @public_facing
            async def get(self, request, *args, **kwargs):
                return json({'anonymous_header': request.headers.get('x-anonymous-consumer') == 'true',
                             'user_type': (await request.user).__class__.__name__}, status=202)

        route = f"/test/{function_session_id}/"

        insanic_application.add_route(MockView.as_view(), route)

        # Test without token
        client = insanic_application.test_client
        request, response = client.get(f'http://{settings.KONG_HOST}:18000{route}')

        assert response.status == 202
        assert response.json == {'anonymous_header': True, 'user_type': '_AnonymousUser'}

        # Test with token
        token = test_user_token_factory(email='test@tester.cc', level=UserLevels.ACTIVE)
        request, response = client.get(f'http://{settings.KONG_HOST}:18000{route}',
                                                                headers={'Authorization': f"{token}"})

        assert response.status == 202
        assert response.json == {'anonymous_header': False, 'user_type': 'User'}

        # Test with banned user
        token = test_user_token_factory(email='test_banned@tester.cc', level=UserLevels.BANNED)
        request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}',
                                                                headers={'Authorization': f"{token}"})

        assert response.status == 401

    def test_routes_with_jwt_auth_and_is_authenticated(self, monkeypatch, insanic_application, test_user_token_factory,
                                                       function_session_id):

        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", [], raising=False)
        monkeypatch.setattr(gateway, "_enabled", True)
        monkeypatch.setattr(gateway, "kong_base_url", URL(f"http://{settings.KONG_HOST}:18001"))
        monkeypatch.setattr(testing, "HOST", "0.0.0.0")

        class MockView(InsanicView):
            authentication_classes = [JSONWebTokenAuthentication]
            permission_classes = [IsAuthenticated]

            @public_facing
            async def get(self, request, *args, **kwargs):
                return json({'test': 'success'}, status=202)

        route = f"/test/{function_session_id}/"

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

    async def test_register_service_idempotence(self, monkeypatch, insanic_application, session_id):

        monkeypatch.setattr(self.gateway, "service_name", session_id[:10])

        async with self.gateway as gw:
            gw.app = insanic_application
            await gw.register_service()
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            sid = self.gateway.service_id

            await gw.register_service()
            assert sid == gw.service_id

            await gw.register_service()
            assert sid == gw.service_id

            # clean up
            await gw.deregister_service()

    async def test_upstream_object(self, monkeypatch, insanic_application, session_id):
        monkeypatch.setattr(self.gateway, "service_name", session_id[:10])

        upstream_object = self.gateway.upstream_object

        assert upstream_object['name'] == self.gateway.kong_service_name
        assert upstream_object['healthchecks']['active']['http_path'].endswith('/health/')
        assert upstream_object['healthchecks']['active']['healthy']['http_statuses'] == [200]

    async def test_register_service_upstream_target(self, monkeypatch, insanic_application, session_id):

        monkeypatch.setattr(self.gateway, "service_name", session_id[:10])

        async with self.gateway as gw:
            gw.app = insanic_application
            await gw.register_service()
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None

            # test register upstream
            await gw.register_upstream()
            assert hasattr(self.gateway, "upstream_id")
            assert self.gateway.upstream_id is not None
            upstream_id = self.gateway.upstream_id

            # test register target
            await gw.register_target()
            assert hasattr(self.gateway, 'target_id')
            assert self.gateway.target_id is not None
            target_id = self.gateway.target_id

            # test register target idempotence
            await gw.register_target()
            assert target_id == self.gateway.target_id

            # test upstream idempotence
            await gw.register_upstream()
            assert upstream_id == gw.upstream_id == self.gateway.upstream_id

            # clean up
            await gw.deregister_target()
            await gw.deregister_upstream()
            await gw.deregister_service()


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
            gw.app = insanic_application
            await gw.register_service()
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            # this will trigger deregister service because there aren't any public routes
            await gw.register_routes()

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

        from insanic.registration.kong import normalize_url_for_kong
        async with self.gateway as gw:
            gw.app = insanic_application
            await gw.register_service()
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            await gw.register_routes()

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
            gw.app = insanic_application
            await gw.register_service()
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            await gw.register_routes()

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

        self.gateway.app = insanic_application

        async with self.gateway as gw:
            await gw.register_service()
            await gw.register_routes()

            session = gw.session

            # Get routes id - Only one route should be available.
            try:
                route_id = list(gw.routes.keys())[0]
            except IndexError:
                pass

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
                gw.app = insanic_application
                await gw.register_routes()

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
            gw.app = insanic_application
            await gw.register_service()
            assert hasattr(self.gateway, "service_id")
            assert self.gateway.service_id is not None
            await gw.register_routes()

            gw.routes = {}

            await gw.deregister_routes()

            assert gw.routes == {}

    async def test_deregister_routes_with_no_routes(self, insanic_application, caplog):
        async with self.gateway as gw:
            gw.app = insanic_application
            await gw.register_service()
            await gw.deregister_routes()

            assert caplog.records[-1].message.endswith("This instance did not register any routes.")

    async def test_deregister_service_without_register(self, caplog):
        async with self.gateway as gw:
            await gw.deregister_service()

            assert caplog.records[-1].message.endswith("This instance did not register a service.")

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
            next_url = kong_base_url.with_path('/services')
            while next_url:
                resp = requests.get(next_url)
                body = jsonloads(resp.text)
                service_ids = []
                for r in body.get('data', []):
                    # service_piece = r['name'].split('.')
                    # app, env, mid = r['name'].split('.')
                    if "test" in r['name'] and "insanic" in r['name']:
                        service_ids.append(r['id'])

                if "next" in body and body['next']:
                    next_url = kong_base_url.with_path(body['next'])
                else:
                    break

            # is 1 because we no longer deregister service
            assert len(service_ids) == 1

    async def test_http_session_manager(self, insanic_application):
        assert self.gateway.session is None
        await self.gateway.register(insanic_application)
        assert self.gateway.session is None
