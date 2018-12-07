import time

from inspect import isawaitable
from traceback import format_exc

from sanic.exceptions import ServerError
from insanic import status
from insanic.handlers import INTERNAL_SERVER_ERROR_JSON
from insanic.log import error_logger, grpc_access_logger as access_logger
from insanic.request import Request as InsanicRequest
from insanic.responses import json_response
from insanic.grpc.dispatch.dispatch_grpc import DispatchBase
from insanic.grpc.dispatch.dispatch_pb2 import ServiceResponse


class DispatchServer(DispatchBase):

    def __init__(self, app):
        super().__init__()
        self.app = app

    async def handle_grpc(self, stream):
        rpc_request = await stream.recv_message()

        request = InsanicRequest.from_protobuf_message(rpc_request, stream)
        try:

            request.app = self.app
            response = await self.app._run_request_middleware(request)
            if not response:

                handler, args, kwargs, uri = self.app.router.get(request)

                if handler is None:
                    raise ServerError(
                        ("'None' was returned while requesting a "
                         "handler from the router"))
                response = handler(request, *args, **kwargs)
                if isawaitable(response):
                    response = await response
        except Exception as e:
            try:
                response = self.app.error_handler.response(request, e)
                if isawaitable(response):
                    response = await response
            except Exception as e:  # pragma: no cover
                err_message = INTERNAL_SERVER_ERROR_JSON
                err_message['description'] = "An error occurred while handling an error"
                error_logger.exception("An error occurred while handling an error")
                response = json_response(err_message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            # -------------------------------------------- #
            # Response Middleware
            # -------------------------------------------- #
            try:
                response = await self.app._run_response_middleware(request, response)
            except BaseException as e:
                error_logger.exception(
                    'Exception occurred in one of response middleware handlers',
                )

            self.log_response(request, response)

        await stream.send_message(ServiceResponse(body=response.body, status_code=response.status))

    def log_response(self, request, response):

        extra = {
            'status': response.status,
            'byte': len(response.body),
            'host': f'{request.socket[0]}:{request.socket[1]}',
            # 'host': f'{request._service.source_ip}',
            'request': f'{request.method} {request.path} HTTP/{request.version}',
            'request_duration': int(time.time() * 1000000) - (request._request_time),
            'is_grpc': 1
        }
        if hasattr(request, "_service"):
            extra.update({
                "request_service": str(request._service.request_service),
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
