import time
import ujson as json

from insanic.conf import settings
from insanic.connections import get_connection
from insanic.exceptions import ImproperlyConfigured

THROTTLE_CACHE = "throttle"


class BaseThrottle(object):
    """
    Rate throttling of requests.
    """

    async def allow_request(self, request, view):
        """
        Return `True` if the request should be allowed, `False` otherwise.
        """
        raise NotImplementedError('.allow_request() must be overridden')

    # def get_ident(self, request):
    #     """
    #     Identify the machine making the request by parsing HTTP_X_FORWARDED_FOR
    #     if present and number of proxies is > 0. If not use all of
    #     HTTP_X_FORWARDED_FOR if it is available, if not use REMOTE_ADDR.
    #     """
    #     xff = request.headers.get(settings.FORWARDED_FOR_HEADER)
    #     remote_addr = request.ip
    #     num_proxies = settings.PROXIES_COUNT
    #
    #     if num_proxies is not -1:
    #         if num_proxies == 0 or xff is None:
    #             return remote_addr
    #         addrs = xff.split(',')
    #         client_addr = addrs[-min(num_proxies, len(addrs))]
    #         return client_addr.strip()
    #
    #     return ''.join(xff.split()) if xff else remote_addr


    def get_ident(self, request):

        xff = request.headers.get(settings.FORWARDED_FOR_HEADER)
        remote_addr = request.remote_addr
        num_proxies = settings.PROXIES_COUNT

        if num_proxies is not -1 and remote_addr:
            return remote_addr
        return ''.join(xff.split()) if xff else remote_addr

    def wait(self):
        """
        Optionally, return a recommended number of seconds to wait before
        the next request.
        """
        return None


class SimpleRateThrottle(BaseThrottle):
    """
    A simple cache implementation, that only requires `.get_cache_key()`
    to be overridden.
    The rate (requests / seconds) is set by a `rate` attribute on the View
    class.  The attribute is a string of the form 'number_of_requests/period'.
    Period should be one of: ('s', 'sec', 'm', 'min', 'h', 'hour', 'd', 'day')
    Previous request information used for throttling is stored in the cache.
    """

    timer = time.time
    cache_format = 'throttle_%(scope)s_%(ident)s'
    scope = None
    THROTTLE_RATES = settings.THROTTLES_DEFAULT_THROTTLE_RATES

    def __init__(self):
        if not getattr(self, 'rate', None):
            self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

    async def get_cache_key(self, request, view):
        """
        Should return a unique cache-key which can be used for throttling.
        Must be overridden.
        May return `None` if the request should not be throttled.
        """
        raise NotImplementedError('.get_cache_key() must be overridden')

    def get_rate(self):
        """
        Determine the string representation of the allowed request rate.
        """
        if not getattr(self, 'scope', None):
            msg = ("You must set either `.scope` or `.rate` for '%s' throttle" %
                   self.__class__.__name__)
            raise ImproperlyConfigured(msg)

        try:
            return self.THROTTLE_RATES[self.scope]
        except KeyError:
            msg = "No default throttle rate set for '%s' scope" % self.scope
            raise ImproperlyConfigured(msg)

    def parse_rate(self, rate):
        """
        Given the request rate string, return a two tuple of:
        <allowed number of requests>, <period of time in seconds>
        """
        if rate is None:
            return (None, None)
        num, period = rate.split('/')
        num_requests = int(num)
        duration = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[period[0]]
        return (num_requests, duration)

    async def allow_request(self, request, view):
        """
        Implement the check to see if the request should be throttled.
        On success calls `throttle_success`.
        On failure calls `throttle_failure`.
        """
        if self.rate is None:
            return True

        self.key = await self.get_cache_key(request, view)
        if self.key is None:
            return True

        redis = await get_connection(THROTTLE_CACHE)
        with await redis as conn:
            history = await conn.get(self.key)
            self.history = json.loads(history) if history else []

        self.now = self.timer()

        # Drop any requests from the history which have now passed the
        # throttle duration
        while self.history and self.history[-1] <= self.now - self.duration:
            self.history.pop()
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        return await self.throttle_success()

    async def throttle_success(self):
        """
        Inserts the current request's timestamp along with the key
        into the cache.
        """
        self.history.insert(0, self.now)
        redis = await get_connection(THROTTLE_CACHE)
        with await redis as conn:
            await conn.set(self.key, json.dumps(self.history), expire=self.duration)
        return True

    def throttle_failure(self):
        """
        Called when a request to the API has failed due to throttling.
        """
        return False

    def wait(self):
        """
        Returns the recommended next request time in seconds.
        """
        if self.history:
            remaining_duration = self.duration - (self.now - self.history[-1])
        else:
            remaining_duration = self.duration

        available_requests = self.num_requests - len(self.history) + 1
        if available_requests <= 0:
            return None

        return remaining_duration / float(available_requests)


class AnonRateThrottle(SimpleRateThrottle):
    """
    Limits the rate of API calls that may be made by a anonymous users.
    The IP address of the request will be used as the unique cache key.
    """
    scope = 'anon'

    async def get_cache_key(self, request, view):
        user = await request.user
        if user.is_authenticated:
            return None  # Only throttle unauthenticated requests.

        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }


class UserRateThrottle(SimpleRateThrottle):
    """
    Limits the rate of API calls that may be made by a given user.
    The user id will be used as a unique cache key if the user is
    authenticated.  For anonymous requests, the IP address of the request will
    be used.
    """
    scope = 'user'

    async def get_cache_key(self, request, view):
        user = await request.user
        if user.is_authenticated:
            ident = user.id
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }


class ScopedRateThrottle(SimpleRateThrottle):
    """
    Limits the rate of API calls by different amounts for various parts of
    the API.  Any view that has the `throttle_scope` property set will be
    throttled.  The unique cache key will be generated by concatenating the
    user id of the request, and the scope of the view being accessed.
    """
    scope_attr = 'throttle_scope'

    def __init__(self):
        # Override the usual SimpleRateThrottle, because we can't determine
        # the rate until called by the view.
        pass

    async def allow_request(self, request, view):
        # We can only determine the scope once we're called by the view.
        self.scope = getattr(view, self.scope_attr, None)

        # If a view does not have a `throttle_scope` always allow the request
        if not self.scope:
            return True

        # Determine the allowed request rate as we normally would during
        # the `__init__` call.
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

        # We can now proceed as normal.
        return await super(ScopedRateThrottle, self).allow_request(request, view)

    async def get_cache_key(self, request, view):
        """
        If `view.throttle_scope` is not set, don't apply this throttle.
        Otherwise generate the unique cache key by concatenating the user id
        with the '.throttle_scope` property of the view.
        """
        user = await request.user
        if user.is_authenticated:
            ident = user.id
        else:
            ident = self.get_ident(request)

        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }
