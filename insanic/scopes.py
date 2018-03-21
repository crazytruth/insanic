from functools import wraps


def public_facing(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return func


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
