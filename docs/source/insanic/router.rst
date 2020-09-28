.. _Sanic's Router: https://sanic.readthedocs.io/en/latest/sanic/routing.html

Public Route Flagging
========================

The decision for this functionality is to provide a list of
endpoints that should be open to the public.  This
functionality is to facilitate the API Gateway pattern when
planning for a microservice architecture.

.. note::

    Usage of :code:`Insanic`'s router is exactly the
    same as `Sanic's Router`_, so please refer to their documentation
    for exact usage.

:code:`public_facing` usage
----------------------------

The only difference with Sanic's Router is the :code:`routes_public`
attribute that :code:`insanic.router.InsanicRouter` possesses.

To register a public route, we must decorate it with a
:code:`insanic.scopes.public_facing` decorator.  This
is to "flag" certain views' http request methods on whether
it should be public or not.

.. code-block:: python

    # in view.py
    from sanic.response import json
    from insanic.scopes import public_facing
    from insanic.views import InsanicView

    class GottaGoFastView(InsanicView):

        @public_facing
        def get(self, request, *args, **kwargs):
            return json({"method": "get"})

        @public_facing
        def post(self, request, *args, **kwargs):
            return json({"method": "post"})

        def put(self, request, *args, **kwargs):
            return json({})

        @public_facing
        def delete(self, request, *args, **kwargs):
            return json({"method": "delete"})

    # in app.py
    from .views import GottaGoFastView

    app = Insanic(__name__, __version__='0.0.0')
    app.add_route(GottaGoFastView.as_view(), "/fast")


Note we only have 3 of the 4 methods decorated with
the :code:`public_facing` decorator.

When accessing the :code:`routes_public` attribute from
the :code:`InsanicRouter`, the application's router is analyzed, iterating
through all the registered routes and route methods looking
for the :code:`public_facing` decorator where the
attribute :code:`scope` is attached with the
value :code:`"public"`.

In our example,
the methods :code:`["GET", "POST", "DELETE"]` with the
route `/fast` are decorated.


.. code-block:: python

    >>> from example.app import app
    >>> app.router
    <insanic.router.InsanicRouter object at 0x100ff3e48>
    >>> app.router.routes_public
    {'^/fast$': {'public_methods': ['DELETE', 'GET', 'POST']}}


Additional Usages
-------------------

The :code:`public_facing` decorator can be configured to only
accept a list of defined query parameters.

.. autodecorator:: insanic.scopes.public_facing

So if we modify our example above and run our code like so...

.. code-block:: python

    class GottaGoFastView(InsanicView):

        @public_facing(params=["trash",])
        def get(self, request, *args, **kwargs):
            return json({"method": "get"})


.. code-block:: bash

    $ curl "http://localhost:8000/fast?trash=1"
    {"method":"get"}

    $ curl -i "http://localhost:8000/fast?trash=1&garbage=1"
    HTTP/1.1 400 Bad Request
    Content-Length: 147
    Content-Type: application/json
    Connection: keep-alive
    Keep-Alive: 60

    {
        "message":"Bad request.",
        "description":"Invalid query params. Allowed: trash",
        "error_code":{
            "name":"insanic_invalid_query_params",
            "value":999400
        }
    }  # formatted for readability
