import inspect
import os
import urllib.request
import socket

from functools import wraps, lru_cache

from insanic.log import error_logger
from insanic.errors import GlobalErrorCodes
from insanic.exceptions import BadRequest


AWS_ECS_METADATA_ENDPOINT = "169.254.170.2/v2/metadata"


def public_facing(fn=None, *, params=None):
    """
    depending on usage can be used to validate query params
    @public_facing  -> does not validate query params and anything is allowed
    @public_facing() -> same as above
    @public_facing(params=[]) -> does not allow any query_params. hard failure (returns 400)
    @public_facing(params=['rabbit']) -> only allows query param "rabbit"

    :param fn: view to decorate
    :param params: params to validate against
    :return: function
    :raise: BadRequest if query_params doesn't validate
    """

    if fn and inspect.isfunction(fn):
        """
        called with just @public_facing and don't need to worry about `params`
        """

        @wraps(fn)
        def public_f(*args, **kwargs):
            return fn(*args, **kwargs)

        setattr(public_f, "scope", "public")
        return public_f

    else:
        """
        called with args @public_facing()
        """
        from insanic.request import Request

        def wrap(fn):
            @wraps(fn)
            def public_f(*args, **kwargs):
                if params is not None:
                    for o in args:
                        if isinstance(o, Request):
                            for qp in o.query_params:
                                if qp not in params:
                                    error_logger.error(
                                        f"Request with invalid params detected! "
                                        f"{qp} not in {', '.join(params)}."
                                    )

                                    raise BadRequest(
                                        description=f"Invalid query params. Allowed: {', '.join(params)}",
                                        error_code=GlobalErrorCodes.invalid_query_params,
                                    )
                            break
                    else:
                        """
                        if here, this means request object was not found... 
                        """
                        raise RuntimeError(
                            "`request` object was not found. "
                            "Must decorate a view function "
                            "or class view method."
                        )

                return fn(*args, **kwargs)

            setattr(public_f, "scope", "public")
            return public_f

        return wrap


@lru_cache(maxsize=1)
def _is_docker():
    try:
        r = urllib.request.urlopen(
            "http://" + AWS_ECS_METADATA_ENDPOINT, timeout=0.5
        )

        return r.status == 200
    except:
        try:
            with open("/proc/self/cgroup", "r") as proc_file:
                for line in proc_file:
                    fields = line.strip().split("/")
                    if fields[1] == "docker":
                        return True
        except FileNotFoundError:
            pass
    return False


is_docker = _is_docker()


@lru_cache(maxsize=1)
def get_machine_id():
    if is_docker:
        machine_id = os.environ.get("HOSTNAME")
    else:
        ip = get_my_ip()
        machine_id = "{:02X}{:02X}{:02X}{:02X}".format(
            *map(int, ip.split("."))
        )
    return machine_id


@lru_cache(maxsize=1)
def get_my_ip():
    try:
        ip = socket.gethostbyname(get_hostname())
        if ip and ip != "127.0.0.1":
            return ip
        else:
            raise socket.gaierror
    except socket.gaierror:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("192.255.255.255", 1))
            ip = s.getsockname()[0]
        finally:
            s.close()

        return ip


@lru_cache(maxsize=1)
def get_hostname():
    return socket.gethostname()
