import typing

from packaging import version
from httpx import __version__, Timeout as HTTPXTimeout, Request, Response

try:
    from httpx.config import (
        UnsetType,
        UNSET,
        TimeoutTypes,
        VerifyTypes,
        CertTypes,
        DEFAULT_TIMEOUT_CONFIG,
        DEFAULT_MAX_REDIRECTS,
    )
except ModuleNotFoundError:
    from httpx._config import (
        UnsetType,
        UNSET,
        TimeoutTypes,
        VerifyTypes,
        CertTypes,
        DEFAULT_TIMEOUT_CONFIG,
        DEFAULT_MAX_REDIRECTS,
    )

try:
    from httpx.models import (
        QueryParamTypes,
        HeaderTypes,
        CookieTypes,
        URLTypes,
    )
except ModuleNotFoundError:
    from httpx._models import (
        QueryParamTypes,
        HeaderTypes,
        CookieTypes,
        URLTypes,
    )

try:

    from httpx.models import AuthTypes, ProxiesTypes
except ModuleNotFoundError:
    from httpx._types import AuthTypes, ProxiesTypes
except ImportError:
    from httpx.auth import AuthTypes
    from httpx.config import ProxiesTypes

IS_HTTPX_VERSION_0_15 = version.parse("0.15") <= version.parse(__version__)
IS_HTTPX_VERSION_0_14 = version.parse("0.14") <= version.parse(__version__)
IS_HTTPX_VERSION_0_11 = (
    version.parse("0.11") <= version.parse(__version__) < version.parse("0.12")
)


if IS_HTTPX_VERSION_0_15:
    from httpx import (  # noqa: ignore=F401
        Limits as HTTPXLimits,
        AsyncClient as HTTPXClient,
        HTTPError,
        HTTPStatusError,
        RequestError,
        TransportError,
        InvalidURL,
        NotRedirectResponse,
        CookieConflict,
        StreamError,
    )

    from httpcore import AsyncHTTPTransport
elif IS_HTTPX_VERSION_0_11:
    from httpx import PoolLimits as HTTPXLimits

    AsyncHTTPTransport = str  # for transports typing

    from httpx import AsyncClient as HTTPXClient, HTTPError  # noqa: ignore=F401

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

    class InvalidURL(HTTPError):
        pass

    class NotRedirectResponse(HTTPError):
        pass

    class CookieConflict(HTTPError):
        pass

    class StreamError(HTTPError):
        pass

    RequestError = HTTPError
    TransportError = HTTPError
else:
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

    class InvalidURL(HTTPError):
        pass

    class NotRedirectResponse(HTTPError):
        pass

    class CookieConflict(HTTPError):
        pass

    class StreamError(HTTPError):
        pass


class Limits(HTTPXLimits):
    def __init__(
        self,
        *,
        max_connections: int = None,
        max_keepalive_connections: int = None,
    ):
        kwargs = {
            "max_keepalive_connections"
            if IS_HTTPX_VERSION_0_14
            else "soft_limit": max_keepalive_connections,
            "max_connections"
            if IS_HTTPX_VERSION_0_14
            else "hard_limit": max_connections,
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
            "connect_timeout"
            if not IS_HTTPX_VERSION_0_14
            else "connect": connect,
            "read_timeout" if not IS_HTTPX_VERSION_0_14 else "read": read,
            "write_timeout" if not IS_HTTPX_VERSION_0_14 else "write": write,
            "pool_timeout" if not IS_HTTPX_VERSION_0_14 else "pool": pool,
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
        if IS_HTTPX_VERSION_0_14:
            kwargs = {
                "transport": transport,
                "limits": limits,
            }

        else:
            kwargs = {
                "dispatch": None,
                "backend": "auto",
                "uds": None,
                "pool_limits": limits,
                "http2": http2,
            }

        super().__init__(
            auth=auth,
            params=params,
            headers=headers,
            cookies=cookies,
            verify=verify,
            cert=cert,
            proxies=proxies,
            timeout=timeout,
            max_redirects=max_redirects,
            base_url=base_url,
            app=app,
            trust_env=trust_env,
            **kwargs,
        )

    def aclose(self):
        if hasattr(super(), "aclose"):
            return super().aclose()
        else:
            return super().close()

    def _merge_url(self, url: URLTypes):
        if not IS_HTTPX_VERSION_0_15:
            return super().merge_url(url)
        else:
            return super()._merge_url(url)

    def _merge_queryparams(
        self, params: QueryParamTypes = None
    ) -> typing.Optional[QueryParamTypes]:
        if not IS_HTTPX_VERSION_0_15:
            return super().merge_queryparams(params)
        else:
            return super()._merge_queryparams(params)
