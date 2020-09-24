from sanic.router import Router as SanicRouter
from sanic.views import CompositionView


class InsanicRouter(SanicRouter):
    def __init__(self):
        super().__init__()

    @property
    def routes_public(self) -> dict:
        """
        Gathers all the registered routes and determines if they have been
        decorated with the :code:`public_facing` decorator.
        """

        _public_routes = {}

        for _url, route in self.routes_all.items():
            for method in route.methods:
                if hasattr(route.handler, "view_class"):
                    _handler = getattr(route.handler.view_class, method.lower())
                elif isinstance(route.handler, CompositionView):
                    _handler = route.handler.handlers[method.upper()].view_class
                    _handler = getattr(_handler, method.lower())
                else:
                    _handler = route.handler

                if hasattr(_handler, "scope") and _handler.scope == "public":
                    # if method is decorated with public_facing, add to kong routes
                    if route.pattern.pattern not in _public_routes:
                        _public_routes[route.pattern.pattern] = {
                            "public_methods": []
                        }
                    _public_routes[route.pattern.pattern][
                        "public_methods"
                    ].append(method.upper())

        return _public_routes
