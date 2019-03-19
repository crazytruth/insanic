import os
from setuptools import setup, find_packages

here = os.path.dirname(__file__)


def read(fname):
    """
    Read given file's content.
    :param str fname: file name
    :returns: file contents
    :rtype: str
    """
    return open(os.path.join(here, fname)).read()


version = '0.7.6.dev0'


def pytest_command():
    from commands.pytest import PyTestCommand
    return PyTestCommand


test_requires = [
    "coverage",
    "pytest",
    "pytest-cov",
    "pytest-redis",
    "pytest-sanic",
    "pytest-sugar",
    "pytest-xdist",
    "chardet",
    "pytest-flake8",
    "asynctest",
    "pact-python",
    "requests",
    "aioresponses",
    "grpc-test-monkey"

    # "beautifulsoup4"
    # "docker",
    # "aiobotocore",

    # "pytest",
    # "pytest-asyncio",
]

setup(
    name='insanic',
    version=version,
    description='API framework for sanic',
    long_description=(
            read('README.md') + '\n\n' + read('CHANGELOG.md')
    ),
    classifiers=[
        'Intended Audience :: Developers',
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development :: Libraries :: Application Frameworks'
    ],
    keywords='api framework sanic async asyncio microservice msa',
    url='http://github.com/MyMusicTaste/insanic',
    author='crazytruth',
    author_email='kwangjinkim@gmail.com',
    license='MIT',
    packages=find_packages(exclude=['contrib', 'docs', 'tests*']),
    setup_requires=["zest.releaser[recommended]", "setuptools"],
    install_requires=[
        'uvloop==0.12.0',
        'sanic==18.12.0',
        'sanic-useragent',
        'aiohttp>=3.0.0',
        'aiodns',
        # 'yarl==1.1.1',
        'aioredis>=1.1.0',
        'PyJWT',
        'aws-xray-sdk>=1.1.1',
        "python-consul",
        "hvac",
        "aiotask_context",
        # "infuse>=0.1.0",
        "python-dateutil",
        "packaging",
        "grpclib==0.2.1",
        "googleapis-common-protos",
        "prometheus-client==0.5.0",
        "psutil==5.4.3"
        # "tenacity==5.0.2"
    ],
    # test_suite='nose.collector',
    tests_require=test_requires,
    test_suite='tests',
    # entry_points={
    #     'pytest11': [
    #         'insanic = insanic.testing.plugin',
    #     ]
    # },
    extras_require={
        "testing": test_requires,
        "dev": ["zest.releaser[recommended]", "flake8"],
        "grpc": ["protobuf", "grpcio-tools", "googleapis-common-protos"]
    },
    cmdclass={'test': pytest_command()},
    include_package_data=True,
    zip_safe=False
)
