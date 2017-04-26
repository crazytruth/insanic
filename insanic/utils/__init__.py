import sys
from insanic import middleware

def import_string(import_name, silent=False):
    """Imports an object based on a string.  This is useful if you want to
    use import paths as endpoints or something similar.  An import path can
    be specified either in dotted notation (``xml.sax.saxutils.escape``)
    or with a colon as object delimiter (``xml.sax.saxutils:escape``).
    If `silent` is True the return value will be `None` if the import fails.
    :param import_name: the dotted name for the object to import.
    :param silent: if set to `True` import errors are ignored and
                   `None` is returned instead.
    :return: imported object
    """
    # force the import name to automatically convert to strings
    # __import__ is not able to handle unicode strings in the fromlist
    # if the module is a package
    import_name = str(import_name).replace(':', '.')
    try:
        try:
            __import__(import_name)
        except ImportError:
            if '.' not in import_name:
                raise
        else:
            return sys.modules[import_name]

        module_name, obj_name = import_name.rsplit('.', 1)
        try:
            module = __import__(module_name, None, None, [obj_name])
        except ImportError:
            # support importing modules not yet set up by the parent module
            # (or package for that matter)
            module = import_string(module_name)

        try:
            return getattr(module, obj_name)
        except AttributeError as e:
            raise ImportError(e)

    except ImportError as e:
        if not silent:
            reraise(
                ImportStringError,
                ImportStringError(import_name, e),
                sys.exc_info()[2])


def attach_middleware(app):
    middlewares = dir(middleware)

    for mw in middlewares:
        if mw.endswith("middleware"):
            if mw.startswith("request"):
                middleware_func = getattr(middleware, mw)
                app.request_middleware.append(middleware_func)
            elif mw.startswith("response"):
                middleware_func = getattr(middleware, mw)
                app.response_middleware.append(middleware_func)
            else:
                raise ImportError("Invalid format for middleware. {0}".format(mw))



def force_str(val):
    if isinstance(val, bytes):
        val = val.decode()
    else:
        val = str(val)
    return val

def to_object(item):
    """
    Convert a dictionary to an object (recursive).
    """

    def convert(item):
        if isinstance(item, dict):
            return type('mmt', (), {k: convert(v) for k, v in item.items()})
        if isinstance(item, list):
            def yield_convert(item):
                for index, value in enumerate(item):
                    yield convert(value)

            return list(yield_convert(item))
        else:
            return item

    return convert(item)


