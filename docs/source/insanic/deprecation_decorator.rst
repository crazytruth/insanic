Endpoint Deprecation
=====================

Deprecation Decorator
----------------------

Insanic provides a decorator that allows the developer to
decorate any views that will be deprecated in the future.
The developer is able to specify when the api will no
longer be in service.

The decorator emits a warning when called calling to action
the service maintainer of the request service or frontend
developers to update to the newer endpoint.

.. code-block:: python

    >>> from insanic.decorators import deprecate
    >>> print(deprecate.__doc__)

        emits a warning if an request is made to the decorated method/path

        :param at: datetime object or timestamp
        :param ttl: (default 1 day) the frequency at which the warning messages will be logged

The value of :code:`ttl` can be modified with the
:code:`DEPRECATION_WARNING_FREQUENCY` settings, or passed
directly as a keyword argument when initializing the decorator.

Usage
^^^^^^

We have several ways to indicate a certain endpoint
will be deprecated.

1. Decorate a specific class method.

*If only a certain method of an endpoint will be deprecated.*

.. code-block:: python

    from insanic.decorators import deprecate
    from insanic.views import InsanicView

    class SomeDeprecatedView(InsanicView):

        @deprecate(at={some time in the future}, ttl=1)
        async def get(self, request, *args, **kwargs):
            return json_response({})

        async def post(self, request, *args, **kwargs):
            return


2. Decorate a function.

.. code-block:: python

    from insanic.decorators import deprecate

    @app.route('/dep')
    @deprecate(at={some time in the future}, ttl=1111111)
    async def some_deprecated_api_handler(request, *args, **kwargs):
        return json_response({})

3. Decorate the whole view Class.

*If all methods of the endpoint will be deprecated.*

.. code-block:: python

    from insanic.decorators import deprecate
    from insanic.views import InsanicView

    @deprecate(at={some time in the future})
    class DeprecatedView(InsanicView):
        async def get(self, request, *args, **kwargs):
            return json_response({})

        async def post(self, request, *args, **kwargs):
            return json_response({})


4. Deprecate when adding routes.

.. code-block:: python

    # in app.py
    from insanic import Insanic
    from insanic.decorators import deprecate
    from {your app}.views import SomeDeprecatedView

    deprecation_policy = deprecate(at={sometime in the future})

    app = Insanic('myapp')

    app.add_route(deprecation_policy(SomeDeprecatedView).as_view(), '/dep/<id:int>')


Output
^^^^^^^

The warning message will be in the following format::

    [DEPRECATION WARNING] For maintainers of @<SERVICE_NAME|FE>! <method> <path> will be deprecated on <time of deprecation>. You have <days and time left until deprecation> left!

For example:::

    [DEPRECATION WARNING] For maintainers of @USER! GET /api/v1/user/<id:uuid>/ will be deprecated on 2019-12-06 05:00:59.641592+00:00. You have 0:00:00.004675 left!
