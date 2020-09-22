Insanic Logging
=================

Insanic provides the same loggers as Sanic so please review
`Sanic's Logging Documentation <https://sanic.readthedocs.io/en/latest/sanic/logging.html>`_.

However, there are a few differences.

1. :code:`JSONFormatter` for JSON output.

This is mainly for sending log messages to
external log aggregation stacks or services.

If you need the JSON formatted logs, set
:code:`LOG_TYPE=json` in your environment.

2. Much more verbose JSON output.

Default JSON output is:

.. code-block:: json

    {
        "level": "%(levelname)s",
        "hostname": "%(hostname)s",
        "where": "%(module)s.%(funcName)s",
        "ts": "%(asctime)s",
        "request": "%(request)s",
        "message": "%(message)s",
        "status": "%(status)d",
        "size": "%(byte)d",
        "name": "%(name)s",
        "thread": "%(thread)s",
        "process": "%(process)s",
        "thread_name": "%(threadName)s",
        "service": "%(service)s",
        "environment": "%(environment)s",
        "insanic_version": "%(insanic_version)s",
        "application_version": "%(application_version)s",
        "request_duration": "%(request_duration)s",
        "correlation_id": "%(correlation_id)s",
        "exc_text": "%(exc_text)s",
        "request_service": "%(request_service)s",
        "error_code_name": "%(error_code_name)s",
        "error_code_value": "%(error_code_value)s",
        "method": "%(method)s",
        "path": "%(path)s",
        "uri_template": "%(uri_template)s",
    }

3. Control Log Levels with environment variables

The :code:`root` and :code:`sanic.error` loggers are
configurable with the :code:`INSANIC_LOG_LEVEL` environment variable.
Default is :code:`INFO`.

Also, the log level for :code:`sanic.access` can be configured
with the :code:`INSANIC_ACCESS_LOG_LEVEL` environment variable.
Default is also :code:`INFO`.
