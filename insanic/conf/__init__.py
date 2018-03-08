import importlib
import logging
import os
import sys
import types
import ujson as json
import urllib.parse
import urllib.request
from yarl import URL

from sanic.config import Config
from configparser import ConfigParser

from insanic.functional import LazyObject, empty, cached_property
from . import global_settings

logger = logging.getLogger('root')


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
        self._wrapped = SecretsConfig()

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
        self.__dict__[name] = val
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
                         ▄▄▄▄▄
                ▀▀▀██████▄▄▄       __________________________
              ▄▄▄▄▄  █████████▄  /                           \\
             ▀▀▀▀█████▌▀ ▐▄ ▀▐█ |   Gotta go insanely fast !  |
           ▀▀█████▄▄ ▀██████▄██ | ____________________________/
           ▀▄▄▄▄▄  ▀▀█▄▀█════█▀ |/
                ▀▀▀▄  ▀▀███ ▀       ▄▄
             ▄███▀▀██▄████████▄ ▄▀▀▀▀▀▀█▌
           ██▀▄▄▄██▀▄███▀ ▀▀████      ▄██
        ▄▀▀▀▄██▄▀▀▌████▒▒▒▒▒▒███     ▌▄▄▀
        ▌    ▐▀████▐███▒▒▒▒▒▐██▌
        ▀▄▄▄▄▀   ▀▀████▒▒▒▒▄██▀
                  ▀▀█████████▀
                ▄▄██▀██████▀█
              ▄██▀     ▀▀▀  █
             ▄█             ▐▌
         ▄▄▄▄█▌              ▀█▄▄▄▄▀▀▄
        ▌     ▐                ▀▀▄▄▄▀
         ▀▀▄▄▀
        """

    def __init__(self):
        super().__init__()
        self.from_object(global_settings)

        self.SERVICE_NAME = self._find_package_name()

        if self.SERVICE_NAME != "insanic":
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

    def _find_package_name(self):

        try:
            check_path = os.path.dirname(os.path.abspath(sys.modules['__main__'].__file__))
        except AttributeError:
            check_path = os.getcwd()
        finally:
            package_name = check_path.split('/')[-1]
            package_name = package_name.split('-')[-1]

        return package_name

    def __getattr__(self, attr):
        try:
            return self.__getattribute__(attr)
        except AttributeError as e:
            return super().__getattr__(attr)

    # COMMON SETTINGS
    @cached_property
    def IS_DOCKER(self):
        try:
            with open('/proc/self/cgroup', 'r') as proc_file:
                for line in proc_file:
                    fields = line.strip().split('/')
                    if fields[1] == 'docker':
                        return True
        except FileNotFoundError:
            pass
        return False


class SecretsConfig(BaseConfig):

    def __init__(self):
        super().__init__()

        try:
            instance_module = importlib.import_module('instance')
            self.from_object(instance_module)
        except ImportError:
            pass

        self._load_secrets()

    def _load_secrets(self):

        try:
            with open('/run/secrets/{0}'.format(self.SERVICE_NAME)) as f:
                docker_secrets = f.read()

            docker_secrets = json.loads(docker_secrets)

            for k, v in docker_secrets.items():
                try:
                    v = int(v)
                except ValueError:
                    pass

                self.update({k: v})
        except FileNotFoundError as e:
            logger.debug("Docker secrets not found %s" % e.strerror)
            filename = os.path.join(os.getcwd(), 'instance.py')
            module = types.ModuleType('config')
            module.__file__ = filename

            try:
                with open(filename) as f:
                    exec(compile(f.read(), filename, 'exec'),
                         module.__dict__)
            except IOError as e:
                logger.debug('Unable to load configuration file (%s)' % e.strerror)
            for key in dir(module):
                if key.isupper():
                    self[key] = getattr(module, key)

    def _locate_service_ini(self):

        for root, dirs, files in os.walk('..'):
            if "services.ini" in files:
                return os.path.join(root, "services.ini")
        return None

    @property
    def SWARM_MANAGER_HOST(self):

        url = URL(self.CONSUL_ADDR)
        url = url.with_path(self.CONSUL_SWARM_MANAGER_ENDPOINT)

        swarm_hosts = []

        for _ in range(3):
            with urllib.request.urlopen(str(url)) as response:
                if response.status == 200:
                    manager_nodes = json.loads(response.read().decode())

                    if len(manager_nodes['Nodes']):
                        for node in manager_nodes['Nodes']:
                            swarm_hosts.append({"host": node['Node']['Address'], "port": self.SWARM_PORT})
                        break
        else:
            raise RuntimeError("Couldn't initialize service configurations.")

        return swarm_hosts[0]

    def _get_network_overlay_id(self, swarm_host_url):
        url = swarm_host_url.with_path('/networks')
        url = url.with_query(filter=json.dumps(["name=mmt-server-*"]))
        with urllib.request.urlopen(str(url)) as response:
            networks = json.loads(response.read())

        for n in networks:
            if n['Name'].endswith(self.SWARM_NETWORK_OVERLAY):
                return n['Id']
        else:
            raise RuntimeError('Network overlay not found: {0}'.format(self.SWARM_NETWORK_OVERLAY))

    @cached_property
    def SERVICES(self):

        service_template = {
            "githuborganization": "MyMusicTaste",
            "pullrepository": 1,
            "isservice": 1,
            "createsoftlink": 0,
            'isexternal': 0
        }

        if self.IS_DOCKER:

            query_params = {
                "filter": json.dumps(["name=mmt-server"])
            }
            try:
                consul_addr = self.CONSUL_ADDR
            except AttributeError:
                consul_addr = None

            if consul_addr:
                try:
                    url = URL.build(scheme='http', **self.SWARM_MANAGER_HOST)
                except TypeError as e:
                    raise TypeError(e.args[0])
            else:
                url = URL.build(scheme="http", host=self.SWARM_HOST, port=self.SWARM_PORT)

            url = url.with_path("/services")
            url = url.with_query(**query_params)
            services_endpoint = str(url)

            with urllib.request.urlopen(services_endpoint) as response:
                swarm_services = response.read()

            swarm_services = json.loads(swarm_services)

            network_overlay_id = self._get_network_overlay_id(url)

            services_config = {}
            for s in swarm_services:
                if not s['Spec']['Name'].startswith('mmt-server'):
                    continue

                service_spec = s['Spec']
                service_name = service_spec['Name'].rsplit('-', 1)[-1].lower()
                # check if service already exists
                if service_name in services_config:
                    raise EnvironmentError("Duplicate Services.. Something wrong {0}".format(service_name))
                else:
                    services_config[service_name] = service_template.copy()

                # scan attached networks for overlay
                for n in service_spec['TaskTemplate']['Networks']:
                    if n['Target'] == network_overlay_id:
                        break
                else:
                    raise EnvironmentError("Network overlay not attached to {0}".format(service_name.upper()))

                for p in service_spec['EndpointSpec']['Ports']:
                    if p['PublishMode'] == 'ingress':
                        internal_service_port = p['TargetPort']
                        external_service_port = p['PublishedPort']
                        break
                else:
                    raise EnvironmentError("External service port not found for {0}".format(service_name))

                services_config[service_name]['externalserviceport'] = external_service_port
                services_config[service_name]['internalserviceport'] = internal_service_port
                services_config[service_name]['repositoryname'] = "mmt-server-{0}".format(service_name)
                services_config[service_name]['host'] = s['Spec']['Name'].rsplit('_', 1)[-1]

        else:
            services_location = self._locate_service_ini()
            config = ConfigParser()
            config.read(services_location)

            services_config = {}
            for section in config.sections():
                if config[section].getboolean('isService', False):
                    config[section]['host'] = 'localhost'
                    services_config.update({section: config[section]})

        web_service = service_template.copy()
        web_service['isexternal'] = 1
        web_service['internalserviceport'] = 8000
        web_service['externalserviceport'] = settings.WEB_PORT
        web_service['host'] = settings.WEB_HOST
        web_service['schema'] = settings.get('WEB_SCHEMA', 'http')
        services_config.update({'web': web_service})
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
        self.default_settings = default_settings

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
