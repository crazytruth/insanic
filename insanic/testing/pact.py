import os
import json
import requests
import socket

from yarl import URL
from pact import Consumer, Provider
from sanic.testing import PORT

from insanic.conf import settings


# copied from pytest-sanic
def unused_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Pact:
    _instance = None
    servers = None
    providers = None
    used_port = [PORT]  # SanicTestClient class uses 42101 port

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
         .will_respond_with(response_status_code, body=response, headers={"Content-Type": "application/json"})
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
        r = requests.put(url=tag_url, headers={"Content-Type": "application/json"})
        r.raise_for_status()
