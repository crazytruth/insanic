import hashlib
import io

from httptools import parse_url
from pprint import pformat


from sanic.request import Request as SanicRequest, RequestParameters

from insanic import exceptions
from insanic.conf import settings
from insanic.models import AnonymousUser
from insanic.utils import force_str
from insanic.utils.mediatypes import parse_header, HTTP_HEADER_ENCODING


def is_form_media_type(media_type):
    """
    Return True if the media type is a valid form media type.
    """
    base_media_type, params = parse_header(media_type.encode(HTTP_HEADER_ENCODING))
    return (base_media_type == 'application/x-www-form-urlencoded' or
            base_media_type == 'multipart/form-data')


class Empty:
    """
    Placeholder for unset attributes.
    Cannot use `None`, as that may be a valid value.
    """
    pass

def _hasattr(obj, name):
    return not getattr(obj, name) is Empty

class Request(SanicRequest):
    """
    Wrapper allowing to enhance a standard `HttpRequest` instance.

    Kwargs:
        - request(HttpRequest). The original request instance.
        - parsers_classes(list/tuple). The parsers to use for parsing the
          request content.
        - authentication_classes(list/tuple). The authentications used to try
          authenticating the request's user.
    """

    __slots__ = (
        'app', 'headers', 'version', 'method', '_cookies', 'transport',
        'body',
        'parsed_json', 'parsed_args', 'parsed_form', 'parsed_files',
        '_ip',
        'authenticators', '_data', '_files', '_full_data', '_content_type',
        '_stream', '_authenticator', '_user', '_auth', '_is_service', '_service_hosts', '_parsed_url', 'uri_template'
    )

    def __init__(self, url_bytes, headers, version, method, transport,
                 authenticators=None):

        super().__init__(url_bytes, headers, version, method, transport)
        # self._request = request
        self._parsed_url = parse_url(url_bytes)

        self._data = Empty
        self._files = Empty
        self._full_data = Empty
        self._content_type = Empty
        self._stream = Empty
        self._is_service = Empty
        self._service_hosts = Empty

        self.authenticators = authenticators or ()

    @property
    def content_type(self):
        meta = self.headers
        return meta.get('content-type', 'application/json')

    @property
    def stream(self):
        """
        Returns an object that may be used to stream the request content.
        """
        if not _hasattr(self, '_stream'):
            self._load_stream()
        return self._stream

    @property
    def query_params(self):
        """
        More semantically correct name for request.GET.
        """
        return self.args

    @property
    def data(self):
        if not _hasattr(self, '_full_data'):
            self._load_data_and_files()
        return self._full_data

    @property
    def is_service(self):

        if not _hasattr(self, "_is_service"):
            if "mmt-token" not in self.headers:
                self._is_service = False
            elif not _hasattr(self, '_service_hosts'):
                self._service_hosts = {c.get('externalserviceport'): s for s, c in settings.SERVICES.items()}
                try:
                    _port = int(self.headers.get('host').split(':')[-1])
                except ValueError:
                    _port = 80
                m = hashlib.sha256()
                m.update('mmt-server-{0}'.format(self._service_hosts.get(_port, '')).encode())
                m.update(settings.WEB_SECRET_KEY.encode())
                self._is_service = m.hexdigest() == self.headers.get('mmt-token')
            else:
                self._is_service = False
        return self._is_service

    @property
    async def user(self):
        """
        Returns the user associated with the current request, as authenticated
        by the authentication classes provided to the request.
        """
        if not hasattr(self, '_user'):
            await self._authenticate()
        return self._user

    @user.setter
    def user(self, value):
        """
        Sets the user on the current request. This is necessary to maintain
        compatibility with django.contrib.auth where the user property is
        set in the login and logout functions.

        Note that we also set the user on Django's underlying `HttpRequest`
        instance, ensuring that it is available to any middleware in the stack.
        """
        self._user = value

    @property
    def auth(self):
        """
        Returns any non-user authentication information associated with the
        request, such as an authentication token.
        """
        if not hasattr(self, '_auth'):
            self._authenticate()
        return self._auth

    @auth.setter
    def auth(self, value):
        """
        Sets any non-user authentication information associated with the
        request, such as an authentication token.
        """
        self._auth = value

    @property
    def successful_authenticator(self):
        """
        Return the instance of the authentication instance class that was used
        to authenticate the request, or `None`.
        """
        if not hasattr(self, '_authenticator'):
            self._authenticate()
        return self._authenticator

    def _load_data_and_files(self):
        """
        Parses the request content into `self.data`.
        """
        if not _hasattr(self, '_data'):
            self._data, self._files = self._parse()
            if self._files:
                self._full_data = RequestParameters(self._data.copy())
                self._full_data.update(self._files)
            else:
                self._full_data = self._data

    def _load_stream(self):
        """
        Return the content body of the request, as a stream.
        """
        meta = self.headers
        try:
            content_length = int(
                meta.get('content-length', 0)
            )
        except (ValueError, TypeError):
            content_length = 0

        if content_length == 0:
            self._stream = None
        # elif not self._request._read_started:
        #     self._stream = self._request
        else:
            self._stream = io.BytesIO(self.body)

    def _supports_form_parsing(self):
        """
        Return True if this requests supports parsing form data.
        """
        form_media = (
            'application/x-www-form-urlencoded',
            'multipart/form-data'
        )
        return any([parser.media_type in form_media for parser in self.parsers])

    def _parse(self):
        """
        Parse the request content, returning a two-tuple of (data, files)

        May raise an `UnsupportedMediaType`, or `ParseError` exception.
        """
        media_type = self.content_type

        if media_type.startswith("application/json"):
            return self.json, self.files
        elif media_type.startswith('application/x-www-form-urlencoded') or media_type.startswith('multipart/form-data'):
            return self.form, self.files
        else:
            raise exceptions.UnsupportedMediaType(media_type)

    async def _authenticate(self):
        """
        Attempt to authenticate the request using each authentication instance
        in turn.
        Returns a three-tuple of (authenticator, user, authtoken).
        """
        for authenticator in self.authenticators:
            try:
                user_auth_tuple = await authenticator.authenticate(self)
            except exceptions.APIException:
                self._not_authenticated()
                raise

            if user_auth_tuple is not None:
                self._authenticator = authenticator
                # self.user_auth = user_auth_tuple
                self.user, self.auth = user_auth_tuple
                return

        self._not_authenticated()

    def _not_authenticated(self):
        """
        Set authenticator, user & authtoken representing an unauthenticated request.

        Defaults are None, AnonymousUser & None.
        """
        self._authenticator = None
        self.user = AnonymousUser()
        self.auth = None

    @property
    def POST(self):
        # Ensure that request.POST uses our request parsing.
        if not _hasattr(self, '_data'):
            self._load_data_and_files()
        if is_form_media_type(self.content_type):
            return self._data
        return {}

    @property
    def FILES(self):
        # Leave this one alone for backwards compat with Django's request.FILES
        # Different from the other two cases, which are not valid property
        # names on the WSGIRequest class.
        if not _hasattr(self, '_files'):
            self._load_data_and_files()
        return self._files


def build_request_repr(request, path_override=None, GET_override=None,
                       POST_override=None, COOKIES_override=None,
                       META_override=None):
    """
    Builds and returns the request's representation string. The request's
    attributes may be overridden by pre-processed values.
    """
    # Since this is called as part of error handling, we need to be very
    # robust against potentially malformed input.
    try:
        get = (pformat(GET_override)
               if GET_override is not None
               else pformat(request.GET))
    except Exception:
        get = '<could not parse>'

    try:
        post = (pformat(POST_override)
                if POST_override is not None
                else pformat(request.data))
    except Exception:
        post = '<could not parse>'

    try:
        cookies = (pformat(COOKIES_override)
                   if COOKIES_override is not None
                   else pformat(request.cookies))
    except Exception:
        cookies = '<could not parse>'
    try:
        meta = (pformat(META_override)
                if META_override is not None
                else pformat(request.headers))
    except Exception:
        meta = '<could not parse>'

    try:
        query_params = pformat(request.args)
    except Exception:
        query_params = '<could not parse>'

    path = path_override if path_override is not None else request.path
    return force_str('<%s\npath:%s,\nGET:%s,\nPOST:%s,\nCOOKIES:%s,\nMETA:%s,\nQUERY_PARAMS:%s>' %
                     (request.__class__.__name__,
                      path,
                      str(get),
                      str(post),
                      str(cookies),
                      str(meta),
                      str(query_params)))

