from ujson import dumps as json_dumps
from sanic.response import HTTPResponse, STATUS_CODES


class InsanicHTTPResponse(HTTPResponse):

    def __init__(self, body=None, status=200, headers=None,
                 content_type='text/plain', body_bytes=b''):
        if status is 204:
            body = None

        super().__init__(body, status, headers, content_type, body_bytes)

    def output(
            self, version="1.1", keep_alive=False, keep_alive_timeout=None):
        # This is all returned in a kind-of funky way
        # We tried to make this as fast as possible in pure python
        timeout_header = b''
        if keep_alive and keep_alive_timeout is not None:
            timeout_header = b'Keep-Alive: %d\r\n' % keep_alive_timeout

        if 100 <= self.status < 200 or self.status is 204:
            # Per section 3.3.2 of RFC 7230, "a server MUST NOT send a Content-Length header field
            # in any response with a status code of 1xx (Informational) or 204 (No Content)."
            try:
                del self.headers['Content-Length']
            except KeyError:
                pass
        else:

            self.headers['Content-Length'] = self.headers.get(
                'Content-Length', len(self.body))
            self.headers['Content-Type'] = self.headers.get(
                'Content-Type', self.content_type)

        headers = self._parse_headers()

        if self.status is 200:
            status = b'OK'
        else:
            status = STATUS_CODES.get(self.status, b'UNKNOWN RESPONSE')

        return (b'HTTP/%b %d %b\r\n'
                b'Connection: %b\r\n'
                b'%b'
                b'%b\r\n'
                b'%b') % (
                   version.encode(),
                   self.status,
                   status,
                   b'keep-alive' if keep_alive else b'close',
                   timeout_header,
                   headers,
                   self.body
               )


def json_response(body, status=200, headers=None,
                  content_type="application/json", dumps=json_dumps,
                  **kwargs):
    """
    Returns response object with body in json format.
    This had to be overridden because bug with status 204, where content-length
    should not be sent

    :param body: Response data to be serialized.
    :param status: Response code.
    :param headers: Custom Headers.
    :param kwargs: Remaining arguments that are passed to the json encoder.
    """

    return InsanicHTTPResponse(dumps(body, **kwargs), headers=headers,
                               status=status, content_type=content_type)
