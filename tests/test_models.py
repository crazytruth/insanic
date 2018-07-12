import pytest

from insanic.choices import UserLevels
from insanic.models import User, AnonymousUser

TEST_USER_ID = "1"


@pytest.fixture()
def test_user():
    test_level = UserLevels.ACTIVE
    test_authenticated = True

    return User(id=TEST_USER_ID, level=test_level, is_authenticated=test_authenticated)


def test_anonymous_user():
    anon_user = AnonymousUser

    assert anon_user.is_staff is False
    assert anon_user.is_authenticated is 0
    assert anon_user.is_active is False
    assert anon_user.is_banned is False

    assert str(anon_user).startswith("AnonymousUser")


def test_user_active(test_user):
    assert test_user.id == TEST_USER_ID
    assert test_user.level == UserLevels.ACTIVE
    assert test_user.is_staff is False
    assert test_user.is_authenticated is 1
    assert test_user.is_active is True
    assert test_user.is_banned is False

    assert str(test_user).startswith('User')
    assert test_user.id in str(test_user)


def test_user_ban(test_user):
    test_user.level = UserLevels.BANNED

    assert test_user.is_staff is False
    assert test_user.is_authenticated is 0
    assert test_user.is_active is False
    assert test_user.is_banned is True

    assert str(test_user).startswith('AnonymousUser')


def test_user_deactivated(test_user):
    test_user.level = UserLevels.DEACTIVATED

    assert test_user.is_staff is False
    assert test_user.is_authenticated is 0
    assert test_user.is_active is False
    assert test_user.is_banned is False

    assert str(test_user).startswith('AnonymousUser')


def test_user_staff(test_user):
    test_user.level = UserLevels.STAFF

    assert test_user.is_staff is True
    assert test_user.is_authenticated is 1
    assert test_user.is_active is True
    assert test_user.is_banned is False

    assert str(test_user).startswith('StaffUser')
