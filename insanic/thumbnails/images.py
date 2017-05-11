import ujson as json

from insanic.thumbnails.helpers import tokey, deserialize, get_module_class
from insanic.thumbnails.storages.s3_storage import storage as default_storage
from insanic.thumbnails.engines.pil_engine import engine

def serialize_image_file(image_file):
    if image_file.size is None:
        raise ThumbnailError('Trying to serialize an ``ImageFile`` with a '
                             '``None`` size.')
    data = {
        'name': image_file.name,
        'storage': image_file.serialize_storage(),
        'size': image_file.size,
    }
    return json.dumps(data)


def deserialize_image_file(s):
    data = deserialize(s)

    # class LazyStorage(LazyObject):
    #     def _setup(self):
    #         self._wrapped = get_module_class(data['storage'])()

    image_file = ImageFile(data['name'], get_module_class(data['storage'])())
    image_file.set_size(data['size'])
    return image_file


class BaseImageFile(object):
    size = []

    def exists(self):
        raise NotImplemented()

    @property
    def width(self):
        return self.size[0]

    x = width

    @property
    def height(self):
        return self.size[1]

    y = height

    def is_portrait(self):
        return self.y > self.x

    @property
    def ratio(self):
        return float(self.x) / float(self.y)

    @property
    def url(self):
        raise NotImplemented()

    src = url


class ImageFile(BaseImageFile):
    _size = None

    def __init__(self, file_, storage=None):

        # figure out name
        self.name = str(file_)

        # figure out storage
        if storage is not None:
            self.storage = storage
        elif hasattr(file_, 'storage'):
            self.storage = file_.storage
        else:
            self.storage = default_storage

        if hasattr(self.storage, 'location'):
            location = self.storage.location
            if not self.storage.location.endswith("/"):
                location += "/"
            if self.name.startswith(location):
                self.name = self.name[len(location):]

    def __unicode__(self):
        return self.name

    async def exists(self):
        return await self.storage.exists(self.name)

    async def set_size(self, size=None):
        # set the size if given
        if size is not None:
            pass
        # Don't try to set the size the expensive way if it already has a
        # value.
        elif self._size is not None:
            return
        elif hasattr(self.storage, 'image_size'):
            # Storage backends can implement ``image_size`` method that
            # optimizes this.
            size = self.storage.image_size(self.name)
        else:
            # This is the worst case scenario
            image = await engine.get_image(self)
            size = engine.get_image_size(image)
        self._size = list(size)

    # @property
    # def size(self):
    #     return self._size

    @property
    async def url(self):
        return await self.storage.url(self.name)

    async def read(self):
        f = await self.storage.open(self.name)

        return await f.read()

    async def write(self, content):
        self._size = None
        self.name = await self.storage.save(self.name, content)

        return self.name
    #
    # def delete(self):
    #     return self.storage.delete(self.name)
    #
    def serialize_storage(self):

        cls = self.storage.__class__
        return '%s.%s' % (cls.__module__, cls.__name__)

    @property
    def key(self):
        return tokey(self.name, self.serialize_storage())
    #
    # def serialize(self):
    #     return serialize_image_file(self)