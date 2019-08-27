import os
import socket
import ujson as json
import urllib.error
import urllib.parse
import urllib.request

from hvac import Client as VaultClient
from hvac.exceptions import Forbidden, VaultError
from yarl import URL
from sanic.config import Config

from insanic.exceptions import ImproperlyConfigured
from insanic.functional import LazyObject, empty, cached_property, cached_property_with_ttl
from insanic.log import logger
from insanic.scopes import is_docker
from . import global_settings
from .base import BaseConfig

ENVIRONMENT_VARIABLE = "VAULT_ROLE_ID"


def is_debug():
    return bool(int(os.environ.get('INSANIC_DEBUG', False)))


class LazySettings(LazyObject):
    """
    A lazy proxy for either global Django settings or a custom settings object.
    The user can manually configure settings prior to using them. Otherwise,
    Django uses the settings module pointed to by DJANGO_SETTINGS_MODULE.
    """

    def _setup(self, name=None):
        """
        Load the settings module pointed to by the environment variable. This
        is used the first time we need any settings at all, if the user has not
        previously configured the settings manually.
        """
        try:
            role_id = os.environ.get(ENVIRONMENT_VARIABLE)
            if not role_id:
                desc = ("setting %s" % name) if name else "settings"
                raise ImproperlyConfigured(
                    "Requested %s, but settings are not configured. "
                    "You must either define the environment variable %s "
                    "or call settings.configure() before accessing settings."
                    % (desc, ENVIRONMENT_VARIABLE))

            self._wrapped = VaultConfig(role_id=role_id)
        except ImproperlyConfigured:
            debug_mode = is_debug()
            if debug_mode:
                service_name_candidate = self._infer_app_name()
                logger.info("Since debug mode. Loading settings from file.")
                self._wrapped = BimilConfig(service_name=service_name_candidate)
            else:
                raise


    def __repr__(self):
        # Hardcode the class name as otherwise it yields 'Settings'.
        if self._wrapped is empty:
            return '<LazySettings [Unevaluated]>'
        return '<LazySettings "%(settings_module)s">' % {
            'settings_module': self._wrapped.__class__.__name__,
        }

    def __getattr__(self, name):
        """Return the value of a setting and cache it in self.__dict__."""
        if self._wrapped is empty:
            self._setup(name)
        val = self.__dict__.get(name) or getattr(self._wrapped, name)
        # self.__dict__[name] = val
        return val

    def __setattr__(self, name, value):
        """
        Set the value of setting. Clear all cached values if _wrapped changes
        (@override_settings does this) or clear single values when set.
        """
        if name == '_wrapped':
            self.__dict__.clear()
        else:
            self.__dict__.pop(name, None)
        super().__setattr__(name, value)

    def __delattr__(self, name):
        """Delete a setting and clear it from cache if needed."""

        super().__delattr__(name)
        self.__dict__.pop(name, None)

    def configure(self, default_settings=global_settings, **options):
        """
        Called to manually configure the settings. The 'default_settings'
        parameter sets where to retrieve any unspecified values from (its
        argument must support attribute access (__getattr__)).
        """
        if self._wrapped is not empty:
            raise RuntimeError('Settings already configured.')
        holder = UserSettingsHolder(default_settings)
        for name, value in options.items():
            setattr(holder, name, value)
        self._wrapped = holder

    @property
    def configured(self):
        """
        Returns True if the settings have already been configured.
        """
        return self._wrapped is not empty

    def get(self, item, default=empty):
        try:
            if default is empty:
                return getattr(self, item)
            else:
                return getattr(self, item, default)
        except AttributeError:
            return None

    def _infer_app_name(self):
        t = []
        for root, dirs, files in os.walk('.'):
            t.append((root, dirs, files))

            exclude_dirs = [d for d in dirs if d.startswith('.') or d.startswith('_')]
            for d in exclude_dirs:
                dirs.remove(d)

            if "config.py" in files:
                return root.split(os.sep)[-1]

        raise EnvironmentError("Unable to predict service_name. "
                               "Maybe you are running in a wrong working directory?")


class BimilConfig(BaseConfig):
    logo = """
    ▄▄▄▄    ██▓ ███▄ ▄███▓ ██▓ ██▓    
    ▓█████▄ ▓██▒▓██▒▀█▀ ██▒▓██▒▓██▒    
    ▒██▒ ▄██▒██▒▓██    ▓██░▒██▒▒██░    
    ▒██░█▀  ░██░▒██    ▒██ ░██░▒██░    
    ░▓█  ▀█▓░██░▒██▒   ░██▒░██░░██████▒
    ░▒▓███▀▒░▓  ░ ▒░   ░  ░░▓  ░ ▒░▓  ░
    ▒░▒   ░  ▒ ░░  ░      ░ ▒ ░░ ░ ▒  ░
     ░    ░  ▒ ░░      ░    ▒ ░  ░ ░   
     ░       ░         ░    ░      ░  ░
          ░                            
    """

    def __init__(self, *, service_name=None, **kwargs):
        self._warned_attributes = []

        self._service_name = service_name
        super().__init__(load_env=False)

        self.load_from_file()
        self.load_environment_vars()

        if self.DEBUG:
            logger.warning(self.logo)

    def load_from_file(self):
        bimil_location = os.path.join(os.getcwd(), f'../.bimil/{self._service_name}_config')

        try:
            self.from_pyfile(bimil_location)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {bimil_location}")

    def __getattr__(self, item):
        try:
            return super().__getattribute__(item)
        except AttributeError as e:
            if item not in self._warned_attributes and item.isupper():
                logger.warning(
                    f"[BIMIL] A setting is NOT in the loaded config file. Returning empty string for the time being: {item}")
                self._warned_attributes.append(item)
            return ''

    @property
    def MMT_ENV(self):
        env = os.environ.get('MMT_ENV', None)
        if env is None:
            logger.warning("MMT_ENV is not set in environment variables.  Please set `export MMT_ENV=<environment>`.")
        return env


class VaultConfig(BaseConfig):
    logo = """
      _   _____  __  ____ ______
     | | / / _ |/ / / / //_  __/
     | |/ / __ / /_/ / /__/ /   
     |___/_/ |_\____/____/_/    
    """

    vault_common_path = "msa/{env}/common"
    vault_service_path = "msa/{env}/{service_name}"
    vault_service_secret_path = "msa_secret/{env}/{service_name}"
    vault_service_config_path = "msa_config/{env}/{service_name}"
    vault_client = VaultClient()

    def __init__(self, *, role_id=None, prechecks=True):
        self._role_id = role_id
        self.vault_client.url = self.VAULT_URL
        self._authenticate(prechecks=prechecks)

        super().__init__(load_env=False)
        self.load_from_vault()

        self.load_environment_vars()

        if self.DEBUG:
            logger.warning(self.logo)

    def _authenticate(self, prechecks=True):
        try:
            if prechecks:
                self.can_vault(raise_exception=True)
            login_response = self.vault_client.auth_approle(self.VAULT_ROLE_ID)
        except VaultError as e:
            raise ImproperlyConfigured(*[f"[VAULT] {a}" for a in e.args])
        else:
            self._service_name = login_response['auth']['metadata']['role_name'].split('-')[-1]

    @property
    def MMT_ENV(self):
        env = os.environ.get('MMT_ENV', None)
        if env is None:
            logger.warning("MMT_ENV is not set in environment variables.  Please set `export MMT_ENV=<environment>`.")
        return env

    def can_vault(self, raise_exception=False):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        try:
            socket.gethostbyaddr(self.VAULT_HOST)
            sock.settimeout(1)
            if sock.connect_ex((self.VAULT_HOST, int(self.VAULT_PORT))) != 0:
                msg = f"[VAULT] Could not connect to port on [{self.VAULT_HOST}:{self.VAULT_PORT}]."
                if raise_exception:
                    raise ImproperlyConfigured(msg)
                else:
                    logger.warning(msg)
                    return False
        except socket.gaierror:
            msg = f"[VAULT] Could not resolve host: {self.VAULT_HOST}"
            if raise_exception:
                raise ImproperlyConfigured(msg)
            else:
                logger.warning(msg)
                return False
        except socket.error as e:
            msg = f"[VAULT] Encountered connection error: {self.VAULT_HOST} {e}"
            if raise_exception:
                raise ImproperlyConfigured(msg)
            else:
                logger.warning(msg)
                return False
        except Exception:
            msg = f"[VAULT] Could not to {self.VAULT_HOST}:{self.VAULT_PORT}"
            if raise_exception:
                raise ImproperlyConfigured(msg)
            else:
                logger.exception(msg)
                return False
        finally:
            sock.close()

        can_vault = self.VAULT_ROLE_ID is not None and self.MMT_ENV is not None
        if can_vault:
            return can_vault
        else:
            if raise_exception:
                raise ImproperlyConfigured(
                    f"VAULT_ROLE_ID and MMT_ENV are required for importing configurations from vault.")
            return can_vault

    def load_from_vault(self, raise_exception=False):
        """
        Settings are loading in the following order
        1. Common
        2. By Service

        updated to
        1. Common
        2. config
        3. secrets

        updated to https://github.com/MyMusicTaste/insanic/issues/159
        1. common
        2. secrets
        3. config

        :param raise_exception:
        :return:
        """

        try:
            common_settings = self.vault_client.read(self.vault_common_path.format(env=self.MMT_ENV))

            try:
                service_config_settings = self.vault_client.read(
                    self.vault_service_config_path.format(
                        env=self.MMT_ENV,
                        service_name=self.SERVICE_NAME)
                )
                service_secret_settings = self.vault_client.read(
                    self.vault_service_secret_path.format(
                        env=self.MMT_ENV,
                        service_name=self.SERVICE_NAME)
                )
            except Forbidden:
                service_settings = self.vault_client.read(
                    self.vault_service_path.format(
                        env=self.MMT_ENV,
                        service_name=self.SERVICE_NAME)
                )
                service_settings = service_settings['data']
            else:
                service_settings = service_secret_settings['data']
                for k, v in service_config_settings['data'].items():
                    service_settings.update({k.upper(): v})

        except Forbidden:
            msg = f"Unable to load settings from vault. Please check settings exists for " \
                f"the environment and service. ENV: {self.MMT_ENV} SERVICE: {self.SERVICE_NAME}"
            logger.critical(msg)
            # raise EnvironmentError(msg)
            if raise_exception:
                raise
        else:
            common_settings = common_settings['data']
            # service_secret_settings = service_secret_settings['data']
            # service_config_settings = service_config_settings['data']

            for k, v in common_settings.items():
                setattr(self, k.upper(), v)

            for k, v in service_settings.items():
                setattr(self, k.upper(), v)

    # vault related properties
    @property
    def VAULT_SCHEME(self):
        return os.environ.get("VAULT_SCHEME", "http")

    @property
    def VAULT_HOST(self):
        return os.environ.get("VAULT_HOST", "vault.msa.swarm")

    @property
    def VAULT_PORT(self):
        return os.environ.get("VAULT_PORT", 8200)

    @property
    def VAULT_URL(self):
        url = URL(f"{self.VAULT_SCHEME}://{self.VAULT_HOST}:{self.VAULT_PORT}")
        return str(url)

    @property
    def VAULT_ROLE_ID(self):
        return self._role_id

    # swarm related properties
    @property
    def SWARM_MANAGER_SCHEME(self):
        return "http"

    @cached_property_with_ttl(ttl=5)
    def SWARM_MANAGER_HOST(self):
        # return random.choice(self.SWARM_MANAGER_HOSTS)
        return "manager.msa.swarm"

    @property
    def SWARM_MANAGER_PORT(self):
        return 2375

    @property
    def SWARM_MANAGER_URL(self):
        return URL(f"{self.SWARM_MANAGER_SCHEME}://{self.SWARM_MANAGER_HOST}:{self.SWARM_MANAGER_PORT}")

    # service related properties
    @cached_property
    def SWARM_SERVICE_LIST(self):

        service_template = {
            "host": "",
            "external_service_port": "",
            "internal_service_port": ""
        }

        query_params = {
            "filters": json.dumps({"name": {"mmt-server": True}})
        }

        url = self.SWARM_MANAGER_URL

        url = url.with_path("/services")
        url = url.with_query(**query_params)

        services_endpoint = str(url)

        try:
            with urllib.request.urlopen(services_endpoint) as response:
                swarm_services = response.read()
        except urllib.error.URLError:
            return {}

        swarm_services = json.loads(swarm_services)

        services_config = {}

        for s in swarm_services:
            service_spec = s['Spec']
            service_name = service_spec['Name'].rsplit('_', 1)[-1].rsplit('-', 1)[-1].lower()

            for p in service_spec['EndpointSpec']['Ports']:
                if p['PublishMode'] == 'ingress':
                    external_service_port = p['PublishedPort']
                    internal_service_port = p['TargetPort']
                    break
            else:
                external_service_port = None
                internal_service_port = None

            if "service_name" in services_config:
                pass
            elif external_service_port is None or internal_service_port is None:
                continue
            else:
                services_config[service_name] = service_template.copy()
                services_config[service_name]['external_service_port'] = external_service_port
                services_config[service_name]['internal_service_port'] = internal_service_port

                if is_docker:
                    services_config[service_name]['host'] = s['Spec']['Name'].rsplit('_', 1)[-1]
                else:
                    services_config[service_name]['host'] = self.SWARM_MANAGER_HOST
        return services_config

    def __repr__(self):
        return '<%(cls)s>' % {
            'cls': self.__class__.__name__,
        }


class UserSettingsHolder:  # pragma: no cover
    """Holder for user configured settings."""
    # SETTINGS_MODULE doesn't make much sense in the manually configured
    # (standalone) case.
    SETTINGS_MODULE = None

    def __init__(self, default_settings):
        """
        Requests for configuration variables not in this class are satisfied
        from the module specified in default_settings (if possible).
        """
        self.__dict__['_deleted'] = set()

        final_settings = Config()
        final_settings.from_object(global_settings)
        final_settings.from_object(default_settings)

        self.default_settings = final_settings

    def __getattr__(self, name):
        if name in self._deleted:
            raise AttributeError
        return getattr(self.default_settings, name)

    def __setattr__(self, name, value):
        self._deleted.discard(name)
        super().__setattr__(name, value)

    def __delattr__(self, name):
        self._deleted.add(name)
        if hasattr(self, name):
            super().__delattr__(name)

    def __dir__(self):
        return sorted(
            s for s in list(self.__dict__) + dir(self.default_settings)
            if s not in self._deleted
        )

    def is_overridden(self, setting):
        deleted = (setting in self._deleted)
        set_locally = (setting in self.__dict__)
        set_on_default = getattr(self.default_settings, 'is_overridden', lambda s: False)(setting)
        return deleted or set_locally or set_on_default

    def __repr__(self):
        return '<%(cls)s>' % {
            'cls': self.__class__.__name__,
        }


settings = LazySettings()
