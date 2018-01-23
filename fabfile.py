import json
import os
import requests

from fabric.api import local
from configparser import ConfigParser

config = None

DOCKER_USERNAME = "199574976045.dkr.ecr.ap-northeast-1.amazonaws.com"
MSA_DOCKER_USERNAME = "120387605022.dkr.ecr.ap-northeast-1.amazonaws.com"

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

    requirements = [r for r in requirements if os.path.exists(r)]

    local('bumpversion --verbose --search "insanic=={{current_version}}" --replace "insanic=={{new_version}}" '
          '--no-commit --no-tag --allow-dirty {0} {1}'.format(bump_part, " ".join(requirements)))
    local('python setup.py sdist upload -r host')

    _slack_developers(new_version=)


def _slack_developers(new_version):
    params = {}
    params['channel'] = '#dev-project-msa'
    params['username'] = "INSANIC UPDATE"
    params['text'] = f'NOTE: New version of insanic=={new_version} has been released. `pip install -U insanic` to update.'
    params['icon_emoji'] = ":ghost:"

    slack_webhook_url = 'https://hooks.slack.com/services/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'

    # f = urllib.urlopen(slack_webhook_url, params)
    r = requests.post(slack_webhook_url, data=json.dumps(params))



def build_insanic():
    local('docker build --no-cache -t {0}/insanic -f Dockerfile .'.format(MSA_DOCKER_USERNAME))
    local('$(aws ecr get-login --no-include-email --profile mmt-msa)')
    local('docker push {0}/insanic:latest'.format(MSA_DOCKER_USERNAME))
