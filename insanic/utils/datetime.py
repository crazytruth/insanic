from datetime import datetime, timezone

VALID_UNITS = {'s': 1, 'ms': 1000}


def get_utc_timestamp():
    return datetime.now(tz=timezone.utc).timestamp()


def utc_to_datetime(timestamp=None, units_hint=None):
    if timestamp is None and units_hint is None:
        timestamp = get_utc_timestamp()
    elif timestamp is not None and units_hint is not None:
        if units_hint in VALID_UNITS.keys():
            timestamp = timestamp / VALID_UNITS[units_hint]
        else:
            raise ValueError(f"{units_hint} is an invalid `units_hint` input. Must "
                             f"be either [{'/'.join(VALID_UNITS.keys())}].")
    else:
        raise ValueError("If passing arguments both, timestamp and `units_hint`, are required.")

    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def utc_to_iso(timestamp=None, units_hint=None):
    return utc_to_datetime(timestamp, units_hint).isoformat(timespec='milliseconds')
