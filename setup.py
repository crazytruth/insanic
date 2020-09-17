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


version = "0.8.4.dev0"

setup(
    name="insanic",
    version=version,
    description="API framework for sanic",
    long_description=(read("README.md") + "\n\n" + read("CHANGELOG.md")),
    classifiers=[
        "Intended Audience :: Developers",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.6",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    keywords="api framework sanic async asyncio microservice msa",
    url="http://github.com/crazytruth/insanic",
    author="crazytruth",
    author_email="kwangjinkim@gmail.com",
    license="MIT",
    packages=find_packages(
        exclude=["contrib", "docs", "requirements", "tests*"]
    ),
    install_requires=[
        "uvloop",
        "sanic>=19.12",
        "aioredis>=1.1.0",
        "PyJWT",
        "aiotask_context",
        "python-dateutil",
        "packaging",
        "prometheus-client==0.5.0",
        "psutil==5.4.8",
    ],
    test_suite="tests",
    include_package_data=True,
    zip_safe=False,
)
