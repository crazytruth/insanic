import asyncio
import ujson as json

from grpclib.const import Status
from grpclib.encoding.base import GRPC_CONTENT_TYPE
from grpclib.encoding.proto import ProtoCodec
from grpclib.exceptions import GRPCError
from grpclib.metadata import Deadline
from grpclib.metadata import decode_metadata
from grpclib.protocol import H2Protocol
from grpclib.server import Server as GRPCServer, Handler as GRPCHandler, Stream
from grpclib.utils import DeadlineWrapper

from insanic.log import grpc_access_logger, grpc_error_logger


async def _send_headers(_stream, _headers, end_stream):
    await _stream.send_headers(_headers, end_stream=end_stream)
    if _stream.closable:
        _stream.reset_nowait()


async def request_handler(mapping, _stream, headers, codec, release_stream):
    response_headers = None
    stream = None
    try:
        headers_map = dict(headers)
        h2_path = headers_map[':path']
        method = mapping.get(h2_path)

        if headers_map[':method'] != 'POST':
            response_headers = [
                (':status', '405')
            ]
            await _send_headers(_stream, response_headers, end_stream=True)
            return

        content_type = headers_map.get('content-type')
        if content_type is None:
            response_headers = [
                (':status', '415'),
                ('grpc-status', str(Status.UNKNOWN.value)),
                ('grpc-message', 'Missing content-type header'),
            ]

            await _send_headers(_stream, response_headers, True)
            return

        base_content_type, _, sub_type = content_type.partition('+')
        sub_type = sub_type or ProtoCodec.__content_subtype__
        if (
                base_content_type != GRPC_CONTENT_TYPE
                or sub_type != codec.__content_subtype__
        ):
            response_headers = [
                (':status', '415'),
                ('grpc-status', str(Status.UNKNOWN.value)),
                ('grpc-message', 'Unacceptable content-type header'),
            ]
            await _send_headers(_stream, response_headers, True)
            return

        if headers_map.get('te') != 'trailers':
            response_headers = [
                (':status', '400'),
                ('grpc-status', str(Status.UNKNOWN.value)),
                ('grpc-message', 'Required "te: trailers" header is missing'),
            ]
            await _send_headers(_stream, response_headers, True)
            return

        if method is None:
            response_headers = [
                (':status', '200'),
                ('grpc-status', str(Status.UNIMPLEMENTED.value)),
                ('grpc-message', 'Method not found'),
            ]

            await _send_headers(_stream, response_headers, end_stream=True)
            return

        try:
            deadline = Deadline.from_headers(headers)
        except ValueError:
            response_headers = [
                (':status', '200'),
                ('grpc-status', str(Status.UNKNOWN.value)),
                ('grpc-message', 'Invalid grpc-timeout header'),
            ]

            await _send_headers(_stream, response_headers, end_stream=True)
            return

        metadata = decode_metadata(headers)

        async with Stream(_stream, method.cardinality, codec,
                          method.request_type, method.reply_type,
                          metadata=metadata, deadline=deadline) as stream:
            deadline_wrapper = None
            try:
                if deadline:
                    deadline_wrapper = DeadlineWrapper()
                    with deadline_wrapper.start(deadline):
                        with deadline_wrapper:
                            await method.func(stream)
                else:
                    await method.func(stream)
            except asyncio.TimeoutError:
                if deadline_wrapper and deadline_wrapper.cancelled:
                    grpc_error_logger.exception('Deadline exceeded')
                    raise GRPCError(Status.DEADLINE_EXCEEDED)
                else:
                    grpc_error_logger.exception('Timeout occurred')
                    raise
            except asyncio.CancelledError:
                grpc_error_logger.exception('Request was cancelled')
                raise
            except Exception:
                grpc_error_logger.exception('Application error')
                raise
    except Exception:
        grpc_error_logger.exception('Server error')
    finally:

        extra = {}
        for k, v in headers_map.items():
            if k.startswith(":"):
                extra.update({k[1:]: v})

        extra.update({"host": extra.get('authority', '')})

        if response_headers is not None:
            response_headers_mapping = dict(response_headers)
            extra.update({"status": response_headers_mapping.get(':status', 200)})
            extra.update({"grpc_status": response_headers_mapping.get('grpc-status', '0')})

            message = response_headers_mapping.get('grpc-message', '')
        else:
            extra.update({"status": '200'})
            extra.update({"grpc_status": 0})
            message = ''

        request_service = json.loads(headers_map.get('context-request-service', "{}"))

        extra.update({"request_service": request_service.get('source', "")})
        extra.update({"correlation_id": headers_map.get('context-request-id', "not set")})
        extra.update({"stream_id": _stream.id})
        extra.update({"cardinality": method.cardinality.name})

        if stream is not None:
            extra.update({"deadline": stream.deadline})

        grpc_access_logger.info(message, extra=extra)

        release_stream()


class Handler(GRPCHandler):

    def accept(self, stream, headers, release_stream):
        self.__gc_step__()
        self._tasks[stream] = self.loop.create_task(
            request_handler(self.mapping, stream, headers, self.codec,
                            release_stream)
        )


class Server(GRPCServer):

    def _protocol_factory(self):
        self.__gc_step__()
        handler = Handler(self._mapping, self._codec, loop=self._loop)
        self._handlers.add(handler)
        return H2Protocol(handler, self._config, loop=self._loop)
