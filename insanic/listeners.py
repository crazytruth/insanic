import aiohttp
import aiotask_context
import asyncio

from insanic.connections import _connections
from insanic.registration import gateway
from insanic.services import ServiceRegistry


# def before_server_start_set_signals(app, loop, **kwargs):
#     from signal import (
#         SIGUSR1,
#         signal as signal_func,
#         Signals
#     )
#
#     def signal_usr1_handler(s, frame):
#         logger.info("Received signal %s. Reloading vault settings.", Signals(s).name)
#         # settings.reload()
#
#     signal_func(SIGUSR1, lambda s, f: signal_usr1_handler(s, f))


def before_server_start_set_task_factory(app, loop, **kwargs):
    loop.set_task_factory(aiotask_context.chainmap_task_factory)


async def after_server_stop_clean_up(app, loop, **kwargs):
    close_tasks = _connections.close_all()
    await close_tasks

    service_sessions = []
    for service_name, service in ServiceRegistry().items():
        if service is not None:
            if service._session is not None:
                service_sessions.append(service._session.close())

    # current_task = asyncio.Task.current_task()
    # await asyncio.gather(*[task for task in asyncio.Task.all_tasks() if not task.done() and task != current_task])
    #
    # task
    # for task in asyncio.Task.all_tasks() if not task.done() and current_task != task and task not in redis_reader_task

    await asyncio.gather(*service_sessions)


async def after_server_start_connect_database(app, loop=None, **kwargs):
    _connections.loop = loop


async def after_server_start_register_service(app, loop, **kwargs):
    # app.gateway_client_session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ttl_dns_cache=300))
    gateway.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ttl_dns_cache=300))


    async with gateway as gw:
        await gw.register(app)


async def before_server_stop_deregister_service(app, loop, **kwargs):
    async with gateway as gw:
        await gw.deregister()

    await gateway.session.close()
