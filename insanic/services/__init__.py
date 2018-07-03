import aiohttp
import aiotask_context
import asyncio
import io
import warnings

# from aiohttp.formdata import FormData
from asyncio import get_event_loop

from sanic.constants import HTTP_METHODS
from sanic.request import File
from yarl import URL

from insanic import exceptions, status
from insanic.authentication.handlers import jwt_service_encode_handler, jwt_service_payload_handler
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.functional import cached_property_with_ttl
from insanic.models import AnonymousUser
from insanic.services.response import InsanicResponse
from insanic.scopes import is_docker
from insanic.tracing.clients import aws_xray_trace_config
from insanic.tracing.utils import tracing_name
from insanic.utils import try_json_decode
from insanic.utils.datetime import get_utc_datetime


DEFAULT_SERVICE_REQUEST_TIMEOUT = 1


class ServiceRegistry(dict):
    __instance = None
    _conn = None

    def __new__(cls, *args, **kwargs):
        if ServiceRegistry.__instance is None:
            ServiceRegistry.__instance = dict.__new__(cls)
            ServiceRegistry.__instance.update(**{s: None for s in
                                                 set(settings.SERVICE_CONNECTIONS +
                                                     settings.REQUIRED_SERVICE_CONNECTIONS)})

        return ServiceRegistry.__instance

    def __setitem__(self, key, value):
        raise RuntimeError("Unable to set new service. Append {0} to SERVICE_CONNECTIONS "
                           "to allow connections to {0}.".format(key))

    def __getitem__(self, key):
        if key not in self:
            raise RuntimeError("{0} service does not exist. Only the following: {1}"
                               .format(key, ", ".join(self.keys())))
        item = super().__getitem__(key)
        if item is None:
            item = Service(key)
            super().__setitem__(key, item)
        return item

    @classmethod
    def reset(cls):
        cls.__instance = None


class Service:
    remove_headers = ["content-length", 'user-agent', 'host', 'postman-token']

    def __init__(self, service_type):
        self._registry = ServiceRegistry()
        self._service_name = service_type
        self._session = None

    @property
    def service_auth_token(self):
        default = dict(AnonymousUser)
        try:
            user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER, default)
        except AttributeError:
            user = default
        return jwt_service_encode_handler(jwt_service_payload_handler(self, user))

    @property
    def service_name(self):
        return self._service_name

    def raise_503(self):
        raise exceptions.ServiceUnavailable503Error(description=f"{self._service_name} is currently unavailable.",
                                                    error_code=GlobalErrorCodes.service_unavailable,
                                                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    @cached_property_with_ttl(ttl=60)
    def schema(self):
        return settings.SERVICE_GLOBAL_SCHEMA

    @cached_property_with_ttl(ttl=60)
    def host(self):
        _host = settings.SERVICE_GLOBAL_HOST_TEMPLATE.format(self.service_name)
        if hasattr(settings, "SWARM_SERVICE_LIST"):
            _host = settings.SWARM_SERVICE_LIST.get(self.service_name, {}).get('host', _host)
        return _host

    @cached_property_with_ttl(ttl=60)
    def port(self):
        _port = settings.SERVICE_GLOBAL_PORT
        if hasattr(settings, "SWARM_SERVICE_LIST"):
            _port = settings.SWARM_SERVICE_LIST.get(self.service_name, {}).get(
                'internal_service_port' if is_docker else 'external_service_port',
                _port)
        return _port

    @property
    def url(self):
        url_partial_path = "/api/v1/"
        return URL(f"{self.schema}://{self.host}:{self.port}{url_partial_path}")

    @property
    def session(self):
        if self._session is None or self._session.loop.is_closed() is True:

            trace_configs = None

            if settings.TRACING_ENABLED:
                trace_configs = [aws_xray_trace_config(tracing_name(self.service_name))]

            self._session = aiohttp.ClientSession(loop=get_event_loop(),
                                                  connector=aiohttp.TCPConnector(limit_per_host=10,
                                                                                 ttl_dns_cache=300),
                                                  response_class=InsanicResponse,
                                                  read_timeout=DEFAULT_SERVICE_REQUEST_TIMEOUT,
                                                  trace_configs=trace_configs)
        return self._session

    def _construct_url(self, endpoint, query_params={}):
        url = self.url.with_path(endpoint)
        if len(query_params):
            url = url.with_query(**query_params)
        return url

    async def http_dispatch(self, method, endpoint, req_ctx=None, *, query_params=None, payload=None,
                            files=None, headers=None,
                            propagate_error=False, skip_breaker=False, include_status_code=False, request_timeout=None):


        if req_ctx is not None:
            warnings.warn("`req_ctx`, the 3rd argument is deprecated.  Please remove. "
                          "Sending this will do absolutely nothing.")

        files = files or {}
        query_params = query_params or {}
        payload = payload or {}
        headers = headers or {}


        if method.upper() not in HTTP_METHODS:
            raise ValueError("{0} is not a valid method.".format(method))

        response, status_code = await self._dispatch(method, endpoint,
                                                     query_params=query_params, payload=payload, files=files,
                                                     headers=headers,
                                                     propagate_error=propagate_error,
                                                     skip_breaker=skip_breaker,
                                                     request_timeout=request_timeout)

        if include_status_code:
            return response, status_code
        return response

    def _prepare_headers(self, headers, files=None):
        for h in self.remove_headers:
            if h in headers:
                del headers[h]

        lower_headers = {k.lower(): v for k, v in headers.items()}

        if "accept" not in lower_headers:
            lower_headers.update({"accept": "application/json"})

        if "content-type" not in lower_headers:
            files = files or {}
            if len(files) is 0:
                lower_headers.update({"content-type": "application/json"})

        lower_headers.update({"date": get_utc_datetime().strftime("%a, %d %b %y %T %z")})

        lower_headers.update(
            {"authorization": f"{settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX']} {self.service_auth_token}"})

        return lower_headers

    def _prepare_body(self, headers, payload, files=None):
        if files is None:
            files = {}

        if len(files) == 0 and headers.get('content-type') == "application/json":
            data = aiohttp.payload.JsonPayload(payload)
        else:
            data = aiohttp.formdata.FormData(payload)
            for k, v in files.items():
                if k in payload.keys():
                    raise RuntimeError(f"CONFLICT ERROR: payload already has the key, {k}. Can not overwrite.")
                elif isinstance(v, io.IOBase):
                    data.add_field(k, v)
                elif isinstance(v, File):
                    data.add_field(k, v.body, filename=v.name, content_type=v.type)
                else:
                    raise RuntimeError(
                        "INVALID FILE: invalid value for files. Must be either and instance of io.IOBase(using open), "
                        "sanic File object, or bytestring.")

        return data


    async def _dispatch_fetch(self, method, request, **kwargs):

        request_params = {
            "method": method,
            "url": str(request.url),
            "headers": request.headers,
            "data": request.body
        }

        timeout = kwargs.pop('request_timeout')
        if timeout:
            request_params.update({"timeout": timeout})

        async with self.session.request(**request_params) as resp:
            await resp.read()
            return resp

    async def _dispatch(self, method, endpoint, *, query_params, payload, files, headers,
                        propagate_error=False, skip_breaker=False, request_timeout=None):
        """

        :param method:
        :param endpoint:
        :param query_params: dict
        :param payload:  dict
        :param files: dict
        :param headers: dict
        :param propagate_error: bool
        :param skip_breaker: bool
        :param request_timeout: int
        :return:
        """

        url = self._construct_url(endpoint)
        headers = self._prepare_headers(headers, files)
        data = self._prepare_body(headers, payload, files)

        outbound_request = aiohttp.ClientRequest(method, url,
                                                 params=query_params, headers=headers, data=data)
        # outbound_request.headers.add("Content-Type", outbound_request.body.content_type)

        try:
            _response_obj = await self._dispatch_fetch(method, outbound_request, skip_breaker=skip_breaker,
                                                       request_timeout=request_timeout)

            if propagate_error:
                _response_obj.raise_for_status()

            response_status = _response_obj.status
            response = try_json_decode(await _response_obj.json())

        except aiohttp.client_exceptions.ClientResponseError as e:
            response = try_json_decode(await e.message)
            try:
                status_code = e.code
            except AttributeError:
                status_code = getattr(e, 'status', status.HTTP_500_INTERNAL_SERVER_ERROR)

            error_code = GlobalErrorCodes.invalid_usage if status_code == status.HTTP_400_BAD_REQUEST \
                else GlobalErrorCodes.unknown_error
            exc = exceptions.APIException(description=response.get('description', response),
                                          error_code=response.get('error_code', error_code),
                                          status_code=status_code)
            exc.message = response.get('message', GlobalErrorCodes.unknown_error.name)
            raise exc

        except aiohttp.client_exceptions.ClientConnectionError as e:
            # https://aiohttp.readthedocs.io/en/v3.0.1/client_reference.html#hierarchy-of-exceptions
            if isinstance(e, aiohttp.client_exceptions.ClientConnectorError):
                """subset of connection errors that are initiated by an OSError exception"""
                if e.errno == 61:
                    msg = settings.SERVICE_UNAVAILABLE_MESSAGE.format(self._service_name)
                    exc = exceptions.ServiceUnavailable503Error(description=msg,
                                                                error_code=GlobalErrorCodes.service_unavailable,
                                                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
                else:
                    exc = exceptions.APIException(description=e.strerror,
                                                  error_code=GlobalErrorCodes.unknown_error,
                                                  status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            elif isinstance(e, aiohttp.client_exceptions.ServerConnectionError):
                """ server connection related errors """

                if isinstance(e, aiohttp.client_exceptions.ServerDisconnectedError):
                    """ server disconnected """
                    exc = exceptions.ServiceUnavailable503Error(description=e.message,
                                                                error_code=GlobalErrorCodes.service_unavailable,
                                                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
                elif isinstance(e, aiohttp.client_exceptions.ServerTimeoutError):
                    """server operation timeout, (read timeout, etc)"""
                    exc = exceptions.APIException(description=e.args[0],
                                                  error_code=GlobalErrorCodes.service_timeout,
                                                  status_code=status.HTTP_504_GATEWAY_TIMEOUT)
                else:
                    msg = settings.SERVICE_UNAVAILABLE_MESSAGE.format(self._service_name)
                    exc = exceptions.ServiceUnavailable503Error(description=msg,
                                                                error_code=GlobalErrorCodes.service_unavailable,
                                                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            elif isinstance(e, aiohttp.client_exceptions.ServerFingerprintMismatch):
                """server fingerprint mismatch"""
                msg = "Server Fingerprint Mismatch"
                exc = exceptions.APIException(description=msg,
                                              error_code=GlobalErrorCodes.server_signature_error,
                                              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                exc = exceptions.APIException(description=e.args[0],
                                              error_code=GlobalErrorCodes.unknown_error,
                                              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            raise exc
        except asyncio.TimeoutError:
            exc = exceptions.ServiceTimeoutError(description=f'{self.service_name} has timed out.',
                                                 error_code=GlobalErrorCodes.service_timeout,
                                                 status_code=status.HTTP_504_GATEWAY_TIMEOUT)
            raise exc
        except aiohttp.client_exceptions.ClientPayloadError as e:
            raise
        except aiohttp.client_exceptions.InvalidURL as e:
            raise

        return response, response_status
