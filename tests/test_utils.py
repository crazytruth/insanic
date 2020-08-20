import pytest
from insanic.utils import force_str, try_json_decode


@pytest.mark.parametrize("val", [True, False, 1, 0, b"a", "b"])
def test_force_string(val):
    val = force_str(val)
    assert isinstance(val, str)


def test_try_json_decode():
    test_string = "aasf{af]afasf[sdaf"

    assert test_string == try_json_decode(test_string)

    test_string = '{"a": "b"}'

    assert isinstance(try_json_decode(test_string), dict)
