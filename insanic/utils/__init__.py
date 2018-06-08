import aiodns
import asyncio

import socket
import ujson as json

from aiodns import DNSResolver, error
from pycares import errno

from insanic.conf import settings



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


def get_my_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('192.255.255.255', 1))
        ip = s.getsockname()[0]
    except:
        ip = socket.gethostbyname(socket.gethostname())
    finally:
        s.close()
    return ip


def get_my_host_by_addr(ip=None):
    if ip is None:
        ip = get_my_ip()
    fut = asyncio.Future()

    def _callback_gethostbyadd(result, errorno):
        if fut.cancelled():
            return
        if errorno is not None:
            fut.set_exception(error.DNSError(errorno, errno.strerror(errorno)))
        else:
            fut.set_result(result)

    _resolver = aiodns.DNSResolver()
    _resolver._channel.gethostbyaddr(ip, _callback_gethostbyadd)
    return fut
