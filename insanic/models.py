import random
import peewee

from cryptography.fernet import Fernet as BaseFernet, MultiFernet, InvalidToken

from .exceptions import FieldError
from .functional import cached_property

from .conf import settings
SECRET_KEY = settings.SECRET_KEY

class Fernet(BaseFernet):

    def encrypt(self, data):

        rnd = random.Random()
        rnd.seed(SECRET_KEY, 1)
        # current_time = int(time.time())
        current_time = int(rnd.random() * 10000000000)
        iv = bytes(bytearray(rnd.getrandbits(8) for i in range(16)))

        # iv = os.urandom(16)
        return self._encrypt_from_parts(data, current_time, iv)

# reference: https://github.com/orcasgit/django-fernet-fields/blob/master/fernet_fields/fields.py#L61
class EncryptedField(peewee.Field):
    """A field that encrypts values using Fernet symmetric encryption."""
    db_field = 'BinaryField'

    def __init__(self, *args, **kwargs):
        if kwargs.get('primary_key'):
            raise FieldError(
                "%s does not support primary_key=True."
                % self.__class__.__name__
            )
        if kwargs.get('unique'):
            raise FieldError(
                "%s does not support unique=True."
                % self.__class__.__name__
            )
        if kwargs.get('index'):
            raise FieldError(
                "%s does not support db_index=True."
                % self.__class__.__name__
            )
        super().__init__(*args, **kwargs)

    @cached_property
    def keys(self):
        # keys = getattr(settings, 'FERNET_KEYS', None)
        keys = ['S5okmn9XavZr08NvyvzMLyB2Wil77TOUuQHtlDhTePg=',]
        if keys is None:
            keys = [settings.SECRET_KEY]
        return keys

    @cached_property
    def fernet_keys(self):
        return self.keys

    @cached_property
    def fernet(self):
        if len(self.fernet_keys) == 1:
            return Fernet(self.fernet_keys[0])
        return MultiFernet([Fernet(k) for k in self.fernet_keys])


    def db_value(self, value):
        value = super().db_value(value)

        if value is None or value == '':
            return value

        if isinstance(value, str):
        #     value = str(value)
            value = value.encode('unicode_escape')
        #     value = value.encode('ascii')
        # else:
        #     value = str(value)

        return self.fernet.encrypt(value)

    def get_db_prep_value(self, value, connection, prepared=False):
        return value

    def python_value(self, value):
        if value is None or not isinstance(value, bytes):
            return value

        try:
            value = self.fernet.decrypt(value)
        except InvalidToken:
            pass

        return value


class EncryptedTextField(EncryptedField, peewee.TextField):
    pass


class EncryptedCharField(EncryptedField, peewee.CharField):
    pass

class EncryptedIntegerField(EncryptedField, peewee.IntegerField):
    pass


class EncryptedDateField(EncryptedField, peewee.DateField):
    pass


class EncryptedDateTimeField(EncryptedField, peewee.DateTimeField):
    pass