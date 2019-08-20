from insanic import Insanic, status, __version__


def test_view_invalid_method():
    app_name = "test"

    app = Insanic(app_name)

    request, response = app.test_client.get(f'/{app_name}/health/')

    assert response.status == status.HTTP_200_OK
    assert response.json is not None
    assert response.json['service'] == app_name
    assert response.json['status'] == "OK"
    assert response.json['insanic_version'] == __version__


def test_json_metrics():
    app_name = "test"

    app = Insanic(app_name)

    request, response = app.test_client.get(f'/{app_name}/metrics/?json')

    assert response.status == status.HTTP_200_OK
    assert response.json is not None
    assert "total_task_count" in response.json
    assert "active_task_count" in response.json
    assert "proc_rss_mem_bytes" in response.json
    assert "proc_rss_mem_perc" in response.json
    assert "proc_cpu_perc" in response.json
    assert "request_count" in response.json
    assert "timestamp" in response.json

    assert isinstance(response.json['total_task_count'], int)
    assert isinstance(response.json['active_task_count'], int)
    assert isinstance(response.json['proc_rss_mem_bytes'], float)
    assert isinstance(response.json['proc_rss_mem_perc'], float)
    assert isinstance(response.json['proc_cpu_perc'], float)


def test_prometheus_metrics():
    app_name = 'prometheus'

    app = Insanic(app_name)

    request, response = app.test_client.get(f'/{app_name}/metrics/')

    assert response.status == status.HTTP_200_OK
    assert response.json is None
    assert "request_count_total" in response.text
    assert "total_task_count" in response.text
    assert "active_task_count" in response.text
    assert "proc_rss_mem_bytes" in response.text
    assert "proc_rss_mem_perc" in response.text
    assert "proc_cpu_perc" in response.text
