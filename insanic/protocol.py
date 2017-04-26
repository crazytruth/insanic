from sanic.server import HttpProtocol, CIDict

from insanic.request import Request

class InsanicHttpProtocol(HttpProtocol):

    def on_headers_complete(self):
        self.request = Request(
            url_bytes=self.url,
            headers=CIDict(self.headers),
            version=self.parser.get_http_version(),
            method=self.parser.get_method().decode(),
            transport=self.transport
        )



