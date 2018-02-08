import asyncio

from ujson import loads as jsonloads
from functools import wraps

from insanic import status
from insanic.conf import settings
from insanic.connections import get_connection
from sanic.response import json


def cache_get_response(ttl=300, status=status.HTTP_200_OK):
    """
    On the request to a view method with GET,
        first check if the relevant news_item can be found from Redis and update if it does not exist.

    :param ttl: time to live for the cache
    :param status: status code for other than 200
    :return:
    """

    def get_key(request):
        """
        Returns the Key for Redis in the following format:
        "{service_name}:{endpoint}:<query_param1>:{query_param1}:<query_param2>:{query_param2}....

        """

        service_name = settings.SERVICE_NAME
        uri = request.path

        to_join = [service_name, uri]
        query_params = request.query_params
        for key in sorted(list(query_params.keys())):
            query_param = query_params.get(key)
            to_join.extend([key, query_param])

        key = ":".join(to_join)
        return key

    async def get(redis, key):
        async with redis.get() as conn:
            value = await conn.get(key)
            if value:
                value = jsonloads(value)
                return json(value, status=status)
            else:
                return None

    async def update(response, redis, key, ttl):
        async with redis.get() as conn:
            await conn.set(key, response.body, expire=ttl)

    def decorator(func):

        @wraps(func)
        async def wrapper(*args, **kwargs):
            view = args[0]
            request = view.request
            assert request.method == "GET", "Can only cache GET methods."

            redis = await get_connection('redis')
            key = get_key(request)
            response = await get(redis, key)
            if response:
                return response
            view_response = await func(*args, **kwargs)
            asyncio.ensure_future(update(view_response, redis, key, ttl))
            return view_response

        return wrapper

    return decorator
