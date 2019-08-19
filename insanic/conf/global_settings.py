import datetime

SECRET_KEY = ''
SERVICE_TOKEN_KEY = ""

ADMINS = (
    ('David', 'david@mymusictaste.com')
)

DEBUG = False

# SERVICE_NAME = None

SERVICE_CONNECTIONS = []
SERVICE_GLOBAL_SCHEMA = "http"
SERVICE_GLOBAL_HOST_TEMPLATE = "{}"
SERVICE_GLOBAL_PORT = "8000"
SERVICE_CONNECTION_KEEP_ALIVE_TIMEOUT = 15

REQUIRED_SERVICE_CONNECTIONS = ["userip", "user"]
ALLOWED_HOSTS = []

LOG_IP_FAIL_TYPE = "hard"

INFUSE_ENABLED = 0
INFUSE_FAIL_TYPE = "soft"  # | "hard"

INSANIC_CACHES = {
    "insanic": {
        "ENGINE": "aioredis",
        "CONNECTION_INTERFACE": "create_redis_pool",
        "CLOSE_CONNECTION_INTERFACE": (('close',), ("wait_closed",)),
        "DATABASE": 1
    },
    "throttle": {
        "ENGINE": "aioredis",
        "CONNECTION_INTERFACE": "create_redis_pool",
        "CLOSE_CONNECTION_INTERFACE": (('close',), ("wait_closed",)),
        "DATABASE": 2
    },
}

CACHES = {
    "default": {
        "ENGINE": "aioredis",
        "CONNECTION_INTERFACE": "create_redis_pool",
        "CLOSE_CONNECTION_INTERFACE": (('close',), ("wait_closed",))
    },
}

TASK_CONTEXT_REQUEST_USER = "request_user"
TASK_CONTEXT_CORRELATION_ID = "correlation_id"

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

JWT_AUTH = {
    'JWT_ENCODE_HANDLER':
        'rest_framework_jwt.utils.jwt_encode_handler',

    'JWT_DECODE_HANDLER':
        'rest_framework_jwt.utils.jwt_decode_handler',

    'JWT_PAYLOAD_HANDLER':
        'rest_framework_jwt.utils.jwt_payload_handler',

    'JWT_PAYLOAD_GET_USER_ID_HANDLER':
        'rest_framework_jwt.utils.jwt_get_user_id_from_payload_handler',

    'JWT_RESPONSE_PAYLOAD_HANDLER':
        'rest_framework_jwt.utils.jwt_response_payload_handler',

    'JWT_PUBLIC_KEY': None,
    'JWT_PRIVATE_KEY': None,
    'JWT_ALGORITHM': 'HS256',
    'JWT_VERIFY': False,
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LEEWAY': 0,
    'JWT_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_AUDIENCE': '.mymusictaste.com',
    'JWT_ISSUER': 'mymusictaste.com',

    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_ROLE': 'user',

    'JWT_AUTH_HEADER_PREFIX': 'Bearer',
}

JWT_SERVICE_AUTH = {
    'JWT_ALGORITHM': 'HS256',
    'JWT_ROLE': 'service',
    'JWT_AUTH_HEADER_PREFIX': 'MSA',
    'JWT_VERIFY': True,
}

INTERNAL_IPS = ()



# THROTTLES_NUM_PROXIES = None # deprecated
THROTTLES_DEFAULT_THROTTLE_RATES = {
    'user': None,
    'anon': None
}

PROXIES_COUNT = -1
FORWARDED_FOR_HEADER = "X-Forwarded-For"
REAL_IP_HEADER = "X-Real-IP"


GATEWAY_REGISTRATION_ENABLED = True

KONG_HOST = "kong"
KONG_ADMIN_PORT = 18001

KONG_ROUTE_REGEX_PRIORITY = {"local": 10,
                             "development": 5}
KONG_ROUTE_REGEX_DEFAULT = 10
KONG_FAIL_SOFT_ENVIRONMENTS = ("local", "test",)

KONG_PLUGIN = {"JSONWebTokenAuthentication": "jwt",
               "HardJSONWebTokenAuthentication": "jwt", }

# VAULT_APPROLE_BIND_SECRET = "pull" # value can be pull or push
REQUEST_ID_HEADER_FIELD = "X-Insanic-Request-ID"
INTERNAL_REQUEST_USER_HEADER = 'x-insanic-request-user'

SERVICE_UNAVAILABLE_MESSAGE = "{} is currently unavailable."
