import pytest
from insanic.utils import force_str


@pytest.mark.parametrize('val', [True, False, 1, 0, b"a", "b"])
def test_force_string(val):
    val = force_str(val)
    assert isinstance(val, str)
