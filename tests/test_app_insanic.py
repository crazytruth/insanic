import pytest
from sanic.response import json
from sanic.router import RouteExists

from insanic import Insanic
from insanic.functional import empty
from insanic.views import InsanicView
from insanic.scopes import public_facing

from .conftest_constants import ROUTES


class TestInsanic:
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

        public_routes = insanic_application.public_routes()

        assert len(public_routes) == len(self.routes)

        insanic_application._public_routes = empty
