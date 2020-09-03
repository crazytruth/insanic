import aiotask_context
import asyncio

from insanic.connections import _connections
from insanic.services import Service


def before_server_start_verify_plugins(app, loop, **kwargs):
    app.verify_plugin_requirements()


def before_server_start_set_task_factory(app, loop, **kwargs):
    loop.set_task_factory(aiotask_context.chainmap_task_factory)


async def after_server_stop_clean_up(app, loop, **kwargs):
    close_tasks = _connections.close_all()
    await close_tasks

    if Service._client is not None:
        await Service._client.aclose()
        await asyncio.sleep(0)

    await asyncio.sleep(0)


async def after_server_start_connect_database(app, loop=None, **kwargs):
    _connections.loop = loop
