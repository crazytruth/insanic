import datetime

SECRET_KEY = ''
SERVICE_TOKEN_KEY = ""

ADMINS = (
    ('David', 'david@mymusictaste.com')
)

DEBUG = False

SERVICE_NAME = None

SERVICE_CONNECTIONS = []
SERVICE_GLOBAL_SCHEMA = "http"
SERVICE_GLOBAL_HOST_TEMPLATE = "{}"
SERVICE_GLOBAL_PORT = "8000"

REQUIRED_SERVICE_CONNECTIONS = ["userip"]
ALLOWED_HOSTS = []

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

TRACING_HOST = 'xray'
TRACING_PORT = 2000
TRACING_ENABLED = True
TRACING_REQUIRED = True
TRACING_SOFT_FAIL = True
TRACING_CONTEXT_MISSING_STRATEGY = "LOG_ERROR"  # or "RUNTIME_ERROR"

DEFAULT_SAMPLING_FIXED_TARGET = 60 * 10
DEFAULT_SAMPLING_RATE = 0.01

SAMPLING_RULES = {
    "version": 1,
    "rules": [
        # {
        #     "description": "Player moves.",
        #     "service_name": "*",
        #     "http_method": "*",
        #     "url_path": "/api/move/*",
        #     "fixed_target": 0,
        #     "rate": 0.05
        # }
    ],
    "default": {
        "fixed_target": DEFAULT_SAMPLING_FIXED_TARGET,
        "rate": DEFAULT_SAMPLING_RATE
    }
}

THROTTLES = {
    "NUM_PROXIES": None,
    "DEFAULT_THROTTLE_RATES": {
        'user': None,
        'anon': None,
    },
}

GATEWAY_REGISTRATION_ENABLED = True

KONG_HOST = "kong"
KONG_ADMIN_PORT = 18000

KONG_ROUTE_REGEX_PRIORITY = {"local": 10,
                             "development": 5}
KONG_ROUTE_REGEX_DEFAULT = 10
KONG_FAIL_SOFT_ENVIRONMENTS = ("local", "test",)

KONG_PLUGIN = {"JSONWebTokenAuthentication": "jwt",}

# VAULT_APPROLE_BIND_SECRET = "pull" # value can be pull or push


PACT_BROKER_URL = 'http://pact'
SERVICE_UNAVAILABLE_MESSAGE = "{} is currently unavailable."