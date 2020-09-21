.. _Sanic's Router: https://sanic.readthedocs.io/en/latest/sanic/routing.html

Insanic's Router
=================

The reason for this functionality is to provide a list of
endpoints that should be open to the public.  This
functionality is to facilitate the API Gateway pattern when
planning for an microservice architecture.


`public_facing` Usage
---------------------

.. note::

    Usage of :code:`Insanic`'s router is exactly the
    same as `Sanic's Router`_, so please refer to their documentation
    for exact usage.

HOWEVER, The only difference is with the :code:`routes_public`
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

The application's router is analyzed, going
through all the routes, and route methods looking
for the `public_facing` decorator where the
attribute `scope` is attached with the
value `"public"`.  In our example,
the methods `["GET", "POST", "DELETE"]` with the
route `/fast`.

Then when accessing the :code:`routes_public`
attribute on :code:`InsanicRouter`,
the registered routes will be traverse to look for the
routes decorated with the :code:`public_facing` decorator.

.. code-block:: python

    >>> from example.app import app
    >>> app.router
    <insanic.router.InsanicRouter object at 0x100ff3e48>
    >>> app.router.routes_public
    {'^/fast$': {'public_methods': ['DELETE', 'GET', 'POST']}}


Additional Usages
-------------------

The :code:`public_facing` decorator can be configured to only
accept only a list of defined query parameters.

.. automodule:: insanic.scopes.public_facing

.. code-block:: python

    >>> from insanic.scopes import public_facing
    >>> print(public_facing.__doc__)

        depending on usage can be used to validate query params
        @public_facing  -> does not validate query params and anything is allowed
        @public_facing() -> same as above
        @public_facing(params=[]) -> does not allow any query_params. hard failure (returns 400)
        @public_facing(params=['rabbit']) -> only allows query param "rabbit"

        :param fn: view to decorate
        :param params: params to validate against
        :return: function
        :raise: BadRequest if query_params don't validate


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
