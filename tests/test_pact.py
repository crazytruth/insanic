import json
import os
import pytest
import uuid

from insanic.conf import settings
from insanic.services import Service
from insanic.testing.helpers import Pact, PactMockService, generate_pact_endpoint_test


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
def pact(monkeypatch):
    monkeypatch.setattr(settings, 'SERVICE_NAME', 'event')
    monkeypatch.setattr(settings, 'SERVICE_CONNECTIONS', ['userip','artist','promotion'])
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

async def test_pact_class(pact, monkeypatch):
    assert pact.providers == ['artist', 'promotion']

    PactMockService.register_mock_dispatch(
        'promotion', PROMOTION_METHOD, PROMOTION_URL, PROMOTION_RESPONSE_BODY, PROMOTION_STATUS
    )
    PactMockService.register_mock_dispatch(
        'artist', ARTIST_METHOD, ARTIST_URL, ARTIST_RESPONSE_BODY, ARTIST_STATUS, request_body=ARTIST_PAYLOAD
    )

    promotion = Service('promotion')
    monkeypatch.setattr(promotion, 'host', host('127.0.0.1') )
    monkeypatch.setattr(promotion, 'port', pact.servers['promotion']['port'])

    result, status = await promotion.http_dispatch(
        method=PROMOTION_METHOD, endpoint=PROMOTION_URL, include_status_code=True
    )
    assert result == PROMOTION_RESPONSE_BODY
    assert status == PROMOTION_STATUS

    artist = Service('artist')
    monkeypatch.setattr(artist, 'host', host('127.0.0.1'))
    monkeypatch.setattr(artist, 'port', pact.servers['artist']['port'])

    result, status = await artist.http_dispatch(
        method=ARTIST_METHOD, endpoint=ARTIST_URL, payload=ARTIST_PAYLOAD, include_status_code=True
    )
    assert result == ARTIST_RESPONSE_BODY
    assert status == ARTIST_STATUS