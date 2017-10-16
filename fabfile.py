import os
from fabric.api import local
from configparser import ConfigParser

config = None

DOCKER_USERNAME = "199574976045.dkr.ecr.ap-northeast-1.amazonaws.com"

def _load_config(mmt_server_path):
    global config
    if config is None:
        config = ConfigParser()
        config.read("/".join([mmt_server_path, "services.ini"]))

def find_directory(dir_name):
    cwd = os.getcwd()
    for i in range(cwd.count('/')):
        cwd = os.path.join(cwd, '../', dir_name)
        if os.path.isdir(cwd):
            print(cwd)
            return cwd


def bumpversion(bump_part="patch"):
    mmt_server_directory = find_directory("mmt-server")

    _load_config(mmt_server_directory)
    requirements = [os.path.join(mmt_server_directory, service, 'requirements.txt')
                    for service in config.sections() if bool(config[service].getboolean('isService')) and not bool(config[service].getboolean('isExternal'))]

    local('bumpversion --verbose --search "insanic=={{current_version}}" --replace "insanic=={{new_version}}" '
          '--no-commit --no-tag --allow-dirty {0} {1}'.format(bump_part, " ".join(requirements)))
    local('python setup.py sdist upload -r host')



def build_insanic():
    local('docker build --no-cache -t {0}/insanic -f Dockerfile .'.format(DOCKER_USERNAME))
    local('$(aws ecr get-login --no-include-email)')
    local('docker push {0}/insanic:latest'.format(DOCKER_USERNAME))
