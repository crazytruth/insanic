# insanic

> A microservice framework that extends [sanic](sanic).

This framework should only include features that bootstraps
the server and any features that will be required for at least 2 or more services.

## Installation

### Prerequisites

```sh
pip install insanic
```

## Usage

_For more examples and usage, please refer to the [Wiki][wiki]._

## Development setup

For development of insanic please install with the following command.

```sh
pip install insanic[dev]
```

## Testing

Test with the this command

```sh
python setup.py test
```

## Release History

_For full changelogs, please refer to the [CHANGELOG][changelog]._


## Meta

David Kwang Jin Kim - david@mymusictaste.com

Distributed under the

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
[changelog]: https://github.com/channelcat/sanic/blob/master/CHANGELOG.md
[]