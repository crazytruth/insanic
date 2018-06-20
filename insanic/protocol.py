from sanic import server
from sanic.server import HttpProtocol, ServerError

from insanic.log import access_logger, logger


class InsanicHttpProtocol(HttpProtocol):

    # -------------------------------------------- #
    # Responding
    # -------------------------------------------- #
    def write_response(self, response):
        """
        Writes response content synchronously to the transport.
        # overriding to inject trace_id and span_id into network logs
        """
        try:
            keep_alive = self.keep_alive
            self.transport.write(
                response.output(
                    self.request.version, keep_alive,
                    self.request_timeout))
            if self.access_log:
                extra = {
                    'status': response.status,
                    'byte': len(response.body),
                    'host': f'{self.request.ip[0]}:{self.request.ip[1]}',
                    'request': f'{self.request.method} {self.request.url}'
                }
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
                    if self.request.url.endswith('/health/') and self.request.host == 'nil':
                        pass
                    else:
                        access_logger.info('', extra=extra)
        except AttributeError as e:
            logger.error(
                (f'Invalid response object for url {self.url}, '
                 f'Expected Type: HTTPResponse, Actual Type: {type(response)}'))
            self.write_error(ServerError('Invalid response type'))
        except RuntimeError:
            logger.error(
                f'Connection lost before response written @ {self.request.ip}')
        except Exception as e:
            self.bail_out(
                "Writing response failed, connection closed {}".format(
                    repr(e)))
        finally:
            if not keep_alive:
                self.transport.close()
            else:
                self._last_request_time = server.current_time
                self.cleanup()
