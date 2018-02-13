"""
Provides a set of pluggable permission policies.
"""
SAFE_METHODS = ['GET', 'HEAD', 'OPTIONS']


class BasePermission(object):
    """
    A base class from which all permission classes should inherit.
    """

    async def has_permission(self, request, view):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return True

    async def has_object_permission(self, request, view, obj):
        """
        Return `True` if permission is granted, `False` otherwise.
        """
        return True


class AllowAny(BasePermission):
    """
    Allow any access.
    This isn't strictly required, since you could use an empty
    permission_classes list, but it's useful because it makes the intention
    more explicit.
    """

    async def has_permission(self, request, view):
        return True


class IsAuthenticated(BasePermission):
    """
    Allows access only to authenticated users.
    """

    async def has_permission(self, request, view):
        user = await request.user

        return user


class IsAdminUser(BasePermission):
    """
    Allows access only to admin users.
    """

    async def has_permission(self, request, view):
        user = await request.user
        return user and user.get('is_staff')


class IsAuthenticatedOrReadOnly(BasePermission):
    """
    The request is authenticated as a user, or is a read-only request.
    """

    async def has_permission(self, request, view):
        user = request.user

        return (
                request.method in SAFE_METHODS or
                user
        )

class IsOwnerOrAdmin(BasePermission):
    """
    Custom permission to only allow owners of an object to view or edit it.
    """

    async def has_permission(self, request, view):

        user = await request.user

        if user.get('is_staff'):
            return True

        try:
            return user.get('id') == int(view.kwargs.get("user_id"))
        except TypeError:
            return False
