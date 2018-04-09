from insanic.choices import UserLevels
from insanic.conf import settings


class User:
    __slots__ = ('_is_authenticated', 'id', 'email', 'level')

    def __init__(self, *, id, email, level, is_authenticated=False, **kwargs):
        self._is_authenticated = is_authenticated
        self.id = id
        self.email = email
        self.level = level

    @property
    def is_staff(self):
        return self.level >= UserLevels.STAFF

    @property
    def is_authenticated(self):
        return self.is_active and self._is_authenticated

    @property
    def is_active(self):
        return self.level >= UserLevels.ACTIVE

    @property
    def is_banned(self):
        return self.level == UserLevels.BANNED

    def __str__(self):

        if not self.is_authenticated:
            user_type = "AnonymousUser"
        else:
            if self.is_staff:
                user_type = "StaffUser"
            else:
                user_type = "User"

        return ",".join([user_type, self.id, self.email])


class _AnonymousUser(User):

    def __init__(self):
        super().__init__(id='', email='', level=-1)


class RequestService:
    __slots__ = ['request_service', 'destination_service', 'source_ip',
                 'destination_version', 'is_authenticated']

    def __init__(self, *, source, aud, source_ip, destination_version, is_authenticated):
        self.request_service = source
        self.destination_service = aud
        self.source_ip = source_ip
        self.destination_version = destination_version
        self.is_authenticated = is_authenticated

    @property
    def is_valid(self):
        return self.destination_service == settings.SERVICE_NAME and self.is_authenticated

    def __str__(self):
        if not self.is_authenticated:
            service_type = "AnonymousService"
        else:
            service_type = self.request_service

        return ",".join([service_type, self.destination_service, self.source_ip, self.destination_service])


AnonymousRequestService = RequestService(source="", aud="", source_ip="", destination_version="",
                                         is_authenticated=False)

# need only 1 instance so.. just instantiate and use
AnonymousUser = _AnonymousUser()
