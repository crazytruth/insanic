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
