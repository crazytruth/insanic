import pytest
from sanic.response import json
from sanic.router import RouteExists

from insanic import Insanic
from insanic.scopes import public_facing


class TestInsanic:
    routes = []

    @pytest.fixture(scope="module")
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

    def test_insanic_app(self):
        raise Exception("Test insanic app initialization")
