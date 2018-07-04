import time
import traceback
import wrapt

from aws_xray_sdk.core import xray_recorder


def capture_async(name=None):
    @wrapt.decorator
    async def wrapper(wrapped, instance, args, kwargs):
        func_name = name
        if not func_name:
            func_name = wrapped.__name__

        subsegment = xray_recorder.begin_subsegment(func_name, 'local')

        exception = None
        stack = None
        return_value = None

        try:
            return_value = await wrapped(*args, **kwargs)
            return return_value
        except Exception as e:
            exception = e
            stack = traceback.extract_stack(limit=xray_recorder._max_trace_back)
            raise
        finally:
            # No-op if subsegment is `None` due to `LOG_ERROR`.
            if subsegment is not None:
                end_time = time.time()

                if exception:
                    if subsegment:
                        subsegment.add_exception(exception, stack)

                if not xray_recorder.context.end_subsegment(end_time, subsegment):
                    pass
                else:
                    if xray_recorder.current_segment().ready_to_send():
                        xray_recorder._send_segment()
                    else:
                        xray_recorder.stream_subsegments()

    return wrapper


def capture(name=None):
    @wrapt.decorator
    def wrapper(wrapped, instance, args, kwargs):
        func_name = name
        if not func_name:
            func_name = wrapped.__name__

        subsegment = xray_recorder.begin_subsegment(func_name, 'local')

        exception = None
        stack = None
        return_value = None

        try:
            return_value = wrapped(*args, **kwargs)
            return return_value
        except Exception as e:
            exception = e
            stack = traceback.extract_stack(limit=xray_recorder._max_trace_back)
            raise
        finally:
            # No-op if subsegment is `None` due to `LOG_ERROR`.
            if subsegment is not None:
                end_time = time.time()

                if exception:
                    if subsegment:
                        subsegment.add_exception(exception, stack)

                if not xray_recorder.context.end_subsegment(end_time, subsegment):
                    pass
                else:
                    if xray_recorder.current_segment().ready_to_send():
                        xray_recorder._send_segment()
                    else:
                        xray_recorder.stream_subsegments()

    return wrapper
