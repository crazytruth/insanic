import asyncio
import logging

from aws_xray_sdk.core.context import Context as _Context

log = logging.getLogger(__name__)

TASK_ENTITIES_KEY = "task_entities"

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
            self._loop.set_task_factory(task_factory)

        self._local = TaskLocalStorage(loop=loop)

    def clear_trace_entities(self):
        """
        Clear all trace_entities stored in the task local context.
        """
        if self._local is not None:
            self._local.clear()

    def _append_entity_to_task(self, entity):
        task = asyncio.Task.current_task(loop=self._loop)
        task.task_entities.append(entity)

    def put_segment(self, segment):
        super().put_segment(segment)
        setattr(self._local, TASK_ENTITIES_KEY, [segment])

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
        self._local.task_entities.append(subsegment)

    def end_subsegment(self, end_time=None):
        if super().end_subsegment(end_time):
            self._local.task_entities.pop()
        else:
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
        task_entities = self._local.task_entities

        if len(task_entities):
            entity = task_entities[-1]
        else:
            entity = self.get_root_entity(self._local.entities[-1])
        return entity

class TaskLocalStorage(object):
    """
    Simple task local storage
    """
    def __init__(self, loop=None):
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop

    def __setattr__(self, name, value):
        if name in ('_loop',):
            # Set normal attributes
            object.__setattr__(self, name, value)

        else:
            # Set task local attributes
            task = asyncio.Task.current_task(loop=self._loop)
            if task is None:
                return None

            if not hasattr(task, 'context'):
                task.context = {}

            task.context[name] = value

    def __getattribute__(self, item):
        if item in ('_loop', 'clear'):
            # Return references to local objects
            return object.__getattribute__(self, item)

        task = asyncio.Task.current_task(loop=self._loop)
        if task is None:
            return None

        if hasattr(task, 'context') and item in task.context:
            return task.context[item]

        raise AttributeError('Task context does not have attribute {0}'.format(item))

    def clear(self):
        # If were in a task, clear the context dictionary
        task = asyncio.Task.current_task(loop=self._loop)
        if task is not None and hasattr(task, 'context'):
            task.context.clear()


def task_factory(loop, coro):
    """
    Task factory function

    Fuction closely mirrors the logic inside of
    asyncio.BaseEventLoop.create_task. Then if there is a current
    task and the current task has a context then share that context
    with the new task
    """
    task = asyncio.Task(coro, loop=loop)
    if task._source_traceback:  # flake8: noqa
        del task._source_traceback[-1]  # flake8: noqa

    # Share context with new task if possible
    current_task = asyncio.Task.current_task(loop=loop)
    if current_task is not None and hasattr(current_task, 'context'):
        context = current_task.context.copy()
        if TASK_ENTITIES_KEY in context:
            context[TASK_ENTITIES_KEY] = []

        setattr(task, 'context', context)



    return task
