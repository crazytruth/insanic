Changelog for insanic
=====================

0.0.184 (unreleased)
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