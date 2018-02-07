import logging
import sys

from insanic.conf import settings

LOGGING_CONFIG_DEFAULTS = dict(
    version=1,
    disable_existing_loggers=False,
    loggers={
        "root": {
            "level": "DEBUG",
            "handlers": ["console"]
        },
        "sanic.error": {
            "level": "INFO",
            "handlers": ["error_console"],
            "propagate": True,
            "qualname": "sanic.error"
        },

        "sanic.access": {
            "level": "INFO",
            "handlers": ["access_console"],
            "propagate": True,
            "qualname": "sanic.access"
        }
    },
    handlers={
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": sys.stdout
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": sys.stderr
        },
        "access_console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "stream": sys.stdout
        },
    },
    formatters={
        "generic": {
            "format": "%(asctime)s [%(process)d] [%(levelname)s] %(message)s",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter"
        },
        "access": {
            "format": "%(asctime)s - (%(name)s)[%(levelname)s][%(host)s]: " +
                      "%(request)s %(message)s %(status)d %(byte)d",
            "datefmt": "[%Y-%m-%d %H:%M:%S %z]",
            "class": "logging.Formatter"
        },
        "json": {
            "()": "insanic.log.formatters.JSONFormatter",
            "format": {"level": "%(levelname)s", "hostname": "%(hostname)s", "where": "%(module)s.%(funcName)s",
                       "ts": "%(asctime)s", "method": "%(request)s", "message": "%(message)s",
                       "status": "%(status)d", "size": "%(byte)d", "name": "%(name)s", "thread": "%(thread)s",
                       "process": "%(process)s", "thread_name": "%(threadName)s", "service": "%(service)s",
                       "environment": "%(environment)s", "insanic_version": "%(insanic_version)s",
                       "service_version": "%(service_version)s", "trace_id": "%(ot_trace_id)s",
                       "span_id": "%(ot_span_id)s",
                       "sampled": "%(ot_sampled)s", "request_duration": "%(ot_duration)s",
                       "parent_id": "%(ot_parent_id)s",
                       "exc_text": "%(exc_text)s"},
            'datefmt': '%Y-%m-%dT%H:%M:%S.%%(msecs)d%z'
        }

    }
)

logger = logging.getLogger('root')
error_logger = logging.getLogger('sanic.error')
access_logger = logging.getLogger('sanic.access')

if not settings.IS_DOCKER:
    LOGGING_CONFIG_DEFAULTS['loggers']['root']['level'] = logging.DEBUG
    LOGGING_CONFIG_DEFAULTS['loggers']['sanic.error']['level'] = logging.DEBUG
    LOGGING_CONFIG_DEFAULTS['loggers']['sanic.access']['level'] = logging.DEBUG
    LOGGING_CONFIG_DEFAULTS['handlers']['console']['formatter'] = 'generic'
    LOGGING_CONFIG_DEFAULTS['handlers']['error_console']['formatter'] = 'generic'
    LOGGING_CONFIG_DEFAULTS['handlers']['access_console']['formatter'] = 'access'
