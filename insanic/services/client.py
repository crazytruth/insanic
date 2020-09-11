import asyncio
import httpx
import socket
from httpx import URL, Headers, Request, codes, StatusCode
from httpx.config import UNSET

from insanic import exceptions, status
from insanic.authentication.handlers import (
    jwt_service_encode_handler,
    jwt_service_payload_handler,
)
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.log import error_logger
from insanic.models import to_header_value
from insanic.services.adapters import (
    Limits,
    Timeout,
    AsyncClient,
    HTTPStatusError,
    RequestError,
    TransportError,
)
from insanic.services.utils import context_user, context_correlation_id
from insanic.utils.datetime import get_utc_datetime


class Service:

    _client = None
    extra_session_configs = {}

    def __init__(self, service_name: str, partial_path: str = None):
        self.service_name = service_name
        self.service_token = jwt_service_encode_handler(
            jwt_service_payload_handler(self)
        )

        partial_path = partial_path or "/api/"
        self.url = URL(
            f"{settings.SERVICE_GLOBAL_SCHEMA}://"
            f"{settings.SERVICE_GLOBAL_HOST_TEMPLATE.format(self.service_name)}"
            f":{settings.SERVICE_GLOBAL_PORT}{partial_path}"
        )
        super().__init__()

    @property
    def client(self) -> AsyncClient:
        if self._client is None:
            limits = Limits(
                max_connections=settings.SERVICE_CONNECTOR_MAX,
                max_keepalive_connections=settings.SERVICE_CONNECTOR_MAX_KEEPALIVE,
            )
            timeout = Timeout(
                timeout=settings.SERVICE_TIMEOUT_TOTAL,
                connect=getattr(settings, "SERVICE_TIMEOUT_CONNECT", UNSET),
                read=getattr(settings, "SERVICE_TIMEOUT_READ", UNSET),
                write=getattr(settings, "SERVICE_TIMEOUT_WRITE", UNSET),
                pool=getattr(settings, "SERVICE_TIMEOUT_POOL", UNSET),
            )

            self._client = AsyncClient(
                limits=limits,
                timeout=timeout,
                base_url=self.url,
                headers={
                    "authorization": f"{settings.JWT_SERVICE_AUTH_AUTH_HEADER_PREFIX} {self.service_token}"
                },
            )
        return self._client

    @property
    def host(self) -> str:
        return self.url.host

    @host.setter
    def host(self, value: str) -> None:
        self.url = self.url.copy_with(host=value)

    @property
    def port(self) -> int:
        return self.url.port

    @port.setter
    def port(self, value: int) -> None:
        self.url = self.url.copy_with(port=value)

    async def close_client(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            await asyncio.sleep(0)

    def add_trace_config(self, trace_config):
        if "trace_configs" not in self.extra_session_configs:
            self.extra_session_configs["trace_configs"] = []
        self.extra_session_configs["trace_configs"].append(trace_config)

    def _inject_headers(self, headers: dict):
        # need to coerce to str
        headers = {k: str(v) for k, v in headers.items()}
        headers.update(
            {"date": get_utc_datetime().strftime("%a, %d %b %y %T %z")}
        )

        # inject user information to request headers
        user = context_user()
        headers.update(
            {
                settings.INTERNAL_REQUEST_USER_HEADER.lower(): to_header_value(
                    user
                )
            }
        )
        # inject correlation_id
        correlation_id = context_correlation_id()
        headers.update(
            {settings.REQUEST_ID_HEADER_FIELD.lower(): correlation_id}
        )

        return Headers(headers)

    def http_dispatch(
        self,
        method: str,
        endpoint: str,
        *,
        query_params: dict = None,
        payload: dict = None,
        files: dict = None,
        headers: dict = None,
        propagate_error: bool = False,
        include_status_code: bool = False,
        response_timeout: int = UNSET,
        retry_count: int = None,
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
        :param retry_count: number times you want to retry the request if failed on server errors
        :type response_timeout: int
        :return:
        :rtype: dict or tuple(dict, int)
        """

        files = files or {}
        query_params = query_params or {}
        payload = payload or {}
        headers = self._inject_headers(headers or {})

        request = self.client.build_request(
            method,
            endpoint,
            data=payload,
            files=files,
            params=query_params,
            headers=headers,
        )

        return asyncio.ensure_future(
            self._dispatch_future(
                request,
                propagate_error=propagate_error,
                response_timeout=response_timeout,
                include_status_code=include_status_code,
                retry_count=retry_count,
                **kwargs,
            )
        )

    async def _dispatch_future(
        self,
        request,
        *,
        propagate_error: bool = False,
        response_timeout: float = None,
        include_status_code: bool = False,
        retry_count: int = None,
        **kwargs,
    ):
        """
        The async method that wraps the actual fetch

        :param request:
        :param propagate_error:
        :param response_timeout:
        :param include_status_code:
        :param retry_count:
        :param kwargs:
        :return:
        """

        try:
            resp = await asyncio.shield(
                self._dispatch_send(
                    request=request,
                    timeout=response_timeout,
                    retry_count=retry_count,
                )
            )

            if propagate_error:
                resp.raise_for_status()
            response = resp.json()

            if include_status_code:
                return response, resp.status_code
            else:
                return response
        except HTTPStatusError as e:

            response = e.response.json()

            exc = exceptions.APIException(
                description=response.get("description", response),
                error_code=response.get(
                    "error_code", GlobalErrorCodes.unknown_error
                ),
                status_code=e.response.status_code,
            )
            exc.message = response.get("message", exc.error_code.name)

            base_error_message = (
                f"ClientResponseError: {e.request.method} {e.request.url} {e.response.status_code} "
                f"{e}"
            )

            if StatusCode.is_server_error(e.response.status_code):
                error_logger.error(base_error_message)
            else:
                error_logger.info(base_error_message)

            raise exc
        except httpx.TimeoutException as e:
            exc = exceptions.ResponseTimeoutError(
                description=str(e),
                error_code=GlobalErrorCodes.service_timeout,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
            raise exc

        except RequestError as e:
            exc = exceptions.APIException(
                description=str(e),
                error_code=GlobalErrorCodes.service_unavailable,
                status_code=getattr(
                    e.response,
                    "status_code",
                    status.HTTP_503_SERVICE_UNAVAILABLE,
                )
                or status.HTTP_503_SERVICE_UNAVAILABLE,
            )
            raise exc
        except socket.gaierror as e:
            raise exceptions.APIException(
                description=str(e),
                error_code=GlobalErrorCodes.service_unavailable,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    async def _dispatch_send(
        self,
        request: Request,
        *,
        timeout: float = None,
        retry_count: int = None,
    ):
        """

        TODO: need better implementation for retry

        :param request:
        :param timeout:
        :param retry_count:
        :return:
        """
        attempts = 1
        if request.method == "GET":
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
                response = await self.client.send(request, timeout=timeout)

                if codes.is_server_error(response.status_code):
                    response.raise_for_status()

            except (TransportError, HTTPStatusError, ConnectionResetError) as e:
                error_logger.debug(f"{str(e)} on attempt {i}")
                if i + 1 >= attempts:
                    raise
            else:
                return response
