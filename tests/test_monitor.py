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
