# Copyright © 2011-present, Encode OSS Ltd. All rights reserved.
#
# Provides a set of pluggable permission policies.
#
# Added several permissions for framework usage.
"""
Basic Permissions provided by Insanic.
"""


from insanic.models import _AnonymousUser

SAFE_METHODS = ["GET", "HEAD", "OPTIONS"]


class BasePermission(object):
    """
    A base class from which all permission classes should inherit.
    """

    def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        raise NotImplementedError(".has_permission() needs to be overridden.")


class AllowAny(BasePermission):
    """
    Allow any access.
    This isn't strictly required, since you could use an empty
    permission_classes list, but it's useful because it makes the intention
    more explicit.
    """

    def has_permission(self, request, view):
        return True


class IsAuthenticated(BasePermission):
    """
    Allows access only to authenticated users.
    """

    def has_permission(self, request, view):
        user = request.user

        return not isinstance(user, _AnonymousUser) and user.is_authenticated


class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        user = request.user
        return not isinstance(user, _AnonymousUser) and user.is_staff


class IsAuthenticatedOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """

    def has_permission(self, request, view):
        user = request.user

        return request.method in SAFE_METHODS or not isinstance(
            user, _AnonymousUser
        )


class IsOwnerOrAdmin(BasePermission):
    """
    Custom permission to only allow owners of an object to view or edit it.
    """

    def has_permission(self, request, view):

        user = request.user

        if user.is_staff:
            return True

        try:
            return user.id == view.kwargs.get("user_id")
        except TypeError:  # pragma: no cover
            return False


class IsAnonymousUser(BasePermission):
    """
    Permission to check this api can only be access by non authenticated user.
    """

    def has_permission(self, request, view):
        user = request.user
        return isinstance(user, _AnonymousUser)


class IsServiceOnly(BasePermission):
    """
    Permission to check this api can only be access by another service
    """

    def has_permission(self, request, view):
        service = request.service

        return service.is_authenticated
