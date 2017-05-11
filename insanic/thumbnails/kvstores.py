import ujson as json
from insanic.conf import settings
from insanic.connections import connections
from insanic.thumbnails.helpers import deserialize
from insanic.thumbnails.images import serialize_image_file, deserialize_image_file

def add_prefix(key, identity='image'):
    """
    Adds prefixes to the key
    """
    return '||'.join(['mmt', identity, key])


class KVStore:

    def __init__(self):
        self._connection_handler = connections.get_connection('redis_client')



        # if hasattr(settings, 'THUMBNAIL_REDIS_URL'):
        #     self.connection = redis.from_url(settings.THUMBNAIL_REDIS_URL)
        # else:
        #     self.connection = redis.Redis(
        #         host=settings.THUMBNAIL_REDIS_HOST,
        #         port=settings.THUMBNAIL_REDIS_PORT,
        #         db=settings.THUMBNAIL_REDIS_DB,
        #         password=settings.THUMBNAIL_REDIS_PASSWORD,
        #         unix_socket_path=settings.THUMBNAIL_REDIS_UNIX_SOCKET_PATH,
        #     )

    # async def get_client(self):
    #     return await self.connection['redi']
    #

    @property
    async def connection(self):
        if hasattr(self, '_connection'):
            return self._connection

        conn = await self._connection_handler
        self._connection = conn
        return self._connection


    async def _get_raw(self, key):
        conn = await self.connection
        return await conn.get(key)

    # def _get_raw(self, key):
    #     return self.connection.get(key)

    async def _set_raw(self, key, value):
        conn = await self.connection
        return await conn.set(key, value)

    async def _delete_raw(self, *keys):
        conn = await self.connection
        return conn.delete(*keys)

    def _find_keys_raw(self, prefix):
        pattern = prefix + '*'
        return list(map(lambda key: key.decode('utf-8'),
                        self.connection.keys(pattern=pattern)))


    async def get(self, image_file):
        """
        Gets the ``image_file`` from store. Returns ``None`` if not found.
        """
        return await self._get(image_file.key)

    async def set(self, image_file, source=None):
        """
        Updates store for the `image_file`. Makes sure the `image_file` has a
        size set.
        """
        await image_file.set_size()  # make sure its got a size
        await self._set(image_file.key, image_file)
        if source is not None:
            get_source = await self.get(source)

            if not get_source:
                # make sure the source is in kvstore
                raise ThumbnailError('Cannot add thumbnails for source: `%s` '
                                     'that is not in kvstore.' % source.name)

            # Update the list of thumbnails for source.
            thumbnails = await self._get(source.key, identity='thumbnails') or []
            thumbnails = set(thumbnails)
            thumbnails.add(image_file.key)

            await self._set(source.key, list(thumbnails), identity='thumbnails')

    async def get_or_set(self, image_file):
        cached = await self.get(image_file)
        if cached is not None:
            return cached
        await self.set(image_file)
        return image_file

    async def _get(self, key, identity='image'):
        """
        Deserializing, prefix wrapper for _get_raw
        """
        value = await self._get_raw(add_prefix(key, identity))

        if not value:
            return None

        if identity == 'image':
            return deserialize_image_file(value)

        return deserialize(value)

    async def _set(self, key, value, identity='image'):
        """
        Serializing, prefix wrapper for _set_raw
        """
        if identity == 'image':
            s = serialize_image_file(value)
        else:
            s = json.dumps(value, sort_keys=True)
        await self._set_raw(add_prefix(key, identity), s)

kvstore = KVStore()