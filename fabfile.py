from fabric.api import local

MSA_DOCKER_USERNAME = "120387605022.dkr.ecr.ap-northeast-1.amazonaws.com"


def build_insanic():
    local('docker build --no-cache -t {0}/insanic -f Dockerfile .'.format(MSA_DOCKER_USERNAME))
    local('$(aws ecr get-login --no-include-email --profile mmt-msa)')
    local('docker push {0}/insanic:latest'.format(MSA_DOCKER_USERNAME))
