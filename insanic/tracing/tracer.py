import traceback

from sanic.log import log

from insanic import __version__
from insanic.tracing.patch import patch
from insanic.tracing.context import AsyncContext
from insanic.tracing.core import xray_recorder

from aws_xray_sdk.core.models import http
from aws_xray_sdk.ext.util import calculate_sampling_decision, \
    calculate_segment_name, construct_xray_header


class InsanicXRayMiddleware:

    def __init__(self, app, loop):

        recorder = xray_recorder

        recorder.configure(service=app.tracing_service_name, context=AsyncContext(loop=loop),
                           sampling=app.sampling_rules, daemon_address='xray:2000',
                           context_missing="LOG_ERROR" if app.config.MMT_ENV=="local" else "RUNTIME_ERROR")

        self.app = app
        log.info("initializing xray middleware")

        self._recorder = recorder

        @app.middleware('request')
        async def start_trace(request):
            if request.path != "/health":
                # self._before_request_fn(request, traced_attributes)

                await self._before_request(request)

        @app.middleware('response')
        def end_trace(request, response):
            if request.path != "/health":
                self._after_request(request, response)
            return response

        patch()

    async def _before_request(self, request):
        headers = request.headers
        xray_header = construct_xray_header(headers)

        name = calculate_segment_name(request.host, self._recorder)

        sampling_decision = calculate_sampling_decision(
            trace_header=xray_header,
            recorder=self._recorder,
            service_name=request.host,
            method=request.method,
            path=request.path,
        )

        segment = self._recorder.begin_segment(
            name=name,
            traceid=xray_header.root,
            parent_id=xray_header.parent,
            sampling=sampling_decision,
        )

        segment.put_annotation('insanic_version', __version__)
        segment.put_http_meta(http.URL, request.url)
        segment.put_http_meta(http.METHOD, request.method)
        segment.put_http_meta(http.USER_AGENT, headers.get('User-Agent'))

        client_ip = headers.get('X-Forwarded-For') or headers.get('HTTP_X_FORWARDED_FOR') or request.ip[0]
        if client_ip:
            segment.put_http_meta(http.CLIENT_IP, client_ip)
            segment.put_http_meta(http.X_FORWARDED_FOR, True)
        else:
            segment.put_http_meta(http.CLIENT_IP, request.remote_addr)

        attributes = ['args', 'body', ' content_type', 'cookies', 'data',
                      'host', 'ip', 'method', 'path', 'scheme', 'url']
        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    segment.put_metadata("{0}".format(attr), payload, "request")

        user = await request.user
        if user.id:
            segment.set_user(user.id)

        request.span = segment

    def _after_request(self, request, response):
        segment = self._recorder.current_segment()
        segment.put_http_meta(http.STATUS, response.status)

        cont_len = response.headers.get('Content-Length')
        if cont_len:
            segment.put_annotation('response', response.body)
            segment.put_http_meta(http.CONTENT_LENGTH, int(cont_len))

        self._recorder.end_segment()
        return response



    #     def before_service_request(self, request, request_context, *, service_name):
    #         op = self._get_operation_name(request)
    #         current_span = self.get_span(request_context)
    #
    #         http_header_carrier = {}
    #         self._tracer.inject(
    #             span_context=current_span.context,
    #             format=opentracing.Format.HTTP_HEADERS,
    #             carrier=http_header_carrier
    #         )
    #
    #         request_header = request.headers
    #         request_header.update(http_header_carrier)
    #
    #         request.update_headers(request_header)


    def _handle_exception(self, exception):
        if not exception:
            return
        segment = self._recorder.current_segment()
        segment.put_http_meta(http.STATUS, 500)
        stack = traceback.extract_stack(limit=self._recorder._max_trace_back)
        segment.add_exception(exception, stack)
        self._recorder.end_segment()


