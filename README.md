# insanic

> A microservice framework that extends [sanic](sanic).

This framework should only include features that bootstraps
the server and any features that will be required for at least 2 or more services.

## Installation

### Prerequisites

Core dependencies include:

- [sanic](sanic) - extends sanic
- [aiohttp](aiohttp) - only uses the client portion
- [aiodns](aiodns) - for async dns resolution(used by aiohttp client)
- [PyJWT](pyjwt) - for authentication

To install:

``` sh
pip install insanic
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




_For more examples and usage, please refer to the [Wiki][wiki]._

## Development Setup

For development of insanic please install with the following command.

```sh
pip install insanic[dev]
```

## Testing

Insanic tests are run with pytest.
Test with this command:

```sh
python setup.py test
```

setuptools handles all the requirements for testing. U

## Release History

_For full changelogs, please refer to the [CHANGELOG][changelog]._


## Meta

[Kwang Jin Kim](https://github.com/crazytruth) - david@mymusictaste.com

Distributed under the MIT license. See ``LICENSE`` for more information.


## TODO

### NEEDED:

- documentation
- tests
- upgrade sanic to 0.7.0

### FEATURES:

- decorator to determine public/private facing api endpoints
- auto route registration on api gateway/consul?
- vault integration
- RPC for interservice communication

### REMOVE:

- loading.py - tentative.. depending on usages
- models.py
- thumbnails/*
- authentication.py - need to decide where to put this (auth service?)

<!-- Markdown link & img dfn's -->
[wiki]: https://github.com/MyMusicTaste/insanic/wiki
[sanic]: https://github.com/channelcat/sanic
[changelog]: https://github.com/MyMusicTaste/insanic/blob/master/CHANGELOG.md
[aiohttp]: https://aiohttp.readthedocs.io/en/stable/
[aiodns]: https://github.com/saghul/aiodns
[pyjwt]: https://github.com/jpadilla/pyjwt


