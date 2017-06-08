import aioredis
import asyncio
import logging

from importlib import import_module
from inspect import isawaitable, CO_ITERABLE_COROUTINE
from threading import local

from peewee import BaseModel
from peewee_async import Manager, PooledMySQLDatabase

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
                    "CLOSE_CONNECTION_INTERFACE": ("_pool", "wait_closed")
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
                                              minsize=5, maxsize=10)

            return _pool
        elif alias == 'mysql_legacy':

            _pool = PooledMySQLDatabase(settings['WEB_MYSQL_DATABASE'],
                                        host=settings['WEB_MYSQL_HOST'],
                                        port=settings['WEB_MYSQL_PORT'],
                                        user=settings['WEB_MYSQL_USER'],
                                        password=settings['WEB_MYSQL_PASS'],
                                        min_connections=5, max_connections=10, charset='utf8', use_unicode=True)
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

        for a in self.databases.keys():
            asyncio.ensure_future(self.close(a))



    async def close(self, alias):
        try:
            logger.info("Start Closing database connection: {0}".format(alias))
            _conn = getattr(self._connections, alias)

            if isawaitable(_conn):
                _conn = await _conn

            close_connection_interface = self.databases[alias].get('CLOSE_CONNECTION_INTERFACE', [])

            close_database = _conn

            for m in close_connection_interface:
                if hasattr(close_database, m):
                    close_database = getattr(close_database, m)
                else:
                    break

            logger.info("Closing database connection: {0}".format(alias))
            delattr(self._connections, alias)
            if _conn != close_database:
                closing = close_database()

                if isawaitable(closing):
                    await closing


        except Exception as e:
            logger.info("Error when closing connection: {0}".format(alias))
            logger.info(e)


    def all(self):
        return [self[alias] for alias in self]

_connections = ConnectionHandler()


async def get_connection(alias):
    _conn = getattr(_connections, alias)

    if isawaitable(_conn) and not isinstance(_conn, aioredis.RedisPool):
        _conn = await _conn

    return _conn


async def close_database(app, loop, **kwargs):
    # app.database.close()
    await app.database.close_async()
    _connections.close_all()

    app.objects.close()



async def connect_database(app, loop=None, **kwargs):

    _connections.loop = loop

    # mysql = await get_connection('mysql_legacy')

    app.database.init(settings.WEB_MYSQL_DATABASE,
                      host=settings.WEB_MYSQL_HOST,
                      port=settings.WEB_MYSQL_PORT,
                      user=settings.WEB_MYSQL_USER,
                      password=settings.WEB_MYSQL_PASS,
                      min_connections=5, max_connections=10, charset='utf8', use_unicode=True)

    # import models and switch out database
    service_models = import_module('{0}.models'.format(settings.SERVICE_NAME))
    for m in dir(service_models):
        if m[0].isupper():
            possible_model = getattr(service_models, m)
            if isinstance(possible_model, BaseModel):
                possible_model._meta.database = app.database

    app.objects = Manager(app.database, loop=loop)
