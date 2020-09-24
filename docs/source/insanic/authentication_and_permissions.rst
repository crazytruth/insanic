.. _`Django-REST-Framework's Authentication`: https://www.django-rest-framework.org/api-guide/authentication/
.. _`Django-REST-Framework's Permissions`: https://www.django-rest-framework.org/api-guide/permissions/
.. _`Sanic's Class-Based Views`: https://sanic.readthedocs.io/en/latest/sanic/class_based_views.html

Authentication and Permissions
===============================

.. note::

    `Django-REST-Framework's Authentication`_ and
    `Django-REST-Framework's Permissions`_ pattern
    was referenced for this implementation.

Insanic takes `Sanic's Class-Based Views`_ and modifies
them to handle authentication and check for permissions.

To register authentication and permissions, we must
first create or use the general authentication and
permission provided by Insanic.

Insanic only provides :code:`JWT` authentication because
it is most suitable for microservices.  Session based implementations
require state and synchronizing states across services introduces
complexity.  You might wonder, what about verifying if the token
with its respective key requires state?  One of the better practices,
in my opinion, is to have an API Gateway that will handle the
JWT verification for you.


Views
------

.. code-block:: python

    from sanic.response import json
    from insanic import permissions, authentication
    from insanic.views import InsanicView


    class GottaGoInsanelyFastView(InsanicView):
        permission_classes = (permissions.AllowAny,)
        authentication_classes = (
            authentication.JSONWebTokenAuthentication,
        )

        async def get(self, request, *args, **kwargs):
            return json({"how fast?": "insanely fast"})


This will authenticate the request with the declared
:code:`authentication_classes`, in this case the
:code:`JSONWebTokenAuthentication`. This will decode the
:code:`jwt` token from the headers and sets the :code:`user`
attribute on the request object.

Then the :code:`permission_classes` are iterated through to
determine this use has the necessary permissions to
access this view.  In this case :code:`AllowAny` allows everyone
to request this view.


JSONWebTokenAuthentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The general flow for the authentication class is as follows:

1. Get the authorization header from the request
object and compares it to the `JWT_AUTH_HEADER_PREFIX`
defined in the settings.
2. Decodes the `jwt` token.  While decoding the following exceptions may occur

    1. Determines if the signature has expired
    2. Error decoding signature
    3. Invalid token

3. Deems the user authenticated. And sets the user to the
request object.


ServiceJWTAuthentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Gets the JWT token was from another Insanic service and sets
the service to the request object.

When making intra service requests, both
the service and user properties become available from the
request object after authentication.


Permissions
-------------

There are couple general usage permission classes in `insanic`

* :code:`AllowAny`
* :code:`IsAuthenticated`
* :code:`IsAdminUser`
* :code:`IsAuthenticatedOrReadOnly`
* :code:`IsOwnerOrAdmin`
* :code:`IsServiceOnly`

Basic flow for permissions is as follows

1. Iterates though the list of `permission_classes` as defined in the view.
2. Calls the `has_permission` method of the permission class
3. If **ALL** result in `True` the request is valid
4. If any is `False`, raises :code:`PermissionDenied` error.

View the :ref:`api-insanic-permissions` API Reference for more details.


Custom Permissions
^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # permissions.py
    from insanic.permissions import BasePermission

    class IsReadOrStaff(BasePermission):
        async def has_permission(self, request, view):
            if request.method.upper() in ['GET']:
                return True
            user = request.user
            if user['is_staff']:
                 return True
            return False


See Also
---------

- `Django-REST-Framework's Authentication`_
- `Django-REST-Framework's Permissions`_
- `Sanic's Class-Based Views`_
- :ref:`api-insanic-permissions` API Reference
