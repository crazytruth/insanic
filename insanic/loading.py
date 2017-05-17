from insanic.services import registry

def get_service(service_name):
    return registry[service_name]
