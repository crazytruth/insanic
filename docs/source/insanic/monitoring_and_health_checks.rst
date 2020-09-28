Monitoring Insanic
===================

Insanic provides several default endpoints when you
run your application.  These are to help with general
health checks, metrics, and to ping intra service communications.

Health Endpoint
----------------

The health endpoint is served from
:code:`/<your_service_name>/health/`.  This provides basic
information about the service that is running.

If we have this application...

.. code-block:: python

    from insanic import Insanic
    from insanic.conf import settings

    __version__ = '0.1.1'

    settings.configure()
    app = Insanic('example', version=__version__)


And if we run and curl...

.. code-block:: bash

    $ curl http://localhost:8000/example/health/
    {
        "service":"example",
        "application_version":"0.1.0",
        "status":"OK",
        "insanic_version":"0.8.4.dev0",
        "ip":"172.20.10.10"
    } # formatted for readability


Metrics Endpoint
-----------------

The metrics endpoint is served from :code:`/<your service name>/metrics/`.
This endpoint is provide basic metrics of the application and
machine/container that it is running in.  This is because transparent
application metrics are very important in a distributed
system.

This endpoint provides information for the following metrics.

- Total asyncio Task Count
- Active asyncio Task Count
- Memory Usage/Percentage
- CPU Usage
- Processed Request Count

And the endpoint provides these metrics in 2 formats.

- JSON
- `Prometheus <https://prometheus.io/>`_

With our example application from above...

.. code-block:: bash

    $ curl http://localhost:8000/example/metrics/
    # HELP python_gc_collected_objects Objects collected during gc
    # TYPE python_gc_collected_objects histogram
    python_gc_collected_objects_bucket{generation="0",le="500.0"} 16.0

    ... truncated for brevity

    # HELP service_info Meta data about this instance.
    # TYPE service_info gauge
    service_info{application_version="0.1.0",insanic_version="0.8.4.dev0",ip="172.20.10.10",service="example",status="OK"} 1.0

    $ curl http://localhost:8000/example/metrics/?json
    {
        "total_task_count":1,
        "active_task_count":1,
        "request_count":6.0,
        "proc_rss_mem_bytes":13205504.0,
        "proc_rss_mem_perc":0.15382766723632812,
        "proc_cpu_perc":0.0,
        "timestamp":1600700128.8033018
    } # formatted for readability


Ping Endpoint
--------------

The ping endpoint is served from :code:`/<your service name>/ping/`.

This endpoint pings the service and provides request process duration
metrics for the respective service (usually 0ms).  However,
its real power lies in its ability to ping other services.

A call to the endpoint gathers the services defined in
the :code:`SERVICE_CONNECTIONS` and :code:`REQUIRED_SERVICE_CONNECTIONS`
settings and also sends a :code:`ping` request
to all of them.  Depth can be set to determine how far in the
mesh you want to traverse with the :code:`depth` query parameter.

This *could* be useful for creating a trace diagram of which
service talks to who, if you have some sort of tracing stack.

.. warning::

    Requests with a large :code:`depth` value should be avoided
    in a production environment as it could quickly flood the
    network. Especially if you have circular connections.


Again, with our example application above...

.. code-block:: bash

    $ curl http://localhost:8000/example/ping/
    {"response":"pong","process_time":"0 ms"}
    $ curl http://localhost:8000/example/ping/?depth=1


If you don't need these endpoints
----------------------------------

If you don't need these, you can turn them off by sending an
argument to Insanic on initialization.

.. code-block:: python

    app = Insanic(
        "nomonitor",
        version='0.0.0',
        attach_monitor_endpoints=False
    )
