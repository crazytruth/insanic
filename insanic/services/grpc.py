import aiodns
import asyncio
import io
import random
import time
import ujson as json

from aiodns.error import DNSError
from collections import OrderedDict
from enum import IntEnum
from grpclib.client import Channel
from grpclib.exceptions import GRPCError, ProtocolError
from grpclib.const import Status as GRPCStatus

from sanic.request import File as SanicFile

from insanic import status, exceptions
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.exceptions import APIException
from insanic.grpc.dispatch.dispatch_grpc import DispatchStub
from insanic.grpc.dispatch.dispatch_pb2 import ServiceRequest, ContextUser, ContextService, FileList
from insanic.grpc.health.health_grpc import HealthStub
from insanic.grpc.health.health_pb2 import HealthCheckRequest
from insanic.log import error_logger, logger
from insanic.services.utils import context_user, context_correlation_id

GRPC_HTTP_STATUS_MAP = OrderedDict([
    (GRPCStatus.OK, status.HTTP_200_OK),
    (GRPCStatus.CANCELLED, status.HTTP_499_CLIENT_CLOSED_REQUEST),
    (GRPCStatus.UNKNOWN, status.HTTP_500_INTERNAL_SERVER_ERROR),
    (GRPCStatus.INVALID_ARGUMENT, status.HTTP_400_BAD_REQUEST),
    (GRPCStatus.DEADLINE_EXCEEDED, status.HTTP_504_GATEWAY_TIMEOUT),
    (GRPCStatus.NOT_FOUND, status.HTTP_404_NOT_FOUND),
    (GRPCStatus.ALREADY_EXISTS, status.HTTP_409_CONFLICT),
    (GRPCStatus.PERMISSION_DENIED, status.HTTP_403_FORBIDDEN),
    (GRPCStatus.UNAUTHENTICATED, status.HTTP_401_UNAUTHORIZED),
    (GRPCStatus.RESOURCE_EXHAUSTED, status.HTTP_429_TOO_MANY_REQUESTS),
    (GRPCStatus.FAILED_PRECONDITION, status.HTTP_400_BAD_REQUEST),
    (GRPCStatus.ABORTED, status.HTTP_409_CONFLICT),
    (GRPCStatus.OUT_OF_RANGE, status.HTTP_400_BAD_REQUEST),
    (GRPCStatus.UNIMPLEMENTED, status.HTTP_501_NOT_IMPLEMENTED),
    (GRPCStatus.INTERNAL, status.HTTP_500_INTERNAL_SERVER_ERROR),
    (GRPCStatus.UNAVAILABLE, status.HTTP_503_SERVICE_UNAVAILABLE),
    (GRPCStatus.DATA_LOSS, status.HTTP_500_INTERNAL_SERVER_ERROR)
])

GRPC_HEALTH_CHECK_CACHE_TTL = 60
DNS_DEFAULT_TTL = 60
DNS_QUERY_TYPE = 'A'

class GRPCServingStatus(IntEnum):
    UNKNOWN = 0
    SERVING = 1
    NOT_SERVING = 2
    SERVICE_UNKNOWN = 3


class ChannelManager:
    _channel = None
    _channel_update_time = time.monotonic()

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._resolver = aiodns.DNSResolver()

    async def resolve_host(self):
        try:
            query_result = await self._resolver.query(self.host, DNS_QUERY_TYPE)
        except DNSError as e:
            ip_list = [(self.host, DNS_DEFAULT_TTL)]
        else:
            ip_list = [(q.host, q.ttl) for q in query_result]

        for ip in ip_list:
            self.add_channel(ip[0], self.port)
        self._channel_update_time = time.monotonic() + min([q[1] for q in ip_list])

    async def get_channel(self):
        if self._channel is None or self._channel_update_time < time.monotonic():
            await self.resolve_host()

        try:
            channel = random.choice(list(self._channel.values()))
        except KeyError:
            logger.error("[GRPC] No channel found.")
            raise
        else:
            return channel

    def add_channel(self, host, port):
        """
        add channel to list of available channels

        :param host:
        :param port:
        :return:
        """
        if self._channel is None:
            self._channel = OrderedDict()

        self._channel.update({host: Channel(host=host,
                                            port=port,
                                            loop=asyncio.get_event_loop())})

    def remove_channel(self, channel: Channel):
        try:
            channel.close()
        except AttributeError:
            pass
        else:
            self._remove_channel(channel._host)

    def close_all(self):
        """
        Closes all channels
        :return:
        """
        if self._channel is None:
            return

        while self._channel:
            h, c = self._channel.popitem()
            c.close()
            self._remove_channel(c._host)

    def _remove_channel(self, key):
        try:
            del self._channel[key]
        except KeyError:
            pass


class GRPCClient:

    _stub = None
    _health_stub = None

    def __init__(self):
        self._status = None
        self._status_check = 0
        self._channel_manager = None

    @property
    def grpc_port(self):
        return int(self.port) + settings.GRPC_PORT_DELTA

    @property
    def channel_manager(self):
        if self._channel_manager is None:
            self._channel_manager = ChannelManager(self.host, self.grpc_port)
        return self._channel_manager

    @property
    async def stub(self):
        if self._stub is None:
            self._stub = DispatchStub(await self.channel_manager.get_channel())
        return self._stub

    @property
    async def health(self):
        if self._health_stub is None:
            self._health_stub = HealthStub(await self.channel_manager.get_channel())
        return self._health_stub

    async def health_status(self):
        if self._status is None or self._status_check + self.next_check_delta < time.monotonic():
            await self.health_check()
        return self._status == GRPCServingStatus.SERVING

    @property
    def status(self):
        try:
            return GRPCServingStatus(self._status)
        except ValueError:
            return self._status

    @status.setter
    def status(self, val):
        self._status = val
        self._status_check = time.monotonic()

    @property
    def next_check_delta(self):
        return GRPC_HEALTH_CHECK_CACHE_TTL

    async def health_check(self):
        request = HealthCheckRequest(service="insanic.v1.Dispatch")

        health_stub = await self.health
        try:
            health = await health_stub.Check(request, timeout=1)
            self.status = health.status
            logger.debug(f'[GRPC] CHECKER: {self.service_name} is grpc status is : {self.status.name}!')
        except ConnectionRefusedError:
            self.status = GRPCServingStatus.NOT_SERVING
            logger.debug(f'[GRPC] CHECKER: {self.service_name} is not serving grpc!')
            self.channel_manager.remove_channel(health_stub.Check.channel)
        except GRPCError as e:
            self.status = GRPCServingStatus.UNKNOWN
            logger.info(f'[GRPC] CHECKER: {self.service_name} error: {e.message}')
            self.channel_manager.remove_channel(health_stub.Check.channel)
        except Exception as e:
            self.status = GRPCServingStatus.UNKNOWN
            logger.warning(f'[GRPC] CHECKER: {self.service_name} unknown error')
            self.channel_manager.remove_channel(health_stub.Check.channel)

    # async def health_watch(self):
    #     request = HealthCheckRequest(service="insanic.grpc.dispatch.Dispatch")
    #
    #     while True:
    #         try:
    #             health = await self.health.Watch(request)
    #             self._status = health.status
    #             logger.info(f'[GRPC] WATCHER: {self.service_name} is grpc healthy!')
    #         except ConnectionRefusedError:
    #             self._status = 2
    #             logger.info(f'[GRPC] WATCHER: {self.service_name} not running!')
    #             await asyncio.sleep(10)
    #         except GRPCError as e:
    #             self._status = 0
    #             logger.warning(f'[GRPC] WATCHER: {self.service_name} error: {e.message}')

    @staticmethod
    def _status_translations(e):
        """
        Translates grpc status codes to http status codes
        https://github.com/googleapis/googleapis/blob/master/google/rpc/code.proto

        OK = 0
        CANCELLED = 1 # operation was cancelled, typically by the caller
        UNKNOWN = 2
        INVALID_ARGUMENT = 3
        DEADLINE_EXCEEDED = 4
        NOT_FOUND = 5
        ALREADY_EXISTS = 6
        PERMISSION_DENIED = 7
        RESOURCE_EXHAUSTED = 8
        FAILED_PRECONDITION = 9
        ABORTED = 10
        OUT_OF_RANGE = 11
        UNIMPLEMENTED = 12
        INTERNAL = 13
        UNAVAILABLE = 14
        DATA_LOSS = 15
        UNAUTHENTICATED = 16

        :param e:
        :return:
        :rtype: APIException
        """
        for grpc_status, http_status in GRPC_HTTP_STATUS_MAP.items():
            if e.status is grpc_status:
                return exceptions.APIException(e.message, status_code=http_status)
        else:
            return exceptions.APIException()

    def _prepare_files(self, files):

        packed_files = {}

        for k, fs in files.items():
            if not isinstance(fs, list):
                fs = [fs]

            for f in fs:
                if isinstance(f, io.BufferedReader):
                    fb = f.read()
                    fn = f.name
                elif isinstance(f, SanicFile):
                    fb = f.body
                    fn = f.name
                else:
                    raise RuntimeError(
                        "INVALID FILE: invalid value for files. Must be either and instance "
                        "of io.IOBase(using open) or sanic File objects.")

                if k not in packed_files:
                    packed_files[k] = FileList()
                try:
                    packed_files[k].f.add(body=fb, name=fn)
                except TypeError:
                    raise

        return packed_files

    async def _dispatch_grpc(self, *, method, endpoint, query_params, headers, payload, files,
                             request_timeout, propagate_error, skip_breaker):

        if not await self.health_status():
            raise ConnectionRefusedError("not healthy")

        body = {k: json.dumps(v) for k, v in payload.items()}
        path = self._construct_url(endpoint, query_params=query_params).path_qs.encode()

        if files:
            files = self._prepare_files(files)

        request = ServiceRequest(
            method=method,
            endpoint=path,
            headers=headers,
            user=ContextUser(**context_user()),
            service=ContextService(**self.service_payload),
            request_id=context_correlation_id(),
            body=body,
            files=files
        )
        dispatch_stub = await self.stub
        try:
            response = await dispatch_stub.handle_grpc(request, timeout=request_timeout)
            response_body = json.loads(response.body)
            if propagate_error:
                if 400 <= response.status_code:
                    e = APIException(response_body['description'],
                                     error_code=response_body['error_code'], status_code=response.status_code)
                    e.message = response_body.get('message', e.message)
                    raise e
        except GRPCError as e:
            raise self._status_translations(e)
        except asyncio.TimeoutError as e:
            self.channel_manager.remove_channel(dispatch_stub.handle_grpc.channel)
            raise exceptions.RequestTimeoutError(description=f'Request to {self.service_name} took too long!',
                                                 error_code=GlobalErrorCodes.request_timeout,
                                                 status_code=status.HTTP_408_REQUEST_TIMEOUT)
        except ProtocolError as e:
            self.channel_manager.remove_channel(dispatch_stub.handle_grpc.channel)
            error_logger.exception(f"GRPC Protocol Error: {e.msg}", exc_info=e)
            raise exceptions.APIException("Something unexpected happened.",
                                          error_code=GlobalErrorCodes.protocol_error,
                                          status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ConnectionRefusedError as e:
            self.channel_manager.remove_channel(dispatch_stub.handle_grpc.channel)
            self.status = 0
            raise e

        return response_body, response.status_code
