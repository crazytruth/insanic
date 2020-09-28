import pytest

from insanic.exceptions import ImproperlyConfigured
from insanic.listeners import before_server_start_verify_plugins


class TestInsanicPlugins:
    routes = []

    def test_plugin_initialized(self, insanic_application):
        instance = object()
        insanic_application.plugin_initialized("help", instance)

        assert len(insanic_application.initialized_plugins) == 1
        assert insanic_application.initialized_plugins["help"] is instance

    def test_plugin_requirements(self, insanic_application, loop, monkeypatch):
        monkeypatch.setattr(
            insanic_application.config, "REQUIRED_PLUGINS", ["inplugin"]
        )
        instance = object()
        insanic_application.plugin_initialized("inplugin", instance)
        before_server_start_verify_plugins(insanic_application, loop)

    def test_plugin_requirements_failed(
        self, insanic_application, loop, monkeypatch
    ):
        monkeypatch.setattr(
            insanic_application.config, "REQUIRED_PLUGINS", ["insomethingelse"]
        )
        instance = object()
        insanic_application.plugin_initialized("inplugin", instance)

        with pytest.raises(ImproperlyConfigured):
            before_server_start_verify_plugins(insanic_application, loop)

    def test_plugin_listener_attached(
        self, insanic_application, loop, monkeypatch
    ):
        assert (
            before_server_start_verify_plugins
            in insanic_application.listeners["before_server_start"]
        )

    async def test_requirement_on_run(
        self, insanic_application, loop, monkeypatch
    ):
        monkeypatch.setattr(
            insanic_application.config, "REQUIRED_PLUGINS", ["insomethingelse"]
        )

        with pytest.raises(ImproperlyConfigured):
            insanic_application.run()
