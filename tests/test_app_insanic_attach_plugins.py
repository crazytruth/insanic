import pytest

from insanic import Insanic
from insanic.exceptions import ImproperlyConfigured
from insanic.listeners import before_server_start_verify_plugins


class TestInsanicPlugins:
    routes = []

    @pytest.fixture()
    def insanic_application(self):
        return Insanic("test")

    # def test_infuse_on_hard_failure(self, insanic_application, monkeypatch):
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', True)
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'hard')
    #
    #     with pytest.raises(ModuleNotFoundError):
    #         insanic_application.attach_plugins()
    #
    # def test_infuse_on_soft_failure(self, insanic_application, monkeypatch, caplog):
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', True)
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'soft')
    #
    #     insanic_application.attach_plugins()
    #
    #     assert caplog.records[-1].message.endswith("[INFUSE] proceeding without infuse. "
    #                                                "No module named 'infuse'")
    #
    # def test_infuse_off_hard_failure(self, insanic_application, monkeypatch, caplog):
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', False)
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'hard')
    #
    #     insanic_application.attach_plugins()
    #
    #     assert caplog.records[-1].message.endswith("[INFUSE] proceeding without infuse. "
    #                                                "Because `INFUSE_ENABLED` set to `False`")
    #
    # def test_infuse_off_soft_failure(self, insanic_application, monkeypatch, caplog):
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', False)
    #     monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'soft')
    #
    #     insanic_application.attach_plugins()
    #
    #     assert caplog.records[-1].message.endswith("[INFUSE] proceeding without infuse. "
    #                                                "Because `INFUSE_ENABLED` set to `False`")

    def test_plugin_initialized(self, insanic_application, monkeypatch):
        instance = object()
        insanic_application.plugin_initialized("help", instance)

        assert len(insanic_application.initialized_plugins) == 1
        assert insanic_application.initialized_plugins['help'] is instance

    def test_plugin_requirements(self, insanic_application, loop, monkeypatch):
        monkeypatch.setattr(insanic_application.config, 'REQUIRED_PLUGINS', ["inplugin"])
        instance = object()
        insanic_application.plugin_initialized("inplugin", instance)
        before_server_start_verify_plugins(insanic_application, loop)

    def test_plugin_requirements_failed(self, insanic_application, loop, monkeypatch):
        monkeypatch.setattr(insanic_application.config, 'REQUIRED_PLUGINS', ["insomethingelse"])
        instance = object()
        insanic_application.plugin_initialized("inplugin", instance)

        with pytest.raises(ImproperlyConfigured):
            before_server_start_verify_plugins(insanic_application, loop)

    def test_plugin_listener_attached(self, insanic_application, loop, monkeypatch):
        assert before_server_start_verify_plugins in insanic_application.listeners['before_server_start']
