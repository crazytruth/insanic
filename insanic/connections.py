import aioredis
import asyncio
import types

from inspect import isawaitable, CO_ITERABLE_COROUTINE
from threading import local

from peewee_async import Manager, PooledMySQLDatabase

from insanic.conf import settings
from insanic.functional import cached_property


class _PersistentAsyncConnectionContextManager:
    __slots__ = ('_pool', '_conn')

    def __init__(self, pool):
        self._pool = pool
        self._conn = None

    @asyncio.coroutine
    def __aenter__(self):
        self._conn = yield from self._pool.acquire()
        return self._conn

    @asyncio.coroutine
    def __aexit__(self, exc_type, exc_value, tb):
        try:
            self._pool.release(self._conn)
        finally:
            self._conn = None


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
                    "CONNECTION_INTERFACE" : "create_reconnecting_redis"
                },
                "mysql_legacy" : {
                    "ENGINE": ""
                }
            }

        return self._databases

    async def _get_connection(self, alias):
        if hasattr(self._connections, alias):
            return getattr(self._connections, alias)

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
                                              minsize=1, maxsize=1)

            return _PersistentAsyncConnectionContextManager(_pool)

            # return await aioredis.create_pool((settings.REDIS_HOST, settings.REDIS_PORT),
            #                                   encoding='utf-8', db=settings.REDIS_DB, loop=self._loop, minsize=1,
            #                                   maxsize=1)


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

    def __iter__(self):


        return iter(self.databases)

    async def close_all(self):
        for a in self.databases.keys():
            await self.close(a)


    async def close(self, alias):

        _conn = getattr(self, alias)

        if isawaitable(_conn):
            _conn = await _conn

        if hasattr(_conn, 'close'):
            _conn.close()


    def all(self):
        return [self[alias] for alias in self]

_connections = ConnectionHandler()


async def get_connection(alias):
    _conn = getattr(_connections, alias)

    if isawaitable(_conn) and not isinstance(_conn, aioredis.RedisPool):
        _conn = await _conn

    return _conn


async def close_database(app, loop, **kwargs):


    await _connections.close_all()

    app.objects.close()

async def connect_database(app, loop=None, **kwargs):

    _connections.loop = loop

    app.objects = Manager(app.database, loop=loop)
