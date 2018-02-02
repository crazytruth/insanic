from datetime import datetime, timezone
import time


def utc_to_datetime(timestamp=None, units=None):
    if timestamp is None and units is None:
        timestamp = time.time()
        units = "ms"
    elif timestamp is not None and units is None:
        raise ValueError("You must pass in the timestamp units. [s/ms]")
    elif timestamp is None and units is not None:
        if units == "s":
            timestamp = int(time.time())
        elif units == "ms":
            timestamp = int(time.time() * 1000)
        else:
            raise ValueError(f"{units} is an invalid units input. Must be either [s/ms].")
    else:
        if units == "ms":
            timestamp = timestamp / 1000
    return datetime.fromtimestamp(timestamp).replace(tzinfo=timezone.utc)


def utc_to_iso(timestamp=None, units=None):
    return utc_to_datetime(timestamp, units).isoformat(timespec='milliseconds')
