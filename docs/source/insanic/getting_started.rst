Getting Started
======================

As with Sanic, please have at least version 3.6 of Python before
starting.


1. Installing Insanic
^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    pip install insanic-framework

2. Create a file called `app.py`
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from sanic.response import json
    from insanic import Insanic
    from insanic.conf import settings


    __version__ = "0.1.0.dev0"

    settings.configure()

    app = Insanic("hello", version=__version__)

    @app.route("/")
    async def reply(request):
        return json({"reply": "gotta go insanely fast!"})

    if __name__ == "__main__":
        app.run(host="0.0.0.0", port=8000)


As you can see, usage is very similar to Sanic, but with a couple
differences.

1. Insanic requires you to pass in a :code:`version` argument.
This decision was to enforce versioning when deploying
applications.  We found it especially important in a
distributed system.

This however, can be turned off with the
:code:`ENFORCE_APPLICATION_VERSION` settings. View the
:doc:`settings documentation <settings>` for more information.

2. An Insanic specific :code:`settings` variable that is accessible
anywhere in the application.  Some of you may recognize as something
very similar to Django.  Not only can this
:code:`settings` variable be accessible anywhere in the application,
it is also compatible with Sanic where the same variables
can be accessible through :code:`app.config`.  Please read the
:doc:`settings documentation <settings>` for more
information.


3. Run the server
^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    python app.py

4. Check if it works!
^^^^^^^^^^^^^^^^^^^^^^

Open the address `http://0.0.0.0:8000 <http://0.0.0.0:8000>`_ in your web browser.
You should see the message *gotta go insanely fast!*.

You have a working Insanic server!
