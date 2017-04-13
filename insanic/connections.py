import aioredis

from peewee_async import Manager, PooledMySQLDatabase

async def connect_database(app, loop, **kwargs):

    REDIS_HOST = app.config['REDIS_HOST']
    REDIS_PORT = app.config['REDIS_PORT']
    REDIS_DB = app.config['REDIS_DB']

    app.conn = {}
    app.conn['redis'] = await aioredis.create_pool((REDIS_HOST, REDIS_PORT),
                                                   encoding='utf-8', db=REDIS_DB, loop=loop, minsize=5,
                                                   maxsize=10)

    app.objects = Manager(app.database, loop=loop)


async def close_database(app, loop, **kwargs):

    app.conn['redis'].close()
    app.objects.close()
