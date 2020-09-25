from typing import Optional, Tuple, List, Dict

#: Not required but give your service an alias
SERVICE_ALIAS: str = ""

#
SERVICE_TOKEN_KEY: str = ""

#: A list of the maintainers of your service.
ADMINS: Tuple[tuple] = (("David", "david@example.com"),)

#: Whether to run in debug mode or not
DEBUG: bool = False

#: Current environment application is deployed to
ENVIRONMENT: str = "development"

#: The application version is set here.
APPLICATION_VERSION: Optional[str] = None

#: Whether to enforce application versioning
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

#: Replace Sanic's default value to 60
KEEP_ALIVE_TIMEOUT: int = 60

#: Replace Sanic's default value of 15s to 29s
GRACEFUL_SHUTDOWN_TIMEOUT: float = 29.0  # sanic default is 15.0s

#: List is connections this application will have connections to.
SERVICE_CONNECTIONS: List[str] = []

#: A list of required connections.
REQUIRED_SERVICE_CONNECTIONS: List[str] = []

#: Schema for constructing the url for intra service communications.
SERVICE_GLOBAL_SCHEMA: str = "http"

#: Host template for constructing the url for intra service communications
SERVICE_GLOBAL_HOST_TEMPLATE: str = "{}"

#: Port for constructing the url for intra service communications
SERVICE_GLOBAL_PORT: str = "8000"

# httpx configs - start
#: httpx config for number of connections
SERVICE_CONNECTOR_MAX: int = 100
#: httpx config for keep alive
SERVICE_CONNECTOR_MAX_KEEPALIVE: int = 20

#: httpx config for timeout
SERVICE_TIMEOUT_TOTAL: float = 5.0
# SERVICE_TIMEOUT_CONNECT: float = None
# SERVICE_TIMEOUT_READ: float = None
# SERVICE_TIMEOUT_WRITE: float = None
# SERVICE_TIMEOUT_POOL: float = None
# httpx configs - end

#: number of retries the Service object will attempt the GET request
SERVICE_CONNECTION_DEFAULT_RETRY_COUNT: int = 2
#: the hard maximum for retries
SERVICE_CONNECTION_MAX_RETRY_COUNT: int = 4

#: Redis host, port, and db cache settings
INSANIC_CACHES: Dict[str, dict] = {
    "insanic": {"HOST": "localhost", "PORT": 6379, "DATABASE": 1},
    "throttle": {"HOST": "localhost", "PORT": 6379, "DATABASE": 2},
}

#: Any other host, port and db redis connections
CACHES: Dict[str, dict] = {
    "default": {"HOST": "localhost", "PORT": 6379, "DATABASE": 0},
}

#: the key for the asyncio task context that hold user information.
TASK_CONTEXT_REQUEST_USER: str = "request_user"
#: the key for the asyncio task context that holds the correlation id
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

#: Throttle values for setting throttles in views.
THROTTLES_DEFAULT_THROTTLE_RATES: Dict[str, Optional[str]] = {
    "user": None,
    "anon": None,
}

#: Header key for setting the request id during intra service requests
REQUEST_ID_HEADER_FIELD: str = "X-Insanic-Request-ID"
#: Header key for setting request user context in intra service requests
INTERNAL_REQUEST_USER_HEADER: str = "x-insanic-request-user"
#: Header key for setting request service context during intra service requests
INTERNAL_REQUEST_SERVICE_HEADER: str = "x-insanic-request-service"

SERVICE_UNAVAILABLE_MESSAGE: str = "{} is currently unavailable."

#: if there should be any required plugins when running Insanic
REQUIRED_PLUGINS: Tuple[str] = ()
