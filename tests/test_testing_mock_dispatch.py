import pytest
from insanic.testing.helpers import BaseMockService


class TestMockService:

    @pytest.fixture(autouse=True)
    def init_mock_service(self):
        self.mock_service = BaseMockService()

    @pytest.mark.parametrize("method", ["GET", "POST"])
    @pytest.mark.parametrize("endpoint", ["/api/v1/{}", "/api/v1/{}?endpoint=this"])
    @pytest.mark.parametrize("request_body", [{}, {"request": "body", "body": "request"}])
    @pytest.mark.parametrize("query_params", [{}, {"query": "params", "params": "query"}])
    async def test_register(self, method, endpoint, request_body, query_params, function_session_id):
        endpoint = endpoint.format(function_session_id)

        expected_response = {}
        # expected_response.update({"method": method})
        # expected_response.update({"endpoint": endpoint})
        # expected_response.update({"request_body": request_body})
        # expected_response.update({"query_params": query_params})
        expected_response.update({"session_id": function_session_id})
        expected_response_status_code = 201

        self.mock_service.register_mock_dispatch(method, endpoint, expected_response,
                                                 expected_response_status_code, request_body, query_params)

        response = await self.mock_service.mock_dispatch(method, endpoint, query_params=query_params,
                                                         payload=request_body)
        assert response == expected_response
        response = await self.mock_service.mock_dispatch(method, endpoint, query_params=query_params)
        assert response == expected_response
        response = await self.mock_service.mock_dispatch(method, endpoint, payload=request_body)
        assert response == expected_response
        response = await self.mock_service.mock_dispatch(method, endpoint)
        assert response == expected_response

        with pytest.raises(RuntimeError):
            response = await self.mock_service.mock_dispatch(method, "/")
