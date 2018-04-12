import datetime

SECRET_KEY = ''
SERVICE_TOKEN_KEY = ""

ADMINS = (
    ('David', 'david@mymusictaste.com')
)

DEBUG = False

SERVICE_NAME = None

SERVICE_CONNECTIONS = []

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
    'JWT_VERIFY': True,
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LEEWAY': 0,
    'JWT_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_AUDIENCE': '.mymusictaste.com',
    'JWT_ISSUER': 'mymusictaste.com',

    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_ROLE': 'user',

    'JWT_AUTH_HEADER_PREFIX': 'MMT',
}

JWT_SERVICE_AUTH = {
    'JWT_ALGORITHM': 'HS256',
    'JWT_ROLE': 'service',
    'JWT_AUTH_HEADER_PREFIX': 'MSA',
    'JWT_VERIFY': True,
}

INTERNAL_IPS = ()

TRACING = dict(
    ENABLED=True,
    HOST='xray',
    PORT=2000,
    FAIL_SOFT_ENVIRONMENTS=('local', 'test', "development"),
    REQUIRED=True,
)

DEFAULT_SAMPLING_FIXED_TARGET = 30
DEFAULT_SAMPLING_RATE = 0.05

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

# VAULT_APPROLE_BIND_SECRET = "pull" # value can be pull or push
