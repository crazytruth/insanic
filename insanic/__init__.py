from sanic import Sanic
from sanic_useragent import SanicUserAgent

try:
    import config
except ImportError:
    config = {}

try:
    import instance
except ImportError:
    instance = {}

from .handlers import ErrorHandler
from .utils import attach_middleware

app = Sanic(__name__, error_handler=ErrorHandler())

SanicUserAgent.init_app(app)
attach_middleware(app)

app.config.from_object(config)
app.config.from_object(instance)