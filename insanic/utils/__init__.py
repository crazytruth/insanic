import re
import ujson as json

from importlib import import_module
from enum import Enum

def force_str(val):
    if isinstance(val, bytes):
        val = val.decode()
    else:
        val = str(val)
    return val


def try_json_decode(data):
    try:
        data = json.loads(data)
    except (ValueError, TypeError):
        pass
    return data


def _unpack_enum_error_message(error_code):
    if isinstance(error_code, Enum):
        prefix = error_code.__module__.split('.', 1)[0]
        error_code_dict = {"name": f"{prefix}_{error_code.name}", "value": error_code.value}
        return error_code_dict
    return error_code


first_cap_re = re.compile('(.)([A-Z][a-z]+)')
number_re = re.compile('(.)([0-9]+)')
all_cap_re = re.compile('([a-z0-9])([A-Z])')


def camel_to_snake(name):
    s1 = first_cap_re.sub(r'\1_\2', name)
    s1 = number_re.sub(r'\1_\2', s1)
    return all_cap_re.sub(r'\1_\2', s1).lower()


def load_class(kls):
    parts = kls.rsplit('.', 1)
    m = import_module(parts[0])
    return getattr(m, parts[-1])
