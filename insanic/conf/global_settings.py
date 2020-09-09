import datetime

SERVICE_ALIAS = ""
SERVICE_TOKEN_KEY = ""

ADMINS = ("David", "kwangjinkim@gmail.com")

DEBUG = False
APPLICATION_VERSION = None
ENFORCE_APPLICATION_VERSION = True

# sanic default configs
# DEFAULT_CONFIG = {
#     "REQUEST_MAX_SIZE": 100000000,  # 100 megabytes
#     "REQUEST_BUFFER_QUEUE_SIZE": 100,
#     "REQUEST_TIMEOUT": 60,  # 60 seconds
#     "RESPONSE_TIMEOUT": 60,  # 60 seconds
#     "KEEP_ALIVE": True,
#     "KEEP_ALIVE_TIMEOUT": 5,  # 5 seconds
#     "WEBSOCKET_MAX_SIZE": 2 ** 20,  # 1 megabytes
#     "WEBSOCKET_MAX_QUEUE": 32,
#     "WEBSOCKET_READ_LIMIT": 2 ** 16,
#     "WEBSOCKET_WRITE_LIMIT": 2 ** 16,
#     "GRACEFUL_SHUTDOWN_TIMEOUT": 15.0,  # 15 sec
#     "ACCESS_LOG": True,
#     "PROXIES_COUNT": -1,
#     "FORWARDED_FOR_HEADER": "X-Forwarded-For",
#     "REAL_IP_HEADER": "X-Real-IP",
# }
KEEP_ALIVE_TIMEOUT = 60

GRACEFUL_SHUTDOWN_TIMEOUT = 29.0  # sanic default is 15.0s

# SERVICE_NAME = None

SERVICE_CONNECTIONS = []
REQUIRED_SERVICE_CONNECTIONS = []

SERVICE_GLOBAL_SCHEMA = "http"
SERVICE_GLOBAL_HOST_TEMPLATE = "{}"
SERVICE_GLOBAL_PORT = "8000"

# httpx configs - start
SERVICE_CONNECTOR_MAX = 100
SERVICE_CONNECTOR_MAX_KEEPALIVE = 20
SERVICE_TIMEOUT_TOTAL = 5.0
# SERVICE_TIMEOUT_CONNECT = None
# SERVICE_TIMEOUT_READ = None
# SERVICE_TIMEOUT_WRITE = None
# SERVICE_TIMEOUT_POOL = None
# httpx configs - end

SERVICE_CONNECTION_DEFAULT_RETRY_COUNT = 2
SERVICE_CONNECTION_MAX_RETRY_COUNT = 4

INSANIC_CACHES = {
    "insanic": {
        "ENGINE": "aioredis",
        "CONNECTION_INTERFACE": "create_redis_pool",
        "CLOSE_CONNECTION_INTERFACE": (("close",), ("wait_closed",)),
        "DATABASE": 1,
    },
    "throttle": {
        "ENGINE": "aioredis",
        "CONNECTION_INTERFACE": "create_redis_pool",
        "CLOSE_CONNECTION_INTERFACE": (("close",), ("wait_closed",)),
        "DATABASE": 2,
    },
}

CACHES = {
    "default": {
        "ENGINE": "aioredis",
        "CONNECTION_INTERFACE": "create_redis_pool",
        "CLOSE_CONNECTION_INTERFACE": (("close",), ("wait_closed",)),
    },
}

TASK_CONTEXT_REQUEST_USER = "request_user"
TASK_CONTEXT_CORRELATION_ID = "correlation_id"

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

JWT_AUTH = {
    "JWT_ENCODE_HANDLER": "rest_framework_jwt.utils.jwt_encode_handler",
    "JWT_DECODE_HANDLER": "rest_framework_jwt.utils.jwt_decode_handler",
    "JWT_PAYLOAD_HANDLER": "rest_framework_jwt.utils.jwt_payload_handler",
    "JWT_PAYLOAD_GET_USER_ID_HANDLER": "rest_framework_jwt.utils.jwt_get_user_id_from_payload_handler",
    "JWT_RESPONSE_PAYLOAD_HANDLER": "rest_framework_jwt.utils.jwt_response_payload_handler",
    "JWT_PUBLIC_KEY": None,
    "JWT_PRIVATE_KEY": None,
    "JWT_ALGORITHM": "HS256",
    "JWT_VERIFY": False,
    "JWT_VERIFY_EXPIRATION": True,
    "JWT_LEEWAY": 0,
    "JWT_EXPIRATION_DELTA": datetime.timedelta(days=7),
    "JWT_AUDIENCE": "",
    "JWT_ISSUER": "",
    "JWT_ALLOW_REFRESH": True,
    "JWT_REFRESH_EXPIRATION_DELTA": datetime.timedelta(days=7),
    "JWT_ROLE": "user",
    "JWT_AUTH_HEADER_PREFIX": "Bearer",
}

JWT_SERVICE_AUTH = {
    "JWT_ALGORITHM": "HS256",
    "JWT_ROLE": "service",
    "JWT_AUTH_HEADER_PREFIX": "MSA",
    "JWT_VERIFY": True,
}

# THROTTLES_NUM_PROXIES = None # deprecated
THROTTLES_DEFAULT_THROTTLE_RATES = {"user": None, "anon": None}

REQUEST_ID_HEADER_FIELD = "X-Insanic-Request-ID"
INTERNAL_REQUEST_USER_HEADER = "x-insanic-request-user"
INTERNAL_REQUEST_SERVICE_HEADER = "x-insanic-request-service"

SERVICE_UNAVAILABLE_MESSAGE = "{} is currently unavailable."

REQUIRED_PLUGINS = ()
