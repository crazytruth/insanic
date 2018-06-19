from insanic.conf import settings


def tracing_name(name=None):
    """

    :param name: if name is none assume self
    :return:
    """
    if name is None:
        name = settings.SERVICE_NAME
    return f"{settings.MMT_ENV.upper()}:{name}"
