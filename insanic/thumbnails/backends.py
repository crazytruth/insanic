import aiobotocore
import asyncio
import os
import ujson as json
import logging

from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from io import BytesIO
from PIL import Image
from sanic.request import File


from insanic.conf import settings
from insanic.connections import get_connection
from insanic.thumbnails.helpers import tokey

from insanic.thumbnails.engines import engine

from insanic.thumbnails.parsers import parse_geometry

EXTENSIONS = {
    'JPEG': 'jpg',
    'PNG': 'png',
}

logger = logging.getLogger('sanic')

class ThumbnailGenerator:

    default_options = {
        'format': settings.get('THUMBNAIL_FORMAT', 'JPEG'),
        'quality': settings.get('THUMBNAIL_QUALITY', 95),
        'colorspace': settings.get('THUMBNAIL_COLORSPACE', 'RGB'),
        'upscale': settings.get('THUMBNAIL_UPSCALE', True),
        'crop': False,
        'cropbox': None,
        'rounded': None,
        'padding': settings.get('THUMBNAIL_PADDING', False),
        'padding_color': settings.get('THUMBNAIL_PADDING_COLOR', '#ffffff')
    }

    def make_thumbnail(self, file, dimension=None):
        log = logging.getLogger('threads')
        log.debug('starting make_thumbnail')

        try:
            if dimension is not None:
                file = self.generate_thumbnail(file, dimension)

            if file is None:
                return None
        except Exception as e:
            log.debug(e)
            raise e

        return file

    def _get_format(self, source):
        file_extension = self.file_extension(source)

        if file_extension == '.jpg' or file_extension == '.jpeg':
            return 'JPEG'
        else:
            return 'PNG'

    def file_extension(self, source):
        return os.path.splitext(source.name)[1].lower()


    def generate_thumbnail(self, file, dimension, **options):
        if dimension == "blur":
            dimension = "500x500"
            options.update({"crop": "center"})
            options.update({"blur": 10})
        else:
            options.update({"crop": "center"})
            options.update({"quality": 95})


        options.setdefault('format', self._get_format(file))
        for key, value in self.default_options.items():
            options.setdefault(key, value)

        buffer = BytesIO(file.body)
        source_image = Image.open(buffer)

        x, y = source_image.size
        ratio = float(x) / y

        geometry = parse_geometry(dimension, ratio)

        try:
            image = engine.create(source_image, geometry, options)
            raw_data = engine.write_sync(image, options)
            thumbnail = File(type=file.type, body=raw_data, name=file.name)
        except IOError:
            thumbnail = None

        return thumbnail



class ThumbnailBackend:
    _session = None

    default_options = {
        'format': settings.get('THUMBNAIL_FORMAT', 'JPEG'),
        'quality': settings.get('THUMBNAIL_QUALITY', 95),
        'colorspace': settings.get('THUMBNAIL_COLORSPACE', 'RGB'),
        'upscale': settings.get('THUMBNAIL_UPSCALE', True),
        'crop': False,
        'cropbox': None,
        'rounded': None,
        'padding': settings.get('THUMBNAIL_PADDING', False),
        'padding_color': settings.get('THUMBNAIL_PADDING_COLOR', '#ffffff')
    }



    def _get_thumbnail_filename(self, source, geometry_string, options):
        """
        Computes the destination filename.
        """
        key = tokey(source.key, geometry_string, json.dumps(options, sort_keys=True))
        # make some subdirs
        path = '%s/%s/%s' % (key[:2], key[2:4], key)
        return '%s.%s' % (path, EXTENSIONS[options['format']])

    async def _create_thumbnail(self, source_image, geometry_string, options,
                          thumbnail):
        """
        Creates the thumbnail by using default.engine
        """

        ratio = engine.get_image_ratio(source_image, options)
        geometry = parse_geometry(geometry_string, ratio)
        image = engine.create(source_image, geometry, options)
        await engine.write(image, options, thumbnail)
        # It's much cheaper to set the size here
        size = engine.get_image_size(image)
        await thumbnail.set_size(size)

    # async def _get_correct_url(self, thumbnail):
    #     environment = settings.MMT_ENV
    #     new_url = await thumbnail.url
    #     if not new_url:
    #         return thumbnail
    #
    #     scheme, netloc, path, qs, anchor = urlsplit(thumbnail.url)
    #     new_url = new_url.replace(scheme, 'https')
    #     new_url = new_url.replace(netloc, settings.AWS_S3_CUSTOM_DOMAIN)
    #     if environment == "development":
    #
    #     else:
    #         return thumbnail
    #     thumbnail.s_url = new_url
    #     return thumbnail

    # async def get_thumbnail(self, file_, geometry_string, **options):
    #     """
    #     Returns thumbnail as an ImageFile instance for file with geometry and
    #     options given. First it will try to get it from the key value store,
    #     secondly it will create it.
    #     """
    #
    #     if file_:
    #         source = ImageFile(file_)
    #     else:
    #         return None
    #
    #     # preserve image filetype
    #     options.setdefault('format', self._get_format(source))
    #
    #     for key, value in self.default_options.items():
    #         options.setdefault(key, value)
    #
    #     name = self._get_thumbnail_filename(source, geometry_string, options)
    #     thumbnail = ImageFile(name, storage)
    #     cached = await kvstore.get(thumbnail)
    #
    #     if cached:
    #         # cached = self._get_correct_url(cached)
    #         return cached
    #
    #     # We have to check exists() because the Storage backend does not
    #     # overwrite in some implementations.
    #     thumbnail_exists = await thumbnail.exists()
    #     if not thumbnail_exists:
    #         try:
    #             source_image = await engine.get_image(source)
    #         except IOError:
    #             return thumbnail
    #
    #         # We might as well set the size since we have the image in memory
    #         image_info = engine.get_image_info(source_image)
    #         options['image_info'] = image_info
    #         size = engine.get_image_size(source_image)
    #         await source.set_size(size)
    #
    #         try:
    #             await self._create_thumbnail(source_image, geometry_string, options, thumbnail)
    #             # self._create_alternative_resolutions(source_image, geometry_string,
    #             #                                      options, thumbnail.name)
    #         except:
    #             raise
    #         finally:
    #             engine.cleanup(source_image)
    #
    #     # If the thumbnail exists we don't create it, the other option is
    #     # to delete and write but this could lead to race conditions so I
    #     # will just leave that out for now.
    #     asyncio.ensure_future(kvstore.get_or_set(source))
    #     asyncio.ensure_future(kvstore.set(thumbnail, source))
    #     # thumbnail = await self._get_correct_url(thumbnail)
    #
    #     return thumbnail


    @property
    def session(self):
        if self._session is None:
            self._session = aiobotocore.get_session()

        return self._session

    async def upload_to_s3(self, file):
        log = logging.getLogger('threads')
        log.debug('starting upload_to_s3')
        try:
            async with self.session.create_client('s3', region_name=settings.AWS_S3_REGION,
                                                  aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                                  aws_access_key_id=settings.AWS_ACCESS_KEY_ID) as client:
                resp = await client.put_object(Bucket=settings.AWS_S3_BUCKET_NAME, Key=file.name, Body=file.body)
                log.debug("{0} {1}".format(file.name, resp))

            await self.set_thumbnail_exists_on_s3(file.name)
        except Exception as e:
            log.debug(e)
            raise e


    async def upload_photo_multiple(self, file_list):
        loop = asyncio.get_event_loop()

        logger.debug('Running uploading in processes...')

        make_thumbnail_tasks = []
        thumbnail_generator = ThumbnailGenerator()

        with ThreadPoolExecutor(max_workers=2) as executor:
            for f, d in file_list:
                make_thumbnail_tasks.append(loop.run_in_executor(executor, thumbnail_generator.make_thumbnail, f, d))

        results = await asyncio.gather(*make_thumbnail_tasks)

        [asyncio.ensure_future(self.upload_to_s3(t)) for t in results]


    thumbnail_prefix = "thumbnail:{0}"
    async def thumbnail_exists_on_s3(self, file_name):
        redis = await get_connection('redis')

        thumbnail_key = self.thumbnail_prefix.format(file_name)
        async with redis as conn:
            result = await conn.getbit(thumbnail_key, 0)

        return result

    async def set_thumbnail_exists_on_s3(self, file_name):
        redis = await get_connection('redis')

        thumbnail_key = self.thumbnail_prefix.format(file_name)
        async with redis as conn:
            await conn.setbit(thumbnail_key, 0, 1)

