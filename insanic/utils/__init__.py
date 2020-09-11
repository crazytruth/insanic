from enum import Enum


def _unpack_enum_error_message(error_code: Enum) -> dict:
    prefix = error_code.__module__.split(".", 1)[0]
    error_code_dict = {
        "name": f"{prefix}_{error_code.name}",
        "value": error_code.value,
    }
    return error_code_dict
