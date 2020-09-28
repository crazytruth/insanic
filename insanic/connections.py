import aioredis
import asyncio
import logging
import traceback

from inspect import isawaitable
from threading import local

from insanic.conf import settings
from insanic.exceptions import ImproperlyConfigured
from insanic.functional import cached_property

logger = logging.getLogger("root")


class ConnectionHandler:
    def __init__(self):
        """
        databases is an optional dictionary of database definitions (structured
        like settings.DATABASES).
        """
        self._caches = None
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
    def caches(self):
        if self._caches is None:
            caches = settings.INSANIC_CACHES

            for k, v in settings.CACHES.items():
                if k in caches:
                    raise ImproperlyConfigured(
                        f"Cannot override {k}.  This is a "
                        f"protected cache reserved for insanic use."
                    )
                caches.update({k: v})

            self._caches = caches

        return self._caches

    async def _get_connection(self, alias):
        conn = await self.connect(alias)
        setattr(self._connections, alias, conn)

        return conn

    async def connect(self, alias):
        # if alias == "redis_client":
        connection_config = self.caches[alias]

        _pool = await aioredis.create_pool(
            (connection_config["HOST"], connection_config["PORT"]),
            encoding="utf-8",
            db=int(connection_config.get("DATABASE", 0)),
            loop=self.loop,
            minsize=1,
            maxsize=10,
        )

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
        return iter(self.caches)

    def close_all(self):

        close_tasks = []
        for a in self.caches.keys():
            close_tasks.append(asyncio.ensure_future(self.close(a)))

        return asyncio.gather(*close_tasks)

    async def close(self, alias):
        try:
            logger.debug("Start Closing database connection: {0}".format(alias))
            if hasattr(self._connections, alias):
                _conn = getattr(self._connections, alias)
            else:
                raise AttributeError("{0} is not connected.")

            # if isawaitable(_conn):
            #     _conn = await _conn
            _conn.close()
            await _conn.wait_closed()
            logger.debug("Closing database connection: {0}".format(alias))
        except AttributeError:
            pass
        except Exception as e:
            logger.info("Error when closing connection: {0}".format(alias))
            logger.info(e)
            traceback.print_exc()
        finally:
            if hasattr(self._connections, alias):
                delattr(self._connections, alias)
            self.loop = None

    def all(self):
        return [self[alias] for alias in self]


_connections = ConnectionHandler()


async def get_connection(alias):
    _conn = getattr(_connections, alias)

    if isawaitable(_conn) and not isinstance(_conn, aioredis.ConnectionsPool):
        _conn = await _conn

    return aioredis.Redis(_conn)
