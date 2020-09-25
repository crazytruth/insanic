HTTP Status Codes
====================

I have imported the status codes from
`Django Rest Framework <http://www.django-rest-framework.org/api-guide/status-codes/>`_
to make code more readable. I have had the pleasure of working with them, so I have
included them for use in Insanic.

Usage
------

.. code-block:: python

    # in python console
    >>> from insanic import status
    >>> status.HTTP_200_OK
    200


Possible usages:

- When giving a response.

- Defining status codes in Insanic exceptions.


.. _`api-insanic-status`:

:code:`insanic.status`
-----------------------

.. automodule:: insanic.status
    :members:
