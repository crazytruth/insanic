import pytest
import uvloop
from sanic.response import json, text

from insanic import status, authentication
from insanic.choices import UserLevels
from insanic.conf import settings
from insanic.exceptions import ImproperlyConfigured
from insanic.models import User
from insanic.request import Request
from insanic.throttles import AnonRateThrottle, UserRateThrottle, BaseThrottle, ScopedRateThrottle, SimpleRateThrottle
from insanic.views import InsanicView


class User3SecRateThrottle(UserRateThrottle):
    rate = '3/sec'
    scope = 'seconds'


class User3MinRateThrottle(UserRateThrottle):
    rate = '3/min'
    scope = 'minutes'


class NonTimeThrottle(BaseThrottle):
    def allow_request(self, request, view):
        if not hasattr(self.__class__, 'called'):
            self.__class__.called = True
            return True
        return False


class MockView(InsanicView):
    throttle_classes = (User3SecRateThrottle,)
    authentication_classes = (authentication.JSONWebTokenAuthentication,)
    permission_classes = ()

    def get(self, request, *args, **kwargs):
        return json({"insanic": "gotta go insanely fast!"})


class MockView_MinuteThrottling(MockView):
    throttle_classes = (User3MinRateThrottle,)


class MockView_NonTimeThrottling(MockView):
    throttle_classes = (NonTimeThrottle,)


class TestThrottling:

    def test_requests_are_throttled(self, insanic_application):
        """
        Ensure request rate is limited
        """
        insanic_application.add_route(MockView.as_view(), '/')

        for _ in range(4):
            request, response = insanic_application.test_client.get('/')

        assert response.status == status.HTTP_429_TOO_MANY_REQUESTS

    def test_request_throttle_timer(self, insanic_application, monkeypatch):
        """
        Ensure request rate is limited for a limited duration only
        """

        insanic_application.add_route(MockView.as_view(), '/')

        monkeypatch.setattr(MockView.throttle_classes[0], 'timer', lambda self: 0)

        for _ in range(4):
            request, response = insanic_application.test_client.get('/')

        assert response.status == status.HTTP_429_TOO_MANY_REQUESTS
        monkeypatch.setattr(MockView.throttle_classes[0], 'timer', lambda self: 1)
        request, response = insanic_application.test_client.get('/')
        assert response.status == status.HTTP_200_OK

    def test_request_throttling_is_per_user(self, insanic_application, test_user_token_factory):
        """
        Ensure request rate is only limited per user, not globally for
        PerUserThrottles
        """
        insanic_application.add_route(MockView.as_view(), '/')
        token1 = test_user_token_factory(email="test1@mmt.com", level=UserLevels.ACTIVE)
        token2 = test_user_token_factory(email="test2@mmt.com", level=UserLevels.ACTIVE)

        for dummy in range(3):
            insanic_application.test_client.get('/', headers={"Authorization": token1})

        request, response = insanic_application.test_client.get('/', headers={"Authorization": token2})
        assert response.status == status.HTTP_200_OK

    def ensure_response_header_contains_proper_throttle_field(self, insanic_application, monkeypatch, view,
                                                              expected_headers):
        """
        Ensure the response returns an Retry-After field with status and next attributes
        set properly.
        """
        for timer, expect in expected_headers:
            monkeypatch.setattr(view.throttle_classes[0], 'timer', lambda self: timer)
            request, response = insanic_application.test_client.get('/')

            if expect is not None:
                assert response.headers['Retry-After'] == expect
            else:
                assert not 'Retry-After' in response.headers

    def test_seconds_fields(self, insanic_application, monkeypatch):
        """
        Ensure for second based throttles.
        """
        insanic_application.add_route(MockView.as_view(), '/')
        expected_headers = (
            (0, None),
            (0, None),
            (0, None),
            (0, '1')
        )
        self.ensure_response_header_contains_proper_throttle_field(insanic_application, monkeypatch,
                                                                   MockView, expected_headers)

    def test_minutes_fields(self, insanic_application, monkeypatch):
        """
        Ensure for minute based throttles.
        """
        insanic_application.add_route(MockView_MinuteThrottling.as_view(), '/')
        self.ensure_response_header_contains_proper_throttle_field(
            insanic_application,
            monkeypatch,
            MockView_MinuteThrottling,
            (
                (0, None),
                (0, None),
                (0, None),
                (0, '60')
            )
        )

    def test_next_rate_remains_constant_if_followed(self, insanic_application, monkeypatch):
        """
        If a client follows the recommended next request rate,
        the throttling rate should stay constant.
        """
        insanic_application.add_route(MockView_MinuteThrottling.as_view(), '/')
        self.ensure_response_header_contains_proper_throttle_field(
            insanic_application,
            monkeypatch,
            MockView_MinuteThrottling,
            (
                (0, None),
                (20, None),
                (40, None),
                (60, None),
                (80, None)
            )
        )

    def test_non_time_throttle(self, insanic_application):
        """
        Ensure for second based throttles.
        """
        # request = self.factory.get('/')
        insanic_application.add_route(MockView_NonTimeThrottling.as_view(), '/')

        assert hasattr(MockView_NonTimeThrottling.throttle_classes[0], 'called') is False

        request, response = insanic_application.test_client.get('/')
        assert ('Retry-After' in response.headers) is False

        assert MockView_NonTimeThrottling.throttle_classes[0].called is True

        request, response = insanic_application.test_client.get('/')
        assert ('Retry-After' in response.headers) is False


class TestScopedRateThrottle:
    """
    Tests for ScopedRateThrottle.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        self.throttle = ScopedRateThrottle()

        class XYScopedRateThrottle(ScopedRateThrottle):
            TIMER_SECONDS = 0
            THROTTLE_RATES = {'x': '3/min', 'y': '1/min'}

            def timer(self):
                return self.TIMER_SECONDS

        class XView(InsanicView):
            authentication_classes = (authentication.JSONWebTokenAuthentication,)
            permission_classes = ()
            throttle_classes = (XYScopedRateThrottle,)
            throttle_scope = 'x'

            def get(self, request):
                return text('x')

        class YView(InsanicView):
            authentication_classes = (authentication.JSONWebTokenAuthentication,)
            permission_classes = ()
            throttle_classes = (XYScopedRateThrottle,)
            throttle_scope = 'y'

            def get(self, request):
                return text('y')

        class UnscopedView(InsanicView):
            authentication_classes = (authentication.JSONWebTokenAuthentication,)
            permission_classes = ()
            throttle_classes = (XYScopedRateThrottle,)

            def get(self, request):
                return text('y')

        self.throttle_class = XYScopedRateThrottle
        self.x_view = XView.as_view()
        self.y_view = YView.as_view()
        self.unscoped_view = UnscopedView.as_view()

    def increment_timer(self, seconds=1):
        self.throttle_class.TIMER_SECONDS += seconds

    def test_scoped_rate_throttle(self, insanic_application):
        insanic_application.add_route(self.x_view, '/x')
        insanic_application.add_route(self.y_view, '/y')

        # Should be able to hit x view 3 times per minute.
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 200

        self.increment_timer()
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 200

        self.increment_timer()
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 200
        self.increment_timer()
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 429

        # Should be able to hit y view 1 time per minute.
        self.increment_timer()
        request, response = insanic_application.test_client.get('/y')
        assert response.status == 200

        self.increment_timer()
        request, response = insanic_application.test_client.get('/y')
        assert response.status == 429

        # Ensure throttles properly reset by advancing the rest of the minute
        self.increment_timer(55)

        # Should still be able to hit x view 3 times per minute.
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 200

        self.increment_timer()
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 200

        self.increment_timer()
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 200

        self.increment_timer()
        request, response = insanic_application.test_client.get('/x')
        assert response.status == 429

        # Should still be able to hit y view 1 time per minute.
        self.increment_timer()
        request, response = insanic_application.test_client.get('/y')
        assert response.status == 200

        self.increment_timer()
        request, response = insanic_application.test_client.get('/y')
        assert response.status == 429

    def test_unscoped_view_not_throttled(self, insanic_application):
        insanic_application.add_route(self.unscoped_view, '/u')

        for idx in range(10):
            self.increment_timer()
            request, response = insanic_application.test_client.get('/u')
            assert response.status == 200

    def test_get_cache_key_returns_correct_key_if_user_is_authenticated(self, insanic_application,
                                                                        test_user_token_factory):
        class DummyView(InsanicView):
            throttle_scope = 'user'

            def get(self, *args, **kwargs):
                return text('dummy')

        user_id = 1
        user = User(id=user_id, email="test@test.test", level=UserLevels.ACTIVE, is_authenticated=True)

        class MockRequest:
            @property
            async def user(self):
                return user

        request = MockRequest()

        loop = uvloop.new_event_loop()
        loop.run_until_complete(self.throttle.allow_request(request, DummyView()))

        loop = uvloop.new_event_loop()
        cache_key = loop.run_until_complete(self.throttle.get_cache_key(request, view=DummyView()))

        assert cache_key == 'throttle_user_%s' % user_id


class XffTestingBase:

    @pytest.fixture(autouse=True)
    def setup(self, insanic_application):
        class Throttle(ScopedRateThrottle):
            THROTTLE_RATES = {'test_limit': '1/day'}
            TIMER_SECONDS = 0

            def timer(self):
                return self.TIMER_SECONDS

        class View(InsanicView):
            throttle_classes = (Throttle,)
            throttle_scope = 'test_limit'
            permission_classes = ()

            def get(self, request):
                return text('test_limit')

        self.throttle = Throttle()
        self.view = View.as_view()

        insanic_application.add_route(self.view, '/')

        @insanic_application.middleware("request")
        def add_headers(request):
            request.headers['remote_addr'] = '3.3.3.3'
            request.headers['x_forwarded_for'] = '0.0.0.0, 1.1.1.1, 2.2.2.2'

    def config_proxy(self, num_proxies, monkeypatch):
        monkeypatch.setitem(settings.THROTTLES, 'NUM_PROXIES', num_proxies)


class TestIdWithXffBasic(XffTestingBase):
    def test_accepts_request_under_limit(self, insanic_application, monkeypatch):
        self.config_proxy(0, monkeypatch)
        request, response = insanic_application.test_client.get('/')
        assert response.status == 200

    def test_denies_request_over_limit(self, insanic_application, monkeypatch):
        self.config_proxy(0, monkeypatch)
        insanic_application.test_client.get('/')
        request, response = insanic_application.test_client.get('/')
        assert response.status == 429


class TestXffSpoofing(XffTestingBase):
    def test_xff_spoofing_doesnt_change_machine_id_with_one_app_proxy(self, insanic_application, monkeypatch):
        self.config_proxy(1, monkeypatch)
        request, response = insanic_application.test_client.get('/')

        @insanic_application.middleware('request')
        def add_headers2(request):
            request.headers['x_forwarded_for'] = '4.4.4.4, 5.5.5.5, 2.2.2.2'

        request, response = insanic_application.test_client.get('/')
        assert response.status == 429

    def test_xff_spoofing_doesnt_change_machine_id_with_two_app_proxies(self, insanic_application, monkeypatch):
        self.config_proxy(2, monkeypatch)

        request, response = insanic_application.test_client.get('/')

        @insanic_application.middleware('request')
        def add_headers2(request):
            request.headers['x_forwarded_for'] = '4.4.4.4, 1.1.1.1, 2.2.2.2'

        request, response = insanic_application.test_client.get('/')
        assert response.status == 429


class TestXffUniqueMachines(XffTestingBase):
    def test_unique_clients_are_counted_independently_with_one_proxy(self, insanic_application, monkeypatch):
        self.config_proxy(1, monkeypatch)
        request, response = insanic_application.test_client.get('/')

        @insanic_application.middleware('request')
        def add_headers2(request):
            request.headers['x_forwarded_for'] = '0.0.0.0, 1.1.1.1, 7.7.7.7'

        request, response = insanic_application.test_client.get('/')

        assert response.status == 200

    def test_unique_clients_are_counted_independently_with_two_proxies(self, insanic_application, monkeypatch):
        self.config_proxy(2, monkeypatch)
        request, response = insanic_application.test_client.get('/')

        @insanic_application.middleware('request')
        def add_headers2(request):
            request.headers['x_forwarded_for'] = '0.0.0.0, 7.7.7.7, 2.2.2.2'

        request, response = insanic_application.test_client.get('/')

        assert response.status == 200


class TestBaseThrottle:
    def test_allow_request_raises_not_implemented_error(self, loop):
        with pytest.raises(NotImplementedError):
            loop.run_until_complete(BaseThrottle().allow_request(request={}, view={}))

    def test_wait(self):
        assert BaseThrottle().wait() is None


class TestSimpleRateThrottleTests:

    @pytest.fixture(autouse=True)
    def setUp(self):
        SimpleRateThrottle.scope = 'anon'

    def test_get_rate_raises_error_if_scope_is_missing(self):
        throttle = SimpleRateThrottle()
        with pytest.raises(ImproperlyConfigured):
            throttle.scope = None
            throttle.get_rate()

    def test_throttle_raises_error_if_rate_is_missing(self):
        SimpleRateThrottle.scope = 'invalid scope'
        with pytest.raises(ImproperlyConfigured):
            SimpleRateThrottle()

    def test_parse_rate_returns_tuple_with_none_if_rate_not_provided(self):
        rate = SimpleRateThrottle().parse_rate(None)
        assert rate == (None, None)

    def test_allow_request_returns_true_if_rate_is_none(self, loop):
        assert loop.run_until_complete(SimpleRateThrottle().allow_request(request={}, view={})) is True

    def test_get_cache_key_raises_not_implemented_error(self, loop):
        with pytest.raises(NotImplementedError):
            loop.run_until_complete(SimpleRateThrottle().get_cache_key({}, {}))

    def test_allow_request_returns_true_if_key_is_none(self, loop, monkeypatch):
        throttle = SimpleRateThrottle()
        throttle.rate = 'some rate'

        async def gck(*args):
            return None

        monkeypatch.setattr(throttle, 'get_cache_key', gck)

        assert loop.run_until_complete(throttle.allow_request(request={}, view={})) is True

    def test_wait_returns_correct_waiting_time_without_history(self):
        throttle = SimpleRateThrottle()
        throttle.num_requests = 1
        throttle.duration = 60
        throttle.history = []
        waiting_time = throttle.wait()
        assert isinstance(waiting_time, float)
        assert waiting_time == 30.0

    def test_wait_returns_none_if_there_are_no_available_requests(self):
        throttle = SimpleRateThrottle()
        throttle.num_requests = 1
        throttle.duration = 60
        throttle.now = throttle.timer()
        throttle.history = [throttle.timer() for _ in range(3)]
        assert throttle.wait() is None


class TestAnonRateThrottle:

    @pytest.fixture(autouse=True)
    def setup(self):
        self.throttle = AnonRateThrottle()

    def test_authenticated_user_not_affected(self, loop):
        user_id = 1
        user = User(id=user_id, email="test@test.test", level=UserLevels.ACTIVE, is_authenticated=True)

        class MockRequest:
            @property
            async def user(self):
                return user

        mock_request = MockRequest()
        assert loop.run_until_complete(self.throttle.get_cache_key(mock_request, view={})) is None

    def test_get_cache_key_returns_correct_value(self, loop):
        user_id = 1
        user = User(id=user_id, email="test@test.test", level=UserLevels.ACTIVE, is_authenticated=False)

        class MockRequest:
            ip = None
            headers = {}

            @property
            async def user(self):
                return user

        mock_request = MockRequest()

        cache_key = loop.run_until_complete(self.throttle.get_cache_key(mock_request, view={}))
        assert cache_key == 'throttle_anon_None'
