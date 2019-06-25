Changelog for insanic
=====================


0.7.12 (unreleased)
-------------------

- UPGRADE: increase log level to critical for uncaught exceptions


0.7.11 (2019-05-29)
-------------------

- BREAKING: THROTTLE_NUM_PROXIES deprecated in favor of PROXIES_COUNT
- BREAKING: remove client_ip attribute from Request object in favor or remote_addr
- UPGRADE: upgrade sanic version to 19.3.1
- FIX: activate unhealthy function in healthcheck forward to target
- FIX: throttle bug where headers aren't properly read
- FIX: grpc channel close when exiting context manager
- CHORE: fixes throttle tests in compliability with header
- REFACTOR: unpack throttle settings
- CHORE: remove pact integration
- CHORE: remove userip middleware
- REVERT: keep alive timeout on inter service to 15s
- REFACTOR: added SERVICE_CONNECTION_KEEP_ALIVE_TIMEOUT in settings to change keepalive_timeout


0.7.10 (2019-03-19)
-------------------

- HOTFIX: aws-xray-sdk and aiohttp setuppy bug fix 


0.7.9 (2019-03-19)
------------------

- HOTFIX: aiohttp version


0.7.8 (2019-03-19)
------------------

- HOTFIX: set aws-xray-sdk to 1.1.2 


0.7.7 (2019-03-19)
------------------

- REVERT: up aws xray sdk


0.7.6 (2019-03-19)
------------------

- HOTFIX: set uvloop requirements to 0.12.0
- REVERT: revert prometheus client
- CHORE: up prometheus client version


0.7.5 (2019-03-18)
------------------

- HOTFIX: remove prometheus counter 


0.7.4 (2019-03-18)
------------------

- HOTFIX: move global process variable into function 
- HOTFIX: lower library restrictions for aws xray sdk


0.7.3 (2019-02-13)
------------------

- HOTFIX: cleanses body of logs when error occurs


0.7.2 (2019-02-13)
------------------

- BREAKING: remove rabbitmq integration
- CHORE: lowers log level for 4xx status codes from exception(error) to info
- FEAT: more information on client response errors
- CHORE: fixes issue when creating gateway aiohttp clientsession   

0.7.1 (2019-01-30)
------------------

- FIX: include psutil in requirements
- FIX: add config for sanic update
- CHORE: updates aws-xray-sdk to 1.1.2


0.7.0 (2019-01-30)
------------------

- FEAT: update sanic dependency to 18.12.0
- FEAT: load grpc server classes and serves
- FEAT: searches installed grpc packages and binds to service client object
- CHORE: remove grpc health in place of grpclib health  
- CHORE: fix tests for new grpclib release 0.2.1
- CHORE: refactor tests to use test package
- FEAT: add error codes, method, path and uri template to network logs for better logging 
- FEAT: changes the order in which the settings from vault are loaded from  common/config/secret to common/secret/config
- FEAT: introduce metrics endpoint which exposes cpu/mem usages and task counts
- FEAT: introduce new config to turn off infuse (INFUSE_ENABLED=0)
- FEAT: include context in grpc stub requests
- FEAT: query param validation upon instantiation
- FEAT: add grpc network logging stub communications


0.6.7 (2018-12-18)
------------------

- CHORE: sanic access logger to always log for info level
- FEAT: userip http call to buffer into mq 


0.6.6 (2018-12-04)
------------------

- FEAT: divide vault settings to config and secrets
- FEAT: if vault settings and config is not set, fall back to original vault settings
- FEAT: rabbitmq integration!
- FEAT: initialize xray subsegments from traced requests
- FEAT: reduce keep alive to 0 to prevent 1 instance sending requests to only 1 instance 
- DEPRECATE: sampling rules for views because hard to manage
- CHORE: refactor legacy span naming to segments


0.6.5 (2018-10-18)
------------------

- FEAT: implement naive client-side grpc loadbalancing


0.6.4 (2018-10-16)
------------------

- CHORE: modify logging for grpc access logs
- FIX: test user token factory for test plugins
- CHORE: better error handling for grpc


0.6.3 (2018-10-11)
------------------

- FIX: grpc healthcheck logging for general exception


0.6.2 (2018-10-11)
------------------

- FIX: view dispatch logic with convert keywords and authentications


0.6.1 (2018-10-11)
------------------

- FIX: set request object to view before dispatch prep
- FIX: add google-common-protos to required packages


0.6.0 (2018-10-05)
------------------

- MAJOR: GRPC server and client implementation
- FEAT: allow multiple files with same keys in dispatch


0.5.10 (2018-08-16)
-------------------

- CHORE: get my ip by hostname and get ip with socket's own address when ip by hostname is empty or localhost address


0.5.9 (2018-08-06)
------------------

- FIX: insanic protocol override


0.5.8 (2018-08-01)
------------------

- REFACTOR: remove env dependent logic
- REVERT: tracing context on dispatch fetch
- ENHANCEMENT: deregister upstream and target on no public routes

0.5.7 (2018-07-25)
------------------

- CHORE: port into settings
- FIX: gunicorn port settings


0.5.6 (2018-07-24)
------------------

- EDGE: support for gunicorn 
- FEAT: ip in service health


0.5.5 (2018-07-18)
------------------

- CHORE: refactor content-length headers for responses.
- CHORE: rename json to json_response


0.5.4 (2018-07-17)
------------------

- FIX: remove content-length header on 204


0.5.3 (2018-07-17)
------------------

- REFACTOR: redo how kong registers services and targets


0.5.2 (2018-07-17)
------------------

- REVERT: allow service jwt backwards compatibility


0.5.1 (2018-07-17)
------------------

- FEAT: add client_ip property in request class to indentify the originating IP address of a client connection with header field x-forwarded-for
- FIX: plugin tests with service tokens by inject user 


0.5.0 (2018-07-16)
------------------

- FEAT: brand spankin new status code HTTP_497_SAGOCHIN_NYOSUK!!
- HUGE REFACTOR: refactor kong gateway object to be synchronous because of integrity issues
- TWEAKING: each deploy creates new service/routes/upstreams
- FEAT: add timings to ping api
- FEAT: add correlation_id to all logs within a context of a request
- OPTIMIZATION: interservice communication authorization
    - remove interservice jwt for each user
    - add single jwt for service-to-service 
    - inject user information to headers
- FEAT: inject correlation id to interservice requests
- CHORE: rename datetime util functions that don't represent what they actually do
- CHORE: unpack exception to error message function to utils
- CHORE: refactor requests object to handle formdata and clean up unused methods


0.4.18 (2018-07-10)
-------------------

- FIX: cast INSANIC_WORKERS to integer


0.4.17 (2018-07-10)
-------------------

- FEAT: allow workers to set from INSANIC_WORKERS environment variable
- FEAT: ping/pong service api with depth 
- FEAT: allow log level to be set from environment variables
- FIX: add slash to userip call 


0.4.16 (2018-07-06)
-------------------

- FIX: hard jwt when no token is provided
- UPDATE: return 408 when request takes too long. Different from 504 when the server
- UPDATE: one client session to rule them all!! for service objects 
- UPDATE: json logging to include request service

0.4.15 (2018-07-04)
-------------------

- FIX: update protocol with updated sanic


0.4.14 (2018-07-04)
-------------------

- FIX: hardjwtauth for testing
- CHORE: ensure connection configs can be extended


0.4.13 (2018-07-04)
-------------------

- FEAT: decorators for capturing functions as subsegments
- FEAT: hard jwt authentication 
- FIX: xray tracing not recording body
- CHORE: refactor gateway registration
- FIX: multipart/form-data in http_dispatch using aiohttp.FormData
- TEST: tests for sending multipart/form-data
- FEAT: wrap service dispatch with xray 


0.4.12 (2018-06-29)
-------------------

- CHORE: set streaming threshold to lower value
- HOTFIX: catch error on environment not running on swarm  


0.4.11 (2018-06-27)
-------------------

- FIX: bug when parsing payload to json
- CHORE: refactor date header on http_dispatch


0.4.10 (2018-06-26)
-------------------

- FEAT: catch `asyncio.TimeoutError` on http_dispatch
- FEAT: `files` parameter on `http_dispatch` to send files. 
    - Will place `multipart/form-data` as content-type
- FEAT: `request_timeout` on `http_dispatch` to override default
- FIX: register target as ip instead of hostname on kong
- FIX: xray middleware with images #114
- FEAT: obfuscate more stuff on logs


0.4.9 (2018-06-22)
------------------

- FIX: xray patching when packages do not exist


0.4.8 (2018-06-21)
------------------

- REFACTOR: xray config so it is the first thing to happen when starting server 


0.4.7 (2018-06-21)
------------------

- FEAT: add request_service in logging
- FEAT: load settings from environment variables. These take precedence!
- REFACTOR: tracing related settings
- DEPRECATE: tracing wrapping of service object 
- NEW: use aiohttp client config for inter service tracing
- FEAT: new util method for kong (force_target_healthy)
- REMOVE: logging for kong healthchecks


0.4.6 (2018-06-19)
------------------

- FIX: restructure xray middleware so user is set at the response middleware


0.4.5 (2018-06-19)
------------------

- FIX: kong route registration with better route comparison
- FIX: fix bug with configs in xray middleware


0.4.4 (2018-06-19)
------------------

- FIX: xray integration
- FIX: plugin integration point changed
- FEAT: changed error codes for not found


0.4.3 (2018-06-08)
------------------

- FIX: bad code when splitting service name in service list


0.4.2 (2018-06-08)
------------------

- REFACTOR: remove used code from gateway


0.4.1 (2018-06-08)
------------------

- FIX: add packaging to required


0.4.0 (2018-06-08)
------------------

- FEAT: pact integration in testing
- FEAT: register upstreams and targets in kong
- FEAT: only the registered container can deregister
- FEAT: service versioning
- FEAT: registering version to settings


0.3.15 (2018-05-31)
-------------------

- FIX: stream reader on service http dispatch
- FEAT: assertion test messages on api endpoint tests


0.3.14 (2018-05-31)
-------------------

- FIX: mock dispatch now raises apiexception on propagate_error


0.3.13 (2018-05-31)
-------------------

- CRITICAL: http_dispatch bug. 


0.3.12 (2018-05-30)
-------------------

- BREAKING: refactor exceptions to be consistent with error responses
    - detail -> description
    - default_detail -> message
- FEAT: i18n attribute on exceptions
- FEAT: prefix servicename or package name on error code response
- FEAT: add several datetime util functions
- FEAT: add iso_to_datetime util function
- FIX: rename units_hint to units on utc_to_datetime function
- FIX: bug with kong plugins where none could be in the list
- FIX: public facing support for composition views 
- CHORE: remove req_ctx from http_dispatch. didnt do anything anyways


0.3.11 (2018-05-23)
-------------------

- FIX: service to service requests for anonymous users(e.g. no token in request)


0.3.10 (2018-05-21)
-------------------

- FIX: better normalized mock dispatch


0.3.9 (2018-05-21)
------------------

- FIX: pytest insanic tests for new jwt contract
- FEAT: check is docker by calling ecs metadata endpoint


0.3.8 (2018-05-19)
------------------

- UPDATE: insanic service authentication with task contexts 
- UPDATE: service tokens are created with user from task contexts
- FEAT: just context added to task when authentication if performed


0.3.7 (2018-05-18)
------------------

- CHANGE: allow vault url from environment variables


0.3.6 (2018-05-17)
------------------

- FIX: cast port to int


0.3.5 (2018-05-17)
------------------

- CHORE: Better Logging for create service on kong 


0.3.4 (2018-05-15)
------------------

- FEAT: refactor so test_user_token_factory can be imported for use
    - from insanic.testing.plugin import user_token_factory
- FEAT: mock userip sending on tests
- FEAT: allow query_params arguments in register_mock_dispatch
- FIX: when authentication headers passed in test_api_endpoint and anonymous user set to true
- FIX: when mocking dispatch for get requests with separate query_params
- FIX: make service exception handling compatible with aiohttp 3.0.1
- FIX: service auth error when not needed


0.3.3 (2018-05-14)
------------------

- FIX: int casting in datetime converting helper function
- FIX: userip service authentication bug


0.3.2 (2018-05-11)
------------------

- FIXED: interservice host configuration


0.3.1 (2018-05-11)
------------------

- FIXED: interservice host resolution when not running in container.


0.3.0 (2018-05-10)
------------------

- FEATURE: add JWT plugin to routes that have JWTAuth assigned (@sunghyun-lee)
- FEATURE: jwt token authentication (@sunghyun-lee)
- FEATURE: ip logging middleware (@jaemyunlee)
- REMOVE: consul dependency
- REMOVE: swarm manager dependency
- DEPRECATE: SERVICE_LIST settings
- FIX: inter service skip breaker problem

0.2.7 (2018-04-23)
------------------

- CHORE: Kong logging refactor
- FIX: when more than 1 worker is run, only the main/first process handles registration
- FEATURE: allow list assertions in api endpoint tests
- FIX: ujson to json in tests because of float loads precision


0.2.6 (2018-04-20)
------------------

- FEATURE: soft fail when kong is not available.
- BUG: testing with mock service requests was monkeypatching wrong method
- BUG: on mock_dispatch fallback to response without payloads if doesn't exist.


0.2.5 (2018-04-19)
------------------

- FEATURE: regex priority for local and development swarms
- FIX: mock service values with iterables as values in body
- FIX: test service token factory to set aud to self
- CHORE: dns changes


0.2.4 (2018-04-19)
------------------

- FIX: public facing decorator wasn't passing arguments correctly


0.2.3 (2018-04-19)
------------------

- FEATURE: service token factory for service only requests
- FEATURE: allow registration mockservice with same endpoints but different payloads
- FEATURE: 'is_service_only' flag for `test_parameter_generator` to inject service tokens on request
- FIX: change get_ip to get proper ip address


0.2.2 (2018-04-18)
------------------

- Change route registration to register one by one


0.2.1 (2018-04-18)
------------------

- FIX: bug with public_facing where view methods have positional arguments
- FIX: logic bug with testing gateway deregistration
- FIX: bug with service name settings

0.2.0 (2018-04-17)
------------------

- FEATURE: flag your public facing endpoints and methods with the public_facing decorator!
- FEATURE: API registration with kong
- FEATURE: get my ip util function
- FEATURE: health check apis now have service name prefix eg /health -> /user/health
- CHORE: domain changes
- CHORE: health check endpoint reconfiguration


0.1.11 (2018-04-10)
-------------------

- FIX: user level is not set properly in pytest-insanic
- REFACTOR: keyword parameters for test_parameter_generator changes to match test_api_endpoint
    - BREAKING: expected_status_code -> expected_response_status
    - BREAKING: expected_response -> expected_response_body


0.1.10 (2018-04-09)
-------------------

- BREAKING: remove MMT_ENV in *.config
- Inject service tokens on service requests
- add IsServiceOnly permission
- authorization header overwrite when request headers declared during endpoint tests
- DEPRECATED: return_obj in service http_dispatch has been removed
- Bunch of refactoring


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
