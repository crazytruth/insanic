import asyncio

from ujson import loads as jsonloads, dumps as jsondumps
from functools import wraps

from insanic.conf import settings
from insanic.connections import get_connection
from sanic.response import json

SEGMENT_DELIMITER = ":"
QUERY_PARAM_DELIMITER = "|"


class cache_get_response:
    """
    On the request to a view method with GET,
        first check if the relevant news_item can be found from Redis and update if it does not exist.

    :param ttl: time to live for the cache
    :param status: status code for other than 200
    :return:
    """

    def __init__(self, ttl=300):
        self.ttl = ttl

    def __call__(self, func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            view = args[0]
            request = view.request
            assert request.method == "GET", "Can only cache GET methods."

            redis = await get_connection("insanic")
            key = self.get_key(request)
            response = await self.get(redis, key)
            if response:
                return response
            view_response = await func(*args, **kwargs)

            # only cache if response status is 200
            if 200 <= view_response.status < 300:
                asyncio.ensure_future(
                    self.update(view_response, redis, key, self.ttl)
                )
            return view_response

        return wrapper

    def get_key(self, request):
        """
        Returns the Key for Redis in the following format:
        "{service_name}:{endpoint}:<query_param1>:{query_param1}:<query_param2>:{query_param2}....
        """

        service_name = settings.SERVICE_NAME
        uri = request.path

        to_join = [service_name, uri]
        query_params = request.query_params
        for key in sorted(list(query_params.keys())):
            query_param = QUERY_PARAM_DELIMITER.join(query_params.getlist(key))
            to_join.extend([key, query_param])

        key = SEGMENT_DELIMITER.join(to_join)
        return key

    async def get(self, redis, key):
        with await redis as conn:
            value = await conn.get(key)
            if value:
                value = jsonloads(value)
                return json(value["body"], status=value["status"])
            else:
                return None

    async def update(self, response, redis, key, ttl):

        cache_data = jsondumps(
            {"status": response.status, "body": jsonloads(response.body)}
        )

        with await redis as conn:
            await conn.set(key, cache_data, expire=ttl)
