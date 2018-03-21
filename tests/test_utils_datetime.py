import pytest
import time

from dateutil.parser import parse
from datetime import datetime, timedelta, timezone
from insanic.utils import datetime as insanic_datetime


def test_get_utc_timestamp():
    ts = insanic_datetime.get_utc_timestamp()

    assert isinstance(ts, float)
    assert ts == pytest.approx(time.time(), rel=1e-3)


def test_utc_to_datetime_default():
    ts = insanic_datetime.utc_to_datetime()
    assert isinstance(ts, datetime)

    current_datetime = datetime.now(tz=timezone.utc)

    delta = timedelta(seconds=1)

    assert current_datetime - delta <= ts <= current_datetime + delta


@pytest.mark.parametrize("ts,units", [(None, "s"), (time.time(), None), (time.time(), "a")])
def test_utc_to_datetime_problems(ts, units):
    with pytest.raises(ValueError):
        insanic_datetime.utc_to_datetime(ts, units)


def test_utc_to_datetime_custom():
    test_timestamp = 946684800
    test_datetime = datetime(2000, 1, 1, 0, 0, 0, 0, timezone.utc)

    dt = insanic_datetime.utc_to_datetime(test_timestamp, 's')

    assert dt == test_datetime

    ms_dt = insanic_datetime.utc_to_datetime(test_timestamp, 'ms')
    test_ms_datetime = datetime(1970, 1, 11, 22, 58, 4, tzinfo=timezone.utc)

    assert ms_dt == test_ms_datetime


def test_utc_to_iso_default():
    string_datetime = insanic_datetime.utc_to_iso()
    current_datetime = datetime.now(tz=timezone.utc)
    delta = timedelta(seconds=1)

    assert isinstance(string_datetime, str)

    dt = parse(string_datetime)

    assert isinstance(dt, datetime)
    assert current_datetime - delta <= dt <= current_datetime + delta


@pytest.mark.parametrize("ts,units", [(None, "s"), (time.time(), None), (time.time(), "a")])
def test_utc_to_iso_problems(ts, units):
    with pytest.raises(ValueError):
        insanic_datetime.utc_to_iso(ts, units)


def test_utc_to_iso_custom():
    test_timestamp = 946684800
    test_datetime = datetime(2000, 1, 1, 0, 0, 0, 0, timezone.utc)

    string_datetime = insanic_datetime.utc_to_iso(test_timestamp, 's')

    assert string_datetime == test_datetime.isoformat(timespec='milliseconds')

    ms_dt = insanic_datetime.utc_to_iso(test_timestamp, 'ms')
    test_ms_datetime = datetime(1970, 1, 11, 22, 58, 4, tzinfo=timezone.utc)

    assert ms_dt == test_ms_datetime.isoformat(timespec='milliseconds')