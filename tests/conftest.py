import pytest
import uuid

from insanic import Insanic
from insanic.authentication import handlers
from insanic.conf import settings
from insanic.models import User

from pytest_redis import factories

settings.configure(SERVICE_NAME="insanic", GATEWAY_REGISTRATION_ENABLED=False, MMT_ENV="test")

for cache_name, cache_config in settings.INSANIC_CACHES.items():
    globals()[f"redisdb_{cache_name}"] = factories.redisdb('redis_proc', db=cache_config.get('DATABASE'))


@pytest.fixture
def insanic_application():
    return Insanic("test")


@pytest.fixture(autouse=True)
def set_redis_connection_info(redisdb, monkeypatch):
    port = redisdb.connection_pool.connection_kwargs['path'].split('/')[-1].split('.')[1]
    db = redisdb.connection_pool.connection_kwargs['db']

    monkeypatch.setattr(settings, 'REDIS_PORT', int(port))
    monkeypatch.setattr(settings, 'REDIS_HOST', '127.0.0.1')
    monkeypatch.setattr(settings, 'REDIS_DB', db)


@pytest.fixture(scope="session")
def test_user_token_factory():
    # from insanic.conf import settings
    # from insanic.authentication import handlers

    def factory(id=None, *, email, level):
        if not id:
            id = uuid.uuid4().hex

        user = User(**{"id": id, 'email': email, 'level': level})
        payload = handlers.jwt_payload_handler(user)
        return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], handlers.jwt_encode_handler(payload)])

    return factory

