import consul
import importlib
import logging
import os
import sys
import ujson as json
import urllib.parse
import urllib.request

from hvac import Client as VaultClient
from hvac.exceptions import Forbidden
from yarl import URL
from sanic.config import Config

from insanic.exceptions import ImproperlyConfigured
from insanic.functional import LazyObject, empty, cached_property, cached_property_with_ttl
from insanic.scopes import is_docker
from . import global_settings

logger = logging.getLogger('root')
ENVIRONMENT_VARIABLE = "VAULT_ROLE_ID"

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
        role_id = os.environ.get(ENVIRONMENT_VARIABLE)
        if not role_id:
            desc = ("setting %s" % name) if name else "settings"
            raise ImproperlyConfigured(
                "Requested %s, but settings are not configured. "
                "You must either define the environment variable %s "
                "or call settings.configure() before accessing settings."
                % (desc, ENVIRONMENT_VARIABLE))

        self._wrapped = VaultConfig(role_id)

    def __repr__(self):
        # Hardcode the class name as otherwise it yields 'Settings'.
        if self._wrapped is empty:
            return '<LazySettings [Unevaluated]>'
        return '<LazySettings "%(settings_module)s">' % {
            'settings_module': self._wrapped.SETTINGS_MODULE,
        }

    def __getattr__(self, name):
        """Return the value of a setting and cache it in self.__dict__."""
        if self._wrapped is empty:
            self._setup(name)
        val = getattr(self._wrapped, name)
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


class BaseConfig(Config):
    LOGO = """
                                  ***********.                                                     
                              **********************                                               
                                      *******./@@@&(@@@@@@((((@/ (                                 
                                          ** @@#&@%@@@@/@@@#@@@*@@@       __________________________                
                         *****,             @@@@@,   % @@@@&@,,*@@@.     /                           \\                  
                     *******************  #@ /. @@@ @@&&@@@ @@@@@@@*(   |   Gotta go insanely fast !  |                  
                     *,  ,************** @@/@ , @@@@@&  @@@@ @@@@ @@@   | ____________________________/                 
                         ,,****,      .** ,&@# &@/%  &/@@@.(*@@@..*@ @  |/                 
                 ,*****************         @@@ @   . @@@.@&&@(&   @,                              
                            ,************   .@@@@ @@%@@,         ./@                               
                 ,                   .*******  @@%@@. #@ @@ @ &  %@@                               
                      *********,          .****   #@*@@&&&&&@@*@@@                               
                             ,******,           * *** #@@@@@@@@@@@@@                               
                                     .*,          * ******                                         
                         ,***************,   ,****************               *********,            
                     ********************* *************************,     **       *****           
                  *************     ********************************** *             ****          
                ********,,************ ***********&&&&&&&&&(***********                **,         
               ****** *******    ***************,&&&&&&&&&&&&&&%*******              ,@@@@@@       
         %@@,,@#.*************,******.**********&&&&&&&&&&&&&&&&*******            @@@@@@#         
         @@@@@@@@@@@@@*************************,&&&&&&&&&&&&&&&*******                             
        @@@@@@@@@@@@@@   **, ,*****************#&&&&&&&&&&&&&&********                             
         @@@@@@@@@@@@%      *******,***********#&&&&&&&&&&&&&,********                             
          @@@@@@@@@@@            ****,********* &&&&&&&&&&&&,*******,                              
             &@@@@@                   **********&&&&&&&&&&*********                                
                                     * ***************************                                 
                                        ************************                                   
                                   *****,*,***************,**                                      
                                *******,   ***************, ***                                    
                             *******         ***********,   ***                                    
                          *****                              ***                                   
                        ****,                                 **,                                  
                      ****,                                   ***                                  
                    ,****                                      ***                                 
                    *****                                       *****                              
                    **                                            ********    ******               
         ****************,                                          ,**************                
         ,***************                                                                          
              ,******                                                                              

    """

    # """
    #                      ▄▄▄▄▄
    #             ▀▀▀██████▄▄▄       __________________________
    #           ▄▄▄▄▄  █████████▄  /                           \\
    #          ▀▀▀▀█████▌▀ ▐▄ ▀▐█ |   Gotta go insanely fast !  |
    #        ▀▀█████▄▄ ▀██████▄██ | ____________________________/
    #        ▀▄▄▄▄▄  ▀▀█▄▀█════█▀ |/
    #             ▀▀▀▄  ▀▀███ ▀       ▄▄
    #          ▄███▀▀██▄████████▄ ▄▀▀▀▀▀▀█▌
    #        ██▀▄▄▄██▀▄███▀ ▀▀████      ▄██
    #     ▄▀▀▀▄██▄▀▀▌████▒▒▒▒▒▒███     ▌▄▄▀
    #     ▌    ▐▀████▐███▒▒▒▒▒▐██▌
    #     ▀▄▄▄▄▀   ▀▀████▒▒▒▒▄██▀
    #               ▀▀█████████▀
    #             ▄▄██▀██████▀█
    #           ▄██▀     ▀▀▀  █
    #          ▄█             ▐▌
    #      ▄▄▄▄█▌              ▀█▄▄▄▄▀▀▄
    #     ▌     ▐                ▀▀▄▄▄▀
    #      ▀▀▄▄▀
    #     """

    def __init__(self):
        super().__init__()
        self.from_object(global_settings)

        if self.SERVICE_NAME != "insanic" and self.SERVICE_NAME is not None:
            self.SETTINGS_MODULE = "{0}.config".format(self.SERVICE_NAME)

            try:
                config_module = importlib.import_module(self.SETTINGS_MODULE)
                self.from_object(config_module)
            except ImportError as e:
                logger.debug(
                    "Could not import settings '%s' (Is it on sys.path? Is there an import error in the settings file?): %s %s"
                    % (self.SETTINGS_MODULE, e, sys.path)
                )
                raise e

    def __getattr__(self, attr):
        try:
            return self.__getattribute__(attr)
        except AttributeError as e:
            return super().__getattr__(attr)

    # COMMON SETTINGS
    # @cached_property
    # def IS_DOCKER(self):
    #     try:
    #         with open('/proc/self/cgroup', 'r') as proc_file:
    #             for line in proc_file:
    #                 fields = line.strip().split('/')
    #                 if fields[1] == 'docker':
    #                     return True
    #     except FileNotFoundError:
    #         pass
    #     return False

    # @cached_property
    # def SERVICE_NAME(self):
    #     split_path = sys.argv[0].split('/')
    #
    #     # this means python was run in interactive mode
    #     if len(split_path) == 0:
    #         check_path = os.getcwd()
    #     else:
    #         try:
    #             check_path = os.path.dirname(sys.argv[0])
    #         except AttributeError:
    #             check_path = os.getcwd()
    #
    #     package_name = check_path.split('/')[-1]
    #     package_name = package_name.split('-')[-1]
    #
    #     return package_name

    @property
    def SERVICE_NAME(self):
        return self._service_name

    @SERVICE_NAME.setter
    def SERVICE_NAME(self, val):
        self._service_name = val


class VaultConfig(BaseConfig):
    CONSUL_HOST = "consul.mmt.local"
    CONSUL_PORT = "8500"

    @property
    def VAULT_SCHEME(self):
        return "http"

    @property
    def VAULT_HOST(self):
        return "vault.mmt.local"

    @property
    def VAULT_PORT(self):
        return 8200

    @property
    def VAULT_URL(self):
        url = URL(f"{self.VAULT_SCHEME}://{self.VAULT_HOST}:{self.VAULT_PORT}")
        return str(url)

    @property
    def VAULT_ROLE_ID(self):
        return self._role_id

    @property
    def MMT_ENV(self):
        env = os.environ.get('MMT_ENV', None)
        if env is None:
            logger.warning("MMT_ENV is not set in environment variables.  Please set `export MMT_ENV=<environment>`.")
        return env
        # if not self._env:
        #     self._env = os.environ.get('MMT_ENV', None)
        #     if self._env is None:
        #         logger.warning("MMT_ENV is not set in environment variables.  Please set `export MMT_ENV=<environment>`.")
        # return self._env

    def can_vault(self, raise_exception=False):
        can_vault = self.VAULT_ROLE_ID is not None and self.MMT_ENV is not None
        if can_vault:
            return can_vault
        else:
            if raise_exception:
                raise EnvironmentError(
                    f"VAULT_ROLE_ID and MMT_ENV are required for importing configurations from vault.")
            return can_vault

    def __init__(self, role_id=None):

        self.vault_client = VaultClient(url=self.VAULT_URL)
        self.consul_client = consul.Consul()

        self._role_id = role_id
        super().__init__()

        self._load_from_vault()

    # def _load_secrets(self):
    #
    #     try:
    #         with open('/run/secrets/{0}'.format(self.SERVICE_NAME)) as f:
    #             docker_secrets = f.read()
    #
    #         docker_secrets = json.loads(docker_secrets)
    #
    #         for k, v in docker_secrets.items():
    #             try:
    #                 v = int(v)
    #             except ValueError:
    #                 pass
    #
    #             self.update({k: v})
    #     except FileNotFoundError as e:
    #         logger.debug("Docker secrets not found %s" % e.strerror)
    #         filename = os.path.join(os.getcwd(), 'instance.py')
    #         module = types.ModuleType('config')
    #         module.__file__ = filename
    #
    #         try:
    #             with open(filename) as f:
    #                 exec(compile(f.read(), filename, 'exec'),
    #                      module.__dict__)
    #         except IOError as e:
    #             logger.debug('Unable to load configuration file (%s)' % e.strerror)
    #         for key in dir(module):
    #             if key.isupper():
    #                 self[key] = getattr(module, key)

    def _load_from_vault(self):

        try:
            self.can_vault(raise_exception=True)
        except EnvironmentError as e:
            logger.critical(f"Configs not set from VAULT!! {e.args[0]}")
        else:
            try:
                common_settings = self.vault_client.read(f"/secret/msa/{self.MMT_ENV}/common")
                service_settings = self.vault_client.read(f"/secret/msa/{self.MMT_ENV}/{self.SERVICE_NAME}")
            except Forbidden:
                msg = f"Unable to load settings from vault. Please check settings exists for " \
                      f"the environment and service. ENV: {self.MMT_ENV} SERVICE: {self.SERVICE_NAME}"
                logger.critical(msg)
                raise EnvironmentError(msg)
            else:
                common_settings = common_settings['data']
                service_settings = service_settings['data']

                for k, v in common_settings.items():
                    self[k.upper()] = v

                for k, v in service_settings.items():
                    self[k.upper()] = v

    @cached_property
    def SERVICE_NAME(self):
        if self.can_vault():
            login_response = self.vault_client.auth_approle(self.VAULT_ROLE_ID)
            return login_response['auth']['metadata']['role_name'].split('-')[-1]
        else:
            return super().SERVICE_NAME

    @cached_property_with_ttl(ttl=60)
    def SWARM_MANAGER_HOSTS(self):
        nodes = self.consul_client.catalog.nodes()
        return [n['Address'] for n in nodes[1] if n["Meta"].get('role', None) == "manager"]

    @property
    def SWARM_MANAGER_SCHEME(self):
        return "http"

    @cached_property_with_ttl(ttl=5)
    def SWARM_MANAGER_HOST(self):
        # return random.choice(self.SWARM_MANAGER_HOSTS)
        return "manager.mmt.local"

    @property
    def SWARM_MANAGER_PORT(self):
        return 2375

    @property
    def SWARM_MANAGER_URL(self):
        return URL(f"{self.SWARM_MANAGER_SCHEME}://{self.SWARM_MANAGER_HOST}:{self.SWARM_MANAGER_PORT}")

    @cached_property
    def SERVICE_LIST(self):

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

        with urllib.request.urlopen(services_endpoint) as response:
            swarm_services = response.read()

        swarm_services = json.loads(swarm_services)

        services_config = {}

        for s in swarm_services:
            service_spec = s['Spec']
            service_name = service_spec['Name'].rsplit('-', 1)[-1].lower()

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


class UserSettingsHolder:
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
        if name == 'DEFAULT_CONTENT_TYPE':
            warnings.warn('The DEFAULT_CONTENT_TYPE setting is deprecated.', RemovedInDjango30Warning)
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
