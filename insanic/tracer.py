import opentracing
from opentracing.ext import tags

from insanic import __version__
from incendiary import Tracer as IncendiaryTracer

# from flask import (Request, _request_ctx_stack as stack)

class InsanicTracer():
    '''
    Tracer that can trace certain requests to a Flask app.
    @param tracer the OpenTracing tracer implementation to trace requests with
    '''
    def __init__(self, tracer=None, trace_all_requests=False, app=None, traced_attributes=[]):

        self._tracer = IncendiaryTracer() if tracer is None else tracer
        self._trace_all_requests = trace_all_requests
        self._current_spans = {}


        # tracing all requests requires that app != None
        if self._trace_all_requests:
            @app.middleware('request')
            def start_trace(request):
                self._before_request_fn(request, traced_attributes)

            @app.middleware('response')
            def end_trace(request, response):
                self._after_request_fn(request, response)
                return response

        opentracing.tracer = self

    def trace_function(self, *attributes):
        '''
        Function decorator that traces functions
        NOTE: Must be placed after the @app.route decorator
        @param attributes any number of flask.Request attributes
        (strings) to be set as tags on the created span
        '''
        def decorator(f):
            def wrapper(*args, **kwargs):
                if not self._trace_all_requests:
                    self._before_request_fn(list(attributes))
                    r = f(*args, **kwargs)
                    self._after_request_fn()
                    return r
                else:
                    return f(*args, **kwargs)
            wrapper.__name__ = f.__name__
            return wrapper
        return decorator

    def get_span(self, request):
        '''
        Returns the span tracing `request`, or the current request if
        `request==None`.
        If there is no such span, get_span returns None.
        @param request the request to get the span from
        '''
        if request is None:
            return None

        try:
            return self._current_spans.get(request.tracing, None)
        except AttributeError:
            return self._tracer.start_span()

    def _before_request_fn(self, request, attributes):
        operation_name = self._get_operation_name(request)
        headers = {}
        for k,v in request.headers.items():
            headers[k.lower()] = v
        span = None
        try:
            span_ctx = self._tracer.extract(opentracing.Format.HTTP_HEADERS, headers)
            span = self._tracer.start_span(operation_name=operation_name, child_of=span_ctx)
        except (opentracing.InvalidCarrierException, opentracing.SpanContextCorruptedException) as e:
            span = self._tracer.start_span(operation_name=operation_name, tags={"Extract failed": str(e)})
        if span is None:
            span = self._tracer.start_span(operation_name)

        span.set_tag("insanic.version", __version__)
        span.set_tag(tags.HTTP_URL, request.url)
        span.set_tag(tags.HTTP_METHOD, request.method)
        span.set_tag(tags.PEER_HOST_IPV4, request.ip[0])
        span.set_tag(tags.PEER_PORT, request.ip[1])

        self._current_spans[request.tracing] = span
        for attr in attributes:
            if hasattr(request, attr):
                payload = str(getattr(request, attr))
                if payload:
                    span.set_tag("request.{0}".format(attr), payload)

        request.span = span

    def _get_operation_name(self, request):
        if hasattr(request, "path"):
            return "{0} {1}".format(request.method.upper(), request.path)
        else:
            return "{0} {1}".format(request.method.upper(), request.url.path)

    def _after_request_fn(self, request, response):
        span = self._current_spans.pop(request.tracing)
        if span is not None:
            span.set_tag(tags.HTTP_STATUS_CODE, response.status)
            span.set_tag('response.body', response.body)

            setattr(response, 'span', span)
            # response.span = span
            span.finish()


    def before_service_request(self, request, request_context, *, service_name):
        op = self._get_operation_name(request)
        current_span = self.get_span(request_context)

        http_header_carrier = {}
        self._tracer.inject(
            span_context=current_span.context,
            format=opentracing.Format.HTTP_HEADERS,
            carrier=http_header_carrier
        )

        request_header = request.headers
        request_header.update(http_header_carrier)

        request.update_headers(request_header)


    def before_http_request(self, request, request_context, *, service_name=""):
        op = self._get_operation_name(request)
        parent_span = self.get_span(request_context)
        outbound_span = self._tracer.start_span(
            operation_name=op,
            child_of=parent_span
        )

        outbound_span.set_tag('http.url', str(request.url))
        # service_name = request.service_name
        if service_name:
            outbound_span.set_tag(tags.PEER_SERVICE, service_name)
        else:
            outbound_span.set_tag(tags.PEER_SERVICE, request.url.name)
        if request.url.host:
            outbound_span.set_tag(tags.PEER_HOST_IPV4, request.url.host)
        if request.url.port:
            outbound_span.set_tag(tags.PEER_PORT, request.url.port)

        http_header_carrier = {}
        self._tracer.inject(
            span_context=outbound_span.context,
            format=opentracing.Format.HTTP_HEADERS,
            carrier=http_header_carrier)

        request_header = request.headers
        request_header.update(http_header_carrier)

        request.update_headers(request_header)

        return outbound_span


    def before_request(self, operation_name, parent_span, tags):
        # parent_span = self.get_span(request)

        if parent_span is not None:
            outbound_span = self._tracer.start_span(
                operation_name=operation_name,
                child_of=parent_span
            )

            for k,v in tags.items():
                outbound_span.set_tag(k, v)

            return outbound_span

