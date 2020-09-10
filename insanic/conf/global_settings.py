from typing import Optional, Tuple, List, Dict

SERVICE_ALIAS: str = ""
SERVICE_TOKEN_KEY: str = ""

ADMINS: Tuple[tuple] = (("David", "kwangjinkim@gmail.com"),)

DEBUG: bool = False
APPLICATION_VERSION: Optional[str] = None
ENFORCE_APPLICATION_VERSION: bool = True

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
KEEP_ALIVE_TIMEOUT: int = 60

GRACEFUL_SHUTDOWN_TIMEOUT: float = 29.0  # sanic default is 15.0s

# SERVICE_NAME = None

SERVICE_CONNECTIONS: List[str] = []
REQUIRED_SERVICE_CONNECTIONS: List[str] = []

SERVICE_GLOBAL_SCHEMA: str = "http"
SERVICE_GLOBAL_HOST_TEMPLATE: str = "{}"
SERVICE_GLOBAL_PORT: str = "8000"

# httpx configs - start
SERVICE_CONNECTOR_MAX: int = 100
SERVICE_CONNECTOR_MAX_KEEPALIVE: int = 20
SERVICE_TIMEOUT_TOTAL: float = 5.0
# SERVICE_TIMEOUT_CONNECT = None
# SERVICE_TIMEOUT_READ = None
# SERVICE_TIMEOUT_WRITE = None
# SERVICE_TIMEOUT_POOL = None
# httpx configs - end

SERVICE_CONNECTION_DEFAULT_RETRY_COUNT: int = 2
SERVICE_CONNECTION_MAX_RETRY_COUNT: int = 4

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

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

TASK_CONTEXT_REQUEST_USER: str = "request_user"
TASK_CONTEXT_CORRELATION_ID: str = "correlation_id"

JWT_AUTH_DECODE_HANDLER: str = "insanic.authentication.handlers.jwt_decode_handler"

JWT_AUTH_ALGORITHM: str = "HS256"
JWT_AUTH_PUBLIC_KEY: Optional[str] = None
JWT_AUTH_PRIVATE_KEY: Optional[str] = None

JWT_AUTH_VERIFY: bool = False
JWT_AUTH_VERIFY_EXPIRATION: bool = True  #
JWT_AUTH_LEEWAY: int = 0

JWT_AUTH_AUDIENCE: str = ""
JWT_AUTH_AUTH_HEADER_PREFIX: str = "Bearer"

JWT_SERVICE_AUTH_ALGORITHM: str = "HS256"
JWT_SERVICE_AUTH_ROLE: str = "service"
JWT_SERVICE_AUTH_AUTH_HEADER_PREFIX: str = "MSA"
JWT_SERVICE_AUTH_VERIFY: bool = True

THROTTLES_DEFAULT_THROTTLE_RATES: Dict[str, Optional[str]] = {
    "user": None,
    "anon": None,
}

REQUEST_ID_HEADER_FIELD: str = "X-Insanic-Request-ID"
INTERNAL_REQUEST_USER_HEADER: str = "x-insanic-request-user"
INTERNAL_REQUEST_SERVICE_HEADER: str = "x-insanic-request-service"

SERVICE_UNAVAILABLE_MESSAGE: str = "{} is currently unavailable."

REQUIRED_PLUGINS: Tuple[str] = ()
