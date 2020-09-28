.. _`Django-REST-Framework's Authentication`: https://www.django-rest-framework.org/api-guide/authentication/
.. _`Django-REST-Framework's Permissions`: https://www.django-rest-framework.org/api-guide/permissions/
.. _`Sanic's Class-Based Views`: https://sanic.readthedocs.io/en/latest/sanic/class_based_views.html

Authentication and Permissions
===============================

.. note::

    `Django-REST-Framework's Authentication`_ and
    `Django-REST-Framework's Permissions`_ pattern
    was referenced for this implementation.

Insanic takes `Sanic's Class-Based Views`_ and extends
it to handle authentication and check for permissions.

To register authentication and permissions, we must
first create or use the general authentication and
permissions provided by Insanic.

Insanic only provides :code:`JWT` authentication because
it is most suitable for microservices.  Session based implementations
require state and synchronizing states across services introduces
complexity.  You might wonder, what about verifying if the token
with its respective key requires state?  In my humble opinion,
one of the better practices, is to have an API Gateway that will handle the
JWT verification for you. This way you don't need to verify the request
in the application, and only use the JWT payload for creating request
context.


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
:code:`JSONWebTokenAuthentication`. The authentication class will decode the
:code:`jwt` token from the headers and sets the :code:`user`
attribute on the request object.

Then the :code:`permission_classes` are iterated through to
determine this user has the necessary permissions to
access this view.  In this case :code:`AllowAny` allows everyone
to request this view.


JSONWebTokenAuthentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The general flow for the authentication class is as follows:

1. Get the authorization header from the request
object and compares the prefix it to the `JWT_AUTH_HEADER_PREFIX`
defined in the settings.

2. Decode the :code:`JWT` token.  While decoding the following exceptions may occur

    1. Exception if it determines the signature has expired
    2. Exception when decoding signature
    3. Exception if an Invalid token

3. Lastly, deems the user authenticated and sets the user to the
:code:`request` object.


ServiceJWTAuthentication
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :code:`ServiceJWTAuthentication` verifies the :code:`JWT` was from
another Insanic service and sets the service to the request object.

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

If Insanic's permissions are not enough, the developer has option
to create their own custom permission.  However, it should inherit
the :code:`BasePermission` class and have it's own :code:`has_permission`
method implemented.

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
