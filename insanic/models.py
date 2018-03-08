from insanic import authentication


class User:
    __slots__ = ('_is_authenticated', 'id', 'email', 'level')

    def __init__(self, *, id, email, level, is_authenticated=False, **kwargs):
        self._is_authenticated = is_authenticated
        self.id = id
        self.email = email
        self.level = level

    @property
    def is_staff(self):
        return self.level >= authentication.UserLevels.STAFF

    @property
    def is_authenticated(self):
        return self.is_active and self._is_authenticated

    @property
    def is_active(self):
        return self.level >= authentication.UserLevels.ACTIVE

    @property
    def is_banned(self):
        return self.level == authentication.UserLevels.BANNED

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


# need only 1 instance so.. just instantiate and use
AnonymousUser = _AnonymousUser()
