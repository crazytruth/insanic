from typing import Union, Optional

import time

from datetime import datetime, timezone
from dateutil import parser

VALID_UNITS = {"s": 1, "ms": 1000}


def get_utc_timestamp() -> float:
    """
    Returns the current utc timestamp with decimals.

    >>> get_utc_datetime()
    1531279648.991617
    """
    # time.time is approx 2 time faster
    # return datetime.now(tz=timezone.utc).timestamp()
    return time.time()


def get_utc_datetime() -> datetime:
    """
    Returns the current utc datetime object.
    """
    return datetime.fromtimestamp(get_utc_timestamp(), tz=timezone.utc)


def timestamp_to_datetime(
    timestamp: Optional[int] = None, units: Optional[str] = None
) -> datetime:
    """
    Converts a timestamp to datetime. Assumes timestamp is in utc timezone.
    If not passed gets the current timestamp and converts that.

    If passing in timestamp, must supply units(either ms or s) to depending on
    the units of the timestamp provided.


    :param timestamp: Defaults to utc timestamp
    :param units: either "ms" or "s" if `timestamp` is passed
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

    :param timestamp: A timestamp in seconds
    """
    return timestamp_to_datetime(timestamp=timestamp, units="s")


def timestamp_milliseconds_to_datetime(
    timestamp: Union[int, float]
) -> datetime:
    """
    Wrapper for timestamp_to_datetime

    :param timestamp: A timestamp in milliseconds
    """
    return timestamp_to_datetime(timestamp=timestamp, units="ms")


def timestamp_to_iso(
    timestamp: Union[int, float, None] = None, units: Optional[str] = None
) -> str:
    """
    Takes a timestamp and converts it to a iso formatted string

    :param timestamp:
    :param units: either "ms" or "s"
    """
    return timestamp_to_datetime(timestamp, units).isoformat(
        timespec="milliseconds"
    )


def iso_to_datetime(datetime_string: str) -> datetime:
    """
    Takes an iso formatted datetime string and tries to convert it to a datetime object

    :param datetime_string: An iso formatted datetime string
    """
    return parser.parse(datetime_string).astimezone(timezone.utc)


def iso_to_timestamp(iso: str) -> float:
    """
    Takes an iso formatted string and tries to convert it to a timestamp

    :param iso: An iso formatted datetime string
    """
    return iso_to_datetime(iso).timestamp()
