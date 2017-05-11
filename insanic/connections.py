import aioredis
import asyncio

from threading import local

from peewee_async import Manager, PooledMySQLDatabase

from insanic.conf import settings
from insanic.functional import cached_property

async def close_database(app, loop, **kwargs):

    app.conn['redis'].close()
    # app.conn['redis_client'].close()
    app.objects.close()

class ConnectionHandler:

    def __init__(self, databases=None):
        """
        databases is an optional dictionary of database definitions (structured
        like settings.DATABASES).
        """
        self._databases = databases
        self._connections = local()

    def set_loop(self, loop):

        self._loop = loop

    @cached_property
    def databases(self):
        if self._databases is None:
            self._databases = {
                "redis": {
                    "ENGINE": "aioredis",
                    "CONNECTION_INTERFACE" : "create_pool"
                },
                'redis_client': {
                    "ENGINE": "aioredis",
                    "CONNECTION_INTERFACE": "create_reconnecting_redis"
                },
                "mysql_legacy" : {
                    "ENGINE": ""
                }
            }

        return self._databases

    async def get_connection(self, alias):
        if hasattr(self._connections, alias):
            return getattr(self._connections, alias)

        # db = self.databases[alias]
        conn = await self.connect(alias)
        setattr(self._connections, alias, conn)
        return conn

    async def connect(self, alias):
        if alias == "redis_client":
            return await aioredis.create_reconnecting_redis((settings.REDIS_HOST, settings.REDIS_PORT),
                                                            encoding='utf-8', db=settings.REDIS_DB, loop=self._loop)
        elif alias == "redis":
            return await aioredis.create_pool((settings.REDIS_HOST, settings.REDIS_PORT),
                                              encoding='utf-8', db=settings.REDIS_DB, loop=self._loop, minsize=1,
                                              maxsize=1)


    def __getitem__(self, alias):
        if hasattr(self._connections, alias):
            return getattr(self._connections, alias)

        conn = asyncio.wait(self.connect(alias))
        setattr(self._connections, alias, conn)
        return conn



    def __setitem__(self, key, value):
        setattr(self._connections, key, value)

    def __delitem__(self, key):
        delattr(self._connections, key)

    def __iter__(self):
        return iter(self.databases)

    def all(self):
        return [self[alias] for alias in self]

connections = ConnectionHandler()


async def connect_database(app, loop=None, **kwargs):

    REDIS_HOST = app.config['REDIS_HOST']
    REDIS_PORT = app.config['REDIS_PORT']
    REDIS_DB = app.config['REDIS_DB']

    connections.set_loop(loop)
    app.conn = {}
    app.conn['redis'] = await aioredis.create_pool((REDIS_HOST, REDIS_PORT),
                                                   encoding='utf-8', db=REDIS_DB, loop=loop, minsize=1,
                                                   maxsize=1)

    # app.conn['redis_client'] = await aioredis.create_reconnecting_redis((REDIS_HOST, REDIS_PORT),
    #                                                                     encoding='utf-8', db=REDIS_DB, loop=loop)
    app.conn['redis_client'] = await connections.get_connection('redis_client')

    app.objects = Manager(app.database, loop=loop)
