import pytest

from insanic.conf import settings
from insanic.services import Service
from insanic.services.registry import LazyServiceRegistry


class TestServiceRegistry:
    @pytest.fixture(autouse=True)
    def initialize_service_registry(self, monkeypatch):
        monkeypatch.setattr(settings, "SERVICE_CONNECTIONS", ["test1"])
        self.registry = LazyServiceRegistry()

    def test_set_item(self):
        with pytest.raises(TypeError):
            self.registry["some_service"] = {}

    def test_get_item(self):
        service = self.registry["test1"]

        assert isinstance(service, Service)
        assert service.service_name == "test1"

        with pytest.raises(RuntimeError):
            self.registry["test2"]

    def test_repr(self):
        self.registry.reset()

        assert repr(self.registry).endswith("[Unevaluated]")
        len(self.registry)

        assert repr(self.registry).endswith("ServiceRegistry")

    def test_service_class_replace(self):

        self.registry.reset()

        class MyService(Service):

            help = "me"

        self.registry.service_class = MyService

        Test1Service = self.registry["test1"]

        assert isinstance(Test1Service, MyService)
        assert Test1Service.help == "me"
