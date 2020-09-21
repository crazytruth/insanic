Error Handling in Insanic
===========================

.. note::

    Take a look at Sanic's
    `Exceptions <https://sanic.readthedocs.io/en/latest/sanic/exceptions.html>`_
    documentation to better understand how Insanic's error handling works.

Insanic's error handling is done with Sanic's error handling
functionality, however, with Insanic's own exception and error
definitions.  Before we move onto the components that comprise of
an Insanic exception let's take a look at a quick example.


.. code-block:: python

    # in example/app.py
    from insanic import Insanic
    from insanic.conf import settings
    from insanic.errors import GlobalErrorCodes
    from insanic.exceptions import APIException

    __version__ = '0.1.0'

    settings.configure()
    app = Insanic('example', version=__version__)

    @app.route('/help')
    def help_view(request, *args, **kwargs):
        raise APIException("Help me! Something blew up!",
                           error_code=GlobalErrorCodes.error_unspecified,
                           status_code=400)

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=8000)


With this piece of code, let's try running...

.. code-block:: bash

    $ python app.py

Now by sending a request to the server...

.. code-block:: bash

    curl -i http://0.0.0.0:8000/help
    HTTP/1.1 400 Bad Request
    Content-Length: 139
    Content-Type: application/json
    Connection: keep-alive
    Keep-Alive: 60

    {
        "message":"An unknown error occurred",
        "description":"Help me! Something blew up!",
        "error_code":{
            "name":"insanic_error_unspecified",
            "value":999998
        }
    } # response was formatted for readability

From the response there are a couple components we need to
cover to understand how Insanic's error handler works.

#. The :code:`GlobalErrorCodes`
#. The :code:`APIException`
#. The response.


1. Error Codes
----------------------------------

In a distributed system, errors can happen anywhere. It can happen within
the service you have created, or it could happen down the road where you made a
request to another service for some additional information, or even worse,
the other service could get a different error message from a request that it had
to make.

As a result, the only way to keep track and possibly debug the situation,
specific pin point traceability was very important. Of course, just returning
a 400 Bad Request error response could suffice, but in some instances,
an application may have to react in a certain manner if it receives a
400 Bad Request error WITH a certain Error Code. For example, rolling back
a database commit only for a specific situation.

Insanic provides common error codes, accessible in :code:`insanic.errors.GlobalErrorCodes`
but each service may provide their own specific error codes with one restriction.
The code must be an :code:`Enum` type.

To create your own:

.. code-block:: python

    # example/errors.py
    from enum import Enum

    class MyErrorCodes(Enum):
        not_going_fast_enough = 10001
        too_slow = 10002
        help_me = 10003


When set to the :code:`error_code` attribute in the Insanic
exception (we will get to that bit later), the enum will be unpacked
by Insanic's Error Handler to a JSON object. So,
:code:`MyErrorCodes.not_going_fast_enough` will be unpacked like so:

.. code-block:: json

    {
        "name":"not_going_fast_enough",
        "value":10001
    }


2. Insanic APIException
----------------------

Insanic provides its own :code:`APIException` base class for its own
error handling.  This exception will create the response as shown above.

There are 4 attributes to the exception.

#. :code:`status_code`: an integer representing the status code of the response.
#. :code:`description`: a string with human readable description of the error.
#. :code:`error_code`: an Enum as explained in the ErrorCode section above.
#. :code:`message`: a string with a general message.

There are several exceptions provided as base templates, but it is
up to the developer to define how detailed the exceptions will be.

.. code-block:: python

    # example/exceptions.py
    from insanic import status
    from insanic.exceptions import APIException, BadRequest

    from .errors import MyErrorCodes

    class TooSlowException(APIException):
        status_code = status.HTTP_408_REQUEST_TIMEOUT
        description = "Too slow!"
        error_code = MyErrorCodes.too_slow

    class MyBadRequest(BadRequest):
        error_code = MyErrorCodes.not_going_fast_enough

To use these exceptions...

.. code-block:: python

    # example/views.py
    from insanic import status
    from insanic.exceptions import APIException
    from .app import app  # your insanic application
    from .errors import MyErrorCodes
    from .exceptions import TooSlowException

    @app.route('/too_slow`)
    def too_slow_view(request, *args, **kwargs):
        raise TooSlowException()

    @app.route('/very_slow')
    def very_slow_view(request, *args, **kwargs):
        raise TooSlowException("This is very slow!")

    @app.route('/help_me_too_slow')
    def help_me_too_slow(request, *args, **kwargs):
        raise APIException(
            "HELP ME!",
            error_code=MyErrorCodes.help_me,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT
        )


3. Putting ErrorCodes and Exceptions together
-----------------------------------------------

With exceptions and error codes defined, Insanic's error handler
will convert the exception to the error response structure as shown in the
example.

.. code-block:: python

    class TooSlowException(APIException):
        status_code = status.HTTP_408_REQUEST_TIMEOUT
        description = "Too slow!"
        error_code = MyErrorCodes.too_slow

With this exception we created above, it will create this response.

.. code-block:: json

    {
        "message":"An unknown error occurred",
        "description":"Too slow!",
        "error_code":{
            "name":"too_slow",
            "value":10002
        }
    }

- The :code:`status_code` is the status code of the response.
- The :code:`description` is the description.
- The :code:`message` is the message attribute in `APIException`.
- The :code:`error_code` is the unpacked enum.


EXTRA: What about NON-Insanic Exceptions?
------------------------------------------

Any Sanic Exceptions will automatically converted to an
Insanic Exception and will try and serialize the message
into Insanic's error message format.

.. code-block:: python

    @app.route('/sanic')
    def raise_sanic(request, *args, **kwargs):
        raise ServiceUnavailable('sanic error')

Will result in...

.. code-block:: bash

    $ curl -i http://0.0.0.0:8000/sanic
    HTTP/1.1 503 Service Unavailable
    Content-Length: 126
    Content-Type: application/json
    Connection: keep-alive
    Keep-Alive: 60

    {
        "message":"Service Unavailable",
        "description":"sanic error",
        "error_code":{
            "name":"insanic_error_unspecified",
            "value":999998
        }
}

Any NON-Insanic and NON-Sanic exceptions raised during the process of a request
will default to a `500 Internal Server Error`.

.. code-block:: json

    {
        "message": "Server Error",
        "description": "Something has blown up really bad. Somebody should be notified?",
        "error_code": {
            "name":"unknown_error",
            "value":999999
        }
    }


See Also...
-------------

- Refer to the insanic.errors module for insanic's ErrorCodes.
- Refer to the insanic.exceptions module for Insanic's Exceptions.
- Refer to the insanic.status module for easy status codes.
