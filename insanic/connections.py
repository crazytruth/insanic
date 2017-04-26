import aioredis

from peewee_async import Manager, PooledMySQLDatabase

async def connect_database(app, loop, **kwargs):

    REDIS_HOST = app.config['REDIS_HOST']
    REDIS_PORT = app.config['REDIS_PORT']
    REDIS_DB = app.config['REDIS_DB']

    app.conn = {}
    app.conn['redis'] = await aioredis.create_pool((REDIS_HOST, REDIS_PORT),
                                                   encoding='utf-8', db=REDIS_DB, loop=loop, minsize=1,
                                                   maxsize=1)

    app.conn['redis_client'] = await aioredis.create_reconnecting_redis((REDIS_HOST, REDIS_PORT),
                                                                        encoding='utf-8', db=REDIS_DB, loop=loop)

    app.objects = Manager(app.database, loop=loop)

async def close_database(app, loop, **kwargs):

    app.conn['redis'].close()
    # app.conn['redis_client'].close()
    app.objects.close()

