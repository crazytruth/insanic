import typing

from packaging import version
from httpx import __version__, Timeout as HTTPXTimeout, Request, Response
from httpx.config import (
    UnsetType,
    UNSET,
    TimeoutTypes,
    VerifyTypes,
    CertTypes,
    DEFAULT_TIMEOUT_CONFIG,
    DEFAULT_MAX_REDIRECTS,
)
from httpx.models import (
    AuthTypes,
    QueryParamTypes,
    HeaderTypes,
    CookieTypes,
    ProxiesTypes,
    URLTypes,
)

HTTPX_VERSION_CHANGE = version.parse("0.14.0")
HTTPX_LEGACY = version.parse(__version__) < HTTPX_VERSION_CHANGE

if HTTPX_LEGACY:
    # if httpx version is < 0.14.0
    from httpx import PoolLimits as HTTPXLimits
    from httpx import Client as HTTPXClient, HTTPError

    AsyncHTTPTransport = str  # for transports typing

    class HTTPStatusError(HTTPError):
        """
            The response had an error HTTP status of 4xx or 5xx.
            May be raised when calling `response.raise_for_status()`
            """

        def __init__(
            self, message: str, *, request: "Request", response: "Response"
        ) -> None:
            super().__init__(message, request=request)
            self.response = response

    RequestError = HTTPError
    TransportError = HTTPError

else:
    from httpx import (  # noqa: ignore=F401
        Limits as HTTPXLimits,
        AsyncClient as HTTPXClient,
        AsyncHTTPTransport,
        HTTPStatusError,
        TransportError,
        RequestError,
    )


class Limits(HTTPXLimits):
    def __init__(
        self,
        *,
        max_connections: int = None,
        max_keepalive_connections: int = None,
    ):
        kwargs = {
            "soft_limit"
            if HTTPX_LEGACY
            else "max_keepalive_connections": max_keepalive_connections,
            "hard_limit"
            if HTTPX_LEGACY
            else "max_connections": max_connections,
        }

        super().__init__(**kwargs)


DEFAULT_LIMITS = Limits(max_connections=100, max_keepalive_connections=20)


class Timeout(HTTPXTimeout):
    def __init__(
        self,
        timeout: typing.Union[TimeoutTypes, UnsetType] = UNSET,
        *,
        connect: typing.Union[None, float, UnsetType] = UNSET,
        read: typing.Union[None, float, UnsetType] = UNSET,
        write: typing.Union[None, float, UnsetType] = UNSET,
        pool: typing.Union[None, float, UnsetType] = UNSET,
    ):
        kwargs = {
            "timeout": timeout,
            "connect_timeout" if HTTPX_LEGACY else "connect": connect,
            "read_timeout" if HTTPX_LEGACY else "read": read,
            "write_timeout" if HTTPX_LEGACY else "write": write,
            "pool_timeout" if HTTPX_LEGACY else "pool": pool,
        }

        super().__init__(**kwargs)


class AsyncClient(HTTPXClient):
    def __init__(
        self,
        *,
        auth: AuthTypes = None,
        params: QueryParamTypes = None,
        headers: HeaderTypes = None,
        cookies: CookieTypes = None,
        verify: VerifyTypes = True,
        cert: CertTypes = None,
        http2: bool = False,
        proxies: ProxiesTypes = None,
        timeout: TimeoutTypes = DEFAULT_TIMEOUT_CONFIG,
        limits: Limits = DEFAULT_LIMITS,
        pool_limits: Limits = None,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        base_url: URLTypes = "",
        transport: AsyncHTTPTransport = None,
        app: typing.Callable = None,
        trust_env: bool = True,
    ):
        # arg differences with <0.14.0
        # dispatch, backend, uds
        # transport >0.14.0
        if HTTPX_LEGACY:
            kwargs = {
                "dispatch": None,
                "backend": "auto",
                "uds": None,
                "pool_limits": limits,
            }
        else:
            kwargs = {
                "transport": transport,
                "limits": limits,
            }

        super().__init__(
            auth=auth,
            params=params,
            headers=headers,
            cookies=cookies,
            verify=verify,
            cert=cert,
            http2=http2,
            proxies=proxies,
            timeout=timeout,
            max_redirects=max_redirects,
            base_url=base_url,
            app=app,
            trust_env=trust_env,
            **kwargs,
        )
