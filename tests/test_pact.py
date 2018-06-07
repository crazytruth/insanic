import json
import os
import pytest
import uuid

from insanic.conf import settings
from insanic.services import Service
from insanic.testing.helpers import Pact, PactMockService, generate_pact_endpoint_test, publish_pact


PROMOTION_UUID = uuid.uuid4().hex
PROMOTION_METHOD = 'GET'
PROMOTION_URL = f'/api/v1/promotions/{PROMOTION_UUID}'
PROMOTION_STATUS = 200
PROMOTION_RESPONSE_BODY = {"result": True}

ARTIST_UUID = uuid.uuid4().hex
ARTIST_METHOD = 'POST'
ARTIST_URL = f'/api/v1/artists/'
ARTIST_PAYLOAD = {'artist_id': ARTIST_UUID}
ARTIST_STATUS = 200
ARTIST_RESPONSE_BODY = {"result": [1,2,3]}


def host(host):
    return host

@pytest.fixture(scope="function")
def pact_with_real_service(monkeypatch):
    monkeypatch.setattr(settings, 'SERVICE_NAME', 'event')
    monkeypatch.setattr(settings, 'SERVICE_CONNECTIONS', ['userip','artist','promotion'])
    monkeypatch.setattr(settings, 'PACT_BROKER_URL', 'http://manager.msa.swarm:82')

    pact = Pact()
    pact.start_pact()
    yield pact
    pact.stop_pact()

    event_artist_file_path = os.path.join(os.getcwd(), 'event-artist.json')
    event_promotion_file_path = os.path.join(os.getcwd(), 'event-promotion.json')
    pact_log_file_path = os.path.join(os.getcwd(), 'pact-mock-service.log')

    assert os.path.exists(event_artist_file_path)
    assert os.path.exists(event_promotion_file_path)

    with open(event_artist_file_path) as f:
        contract = json.load(f)
        response = contract['interactions'][0]['response']
        assert response['status'] == ARTIST_STATUS
        assert response['body'] == ARTIST_RESPONSE_BODY

    with open(event_promotion_file_path) as f:
        contract = json.load(f)
        response = contract['interactions'][0]['response']
        assert response['status'] == PROMOTION_STATUS
        assert response['body'] == PROMOTION_RESPONSE_BODY

    os.remove(event_artist_file_path)
    os.remove(event_promotion_file_path)
    os.remove(pact_log_file_path)

async def test_pact_class(pact_with_real_service, monkeypatch):
    assert pact_with_real_service.providers == ['artist', 'promotion']

    PactMockService.register_mock_dispatch(
        'promotion', PROMOTION_METHOD, PROMOTION_URL, PROMOTION_RESPONSE_BODY, PROMOTION_STATUS
    )
    PactMockService.register_mock_dispatch(
        'artist', ARTIST_METHOD, ARTIST_URL, ARTIST_RESPONSE_BODY, ARTIST_STATUS, request_body=ARTIST_PAYLOAD
    )

    promotion = Service('promotion')
    monkeypatch.setattr(promotion, 'host', host('127.0.0.1') )
    monkeypatch.setattr(promotion, 'port', pact_with_real_service.servers['promotion']['port'])

    result, status = await promotion.http_dispatch(
        method=PROMOTION_METHOD, endpoint=PROMOTION_URL, include_status_code=True
    )
    assert result == PROMOTION_RESPONSE_BODY
    assert status == PROMOTION_STATUS

    artist = Service('artist')
    monkeypatch.setattr(artist, 'host', host('127.0.0.1'))
    monkeypatch.setattr(artist, 'port', pact_with_real_service.servers['artist']['port'])

    result, status = await artist.http_dispatch(
        method=ARTIST_METHOD, endpoint=ARTIST_URL, payload=ARTIST_PAYLOAD, include_status_code=True
    )
    assert result == ARTIST_RESPONSE_BODY
    assert status == ARTIST_STATUS

RESPONSE_BODY = {"random": uuid.uuid4().hex}

@pytest.fixture(scope="function")
def pact_with_dummy_service(monkeypatch):
    monkeypatch.setattr(settings, 'SERVICE_NAME', 'test_consumer')
    monkeypatch.setattr(settings, 'SERVICE_CONNECTIONS', ['userip', 'test_provider'])
    monkeypatch.setattr(settings, 'PACT_BROKER_URL', 'http://manager.msa.swarm:82')
    pact = Pact()
    pact.start_pact()

    yield pact

async def test_publish(pact_with_dummy_service, monkeypatch):
    PactMockService.register_mock_dispatch('test_provider', 'GET', '/test', RESPONSE_BODY, 200)

    test_provider = Service('test_provider')
    monkeypatch.setattr(test_provider, 'host', host('127.0.0.1'))
    monkeypatch.setattr(test_provider, 'port', pact_with_dummy_service.servers['test_provider']['port'])

    result, status = await test_provider.http_dispatch(
        method='GET', endpoint='/test', include_status_code=True
    )
    assert result == RESPONSE_BODY
    assert status == 200

    pact_with_dummy_service.stop_pact()

    publish_pact()

    contract_file_path = os.path.join(os.getcwd(), 'test_consumer-test_provider.json')
    pact_log_file_path = os.path.join(os.getcwd(), 'pact-mock-service.log')

    assert os.path.exists(contract_file_path)
    assert os.path.exists(pact_log_file_path)

    os.remove(contract_file_path)
    os.remove(pact_log_file_path)

def test_generate_pact_endpoint(pact_with_dummy_service):
    pact_with_dummy_service.stop_pact()
    endpoint = generate_pact_endpoint_test()
    assert endpoint[0][5] == RESPONSE_BODY

    pact_log_file_path = os.path.join(os.getcwd(), 'pact-mock-service.log')
    os.remove(pact_log_file_path)