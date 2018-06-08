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
                "http_statuses": empty,
                "successes": 3
            },
            "unhealthy": {
                "interval": 5,
                "http_statuses": [
                ],
                "tcp_failures": 3,  # Number of TCP failures in active probes to consider a target unhealthy.
                "timeouts": 1,  # Number of timeouts in active probes to consider a target unhealthy.
                "http_failures": 0
            }
        },
        "passive": {
            "healthy": {
                "http_statuses": [],
                "successes": 0
            },
            "unhealthy": {
                "http_statuses": [],
                "tcp_failures": 3,
                "timeouts": 3,
                "http_failures": 0
            }
        }
    }
}
