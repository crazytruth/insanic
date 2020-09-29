import os
import re

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


with open("insanic/__init__.py", encoding="utf8") as f:
    version = re.search(r'__version__ = "(.*?)"', f.read()).group(1)


setup(
    name="insanic",
    version=version,
    description="An API framework that extends sanic with a focus on microservices.",
    long_description=(read("README.rst") + "\n\n" + read("CHANGELOG.rst")),
    classifiers=[
        "Intended Audience :: Developers",
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Framework :: Sanic",
    ],
    keywords="api framework sanic async asyncio microservice msa python python3",
    url="https://github.com/crazytruth/insanic",
    author="Kwang Jin Kim",
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
        "prometheus-client==0.5.0",
        "psutil",
    ],
    test_suite="tests",
    include_package_data=True,
    zip_safe=False,
    project_urls={
        "Documentation": "https://insanic.readthedocs.io/en/latest/",
        "Source": "https://github.com/crazytruth/insanic",
        "Tracker": "https://github.com/crazytruth/insanic/issues",
    },
    python_requires=">=3.6",
)
