import aiohttp
import hashlib
import opentracing
import ujson as json

from asyncio import get_event_loop
from collections import namedtuple
from sanic.constants import HTTP_METHODS
from urllib.parse import urlunsplit, urljoin
from yarl import URL

from insanic import exceptions, status
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.utils import to_object


class InterServiceAuth(namedtuple('InterServiceAuth', ['prefix', 'token'])):
    """Http basic authentication helper.

    :param str login: Login
    :param str password: Password
    :param str encoding: (optional) encoding ('latin1' by default)
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
    def __init__(self, *args, **kwargs):

        self._registry = {s: None for s in settings.SERVICES.keys()}

        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        raise RuntimeError("Unable to set new service.")

    def __getitem__(self, item):

        if item not in self._registry:
            raise RuntimeError("{0} service does not exist. Only the following: {1}"
                               .format(item, ", ".join(self._registry.keys())))

        if self._registry[item] is None:
            self._registry[item] = Service(item)

        return self._registry[item]

registry = ServiceRegistry()

class Service:

    def __init__(self, service_type):

        self._service_name = service_type
        self._session = None


        if service_type not in settings.SERVICES.keys():
            raise AssertionError("Invalid service type.")
        if settings.MMT_ENV == "local":
            api_host = settings.API_GATEWAY_HOST
        else:
            api_host = "mmt-server-{0}".format(service_type)

        # url_scheme = settings.API_GATEWAY_SCHEME
        # service_host = api_host
        # service_port = settings.SERVICES[service_type].get('externalserviceport')
        # self._url_netloc = "{0}:{1}".format(self._service_host, self._service_port)
        url_partial_path = "/api/v1/{0}".format(service_type)
        # self._base_url = urlunsplit((settings.API_GATEWAY_SCHEME, self._url_netloc, self._url_partial_path, "", ""))
        self.url = URL.build(scheme=settings.API_GATEWAY_SCHEME, host=api_host, port=settings.SERVICES[service_type].get('externalserviceport'), path=url_partial_path)

        self.remove_headers = ["content-length", 'user-agent', 'host', 'postman-token']

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


    async def http_dispatch(self, method, endpoint, req_ctx, *, query_params={}, payload={}, headers={}, return_obj=True, propagate_error=False):

        if method.upper() not in HTTP_METHODS:
            raise ValueError("{0} is not a valid method.".format(method))

        return await self._dispatch(method, endpoint, req_ctx, query_params=query_params, payload=payload, headers=headers, return_obj=return_obj, propagate_error=propagate_error)

    def _prepare_headers(self, headers):
        for h in self.remove_headers:
            if h in headers:
                del headers[h]

        headers.update({"accept": "application/json"})

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
            async with request_method(str(outbound_request.url), headers=outbound_request.headers, data=payload) as resp:
                response = await resp.text()
                if propagate_error:
                    resp.raise_for_status()

                response_status = resp.status
                response = self._try_json_decode(response)

        except aiohttp.client_exceptions.ClientResponseError as e:
            response = self._try_json_decode(response)
            exc = exceptions.APIException(detail=response['description'],
                                          error_code=response['error_code'],
                                          status_code=e.code)
            exc.default_detail = response['message']
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
        finally:
            pass


        if return_obj:
            return to_object(response)
        else:
            return response



