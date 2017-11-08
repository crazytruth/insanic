import importlib
import os
import sys
import types
import ujson as json
import urllib.parse
import urllib.request
from yarl import URL

from sanic.config import Config
from configparser import ConfigParser

from insanic import global_settings
from insanic.exceptions import ImproperlyConfigured
from insanic.functional import LazyObject, empty, cached_property


SERVICE_VARIABLE = "MMT_SERVICE"

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
        service_name = os.environ.get(SERVICE_VARIABLE)

        if not service_name:
            desc = ("setting %s" % name) if name else "settings"
            raise ImproperlyConfigured(
                "Requested %s, but settings are not configured. "
                "You must either define the environment variable %s "
                "or call settings.configure() before accessing settings."
                % (desc, SERVICE_VARIABLE))

        settings_module = "{0}.config".format(service_name)

        self._wrapped = DockerSecretsConfig(settings_module=settings_module)

    def __getattr__(self, name):
        if self._wrapped is empty:
            self._setup(name)
        return getattr(self._wrapped, name)

    @property
    def configured(self):
        """
        Returns True if the settings have already been configured.
        """
        return self._wrapped is not empty


class DockerSecretsConfig(Config):

    def __init__(self, defaults=None, *, settings_module=None):
        super().__init__(defaults)

        self.SETTINGS_MODULE = settings_module

        self.from_object(global_settings)

        try:
            config_module = importlib.import_module(self.SETTINGS_MODULE)
        except ImportError as e:
            raise ImportError(
                "Could not import settings '%s' (Is it on sys.path? Is there an import error in the settings file?): %s %s"
                % (self.SETTINGS_MODULE, e, sys.path)
            )

        self.from_object(config_module)

        try:
            instance_module = importlib.import_module('instance')
            self.from_object(instance_module)
        except ImportError:
            pass

        self._load_secrets()

    def __getattr__(self, attr):
        try:
            return self.__getattribute__(attr)
        except AttributeError:
            return super().__getattr__(attr)


    @cached_property
    def app(self):
        application = importlib.import_module(self.SERVICE_NAME)
        return application.app


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

    def _load_secrets(self):

        try:
            with open('/run/secrets/{0}'.format(os.environ[SERVICE_VARIABLE])) as f:
                docker_secrets = f.read()

            # print(docker_secrets)
            docker_secrets = json.loads(docker_secrets)

            for k, v in docker_secrets.items():
                try:
                    v = int(v)
                except ValueError:
                    pass

                self.update({k: v})
        except FileNotFoundError as e:
            sys.stderr.write("File not found %s" % e.strerror)
            filename = os.path.join(os.getcwd(), 'instance.py')
            module = types.ModuleType('config')
            module.__file__ = filename

            try:
                with open(filename) as f:
                    exec(compile(f.read(), filename, 'exec'),
                         module.__dict__)
            except IOError as e:
                sys.stderr.write('Unable to load configuration file (%s)' % e.strerror)
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
            raise RuntimeError('Network overlay not found.')

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

            # return services_config

            web_service = service_template.copy()
            web_service['isexternal'] = 1
            web_service['internalserviceport'] = 8000
            web_service['externalserviceport'] = settings.WEB_HOST
            web_service['host'] = settings.WEB_HOST
            services_config.update({'web': web_service})

        else:
            services_location = self._locate_service_ini()
            config = ConfigParser()
            config.read(services_location)

            services_config = {section: config[section] for section in config.sections()
                        if config[section].getboolean('isService', False)}

        return services_config

settings = LazySettings()
