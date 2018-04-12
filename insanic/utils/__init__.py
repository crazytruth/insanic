import socket
import ujson as json


def force_str(val):
    if isinstance(val, bytes):
        val = val.decode()
    else:
        val = str(val)
    return val


def try_json_decode(data):
    try:
        data = json.loads(data)
    except ValueError:
        pass
    return data


def get_my_ip():
    return socket.gethostbyname(socket.gethostname())
