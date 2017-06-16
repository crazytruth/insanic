import ujson as json
from collections import namedtuple

User = namedtuple('User', ['id', 'email', 'is_active', 'is_authenticated'])

class BaseMockService:

    service_responses = {}
    def _key_for_request(self, method, endpoint):
        return (method.upper(), endpoint)

    async def mock_dispatch(self, method, endpoint, payload={}, headers={}, return_obj=True, propagate_error=False, **kwargs):
        key = self._key_for_request(method, endpoint)

        if method == "GET" and endpoint == "/api/v1/user/self?fields=id,username,email,is_active,is_ban,is_superuser,locale,version,password,is_authenticated":
            return kwargs.get('test_user')

        if key in self.service_responses:
            return self.service_responses[key]

        raise RuntimeError("Unknown service request: {0} {1}".format(method.upper(), endpoint))

    def register_mock_dispatch(self, method, endpoint, response):
        key = self._key_for_request(method, endpoint)

        if key in self.service_responses:
            raise RuntimeError("Duplicate registrations for {0} {1}".format(key[0], key[1]))

        self.service_responses.update({key: response})


MockService = BaseMockService()


def test_api_endpoint(insanic_application, authorization_token, endpoint, method, request_headers,
                      request_body, expected_response_status, expected_response_body):

    handler = getattr(insanic_application.test_client, method.lower())

    request_headers.update({"content-type": "application/json", "accept": "application/json"})
    if "Authorization" in request_headers:
        request_headers.update({"Authorization": authorization_token})

    request, response = handler(endpoint,
                                debug=True,
                                headers=request_headers,
                                json=request_body)

    assert response.status == expected_response_status

    response_body = json.loads(response.text)

    response_status_category = int(expected_response_status / 100)

    if response_status_category == 2:
        if isinstance(response_body, dict) and isinstance(expected_response_body, dict):
            assert response_body == expected_response_body
        elif isinstance(response_body, dict) and isinstance(expected_response_body, list):
            assert sorted(response_body.keys()) == sorted(expected_response_body)
        elif isinstance(response_body, list) and isinstance(expected_response_body, int):
            assert len(response_body) == expected_response_body
        else:
            raise RuntimeError("Shouldn't be in here. Check response type.")
    elif response_status_category == 3:
        raise RuntimeError("Shouldn't be in here. Redirects not possible.")
    elif response_status_category == 4:
        # if http status code is in the 4 hundreds, check error code
        assert response_body['error_code']['value'] == expected_response_body


TestParams = namedtuple('TestParams', ['method', 'endpoint', 'request_headers', 'request_body',
                                       'expected_response_status', 'expected_response_body'])
def test_parameter_generator(method, endpoint, request_headers, request_body, success_status_code,
                             success_response, check_authorization=True, check_permissions=True, **kwargs):

    if check_permissions:
        if "permissions_endpoint" not in kwargs:
            raise RuntimeError("'permissions_endpoint' must be passed for permissions check parameters.")

    request_headers.update({"Authorization": ""})

    test_parameters_template = TestParams(method=method, endpoint=endpoint, request_headers=request_headers,
                                          request_body=request_body, expected_response_status=success_status_code,
                                          expected_response_body=success_response)
    if check_authorization:
        _req_headers = request_headers.copy()
        if "Authorization" in _req_headers:
            del _req_headers['Authorization']

        p = test_parameters_template._replace(request_headers=_req_headers,
                                              expected_response_status=401, expected_response_body=90001)
        # parameters.append(p)
        yield tuple(p)

    if check_permissions:
        p = test_parameters_template._replace(endpoint=kwargs['permissions_endpoint'],
                                              expected_response_status=403, expected_response_body=90010)

        yield tuple(p)

    yield tuple(test_parameters_template)

def test_parameter(method, endpoint, request_headers, request_body, expected_response_status, expected_response_body):
    return [tuple(TestParams(method=method, endpoint=endpoint, request_headers=request_headers,
                            request_body=request_body, expected_response_status=expected_response_status,
                            expected_response_body=expected_response_body))]

