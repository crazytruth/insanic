Change Logs for Insanic
========================

These are the current tracked changes. There was a point in
time when Insanic was developed and released privately.
Refer to `CHANGELOG_LEGACY.rst <CHANGELOG_LEGACY.rst>`_
for changes during that time.

0.9.0 (2020-09-25)
------------------

- BREAKING: :code:`request.user` and :code:`request.service` is now synchronous.
- MAJOR: only supports :code:`sanic>=19.12` because of httpx dependency issues
- MAJOR: removes all kong registration

    - HardJSONAuthentication has been removed
    - InsanicAdminView has been removed

- MAJOR: removes VaultConfig settings for less opinionated configs

    - Streamlines sanic and config config initialization
    - Updated tests to reflect changes
    - Removes hvac from required dependencies

- MAJOR: refactor public routes from Insanic to Router
- MAJOR: removes testing helpers
- MAJOR: removes translation management object
- MAJOR: retires aiohttp for httpx

    - moved :code:`Service` object to client module
    - created :code:`adapter` module for different httpx version compatibility

- MAJOR: Removed :code:`responses` module because issue with 204 has been fixed in sanic 19.12 and above
- MINOR: authentication and permission checks are now only synchronous
- MINOR: refactor service registry to use mapping collection

    - Move registry to registry module
    - Lazy loading for registry

- MINOR: removes gunicorn worker interface (possibly for future implementation)
- MINOR: removed :code:`destination_version` in request services model
- MINOR: moved :code:`ServiceJWTAuthentication to authenication_classes`
- FEAT: tox testing for python>3.6 and sanic>19.3 versions
- CHORE: extracts extra requirements into their own requirments files
- CHORE: reorganizes artwork into its own directory
- CHORE: removes config that are no longer used
- CHORE: refactors Insanic object
- CHORE: refactor jwt handlers and authentication
- CHORE: simplify connections module
