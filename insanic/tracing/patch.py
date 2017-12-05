import wrapt

# from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.ext.util import inject_trace_header, http

from insanic.conf import settings
from insanic.tracing.core import xray_recorder

def patch():
    """
    Patch insanic service client so it generates subsegments
    when calling other services.
    """

    wrapt.wrap_function_wrapper(
        'insanic.services',
        'Service._prepare_headers',
        _inject_header,
    )

    wrapt.wrap_function_wrapper(
        'insanic.services',
        'Service._dispatch',
        _xray_traced_service_dispatch,
    )


def _inject_header(wrapped, instance, args, kwargs):
    headers = args[0]
    inject_trace_header(headers, xray_recorder.current_subsegment())
    return wrapped(*args, **kwargs)

async def _xray_traced_service_dispatch(wrapped, instance, args, kwargs):
    result = await xray_recorder.record_subsegment_async(
        wrapped, instance, args, kwargs,
        name="{0}:{1}".format(settings.MMT_ENV.upper(), instance._service_name),
        namespace="remote",
        meta_processor=service_processor,
    )

    return result

def service_processor(wrapped, instance, args, kwargs,
                       return_value, exception, subsegment, stack):

    method = kwargs.get('method') or args[0]
    url = kwargs.get('url') or args[1]

    subsegment.put_http_meta(http.METHOD, method)
    subsegment.put_http_meta(http.URL, url)

    if return_value is not None:
        subsegment.put_http_meta(http.STATUS, return_value[1])
        subsegment.put_annotation('response', return_value[0])
    elif exception:
        subsegment.add_exception(exception, stack)