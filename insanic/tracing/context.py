import aiotask_context
import asyncio
import logging

from aws_xray_sdk.core.context import Context as _Context
from aws_xray_sdk.core.async_context import TaskLocalStorage

log = logging.getLogger(__name__)


class AsyncContext(_Context):
    """
    Async Context for storing segments.

    Inherits nearly everything from the main Context class.
    Replaces threading.local with a task based local storage class,
    Also overrides clear_trace_entities
    """
    def __init__(self, *args, loop=None, use_task_factory=True, **kwargs):
        super(AsyncContext, self).__init__(*args, **kwargs)

        self._loop = loop
        if loop is None:
            self._loop = asyncio.get_event_loop()

        if use_task_factory:
            self._loop.set_task_factory(aiotask_context.copying_task_factory)

        self._local = TaskLocalStorage(loop=loop)

    def clear_trace_entities(self):
        """
        Clear all trace_entities stored in the task local context.
        """
        if self._local is not None:
            self._local.clear()

    def _append_entity_to_task(self, entity):
        task = asyncio.Task.current_task(loop=self._loop)
        task.ref_entity = entity

    def put_segment(self, segment):
        super().put_segment(segment)
        setattr(self._local, "ref_entity", segment)

    def end_segment(self, end_time=None):
        """
        End the current active segment.

        :param int end_time: epoch in seconds. If not specified the current
            system time will be used.
        """
        entity = self.get_trace_entity()
        if not entity:
            log.warning("No segment to end")
            return
        if self._is_subsegment(entity):
            entity.parent_segment.close(end_time)
        else:
            entity.close(end_time)
        # self._local.ref_entity = None

    def put_subsegment(self, subsegment):
        """
        Store the subsegment created by ``xray_recorder`` to the context.
        If you put a new subsegment while there is already an open subsegment,
        the new subsegment becomes the child of the existing subsegment.
        """
        entity = self.get_trace_entity()
        if not entity:
            log.warning("Active segment or subsegment not found. Discarded %s." % subsegment.name)
            return

        entity.add_subsegment(subsegment)
        self._local.entities.append(subsegment)
        setattr(self._local, "ref_entity", subsegment)

    def end_subsegment(self, end_time=None, subsegment=None):
        """
        End the current active segment. Return False if there is no
        subsegment to end.

        :param int end_time: epoch in seconds. If not specified the current
            system time will be used.
        """
        if not subsegment:
            subsegment = self.get_trace_entity()

        if self._is_subsegment(subsegment):
            subsegment.close(end_time)
            self._local.entities.remove(subsegment)
            setattr(self._local, "ref_entity", None)
            return True
        else:
            log.warning("No subsegment to end.")
            return False

    def get_root_entity(self, entity):
        root_entity = entity
        while hasattr(root_entity, 'parent_segment') and root_entity.parent_segment is not None:
            root_entity = root_entity.parent_segment
        return root_entity

    def get_trace_entity(self):
        """
        Return the current trace entity(segment/subsegment). If there is none,
        it behaves based on pre-defined ``context_missing`` strategy.
        """
        if not getattr(self._local, 'entities', None):
            return self.handle_context_missing()
        ref_entity = self._local.ref_entity

        if ref_entity is not None:
            entity = ref_entity
        else:
            entity = self._local.entities[0]
        return entity
