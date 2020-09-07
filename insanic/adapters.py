import inspect
from collections import OrderedDict
from typing import Callable


def match_signature(func: Callable, **kwargs) -> dict:
    """
    To match different signatures for
    different versions of callables.
    If kwargs is in the signature, just pass through

    :param func: any callable
    :param kwargs: the potential arguments for callable
    :return: dict of arguments
    """
    signature = inspect.signature(func)

    last_param, last_param_type = OrderedDict(signature.parameters).popitem(
        last=True
    )

    if last_param_type.kind == last_param_type.VAR_KEYWORD:
        sig = kwargs
    else:
        sig = {}
        for param, _param_type in signature.parameters.items():
            if param in kwargs:
                sig.update({param: kwargs[param]})

    return sig
