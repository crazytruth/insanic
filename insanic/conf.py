import os
import sys
import types

from sanic.config import Config
from configparser import ConfigParser

from insanic import global_settings

class DockerSecretsConfig(Config):

    def __init__(self, defaults=None):
        super().__init__(defaults)
        self.from_object(global_settings)
        self._load_secrets()

        services_location = self._locate_service_ini()
        self._load_service_locations(services_location)


    def _load_secrets(self):
        try:
            with open('/run/secrets/{0}'.format(os.environ['MMT_SERVICE'])) as f:
                docker_secrets = f.read()

            for e in docker_secrets.split(' '):
                k, v = e.split(':', 1)
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

    def _load_service_locations(self, path):
        config = ConfigParser()
        config.read(path)

        services = {section: config[section] for section in config.sections()
                    if config[section].getboolean('isService', False)}

        self['SERVICES'] = services

settings = DockerSecretsConfig()
