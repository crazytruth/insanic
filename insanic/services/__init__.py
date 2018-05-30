import aiohttp
import aiotask_context
import datetime
import ujson as json
import warnings

from asyncio import get_event_loop

from sanic.constants import HTTP_METHODS
from yarl import URL

from insanic import exceptions, status
from insanic.authentication.handlers import jwt_service_encode_handler, jwt_service_payload_handler
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.functional import cached_property_with_ttl
from insanic.models import AnonymousUser
from insanic.services.response import InsanicResponse
from insanic.scopes import is_docker
from insanic.utils import try_json_decode


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
        user = aiotask_context.get(settings.TASK_CONTEXT_REQUEST_USER) or dict(AnonymousUser)
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
                settings.SERVICE_GLOBAL_PORT)
        return _port

    @property
    def url(self):
        url_partial_path = "/api/v1/"
        return URL(f"{self.schema}://{self.host}:{self.port}{url_partial_path}")

    @property
    def session(self):
        if self._session is None or self._session.loop.is_closed() is True:
            self._session = aiohttp.ClientSession(loop=get_event_loop(),
                                                  connector=aiohttp.TCPConnector(limit_per_host=25,
                                                                                 ttl_dns_cache=300),
                                                  response_class=InsanicResponse)
        return self._session

    def _construct_url(self, endpoint, query_params={}):
        url = self.url.with_path(endpoint)
        if len(query_params):
            url = url.with_query(**query_params)
        return url

    async def http_dispatch(self, method, endpoint, req_ctx=None, *, query_params={}, payload={}, headers={},
                            propagate_error=False, skip_breaker=False, include_status_code=False):

        if req_ctx is not None:
            warnings.warn("`req_ctx`, the 3rd argument is deprecated.  Please remove. "
                          "Sending this will do absolutely nothing.")

        if method.upper() not in HTTP_METHODS:
            raise ValueError("{0} is not a valid method.".format(method))

        response, status_code = await self._dispatch(method, endpoint,
                                                     query_params=query_params, payload=payload,
                                                     headers=headers,
                                                     propagate_error=propagate_error,
                                                     skip_breaker=skip_breaker)

        response_text = await response.text()
        response_final = try_json_decode(response_text)

        if include_status_code:
            return response_final, status_code
        return response_final

    def _prepare_headers(self, headers):
        for h in self.remove_headers:
            if h in headers:
                del headers[h]

        headers.update({"Accept": "application/json"})
        headers.update({"Content-Type": "application/json"})
        # headers.update({"Referrer": "https://staging.mymusictaste.com"})
        headers.update({"Date": datetime.datetime.utcnow()
                       .replace(tzinfo=datetime.timezone.utc).strftime("%a, %d %b %y %T %z")})

        headers.update(
            {"Authorization": f"{settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX']} {self.service_auth_token}"})

        return headers

    async def _dispatch_fetch(self, method, request, **kwargs):

        async with self.session.request(method, str(request.url), headers=request.headers,
                                        data=request.body) as resp:
            return resp

    async def _dispatch(self, method, endpoint, *, query_params={}, payload={}, headers={},
                        propagate_error=False, skip_breaker=False):

        url = self._construct_url(endpoint, query_params)
        headers = self._prepare_headers(headers)

        if not isinstance(payload, str):
            payload = json.dumps(payload)

        outbound_request = aiohttp.ClientRequest(method, url, headers=headers, data=payload)

        try:
            _response_obj = await self._dispatch_fetch(method, outbound_request, skip_breaker=skip_breaker)

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
        except aiohttp.client_exceptions.ClientPayloadError as e:
            raise
        except aiohttp.client_exceptions.InvalidURL as e:
            raise

        return response, response_status
