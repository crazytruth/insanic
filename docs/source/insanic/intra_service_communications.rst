Intra Service Communications
=============================

One of the core additional features of :code:`Insanic`,
that differentiates it from other frameworks,
is the :code:`Service` object.  The :code:`Service` object
allows easy http request responses to other services running,
not only :code:`Insanic` (although it will be easier), but to
other services within the microservice architecture.

Features of the :code:`Service` object includes:

- Address resolution, especially if you have a pattern for your host names
- Endpoint Construction
- Error Handling
- Response Handling
- Inject User and Service Context headers for the receiving service

Under the hood, the :code:`Service` object uses the :code:`httpx`
:code:`AsyncClient` for making requests.


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

Under the hood, the instances are initialized in a
:code:`ServiceRegistry` with only available services defined
in the `SERVICE_CONNECTIONS` and `REQUIRED_SERVICE_CONNECTIONS`
settings.  Attempting to get any services not defined in either
of those settings will raise a :code:`RuntimeError`.


API Reference
--------------

.. code-block:: python

    >>> print(Service.http_dispatch.__doc__)

        Interface for sending requests to other services.

        :param method: method to send request (GET, POST, PATCH, PUT, etc)
        :type method: string
        :param endpoint: the path to send request to (eg /api/v1/..)
        :type endpoint: string
        :param query_params: query params to attach to url
        :type query_params: dict
        :param payload: the data to send on any non GET requests
        :type payload: dict
        :param files: if any files to send with request, must be included here
        :type files: dict
        :param headers: headers to send along with request
        :type headers: dict
        :param propagate_error: if you want to raise on 400 or greater status codes
        :type propagate_error: bool
        :param include_status_code: if you want this method to return the response with the status code
        :type include_status_code: bool
        :param response_timeout: if you want to increase the timeout for this requests
        :type response_timeout: int
        :param retry_count: number times you want to retry the request if failed on server errors
        :type response_timeout: int
        :return:
        :rtype: Coroutine that returns dict or tuple(dict, int)


Exceptions
------------

- :code:`httpx` exceptions are translated to an instance of :code:`insanic.exceptions.APIException`
