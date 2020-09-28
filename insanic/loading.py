from insanic.services import Service
from insanic.services.registry import registry


def get_service(service_name: str) -> Service:
    """
    Helper function to get the service connection object

    :param service_name: Name of the service defined in settings.
    """

    return registry[service_name]
