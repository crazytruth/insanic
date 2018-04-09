from insanic.connections import _connections


async def after_server_stop_close_database(app, loop, **kwargs):
    close_tasks = _connections.close_all()
    await close_tasks


async def after_server_start_connect_database(app, loop=None, **kwargs):
    _connections.loop = loop

