import pytest
import os
import types

from hvac.exceptions import Forbidden

from insanic.conf import ENVIRONMENT_VARIABLE, VaultConfig, BaseConfig, LazySettings
from insanic.exceptions import ImproperlyConfigured
from insanic.functional import empty


class TestLazySettings:

    @pytest.fixture
    def insanic_settings(self):
        # resets settings because settings is evaluated in conftest for other tests
        return LazySettings()

    @pytest.fixture
    def mock_vault(self, monkeypatch):
        def mock_init(self, *args, **kwargs):
            setattr(self, "SERVICE_NAME", "test_insanic")

        monkeypatch.setattr(VaultConfig, "__init__", mock_init)
        return VaultConfig

    def test_repr_not_evaluated(self, insanic_settings):
        assert "Unevaluated" in repr(insanic_settings)

    def test_repr_user_evaluated(self, insanic_settings):
        insanic_settings.configure(SERVICE_NAME="test")
        assert "UserSettingsHolder" in repr(insanic_settings)

    def test_repr_vault_evaluated(self, insanic_settings, mock_vault, monkeypatch):
        test_service_name = "test_insanic"

        monkeypatch.setenv(ENVIRONMENT_VARIABLE, "some_role_id")

        assert test_service_name == insanic_settings.SERVICE_NAME
        assert "VaultConfig" in repr(insanic_settings)

    def test_settings_without_vault_role_id(self, monkeypatch, insanic_settings):

        with pytest.raises(ImproperlyConfigured):
            insanic_settings._setup()

    def test_simple_get_attr(self, insanic_settings, mock_vault, monkeypatch):
        monkeypatch.setenv(ENVIRONMENT_VARIABLE, "some_role_id")
        assert insanic_settings.SERVICE_NAME == "test_insanic"

    def test_set_attr(self, insanic_settings, mock_vault, monkeypatch):
        monkeypatch.setenv(ENVIRONMENT_VARIABLE, "some_role_id")
        insanic_settings.SERVICE_NAME = "gotta_go"

        assert insanic_settings.SERVICE_NAME == "gotta_go"

        insanic_settings._wrapped = empty
        assert insanic_settings.SERVICE_NAME is "test_insanic"

    def test_del_attr(self, insanic_settings, mock_vault, monkeypatch):
        monkeypatch.setenv(ENVIRONMENT_VARIABLE, "some_role_id")
        insanic_settings.SOME_RANDOM_SETTING = "a"

        assert insanic_settings.SOME_RANDOM_SETTING == "a"

        delattr(insanic_settings, "SOME_RANDOM_SETTING")

        with pytest.raises(AttributeError):
            insanic_settings.SOME_RANDOM_SETTING

    def test_configured(self, insanic_settings, mock_vault, monkeypatch):
        assert insanic_settings.configured is False

        monkeypatch.setenv(ENVIRONMENT_VARIABLE, "some_role_id")
        insanic_settings.SERVICE_NAME = "tests.intest"

        assert insanic_settings.configured is True

        # test when trying to configure again
        with pytest.raises(RuntimeError):
            insanic_settings.configure()


class TestBaseSettings:

    @pytest.fixture(autouse=True)
    def base_config(self):
        self.base_config = BaseConfig(settings_module="tests.intest")

    @pytest.fixture
    def mock_settings_file(self, tmpdir):
        success_load = "upper_mock_settings"
        tmpfile = tmpdir.join("mock_settings.py")

        tmpfile.write(f"MOCK_SETTINGS = '{success_load}'\nmock_settings = 'lower_mock_settings'")
        return tmpfile

    @pytest.fixture
    def intest_config(self):
        filename = os.path.join(os.path.dirname(__file__), "intest/config.py")
        module = types.ModuleType('config')
        module.__file__ = filename
        with open(filename) as config_file:
            exec(compile(config_file.read(), filename, 'exec'), module.__dict__)

        return module

    def test_init(self):
        assert self.base_config._service_name is empty

        # assert everything in global settings is set
        from insanic.conf import global_settings
        for k in dir(global_settings):
            if k.isupper():
                assert hasattr(self.base_config, k)

    def test_service_name(self):
        assert self.base_config._service_name is empty

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
        assert self.base_config.MOCK_SETTINGS == 'upper_mock_settings'
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
        assert self.base_config.MOCK_SETTINGS == 'upper_mock_settings'
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

        self.base_config.load_environment_vars()
        assert self.base_config.MOCK_SETTINGS == set_value

        assert isinstance(self.base_config.FLOAT_VALUE, float)
        assert self.base_config.FLOAT_VALUE == 1.3

        # check if variables can be loaded with different prefix and if is loaded as int
        self.base_config.load_environment_vars(other_prefix)
        assert isinstance(self.base_config.MOCK_SETTINGS, int)
        assert self.base_config.MOCK_SETTINGS == int(other_prefix_value)

    def test_load_from_service_error(self):

        with pytest.raises(OSError):
            self.base_config.load_from_service()

    def test_load_from_service_with_param_error(self):
        with pytest.raises(ModuleNotFoundError):
            self.base_config.load_from_service("ladidadida")

    def assert_settings_with_module(self, config):

        for s in dir(config):
            if not s.startswith("__"):
                if s.isupper():
                    assert hasattr(self.base_config, s)
                    assert getattr(self.base_config, s) == getattr(config, s)
                elif s.islower():
                    assert not hasattr(self.base_config, s)
                else:
                    raise RuntimeError("Tests are configured improperly. Something in "
                                       "intest.config is messing this up.")

    def test_load_from_service_with_param(self, intest_config):
        self.base_config.load_from_service('tests.intest.config')
        self.assert_settings_with_module(intest_config)

    def test_load_from_service_with_service_name(self, intest_config):
        self.base_config.SERVICE_NAME = "tests.intest"
        self.base_config.load_from_service()
        self.assert_settings_with_module(intest_config)


from hvac import Client
from consul import Consul


class TestVaultConfig:
    role_id = "some-random-uuid"

    @pytest.fixture(autouse=True)
    def vault_config(self, monkeypatch):
        def mock_load_from_service(self, *arg, **kwargs):
            pass

        def mock_load_from_vault(self, *args, **kwargs):
            pass

        monkeypatch.setattr(VaultConfig, "load_from_service", mock_load_from_service)
        monkeypatch.setattr(VaultConfig, "load_from_vault", mock_load_from_vault)

        self.config = VaultConfig(self.role_id)

    def undo_mock_load_from_vault(self, monkeypatch):
        for i in range(len(monkeypatch._setattr)):
            setattr_record = monkeypatch._setattr[i]
            if setattr_record[0] == VaultConfig and setattr_record[1] == "load_from_vault":
                break

        undo_setattr = monkeypatch._setattr.pop(i)
        setattr(*undo_setattr)

    def test_init(self):

        assert self.config._role_id == self.role_id

        assert isinstance(self.config.vault_client, Client)
        # deprecated: consul client is not longer used
        # assert isinstance(self.config.consul_client, Consul)

    def test_default_properties(self, monkeypatch):
        vault_properties = ("VAULT_SCHEME", "VAULT_HOST",
                            "VAULT_PORT", "VAULT_URL", "VAULT_ROLE_ID")
        swarm_properties = ("SWARM_MANAGER_SCHEME", "SWARM_MANAGER_HOST", "SWARM_MANAGER_PORT", "SWARM_MANAGER_URL")

        for p in vault_properties + swarm_properties:
            assert getattr(self.config, p) is not None

    @pytest.mark.parametrize("role_id,mmt_env,expected", ((None, None, False),
                                                          ("a", None, False),
                                                          (None, "b", False),
                                                          ("a", "b", True)))
    def test_can_vault(self, role_id, mmt_env, expected, monkeypatch):

        assert self.config.can_vault() is False
        with pytest.raises(EnvironmentError):
            self.config.can_vault(True)

        if mmt_env is not None:
            monkeypatch.setenv('MMT_ENV', mmt_env)
        self.config._role_id = role_id

        assert self.config.can_vault() is expected
        if not expected:
            with pytest.raises(EnvironmentError):
                self.config.can_vault(True)
        else:
            assert self.config.can_vault(True) is expected

    @pytest.mark.parametrize("role_id,mmt_env", ((None, None),
                                                 ("a", None),
                                                 (None, "b")))
    def test_load_from_vault_cannot_vault(self, role_id, mmt_env, monkeypatch):
        self.undo_mock_load_from_vault(monkeypatch)
        if mmt_env is not None:
            monkeypatch.setenv('MMT_ENV', mmt_env)
        self.config._role_id = role_id

        with pytest.raises(EnvironmentError):
            self.config.load_from_vault(True)

    @pytest.mark.parametrize("raise_for", ("common", "test_service"))
    def test_load_from_vault_handle_forbidden(self, raise_for, monkeypatch):
        self.undo_mock_load_from_vault(monkeypatch)

        def raise_forbidden(path, **kwargs):
            if path.endswith(raise_for):
                raise Forbidden("Forbidden")

        monkeypatch.setattr(self.config, "_service_name", "test_service")

        monkeypatch.setenv('MMT_ENV', "test")
        monkeypatch.setattr(self.config.vault_client, "read", raise_forbidden)

        with pytest.raises(Forbidden):
            self.config.load_from_vault(True)

    def test_load_from_vault(self, monkeypatch):
        self.undo_mock_load_from_vault(monkeypatch)

        env = "test"
        service_name = "testservice"

        def mock_data(path, **kwargs):
            if path == self.config.vault_common_path.format(env=env):
                return {'data': {"COMMON_SETTING": "common setting"}}
            elif path == self.config.vault_service_secret_path.format(env=env, service_name=service_name):
                return {'data': {"SERVICE_SECRET_SETTING": "service secret setting"}}
            elif path == self.config.vault_service_config_path.format(service_name=service_name):
                return {'data': {"SERVICE_CONFIG_SETTING": "service config setting"}}
            else:
                raise Forbidden(f"Forbidden: {path}")

        monkeypatch.setattr(self.config, "_service_name", service_name)
        monkeypatch.setenv('MMT_ENV', env)
        monkeypatch.setattr(self.config.vault_client, "read", mock_data)

        self.config.load_from_vault()

        assert hasattr(self.config, "COMMON_SETTING") is True
        assert hasattr(self.config, "SERVICE_SECRET_SETTING") is True
        assert hasattr(self.config, "SERVICE_CONFIG_SETTING") is True
        assert self.config.COMMON_SETTING == "common setting"
        assert self.config.SERVICE_SECRET_SETTING == "service secret setting"
        assert self.config.SERVICE_CONFIG_SETTING == "service config setting"

    def test_service_name(self, monkeypatch):
        import uuid
        env = "test"
        service_name = "testservice"
        some_role_id = uuid.uuid4()

        def mock_auth_approle(role_id, **kwargs):
            if role_id == some_role_id:
                return {"auth": {"metadata": {"role_name": "mmt-{}-{}".format(env, service_name)}}}

        monkeypatch.setattr(self.config, "_service_name", empty)
        monkeypatch.setattr(self.config, "_role_id", some_role_id)
        monkeypatch.setenv('MMT_ENV', env)
        monkeypatch.setattr(self.config.vault_client, "auth_approle", mock_auth_approle)

        assert self.config.SERVICE_NAME == service_name

    @pytest.mark.skip(reason="settings.SERVICE_LIST is now deprecated.")
    def test_service_list(self, monkeypatch):

        service_list = self.config.SERVICE_LIST

        assert isinstance(service_list, dict)

        for service_name, service_config in service_list.items():
            assert sorted(['host', 'external_service_port', 'internal_service_port']) == sorted(service_config.keys())
