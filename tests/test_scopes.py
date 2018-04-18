from sanic.response import json
from insanic.scopes import public_facing
from insanic.views import InsanicView


class TestPublicFacingScope:

    def test_public_facing_decorator(self, insanic_application):
        class PublicView(InsanicView):
            authentication_classes = ()
            permission_classes = ()

            @public_facing
            def get(self, request, *args, **kwargs):
                return json({})

            def post(self, request, *args, **kwargs):
                return json({})

            @public_facing
            def delete(self, request, *args, **kwargs):
                return json({})

        route = '/hello'
        insanic_application.add_route(PublicView.as_view(), route)

        public_routes = insanic_application.public_routes()

        assert f"^{route}$" in public_routes.keys()
        assert sorted(["GET", "DELETE"]) == sorted(public_routes[f"^{route}$"])

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
