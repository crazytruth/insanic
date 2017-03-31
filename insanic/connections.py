import aioredis

from peewee_async import Manager, PooledMySQLDatabase

from . import app

MYSQL_DATABASE = app.config['MYSQL_DATABASE']
MYSQL_HOST = app.config['MYSQL_HOST']
MYSQL_PORT = app.config['MYSQL_PORT']
MYSQL_USER = app.config['MYSQL_USER']
MYSQL_PWD = app.config['MYSQL_PWD']

REDIS_HOST = app.config['REDIS_HOST']
REDIS_PORT = app.config['REDIS_PORT']
REDIS_DB = app.config['REDIS_DB']

database = PooledMySQLDatabase(MYSQL_DATABASE, host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
                               password=MYSQL_PWD, min_connections=5, max_connections=10)

async def connect_database(app, loop, **kwargs):

    app.conn = {}
    app.conn['redis'] = await aioredis.create_pool((REDIS_HOST, REDIS_PORT),
                                                   encoding='utf-8', db=REDIS_DB, loop=loop, minsize=5,
                                                   maxsize=10)

    app.objects = Manager(database, loop=loop)


async def close_database(app, loop, **kwargs):

    app.conn['redis'].close()
    app.objects.close()
