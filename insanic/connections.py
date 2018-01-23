import aioredis
import asyncio
import logging
import traceback

from inspect import isawaitable, CO_ITERABLE_COROUTINE
from threading import local

from insanic.conf import settings
from insanic.functional import cached_property

logger = logging.getLogger('sanic')

class ConnectionHandler:

    def __init__(self, databases=None):
        """
        databases is an optional dictionary of database definitions (structured
        like settings.DATABASES).
        """
        self._databases = databases
        self._connections = local()
        self._loop = None

    @property
    def loop(self):
        if self._loop is None:
            self._loop = asyncio.get_event_loop()

        return self._loop

    @loop.setter
    def loop(self, loop):
        self._loop = loop


    @cached_property
    def databases(self):
        if self._databases is None:
            self._databases = {
                "redis": {
                    "ENGINE": "aioredis",
                    "CONNECTION_INTERFACE" : "create_pool",
                    "CLOSE_CONNECTION_INTERFACE": (('close',), ("wait_closed",))
                },
            }

        return self._databases

    async def _get_connection(self, alias):
        # if hasattr(self._connections, alias):
        #     return getattr(self._connections, alias)

        # db = self.databases[alias]
        # conn = await self.connect(alias)
        conn = await self.connect(alias)
        setattr(self._connections, alias, conn)

        return conn

    async def connect(self, alias):
        # if alias == "redis_client":

        if alias == "redis":
            _pool = await aioredis.create_pool((settings.REDIS_HOST, settings.REDIS_PORT),
                                              encoding='utf-8', db=settings.REDIS_DB, loop=self.loop,
                                              minsize=5, maxsize=10)

            return _pool

    def __getitem__(self, alias):
        if hasattr(self._connections, alias):
            return getattr(self._connections, alias)

        conn = asyncio.wait(self.connect(alias))
        setattr(self._connections, alias, conn)
        return conn

    def __getattr__(self, item):
        if hasattr(self._connections, item):
            return getattr(self._connections, item)
        return self._get_connection(item)

    def __setitem__(self, key, value):
        setattr(self._connections, key, value)

    def __delitem__(self, key):
        delattr(self._connections, key)

    def __delattr__(self, item):
        delattr(self._connections, item)

    def __iter__(self):
        return iter(self.databases)

    def close_all(self):

        close_tasks = []
        for a in self.databases.keys():
            close_tasks.append(asyncio.ensure_future(self.close(a)))

        return asyncio.gather(*close_tasks)

    async def close(self, alias):
        try:
            logger.info("Start Closing database connection: {0}".format(alias))
            if hasattr(self._connections, alias):
                _conn = getattr(self._connections, alias)
            else:
                raise AttributeError("{0} is not connected.")

            # if isawaitable(_conn):
            #     _conn = await _conn

            close_connection_interface = self.databases[alias].get('CLOSE_CONNECTION_INTERFACE', [])

            logger.info("Closing database connection: {0}".format(alias))
            for close_attr in close_connection_interface:
                close_database = _conn
                for m in close_attr:
                    if hasattr(close_database, m):
                        close_database = getattr(close_database, m)
                    else:
                        break

                if _conn != close_database:
                    closing = close_database()

                    if isawaitable(closing):
                        await closing
        except AttributeError:
            pass

        except Exception as e:
            logger.info("Error when closing connection: {0}".format(alias))
            logger.info(e)
            traceback.print_exc()
        finally:

            if hasattr(self._connections, alias):
                delattr(self._connections, alias)


    def all(self):
        return [self[alias] for alias in self]

_connections = ConnectionHandler()


async def get_connection(alias):
    _conn = getattr(_connections, alias)

    if isawaitable(_conn) and not isinstance(_conn, aioredis.RedisPool):
        _conn = await _conn

    return _conn


async def get_future_connection(alias, future):
    _conn = getattr(_connections, alias)

    if isawaitable(_conn) and not isinstance(_conn, aioredis.RedisPool):
        _conn = await _conn
        future.set_result(_conn)

    # return _conn



