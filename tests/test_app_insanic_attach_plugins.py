import pytest

from insanic import Insanic


class TestInsanic:
    routes = []

    @pytest.fixture()
    def insanic_application(self):
        return Insanic("test")

    def test_infuse_on_hard_failure(self, insanic_application, monkeypatch):
        monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', True)
        monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'hard')

        with pytest.raises(ModuleNotFoundError):
            insanic_application.attach_plugins()

    def test_infuse_on_soft_failure(self, insanic_application, monkeypatch, caplog):
        monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', True)
        monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'soft')

        insanic_application.attach_plugins()

        assert caplog.records[-1].message.endswith("[INFUSE] proceeding without infuse. "
                                                   "No module named 'infuse'")

    def test_infuse_off_hard_failure(self, insanic_application, monkeypatch, caplog):
        monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', False)
        monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'hard')

        insanic_application.attach_plugins()

        assert caplog.records[-1].message.endswith("[INFUSE] proceeding without infuse. "
                                                   "Because `INFUSE_ENABLED` set to `False`")

    def test_infuse_off_soft_failure(self, insanic_application, monkeypatch, caplog):
        monkeypatch.setattr(insanic_application.config, 'INFUSE_ENABLED', False)
        monkeypatch.setattr(insanic_application.config, 'INFUSE_FAIL_TYPE', 'soft')

        insanic_application.attach_plugins()

        assert caplog.records[-1].message.endswith("[INFUSE] proceeding without infuse. "
                                                   "Because `INFUSE_ENABLED` set to `False`")
