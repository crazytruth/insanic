import aiohttp
import datetime
import ujson as json

from asyncio import get_event_loop

from sanic.constants import HTTP_METHODS
from yarl import URL

from insanic import exceptions, status
from insanic.authentication.handlers import jwt_service_encode_handler, jwt_service_payload_handler
from insanic.conf import settings
from insanic.connections import get_connection
from insanic.errors import GlobalErrorCodes
from insanic.functional import cached_property_with_ttl
from insanic.log import logger
from insanic.scopes import is_docker

IS_INFUSED = False
try:
    from infuse import AioCircuitBreaker, CircuitAioRedisStorage, STATE_CLOSED, \
        CircuitBreakerError

    IS_INFUSED = True
except (ImportError, ModuleNotFoundError) as e:
    if settings.get('MMT_ENV') == "production":
        raise e
    else:
        CircuitBreakerError = Exception
        IS_INFUSED = False
        logger.warn("Running without [infuse]. For production infuse is required!")


class ServiceRegistry(dict):
    __instance = None
    _conn = None

    def __new__(cls, *args, **kwargs):
        if ServiceRegistry.__instance is None:
            ServiceRegistry.__instance = dict.__new__(cls)
            ServiceRegistry.__instance.update(**{s: None for s in settings.SERVICE_CONNECTIONS})
        return ServiceRegistry.__instance

    def __setitem__(self, key, value):
        raise RuntimeError("Unable to set new service. Append {0} SERVICE_CONNECTIONS "
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


class Service:

    remove_headers = ["content-length", 'user-agent', 'host', 'postman-token']

    def __init__(self, service_type):

        self._registry = ServiceRegistry()
        self._service_name = service_type
        self._session = None
        self._breaker = None
        self._service_auth_token = jwt_service_encode_handler(jwt_service_payload_handler(self))

    @property
    def service_name(self):
        return self._service_name

    def _service_spec(self, raise_exception=False):
        spec = settings.SERVICE_LIST.get(self._service_name, {})
        if spec == {} and raise_exception:
            self.raise_503()
        return spec

    def raise_503(self):
        raise exceptions.ServiceUnavailable503Error(detail=f"{self._service_name} is currently unavailable.",
                                                    error_code=GlobalErrorCodes.service_unavailable,
                                                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

    @cached_property_with_ttl(ttl=60)
    def schema(self):
        return self._service_spec().get('schema', 'http')

    @cached_property_with_ttl(ttl=60)
    def host(self):
        host = self._service_spec(True).get('host')
        return host

    @cached_property_with_ttl(ttl=60)
    def port(self):
        return self._service_spec(True).get('internal_service_port' if is_docker else 'external_service_port')

    @property
    def url(self):
        url_partial_path = "/api/v1/"
        return URL(f"{self.schema}://{self.host}:{self.port}{url_partial_path}")

    @property
    async def breaker(self):
        if self._breaker is None:
            # conn = await aioredis.create_redis((settings.REDIS_HOST, settings.REDIS_PORT),
            #                                    encoding='utf-8', db=settings.REDIS_DB)
            conn = await get_connection('infuse')

            self._registry.conn = conn

            circuit_breaker_storage = await CircuitAioRedisStorage.initialize(STATE_CLOSED, conn, self._service_name)
            # await circuit_breaker_storage.init_storage(STATE_CLOSED)
            self._breaker = await AioCircuitBreaker.initialize(fail_max=settings.INFUSE_MAX_FAILURE,
                                                               reset_timeout=settings.INFUSE_RESET_TIMEOUT,
                                                               state_storage=circuit_breaker_storage,
                                                               listeners=[])
        return self._breaker

    @property
    def session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(loop=get_event_loop(),
                                                  connector=aiohttp.TCPConnector(limit_per_host=10))
        return self._session

    def _construct_url(self, endpoint, query_params={}):

        url = self.url.with_path(endpoint)
        if len(query_params):
            url = url.with_query(**query_params)
        return url
        # return urljoin(self._base_url, endpoint)

    async def http_dispatch(self, method, endpoint, req_ctx={}, *, query_params={}, payload={}, headers={},
                            return_obj=True, propagate_error=False, skip_breaker=False, include_status_code=False):

        if method.upper() not in HTTP_METHODS:
            raise ValueError("{0} is not a valid method.".format(method))

        response, status_code = await self._dispatch(method, endpoint, req_ctx,
                                                     query_params=query_params, payload=payload,
                                                     headers=headers, return_obj=return_obj,
                                                     propagate_error=propagate_error,
                                                     skip_breaker=skip_breaker,
                                                     include_status_code=include_status_code)

        response_text = await response.text()
        response_final = self._try_json_decode(response_text)

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
            {"MMT-Authorization": f"{settings.JWT_SERVICE_AUTH['JWT_AUTH_HEADER_PREFIX']} {self._service_auth_token}"})

        return headers

    def _try_json_decode(self, data):
        try:
            data = json.loads(data)
        except ValueError:
            pass
        return data

    async def _dispatch(self, method, endpoint, req_ctx, *, query_params={}, payload={}, headers={}, return_obj=True,
                        propagate_error=False, skip_breaker=False, include_status_code=False):

        request_method = getattr(self.session, method.lower(), None)

        url = self._construct_url(endpoint, query_params)
        headers = self._prepare_headers(headers)

        if not isinstance(payload, str):
            payload = json.dumps(payload)

        outbound_request = aiohttp.ClientRequest(method, url, headers=headers, data=payload)

        # opentracing.tracer.before_service_request(outbound_request, req_ctx, service_name=self._service_name)

        try:
            if IS_INFUSED and not skip_breaker:
                breaker = await self.breaker
                # resp = await request_method(str(outbound_request.url), headers=outbound_request.headers, data=payload)

                resp = await breaker.call(request_method, str(outbound_request.url),
                                          headers=outbound_request.headers, data=payload)
            else:
                resp = await request_method(str(outbound_request.url), headers=outbound_request.headers, data=payload)

            response = await resp.text()
            if propagate_error:
                resp.raise_for_status()

            response_status = resp.status
            response = self._try_json_decode(response)

        except aiohttp.client_exceptions.ClientResponseError as e:
            response = self._try_json_decode(response)
            status_code = e.code
            error_code = GlobalErrorCodes.invalid_usage if status_code == status.HTTP_400_BAD_REQUEST \
                else GlobalErrorCodes.unknown_error
            exc = exceptions.APIException(detail=response.get('description', response),
                                          error_code=response.get('error_code',
                                                                  error_code),
                                          status_code=status_code)
            exc.default_detail = response.get('message', GlobalErrorCodes.unknown_error.name)
            raise exc

        except aiohttp.client_exceptions.ClientConnectionError as e:

            if isinstance(e, aiohttp.client_exceptions.ClientOSError):
                """subset of connection errors that are initiated by an OSError exception"""
                if e.errno == 61:
                    msg = "Client Connector Error[{0}]: {1}".format(self._service_name, e.strerror)
                    exc = exceptions.ServiceUnavailable503Error(detail=msg,
                                                                error_code=GlobalErrorCodes.service_unavailable,
                                                                status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
                else:
                    exc = exceptions.APIException(detail=e.strerror,
                                                  error_code=GlobalErrorCodes.unknown_error,
                                                  status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            elif isinstance(e, aiohttp.client_exceptions.ServerConnectionError):
                """ server connection related errors """
                if settings.get('MMT_ENV', "") == "production":
                    msg = "Service unavailable. Please try again later."
                else:
                    msg = "Cannot connect to {0}. Please try again later".format(self._service_name)

                exc = exceptions.ServiceUnavailable503Error(detail=msg,
                                                            error_code=GlobalErrorCodes.service_unavailable,
                                                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            elif isinstance(e, aiohttp.client_exceptions.ServerDisconnectedError):
                """ server disconnected """
                exc = exceptions.ServiceUnavailable503Error(detail=e.message,
                                                            error_code=GlobalErrorCodes.service_unavailable,
                                                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            elif isinstance(e, aiohttp.client_exceptions.ServerTimeoutError):
                """server operation timeout, (read timeout, etc)"""
                exc = exceptions.APIException(detail=e.message,
                                              error_code=GlobalErrorCodes.service_timeout,
                                              status_code=status.HTTP_504_GATEWAY_TIMEOUT)
            elif isinstance(e, aiohttp.client_exceptions.ServerFingerprintMismatch):
                """server fingerprint mismatch"""
                msg = "Server Fingerprint Mismatch"
                exc = exceptions.APIException(detail=msg,
                                              error_code=GlobalErrorCodes.server_signature_error,
                                              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                exc = exceptions.APIException(detail=e.message,
                                              error_code=GlobalErrorCodes.unknown_error,
                                              status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

            raise exc
        except aiohttp.client_exceptions.ClientPayloadError as e:
            raise
        except CircuitBreakerError as e:

            exc = exceptions.ServiceUnavailable503Error(detail="{0}: {1}".format(e.args[0], self._service_name),
                                                        error_code=GlobalErrorCodes.service_unavailable,
                                                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            raise exc
        finally:
            pass

        return resp, response_status
