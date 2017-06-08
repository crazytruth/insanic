import random
import peewee

from cryptography.fernet import Fernet as BaseFernet, MultiFernet, InvalidToken

from .exceptions import FieldError
from .functional import cached_property

from .conf import settings


class Fernet(BaseFernet):

    def encrypt(self, data):

        rnd = random.Random()
        rnd.seed(settings.WEB_SECRET_KEY, 1)
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

class AnonymousUser(object):
    id = None
    pk = None
    username = ''
    is_staff = False
    is_active = False
    is_superuser = False

    def __init__(self):
        pass

    def __str__(self):
        return 'AnonymousUser'

    def __eq__(self, other):
        return isinstance(other, self.__class__)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return 1  # instances always return the same hash value

    def save(self):
        raise NotImplementedError("Django doesn't provide a DB representation for AnonymousUser.")

    def delete(self):
        raise NotImplementedError("Django doesn't provide a DB representation for AnonymousUser.")

    def set_password(self, raw_password):
        raise NotImplementedError("Django doesn't provide a DB representation for AnonymousUser.")

    def check_password(self, raw_password):
        raise NotImplementedError("Django doesn't provide a DB representation for AnonymousUser.")

    def _get_groups(self):
        return self._groups
    groups = property(_get_groups)

    def _get_user_permissions(self):
        return self._user_permissions
    user_permissions = property(_get_user_permissions)

    def get_group_permissions(self, obj=None):
        return set()

    def has_perm(self, perm, obj=None):
        return False

    def has_perms(self, perm_list, obj=None):
        for perm in perm_list:
            if not self.has_perm(perm, obj):
                return False
        return True

    def has_module_perms(self, module):
        return False

    def is_anonymous(self):
        return True

    @property
    def is_authenticated(self):
        return False
