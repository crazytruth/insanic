import copy
import os
import sys
import json
import socket
import uuid
import aiohttp
import requests

from enum import Enum
from collections import namedtuple, OrderedDict
from setuptools.command.test import test as TestCommand
from yarl import URL

from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.errors import GlobalErrorCodes
from insanic.exceptions import APIException
from insanic.handlers import _unpack_enum_error_message
from insanic.functional import empty
from pytest_sanic.plugin import unused_port
from sanic.testing import PORT
from pact import Consumer, Provider

DEFAULT_USER_LEVEL = UserLevels.ACTIVE


class PyTestCommand(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to pytest")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = ""

    def run_tests(self):
        import shlex
        # import here, cause outside the eggs aren't loaded
        import pytest
        os.environ['MMT_ENV'] = "test"

        errno = pytest.main(shlex.split(self.pytest_args))
        sys.exit(errno)


class BaseMockService:

    service_responses = {}

    def __init__(self):
        self.register_mock_dispatch("POST", "/api/v1/ip", {}, )


    def _key_for_request(self, method, endpoint, body):
        body_list = []
        for k in sorted(body.keys()):

            if isinstance(body, (list, dict)):
                v = json.dumps(body[k], sort_keys=True)
            else:
                v = body[k]

            body_list.extend([k, v])
        return (method.upper(), endpoint, ":".join(body_list))

    async def mock_dispatch(self, method, endpoint, req_ctx={}, *, query_params={}, payload={}, headers={},
                            propagate_error=False, include_status_code=False, **kwargs):

        request = self._normalize_request(method, endpoint, query_params, payload)
        keys = self._keys_for_request(request)
        #
        # if method == "GET" and query_params != {}:
        #     keys.append(self._key_for_request(method, endpoint, query_params))
        #
        # if payload != {}:
        #     keys.append(self._key_for_request(method, endpoint, {}))
        #
        # keys.append(self._key_for_request(method, endpoint, payload))

        for k in keys:
            if k in self.service_responses:
                resp = self.service_responses[k][0]
                status_code = self.service_responses[k][1]

                if propagate_error and 400 <= status_code:
                    # raise aiohttp.client_exceptions.ClientResponseError('', '', status=status_code)
                    exc = APIException(description=resp.get('description'),
                                       error_code=_unpack_enum_error_message(
                                           resp.get('error_code', GlobalErrorCodes.unknown_error)),
                                       status_code=status_code)
                    exc.message = resp.get('message') or exc.message
                    raise exc

                if include_status_code:
                    return copy.deepcopy(resp), status_code
                else:
                    return copy.deepcopy(resp)

        raise RuntimeError(
            "Unknown service request: {0} {1}. Need to register mock dispatch.".format(method.upper(), endpoint))

    def _keys_for_request(self, request):

        body = json.loads(request.body._value)

        sorted_body = OrderedDict(sorted(body.items()))
        yield self._key_for_request(request.method, request.url.path_qs, sorted_body)
        yield self._key_for_request(request.method, request.url.path, sorted_body)
        yield self._key_for_request(request.method, request.url.path_qs, {})
        yield self._key_for_request(request.method, request.url.path, {})

    def _normalize_request(self, method, endpoint, query_params, request_body):
        fudge_url = "http://localhost"
        return aiohttp.ClientRequest(method=method.upper(), url=URL(fudge_url + endpoint),
                                     params=OrderedDict(sorted((query_params or {}).items())),
                                     data=aiohttp.payload.JsonPayload(
                                         OrderedDict(sorted((request_body or {}).items()))))

    def register_mock_dispatch(self, method, endpoint, response, response_status_code=200, request_body=None,
                               query_params=None):

        request = self._normalize_request(method, endpoint, query_params, request_body)

        for k in self._keys_for_request(request):
            if k in self.service_responses:
                if self.service_responses[k] == (response, response_status_code):
                    pass
                else:
                    print(f"""Service Response already exists for {json.dumps(k)}
                    expected response: {json.dumps((response, response_status_code))}
                    registered response: {json.dumps(self.service_responses[k])}""")

            self.service_responses.update({k: (response, response_status_code)})

        # key = self._key_for_request(request.method, request.url.path, OrderedDict(sorted(request.url.query)))
        #
        #
        # if method.upper() == "GET":
        #     if query_params is None:
        #         query_params = {}
        #
        #     key = self._key_for_request(method, endpoint, query_params)
        #     self.service_responses.update({key: (response, response_status_code)})
        #     if query_params != {}:
        #         key = self._key_for_request(method, endpoint, {})
        #         self.service_responses.update({key: (response, response_status_code)})
        # else:
        #
        #     if request_body is None:
        #         request_body = {}
        #
        #     key = self._key_for_request(method, endpoint, request_body)
        #     self.service_responses.update({key: (response, response_status_code)})
        #
        #     if request_body != {}:
        #         key = self._key_for_request(method, endpoint, {})
        #         self.service_responses.update({key: (response, response_status_code)})


MockService = BaseMockService()



class DunnoValue:
    def __init__(self, expected_type):
        self.expected_type = expected_type

    def __eq__(self, other):

        if self.expected_type == uuid.UUID and isinstance(other, str):
            try:
                uuid.UUID(other)
            except ValueError:
                return False
            else:
                return True
        else:
            return isinstance(other, self.expected_type)


def test_api_endpoint(insanic_application, test_user_token_factory, test_service_token_factory,
                      endpoint, method, request_headers, request_body, expected_response_status,
                      expected_response_body, user_level):
    handler = getattr(insanic_application.test_client, method.lower())

    request_headers.update({"accept": "application/json"})

    if "Authorization" in request_headers.keys() and request_headers.get("Authorization") == _TokenType('user'):
        user, token = test_user_token_factory(email="test@mmt.com", level=user_level, return_with_user=True)
        request_headers.update({"Authorization": token, 'x-consumer-username': user.id})
    elif "Authorization" in request_headers.keys() and request_headers.get("Authorization") == _TokenType('service'):
        user, token = test_user_token_factory(email="test@mmt.com", level=user_level, return_with_user=True)

        request_headers.update({"Authorization": test_service_token_factory(user)})
    elif "Authorization" not in request_headers.keys():
        request_headers.update({'x-anonymous-consumer': 'true'})

    if request_headers.get('content-type', "application/json") == "application/json":
        handler_kwargs = {"json": request_body}
    else:
        handler_kwargs = {"data": request_body}

    request_headers.pop('content-type', None)

    request, response = handler(endpoint,
                                debug=True,
                                headers=request_headers,
                                **handler_kwargs)

    assert expected_response_status == response.status, response.text

    response_body = response.text

    try:
        response_body = json.loads(response.text)
    except ValueError:
        pass

    test_api_endpoint_assertion(response, response_body, expected_response_body, expected_response_status)


def test_api_endpoint_assertion(response, response_body, expected_response_body, expected_response_status):
    response_status_category = int(expected_response_status / 100)
    assertion_message = f"\nExpected: {expected_response_body}\n\nReturned: {response_body}"

    if response_status_category == 2:
        if isinstance(response_body, dict) and isinstance(expected_response_body, dict):
            assert expected_response_body == response_body, assertion_message
        elif isinstance(response_body, dict) and isinstance(expected_response_body, list):
            assert sorted(expected_response_body) == sorted(response_body.keys()), assertion_message
        elif isinstance(response_body, list) and isinstance(expected_response_body, list):
            assert sorted(response_body) == sorted(expected_response_body), assertion_message
        elif isinstance(response_body, list) and isinstance(expected_response_body, int):
            assert expected_response_body == len(response_body), assertion_message
        elif isinstance(expected_response_body, str):
            assert expected_response_body == response_body, assertion_message
        else:
            raise RuntimeError("Shouldn't be in here. Check response type.")
    elif response_status_category == 3:
        raise RuntimeError("Shouldn't be in here. Redirects not possible.")
    elif response_status_category == 4:
        # if http status code is in the 4 hundreds, check error code
        if isinstance(expected_response_body, dict):
            assert expected_response_body == response_body, assertion_message
        elif isinstance(expected_response_body, list):
            assert sorted(expected_response_body) == sorted(response_body.keys()), assertion_message
        elif isinstance(expected_response_body, Enum):
            assert expected_response_body.value == response_body['error_code']['value'], assertion_message
        elif isinstance(expected_response_body, int):
            assert expected_response_body == response_body['error_code']['value'], assertion_message
        else:
            raise RuntimeError("Shouldn't be in here. Check response type.")
    elif response_status_category == 5:
        raise RuntimeError("We got a 500 level status code, something isn't right.")


TestParams = namedtuple('TestParams', ['method', 'endpoint', 'request_headers', 'request_body',
                                       'expected_response_status', 'expected_response_body', 'user_level'])


# TestParams = namedtuple("TestParams", [k for k,v in inspect.signature(test_api_endpoint).parameters.items() if v.kind == v.KEYWORD_ONLY])

class _TokenType:
    def __init__(self, type):
        self.type = type

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.type == other.type
        else:
            return False



def test_parameter_generator(method, endpoint, *, request_headers, request_body, expected_response_status,
                             expected_response_body, check_authorization=True, check_permissions=True,
                             user_level=DEFAULT_USER_LEVEL, is_service_only=False, **kwargs):

    if check_permissions:
        if "permissions_endpoint" not in kwargs:
            raise RuntimeError("'permissions_endpoint' must be passed for permissions check parameters.")

    # auth_token = request_headers.pop("Authorization", empty)

    if "Authorization" not in request_headers and is_service_only:
        request_headers.update({"Authorization": _TokenType('service')})
    elif "Authorization" not in request_headers:
        request_headers.update({"Authorization": _TokenType('user')})


    test_parameters_template = TestParams(method=method, endpoint=endpoint, request_headers=request_headers,
                                          request_body=request_body, expected_response_status=expected_response_status,
                                          expected_response_body=expected_response_body, user_level=user_level)
    if check_authorization:
        _req_headers = request_headers.copy()
        if "Authorization" in _req_headers:
            del _req_headers['Authorization']

        p = test_parameters_template. \
            _replace(request_headers=_req_headers,
                     expected_response_status=401,
                     expected_response_body=GlobalErrorCodes.authentication_credentials_missing)
        # parameters.append(p)
        yield tuple(p)

    if check_permissions:
        p = test_parameters_template._replace(endpoint=kwargs['permissions_endpoint'],
                                              expected_response_status=403,
                                              expected_response_body=GlobalErrorCodes.permission_denied)

        yield tuple(p)

    yield tuple(test_parameters_template)


def test_parameter(method, endpoint, request_headers, request_body, expected_response_status, expected_response_body,
                   user_level=DEFAULT_USER_LEVEL):
    return [tuple(TestParams(method=method, endpoint=endpoint, request_headers=request_headers,
                             request_body=request_body, expected_response_status=expected_response_status,
                             expected_response_body=expected_response_body, user_level=user_level))]


class Pact:
    _instance = None
    servers = None
    providers = None
    used_port = [PORT] # SanicTestClient class uses 42101 port

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)

        return cls._instance

    def start_pact(cls):
        customer = settings.SERVICE_NAME
        providers = [s for s in settings.SERVICE_CONNECTIONS if s != 'userip']
        pact_dict = {}

        for provider in providers:
            port = unused_port()

            while port in cls.used_port:
                port = unused_port()

            pact_dict[provider] = {
                "pact": Consumer(customer).has_pact_with(Provider(provider), port=port),
                "port": port
            }

            pact_dict[provider]['pact'].start_service()

        cls.servers = pact_dict
        cls.providers = providers

    def stop_pact(cls):
        if cls.servers:
            for server in cls.servers.values():
                server['pact'].stop_service()

    def verify(cls):
        for provider in cls.providers:
            cls.servers[provider]['pact'].verify()


class PactMock:

    def __init__(self):
        self.service_name = None

    @property
    def url(self):
        pact = Pact()
        url_partial_path = "/api/v1/"

        port = pact.servers[self.service_name]['port']
        return URL(f'http://127.0.0.1:{port}{url_partial_path}')

    def register_mock_dispatch(self, provider, method, endpoint, response, response_status_code=200, request_body={},
                               provider_state="Empty", scenario=None):

        self.service_name = provider.lower()
        pact = Pact()
        pact = pact.servers[self.service_name]["pact"]

        pact_request_kwarg = {
            'method': method,
        }

        if endpoint:
            pact_request_kwarg.update({'path': endpoint})

        if request_body:
            pact_request_kwarg.update({'body': request_body})

        if not scenario:
            scenario = f'{provider}_{method}_{endpoint}'

        (pact
         .given(provider_state)
         .upon_receiving(scenario)
         .with_request(**pact_request_kwarg)
         .will_respond_with(response_status_code, body=response, headers={"Content-Type":"application/json"})
         )

        pact.setup()

PactMockService = PactMock()

def generate_pact_endpoint_test(env='test'):
    pact = Pact()
    pact_broker_host = settings.PACT_BROKER_URL
    PACT_ENDPOINT = []

    for provider in pact.providers:
        url = f'{pact_broker_host}/pacts/provider/{provider}/latest/{env}'
        consumer_list = requests.get(url).json()['_links']['pb:pacts']

        for consumer in consumer_list:
            consumer_service_name = consumer.get('name')
            url = consumer.get('href')

            if url and consumer_service_name:
                endpoints = requests.get(url).json()['interactions']

                for endpoint in endpoints:
                    pact_request = endpoint['request']
                    pact_response = endpoint['response']
                    PACT_ENDPOINT.extend(test_parameter_generator(
                        pact_request['method'],
                        pact_request['path'],
                        request_headers=pact_request.get('headers', {}),
                        request_body=pact_request.get('body', {}),
                        expected_response_status=pact_response['status'],
                        expected_response_body=pact_response.get('body', {}),
                        check_authorization=False,
                        check_permissions=False,
                        is_service_only=True
                    ))

    return PACT_ENDPOINT

def publish_pact(version='0.0.1', env='test'):
    pact = Pact()
    consumer = settings.SERVICE_NAME
    for provider in pact.providers:
        contract_file_path = os.path.join(os.getcwd(), f'{consumer}-{provider}.json')
        data = json.loads(open(contract_file_path).read())
        publish_url = f'{settings.PACT_BROKER_URL}/pacts/provider/{provider}/consumer/{consumer}/version/{version}.{env}'
        tag_url = f'{settings.PACT_BROKER_URL}/pacticipants/{consumer}/versions/{version}.{env}/tags/{env}'
        r = requests.put(url=publish_url, json=data)
        r.raise_for_status()
        r = requests.put(url=tag_url, headers={"Content-Type":"application/json"})
        r.raise_for_status()