.. _Django REST Framework: https://www.django-rest-framework.org/api-guide/requests/
.. _Sanic Requests: https://sanic.readthedocs.io/en/latest/sanic/request_data.html


Request Object
=================

Apart from the request attributes provided by :code:`Sanic`'s
request object, :code:`insanic` creates additional attributes
with a lot of inspiration from `Django REST Framework`_, especially for
authentication.


Extra Attributes
-----------------

Request Parsing
^^^^^^^^^^^^^^^^

- :code:`request.data`
    Like with `Django REST Framework`_, data provides the parsed
    content of the request body. It includes all data
    including file and non-file inputs without needing to worry
    about :code:`content-type`.


- :code:`request.query_params`
    An alias for Sanic's :code:`request.args`,
    it includes all the query parameters in the request.


Authentication
^^^^^^^^^^^^^^^

- :code:`request.user`:
    Depending on the authentication class declared in the
    class view, this will return an User object or be an instance
    of AnonymousUser.  Like with Django REST Framework, authentication
    is done lazily.  First access will evaluate if the request is
    from a authenticated user.

- :code:`request.service`

    If the request is from another contracted service(i.e. another
    :code:`Insanic` service), request information about the
    requested service is accessible with this attribute.


See Also...
^^^^^^^^^^^^^

- `Django REST Framework`_ Requests documentation.
- `Sanic Requests`_ documentation.
