import os


class public_facing:
    def __init__(self, f):
        self.func = f
        self.scope = "public"
        self.__name__ = f.__name__
        self.__doc__ = f.__doc__
        self.__module__ = f.__module__

    def __call__(self, *args, **kwargs):
        return self.func(self, *args, **kwargs)


def _is_docker():
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
