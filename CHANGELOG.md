Changelog for insanic
=====================

0.1.10 (unreleased)
-------------------

- Nothing changed yet.


0.1.9 (2018-03-29)
------------------

- REVERT: authorization header check in test_api_endpoint


0.1.8 (2018-03-29)
------------------

- FIX: remove content type when making requests in test_api_endpoint


0.1.7 (2018-03-29)
------------------

- FIX: fix for when content-type is not json and data sent as json
- REVERT: authorization header in test_api_endpoint


0.1.6 (2018-03-29)
------------------

- REFACTOR: flake8 compliance
- FEAT: support content type in test_api_endpoints


0.1.5 (2018-03-28)
------------------

- FIX: redis port settings when running tests


0.1.4 (2018-03-28)
------------------

- UPGRADE: Upgrade aioredis for 1.1.0 compatibility
- REFACTOR: cache connection usages
- ADD: insanic default cache in default settings to divide cache usages
- ADD: add different cache fixtures for insanic tests(not plugin)
- FIX: but in cache_get_response decorator when query params has more than 1 item
- REMOVE: monkeypatching redisdb for asyncio compatibility


0.1.3 (2018-03-23)
------------------

- Sanic error handling
- remove development from xray patch


0.1.2 (2018-03-22)
------------------

- change location of secrets in vault


0.1.1 (2018-03-22)
------------------

- Add hvac to requirements
- Fix circular imports with userlevels


0.1.0 (2018-03-21)
------------------

- MAJOR: now pulls settings from VAULT
- MAJOR: remove thumbnails
- MAJOR: throttling support
- MAJOR: updated logo
- FEATURE: can create services that haven't been declared. Will just throw 503 when route information doens't exist.
- FEATURE: new permission IsAnonymousUser
- UPDATE: better sanic exception handling
- UPDATE: refactor and user and anonymous user object when authenticating
- UPDATE: TESTS!
- UPDATE: cache_get_response doesn't take status as a parameter, it is saved in the cache now
- UPDATE: permissions actually works lol
- REFACTOR: tentative settings refactor for vault settings
- REFACTOR: create separate test command for testing insanic
- REFACTOR: change cache_get_response decorator to class for easier testing
- REFACTOR: tracing sampler to own class. No longer in Insanic app
- CHORE: better logging on errors
- DEPRECATED: has_object_permissions is now deprecated

0.0.192 (2018-02-19)
--------------------

- FIX: int casting of user_id in permissions
- FEATURE: Add AnonymousUser to user when not authenticated
- UPDATE: Remove Request object protocol override in place of sanic's updated app interface
- REFACTOR: remove unused code
- REFACTOR: config abstraction for preparation for difference source config loading
- FIX: override redis connection info when running tests


0.0.191 (2018-02-13)
--------------------

- FIX: permissions when user is not staff
- FIX: when user is not authenticated
- FIX: token generation during tests


0.0.190 (2018-02-13)
--------------------

- FIX: jwt authentication to not request user
- FEATURE: test user token generation factory depending on user level


0.0.189 (2018-02-13)
--------------------

- FIX: asynchronous permissions


0.0.188 (2018-02-13)
--------------------

- FIX: is_staff in helpers


0.0.187 (2018-02-12)
--------------------

- BREAKING: changed name of MMTBaseView to InsanicView for opensourcedness(is this a word?)
- FEATURE: DunnoValue in insanic tests
- FEATURE: add is_staff to mock user namedtuple
- REFACTOR: moved sampling rules to global settings
- REFACTOR: refactor logging config
- CHORE: tracing config
- CHORE: generalize settings object


0.0.186 (2018-02-08)
--------------------

- CHORE: Refactor tracing and silences when not needed
- FEATURE: response caching decorator


0.0.185 (2018-02-07)
--------------------

- MAJOR: updated sanic to 0.7.0
- BREAKING: when running insanic in run.py remove log_config parameter
- FEATURE: better organization of logging modules
- FIX: 204 empty body assertion in test_api_endpoint
- FIX: bug with tracing not getting sent with logs
- REFACTOR: remove log email handlers and reporters
- CHORE: refactor middleware registration for sanic 0.7.0 upgrade


0.0.184 (2018-02-07)
--------------------

- FIX: Assertion in test_api_endpoint on 400 level status codes were being asserted properly


0.0.183 (2018-02-06)
--------------------

- FIX: config discovery logic didn't work when run in cmdline


0.0.182 (2018-02-06)
--------------------

- FEATURE: allows configuration from last word of project root split by "-"


0.0.181 (2018-02-06)
--------------------

- runservices marker fix


0.0.180 (2018-02-06)
--------------------

- *MAJOR* Remove dependency on MMT_SERVICE environment variable.
   DO NOT need it anymore!
- Add Pytest setuptools command
- Migrate runservices pytest marker to insanic


0.0.179 (2018-02-05)
--------------------

- *BREAKING* remove `data` from view functions
- test environment variables refactored
- added datetime utils functions
- async allow any permission class fix
- respect error code declaration in APIExceptions


0.0.168 (2018-01-31)
--------------------

- Bug fix with authentication in tests


0.0.167 (2018-01-31)
--------------------

- switch assertion variable in api tests
- README update
- tests to setuptools command


0.0.166 (2018-01-25)
--------------------