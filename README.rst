.. image:: artwork/insanic200px.png
    :width: 200px
    :alt: Insanic


Insanic
=======

|Build Status| |Documentation Status| |Codecov|

|PyPI pyversions| |PyPI version| |Code style black| |PyPI license|

.. |Build Status| image:: https://img.shields.io/github/workflow/status/crazytruth/insanic/python-package
    :target: https://github.com/crazytruth/insanic/actions?query=workflow%3A%22Python+package%22

.. |Documentation Status| image:: https://readthedocs.org/projects/insanic/badge/?version=latest
    :target: http://insanic.readthedocs.io/?badge=latest

.. |Codecov| image:: https://codecov.io/gh/crazytruth/insanic/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/crazytruth/insanic

.. |PyPI version| image:: https://img.shields.io/pypi/v/insanic
    :target: https://pypi.python.org/pypi/insanic/

.. |PyPI pyversions| image:: https://img.shields.io/pypi/pyversions/insanic
    :target: https://pypi.python.org/pypi/insanic/

.. |PyPI license| image:: https://img.shields.io/github/license/crazytruth/insanic?style=flat-square
    :target: https://pypi.python.org/pypi/insanic/

.. |Code style black| image:: https://img.shields.io/badge/code%20style-black-black
    :target: https://github.com/psf/black

    A microservice framework that extends `sanic`_.

Insanic is a pretty opinionated framework.  It tries to include all the best practices for
developing in a microservice architecture.  To do this, certain technologies needed to be used.

Think of this as django-rest-framework is to django but for microservice usage (and a lot less functionality than drf).

Why we needed this
------------------

We needed this because we need a framework for our developers to quickly develop services
while migrating to a microservice architecture.

As stated before, this is very opinionated and the reason being, to reduce research time when
trying to select packages to use for their service.  It lays down all the necessary patterns and
bootstraps the application for quick cycle time between idea and deployment.

FEATURES
---------

- Authentication and Authorization for Users and other Services (like drf)
- Easy Service Requests
- Normalized Error Message Formats
- Connection manager to redis
- Utils for extracting public routes (will help when registering to api gateway)
- Bootstrap monitoring endpoints
- Throttling

Documentation
--------------

For more detailed information please refer to the `documentation`_

Installation
------------

Prerequisites
^^^^^^^^^^^^^

Core dependencies include:

- `sanic`_ - extends sanic
- `httpx`_ - to make async requests to other services
- `PyJWT`_ - for authentication
- `Redis`_ - for cache and throttling

To install:

.. code-block::

    $ pip install insanic

.. _sanic: https://github.com/huge-success/sanic
.. _httpx: https://github.com/encode/httpx
.. _PyJWT: https://github.com/jpadilla/pyjwt/
.. _Redis: https://redis.io/


Usage
-----

For very basic usage, it is pretty much the same as Sanic:

1. Create a python file. ex. `app.py`

.. code-block:: python

    from insanic import Insanic
    from insanic.conf import settings
    from sanic.response import json

    settings.configure()
    __version__ = "0.1.0"

    app = Insanic(__name__, version=__version__)

    @app.route('/')
    async def example(request):
        return json({"insanic": "Gotta go insanely fast!"})

    if __name__ == '__main__':
        app.run(host='0.0.0.0', port=8000)



2. Run with

.. code-block::

    python run.py


3. Check in browser or `curl`

.. code-block::

    curl http://localhost:8000/


For more examples and usage, please refer to the `documentation`_.

Testing
-------

Insanic tests are run with pytest and tox.

.. code-block::

    $ pytest

    # with coverage
    $ pytest --cov=insanic --cov-report term-missing:skip-covered

    # a certain set of tests
    $ pytest --pytest-args tests/test_pact.py

    # tox, run for sanic > 19.12 and python >= 3.6
    $ tox


Release History
---------------

For full changelogs, please refer to the `CHANGELOG.rst <CHANGELOG.rst>`_.

Since Insanic was initially developed and released internally,
for changes made during that period, please refer to
`CHANGELOG_LEGACY.rst <CHANGELOG_LEGACY.rst>`_.

Contributing
-------------

For guidance on setting up a development environment and
how to make a contribution to Insanic,
see the `CONTRIBUTING.rst <CONTRIBUTING.rst>`_ guidelines.


Known Issues
-------------

-   Insanic cannot run with more than 1 worker.


Meta
----

Distributed under the MIT license. See `LICENSE <LICENSE>`_ for more information.

Thanks to all the people at my prior company that worked with me to make this possible.

Links
-----

- Documentation: https://readthedocs.org/
- Releases: https://pypi.org/project/insanic/
- Code: https://www.github.com/crazytruth/insanic/
- Issue Tracker: https://www.github.com/crazytruth/insanic/issues
- Sanic Documentation: https://sanic.readthedocs.io/en/latest/index.html
- Sanic Repository: https://github.com/huge-success/sanic

.. _documentation: https://readthedocs.org/
