import asyncio
from insanic.conf import settings
from insanic.connections import _connections, get_connection
from insanic.services import IS_INFUSED

from importlib import import_module
from peewee import BaseModel
from peewee_async import Manager


# async def before_server_stop_close_database(app, loop, **kwargs):
async def after_server_stop_close_database(app, loop, **kwargs):
    await app.database.close_async()
    close_tasks = _connections.close_all()
    await close_tasks

    await app.objects.close()


async def after_server_start_connect_database(app, loop=None, **kwargs):

    _connections.loop = loop

    app.database.init(settings.WEB_MYSQL_DATABASE,
                      host=settings.WEB_MYSQL_HOST,
                      port=settings.WEB_MYSQL_PORT,
                      user=settings.WEB_MYSQL_USER,
                      password=settings.WEB_MYSQL_PASS,
                      min_connections=5, max_connections=10, charset='utf8', use_unicode=True)

    # import models and switch out database
    try:
        service_models = import_module('{0}.models'.format(settings.SERVICE_NAME))
        for m in dir(service_models):
            if m[0].isupper():
                possible_model = getattr(service_models, m)
                if isinstance(possible_model, BaseModel):
                    possible_model._meta.database = app.database
    except ModuleNotFoundError:
        pass

    app.objects = Manager(app.database, loop=loop)


async def after_server_start_half_open_circuit(app, loop=None, **kwargs):
    '''
    If the circuit to running service is open, convert to half open state to try and allow connections.
    If multiple services are run, there could be multiple attempts at half-open circuit.
    '''

    if IS_INFUSED:
        from infuse import AioCircuitBreaker, CircuitAioRedisStorage, STATE_HALF_OPEN, STATE_OPEN

        redis = await get_connection('redis')
        conn = await redis.acquire()

        circuit_breaker_storage = CircuitAioRedisStorage(STATE_HALF_OPEN, conn, settings.SERVICE_NAME)

        breaker = await AioCircuitBreaker.initialize(fail_max=settings.INFUSE_MAX_FAILURE,
                                                     reset_timeout=settings.INFUSE_RESET_TIMEOUT,
                                                     state_storage=circuit_breaker_storage,
                                                     listeners=[])

        current_state = await breaker.current_state

        # if open, try half open state to allow connections.
        # if half-open, pass
        # if closed, pass
        if current_state == STATE_OPEN:
            await breaker.half_open()

        redis.release(conn)
