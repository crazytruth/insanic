from sanic.worker import GunicornWorker

from insanic.conf import settings
from insanic.protocol import InsanicHttpProtocol


class InsanicGunicornWorker(GunicornWorker):
    http_protocol = InsanicHttpProtocol

    def __init__(self, *args, **kw):  # pragma: no cover
        super().__init__(*args, **kw)

        settings.SERVICE_PORT = self.cfg.address[0][1]
