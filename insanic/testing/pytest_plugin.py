import asyncio
import pytest

import uuid
import uvloop

from aioredis.connection import RedisConnection
from functools import partial
from pytest_asyncio.plugin import unused_tcp_port

from redis.connection import Connection
from insanic.utils import jwt
from insanic.conf import settings
from insanic.services import Service
from insanic.testing.helpers import User, MockService

pytest.register_assert_rewrite('insanic.testing.helpers')




# def pytest_addoption(parser):
#     parser.addoption('--')
@pytest.fixture(scope="session", autouse=True)
def test_session_id():
    return str(uuid.uuid4())

@pytest.fixture(scope="module", autouse=True)
def test_module_id():
    return str(uuid.uuid4())

@pytest.fixture(scope="function", autouse=True)
def test_function_id():
    return str(uuid.uuid4())

@pytest.fixture(scope="session")
def session_unused_tcp_port_factory():
    """A factory function, producing different unused TCP ports."""
    produced = set()

    def factory():
        """Return an unused port."""
        port = unused_tcp_port()

        while port in produced:
            port = unused_tcp_port()

        produced.add(port)

        return port
    return factory



@pytest.fixture(scope='session')
def authorization_token(request, test_user):
    payload = jwt.jwt_payload_handler(test_user)
    token = jwt.jwt_encode_handler(payload)

    return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], token])

@pytest.fixture(scope='session')
def test_user(user_id=19705):
    return User(id=user_id, email="admin@mymusictaste.com", is_active=True, is_authenticated=True)


@pytest.fixture(scope="session")
def event_loop():
    loop = uvloop.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope='function', autouse=True)
def monkeypatch_redis(monkeypatch, redisdb):

    await_list = []

    # the following two functions are required to make redis-py compatible with aioredis
    def parse_response(connection, command_name, **options):
        if isinstance(command_name, bytes):
            command_name = command_name.decode()

        response = connection.read_response()

        if command_name == "FLUSHALL":
            return response

        async def _coro_wrapper(response):
            if isinstance(response, list):
                response = [i.decode() if isinstance(i, bytes) else i for i in response]
            return response


        task = _coro_wrapper(response)
        await_list.append(task)

        return task

    def send_command(self, *args):
        if isinstance(args[0], bytes):
            args = list(args)
            args[0] = args[0].decode()
        self.send_packed_command(self.pack_command(*args))

    monkeypatch.setattr(redisdb, 'parse_response', parse_response)
    monkeypatch.setattr(Connection, 'send_command', send_command)


    def execute(self, *args, **kwargs):
        return asyncio.ensure_future(redisdb.execute_command(*args, **kwargs))

    monkeypatch.setattr(RedisConnection, 'execute', execute)


@pytest.fixture(scope='function', autouse=True)
def monkeypatch_service(request, monkeypatch, test_user):
    if "runservices" in request.keywords.keys():
        pass
    else:
        monkeypatch.setattr(Service, '_dispatch', partial(MockService.mock_dispatch, test_user=test_user))
