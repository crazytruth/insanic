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
        assert ["GET", "DELETE"] == public_routes[f"^{route}$"]
