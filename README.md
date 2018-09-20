<img src="https://github.com/MyMusicTaste/insanic/blob/master/insanic.png" width="200">

# insanic

> A microservice framework that extends [sanic](sanic).

This framework should only include features that bootstraps
the server and any features that will be required for at least 2 or more services.

Insanic is a very opinionated framework.  It tries to include all the best practices but confines
the developer into using certain packages. For example, for tests, the developer must use
`pytest` and their respective plugin libraries.

### Why we need this

We needed this because we need a core framework for our developers to quickly develop services.
As stated before, this is very opinionated and the reason being, to reduce research time when
trying to select packages to use for their service.  It lays down all the necessary patterns and
bootstraps the application for quick cycle time between idea and deployment.

### Documentation

For more detailed information please refer to the [wiki][wiki]

## Installation

### Prerequisites

Core dependencies include:

- [sanic][sanic] - extends sanic
- [aiohttp][aiohttp] - only uses the client
- [aiodns][aiodns] - for async dns resolution(used by aiohttp client)
- [PyJWT][pyjwt] - for authentication

To install:

``` sh
pip install insanic
```

OR to install from source:

``` bash
pip install git+https://github.com/MyMusicTaste/insanic.git
```

## Usage

For very basic usage:

1. Create a python file. ex. `run.py`

``` py
from insanic import Insanic
from sanic.response import json

app = Insanic(__name__)

@app.route('/')
async def example(request):
    return json({"insanic": "Gotta go insanely fast!"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

```

2. Run with
``` sh
MMT_SERVICE=example python run.py
```

3. Check in browser or `curl`
``` sh
curl http://localhost:8000/
```


_For more examples and usage, please refer to the [Wiki][wiki]._

## Development Setup

If you plan to develop and more importantly, do releases, for insanic, please install with the following command.

```sh
pip install insanic[dev]
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

```



setuptools handles all the requirements for testing.


## Building Base Docker Image

To build base image

``` bash
$ docker build --no-cache -t {username}/insanic -f Dockerfile .
$ docker push {username}/insanic:latest
```

## Generating GRPC stubs

We use [grclib][grpclib] for our grpc implementation. This is because the google implementation 
isn't compatible with asyncio so the generation is a little different.

```bash
# from root of insanic
# for dispatch service
$ python -m grpc_tools.protoc --proto_path=. --python_out=. --python_grpc_out=. insanic/grpc/dispatch/dispatch.proto
# for health 
$ python -m grpc_tools.protoc --proto_path=. --python_out=. --python_grpc_out=. insanic/grpc/health/health.proto
```

This is create the respective `*.grpc.py` and `*_pb2.py` in `insanic.grpc.*` directory.
Any updates to the `.proto` should be followed up with these commands.



## Release History

_For full changelogs, please refer to the [CHANGELOG][changelog]._


## Meta

[Kwang Jin Kim](https://github.com/crazytruth) - david@mymusictaste.com
[Sunghyun Lee](https://github.com/sunghyun-lee) - sunghyunlee@mymusictaste.com
[Jaemyun Lee](https://github.com/jaemyunlee) - jake@mymusictaste.com

Distributed under the MIT license. See ``LICENSE`` for more information.


## TODO

### NEEDED:

- documentation
- tests

### FEATURES:

- RPC for interservice communication


<!-- Markdown link & img dfn's -->
[wiki]: https://github.com/MyMusicTaste/insanic/wiki
[sanic]: https://github.com/channelcat/sanic
[changelog]: https://github.com/MyMusicTaste/insanic/blob/master/CHANGELOG.md
[aiohttp]: https://aiohttp.readthedocs.io/en/stable/
[aiodns]: https://github.com/saghul/aiodns
[pyjwt]: https://github.com/jpadilla/pyjwt
[grpclib]: https://github.com/vmagamedov/grpclib

