import time

from sanic.server import HttpProtocol

from insanic.log import access_logger


class InsanicHttpProtocol(HttpProtocol):

    def log_response(self, response):
        if self.access_log:
            if self.request.url.endswith('/health/'):
                return

            extra = {
                'status': response.status,
                'byte': len(response.body),
                'host': f'{self.request.socket[0]}:{self.request.socket[1]}',
                'request': f'{self.request.method} {self.request.url}',
                'request_duration': int(time.time() * 1000000) - (self.request._request_time)
            }
            if hasattr(self.request, "_service"):
                extra.update({
                    "request_service": str(self.request._service.request_service),
                })
            if hasattr(response, 'span'):
                span = response.span
                if span is not None:
                    extra.update({
                        'ot_trace_id': span.trace_id,
                        'ot_parent_id': span.parent_id,
                        'ot_sampled': int(span.sampled),
                        'ot_duration': (span.end_time - span.start_time) * 1000
                    })

            if str(response.status)[0] == "5":
                access_logger.exception('', extra=extra, exc_info=response.exception)
            else:
                access_logger.info('', extra=extra)
