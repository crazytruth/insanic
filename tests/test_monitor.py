import pytest

from insanic import Insanic, status, __version__
from insanic.conf import settings
from insanic.loading import get_service
from insanic.services.registry import registry


def test_view_invalid_method():
    app_name = "test"

    app = Insanic(app_name)

    request, response = app.test_client.get(f"/{app_name}/health/")

    assert response.status == status.HTTP_200_OK
    assert response.json is not None
    assert response.json["service"] == app_name
    assert response.json["status"] == "OK"
    assert response.json["insanic_version"] == __version__


def test_json_metrics():
    app_name = "test"

    app = Insanic(app_name)

    request, response = app.test_client.get(f"/{app_name}/metrics/?json")

    assert response.status == status.HTTP_200_OK
    assert response.json is not None
    assert "total_task_count" in response.json
    assert "active_task_count" in response.json
    assert "proc_rss_mem_bytes" in response.json
    assert "proc_rss_mem_perc" in response.json
    assert "proc_cpu_perc" in response.json
    assert "request_count" in response.json
    assert "timestamp" in response.json

    assert isinstance(response.json["total_task_count"], int)
    assert isinstance(response.json["active_task_count"], int)
    assert isinstance(response.json["proc_rss_mem_bytes"], float)
    assert isinstance(response.json["proc_rss_mem_perc"], float)
    assert isinstance(response.json["proc_cpu_perc"], float)


def test_prometheus_metrics():
    app_name = "prometheus"

    app = Insanic(app_name)

    request, response = app.test_client.get(f"/{app_name}/metrics/")

    assert response.status == status.HTTP_200_OK
    assert response.json is None
    assert "request_count_total" in response.text
    assert "total_task_count" in response.text
    assert "active_task_count" in response.text
    assert "proc_rss_mem_bytes" in response.text
    assert "proc_rss_mem_perc" in response.text
    assert "proc_cpu_perc" in response.text


class TestPingPongView:
    def test_no_depth(self):
        app = Insanic("ping")

        request, response = app.test_client.get("/ping/ping/")
        assert response.status_code == 200
        assert "response" in response.json
        assert "process_time" in response.json

    def test_depth_connection_doesnt_exist(self, monkeypatch):
        registry.reset()
        monkeypatch.setattr(settings, "SERVICE_CONNECTIONS", ["pong"])

        app = Insanic("ping")

        request, response = app.test_client.get(
            "/ping/ping/", params={"depth": 1}
        )
        assert response.status_code == 200
        assert "response" in response.json
        assert "process_time" in response.json

        assert "response" in response.json
        assert "pong" in response.json["response"]

    @pytest.fixture
    def pong_server(self, loop, test_server):
        pong_application = Insanic("pong")

        return loop.run_until_complete(
            test_server(pong_application, host="0.0.0.0")
        )

    @pytest.fixture
    def ping_client(self, loop, test_client):
        app = Insanic("ping")
        return loop.run_until_complete(test_client(app))

    async def test_depth_connection_exists(
        self, monkeypatch, pong_server, ping_client
    ):
        registry.reset()
        monkeypatch.setattr(settings, "SERVICE_CONNECTIONS", ["pong"])

        pong_service = get_service("pong")
        pong_service.host = "127.0.0.1"
        pong_service.port = pong_server.port

        response = await ping_client.get(
            "/ping/ping/",
            params={"depth": 1},
            # server_kwargs={"run_async": True}
        )

        assert response.status == 200

        response_body = await response.json()
        assert "response" in response_body
        assert "process_time" in response_body

        assert "response" in response_body
        assert "pong" in response_body["response"]
        assert response_body["response"]["pong"]["status_code"] == 200
