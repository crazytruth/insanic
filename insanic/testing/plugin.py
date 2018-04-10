import asyncio
import docker
import pytest
import requests
import os

import uuid
import uvloop

from aws_xray_sdk.core.recorder import CONTEXT_MISSING_KEY
from collections import OrderedDict
from functools import partial
from io import BytesIO
from pytest_asyncio.plugin import unused_tcp_port
from zipfile import ZipFile

from insanic.authentication import handlers
from insanic.choices import UserLevels
from insanic.connections import _connections
from insanic.conf import settings
from insanic.loading import get_service
from insanic.models import User
from insanic.services import Service
from insanic.testing.helpers import MockService
from insanic.tracing.core import xray_recorder
from insanic.tracing.context import AsyncContext

pytest.register_assert_rewrite('insanic.testing.helpers')


def pytest_configure(config):
    config.addinivalue_line("markers",
                            "runservices: Mark the test as runservices which "
                            "will run dependent services as docker containers")


@pytest.fixture(scope="function", autouse=True)
def silence_tracer(event_loop):
    os.environ[CONTEXT_MISSING_KEY] = "LOG_ERROR"
    xray_recorder.configure(context=AsyncContext(loop=event_loop))

    xray_recorder.begin_segment(name="test", sampling=0)
    yield
    try:
        xray_recorder.end_segment()
    except AttributeError as e:
        print(e)


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
    def factory(id=uuid.uuid4(), *, email, level):
        user = User(id=id.hex, email=email, level=level)
        payload = handlers.jwt_payload_handler(user)
        return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], handlers.jwt_encode_handler(payload)])

    return factory


@pytest.fixture(scope='session')
def test_user(test_user_token_factory):
    return test_user_token_factory(email="staff@mmt.com", level=UserLevels.ACTIVE)


@pytest.fixture(scope='session')
def test_staff_user(test_user_token_factory):
    return test_user_token_factory(email="staff@mmt.com", level=UserLevels.STAFF)


@pytest.fixture(scope="session")
def event_loop():
    loop = uvloop.new_event_loop()
    yield loop
    loop.close()


# to create pytest-redis connection fixtures for each database
# for cache_name, cache_config in _connections.caches.items():
# for cache_name, cache_config in settings.INSANIC_CACHES.items():
#     globals()[f"redisdb_{cache_name}"] = factories.redisdb('redis_proc', db=cache_config.get('DATABASE'))
@pytest.fixture(scope='function', autouse=True)
async def close_connections(event_loop):
    _connections.loop = event_loop
    yield

    close_tasks = _connections.close_all()
    await close_tasks


@pytest.fixture(scope='session', autouse=True)
def monkeypatch_redis(redis_proc):
    # because of aynschronous issues while testing, aioredis needs to be monkeypatched
    settings.REDIS_PORT = redis_proc.port
    settings.REDIS_HOST = redis_proc.host


@pytest.fixture(scope='function', autouse=True)
def monkeypatch_service(request, monkeypatch, test_user):
    if "runservices" in request.keywords.keys():
        pass
    else:
        monkeypatch.setattr(Service, '_dispatch', partial(MockService.mock_dispatch, test_user=test_user))


async def wait_for_container(service, health_endpoint):
    for _ in range(30):
        try:
            await service.http_dispatch('GET', health_endpoint, skip_breaker=True)
        except Exception as e:
            await asyncio.sleep(1)
        else:
            break
    else:
        raise RuntimeError("{0} container failed to run.".format(service._service_name))

    return True


def remove_containers(client, session_id):
    for container in client.containers.list(all=True):
        if session_id in container.name:
            container.remove(force=True)


def _download_bimil(tmpdir):
    r = requests.get('http://david.mmt.local:8888/', auth=("development", "development"[::-1]))
    fp = BytesIO(r.content)
    with ZipFile(fp, 'r') as z:
        for f in z.filelist:
            if f.filename.startswith('settings'):
                with z.open(f) as settings_file:
                    tmpdir.join(settings_file.name).write_binary(settings_file.read())


@pytest.fixture(scope="session", autouse=True)
async def run_services(request, test_session_id, session_unused_tcp_port_factory, tmpdir_factory):

    for test_func in request.node.items:
        if "runservices" in test_func.keywords.keys():
            launch_service = True
            break
    else:
        launch_service = False

    running_containers = OrderedDict()
    running_services = OrderedDict()
    if launch_service:
        # DOCKER_PRIVATE_REPO = os.environ['INSANIC_TEST_DOCKER_REPO']
        # DOCKER_USERNAME = os.environ['INSANIC_TEST_DOCKER_USER']
        # DOCKER_PASSWORD = os.environ['INSANIC_TEST_DOCKER_PASSWORD']
        # DOCKER_WEB_SRC_TAG = os.environ['INSANIC_TEST_WEB_SRC_TAG']
        # TEST_PROJECT_ENV = os.environ['INSANIC_TEST_PROJECT_ENV']

        DOCKER_PRIVATE_REPO = settings.INSANIC_TEST_DOCKER_REPO
        DOCKER_USERNAME = settings.INSANIC_TEST_DOCKER_USER
        DOCKER_PASSWORD = settings.INSANIC_TEST_DOCKER_PASSWORD
        DOCKER_WEB_SRC_TAG = settings.INSANIC_TEST_WEB_SRC_TAG
        TEST_PROJECT_ENV = settings.INSANIC_TEST_PROJECT_ENV

        force_exit = None
        docker_client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
        try:

            web_login_config = {"username": DOCKER_USERNAME, "password": DOCKER_PASSWORD}
            docker_client.login(registry=DOCKER_PRIVATE_REPO, **web_login_config)

            for service_name in settings.SERVICE_CONNECTIONS:
                service_config = settings.SERVICE_LIST.get(service_name, {})

                bind_port = session_unused_tcp_port_factory()
                internal_service_port = service_config.get("internalserviceport", 8000)

                settings.SERVICE_LIST.update({service_name: {"host": "localhost",
                                                             "external_service_port": bind_port,
                                                             "internal_service_port": internal_service_port}})

                params = {
                    "name": "test-{0}-{1}".format(test_session_id, service_name),
                    "image": "{0}/mmt-server-{0}:stable".format(DOCKER_USERNAME),
                    "detach": True,
                    "labels": {"container-type": "mmt-{0}".format(service_name), "test_session": test_session_id},
                    "environment": {"MMT_ENV": "test", "MMT_SERVICE": service_name},
                    "ports": {"{0}/tcp".format(internal_service_port): bind_port},
                }

                if service_name == "web":
                    # first run mmt-src
                    src_params = {}
                    src_params['image'] = "{0}/mmt-src:{1}".format(DOCKER_PRIVATE_REPO, DOCKER_WEB_SRC_TAG)
                    src_params['remove'] = False
                    src_params['detach'] = True
                    src_params["name"] = "test-{0}-{1}".format(test_session_id, "src")
                    src_params['labels'] = {"test_session": test_session_id}

                    docker_client.images.pull(src_params['image'].rsplit(':', 1)[0],
                                              tag=src_params['image'].rsplit(':', 1)[1],
                                              auth_config=web_login_config)
                    src_container = docker_client.containers.run(**src_params)

                    temp_bimil = tmpdir_factory.mktemp('.bimil')
                    _download_bimil(temp_bimil)

                    params.update({
                        "image": "{0}/mmt-app:development".format(DOCKER_PRIVATE_REPO),
                        "command": "0.0.0.0:8000",
                        "environment": {"MMT_ENV": "development_test",
                                        "MMT_PASS": settings.MMT_WEB_PASS,
                                        "MMT_TEST_DB": TEST_PROJECT_ENV},
                        "working_dir": "/opt/django",
                        "volumes_from": [src_container.id],
                        "sysctls": {"net.core.somaxconn": 1000},
                        "volumes": {temp_bimil.strpath: {'bind': '/opt/django/.bimil', 'mode': 'rw'}},
                        "entrypoint": ["/usr/bin/python", "/opt/django/mmt_mk2/manage.py", "runserver"],
                    })
                    docker_client.images.pull(params['image'].rsplit(':', 1)[0],
                                              tag=params['image'].rsplit(':', 1)[1],
                                              auth_config=web_login_config)
                    app_container = docker_client.containers.run(**params)

                    celery_params = params.copy()
                    del celery_params['command']
                    del celery_params['ports']
                    celery_params['name'] = "test-{0}-{1}".format(test_session_id, 'celery')
                    celery_params['entrypoint'] = ["/usr/bin/python", "/opt/django/mmt_mk2/celery", "worker",
                                                   "-Q", "celery_test",
                                                   "-A", "mmt_mk2.core",
                                                   "-l", "info",
                                                   "--statedb=/tmp/worker.%n.state",
                                                   "-n", "testworker1@%h"]
                    celery_container = docker_client.containers.run(**celery_params)

                    running_containers.update({"celery": celery_container})
                    running_containers.update({service_name: app_container})
                    running_containers.update({"src": src_container})
                else:
                    # run insanic service
                    pass

                service = get_service(service_name)
                running_services.update({service_name: service})

            waiters = []

            for sn, s in running_services.items():
                if sn == "web":
                    health_url = "/monitor/version"
                else:
                    health_url = "/health"
                waiters.append(wait_for_container(s, health_url))

            result = await asyncio.gather(*waiters)
            if not all(result):
                raise RuntimeError("Docker containers failed to run.")
        except Exception as e:
            force_exit = e
            import warnings

            warnings.warn(str(e.args[0]))

            import traceback
            traceback.print_exc()
            # raise
        else:
            pass

        finally:

            if force_exit is not None:
                remove_containers(docker_client, test_session_id)

                # pytest.warns(force_exit)
                # pytest.fail("Failed to run docker containers", force_exit)

        yield

        remove_containers(docker_client, test_session_id)
    else:
        yield


def pytest_runtest_setup(item):
    pass
