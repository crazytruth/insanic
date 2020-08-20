import asyncio

import aiohttp
import io
import ujson as json

from asyncio import get_event_loop
from inspect import isawaitable
from sanic.constants import HTTP_METHODS
from sanic.request import File
from yarl import URL

from insanic import exceptions, status
from insanic.authentication.handlers import (
    jwt_service_encode_handler,
    jwt_service_payload_handler,
)
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.functional import cached_property_with_ttl
from insanic.log import error_logger
from insanic.models import to_header_value
from insanic.services.response import InsanicResponse
from insanic.scopes import is_docker
from insanic.utils import try_json_decode
from insanic.utils.datetime import get_utc_datetime
from insanic.utils.obfuscating import get_safe_dict
from insanic.services.utils import context_user, context_correlation_id


class Service(object):

    _session = None
    _semaphore = None
    extra_session_configs = {}

    def __init__(self, service_type):
        self._service_name = service_type
        # self._session = None
        self._token = None
        super().__init__()

    @property
    def service_name(self):
        return self._service_name

    @cached_property_with_ttl(ttl=60)
    def schema(self):
        return settings.SERVICE_GLOBAL_SCHEMA

    @cached_property_with_ttl(ttl=60)
    def host(self):
        # return "localhost"
        _host = settings.SERVICE_GLOBAL_HOST_TEMPLATE.format(self.service_name)
        if hasattr(settings, "SWARM_SERVICE_LIST"):
            _host = settings.SWARM_SERVICE_LIST.get(self.service_name, {}).get(
                "host", _host
            )
        return _host

    @cached_property_with_ttl(ttl=60)
    def port(self):
        _port = settings.SERVICE_GLOBAL_PORT
        if hasattr(settings, "SWARM_SERVICE_LIST"):
            _port = settings.SWARM_SERVICE_LIST.get(self.service_name, {}).get(
                "internal_service_port"
                if is_docker
                else "external_service_port",
                _port,
            )
        return _port

    @property
    def service_payload(self):
        return jwt_service_payload_handler(self)

    @property
    def service_token(self):
        if self._token is None:
            self._token = jwt_service_encode_handler(self.service_payload)
        return self._token

    @property
    def url(self):
        url_partial_path = "/api/v1/"
        return URL(
            f"{self.schema}://{self.host}:{self.port}{url_partial_path}"
        )

    @classmethod
    def add_trace_config(cls, trace_config):
        if "trace_configs" not in cls.extra_session_configs:
            cls.extra_session_configs["trace_configs"] = []
        cls.extra_session_configs["trace_configs"].append(trace_config)

    @classmethod
    def session(cls):
        if (
            cls._session is None
            or cls._session.closed
            or cls._session.loop._closed
        ):
            default_timeout = aiohttp.ClientTimeout(
                total=settings.SERVICE_TIMEOUT_TOTAL,
                connect=settings.SERVICE_TIMEOUT_CONNECT,
                sock_read=settings.SERVICE_TIMEOUT_SOCK_READ,
                sock_connect=settings.SERVICE_TIMEOUT_SOCK_CONNECT,
            )

            # 20181128 changed TCPConnector from keepalive_timeout=15 to 0 to stop connections getting reused
            # not the most elegant solution because now each connection will open and close
            # force_close seems to absolutely close the connection so don't use because we need to get
            # meta data from the connection even if it is closed
            _client_session_configs = dict(
                loop=get_event_loop(),
                connector=aiohttp.TCPConnector(
                    limit=settings.SERVICE_CONNECTOR_LIMIT,
                    keepalive_timeout=int(
                        settings.SERVICE_CONNECTION_KEEP_ALIVE_TIMEOUT
                    ),
                    limit_per_host=settings.SERVICE_CONNECTOR_LIMIT_PER_HOST,
                    ttl_dns_cache=settings.SERVICE_CONNECTOR_TTL_DNS_CACHE,
                ),
                response_class=InsanicResponse,
                timeout=default_timeout,
                json_serialize=json.dumps,
                cookie_jar=aiohttp.DummyCookieJar(),
            )
            _client_session_configs.update(**cls.extra_session_configs)

            cls._session = aiohttp.ClientSession(**_client_session_configs)

        return cls._session

    @classmethod
    def semaphore(cls):
        if cls._semaphore is None:
            cls._semaphore = asyncio.Semaphore(
                settings.SERVICE_CONNECTOR_SEMAPHORE_COUNT
            )
        return cls._semaphore

    def _construct_url(self, endpoint, query_params=None):
        url = self.url.with_path(endpoint)
        query_params = query_params or {}
        if len(query_params):
            url = url.with_query(**query_params)
        return url

    def _prepare_headers(self, headers, files=None):

        lower_headers = {k.lower(): v for k, v in headers.items()}

        if "accept" not in lower_headers:
            lower_headers.update({"accept": "application/json"})

        if "content-type" not in lower_headers:
            files = files or {}
            if len(files) is 0:
                lower_headers.update({"content-type": "application/json"})

        lower_headers.update(
            {"date": get_utc_datetime().strftime("%a, %d %b %y %T %z")}
        )

        # inject jwt token to headers
        lower_headers.update(
            {
                "authorization": f"{settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX']} {self.service_token}"
            }
        )

        # inject user information to request headers
        user = context_user()
        lower_headers.update(
            {
                settings.INTERNAL_REQUEST_USER_HEADER.lower(): to_header_value(
                    user
                )
            }
        )

        # inject correlation_id
        correlation_id = context_correlation_id()
        lower_headers.update(
            {settings.REQUEST_ID_HEADER_FIELD.lower(): correlation_id}
        )
        return lower_headers

    def _prepare_body(self, headers, payload, files=None):
        if files is None:
            files = {}

        if (
            len(files) == 0
            and headers.get("content-type") == "application/json"
        ):
            data = aiohttp.payload.JsonPayload(payload)
        else:
            data = aiohttp.formdata.FormData()
            for k, v in payload.items():
                data.add_field(k, v, content_type=None)

            def add_file(key, item):
                if isinstance(item, io.IOBase):
                    data.add_field(key, item, filename=item.name)
                elif isinstance(item, File):
                    data.add_field(
                        key,
                        item.body,
                        filename=item.name,
                        content_type=item.type,
                    )
                elif isinstance(item, (list, set, tuple)):
                    for v1 in item:
                        add_file(key, v1)
                else:
                    raise RuntimeError(
                        "INVALID FILE: invalid value for files. Must be either and instance of io.IOBase(using open) or"
                        "sanic File object."
                    )

            for k, v in files.items():
                add_file(k, v)

        return data

    def http_dispatch(
        self,
        method,
        endpoint,
        *,
        query_params=None,
        payload=None,
        files=None,
        headers=None,
        propagate_error=False,
        include_status_code=False,
        response_timeout=None,
        retry_count=None,
        **kwargs,
    ):
        """
        Interface for sending requests to other services.

        :param method: method to send request (GET, POST, PATCH, PUT, etc)
        :type method: string
        :param endpoint: the path to send request to (eg /api/v1/..)
        :type endpoint: string
        :param query_params: query params to attach to url
        :type query_params: dict
        :param payload: the data to send on any non GET requests
        :type payload: dict
        :param files: if any files to send with request, must be included here
        :type files: dict
        :param headers: headers to send along with request
        :type headers: dict
        :param propagate_error: if you want to raise on 400 or greater status codes
        :type propagate_error: bool
        :param include_status_code: if you want this method to return the response with the status code
        :type include_status_code: bool
        :param response_timeout: if you want to increase the timeout for this requests
        :type response_timeout: int
        :return:
        :rtype: dict or tuple(dict, int)
        """

        files = files or {}
        query_params = query_params or {}
        payload = payload or {}
        headers = headers or {}

        if method.upper() not in HTTP_METHODS:
            raise ValueError("{0} is not a valid method.".format(method))

        url = self._construct_url(endpoint, query_params=query_params)
        headers = self._prepare_headers(headers, files)
        data = self._prepare_body(headers, payload, files)

        return asyncio.ensure_future(
            self._dispatch_future(
                method,
                url,
                body=data,
                headers=headers,
                propagate_error=propagate_error,
                response_timeout=response_timeout,
                include_status_code=include_status_code,
                retry_count=retry_count,
                **kwargs,
            )
        )

    async def _dispatch_future(
        self,
        method,
        url,
        *,
        body,
        headers,
        propagate_error=False,
        response_timeout=None,
        include_status_code=False,
        retry_count=None,
        **kwargs,
    ):
        """

        :param method:
        :param endpoint:
        :param query_params: dict
        :param payload:  dict
        :param files: dict
        :param headers: dict
        :param propagate_error: bool
        :param response_timeout: int
        :return:
        """
        # request_start_time = time.monotonic()

        request_params = {
            "method": method,
            "url": str(url),
            "headers": headers,
            "data": body,
            "retry_count": retry_count,
        }
        if response_timeout:
            timeout = aiohttp.ClientTimeout(
                total=response_timeout,
                sock_connect=settings.SERVICE_TIMEOUT_SOCK_CONNECT,
                sock_read=settings.SERVICE_TIMEOUT_SOCK_READ,
            )
            request_params.update({"timeout": timeout})

        try:
            kwargs.update(request_params)
            async with self.semaphore():
                resp = await asyncio.shield(
                    self._dispatch_future_fetch(**kwargs)
                )

            if propagate_error:
                resp.raise_for_status()

            response_status = resp.status
            response = try_json_decode(await resp.text())
            if include_status_code:
                return response, response_status
            else:
                return response

        except aiohttp.client_exceptions.ClientResponseError as e:
            message = e.message
            if isawaitable(message):
                message = await message

            response = try_json_decode(message)
            try:
                status_code = e.code
            except AttributeError:
                status_code = getattr(
                    e, "status", status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            base_error_message = (
                f"ClientResponseError: {method} {url} {status_code} "
                f"{json.dumps(json.loads(message))} {json.dumps(get_safe_dict(json.loads(body._value.decode())))}"
            )
            if status_code >= 500:
                error_logger.error(base_error_message)
            else:
                error_logger.info(base_error_message)

            error_code = (
                GlobalErrorCodes.invalid_usage
                if status_code == status.HTTP_400_BAD_REQUEST
                else GlobalErrorCodes.unknown_error
            )
            exc = exceptions.APIException(
                description=response.get("description", response),
                error_code=response.get("error_code", error_code),
                status_code=status_code,
            )
            exc.message = response.get(
                "message", GlobalErrorCodes.unknown_error.name
            )
            raise exc
        except aiohttp.client_exceptions.ClientConnectorError as e:

            """subset of connection errors that are initiated by an OSError exception"""
            if e.errno == 61:
                msg = settings.SERVICE_UNAVAILABLE_MESSAGE.format(
                    self._service_name
                )
                exc = exceptions.ServiceUnavailable503Error(
                    description=msg,
                    error_code=GlobalErrorCodes.service_unavailable,
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            else:
                exc = exceptions.APIException(
                    description=e.strerror,
                    error_code=GlobalErrorCodes.unknown_error,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
            error_logger.exception(f"ClientConnectorError: {e.strerror}")
            raise exc
        except aiohttp.client_exceptions.ServerFingerprintMismatch:
            """server fingerprint mismatch"""
            msg = "Server Fingerprint Mismatch"
            exc = exceptions.APIException(
                description=msg,
                error_code=GlobalErrorCodes.server_signature_error,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            raise exc
        except aiohttp.client_exceptions.ServerConnectionError as e:
            """ server connection related errors """
            if isinstance(
                e, aiohttp.client_exceptions.ServerDisconnectedError
            ):
                """ server disconnected """
                exc = exceptions.ServiceUnavailable503Error(
                    description=e.message,
                    error_code=GlobalErrorCodes.service_unavailable,
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            elif isinstance(e, aiohttp.client_exceptions.ServerTimeoutError):
                """server operation timeout, (read timeout, etc)"""
                exc = exceptions.ResponseTimeoutError(
                    description=f"{self.service_name} has timed out."
                )
            else:
                msg = settings.SERVICE_UNAVAILABLE_MESSAGE.format(
                    self._service_name
                )
                exc = exceptions.ServiceUnavailable503Error(
                    description=msg,
                    error_code=GlobalErrorCodes.service_unavailable,
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            error_logger.exception(f"ServerConnectionError: {e}")
            raise exc
        except aiohttp.client_exceptions.ClientConnectionError as e:
            error_logger.exception(f"ClientConnectionError: {e.args[0]}")
            # https://aiohttp.readthedocs.io/en/v3.0.1/client_reference.html#hierarchy-of-exceptions
            exc = exceptions.APIException(
                description=e.args[0],
                error_code=GlobalErrorCodes.unknown_error,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
            raise exc
        except asyncio.TimeoutError:
            exc = exceptions.ResponseTimeoutError(
                description=f"{self.service_name} has timed out."
            )
            raise exc
        except aiohttp.client_exceptions.ClientPayloadError:
            raise
        except aiohttp.client_exceptions.InvalidURL:
            raise
        # finally:
        #     duration = time.monotonic() - request_start_time
        #     if duration > 5:
        #         error_logger.error(f"Request time: {duration}")

    async def _dispatch_future_fetch(
        self, method, url, headers, data, retry_count=None, **request_params
    ):

        attempts = 1
        if method == "GET":
            attempts += (
                settings.SERVICE_CONNECTION_DEFAULT_RETRY_COUNT
                if retry_count is None
                else min(
                    retry_count,
                    int(settings.SERVICE_CONNECTION_MAX_RETRY_COUNT),
                )
            )

        for i in range(attempts):

            try:
                async with self.session().request(
                    method=method,
                    url=url,
                    headers=headers,
                    data=data,
                    **request_params,
                ) as resp:
                    await resp.read()
                    return resp
            except (
                aiohttp.client_exceptions.ClientConnectionError,
                aiohttp.client_exceptions.ServerDisconnectedError,
                ConnectionResetError,
            ) as e:
                error_logger.debug(f"{str(e)} on attempt {i}")

                if i + 1 >= attempts:
                    raise

    # def _log_failed(self, exc, request_start_time):
    #     """
    #     possible outcomes that this method should log
    #     1. a response from target server where status is 500 or above (api error)
    #     2. an error from aiohttp where target server could not be reached (not an api error)
    #     3.
    #
    #     :param response:
    #     :param exc:
    #     :param request_start_time:
    #     :return:
    #     """
    #
    #     if not isinstance(exc, exceptions.APIException):
    #         if exc.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
    #             extra = {
    #                 'status': exc.status_code,
    #                 'byte': -1,
    #                 'host': f'{self.request.socket[0]}:{self.request.socket[1]}',
    #                 'request': f'{self.request.method} {self.request.url}',
    #                 'request_duration': int(time.time() * 1000000) - (self.request._request_time),
    #                 'method': self.request.method,
    #                 'path': self.request.path,
    #                 'error_code_name': None,
    #                 'error_code_value': None,
    #                 'uri_template': self.request.uri_template
    #
    #             }

    #         access_logger.exception('', extra=extra, exc_info=exc)
    #
