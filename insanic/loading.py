from insanic.services import ServiceRegistry


def get_service(service_name):
    return ServiceRegistry()[service_name]
