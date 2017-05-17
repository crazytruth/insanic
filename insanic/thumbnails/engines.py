import math
from io import BytesIO as BufferIO

from PIL import Image, ImageFile, ImageDraw, ImageFilter

from insanic.conf import settings
from insanic.thumbnails.helpers import toint
from insanic.thumbnails.parsers import parse_crop

def round_corner(radius, fill):
    """Draw a round corner"""
    corner = Image.new('L', (radius, radius), 0)  # (0, 0, 0, 0))
    draw = ImageDraw.Draw(corner)
    draw.pieslice((0, 0, radius * 2, radius * 2), 180, 270, fill=fill)
    return corner


def round_rectangle(size, radius, fill):
    """Draw a rounded rectangle"""
    width, height = size
    rectangle = Image.new('L', size, 255)  # fill
    corner = round_corner(radius, 255)  # fill
    rectangle.paste(corner, (0, 0))
    rectangle.paste(corner.rotate(90),
                    (0, height - radius))  # Rotate the corner and paste it
    rectangle.paste(corner.rotate(180), (width - radius, height - radius))
    rectangle.paste(corner.rotate(270), (width - radius, 0))
    return rectangle


class GaussianBlur(ImageFilter.Filter):
    name = "GaussianBlur"

    def __init__(self, radius=2):
        self.radius = radius

    def filter(self, image):
        return image.gaussian_blur(self.radius)


class Engine:
    def create(self, image, geometry, options):
        """
        Processing conductor, returns the thumbnail as an image engine instance
        """

        image = self.colorspace(image, geometry, options)
        image = self.scale(image, geometry, options)
        image = self.crop(image, geometry, options)
        image = self.blur(image, geometry, options)
        image = self.padding(image, geometry, options)
        return image

    def colorspace(self, image, geometry, options):
        """
        Wrapper for ``_colorspace``
        """
        colorspace = options['colorspace']
        return self._colorspace(image, colorspace)

    def _calculate_scaling_factor(self, x_image, y_image, geometry, options):
        crop = options['crop']
        factors = (geometry[0] / x_image, geometry[1] / y_image)
        return max(factors) if crop else min(factors)

    def scale(self, image, geometry, options):
        """
        Wrapper for ``_scale``
        """
        upscale = options['upscale']
        x_image, y_image = map(float, self.get_image_size(image))
        factor = self._calculate_scaling_factor(x_image, y_image, geometry, options)

        if factor < 1 or upscale:
            width = toint(x_image * factor)
            height = toint(y_image * factor)
            image = self._scale(image, width, height)

        return image

    def crop(self, image, geometry, options):
        """
        Wrapper for ``_crop``
        """
        crop = options['crop']
        x_image, y_image = self.get_image_size(image)

        if not crop or crop == 'noop':
            return image
        elif crop == 'smart':
            # Smart cropping is suitably different from regular cropping
            # to warrent it's own function
            return self._entropy_crop(image, geometry[0], geometry[1], x_image, y_image)

        # Handle any other crop option with the backend crop function.
        geometry = (min(x_image, geometry[0]), min(y_image, geometry[1]))
        x_offset, y_offset = parse_crop(crop, (x_image, y_image), geometry)
        return self._crop(image, geometry[0], geometry[1], x_offset, y_offset)


    def blur(self, image, geometry, options):
        """
        Wrapper for ``_blur``
        """
        if options.get('blur'):
            return self._blur(image, int(options.get('blur')))
        return image

    def padding(self, image, geometry, options):
        """
        Wrapper for ``_padding``
        """
        if options.get('padding') and self.get_image_size(image) != geometry:
            return self._padding(image, geometry, options)
        return image

    async def write(self, image, options, thumbnail):
        """
        Wrapper for ``_write``
        """
        format_ = options['format']
        quality = options['quality']
        image_info = options.get('image_info', {})
        # additional non-default-value options:
        progressive = options.get('progressive', settings.get('THUMBNAIL_PROGRESSIVE', True))
        raw_data = self._get_raw_data(
            image, format_, quality,
            image_info=image_info,
            progressive=progressive
        )
        await thumbnail.write(raw_data)

    def write_sync(self, image, options):
        format_ = options['format']
        quality = options['quality']
        image_info = options.get('image_info', {})
        # additional non-default-value options:
        progressive = options.get('progressive', settings.get('THUMBNAIL_PROGRESSIVE', True))
        raw_data = self._get_raw_data(
            image, format_, quality,
            image_info=image_info,
            progressive=progressive
        )
        # await thumbnail.write(raw_data)
        return raw_data

    def cleanup(self, image):
        """Some backends need to manually cleanup after thumbnails are created"""
        pass

    def get_image_ratio(self, image, options):
        """
        Calculates the image ratio. If cropbox option is used, the ratio
        may have changed.
        """
        cropbox = options['cropbox']

        if cropbox:
            x, y, x2, y2 = parse_cropbox(cropbox)
            x = x2 - x
            y = y2 - y
        else:
            x, y = self.get_image_size(image)

        return float(x) / y


    async def get_image(self, source):
        source_body = await source.read()
        buffer = BufferIO(source_body)
        return Image.open(buffer)

    def get_image_size(self, image):
        return image.size

    def get_image_info(self, image):
        return image.info or {}

    def is_valid_image(self, raw_data):
        buffer = BufferIO(raw_data)
        try:
            trial_image = Image.open(buffer)
            trial_image.verify()
        except Exception:
            return False
        return True

    def _cropbox(self, image, x, y, x2, y2):
        return image.crop((x, y, x2, y2))

    def _orientation(self, image):
        try:
            exif = image._getexif()
        except (AttributeError, IOError, KeyError, IndexError):
            exif = None

        if exif:
            orientation = exif.get(0x0112)

            if orientation == 2:
                image = image.transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 3:
                image = image.rotate(180)
            elif orientation == 4:
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            elif orientation == 5:
                image = image.rotate(-90).transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 6:
                image = image.rotate(-90)
            elif orientation == 7:
                image = image.rotate(90).transpose(Image.FLIP_LEFT_RIGHT)
            elif orientation == 8:
                image = image.rotate(90)

        return image

    def _colorspace(self, image, colorspace):
        if colorspace == 'RGB':
            if image.mode == 'RGBA':
                return image  # RGBA is just RGB + Alpha
            if image.mode == 'LA' or (image.mode == 'P' and 'transparency' in image.info):
                return image.convert('RGBA')
            return image.convert('RGB')
        if colorspace == 'GRAY':
            return image.convert('L')
        return image

    # Credit to chrisopherhan https://github.com/christopherhan/pycrop
    # This is just a slight rework of pycrops implimentation
    def _entropy_crop(self, image, geometry_width, geometry_height, image_width, image_height):
        geometry_ratio = geometry_width / geometry_height

        # The is proportionally wider than it should be
        while image_width / image_height > geometry_ratio:

            slice_width = max(image_width - geometry_width, 10)

            right = image.crop((image_width - slice_width, 0, image_width, image_height))
            left = image.crop((0, 0, slice_width, image_height))

            if self._get_image_entropy(left) < self._get_image_entropy(right):
                image = image.crop((slice_width, 0, image_width, image_height))
            else:
                image = image.crop((0, 0, image_height - slice_width, image_height))

            image_width -= slice_width

        # The image is proportionally taller than it should be
        while image_width / image_height < geometry_ratio:

            slice_height = min(image_height - geometry_height, 10)

            bottom = image.crop((0, image_height - slice_height, image_width, image_height))
            top = image.crop((0, 0, image_width, slice_height))

            if self._get_image_entropy(bottom) < self._get_image_entropy(top):
                image = image.crop((0, 0, image_width, image_height - slice_height))
            else:
                image = image.crop((0, slice_height, image_width, image_height))

            image_height -= slice_height

        return image

    def _scale(self, image, width, height):
        return image.resize((width, height), resample=Image.ANTIALIAS)

    def _crop(self, image, width, height, x_offset, y_offset):
        return image.crop((x_offset, y_offset,
                           width + x_offset, height + y_offset))

    def _rounded(self, image, r):
        i = round_rectangle(image.size, r, "notusedblack")
        image.putalpha(i)
        return image

    def _blur(self, image, radius):
        return image.filter(GaussianBlur(radius))

    def _padding(self, image, geometry, options):
        x_image, y_image = self.get_image_size(image)
        left = int((geometry[0] - x_image) / 2)
        top = int((geometry[1] - y_image) / 2)
        color = options.get('padding_color')
        im = Image.new(image.mode, geometry, color)
        im.paste(image, (left, top))
        return im

    def _get_raw_data(self, image, format_, quality, image_info=None, progressive=False):
        # Increase (but never decrease) PIL buffer size
        ImageFile.MAXBLOCK = max(ImageFile.MAXBLOCK, image.size[0] * image.size[1])
        bf = BufferIO()

        params = {
            'format': format_,
            'quality': quality,
            'optimize': 1,
        }

        # keeps icc_profile
        if 'icc_profile' in image_info:
            params['icc_profile'] = image_info['icc_profile']

        raw_data = None

        if format_ == 'JPEG' and progressive:
            params['progressive'] = True
        try:
            # Do not save unnecessary exif data for smaller thumbnail size
            params.pop('exif', {})
            image.save(bf, **params)
        except (IOError, OSError):
            # Try without optimization.
            params.pop('optimize')
            image.save(bf, **params)
        else:
            raw_data = bf.getvalue()
        finally:
            bf.close()

        return raw_data

    def _get_image_entropy(self, image):
        """calculate the entropy of an image"""
        hist = image.histogram()
        hist_size = sum(hist)
        hist = [float(h) / hist_size for h in hist]
        return -sum([p * math.log(p, 2) for p in hist if p != 0])

engine = Engine()