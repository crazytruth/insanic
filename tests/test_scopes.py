import pytest

from sanic.response import json
from insanic.functional import empty
from insanic.scopes import public_facing, get_my_ip
from insanic.views import InsanicView



class TestPublicFacingScope:

    @pytest.mark.parametrize("decorator", (
            public_facing,  # this means anything is allowed
            public_facing(),  # this means anything is allowed
            public_facing(params=[]),  # this means that no query params are allowed
            public_facing(params=["trash"]),  # only `trash` is allowed
            public_facing(params=["trash", "rubbish"]),  # only `trash` and `rubbish` is allowed
    ))
    def test_public_facing_decorator(self, insanic_application, decorator):
        class PublicView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @decorator
            def get(self, request, *args, **kwargs):
                return json({})

            def post(self, request, *args, **kwargs):
                return json({})

            @decorator
            def delete(self, request, *args, **kwargs):
                return json({})

        route = '/hello'
        insanic_application.add_route(PublicView.as_view(), route)
        assert insanic_application._public_routes is empty

        public_routes = insanic_application.public_routes()

        assert f"^{route}$" in public_routes.keys()
        assert sorted(["GET", "DELETE"]) == sorted(public_routes[f"^{route}$"]['public_methods'])

    def test_positional_args_in_view(self, insanic_application):
        get_response = {"method": "get"}
        post_response = {"method": "post"}

        class MockView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @public_facing
            def get(self, request, user_id, *args, **kwargs):
                return json(get_response, status=200)

            @public_facing
            async def post(self, request, user_id, *args, **kwargs):
                return json(post_response, status=201)

        insanic_application.add_route(MockView.as_view(), '/test/<user_id>')

        request, response = insanic_application.test_client.get("/test/1234")
        assert response.status == 200
        assert response.json == get_response

        request, response = insanic_application.test_client.post("/test/1234")
        assert response.status == 201
        assert response.json == post_response

    @pytest.mark.parametrize("decorator,query_params,expected_status_code", (
            (public_facing, None, 200),  # this means anything is allowed
            (public_facing, "trash=a", 200),  # this means anything is allowed
            (public_facing(), None, 200),  # this means anything is allowed
            (public_facing(), "trash=a", 200),  # this means anything is allowed
            (public_facing(params=[]), None, 200),  # this means that no query params are allowed
            (public_facing(params=[]), 'trash=a', 400),  # this means that no query params are allowed
            (public_facing(params=["trash"]), None, 200),  # only `trash` is allowed
            (public_facing(params=["trash"]), 'trash=a', 200),  # only `trash` is allowed
            (public_facing(params=["trash"]), 'trash=a&ssuregi=b', 400),  # only `trash` is allowed
            (public_facing(params=["trash", "rubbish"]), None, 200),  # only `trash` and `rubbish` is allowed
            (public_facing(params=["trash", "rubbish"]), 'trash=a', 200),  # only `trash` and `rubbish` is allowed
            (public_facing(params=["trash", "rubbish"]), 'trash=a&rubbish=b', 200),
            # only `trash` and `rubbish` is allowed
            (public_facing(params=["trash", "rubbish"]), 'trash=a&ssuregi=b', 400),
    # only `trash` and `rubbish` is allowed
    ))
    def test_query_params_validation(self, insanic_application, decorator, query_params, expected_status_code):
        get_response = {"method": "get"}
        post_response = {"method": "post"}

        class MockView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @decorator
            def get(self, request, user_id, *args, **kwargs):
                return json(get_response, status=200)

        insanic_application.add_route(MockView.as_view(), '/test/<user_id>')

        endpoint = "/test/1234"
        if query_params is not None:
            endpoint = f"{endpoint}?{query_params}"

        request, response = insanic_application.test_client.get(endpoint)
        assert response.status == expected_status_code

    @pytest.mark.parametrize("decorator,query_params,expected_status_code", (
            (public_facing, None, 200),  # this means anything is allowed
            (public_facing, "trash=a", 200),  # this means anything is allowed
            (public_facing(), None, 200),  # this means anything is allowed
            (public_facing(), "trash=a", 200),  # this means anything is allowed
            (public_facing(params=[]), None, 200),  # this means that no query params are allowed
            (public_facing(params=[]), 'trash=a', 400),  # this means that no query params are allowed
            (public_facing(params=["trash"]), None, 200),  # only `trash` is allowed
            (public_facing(params=["trash"]), 'trash=a', 200),  # only `trash` is allowed
            (public_facing(params=["trash"]), 'trash=a&ssuregi=b', 400),  # only `trash` is allowed
            (public_facing(params=["trash", "rubbish"]), None, 200),  # only `trash` and `rubbish` is allowed
            (public_facing(params=["trash", "rubbish"]), 'trash=a', 200),  # only `trash` and `rubbish` is allowed
            (public_facing(params=["trash", "rubbish"]), 'trash=a&rubbish=b', 200),
            # only `trash` and `rubbish` is allowed
            (public_facing(params=["trash", "rubbish"]), 'trash=a&ssuregi=b', 400),
            # only `trash` and `rubbish` is allowed

    ))
    def test_query_params_validation_async(self, insanic_application, decorator, query_params, expected_status_code):
        get_response = {"method": "get"}
        post_response = {"method": "post"}

        class MockView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @decorator
            async def get(self, request, user_id, *args, **kwargs):
                return json(get_response, status=200)

        insanic_application.add_route(MockView.as_view(), '/test/<user_id>')

        endpoint = "/test/1234"
        if query_params is not None:
            endpoint = f"{endpoint}?{query_params}"

        request, response = insanic_application.test_client.get(endpoint)
        assert response.status == expected_status_code

    def test_get_my_ip(self):

        import timeit
        assert timeit.timeit('get_my_ip()', number=10000, setup='from insanic.scopes import get_my_ip') < 1
