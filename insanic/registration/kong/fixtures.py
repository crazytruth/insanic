from insanic.functional import empty

SERVICE_OBJECT = {

}

UPSTREAM_OBJECT = {
    "name": empty,
    "healthchecks": {
        "active": {
            "timeout": 1,
            "concurrency": 10,
            "http_path": empty,
            "healthy": {
                "interval": 30,
                "http_statuses": [],
                "successes": 3
            },
            "unhealthy": {
                "interval": 5,
                "http_statuses": [429, 404, 500, 501, 502, 503, 504, 505],
                "tcp_failures": 3,  # Number of TCP failures in active probes to consider a target unhealthy.
                "timeouts": 3,  # Number of timeouts in active probes to consider a target unhealthy.
                "http_failures": 2
            }
        },
        "passive": {
            "healthy": {
                "http_statuses": [200, 201, 202, 203, 204, 205, 206, 207, 208, 226, 300, 301, 302, 303, 304, 305, 306,
                                  307, 408],
                "successes": 0
            },
            "unhealthy": {
                "http_statuses": [404],
                "tcp_failures": 3,
                "timeouts": 3,
                "http_failures": 0
            }
        }
    }
}
