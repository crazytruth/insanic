from insanic.services.registry import registry


def get_service(service_name):
    """
    Helper function to get the service connection object

    :param service_name: name defined in settings
    :return: service object
    """

    return registry[service_name]
