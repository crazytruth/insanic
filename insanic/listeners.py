from insanic.conf import settings
from insanic.connections import _connections, get_connection
from insanic.services import IS_INFUSED
from insanic.tracing.tracer import InsanicXRayMiddleware

# async def before_server_stop_close_database(app, loop, **kwargs):
async def after_server_stop_close_database(app, loop, **kwargs):
    close_tasks = _connections.close_all()
    await close_tasks

async def after_server_start_start_tracing(app, loop=None, **kwargs):
    if settings.IS_DOCKER:
        app.tracer = InsanicXRayMiddleware(app, loop)
    else:
        app.tracer = None

async def after_server_start_connect_database(app, loop=None, **kwargs):
    _connections.loop = loop



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
