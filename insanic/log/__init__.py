import os
import sys

from sanic.config import LOGGING
from sanic.log import log, netlog

LOGGING.update({"disable_existing_loggers": False})
LOGGING['formatters']['json'] = {
    "()": "insanic.log.formatters.JSONFormatter",
    "format": {"level": "%(levelname)s", "hostname": "%(hostname)s", "where": "%(module)s.%(funcName)s",
               "ts": "%(asctime)s", "method": "%(request)s", "message": "%(message)s",
              "status": "%(status)d", "size": "%(byte)d", "name": "%(name)s", "thread": "%(thread)s",
               "process": "%(process)s", "thread_name": "%(threadName)s", "service": "%(service)s",
               "environment": "%(environment)s", "insanic_version": "%(insanic_version)s",
               "service_version": "%(service_version)s", "trace_id": "%(ot_trace_id)s", "span_id": "%(ot_span_id)s",
               "sampled": "%(ot_sampled)s", "request_duration": "%(ot_duration)s", "parent_id": "%(ot_parent_id)s",},
    'datefmt': '%Y-%m-%dT%H:%M:%S.%%(msecs)d%z'
}

if os.environ.get('MMT_ENV') != "local":

    LOGGING['handlers']['accessStream']['formatter'] = 'json'
    LOGGING['handlers']['accessStream']['stream'] = sys.stdout
    LOGGING['handlers']['errorStream']['formatter'] = 'json'
# "format"=>"%Y-%m-%dT%H:%M:%S.%N%z", "value"=>"2017-07-27T08:58:16+0000"
# LOGGING = {
#     'version': 1,
#     'disable_existing_loggers': False,
#     'formatters': {
#         # 'simple': {
#         #     'format': '%(asctime)s - (%(name)s)[%(levelname)s]: %(message)s',
#         #     'datefmt': '%Y-%m-%d %H:%M:%S'
#         # },
#         # 'access': {
#         #     'format': '%(asctime)s - (%(name)s)[%(levelname)s][%(host)s]: ' +
#         #               '%(request)s %(message)s %(status)d %(byte)d',
#         #     'datefmt': '%Y-%m-%d %H:%M:%S'
#         # },
#         "json": {
#             "format": {
#                 "level": "%(levelname)s",
#                 "hostname": "%(hostname)s",
#                 "where": "%(module)s.%(funcName)s",
#                 "timestamp": '%(asctime)s',
#                 "host": "%(host)s",
#                 "method": "%(request)s",
#                 "message": "%(message)s",
#                 "status": "%(status)d",
#                 "size": "%(byte)d"
#             },
#             'datefmt': '%Y-%m-%d %H:%M:%S.%f'
#         }
#     },
#     'handlers': {
#         'mail_admins': {
#             'level': 'ERROR',
#             # 'filters': ['require_debug_false'],
#             'class': 'insanic.log.handlers.AdminEmailHandler'
#         },
#         'accessStream': {
#             'class': 'logging.StreamHandler',
#             'filters': ['accessFilter'],
#             'formatter': 'json',
#             'stream': sys.stderr
#         },
#         'errorStream': {
#             'class': 'logging.StreamHandler',
#             'filters': ['errorFilter'],
#             'formatter': 'json',
#             'stream': sys.stderr
#         },
#     },
#     'loggers': {
#         'network': {
#             'level': 'DEBUG',
#             'handlers': ['accessStream', 'errorStream'],
#         },
#
#     }
# }
