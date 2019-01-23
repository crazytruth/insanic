import aiotask_context
import ujson as json
import time
import uuid

from cgi import parse_header
from multidict import CIMultiDict
from pprint import pformat
from urllib.parse import parse_qs

from sanic.exceptions import InvalidUsage
from sanic.request import Request as SanicRequest, RequestParameters, File

from insanic import exceptions
from insanic.conf import settings
from insanic.functional import empty
from insanic.log import logger, error_logger
from insanic.utils import force_str


DEFAULT_HTTP_CONTENT_TYPE = "application/octet-stream"


def _hasattr(obj, name):
    return not getattr(obj, name) is empty


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
        'body', 'parsed_json', 'parsed_args', 'parsed_form', 'parsed_files',
        '_ip', '_parsed_url', 'uri_template', 'stream', '_remote_addr',
        'authenticators', 'parsed_data',
        '_stream', '_authenticator', '_user', '_auth',
        '_request_time', '_segment', '_service', '_id', 'grpc_request_message'
    )

    def __init__(self, url_bytes, headers, version, method, transport,
                 authenticators=None):

        super().__init__(url_bytes, headers, version, method, transport)

        self._request_time = int(time.time() * 1000000)
        self._id = empty
        self.parsed_data = empty
        self.authenticators = authenticators or ()
        self.grpc_request_message = empty

    @classmethod
    def from_protobuf_message(cls, request_message, stream):

        request_headers = {k: v for k, v in request_message.headers.items()}

        req = cls(url_bytes=request_message.endpoint,
                  headers=CIMultiDict(request_headers),
                  version=2, method=request_message.method, transport=stream._stream._transport)

        req._id = request_message.request_id
        req.parsed_json = {k: json.loads(v) for k, v in request_message.body.items()}
        req.parsed_files = RequestParameters({k: [File(body=f.body, name=f.name, type="")
                                                  for f in v.f] for k, v in request_message.files.items()})
        req.grpc_request_message = request_message

        return req

    @property
    def socket(self):
        if not hasattr(self, '_socket'):
            self._get_address()
        return self._socket

    @property
    def id(self):
        if self._id is empty:
            self._id = self.headers.get(settings.REQUEST_ID_HEADER_FIELD, f"I-{uuid.uuid4()}-{self._request_time}")
        return self._id

    @property
    def segment(self):
        return self._segment

    @segment.setter
    def segment(self, value):
        self._segment = value

    @property
    def query_params(self):
        """
        More semantically correct name for request.GET.
        """
        return self.args

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
        aiotask_context.set(settings.TASK_CONTEXT_REQUEST_USER, dict(value))

    @property
    async def service(self):
        if not hasattr(self, '_service'):
            await self._authenticate()
        return self._service

    @service.setter
    def service(self, value):
        self._service = value

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

    @property
    def data(self):
        if not _hasattr(self, 'parsed_data'):
            try:
                self.parsed_data = self.json
            except InvalidUsage:
                self.parsed_data = self.form
            finally:
                if self.parsed_files:
                    for k in self.parsed_files.keys():
                        v = self.parsed_files.getlist(k)
                        self.parsed_data.update({k: v})
        return self.parsed_data

    @property
    def form(self):
        if self.parsed_form is None:
            self.parsed_form = RequestParameters()
            self.parsed_files = RequestParameters()
            content_type = self.headers.get(
                'Content-Type', DEFAULT_HTTP_CONTENT_TYPE)
            content_type, parameters = parse_header(content_type)
            try:
                if content_type == 'application/x-www-form-urlencoded':
                    self.parsed_form = RequestParameters(
                        parse_qs(self.body.decode('utf-8')))
                elif content_type == 'multipart/form-data':
                    # TODO: Stream this instead of reading to/from memory
                    boundary = parameters['boundary'].encode('utf-8')
                    self.parsed_form, self.parsed_files = (
                        parse_multipart_form(self.body, boundary))
            except Exception:
                error_logger.exception("Failed when parsing form")

        return self.parsed_form

    @property
    def client_ip(self):
        return self.headers.get('x-forwarded-for', '').split(",")[0] if self.headers.get('x-forwarded-for') else None

    async def _authenticate(self):
        """
        Attempt to authenticate the request using each authentication instance
        in turn.
        Returns a three-tuple of (authenticator, user, authtoken).
        """
        for authenticator in self.authenticators:
            try:
                user_auth_tuple = await authenticator.authenticate(request=self)
            except exceptions.APIException as e:
                self._not_authenticated()
                raise

            if user_auth_tuple is not None:
                self._authenticator = authenticator
                # self.user_auth = user_auth_tuple
                self.user, self.service, self.auth = user_auth_tuple

                return

        self._not_authenticated()

    def _not_authenticated(self):
        """
        Set authenticator, user & authtoken representing an unauthenticated request.

        Defaults are None, AnonymousUser & None.
        """
        from insanic.models import AnonymousUser, AnonymousRequestService
        self._authenticator = None
        self.user = AnonymousUser
        self.service = AnonymousRequestService
        self.auth = None

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


def parse_multipart_form(body, boundary):
    """Parse a request body and returns fields and files
    :param body: bytes request body
    :param boundary: bytes multipart boundary
    :return: fields (RequestParameters), files (RequestParameters)
    """
    files = RequestParameters()
    fields = RequestParameters()

    form_parts = body.split(boundary)
    for form_part in form_parts[1:-1]:
        file_name = None
        content_type = 'text/plain'
        content_charset = 'utf-8'
        field_name = None
        line_index = 2
        line_end_index = 0
        while not line_end_index == -1:
            line_end_index = form_part.find(b'\r\n', line_index)
            form_line = form_part[line_index:line_end_index].decode('utf-8')
            line_index = line_end_index + 2

            if not form_line:
                break

            colon_index = form_line.index(':')
            form_header_field = form_line[0:colon_index].lower()
            form_header_value, form_parameters = parse_header(
                form_line[colon_index + 2:])

            if form_header_field == 'content-disposition':
                file_name = form_parameters.get('filename')
                field_name = form_parameters.get('name')
            elif form_header_field == 'content-type':
                content_type = form_header_value
                content_charset = form_parameters.get('charset', 'utf-8')

        if field_name:
            post_data = form_part[line_index:-4]
            if file_name:
                form_file = File(type=content_type,
                                 name=file_name,
                                 body=post_data)
                if field_name in files:
                    files[field_name].append(form_file)
                else:
                    files[field_name] = [form_file]
            else:
                value = post_data.decode(content_charset)
                if field_name in fields:
                    fields[field_name].append(value)
                else:
                    fields[field_name] = [value]
        else:
            logger.debug('Form-data field does not have a \'name\' parameter \
                         in the Content-Disposition header')

    return fields, files
