from importlib import import_module


def get_callback_function(callback):
    callback = callback.split('.')
    f_n = callback.pop()
    mo = import_module(".".join(callback))
    return getattr(mo, f_n)
