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


version = '0.8.4.dev0'


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
    "requests",
    "aioresponses",
    "grpc-test-monkey"
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
        'sanic==19.6.2',
        'sanic-useragent',
        'aiohttp>=3.3.0',
        'aiodns',
        # 'yarl==1.1.1',
        'aioredis>=1.1.0',
        'PyJWT',
        "hvac==0.9.5",
        "aiotask_context",
        "python-dateutil",
        "packaging",
        "prometheus-client==0.5.0",
        "psutil==5.4.8"
    ],

    tests_require=test_requires,
    test_suite='tests',
    extras_require={
        "testing": test_requires,
        "dev": ["zest.releaser[recommended]", "flake8"],
    },
    cmdclass={'test': pytest_command()},
    include_package_data=True,
    zip_safe=False
)
