from aiohttp.client_exceptions import ClientConnectorError

from insanic.conf import settings
from insanic.connections import _connections
from insanic.registration import gateway


async def after_server_stop_close_database(app, loop, **kwargs):
    close_tasks = _connections.close_all()
    await close_tasks


async def after_server_start_connect_database(app, loop=None, **kwargs):
    _connections.loop = loop


async def after_server_start_register_service(app, loop, **kwargs):

    async with gateway as gw:
        # await gw.register(app)
        try:
            await gw.register(app)
        except ClientConnectorError:
            if settings.MMT_ENV in settings.KONG_FAIL_SOFT_ENVIRONMENTS:
                pass
            else:
                raise


async def before_server_stop_deregister_service(app, loop, **kwargs):
    async with gateway as gw:
        try:
            await gw.deregister()
        except ClientConnectorError:
            if settings.MMT_ENV in settings.KONG_FAIL_SOFT_ENVIRONMENTS:
                pass
            else:
                raise
