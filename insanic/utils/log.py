import logging
import sys
import syslog

from sanic.defaultFilter import DefaultFilter
from insanic.conf import settings

LOGGING = {
    'version': 1,
    'filters': {
        'accessFilter': {
            '()': 'insanic.utils.log.DefaultFilter',
            'param': [0, 10, 20]
        },
        'errorFilter': {
            '()': 'insanic.utils.log.DefaultFilter',
            'param': [30, 40, 50]
        },
        'require_debug_false': {
            '()': 'insanic.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'insanic.utils.log.RequireDebugTrue',
        },
    },
    'formatters': {
        'simple': {
            'format': '%(asctime)s - (%(name)s)[%(levelname)s]: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        'access': {
            'format': '%(asctime)s - (%(name)s)[%(levelname)s][%(host)s]: ' +
                      '%(request)s %(message)s %(status)d %(byte)d',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
        "threads": {
            'format': '%(asctime)s - (%(name)s)[%(levelname)s]: %(threadName)10s %(name)18s: %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            # 'filters': ['require_debug_false'],
            'class': 'insanic.log.handlers.AdminEmailHandler'
        },
        'threads_internal': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'threads',
            'stream': sys.stderr
        },
        'internal': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'simple',
            'stream': sys.stderr
        },
        'accessStream': {
            'class': 'logging.StreamHandler',
            'filters': ['accessFilter'],
            'formatter': 'access',
            'stream': sys.stderr
        },
        'errorStream': {
            'class': 'logging.StreamHandler',
            'filters': ['errorFilter'],
            'formatter': 'simple',
            'stream': sys.stderr
        },
        # before you use accessSysLog, be sure that log levels
        # 0, 10, 20 have been enabled in you syslog configuration
        # otherwise you won't be able to see the output in syslog
        # logging file.
        # 'accessSysLog': {
        #     'class': 'logging.handlers.SysLogHandler',
        #     'address': '/var/run/syslog',
        #     'facility': syslog.LOG_DAEMON,
        #     'filters': ['accessFilter'],
        #     'formatter': 'access'
        # },
        # 'errorSysLog': {
        #     'class': 'logging.handlers.SysLogHandler',
        #     'address': '/var/run/syslog',
        #     'facility': syslog.LOG_DAEMON,
        #     'filters': ['errorFilter'],
        #     'formatter': 'simple'
        # },
        'accessTimedRotatingFile': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filters': ['accessFilter'],
            'formatter': 'access',
            'when': 'D',
            'interval': 1,
            'backupCount': 7,
            'filename': '/tmp/access.log'
        },
        'errorTimedRotatingFile': {
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filters': ['errorFilter'],
            'when': 'D',
            'interval': 1,
            'backupCount': 7,
            'filename': '/tmp/error.log',
            'formatter': 'simple'
        }
    },
    'loggers': {
        'sanic': {
            'level': 'DEBUG',
            'handlers': ['internal', 'errorStream']
        },
        'network': {
            'level': 'DEBUG',
            'handlers': ['accessStream', 'errorStream']
        },
        'insanic.request': {
            'include_html': True,
            'level': 'ERROR',
            'handlers': ['mail_admins'],
            'propagate': False,
        },
        "threads": {
            'level': 'DEBUG',
            'handlers': ['threads_internal']
        }
    }
}



class RequireDebugFalse(logging.Filter):
    def filter(self, record):
        return not settings.DEBUG


class RequireDebugTrue(logging.Filter):
    def filter(self, record):
        return settings.DEBUG
