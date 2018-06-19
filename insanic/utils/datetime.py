from datetime import datetime, timezone
from dateutil import parser

VALID_UNITS = {'s': 1, 'ms': 1000}


def get_utc_timestamp():
    return datetime.now(tz=timezone.utc).timestamp()


def get_utc_datetime():
    return datetime.fromtimestamp(get_utc_timestamp(), tz=timezone.utc)


def utc_to_datetime(timestamp=None, units=None):
    if timestamp is None and units is None:
        timestamp = get_utc_timestamp()
    elif timestamp is not None and units is not None:
        if units in VALID_UNITS.keys():
            timestamp = timestamp / VALID_UNITS[units]
        else:
            raise ValueError(f"{units} is an invalid `units_hint` input. Must "
                             f"be either [{'/'.join(VALID_UNITS.keys())}].")
    else:
        raise ValueError("If passing arguments both, timestamp and `units_hint`, are required.")

    return datetime.fromtimestamp(timestamp, tz=timezone.utc)

def utc_seconds_to_datetime(timestamp):
    return utc_to_datetime(timestamp=timestamp, units='s')

def utc_milliseconds_to_datetime(timestamp):
    return utc_to_datetime(timestamp=timestamp, units='ms')

def utc_to_iso(timestamp=None, units_hint=None):
    return utc_to_datetime(timestamp, units_hint).isoformat(timespec='milliseconds')


def iso_to_datetime(datetime_string):
    return parser.parse(datetime_string).astimezone(timezone.utc)
