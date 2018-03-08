import pytest
import uuid

from sanic.response import text

from insanic import status
from insanic.authentication import JSONWebTokenAuthentication, UserLevels
from insanic.permissions import BasePermission, AllowAny, IsAuthenticated, IsAdminUser, \
    IsAuthenticatedOrReadOnly, IsOwnerOrAdmin, IsAnonymousUser
from insanic.views import InsanicView


def permission_view(permissions, authentications=[]):
    class MockView(InsanicView):
        permission_classes = permissions
        authentication_classes = authentications

        def get(self, request, *args, **kwargs):
            return text('get')

        def post(self, request, *args, **kwargs):
            return text('post')

        def put(self, request, *args, **kwargs):
            return text('put')

        def patch(self, request, *args, **kwargs):
            return text('patch')

        def delete(self, request, *args, **kwargs):
            return text('delete')

    return MockView


class BaseSpecificPermissionTestClass:
    authentications = [JSONWebTokenAuthentication, ]

    def test_permission(self, insanic_application, test_user_token_factory, user_level, expected):
        view = permission_view(self.permissions, self.authentications)

        insanic_application.add_route(view.as_view(), '/')

        headers = {}
        if user_level is not None:
            token = test_user_token_factory(email="test", level=user_level)
            headers = {"Authorization": token}

        request, response = insanic_application.test_client.get('/', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.post('/', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.put('/', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.patch('/', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.delete('/', headers=headers)
        assert response.status == expected


class TestBasePermission:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.view = permission_view([BasePermission])

    def test_base_permission(self, insanic_application):
        insanic_application.add_route(self.view.as_view(), '/')
        request, response = insanic_application.test_client.get('/')

        assert response.status == status.HTTP_500_INTERNAL_SERVER_ERROR


@pytest.mark.parametrize('permission,expected', [
    (AllowAny, status.HTTP_200_OK),
    (IsAnonymousUser, status.HTTP_200_OK),
    (IsAuthenticated, status.HTTP_401_UNAUTHORIZED),
    (IsAdminUser, status.HTTP_401_UNAUTHORIZED),
    (IsAuthenticatedOrReadOnly, status.HTTP_200_OK),
    (IsOwnerOrAdmin, status.HTTP_401_UNAUTHORIZED)])
class TestNotAuthenticatedPermissions:
    def test_not_authenticated_permissions(self, insanic_application, permission, expected):
        view = permission_view([permission, ])
        insanic_application.add_route(view.as_view(), '/')

        request, response = insanic_application.test_client.get('/')
        assert response.status == expected


@pytest.mark.parametrize('permission,safe_expected,not_safe_expected', [
    (AllowAny, status.HTTP_200_OK, status.HTTP_200_OK),
    (IsAnonymousUser, status.HTTP_200_OK, status.HTTP_200_OK),
    (IsAuthenticated, status.HTTP_401_UNAUTHORIZED, status.HTTP_401_UNAUTHORIZED),
    (IsAdminUser, status.HTTP_401_UNAUTHORIZED, status.HTTP_401_UNAUTHORIZED),
    (IsAuthenticatedOrReadOnly, status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED),
    (IsOwnerOrAdmin, status.HTTP_401_UNAUTHORIZED, status.HTTP_401_UNAUTHORIZED)])
class TestNotAuthenticatedWithAuthenticationPermissions:
    def test_not_authenticated_permissions(self, insanic_application, permission, safe_expected, not_safe_expected):
        view = permission_view([permission, ], [JSONWebTokenAuthentication, ])
        insanic_application.add_route(view.as_view(), '/')

        request, response = insanic_application.test_client.get('/')
        assert response.status == safe_expected

        request, response = insanic_application.test_client.post('/')
        assert response.status == not_safe_expected

        request, response = insanic_application.test_client.put('/')
        assert response.status == not_safe_expected

        request, response = insanic_application.test_client.patch('/')
        assert response.status == not_safe_expected

        request, response = insanic_application.test_client.delete('/')
        assert response.status == not_safe_expected


class TestAllowAny(BaseSpecificPermissionTestClass):
    permissions = [AllowAny, ]

    @pytest.mark.parametrize('user_level,expected', [
        (None, status.HTTP_200_OK),
        (UserLevels.STAFF, status.HTTP_200_OK),
        (UserLevels.ACTIVE, status.HTTP_200_OK),
        (UserLevels.DEACTIVATED, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.BANNED, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_permission(self, insanic_application, test_user_token_factory, user_level, expected):
        super().test_permission(insanic_application, test_user_token_factory, user_level, expected)


class TestIsAuthenticated(BaseSpecificPermissionTestClass):
    permissions = [IsAuthenticated, ]

    @pytest.mark.parametrize('user_level,expected', [
        (None, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.STAFF, status.HTTP_200_OK),
        (UserLevels.ACTIVE, status.HTTP_200_OK),
        (UserLevels.DEACTIVATED, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.BANNED, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_permission(self, insanic_application, test_user_token_factory, user_level, expected):
        super().test_permission(insanic_application, test_user_token_factory, user_level, expected)


class TestIsAdminUser(BaseSpecificPermissionTestClass):
    permissions = [IsAdminUser, ]

    @pytest.mark.parametrize('user_level,expected', [
        (None, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.STAFF, status.HTTP_200_OK),
        (UserLevels.ACTIVE, status.HTTP_403_FORBIDDEN),
        (UserLevels.DEACTIVATED, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.BANNED, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_permission(self, insanic_application, test_user_token_factory, user_level, expected):
        super().test_permission(insanic_application, test_user_token_factory, user_level, expected)


class TestIsAnonymousUser(BaseSpecificPermissionTestClass):
    permissions = [IsAnonymousUser, ]

    @pytest.mark.parametrize('user_level,expected', [
        (None, status.HTTP_200_OK),
        (UserLevels.STAFF, status.HTTP_403_FORBIDDEN),
        (UserLevels.ACTIVE, status.HTTP_403_FORBIDDEN),
        (UserLevels.DEACTIVATED, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.BANNED, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_permission(self, insanic_application, test_user_token_factory, user_level, expected):
        super().test_permission(insanic_application, test_user_token_factory, user_level, expected)


class TestIsOwnerOrAdminUser(BaseSpecificPermissionTestClass):
    permissions = [IsOwnerOrAdmin, ]

    @pytest.mark.parametrize('user_level,expected', [
        (None, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.STAFF, status.HTTP_200_OK),
        (UserLevels.ACTIVE, status.HTTP_403_FORBIDDEN),
        (UserLevels.DEACTIVATED, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.BANNED, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_permission(self, insanic_application, test_user_token_factory, user_level, expected):
        super().test_permission(insanic_application, test_user_token_factory, user_level, expected)

    @pytest.mark.parametrize('user_level,expected', [
        (None, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.STAFF, status.HTTP_200_OK),
        (UserLevels.ACTIVE, status.HTTP_200_OK),
        (UserLevels.DEACTIVATED, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.BANNED, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_is_owner(self, insanic_application, test_user_token_factory, user_level, expected):
        view = permission_view(self.permissions, self.authentications)

        insanic_application.add_route(view.as_view(), '/<user_id:[0-9a-fA-F]{32}>')

        headers = {}
        if user_level is not None:
            user_id = uuid.uuid4().hex
            token = test_user_token_factory(id=user_id, email="test", level=user_level)
            headers = {"Authorization": token}
        else:
            #     create some random id
            user_id = uuid.uuid4().hex

        request, response = insanic_application.test_client.get(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.post(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.put(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.patch(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.delete(f'/{user_id}', headers=headers)
        assert response.status == expected

    @pytest.mark.parametrize('user_level,expected', [
        (None, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.STAFF, status.HTTP_200_OK),
        (UserLevels.ACTIVE, status.HTTP_403_FORBIDDEN),
        (UserLevels.DEACTIVATED, status.HTTP_401_UNAUTHORIZED),
        (UserLevels.BANNED, status.HTTP_401_UNAUTHORIZED),
    ])
    def test_is_not_owner(self, insanic_application, test_user_token_factory, user_level, expected):
        view = permission_view(self.permissions, self.authentications)

        insanic_application.add_route(view.as_view(), '/<user_id:[0-9a-fA-F]{32}>')

        headers = {}
        user_id = uuid.uuid4().hex
        if user_level is not None:
            token = test_user_token_factory(email="test", level=user_level)
            headers = {"Authorization": token}

        request, response = insanic_application.test_client.get(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.post(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.put(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.patch(f'/{user_id}', headers=headers)
        assert response.status == expected

        request, response = insanic_application.test_client.delete(f'/{user_id}', headers=headers)
        assert response.status == expected
