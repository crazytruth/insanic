import ujson as json

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
