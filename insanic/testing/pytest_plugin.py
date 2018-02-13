import asyncio
import aiobotocore
import base64
import docker
import pytest
import requests
import os

import uuid
import uvloop

from aioredis.connection import RedisConnection
from aws_xray_sdk.core.recorder import CONTEXT_MISSING_KEY
from collections import OrderedDict
from functools import partial
from io import BytesIO
from pytest_asyncio.plugin import unused_tcp_port
from zipfile import ZipFile

from redis.connection import Connection
from insanic.utils import jwt
from insanic.conf import settings
from insanic.loading import get_service
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

    segment = xray_recorder.begin_segment(name="test", sampling=0)
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
        payload = {"user_id": id.hex, 'email': email, 'level': level}
        return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], jwt.jwt_encode_handler(payload)])

    return factory

@pytest.fixture(scope='session')
def test_user(test_user_token_factory):
    return test_user_token_factory(email="staff@mmt.com", level=20)

@pytest.fixture(scope='session')
def test_staff_user(test_user_token_factory):
    return test_user_token_factory(email="staff@mmt.com", level=30)


# @pytest.fixture(scope='session')
# def authorization_token(request, test_user):
#     payload = jwt.jwt_payload_handler(test_user)
#     token = jwt.jwt_encode_handler(payload)
#
#     return " ".join([settings.JWT_AUTH['JWT_AUTH_HEADER_PREFIX'], token])
#
# @pytest.fixture(scope='session')
# def test_user(user_id=19705):
#     return User(id=user_id, email="admin@mymusictaste.com", is_active=True, is_authenticated=True, is_staff=False)


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

async def wait_for_container(service, health_endpoint):
    for _ in range(30):
        try:
            val = await service.http_dispatch('GET', health_endpoint, skip_breaker=True)
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
        DOCKER_PRIVATE_REPO = os.environ['INSANIC_TEST_DOCKER_REPO']
        DOCKER_USERNAME = os.environ['INSANIC_TEST_DOCKER_USER']
        DOCKER_PASSWORD = os.environ['INSANIC_TEST_DOCKER_PASSWORD']
        DOCKER_WEB_SRC_TAG = os.environ['INSANIC_TEST_WEB_SRC_TAG']
        TEST_PROJECT_ENV = os.environ['INSANIC_TEST_PROJECT_ENV']

        repository = None
        force_exit = None
        docker_client = docker.DockerClient(base_url="unix:///var/run/docker.sock")
        try:

            web_login_config = {"username": DOCKER_USERNAME, "password": DOCKER_PASSWORD}
            login_response = docker_client.login(registry=DOCKER_PRIVATE_REPO, **web_login_config)

            for service_name in settings.SERVICE_CONNECTIONS:
                service_config = settings.SERVICES[service_name]

                bind_port = session_unused_tcp_port_factory()

                params = {
                    "name": "test-{0}-{1}".format(test_session_id, service_name),
                    "image": "{0}/mmt-server-{0}:stable".format(DOCKER_USERNAME),
                    "detach": True,
                    "labels": {"container-type": "mmt-{0}".format(service_name), "test_session": test_session_id},
                    "environment": {"MMT_ENV": "test", "MMT_SERVICE": service_name},
                    "ports": {"{0}/tcp".format(service_config.get("internalserviceport")): bind_port},
                }

                if service_name == "web":
                    # first run mmt-src
                    src_params = {}
                    src_params['image'] = "{0}/mmt-src:{1}".format(DOCKER_PRIVATE_REPO, DOCKER_WEB_SRC_TAG)
                    src_params['remove'] = False
                    src_params['detach'] = True
                    src_params["name"] = "test-{0}-{1}".format(test_session_id, "src")
                    src_params['labels'] = {"test_session": test_session_id}

                    src_image = docker_client.images.pull(src_params['image'].rsplit(':', 1)[0],
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
                    app_image = docker_client.images.pull(params['image'].rsplit(':', 1)[0],
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
                service._host = "127.0.0.1"
                service._port = bind_port

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
            raise
        finally:

            if force_exit is not None:
                remove_containers(docker_client, test_session_id)

                pytest.fail("Failed to run docker containers", force_exit)

        yield

        remove_containers(docker_client, test_session_id)
    else:
        yield
