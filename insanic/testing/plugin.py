import pytest
import requests

import uuid
import uvloop

from functools import partial
from pytest_asyncio.plugin import unused_tcp_port

from insanic.authentication import (
    handlers,
    HardJSONWebTokenAuthentication,
    JSONWebTokenAuthentication,
)
from insanic.choices import UserLevels
from insanic.connections import _connections
from insanic.conf import settings
from insanic.models import User
from insanic.services import Service
from insanic.testing.helpers import MockService
from insanic.registration import gateway


@pytest.fixture(autouse=True)
def patch_hard_jwt_authentication(monkeypatch):
    monkeypatch.setattr(
        HardJSONWebTokenAuthentication,
        "get_jwt_value",
        JSONWebTokenAuthentication.get_jwt_value,
    )
    monkeypatch.setattr(
        HardJSONWebTokenAuthentication,
        "try_decode_jwt",
        JSONWebTokenAuthentication.try_decode_jwt,
    )
    monkeypatch.setattr(
        HardJSONWebTokenAuthentication,
        "authenticate_credentials",
        JSONWebTokenAuthentication.authenticate_credentials,
    )
    monkeypatch.setattr(
        HardJSONWebTokenAuthentication,
        "authenticate",
        JSONWebTokenAuthentication.authenticate,
    )


@pytest.fixture(scope="function", autouse=True)
def disable_kong(monkeypatch):
    monkeypatch.setattr(
        settings._wrapped, "GATEWAY_REGISTRATION_ENABLED", False
    )


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


@pytest.fixture(scope="session")
def test_user_token_factory():
    created_test_user_ids = set()

    def user_token_factory(id=None, *, level, return_with_user=False):
        if id is None:
            id = uuid.uuid4()

        user = User(id=id.hex, level=level, is_authenticated=True)
        created_test_user_ids.add(user.id)
        # Create test consumer
        requests.post(
            gateway.kong_base_url.with_path(f"/consumers/"),
            json={"username": user.id},
        )

        # Generate JWT information
        response = requests.post(
            gateway.kong_base_url.with_path(f"/consumers/{user.id}/jwt/")
        )
        response.raise_for_status()

        token_data = response.json()

        payload = handlers.jwt_payload_handler(user, token_data["key"])
        token = handlers.jwt_encode_handler(
            payload, token_data["secret"], token_data["algorithm"]
        )

        if return_with_user:
            return (
                user,
                " ".join([settings.JWT_AUTH["JWT_AUTH_HEADER_PREFIX"], token]),
            )

        return " ".join([settings.JWT_AUTH["JWT_AUTH_HEADER_PREFIX"], token])

    yield user_token_factory

    for user_id in created_test_user_ids:
        # Delete JWTs
        response = requests.get(
            gateway.kong_base_url.with_path(f"/consumers/{user_id}/jwt/")
        )
        response.raise_for_status()

        jwt_ids = (response.json())["data"]
        for jwt in jwt_ids:
            response = requests.delete(
                gateway.kong_base_url.with_path(
                    f"/consumers/{user_id}/jwt/{jwt['id']}/"
                )
            )
            response.raise_for_status()

        # Delete test consumer
        response = requests.delete(
            gateway.kong_base_url.with_path(f"/consumers/{user_id}/")
        )
        response.raise_for_status()


# token_factory = _UserTokenFactory()
# test_user_token_factory = token_factory.test_user_token_factory
# user_token_factory = token_factory.user_token_factory


@pytest.fixture(scope="session")
def test_service_token_factory():
    class MockService:
        service_name = settings.SERVICE_NAME

    def factory(user=None):
        if user is None:
            user = User(
                id=uuid.uuid4().hex,
                level=UserLevels.ACTIVE,
                is_authenticated=True,
            )
        # source, aud, source_ip, destination_version, is_authenticated):
        service = MockService()
        payload = handlers.jwt_service_payload_handler(service)
        return " ".join(
            [
                settings.JWT_SERVICE_AUTH["JWT_AUTH_HEADER_PREFIX"],
                handlers.jwt_service_encode_handler(payload),
            ]
        )

    return factory


@pytest.fixture(scope="session")
def test_user(test_user_token_factory):
    return test_user_token_factory(level=UserLevels.ACTIVE)


@pytest.fixture(scope="session")
def test_staff_user(test_user_token_factory):
    return test_user_token_factory(level=UserLevels.STAFF)


@pytest.fixture(scope="session")
def event_loop():
    loop = uvloop.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function", autouse=True)
async def close_connections(event_loop):
    _connections.loop = event_loop
    yield

    close_tasks = _connections.close_all()
    await close_tasks


@pytest.fixture(scope="session", autouse=True)
def monkeypatch_redis(redis_proc):
    # because of aynschronous issues while testing, aioredis needs to be monkeypatched
    settings.REDIS_PORT = redis_proc.port
    settings.REDIS_HOST = redis_proc.host


@pytest.fixture(scope="function", autouse=True)
def monkeypatch_service(request, monkeypatch, test_user):
    if "runservices" in request.keywords.keys():
        pass
    else:
        monkeypatch.setattr(
            Service,
            "http_dispatch",
            partial(MockService.mock_dispatch, test_user=test_user),
        )
