from sanic import Sanic
from sanic_useragent import SanicUserAgent

import config
from .handlers import ErrorHandler
from .utils import attach_middleware

app = Sanic(__name__, error_handler=ErrorHandler())

SanicUserAgent.init_app(app)
attach_middleware(app)

app.config.from_object(config)