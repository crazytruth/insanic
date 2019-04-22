from sanic.request import File

from insanic.conf import settings
from insanic.utils.obfuscating import get_safe_dict


def tracing_name(name=None):
    """

    :param name: if name is none assume self
    :return:
    """
    if name is None:
        name = settings.SERVICE_NAME
    return f"{settings.MMT_ENV.upper()}:{name}"

def abbreviate_for_xray(payload):
    for k in payload.keys():
        v = payload.get(k)
        if isinstance(v, File):
            v = {"type": v.type, "size": len(v.body)}
        payload[k] = v
    return payload


def get_safe_settings():
    "Returns a dictionary of the settings module, with sensitive settings blurred out."

    return get_safe_dict({k: getattr(settings, k) for k in dir(settings) if k.isupper()})
