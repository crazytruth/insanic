.. role:: bash(code)
    :language: bash

.. role:: python(code)
    :language: python

Settings
==========

Settings for Insanic differ a lot from sanic's config pattern.
While implementing, I found the need to access the settings
from modules where the sanic application was not accessible.
Thus the settings object in insanic takes a lot from Django's
settings configuration where the settings object is a single
instantiated settings object that can be imported and accessed
anywhere.

In addition to Sanic's config object, where it is usually
instantiated and attached to sanic's application instance,
the settings object in insanic is a lazy loaded while also,
for compatibility with Sanic, is also attached to the
application object (i.e. :code:`app.config`).


Initialization
-----------------

There are a couple ways to initialize settings.  In all methods,
the global settings all gets initialized.


Settings Priority
------------------

#. Sanic's :python:`DEFAULT_CONFIG`.
#. :python:`SANIC_PREFIX` environment variables.
#. Insanic's global_settings (:code:insanic.conf.global_settings)
#. Service configs loaded from :bash:`INSANIC_SETTINGS_MODULE` environment variable
#. :python:`INSANIC_PREFIX` environment variables, without the prefix.


Any settings defined in subsequent steps will replace any
existing values.

For example, if you have :python:`SPEED="fast"` defined in your
settings module and you have :bash:`INSANIC_SPEED=insanely` in your
environment variable, the final value will be 'insanely`.


Simple Configuration
---------------------

Before settings has been initialized. Use this if you don't
have many settings and/or in tests.

.. code-block:: python

    from insanic.conf import settings
    settings.configure(DEBUG=False)


General Configuration
----------------------

Most people will want to load their settings with this method.

Create a :bash:`touch config.py` file to place your settings.

.. code-block:: python

    # in config.py
    # you can replace global configuration values here too
    SPEED = "great"
    # and any other settings for your application


Now when you run your application make sure you have
:bash:`INSANIC_SETTINGS_MODULE=example.config` in your
environment variables.


Usage
-------

.. code-block:: python

    from insanic.conf import settings


This is how the settings should be accessed and should
be available anywhere within your application.

To use defined settings.

.. code-block:: python

    >>> settings.SPEED
    "great"


Loading settings from Environment
-----------------------------------

To load settings from environment variables,
the environment variables must be prefixed
with a prefix. The default prefix is :code:`INSANIC_`.

.. code-block:: bash

    export INSANIC_SPEED="medium"

and to use the settings:

.. code-block:: python

    from insanic.conf import settings

    settings.SPEED
    "medium"


See Also
---------

Take a look at the :doc:`global variables <global_settings>` for a
complete list of global config values used in :code:`Insanic`.
