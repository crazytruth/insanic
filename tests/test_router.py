import pytest
from sanic.response import json
from sanic.router import RouteExists

from insanic import Insanic
from insanic.functional import empty
from insanic.router import InsanicRouter
from insanic.scopes import public_facing
from insanic.views import InsanicView

from .conftest_constants import ROUTES


class TestInsanicRouter:
    routes = []

    @pytest.fixture("module")
    def insanic_application(self):
        return Insanic("test")

    def add_route(self, insanic_application, route):
        try:

            @insanic_application.route(route)
            @public_facing
            def get(self, request, *args, **kwargs):
                return json({}, status=200)

        except RouteExists:
            pass
        else:
            self.routes.append(route)

    @pytest.mark.parametrize("route", ROUTES)
    def test_public_routes(self, insanic_application, route):

        self.add_route(insanic_application, route)

        public_routes = insanic_application.router.routes_public

        assert len(public_routes) == len(self.routes)
        # need this to recalculate public routes, otherwise just returns the saved routes
        insanic_application._public_routes = empty

    @pytest.mark.parametrize("route", ROUTES)
    def test_public_routes_classes(self, insanic_application, route):

        self.add_route(insanic_application, route)

        public_routes = insanic_application.router.routes_public

        assert len(public_routes) == len(self.routes)

        insanic_application._public_routes = empty

    def test_public_routes_class_view(self):
        insanic_application = Insanic("test2")

        class ClassView(InsanicView):
            @public_facing
            def get(self, request, *args, **kwargs):
                return {"method": "get"}

            @public_facing
            def post(self, request, *args, **kwargs):
                return {"method": "post"}

            def put(self, request, *args, **kwargs):
                return {"method": "put"}

        insanic_application.add_route(
            handler=ClassView.as_view(),
            uri="/insanic/",
            name="ClassView",
            strict_slashes=True,
        )

        routes = insanic_application.router.routes_public
        assert "^/insanic/$" in routes
        assert sorted(routes["^/insanic/$"]["public_methods"]) == sorted(
            ["GET", "POST"]
        )

    def test_public_routes_same_endpoint_different_views(self):
        insanic_application = Insanic("test2")

        class GetOnlyView(InsanicView):
            @public_facing
            def get(self, request, *args, **kwargs):
                return {"method": "get"}

            def delete(self, request, *args, **kwargs):
                return {"method": "delete"}

        class PostOnlyView(InsanicView):
            @public_facing
            def post(self, request, *args, **kwargs):
                return {"method": "post"}

        insanic_application.add_route(
            handler=GetOnlyView.as_view(),
            uri="/insanic/",
            methods=["GET"],
            name="GetOnlyView",
            strict_slashes=True,
        )
        insanic_application.add_route(
            handler=PostOnlyView.as_view(),
            uri="/insanic/",
            methods=["POST"],
            name="PostOnlyView",
            strict_slashes=True,
        )

        routes = insanic_application.router.routes_public

        assert "^/insanic/$" in routes
        assert sorted(routes["^/insanic/$"]["public_methods"]) == sorted(
            ["GET", "POST"]
        )
