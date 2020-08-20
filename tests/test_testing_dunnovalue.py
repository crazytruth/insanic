import uuid

import pytest

from insanic.testing.helpers import DunnoValue


@pytest.mark.parametrize(
    "type_to_compare, value_to_compare",
    [
        (int, 3),
        (str, "asdf"),
        (float, 4.2),
        (uuid.UUID, uuid.uuid4()),
        (uuid.UUID, uuid.uuid4().hex),
    ],
)
def test_dunno_value(type_to_compare, value_to_compare):
    assert DunnoValue(type_to_compare) == value_to_compare
    assert (
        repr(DunnoValue(type_to_compare))
        == f"DunnoValue with {type_to_compare}"
    )
