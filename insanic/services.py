import aiohttp
import gzip
import hashlib
import opentracing
import ujson as json

from asyncio import get_event_loop
from collections import namedtuple
from sanic.constants import HTTP_METHODS
from yarl import URL

from insanic import exceptions, status
from insanic.conf import settings
from insanic.connections import get_connection, get_future_connection
from insanic.errors import GlobalErrorCodes
from insanic.log import log
from insanic.utils import to_object

try:
    from infuse import AioCircuitBreaker, CircuitAioRedisStorage, STATE_CLOSED, \
        CircuitBreakerError

    IS_INFUSED = True
except ImportError as e:
    if settings.MMT_ENV == "production":
        raise e
    else:
        CircuitBreakerError = Exception
        IS_INFUSED = False
        log.warn("Running without [infuse]. For production infuse is required!")


class InterServiceAuth(namedtuple('InterServiceAuth', ['prefix', 'token'])):
    """Http basic authentication helper.
    """

    def __new__(cls, prefix, token=''):
        if prefix is None:
            raise ValueError('None is not allowed as login value')

        if token is None:
            raise ValueError('None is not allowed as password value')

        return super().__new__(cls, prefix, token)

    @classmethod
    def decode(cls, auth_header):
        """Create a :class:`BasicAuth` object from an ``Authorization`` HTTP
        header."""
        split = auth_header.strip().split(' ')
        if len(split) != 2:
            raise ValueError('Could not parse authorization header.')

        return cls(split[0], split[1])

    def encode(self):
        """Encode credentials."""
        return '%s %s' % (self.prefix, self.token)


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

# registry = ServiceRegistry()

class Service:

    def __init__(self, service_type):

        self._registry = ServiceRegistry()
        self._service_name = service_type
        self._session = None
        self._breaker = None


        if service_type not in settings.SERVICES.keys():
            raise AssertionError("Invalid service type.")
        if settings.MMT_ENV == "local":
            api_host = settings.API_GATEWAY_HOST
        else:
            api_host = "mmt-server-{0}".format(service_type)

        url_partial_path = "/api/v1/{0}".format(service_type)
        self.url = URL.build(scheme=settings.API_GATEWAY_SCHEME, host=api_host, port=settings.SERVICES[service_type].get('externalserviceport'), path=url_partial_path)

        self.remove_headers = ["content-length", 'user-agent', 'host', 'postman-token']

    @property
    async def breaker(self):
        if self._breaker is None:

            conn = await get_connection('redis')
            conn = await conn.acquire()
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
                            return_obj=True, propagate_error=False):

        if method.upper() not in HTTP_METHODS:
            raise ValueError("{0} is not a valid method.".format(method))

        return await self._dispatch(method, endpoint, req_ctx, query_params=query_params, payload=payload,
                                    headers=headers, return_obj=return_obj, propagate_error=propagate_error)

    def _prepare_headers(self, headers):
        for h in self.remove_headers:
            if h in headers:
                del headers[h]

        headers.update({"accept": "application/json"})
        headers.update({"content-type": "application/json"})

        m = hashlib.sha256()
        m.update('mmt-server-{0}'.format(self._service_name).encode())
        m.update(settings.WEB_SECRET_KEY.encode())

        headers.update({"mmt-token": m.hexdigest()})
        return headers

    def _try_json_decode(self, data):
        try:
            data = json.loads(data)
        except ValueError:
            pass
        return data

    async def _dispatch(self, method, endpoint, req_ctx, query_params={}, payload={}, headers={}, return_obj=True, propagate_error=False):

        request_method = getattr(self.session, method.lower(), None)

        url = self._construct_url(endpoint, query_params)
        headers = self._prepare_headers(headers)

        if not isinstance(payload, str):
            payload = json.dumps(payload)

        outbound_request = aiohttp.ClientRequest(method, url, headers=headers, data=payload)

        opentracing.tracer.before_service_request(outbound_request, req_ctx, service_name=self._service_name)

        try:
            if IS_INFUSED:
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
            error_code = GlobalErrorCodes.invalid_usage if status_code == status.HTTP_400_BAD_REQUEST else GlobalErrorCodes.unknown_error
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
                if settings.MMT_ENV == "production":
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
            pass
        except CircuitBreakerError as e:

            exc = exceptions.ServiceUnavailable503Error(detail="{0}: {1}".format(e.args[0], self._service_name),
                                                        error_code=GlobalErrorCodes.service_unavailable,
                                                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
            raise exc
        finally:
            pass

        if return_obj:
            return to_object(response)
        else:
            return response



