from __future__ import absolute_import

from opentracing import SpanContextCorruptedException
from basictracer.context import SpanContext
from basictracer.propagator import Propagator

prefix_tracer_state = 'x-b3-'
field_name_trace_id = prefix_tracer_state + 'traceid'
field_name_span_id = prefix_tracer_state + 'spanid'
field_name_sampled = prefix_tracer_state + 'sampled'

field_count = 3


class ZipkinPropagator(Propagator):
    """A BasicTracer Propagator for Format.TEXT_MAP and Format.HTTP_HEADERS."""

    def inject(self, span_context, carrier):
        carrier[field_name_trace_id] = '{0:x}'.format(span_context.trace_id)
        carrier[field_name_span_id] = '{0:x}'.format(span_context.span_id)
        carrier[field_name_sampled] = "1" if span_context.sampled else "0"

    def extract(self, carrier):
        count = 0
        span_id, trace_id, sampled = (0, 0, False)
        baggage = {}
        for k in carrier:
            v = carrier[k]
            k = k.lower()
            if k == field_name_span_id:
                span_id = int(v, 16)
                count += 1
            elif k == field_name_trace_id:
                trace_id = int(v, 16)
                count += 1
            elif k == field_name_sampled:
                if v == "1":
                    sampled = True
                elif v == "0":
                    sampled = False
                else:
                    raise SpanContextCorruptedException()
                count += 1

        if count != field_count:
            raise SpanContextCorruptedException()

        return SpanContext(
            span_id=span_id,
            trace_id=trace_id,
            baggage=baggage,
            sampled=sampled)


class NoopPropagator(Propagator):
    """A Propagator for Format.BINARY that does nothing."""

    def inject(self, span_context, carrier):
        pass

    def extract(self, carrier):
        return SpanContext()