import aiotask_context
import datetime
import jwt
import pytest
import uuid

from calendar import timegm

from insanic import Insanic
from insanic.authentication import handlers
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.functional import empty
from insanic.models import User

from pytest_redis import factories

settings.configure(
    SERVICE_NAME="insanic",
    GATEWAY_REGISTRATION_ENABLED=False,
    TRACING_ENABLED=False,
    ENFORCE_APPLICATION_VERSION=False,
)

for cache_name, cache_config in settings.INSANIC_CACHES.items():
    globals()[f"redisdb_{cache_name}"] = factories.redisdb(
        "redis_proc", dbnum=cache_config.get("DATABASE")
    )


@pytest.fixture(scope="session")
def session_id():
    return uuid.uuid4().hex


@pytest.fixture(scope="function")
def function_session_id():
    return uuid.uuid4().hex


@pytest.fixture
def insanic_application():
    yield Insanic("test")


@pytest.fixture(autouse=True)
def loop(loop):
    loop.set_task_factory(aiotask_context.copying_task_factory)
    return loop


@pytest.fixture(autouse=True)
def set_redis_connection_info(redisdb, monkeypatch):
    port = (
        redisdb.connection_pool.connection_kwargs["path"]
        .split("/")[-1]
        .split(".")[1]
    )

    insanic_caches = settings.INSANIC_CACHES.copy()

    for cache_name in insanic_caches.keys():
        insanic_caches[cache_name]["HOST"] = "127.0.0.1"
        insanic_caches[cache_name]["PORT"] = int(port)

    caches = settings.CACHES.copy()

    for cache_name in caches.keys():
        caches[cache_name]["HOST"] = "127.0.0.1"
        caches[cache_name]["PORT"] = int(port)

    monkeypatch.setattr(settings, "INSANIC_CACHES", insanic_caches)
    monkeypatch.setattr(settings, "CACHES", caches)


def jwt_payload_handler(user, issuer):

    payload = {
        "user_id": user.id,
        "level": user.level,
        "iss": issuer,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(days=7),
        "orig_iat": timegm(datetime.datetime.utcnow().utctimetuple()),
        "rol": "user",
    }

    # Include original issued at time for a brand new token,
    # to allow token refresh

    if settings.JWT_AUTH_AUDIENCE is not None:
        payload["aud"] = settings.JWT_AUTH_AUDIENCE

    return payload


@pytest.fixture(scope="session")
def test_user_token_factory():
    # created_test_user_ids = set()

    def factory(id=None, *, level, return_with_user=False):
        if not id:
            id = uuid.uuid4().hex

        user = User(id=id, level=level)

        mock_issuer = uuid.uuid4().hex
        mock_secret = uuid.uuid4().hex

        payload = jwt_payload_handler(user, mock_issuer)
        token = jwt.encode(payload, mock_secret, "HS256").decode()

        if return_with_user:
            return (
                user,
                " ".join([settings.JWT_AUTH_AUTH_HEADER_PREFIX, token]),
            )

        return " ".join([settings.JWT_AUTH_AUTH_HEADER_PREFIX, token])

    yield factory


@pytest.fixture(scope="session")
def test_service_token_factory():
    class MockService:
        service_name = "test"

    def factory():

        # source, aud, source_ip, destination_version, is_authenticated):
        service = MockService()
        payload = handlers.jwt_service_payload_handler(service)
        return " ".join(
            [
                settings.JWT_SERVICE_AUTH_AUTH_HEADER_PREFIX,
                handlers.jwt_service_encode_handler(payload),
            ]
        )

    return factory


@pytest.fixture(scope="session")
def test_service_token_factory_pre_0_4():
    class MockService:
        service_name = "test"

    def factory(user=None):
        if user is None:
            user = User(
                id=uuid.uuid4().hex,
                email="service@token.factory",
                level=UserLevels.ACTIVE,
            )
        # source, aud, source_ip, destination_version, is_authenticated):
        service = MockService()
        payload = handlers.jwt_service_payload_handler(service)
        payload.update({"user": dict(user)})

        return " ".join(
            [
                settings.JWT_SERVICE_AUTH_AUTH_HEADER_PREFIX,
                handlers.jwt_service_encode_handler(payload),
            ]
        )

    return factory


@pytest.fixture(autouse=True)
def clear_prometheus_registry():
    yield

    from insanic.metrics import InsanicMetrics

    InsanicMetrics.reset()


@pytest.fixture(autouse=True)
def reset_settings():
    settings._wrapped = empty
    settings.configure(SERVICE_NAME="test", ENFORCE_APPLICATION_VERSION=False)
