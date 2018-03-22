from enum import IntEnum


class UserLevels(IntEnum):
    BANNED = 0
    DEACTIVATED = 10
    ACTIVE = 100
    STAFF = 1000
