import aiohttp
import aiotask_context
import asyncio

from insanic.connections import _connections
from insanic.registration import gateway
from insanic.services import ServiceRegistry


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
    await asyncio.gather(*service_sessions)
    await gateway.session.close()


async def after_server_start_connect_database(app, loop=None, **kwargs):
    _connections.loop = loop




async def after_server_start_register_service(app, loop, **kwargs):
    # need to leave session because we need this in hardjwt to get consumer
    gateway.session = aiohttp.ClientSession(connector=aiohttp.TCPConnector(ttl_dns_cache=300))
    gateway.register(app)


def before_server_stop_deregister_service(app, loop, **kwargs):
    gateway.deregister()
