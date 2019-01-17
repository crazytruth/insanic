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
                'request_duration': int(time.time() * 1000000) - (self.request._request_time),
                'method': self.request.method,
                'path': self.request.path,
                'error_code_name': None,
                'error_code_value': None,
                'uri_template': self.request.uri_template

            }
            if hasattr(response, "error_code") and response.error_code is not None:
                extra.update({"error_code_name": response.error_code['name']})
                extra.update({"error_code_value": response.error_code['value']})

            if hasattr(self.request, "_service"):
                extra.update({
                    "request_service": str(self.request._service.request_service),
                })
            if hasattr(response, 'segment'):
                segment = response.segment
                if segment is not None:
                    extra.update({
                        'ot_trace_id': segment.trace_id,
                        'ot_parent_id': segment.parent_id,
                        'ot_sampled': int(segment.sampled),
                        'ot_duration': (segment.end_time - segment.start_time) * 1000
                    })

            if str(response.status)[0] == "5":
                access_logger.exception('', extra=extra, exc_info=response.exception)
            else:
                access_logger.info('', extra=extra)
