import re

HIDDEN_KEY_WORDS = [
    "API",
    "TOKEN",
    "KEY",
    "SECRET",
    "PASS",
    "PROFANITIES_LIST",
    "SIGNATURE",
    "SESSION",
    "EMAIL",
    "PHONE",
]

HIDDEN_SETTINGS = re.compile(
    "|".join(HIDDEN_KEY_WORDS + [v.lower() for v in HIDDEN_KEY_WORDS])
)

CLEANSED_SUBSTITUTE = "*********"


def cleanse_value(key, value):
    """Cleanse an individual setting key/value of sensitive content.
    If the value is a dictionary, recursively cleanse the keys in
    that dictionary.
    """
    try:
        if HIDDEN_SETTINGS.search(key):
            cleansed = CLEANSED_SUBSTITUTE
        else:
            if isinstance(value, dict):
                cleansed = dict(
                    (k, cleanse_value(k, v)) for k, v in value.items()
                )
            else:
                cleansed = value
    except TypeError:
        # If the key isn't regex-able, just return as-is.
        cleansed = value

    return cleansed


def get_safe_dict(target):
    "Returns a dictionary with sensitive settings blurred out."
    return_value = {}
    for k in target:
        return_value[k] = cleanse_value(k, target.get(k))
    return return_value
