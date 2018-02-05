from datetime import datetime, timezone


def get_utc_timestamp():
    return datetime.utcnow().timestamp()


def utc_to_datetime(timestamp=None, units=None):

    if timestamp is None and units is None:
        timestamp = get_utc_timestamp()
        units = "s"
    elif timestamp is not None and units is not None:
        if units == "s":
            timestamp = int(timestamp)
        elif units == "ms":
            timestamp = int(timestamp * 1000)
        else:
            raise ValueError(f"{units} is an invalid units input. Must be either [s/ms].")
    else:
        raise ValueError("If passing arguments both, timestamp and units, are required.")

    return datetime.fromtimestamp(timestamp).replace(tzinfo=timezone.utc)


def utc_to_iso(timestamp=None, units=None):
    return utc_to_datetime(timestamp, units).isoformat(timespec='milliseconds')
