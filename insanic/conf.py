import os
import sys
import types
import ujson as json
import urllib.parse
import urllib.request

from sanic.config import Config
from configparser import ConfigParser

from insanic import global_settings

class DockerSecretsConfig(Config):

    def __init__(self, defaults=None):
        super().__init__(defaults)
        self.from_object(global_settings)
        self._load_secrets()

        services_location = self._locate_service_ini()

        if services_location is not None:
            self._load_service_locations(services_location)
        else:
            self._initiate_from_swarm()

        print(self)


    def _load_secrets(self):

        try:
            with open('/run/secrets/{0}'.format(os.environ['MMT_SERVICE'])) as f:
                docker_secrets = f.read()

            print(docker_secrets)
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

    def _load_service_locations(self, path):
        config = ConfigParser()
        config.read(path)

        services = {section: config[section] for section in config.sections()
                    if config[section].getboolean('isService', False)}

        self['SERVICES'] = services

    def _initiate_from_swarm(self):

        query_params = {
            "filter": json.dumps(["name=mmt-server-*"])
        }

        query = urllib.parse.urlencode(query_params)
        parsed_endpoint = ('http', '{0}:{1}'.format(self.SWARM_HOST, self.SWARM_PORT), "/services", "", query, '')

        services_endpoint = urllib.parse.urlunparse(parsed_endpoint)

        with urllib.request.urlopen(services_endpoint) as response:
            swarm_services = response.read()

        swarm_services = json.loads(swarm_services)

        service_template = {
            "githuborganization": "MyMusicTaste",
            "pullrepository": 1,
            "isservice": 1,
            "createsoftlink": 0
        }

        services_config = {}
        for s in swarm_services:
            if not s['Spec']['Name'].startswith('mmt-server-'):
                continue

            service_spec = s['Spec']
            service_name = service_spec['Name'].split('-', 2)[-1].lower()
            # check if service already exists
            if service_name in services_config:
                raise EnvironmentError("Duplicate Services.. Something wrong {0}".format(service_name))
            else:
                services_config[service_name] = service_template.copy()

            # scan attached networks for overlay
            for n in service_spec['Networks']:
                if n['Target'] == self.SWARM_NETWORK_OVERLAY:
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


        self['SERVICES'] = services_config



settings = DockerSecretsConfig()
