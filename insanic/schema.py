import asyncio
import datetime
import imghdr
import os
import warnings

from collections import Mapping
from inspect import isawaitable
from uuid import uuid4

from marshmallow import utils, Schema, MarshalResult, fields
from marshmallow.exceptions import ValidationError
from marshmallow.decorators import (PRE_DUMP, POST_DUMP)
from marshmallow.marshalling import Marshaller
from marshmallow.utils import missing as missing_
from marshmallow.compat import iteritems
from marshmallow_peewee.convert import ModelConverter as MPModelConverter
from sanic.request import File

from insanic.conf import settings
from insanic.thumbnails import generator
from insanic.thumbnails.backends import EXTENSIONS
from insanic.thumbnails.helpers import tokey

class ImageField(fields.FormattedString):
    _CHECK_ATTRIBUTE = True

    def __init__(self, upload_to, dimension=None, *args, **kwargs):
        self.upload_to = upload_to

        if dimension:
            self.dimension = dimension
        src_str = "https://{0}/{{photo}}".format(settings.AWS_S3_CUSTOM_DOMAIN)
        super().__init__(src_str, *args, **kwargs)

    def _deserialize(self, value, attr, obj):

        if isinstance(value, dict):
            return value['original']
        elif isinstance(value, File):

            file_type = imghdr.what(None, value.body)

            if file_type is None:
                raise ValidationError("Not a valid image type.")
            elif file_type.upper() not in EXTENSIONS.keys():
                raise ValidationError("Not a valid image type. Only jpg's or png's are allowed.")

            rename_file = File(type=value.type, body=value.body, name=self._get_filename(value.name))
            # upload file to s3

            tasks = []
            tasks.append((rename_file, None))
            # asyncio.ensure_future(upload_user_photo(rename_file, getattr(self, 'dimension', None)))
            for thumb_type, thumb_dimension in settings.USER_THUMBNAIL_DIMENSION.items():
                thumbnail_file = File(type=value.type, body=value.body, name=self._get_filename(value.name, thumb_dimension))
                tasks.append((thumbnail_file, thumb_dimension))

            # loop = asyncio.get_event_loop()
            # upload = loop.call_later(1, generator.upload_photo_multiple(tasks))

            #
            asyncio.ensure_future(generator.upload_photo_multiple(tasks))

            # asyncio.ensure_future(generator.upload_photo(rename_file, None))
            # for thumb_type, thumb_dimension in settings.USER_THUMBNAIL_DIMENSION.items():
            #     thumbnail_file = File(type=value.type, body=value.body,
            #                           name=self._get_filename(value.name, thumb_dimension))
            #     asyncio.ensure_future(generator.upload_photo(thumbnail_file, thumb_dimension))
            #
            value = rename_file.name

        return value

    def _serialize(self, value, attr, obj):
        value = self._get_filename(value)
        return self.src_str.format(photo=value)

    def _get_filename(self, value, dimension=None):
        filename = os.path.basename(value)

        filename_base, extension = os.path.splitext(filename)
        if dimension is not None:
            dimension = dimension
        elif hasattr(self, 'dimension'):
            dimension = self.dimension


        if dimension:
            filename = "{filename}.{dimension}{extension}".format(filename=filename_base, dimension=dimension, extension=extension)
        else:
            filename = "{filename}{extension}".format(filename=filename_base, extension=extension)

        return os.path.join(self.upload_to, filename)


class ModelConverter(MPModelConverter):

    def convert_BooleanField(self, field, validate=None, **params):
        return fields.Int(**params)

    def convert_DecimalField(self, field, validate=None, **params):
        return fields.Float(**params)


class ThumbnailsField(fields.Field):
# class ThumbnailsField(Schema):
#     original = ImageField(required=False, upload_to=settings.AWS_S3_USER_PHOTO_LOCATION)

    def __init__(self, upload_to, *args, **kwargs):
        self.upload_to = upload_to
        self.structure = {}
        self.structure.update({"original": ImageField(upload_to=upload_to, required=False)})

        for thumbnail_type, dimension in settings.USER_THUMBNAIL_DIMENSION.items():
            self.structure.update({thumbnail_type: ImageField(upload_to, dimension=dimension)})

        super().__init__(*args, **kwargs)

    def _deserialize(self, value, attr, data):

        if isinstance(value, File):
            upload_file = File(type=value.type, body=value.body, name=self._set_image_name(value.name))

            value = self.structure['original']._deserialize(upload_file, 'original', data)

        return value


    def _serialize(self, value, attr, obj):

        if isinstance(value, File):
            value = File(type=value.type, body=value.body, name=self._set_image_name(value.name))
            # format_data = {t: rename_file for t in self.fields.keys()}

        format_data = {k: f._serialize(value, k, obj) for k, f in self.structure.items()}
        return format_data


    def _set_image_name(self, filename):
        ext = filename.split('.')[-1]
        # get filename
        now = str(datetime.datetime.now())
        key = tokey(uuid4().hex, ext, now)
        filename = '{}.{}'.format(key, ext)
        # return the whole path to the file
        return os.path.join(self.upload_to, filename)


class AsyncField(fields.Field):

    async def aserialize(self, attr, obj, accessor=None):

        """Pulls the value for the given key from the object, applies the
        field's formatting and returns the result.

        :param str attr: The attibute or key to get from the object.
        :param str obj: The object to pull the key from.
        :param callable accessor: Function used to pull values from ``obj``.
        :raise ValidationError: In case of formatting problem
        """
        if self._CHECK_ATTRIBUTE:
            value = self.get_value(attr, obj, accessor=accessor)
            if value is missing_:
                if hasattr(self, 'default'):
                    if callable(self.default):
                        return self.default()
                    else:
                        return self.default
        else:
            value = None
        serialize = self._aserialize(value, attr, obj)

        return await serialize


class AsyncListField(AsyncField, fields.List):

    async def _aserialize(self, value, attr, obj):
        if value is None:
            return None
        if utils.is_collection(value):
            return [await self.container._aserialize(each, attr, obj) for each in value]
        return [await self.container._aserialize(value, attr, obj)]


class AsyncMarshaller(Marshaller):
    async def aserialize(self, obj, fields_dict, many=False,
                  accessor=None, dict_class=dict, index_errors=True, index=None):
        """Takes raw data (a dict, list, or other object) and a dict of
        fields to output and serializes the data based on those fields.

        :param obj: The actual object(s) from which the fields are taken from
        :param dict fields_dict: Mapping of field names to :class:`Field` objects.
        :param bool many: Set to `True` if ``data`` should be serialized as
            a collection.
        :param callable accessor: Function to use for getting values from ``obj``.
        :param type dict_class: Dictionary class used to construct the output.
        :param bool index_errors: Whether to store the index of invalid items in
            ``self.errors`` when ``many=True``.
        :param int index: Index of the item being serialized (for storing errors) if
            serializing a collection, otherwise `None`.
        :return: A dictionary of the marshalled data

        .. versionchanged:: 1.0.0
            Renamed from ``marshal``.
        """
        # Reset errors dict if not serializing a collection
        if not self._pending:
            self.reset_errors()
        if many and obj is not None:
            self._pending = True
            ret = [await self.aserialize(d, fields_dict, many=False,
                                    dict_class=dict_class, accessor=accessor,
                                    index=idx, index_errors=index_errors)
                    for idx, d in enumerate(obj)]
            self._pending = False
            if self.errors:
                raise ValidationError(
                    self.errors,
                    field_names=self.error_field_names,
                    fields=self.error_fields,
                    data=ret,
                )
            return ret
        items = []
        for attr_name, field_obj in iteritems(fields_dict):
            if getattr(field_obj, 'load_only', False):
                continue

            key = ''.join([self.prefix or '', field_obj.dump_to or attr_name])

            async def field_serialize(d):
                if hasattr(field_obj, "aserialize"):
                    return await field_obj.aserialize(attr_name, d, accessor=accessor)
                else:
                    return field_obj.serialize(attr_name, d, accessor=accessor)
            #
            getter = field_serialize
            # getter = lambda d: field_obj.serialize(attr_name, d, accessor=accessor)
            value = await self.call_and_store(
                getter_func=getter,
                data=obj,
                field_name=key,
                field_obj=field_obj,
                index=(index if index_errors else None)
            )
            if value is missing_:
                continue
            items.append((key, value))
        ret = dict_class(items)
        if self.errors and not self._pending:
            raise ValidationError(
                self.errors,
                field_names=self.error_field_names,
                fields=self.error_fields,
                data=ret
            )
        return ret

    async def call_and_store(self, getter_func, data, field_name, field_obj, index=None):
        """Call ``getter_func`` with ``data`` as its argument, and store any `ValidationErrors`.

        :param callable getter_func: Function for getting the serialized/deserialized
            value from ``data``.
        :param data: The data passed to ``getter_func``.
        :param str field_name: Field name.
        :param FieldABC field_obj: Field object that performs the
            serialization/deserialization behavior.
        :param int index: Index of the item being validated, if validating a collection,
            otherwise `None`.
        """
        try:
            value = await getter_func(data)
            # value = getter_func(data)
        except ValidationError as err:  # Store validation errors
            self.error_kwargs.update(err.kwargs)
            self.error_fields.append(field_obj)
            self.error_field_names.append(field_name)
            errors = self.get_errors(index=index)
            # Warning: Mutation!
            if isinstance(err.messages, dict):
                errors[field_name] = err.messages
            elif isinstance(errors.get(field_name), dict):
                errors[field_name].setdefault(FIELD, []).extend(err.messages)
            else:
                errors.setdefault(field_name, []).extend(err.messages)
            # When a Nested field fails validation, the marshalled data is stored
            # on the ValidationError's data attribute
            value = err.data or missing_
        return value

    __call__ = aserialize

class AsyncNested(fields.Nested):


    def __init__(self, nested, default=missing_, exclude=tuple(), only=None, **kwargs):
        self.nested = nested
        self.only = only
        self.exclude = exclude
        self.many = kwargs.get('many', False)
        self.__schema = None  # Cached Schema instance
        self.__updated_fields = False
        super().__init__(nested, default=missing_, exclude=tuple(), only=None, **kwargs)

    async def aserialize(self, attr, obj, accessor=None):
        """Pulls the value for the given key from the object, applies the
        field's formatting and returns the result.

        :param str attr: The attibute or key to get from the object.
        :param str obj: The object to pull the key from.
        :param callable accessor: Function used to pull values from ``obj``.
        :raise ValidationError: In case of formatting problem
        """
        if self._CHECK_ATTRIBUTE:
            value = self.get_value(attr, obj, accessor=accessor)
            if value is missing_:
                if hasattr(self, 'default'):
                    if callable(self.default):
                        return self.default()
                    else:
                        return self.default
        else:
            value = None
        return await self._aserialize(value, attr, obj)

    async def _aserialize(self, nested_obj, attr, obj):
        # Load up the schema first. This allows a RegistryError to be raised
        # if an invalid schema name was passed
        schema = self.schema
        if nested_obj is None:
            return None
        if not self.__updated_fields:
            schema._update_fields(obj=nested_obj, many=self.many)
            self.__updated_fields = True
        ret, errors = await schema.adump(nested_obj, many=self.many,
                update_fields=not self.__updated_fields)
        if isinstance(self.only, str):  # self.only is a field name
            if self.many:
                return utils.pluck(ret, key=self.only)
            else:
                return ret[self.only]
        if errors:
            raise ValidationError(errors, data=ret)
        return ret



class AsyncSchema(Schema):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._amarshal = AsyncMarshaller(prefix=self.prefix)

    async def adump(self, obj, many=None, update_fields=True, **kwargs):
        """Serialize an object to native Python data types according to this
        Schema's fields.

        :param obj: The object to serialize.
        :param bool many: Whether to serialize `obj` as a collection. If `None`, the value
            for `self.many` is used.
        :param bool update_fields: Whether to update the schema's field classes. Typically
            set to `True`, but may be `False` when serializing a homogenous collection.
            This parameter is used by `fields.Nested` to avoid multiple updates.
        :return: A tuple of the form (``data``, ``errors``)
        :rtype: `MarshalResult`, a `collections.namedtuple`

        .. versionadded:: 1.0.0
        """
        errors = {}
        many = self.many if many is None else bool(many)
        if not many and utils.is_collection(obj) and not utils.is_keyed_tuple(obj):
            warnings.warn('Implicit collection handling is deprecated. Set '
                            'many=True to serialize a collection.',
                            category=DeprecationWarning)

        if many and utils.is_iterable_but_not_string(obj):
            obj = list(obj)

        if self._has_processors:
            try:
                processed_obj = await self._ainvoke_dump_processors(
                    PRE_DUMP,
                    obj,
                    many,
                    original_data=obj)
            except ValidationError as error:
                errors = error.normalized_messages()
                result = None
        else:
            processed_obj = obj

        if not errors:
            if update_fields:
                obj_type = type(processed_obj)
                if obj_type not in self._types_seen:
                    self._update_fields(processed_obj, many=many)
                    if not isinstance(processed_obj, Mapping):
                        self._types_seen.add(obj_type)

            try:
                preresult = self._amarshal(
                    processed_obj,
                    self.fields,
                    many=many,
                    # TODO: Remove self.__accessor__ in a later release
                    accessor=self.get_attribute or self.__accessor__,
                    dict_class=self.dict_class,
                    index_errors=self.opts.index_errors,
                    **kwargs
                )
                if isawaitable(preresult):
                    preresult = await preresult

            except ValidationError as error:
                errors = self._amarshal.errors
                preresult = error.data

            result = self._postprocess(preresult, many, obj=obj)

        if not errors and self._has_processors:
            try:
                result = await self._ainvoke_dump_processors(
                    POST_DUMP,
                    result,
                    many,
                    original_data=obj)
            except ValidationError as error:
                errors = error.normalized_messages()
        if errors:
            # TODO: Remove self.__error_handler__ in a later release
            if self.__error_handler__ and callable(self.__error_handler__):
                self.__error_handler__(errors, obj)
            exc = ValidationError(
                errors,
                field_names=self._amarshal.error_field_names,
                fields=self._amarshal.error_fields,
                data=obj,
                **self._amarshal.error_kwargs
            )
            self.handle_error(exc, obj)
            if self.strict:
                raise exc

        return MarshalResult(result, errors)


    async def _ainvoke_dump_processors(self, tag_name, data, many, original_data=None):
        # The pass_many post-dump processors may do things like add an envelope, so
        # invoke those after invoking the non-pass_many processors which will expect
        # to get a list of items.
        data = await self._ainvoke_processors(tag_name, pass_many=False,
            data=data, many=many, original_data=original_data)
        data = await self._ainvoke_processors(tag_name, pass_many=True,
            data=data, many=many, original_data=original_data)

        if isawaitable(data):
            return await data
        return data

    async def _ainvoke_load_processors(self, tag_name, data, many, original_data=None):
        # This has to invert the order of the dump processors, so run the pass_many
        # processors first.
        data = await self._ainvoke_processors(tag_name, pass_many=True,
            data=data, many=many, original_data=original_data)
        data = await self._ainvoke_processors(tag_name, pass_many=False,
            data=data, many=many, original_data=original_data)
        return data

    async def _ainvoke_processors(self, tag_name, pass_many, data, many, original_data=None):
        for attr_name in self.__processors__[(tag_name, pass_many)]:
            # This will be a bound method.
            processor = getattr(self, attr_name)

            processor_kwargs = processor.__marshmallow_kwargs__[(tag_name, pass_many)]
            pass_original = processor_kwargs.get('pass_original', False)

            if pass_many:
                if pass_original:
                    data = await utils.if_none(processor(data, many, original_data), data)
                else:
                    data = await utils.if_none(processor(data, many), data)
            elif many:
                if pass_original:
                    data = [asyncio.ensure_future(utils.if_none(processor(item, original_data), item))
                            for item in data]
                    data = await asyncio.gather(*data)
                else:
                    data = [asyncio.ensure_future(utils.if_none(processor(item), item)) for item in data]
                    data = await asyncio.gather(*data)
            else:
                if pass_original:
                    data = await asyncio.ensure_future(utils.if_none(processor(data, original_data), data))
                else:
                    data = await utils.if_none(processor(data), data)

        if isawaitable(data):
            return await data

        return data