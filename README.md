<img src="https://github.com/MyMusicTaste/insanic/blob/master/insanic.png" width="200">

# insanic

> A microservice framework that extends [sanic](sanic).

Think of this as django-rest-framework is to django but for microservice usage (and a lot less functionality than drf).

Insanic is a very opinionated framework.  It tries to include all the best practices for
developing in a microservice architecture.  To do this certain technologies needed to be used.

### Why we need this

We needed this because we need a framework for our developers to quickly develop services
while migrating to a microservice architecture.
As stated before, this is very opinionated and the reason being, to reduce research time when
trying to select packages to use for their service.  It lays down all the necessary patterns and
bootstraps the application for quick cycle time between idea and deployment.

### FEATURES:

- Authentication and Authorization (like drf)
- Easy Service Requests
- Normalized Error Message Formats
- Connection manager to redis
- Utils for extracting public routes (will help when registering to api gateway)
- Bootstrap monitoring endpoints
- Throttling

### Documentation

For more detailed information please refer to the [wiki][wiki]

## Installation

### Prerequisites

Core dependencies include:

- [sanic][sanic] - extends sanic
- [httpx][httpx] - to make requests to other services
- [aiodns][aiodns] - for async dns resolution
- [PyJWT][pyjwt] - for authentication
- Redis server

To install:

``` sh
pip install insanic
```

OR to install from source:

``` bash
pip install git+https://github.com/MyMusicTaste/insanic.git
```

## Usage

For very basic usage, it is pretty much the same as Sanic:

1. Create a python file. ex. `run.py`

``` py
from insanic import Insanic
from insanic.conf import settings
from sanic.response import json

settings.configure()
__version__ = "0.1.0"

app = Insanic(__name__, version=__version__)

@app.route('/')
async def example(request):
    return json({"insanic": "Gotta go insanely fast!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

```

2. Run with
``` sh
python run.py
```

3. Check in browser or `curl`
``` sh
curl http://localhost:8000/
```


_For more examples and usage, please refer to the [Wiki][wiki]._

## Development Setup

If you plan to develop and more importantly, do releases, for insanic, please install with the following command.

```sh
$ pip install .
$ pip install -r requirements/dev.txt
$ pre-commit install
```

To recompile requirements. Add the requirements to *.in
```sh
$ pip-compile dev.in
```


## Testing

Insanic tests are run with pytest.
Test with this command:

```sh
$ python setup.py test

# with coverage

$ python setup.py test -a "--cov=insanic --cov-report term-missing:skip-covered"

# a certain set of tests

$ python setup.py test --pytest-args tests/test_pact.py

# tox, run for sanic > 19.12 and python >= 3.6

$ tox

```

## Release History

_For full changelogs, please refer to the [CHANGELOG][changelog]._

## Contributing

For guidance on setting up a development environment and how to make a contribution to Insanic,
see the contributing guidelines.

## Meta

- [Kwang Jin Kim](https://github.com/crazytruth) - kwangjinkim@gmailcom
- [Sunghyun Lee](https://github.com/sunghyun-lee) - sunghyunlee@mymusictaste.com
- [Jaemyun Lee](https://github.com/jaemyunlee) - jake@mymusictaste.com

Distributed under the MIT license. See ``LICENSE`` for more information.

Thanks to all the people at MyMusicTaste that worked with me to make this possible.

## TODO

### NEEDED:

- documentation

## Links

- Documentation: https
- Releases: https://pypi.org/project/insanic/
- Code: https://www.github.com/crazytruth/insanic/
- Issue Tracker: https://www.github.com/crazytruth/insanic/issues
- Sanic Documentation: https://sanic.readthedocs.io/en/latest/index.html
- Sanic Repository:


<!-- Markdown link & img dfn's -->
[wiki]: https://github.com/MyMusicTaste/insanic/wiki
[sanic]: https://github.com/channelcat/sanic
[changelog]: https://github.com/MyMusicTaste/insanic/blob/master/CHANGELOG.md
[httpx]: https://www.python-httpx.org/
[aiodns]: https://github.com/saghul/aiodns
[pyjwt]: https://github.com/jpadilla/pyjwt
