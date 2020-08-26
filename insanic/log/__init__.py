import os

import logging
import queue
import sys

from functools import lru_cache


@lru_cache(maxsize=1)
def get_log_level():
    from insanic.scopes import is_docker

    return os.environ.get("INSANIC_LOG_LEVEL", "INFO" if is_docker else "DEBUG")


@lru_cache(maxsize=1)
def get_access_log_level():
    return os.environ.get("INSANIC_ACCESS_LOG_LEVEL", "INFO")


@lru_cache(maxsize=10)
def get_log_queue(name=None):
    return queue.Queue(maxsize=-1)


def get_logging_config():
    log_level = get_log_level()
    from insanic.scopes import is_docker

    LOGGING_CONFIG_DEFAULTS = dict(
        version=1,
        disable_existing_loggers=False,
        loggers={
            "root": {"level": log_level, "handlers": ["console"]},
            "sanic.error": {
                "level": log_level,
                "handlers": ["error_console"],
                "propagate": True,
                "qualname": "sanic.error",
            },
            "sanic.access": {
                "level": get_access_log_level(),
                # "handlers": ["queue_listener"],
                "handlers": ["access_console"],
                "propagate": True,
                "qualname": "sanic.access",
            },
        },
        handlers={
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": sys.stdout,
            },
            "error_console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": sys.stderr,
            },
            "access_console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "stream": sys.stdout,
            },
            # "queue_listener": {
            #     "class": "insanic.log.handlers.QueueListenerHandler",
            #     "formatter": "json",
            #     "handlers": [
            #         "cfg://handlers.access_console",
            #     ],
            #     "queue": get_log_queue()
            # }
        },
        formatters={
            "generic": {
                "format": "%(asctime)s [%(process)d] [%(levelname)s] %(message)s",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
            "access": {
                "format": "%(asctime)s - (%(name)s)[%(levelname)s][%(host)s]: "
                "%(request)s %(message)s %(status)d %(byte)d",
                "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
                "class": "logging.Formatter",
            },
            "json": {
                "()": "insanic.log.formatters.JSONFormatter",
                "format": {
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
                    "service_version": "%(service_version)s",
                    "trace_id": "%(ot_trace_id)s",
                    "span_id": "%(ot_span_id)s",
                    "sampled": "%(ot_sampled)s",
                    "request_duration": "%(request_duration)s",
                    "parent_id": "%(ot_parent_id)s",
                    "correlation_id": "%(correlation_id)s",
                    "exc_text": "%(exc_text)s",
                    "request_service": "%(request_service)s",
                    # added in 0.6.8
                    "error_code_name": "%(error_code_name)s",
                    "error_code_value": "%(error_code_value)s",
                    "method": "%(method)s",
                    "path": "%(path)s",
                    "uri_template": "%(uri_template)s",
                    # added in 0.8.0
                    "squad": "%(squad)s",
                },
                "datefmt": "%Y-%m-%dT%H:%M:%S.%%(msecs)d%z",
            },
        },
    )

    if not is_docker or os.getenv("LOG_TYPE", "json") == "access":
        LOGGING_CONFIG_DEFAULTS["handlers"]["console"]["formatter"] = "generic"
        LOGGING_CONFIG_DEFAULTS["handlers"]["error_console"][
            "formatter"
        ] = "generic"
        LOGGING_CONFIG_DEFAULTS["handlers"]["access_console"][
            "formatter"
        ] = "access"
        # LOGGING_CONFIG_DEFAULTS['handlers']['queue_listener']['formatter'] = 'access'

    return LOGGING_CONFIG_DEFAULTS


logger = logging.getLogger("root")
error_logger = logging.getLogger("sanic.error")
access_logger = logging.getLogger("sanic.access")
