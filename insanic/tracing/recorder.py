import time
import traceback

from aws_xray_sdk.core.async_recorder import AsyncAWSXRayRecorder


class InsanicAWSXRayRecorder(AsyncAWSXRayRecorder):

    # def end_subsegment_with_reference(self, subsegment, end_time=None):
    #     """
    #     End the current active subsegment. If this is the last one open
    #     under its parent segment, the entire segment will be sent.
    #
    #     :param float end_time: subsegment compeletion in unix epoch in seconds.
    #     """
    #     if not self.context.end_subsegment_with_reference(subsegment, end_time):
    #         return
    #
    #     # if segment is already close, we check if we can send entire segment
    #     # otherwise we check if we need to stream some subsegments
    #     if self.current_segment().ready_to_send():
    #         self._send_segment()
    #     else:
    #         self.stream_subsegments()

    def end_subsegment(self, end_time=None, subsegment=None):
        """
        End the current active subsegment. If this is the last one open
        under its parent segment, the entire segment will be sent.
        :param float end_time: subsegment compeletion in unix epoch in seconds.
        """
        if not self.context.end_subsegment(end_time, subsegment):
            return

        # if segment is already close, we check if we can send entire segment
        # otherwise we check if we need to stream some subsegments
        if self.current_segment().ready_to_send():
            self._send_segment()
        else:
            self.stream_subsegments()

    async def record_subsegment_async(self, wrapped, instance, args, kwargs, name,
                                namespace, meta_processor):

        subsegment = self.begin_subsegment(name, namespace)

        exception = None
        stack = None
        return_value = None

        try:
            return_value = await wrapped(*args, **kwargs)
            return return_value
        except Exception as e:
            exception = e
            stack = traceback.extract_stack(limit=self._max_trace_back)
            raise
        finally:
            end_time = time.time()
            if callable(meta_processor):
                meta_processor(
                    wrapped=wrapped,
                    instance=instance,
                    args=args,
                    kwargs=kwargs,
                    return_value=return_value,
                    exception=exception,
                    subsegment=subsegment,
                    stack=stack,
                )
            elif exception:
                if subsegment:
                    subsegment.add_exception(exception, stack)

            self.end_subsegment(end_time, subsegment)
