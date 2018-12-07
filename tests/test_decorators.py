import ujson as json

from enum import Enum
from sanic.response import json as response_json

from insanic import status
from insanic.decorators import cache_get_response
from insanic.exceptions import ValidationError
from insanic.views import InsanicView


def test_cache_get_response(insanic_application, redisdb_insanic):
    response_body = {"insanic": ["gotta", "go"]}

    cache_decorator = cache_get_response()

    class CacheView(InsanicView):
        authentication_classes = ()
        permission_classes = ()

        @cache_decorator
        async def get(self, request, *args, **kwargs):
            query_params = request.query_params
            return response_json(query_params, status=status.HTTP_202_ACCEPTED)

    insanic_application.add_route(CacheView.as_view(), '/')

    request, response = insanic_application.test_client.get('/?insanic=gotta&insanic=go')

    # check response is equal to expected response
    assert response.status == status.HTTP_202_ACCEPTED
    assert response.json == response_body

    # check response value is equal to cached value
    cache_key = cache_decorator.get_key(request)
    cache_value = json.loads(redisdb_insanic.get(cache_key).decode())

    assert cache_value['body'] == response_body
    assert cache_value['status'] == response.status

    # check response value is returned from cache
    request, response = insanic_application.test_client.get('/?insanic=gotta&insanic=go')
    assert response.status == status.HTTP_202_ACCEPTED
    assert response.json == response_body


def test_cache_get_response_400(insanic_application, redisdb):

    cache_decorator = cache_get_response()

    class ErrorEnum(Enum):
        forced_error = 99999999

    class CacheView(InsanicView):
        authentication_classes = ()
        permission_classes = ()

        @cache_decorator
        async def get(self, request, *args, **kwargs):
            raise ValidationError("Force Error", error_code=ErrorEnum.forced_error)

    insanic_application.add_route(CacheView.as_view(), '/')

    request, response = insanic_application.test_client.get('/?insanic=gotta&insanic=go')

    assert response.status == status.HTTP_400_BAD_REQUEST

    # check response value is equal to cached value
    cache_key = cache_decorator.get_key(request)
    cache_value = redisdb.get(cache_key)

    assert cache_value is None

    cached_keys = redisdb.keys('insanic:*')
    assert cached_keys == []
