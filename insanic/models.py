from typing import Union

from insanic.choices import UserLevels
from insanic.conf import settings


class User:
    """
    Basic User model used for Insanic's Authentication

    :param id: The user id.
    :param level: The user's level (for determining if banned, is staff).
    :param is_authenticated: If the user is authenticated.
    """

    __slots__ = ("_is_authenticated", "id", "level")

    def __init__(
        self,
        *,
        id: str = "",
        level: int = -1,
        is_authenticated: Union[bool, int] = False,
        **kwargs,
    ) -> None:

        self._is_authenticated = is_authenticated
        self.id = id

        self.level = int(level)

    @property
    def is_staff(self) -> bool:
        """
        If user's is determined to be a staff member
        """
        return self.level >= UserLevels.STAFF

    @property
    def is_authenticated(self) -> int:
        """
        If user is resolved to be authenticated
        :return:
        """
        # Why did I make this int?
        return int(self.is_active and self._is_authenticated)

    @property
    def is_active(self) -> bool:
        """
        If user is an active user.
        """
        return self.level >= UserLevels.ACTIVE

    @property
    def is_banned(self) -> bool:
        """
        If user is a banned user.
        """
        return self.level == UserLevels.BANNED

    def __str__(self):

        if not self.is_authenticated:
            user_type = "AnonymousUser"
        else:
            if self.is_staff:
                user_type = "StaffUser"
            else:
                user_type = "User"

        return ",".join([user_type, self.id])

    def __iter__(self):
        yield ("id", self.id)
        yield ("level", self.level)
        yield ("is_authenticated", self.is_authenticated)


class _AnonymousUser(User):
    """
    User when user credentials do not exist in the request.
    """

    def __init__(self):
        super().__init__(id="", level=-1)


class RequestService:
    """
    Basic Request Service model.

    :param source: The Request service's name.
    :param aud: The current application's name.
    :param source_ip: The ip of the requested service.
    :param is_authenticated: If the service is authenticated.
    """

    __slots__ = [
        "request_service",
        "destination_service",
        "source_ip",
        "is_authenticated",
    ]

    def __init__(
        self,
        *,
        source: str,
        aud: str,
        source_ip: str,
        is_authenticated: Union[int, bool],
    ):
        self.request_service = source
        self.destination_service = aud
        self.source_ip = source_ip
        self.is_authenticated = is_authenticated

    @property
    def is_valid(self) -> bool:
        """
        If it is a valid request to the current application.
        """
        return (
            self.destination_service == settings.SERVICE_NAME
            and self.is_authenticated
        )

    def __str__(self):
        if not self.is_authenticated:
            service_type = "AnonymousService"
        else:
            service_type = self.request_service

        return f"{service_type} - {self.destination_service} ({self.source_ip})"

    def __iter__(self):
        yield ("source", self.request_service)
        yield ("aud", self.destination_service)
        yield ("source_ip", self.source_ip)


# need only 1 instance so.. just instantiate and use
#: An AnonmyousUser instance.
AnonymousUser = _AnonymousUser()

#: An Anonymous Request Service instance.
AnonymousRequestService = RequestService(
    source="", aud="", source_ip="", is_authenticated=False,
)


def to_header_value(user: User) -> str:
    """
    A helper method to convert the User object to str.

    :param user:
    :return: A serialized User string.
    """
    return ";".join([f"{k}={v}" for k, v in dict(user).items()])
