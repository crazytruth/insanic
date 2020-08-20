import pytest
import os
import types

from insanic.conf import InsanicConfig, LazySettings, ENVIRONMENT_VARIABLE
from insanic.conf.config import INSANIC_PREFIX


class TestLazySettings:
    @pytest.fixture
    def insanic_settings(self):
        # resets settings because settings is evaluated in conftest for other tests
        return LazySettings()

    def test_repr_not_evaluated(self, insanic_settings):
        assert "Unevaluated" in repr(insanic_settings)

    def test_repr_user_evaluated(self, insanic_settings):
        insanic_settings.configure(SERVICE_NAME="test")
        assert "UserSettingsHolder" in repr(insanic_settings)

    def test_simple_get_attr(self, insanic_settings):
        insanic_settings.configure(SERVICE_NAME="test")
        assert insanic_settings.SERVICE_NAME == "test"

    def test_set_attr(self, insanic_settings):
        insanic_settings.configure(SERVICE_NAME="test")
        insanic_settings.SERVICE_ALIAS = "gotta_go"
        assert insanic_settings.SERVICE_ALIAS == "gotta_go"

    def test_del_attr(self, insanic_settings, monkeypatch):
        insanic_settings.configure(SERVICE_NAME="test")
        insanic_settings.SOME_RANDOM_SETTING = "a"

        assert insanic_settings.SOME_RANDOM_SETTING == "a"

        delattr(insanic_settings, "SOME_RANDOM_SETTING")

        with pytest.raises(AttributeError):
            insanic_settings.SOME_RANDOM_SETTING

    def test_configured(self, insanic_settings, monkeypatch):
        assert insanic_settings.configured is False

        insanic_settings.configure(SERVICE_NAME="test")
        monkeypatch.setenv(ENVIRONMENT_VARIABLE, "tests.intest.config")
        insanic_settings.SERVICE_ALIAS = "intest"

        assert insanic_settings.configured is True

        # test when trying to configure again
        with pytest.raises(RuntimeError):
            insanic_settings.configure()

    def test_config_was_loaded(self, insanic_settings, monkeypatch):
        monkeypatch.setenv(ENVIRONMENT_VARIABLE, "tests.intest.config")

        insanic_settings._setup()

        assert isinstance(insanic_settings._wrapped, InsanicConfig)


class TestInsanicSettings:
    @pytest.fixture(autouse=True)
    def base_config(self):
        self.base_config = InsanicConfig(settings_module="tests.intest.config")

    @pytest.fixture
    def mock_settings_file(self, tmpdir):
        success_load = "upper_mock_settings"
        tmpfile = tmpdir.join("mock_settings.py")

        tmpfile.write(
            f"MOCK_SETTINGS = '{success_load}'\nmock_settings = 'lower_mock_settings'"
        )
        return tmpfile

    @pytest.fixture
    def intest_config(self):
        filename = os.path.join(os.path.dirname(__file__), "intest/config.py")
        module = types.ModuleType("config")
        module.__file__ = filename
        with open(filename) as config_file:
            exec(
                compile(config_file.read(), filename, "exec"), module.__dict__
            )

        return module

    def test_init(self):

        # assert everything in global settings is set
        from insanic.conf import global_settings

        for k in dir(global_settings):
            if k.isupper():
                assert hasattr(self.base_config, k)

    def test_service_name(self):

        self.base_config.SERVICE_NAME = "test_insanic"
        assert self.base_config.SERVICE_NAME == "test_insanic"

    def test_load_from_object(self):
        class MockObject:
            MOCK_SETTINGS = "upper_mock_settings"
            mock_settings = "lower_mock_settings"

        mock_object = MockObject()

        self.base_config.from_object(mock_object)

        assert self.base_config.MOCK_SETTINGS == mock_object.MOCK_SETTINGS
        with pytest.raises(AttributeError):
            self.base_config.mock_settings

    def test_load_from_pyfile(self, mock_settings_file):
        assert self.base_config.from_pyfile(mock_settings_file.strpath) is True
        assert self.base_config.MOCK_SETTINGS == "upper_mock_settings"
        with pytest.raises(AttributeError):
            self.base_config.mock_settings

    def test_load_from_pyfile_fail(self):
        with pytest.raises(IOError):
            self.base_config.from_pyfile("a")

    def test_load_from_envvar(self, monkeypatch, mock_settings_file):

        with pytest.raises(RuntimeError):
            self.base_config.from_envvar("THIS_SHOULDNT_EXIST")

        settings_env = "INSANIC_SETTINGS_MODULE"
        monkeypatch.setenv(settings_env, mock_settings_file.strpath)

        assert self.base_config.from_envvar(settings_env) is True
        assert self.base_config.MOCK_SETTINGS == "upper_mock_settings"
        with pytest.raises(AttributeError):
            self.base_config.mock_settings

    def test_load_environment_vars(self, monkeypatch):

        env_name = "MOCK_SETTINGS"
        set_value = "a"
        not_set_value = "b"
        other_prefix = "CINASNI_"
        other_prefix_value = 1

        monkeypatch.setenv(f"INSANIC_{env_name}", set_value)
        monkeypatch.setenv(f"INSANIC_FLOAT_VALUE", 1.3)
        monkeypatch.setenv(f"{env_name}", not_set_value)
        monkeypatch.setenv(f"{other_prefix}{env_name}", other_prefix_value)

        self.base_config.load_environment_vars(prefix=INSANIC_PREFIX)
        assert self.base_config.MOCK_SETTINGS == set_value

        assert isinstance(self.base_config.FLOAT_VALUE, float)
        assert self.base_config.FLOAT_VALUE == 1.3

        # check if variables can be loaded with different prefix and if is loaded as int
        self.base_config.load_environment_vars(other_prefix)
        assert isinstance(self.base_config.MOCK_SETTINGS, int)
        assert self.base_config.MOCK_SETTINGS == int(other_prefix_value)

    def test_load_from_service(self):

        # self.base_config.load_from_service()

        assert self.base_config.INT_SETTINGS == 1
        assert self.base_config.FLOAT_SETTINGS == 2.3
        assert self.base_config.STRING_SETTINGS == "a"

    def assert_settings_with_module(self, config):

        for s in dir(config):
            if not s.startswith("__"):
                if s.isupper():
                    assert hasattr(self.base_config, s)
                    assert getattr(self.base_config, s) == getattr(config, s)
                elif s.islower():
                    assert not hasattr(self.base_config, s)
                else:
                    raise RuntimeError(
                        "Tests are configured improperly. Something in "
                        "intest.config is messing this up."
                    )

    def test_sanic_default_config(self):
        from sanic.config import DEFAULT_CONFIG

        for k, v in DEFAULT_CONFIG.items():
            assert hasattr(self.base_config, k)


class TestLoadingPriority:
    def test_2_1_arguments_over_sanic_defaults(self):

        config = InsanicConfig(
            defaults={"REAL_IP_HEADER": "should_be_this_value"}
        )
        assert config.REAL_IP_HEADER == "should_be_this_value"
        assert config.REAL_IP_HEADER != "X-Real-IP"

    def test_3_2_sanic_env_prefix_over_sanic_default_config(self, monkeypatch):
        correct_value = "X-Should-Be-This-Value"
        monkeypatch.setenv("SANIC_REAL_IP_HEADER", correct_value)

        config = InsanicConfig(defaults={"REAL_IP_HEADER": "wrong_value"})

        assert config.REAL_IP_HEADER == correct_value

    def test_4_3_insanic_global_settings_over_sanic_env_prefix(
        self, monkeypatch
    ):
        monkeypatch.setenv("SANIC_SERVICE_ALIAS", "wrong_value")

        config = InsanicConfig(
            defaults={"SERVICE_ALIAS": "another_wrong_value"}
        )

        assert (
            config.SERVICE_ALIAS == ""
        )  # value from `insanic.conf.global_settings`

    def test_5_4_service_config_over_insanic_globals(self):
        config = InsanicConfig(
            settings_module="tests.intest.config",
            defaults={"SERVICE_ALIAS": "wrong_value"},
        )

        assert (
            config.SERVICE_ALIAS == "intest"
        )  # value from `test.intest.config`

    def test_6_5_insanic_env_prefix_over_service_config(self, monkeypatch):
        correct_value = "the real service alias"
        monkeypatch.setenv("INSANIC_SERVICE_ALIAS", correct_value)

        config = InsanicConfig(
            settings_module="tests.intest.config",
            defaults={"SERVICE_ALIAS": "wrong_value"},
        )

        assert config.SERVICE_ALIAS == correct_value
