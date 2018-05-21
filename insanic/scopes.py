import os
import urllib.request

from functools import wraps

from insanic.log import logger

AWS_ECS_METADATA_ENDPOINT = "169.254.170.2/v2/metadata"

def public_facing(f):
    @wraps(f)
    def public_f(*args, **kwargs):
        return f(*args, **kwargs)

    setattr(public_f, "scope", "public")
    return public_f

def _is_docker():
    try:
        r = urllib.request.urlopen("http://" + AWS_ECS_METADATA_ENDPOINT, timeout=0.5)
        logger.info(r.read().decode())
        return r.status == 200
    except:
        try:
            with open('/proc/self/cgroup', 'r') as proc_file:
                for line in proc_file:
                    fields = line.strip().split('/')
                    if fields[1] == 'docker':
                        return True
        except FileNotFoundError:
            pass
    return False


is_docker = _is_docker()


def get_machine_id():
    if is_docker:
        machine_id = os.environ.get('HOSTNAME')
    else:
        import socket
        ip = socket.gethostbyname(socket.gethostname())
        machine_id = '{:02X}{:02X}{:02X}{:02X}'.format(*map(int, ip.split('.')))
    return machine_id
