def _service_name(service):
    methods = service.__mapping__()
    method_name = next(iter(methods), None)
    assert method_name is not None
    _, service_name, _ = method_name.split('/')
    return service_name
