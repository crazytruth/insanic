from insanic import status
from insanic.responses import json_response


def test_malformed_204_response_has_no_content_length():
    # flask-restful can generate a malformed response when doing `return '', 204`

    response = json_response({}, status=status.HTTP_204_NO_CONTENT)
    assert response.status == status.HTTP_204_NO_CONTENT
    assert response.body == b""

    http_response = response.output().split(b'\r\n')

    assert status.HTTP_204_NO_CONTENT in http_response[0]
    assert "No Content" in http_response[0]
    assert "Content-Type" not in http_response[2]
