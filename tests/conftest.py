import pytest
import uuid

import requests
from yarl import URL

from authentication import handlers
from insanic import Insanic
from insanic.conf import settings
from insanic.models import User

from pytest_redis import factories

settings.configure(SERVICE_NAME="insanic", GATEWAY_REGISTRATION_ENABLED=False, MMT_ENV="test")

for cache_name, cache_config in settings.INSANIC_CACHES.items():
    globals()[f"redisdb_{cache_name}"] = factories.redisdb('redis_proc', db=cache_config.get('DATABASE'))


@pytest.fixture(scope="session")
def session_id():
    return uuid.uuid4().hex


@pytest.fixture(scope="function")
def function_session_id():
    return uuid.uuid4().hex


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
    created_test_user_ids = set()

    def factory(id=uuid.uuid4(), *, email, level, return_with_user=False):
        user = User(id=id.hex, email=email, level=level)
        created_test_user_ids.add(user.id)
        # Create test consumer
        requests.post(f"http://kong.msa.swarm:18001/consumers/", json={'username': user.id})

        # Generate JWT information
        response = requests.post(f'http://kong.msa.swarm:18001/consumers/{user.id}/jwt/')
        response.raise_for_status()

        token_data = response.json()

        payload = handlers.jwt_payload_handler(user, token_data['key'])
        token = handlers.jwt_encode_handler(payload, token_data['secret'], token_data['algorithm'])

        if return_with_user:
            return user, " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], token])

        return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], token])

    yield factory

    for user_id in created_test_user_ids:
        # Delete JWTs
        response = requests.get(f'http://kong.msa.swarm:18001/consumers/{user_id}/jwt/')
        response.raise_for_status()

        jwt_ids = (response.json())['data']
        for jwt in jwt_ids:
            response = requests.delete(f"http://kong.msa.swarm:18001/consumers/{user_id}/jwt/{jwt['id']}/")
            response.raise_for_status()

        # Delete test consumer
        response = requests.delete(f"http://kong.msa.swarm:18001/consumers/{user_id}/")
        response.raise_for_status()
