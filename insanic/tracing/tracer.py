import traceback
import ujson as json

from insanic import __version__
from insanic.conf import settings
from insanic.log import logger
from insanic.tracing.utils import get_safe_dict, abbreviate_for_xray

try:
    from aws_xray_sdk.core import xray_recorder
    from aws_xray_sdk.core.models import http
    from aws_xray_sdk.ext.util import calculate_sampling_decision, \
        calculate_segment_name, construct_xray_header
except ImportError:
    pass


class InsanicXRayMiddleware:

    def __init__(self, app, loop):

        self.app = app
        logger.debug("[XRAY] Initializing xray middleware")

        @app.middleware('request')
        async def start_trace(request):
            if not request.path.endswith("/health/"):
                await self._before_request(request)

        @app.middleware('response')
        async def end_trace(request, response):
            if not request.path.endswith("/health/"):
                await self._after_request(request, response)

            if hasattr(request, "span"):
                response.span = request.span
            return response

        # patch()

    async def _before_request(self, request):
        headers = request.headers
        xray_header = construct_xray_header(headers)

        name = calculate_segment_name(request.host, xray_recorder)

        sampling_decision = calculate_sampling_decision(
            trace_header=xray_header,
            recorder=xray_recorder,
            service_name=request.host,
            method=request.method,
            path=request.path,
        )

        segment = xray_recorder.begin_segment(
            name=name,
            traceid=xray_header.root,
            parent_id=xray_header.parent,
            sampling=sampling_decision,
        )
        segment.save_origin_trace_header(xray_header)
        segment.put_annotation('insanic_version', __version__)
        segment.put_annotation("service_version", settings.get('SERVICE_VERSION'))
        segment.put_http_meta(http.URL, request.url)
        segment.put_http_meta(http.METHOD, request.method)
        segment.put_http_meta(http.USER_AGENT, headers.get('User-Agent'))

        client_ip = headers.get('X-Forwarded-For') or headers.get('HTTP_X_FORWARDED_FOR') or request.ip[0]
        if client_ip:
            segment.put_http_meta(http.CLIENT_IP, client_ip)
            segment.put_http_meta(http.X_FORWARDED_FOR, True)
        else:
            segment.put_http_meta(http.CLIENT_IP, request.remote_addr)

        attributes = ['args', 'content_type', 'cookies', 'data',
                      'host', 'ip', 'method', 'path', 'scheme', 'url', ]
        for attr in attributes:
            if hasattr(request, attr):
                payload = getattr(request, attr)

                if isinstance(payload, dict):
                    payload = abbreviate_for_xray(get_safe_dict(payload))
                payload = json.dumps(payload)

                segment.put_metadata(f"{attr}", payload, "request")

        request.span = segment

    async def _after_request(self, request, response):
        segment = xray_recorder.current_segment()

        # setting user was moved from _before_request,
        # because calling request.user authenticates, and if
        # authenticators are not set for request, will end not being
        # able to authenticate correctly
        user = await request.user
        if user.id:
            segment.set_user(user.id)
            segment.put_annotation('user__level', user.level)

        segment.put_http_meta(http.STATUS, response.status)

        cont_len = response.headers.get('Content-Length')
        segment.put_annotation('response', response.body.decode())
        if cont_len:
            segment.put_http_meta(http.CONTENT_LENGTH, int(cont_len))

        if hasattr(response, 'exception'):
            stack = traceback.extract_stack(limit=xray_recorder.max_trace_back)
            segment.add_exception(response.exception, stack)

        xray_recorder.end_segment()
        return response
