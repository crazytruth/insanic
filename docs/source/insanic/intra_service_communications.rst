Intra Service Communications
=============================

One of the core additional features of :code:`Insanic`,
is the :code:`Service` object.  The :code:`Service` object
facilitates easy http request responses to other services running,
not only :code:`Insanic` (although it will be easier), but to
other services within the microservices.

Features of the :code:`Service` object includes:

- Address resolution, especially if you have a pattern for your host names.
- Endpoint Construction
- Error Handling
- Response Handling
- Injection of User and Service Context headers

Under the hood, the :code:`Service` object uses the :code:`httpx.AsyncClient` for making requests.


Basic Usage
------------

.. code-block:: python

    from insanic.loading import get_service

    UserService = get_service('user')

    # only http/1.1
    response, status_code = await UserService.http_dispatch(
        'GET',
        '/api/v1/users/',
        query_params={"query": "insanic"},
        include_status_code=True
    )

The function, :code:`get_service`, is a helper method that returns a :code:`Service`
instance of the service the developer wants to send a request to.

The instances are initialized in a
:code:`ServiceRegistry` with only available services defined
in the `SERVICE_CONNECTIONS` and `REQUIRED_SERVICE_CONNECTIONS`
settings.  Attempting to get any services not defined in either
of those settings will raise a :code:`RuntimeError`.


Exceptions
------------

- :code:`httpx` exceptions are translated to an instance of :code:`insanic.exceptions.APIException`


See Also
---------

- :ref:`api-insanic-services`
