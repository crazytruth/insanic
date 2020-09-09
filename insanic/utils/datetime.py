from typing import Union

import time

from datetime import datetime, timezone
from dateutil import parser

VALID_UNITS = {"s": 1, "ms": 1000}


def get_utc_timestamp() -> float:
    """
    Returns the current utc timestamp with decimals.

    >>> get_utc_datetime()
    1531279648.991617

    :return:
    :rtype: float
    """
    # time.time is approx 2 time faster
    # return datetime.now(tz=timezone.utc).timestamp()
    return time.time()


def get_utc_datetime() -> datetime:
    """
    Returns the current utc datetime object.

    :return:
    ;:rtype: datetime.Datetime
    """
    return datetime.fromtimestamp(get_utc_timestamp(), tz=timezone.utc)


def timestamp_to_datetime(timestamp: int = None, units: str = None) -> datetime:
    """
    Converts a timestamp to datetime. Assumes timestamp is in utc timezone.
    If not passed gets the current timestamp and converts that.

    If passing in timestamp, must supply units(either ms or s) to depending on
    the units of the timestamp provided.


    :param timestamp:
    :type timestamp: int
    :param units: either ms or s
    :type units: string
    :return:
    :rtype: datetime
    """
    if timestamp is None and units is None:
        timestamp = get_utc_timestamp()
    elif timestamp is not None and units is not None:
        if units in VALID_UNITS.keys():
            timestamp = timestamp / VALID_UNITS[units]
        else:
            raise ValueError(
                f"{units} is an invalid `units_hint` input. Must "
                f"be either [{'/'.join(VALID_UNITS.keys())}]."
            )
    else:
        raise ValueError(
            "If passing arguments both, timestamp and `units_hint`, are required."
        )

    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def timestamp_seconds_to_datetime(timestamp: Union[int, float]) -> datetime:
    """
    Wrapper for timestamp_to_datetime

    :param timestamp:
    :type timestamp: int or float
    :return: datetime
    """
    return timestamp_to_datetime(timestamp=timestamp, units="s")


def timestamp_milliseconds_to_datetime(
    timestamp: Union[int, float]
) -> datetime:
    """
    Wrapper for timestamp_to_datetime

    :param timestamp:
    :type timestamp: int or float
    :return: datetime
    """
    return timestamp_to_datetime(timestamp=timestamp, units="ms")


def timestamp_to_iso(
    timestamp: Union[int, float] = None, units: str = None
) -> str:
    """
    Takes a timestamp and converts it to a iso formatted string


    :param timestamp:
    :param units:
    :type units: string (ms or s)
    :return:
    :rtype: string
    """
    return timestamp_to_datetime(timestamp, units).isoformat(
        timespec="milliseconds"
    )


def iso_to_datetime(datetime_string: str) -> datetime:
    """
    Takes an iso formatted datetime string and tries to convert it to a datetime object

    :param datetime_string:
    :type datetime_string: string
    :return:
    :rtype: datetime
    """
    return parser.parse(datetime_string).astimezone(timezone.utc)


def iso_to_timestamp(iso: str) -> float:
    """
    Takes an iso formatted string and tries to convert it to a timestamp

    :param iso: iso formatted string
    :type iso: string
    :return: timestamp in utc timezone
    :rtype: float
    """
    return iso_to_datetime(iso).timestamp()
