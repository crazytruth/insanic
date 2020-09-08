import aiotask_context
import asyncio

from insanic.connections import _connections
from insanic.services.registry import registry


def before_server_start_verify_plugins(app, loop, **kwargs):
    app.verify_plugin_requirements()


def before_server_start_set_task_factory(app, loop, **kwargs):
    loop.set_task_factory(aiotask_context.chainmap_task_factory)


async def after_server_start_connect_database(app, loop=None, **kwargs):
    _connections.loop = loop


async def after_server_stop_clean_up(app, loop, **kwargs):
    """
    Clean up all connections and close service client connections.
    :param app:
    :param loop:
    :param kwargs:
    :return:
    """
    close_tasks = _connections.close_all()
    await close_tasks

    close_client_tasks = [
        service.close_client() for service in registry.values()
    ]
    await asyncio.gather(*close_client_tasks)
    await asyncio.sleep(0)
