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
            ("_register", {}),
            ("_deregister", {}),
            ("register", {"app": None}),
            ("deregister", {})))
    async def test_not_implemented_errors(self, method, params):
        with pytest.raises(NotImplementedError):
            test_method = getattr(self.gateway, method)
            test_method(**params)

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

        yield

        # @pytest.fixture(autouse=True, scope="module")
        # def kong_clean_up(self):
        #
        #     yield
        #     global gw

        kong_base_url = self.gateway.kong_base_url.with_host('kong.msa.swarm')
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

    def test_kong_service_host(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_VERSION", "0.0.0", raising=False)

        ksh = self.gateway.kong_service_host

        sn, e, mi = ksh.split('-')

        assert sn == self.gateway.environment.lower()
        assert e == self.gateway.service_name.lower()
        assert mi == self.gateway.service_version.lower()

    def test_kong_service_name(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_VERSION", "0.0.0", raising=False)

        ksn = self.gateway.kong_service_name

        sn, e = ksn.split('-')

        assert sn == self.gateway.environment.lower()
        assert e == self.gateway.service_name.lower()


    @staticmethod
    async def _force_target_healthy(app, loop):
        gateway.force_target_healthy()

    @pytest.fixture
    def sanic_test_server(self, loop, insanic_application, test_server, monkeypatch, test_route):
        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", [], raising=False)
        monkeypatch.setattr(gateway, "_enabled", True)
        monkeypatch.setattr(gateway, "_kong_base_url", URL(f"http://{settings.KONG_HOST}:18001"))
        monkeypatch.setattr(testing, "HOST", "0.0.0.0")

        class MockView(InsanicView):
            authentication_classes = [JSONWebTokenAuthentication]
            permission_classes = [AllowAny]

            @public_facing
            async def get(self, request, *args, **kwargs):
                return json({'anonymous_header': request.headers.get('x-anonymous-consumer') == 'true',
                             'user_type': (await request.user).__class__.__name__}, status=202)

        # insanic_application.listeners["after_server_start"].append(self._force_target_healthy)
        insanic_application.add_route(MockView.as_view(), test_route)

        return loop.run_until_complete(test_server(insanic_application, host='0.0.0.0'))

    @pytest.fixture
    def test_route(self, function_session_id):
        return f"/test/{function_session_id}/"

    def test_routes_with_jwt_auth_and_allow_any(self, monkeypatch, sanic_test_server, test_user_token_factory,
                                                test_route):

        # Test without token
        self.gateway.app = sanic_test_server.app
        # self.gateway.app._port = sanic_test_server.port
        monkeypatch.setattr(settings, 'SERVICE_PORT', sanic_test_server.port)

        self.gateway.force_target_healthy()
        import time
        time.sleep(5)

        test_url = f'http://{settings.KONG_HOST}:18000{test_route}'

        resp = requests.get(test_url)
        assert resp.status_code == 202, resp.text
        assert resp.json() == {'anonymous_header': True, 'user_type': '_AnonymousUser'}

        # Test with token
        token = test_user_token_factory(level=UserLevels.ACTIVE)

        resp = requests.get(test_url, headers={"Authorization": token})

        assert resp.status_code == 202
        assert resp.json() == {'anonymous_header': False, 'user_type': 'User'}

        # Test with banned user
        token = test_user_token_factory(level=UserLevels.BANNED)

        resp = requests.get(test_url, headers={"Authorization": token})
        response_json = resp.json()
        assert resp.status_code == 401

    def test_routes_with_jwt_auth_and_is_authenticated(self, sanic_test_server, test_user_token_factory,
                                                             test_route):
        import time
        # self.gateway.app = sanic_test_server.app
        # self.gateway.app._port = sanic_test_server.port
        time.sleep(1)
        gateway.force_target_healthy()

        test_url = f'http://{settings.KONG_HOST}:18000{test_route}'
        time.sleep(6)
        # Test without token
        resp = requests.get(test_url)

        response_json = resp.text
        assert resp.status_code == 401, response_json
        assert response_json == {'anonymous_header': True, 'user_type': '_AnonymousUser'}

        # request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}')
        # assert response.status == 401

        # Test with token
        token = test_user_token_factory(level=UserLevels.ACTIVE)

        resp = requests.get(test_url, headers={"Authorization": token})
        response_json = resp.text
        assert resp.status_code == 202
        assert response_json == {'test': 'success'}

            # assert response_json == {'anonymous_header': True, 'user_type': '_AnonymousUser'}

        # request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}',
        #                                                         headers={'Authorization': f"{token}"})
        #
        # assert response.status == 202
        # assert response.json == {'test': 'success'}

        # Test with banned user
        token = test_user_token_factory(level=UserLevels.BANNED)
        resp = requests.get(test_url, headers={"Authorization": token})
        assert resp.status_code == 401
        # request, response = try_multiple(f'http://{settings.KONG_HOST}:18000{route}', 401, {'Authorization': f"{token}"})
        token = test_user_token_factory(level=UserLevels.ACTIVE)
        resp = requests.get(test_url, headers={"Authorization": token})
        assert resp.status_code == 401
        # assert response_json == {'test': 'success'}

    # request, response = insanic_application.test_client.get(f'http://{settings.KONG_HOST}:18000{route}',
        #                                                         headers={'Authorization': f"{token}"})

        # assert response.status == 401

    async def test_register_service_idempotence(self, monkeypatch, insanic_application, session_id):

        monkeypatch.setattr(self.gateway, "_service_name", session_id[:10])

        self.gateway.app = insanic_application
        self.gateway.register_service()
        assert hasattr(self.gateway, "service_id")
        assert self.gateway.service_id is not None
        sid = self.gateway.service_id

        self.gateway.register_service()
        assert sid == self.gateway.service_id

        self.gateway.register_service()
        assert sid == self.gateway.service_id

        # clean up
        self.gateway.deregister_service()

    async def test_upstream_object(self, monkeypatch, insanic_application, session_id):
        monkeypatch.setattr(self.gateway, "_service_name", session_id[:10])

        upstream_object = self.gateway.upstream_object

        assert upstream_object['name'] == self.gateway.kong_service_host
        assert upstream_object['healthchecks']['active']['http_path'].endswith('/health/')
        assert upstream_object['healthchecks']['active']['healthy']['http_statuses'] == [200]

    async def test_register_service_upstream_target(self, monkeypatch, insanic_application, session_id):

        monkeypatch.setattr(self.gateway, "_service_name", session_id[:10])

        self.gateway.app = insanic_application
        self.gateway.register_service()
        assert hasattr(self.gateway, "service_id")
        assert self.gateway.service_id is not None

        # test register upstream
        self.gateway.register_upstream()
        assert hasattr(self.gateway, "upstream_id")
        assert self.gateway.upstream_id is not None
        upstream_id = self.gateway.upstream_id

        # test register target
        self.gateway.register_target()
        assert hasattr(self.gateway, 'target_id')
        assert self.gateway.target_id is not None
        target_id = self.gateway.target_id

        # test register target idempotence
        self.gateway.register_target()
        assert target_id == self.gateway.target_id

        # test upstream idempotence
        self.gateway.register_upstream()
        assert upstream_id == self.gateway.upstream_id

        # clean up
        self.gateway.deregister_target()
        self.gateway.deregister_upstream()
        self.gateway.deregister_service()


    async def test_register_routes_but_no_routes(self, monkeypatch, insanic_application):
        '''
        no routes added to insanic application so will not fire to kong

        :param monkeypatch:
        :param insanic_application:
        :param unused_port:
        :param kong_get_service_detail_200:
        :return:
        '''

        self.gateway.app = insanic_application
        self.gateway.register_service()
        assert hasattr(self.gateway, "service_id")
        assert self.gateway.service_id is not None
        # this will trigger deregister service because there aren't any public routes
        self.gateway.register_routes()

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

        self.gateway.app = insanic_application
        self.gateway.register_service()
        assert hasattr(self.gateway, "service_id")
        assert self.gateway.service_id is not None
        self.gateway.register_routes()

        assert len(self.gateway.routes) == 1
        assert [normalize_url_for_kong(r) for r in insanic_application.public_routes().keys()] in [r['paths'] for r
                                                                                                   in
                                                                                                   self.gateway.routes.values()]
        assert ["GET"] in [r['methods'] for r in self.gateway.routes.values()]

        # deregistration flow
        self.gateway.deregister_routes()
        assert len(self.gateway.routes) == 0
        self.gateway.deregister_service()
        assert self.gateway.service_id is None

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

        self.gateway.app = insanic_application
        self.gateway.register_service()
        assert hasattr(self.gateway, "service_id")
        assert self.gateway.service_id is not None
        self.gateway.register_routes()

        # Create a Kong consumer
        req_payload = {'username': kong_jwt_test_fixture}
        resp = requests.post(
            f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/consumers/", json=req_payload
        )
        result = resp.json()

        assert "username" in result
        assert result['username'] == req_payload['username']

        consumer_id = result['id']

        # Create JWT credentials for user
        resp = requests.post(
            f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/consumers/{req_payload['username']}/jwt/",
        )
        result = resp.json()

        assert result['consumer_id'] == consumer_id
        assert all(key in result for key in ('created_at', 'id', 'algorithm', 'key', 'secret', 'consumer_id'))

        self.gateway.deregister_routes()
        self.gateway.deregister_service()

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

        self.gateway.register_service()
        self.gateway.register_routes()

        # Get routes id - Only one route should be available.
        try:
            route_id = list(self.gateway.routes.keys())[0]
        except IndexError:
            pass

        resp = requests.get(f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/plugins?route_id={route_id}")
        result = resp.json()
        assert resp.status_code == 200
        assert 'data' in result
        assert any(d['name'] == 'jwt' for d in result['data'])

        self.gateway.deregister_routes()
        self.gateway.deregister_service()

        resp = requests.get(f"http://{settings.KONG_HOST}:{settings.KONG_ADMIN_PORT}/plugins?route_id={route_id}")
        result = resp.json()
        assert resp.status_code == 200
        assert 'total' in result and result['total'] == 0
        assert 'data' in result and not result['data']

    async def test_register_routes_without_register_service(self, insanic_application):

        with pytest.raises(RuntimeError):
            self.gateway.app = insanic_application
            self.gateway.register_routes()

    async def test_deregister_routes_but_with_route_leftover_from_last_run(self, monkeypatch, insanic_application):

        monkeypatch.setattr(settings._wrapped, "ALLOWED_HOSTS", ['test.mmt.local'], raising=False)

        class MockView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

        insanic_application.add_route(MockView.as_view(), "/hello")

        self.gateway.app = insanic_application
        self.gateway.register_service()
        assert hasattr(self.gateway, "service_id")
        assert self.gateway.service_id is not None
        self.gateway.register_routes()

        self.gateway.routes = {}

        self.gateway.deregister_routes()

        assert self.gateway.routes == {}

    async def test_deregister_routes_with_no_routes(self, insanic_application, caplog):

        self.gateway.app = insanic_application
        self.gateway.register_service()
        self.gateway.deregister_routes()

        assert caplog.records[-1].message.endswith("This instance did not register any routes.")

    async def test_deregister_service_without_register(self, caplog):
        self.gateway.deregister_service()
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

        self.gateway.register(insanic_application)
        self.gateway.deregister()

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
                if "test" in r['name']:
                    service_ids.append(r['id'])

            if "next" in body and body['next']:
                next_url = kong_base_url.with_path(body['next'])
            else:
                break

        assert len(service_ids) == 1

    @pytest.mark.parametrize(
        'path1, path2, method1, method2, expected',
        (
                ("/a", "/a", ["a"], ["a"], False),
                ("/a", "/b", ["a"], ["a"], True),
                ("/a", "/a/b", ["a"], ["a"], True),
                ("/a", "/a", ["a"], ["b"], True),
                ("/a", "/a", ["a"], ["a","b"], True),
                ("/a", "/a", ["b","a"], ["a", "b"], False),
        )
    )
    def test_route_change_detected(self, path1, path2, method1, method2, expected):

        route1 = self.gateway._route_object(path1, method1)
        route2 = self.gateway._route_object(path2, method2)

        assert self.gateway.change_detected(route1, route2, ['paths', 'methods']) == expected
