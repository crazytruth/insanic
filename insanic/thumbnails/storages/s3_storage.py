import aiobotocore
import asyncio
import mimetypes
import posixpath
import os

from urllib.parse import urljoin, quote, urlsplit, parse_qsl


from botocore.exceptions import ClientError

from insanic.conf import settings
from insanic.thumbnails.helpers import get_random_string

class StorageFile:
    def __init__(self, name, data, mode):
        self._name = name
        self._mode = mode
        self._data = data

    @property
    def size(self):
        return self._data['ContentLength']

    async def read(self, *args, **kwargs):
        if 'r' not in self._mode:
            raise AttributeError("File was not opened in read mode.")

        stream = self._data['Body']

        image_body = chunk = await stream.read(100)

        while len(chunk) > 0:
            chunk = await stream.read(100)
            image_body += chunk



        return image_body





def safe_join(base, *paths):
    """
    A version of django.utils._os.safe_join for S3 paths.
    Joins one or more path components to the base path component
    intelligently. Returns a normalized version of the final path.
    The final path must be located inside of the base path component
    (otherwise a ValueError is raised).
    Paths outside the base path indicate a possible security
    sensitive operation.
    """
    base_path = str(base)
    base_path = base_path.rstrip('/')
    paths = [str(p) for p in paths]

    final_path = base_path
    for path in paths:
        final_path = urljoin(final_path.rstrip('/') + "/", path)

    # Ensure final_path starts with base_path and that the next character after
    # the final path is '/' (or nothing, in which case final_path must be
    # equal to base_path).
    base_path_len = len(base_path)
    if (not final_path.startswith(base_path) or
            final_path[base_path_len:base_path_len + 1] not in ('', '/')):
        raise ValueError('the joined path is located outside of the base path'
                         ' component')

    return final_path.lstrip('/')


class Storage:
    connection_response_error = ClientError
    location = ""
    default_content_type = 'application/octet-stream'
    custom_domain = settings.AWS_S3_CUSTOM_DOMAIN
    url_protocol = settings.get('AWS_S3_URL_PROTOCOL', 'http:')
    querystring_expire = settings.get('AWS_QUERYSTRING_EXPIRE', 3600)
    querystring_auth = settings.get('AWS_QUERYSTRING_AUTH', True)
    object_parameters = settings.get('AWS_S3_OBJECT_PARAMETERS', {})
    default_acl = settings.get('AWS_DEFAULT_ACL', 'public-read')
    secure_urls = settings.get('AWS_S3_SECURE_URLS', True)

    def __init__(self):
        self._bucket = None
        self._connection = None
        self._entries = {}
        self.bucket_name = settings.AWS_S3_BUCKET_NAME

        self.location = (self.location or '').lstrip('/')

        if self.secure_urls:
            self.url_protocol = 'https:'

    @property
    def entries(self):
        """
        Get the locally cached files for the bucket.
        """
        return self._entries

    @property
    async def connection(self):
        if self._connection is None:
            session = aiobotocore.get_session(loop=asyncio.get_event_loop())
            self._connection = session.create_client('s3', region_name=settings.AWS_S3_REGION,
                                                           aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                                           aws_access_key_id=settings.AWS_ACCESS_KEY_ID)
        return self._connection

    async def exists(self, name):
        name = self._normalize_name(self._clean_name(name))
        if self.entries:
            return name in self.entries

        conn = await self.connection
        try:
            await conn.head_object(Bucket=self.bucket_name, Key=name)
            return True
        except self.connection_response_error:
            return False

    def _normalize_name(self, name):
        """
        Normalizes the name so that paths like /path/to/ignored/../something.txt
        work. We check to make sure that the path pointed to is not outside
        the directory specified by the LOCATION setting.
        """
        try:
            return safe_join(self.location, name)
        except ValueError:
            raise SuspiciousOperation("Attempted access to '%s' denied." %
                                      name)

    def _clean_name(self, name):
        """
        Cleans the name so that Windows style paths work
        """
        # Normalize Windows style paths
        clean_name = posixpath.normpath(name).replace('\\', '/')

        # os.path.normpath() can strip trailing slashes so we implement
        # a workaround here.
        if name.endswith('/') and not clean_name.endswith('/'):
            # Add a trailing slash as it was stripped.
            clean_name += '/'
        return clean_name

    async def open(self, name, mode='rb'):
        """
        Retrieves the specified file from storage.
        """
        name = self._normalize_name(self._clean_name(name))

        conn = await self.connection

        try:
            s3_obj = await conn.get_object(Bucket=self.bucket_name, Key=name)
            f = StorageFile(name, s3_obj, mode)

        except self.connection_response_error as err:
            if err.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                raise IOError('File does not exist: %s' % name)
            raise  # Let it bubble up if it was some other error
        return f

    def filepath_to_uri(self, path):
        return quote(path.encode('utf-8').replace(b"\\", b"/"), safe = b"/~!*()'")


    async def url(self, name, parameters=None, expire=None):
        # Preserve the trailing slash after normalizing the path.
        # TODO: Handle force_http=not self.secure_urls like in s3boto
        name = self._normalize_name(self._clean_name(name))
        if self.custom_domain:
            return "%s//%s/%s" % (self.url_protocol,
                                  self.custom_domain, self.filepath_to_uri(name))
        if expire is None:
            expire = self.querystring_expire

        params = parameters.copy() if parameters else {}
        params['Bucket'] = self.bucket_name
        params['Key'] = name.encode('utf-8')

        conn = await self.connection

        url = conn.generate_presigned_url('get_object', Params=params, ExpiresIn=expire)
        if self.querystring_auth:
            return url
        return self._strip_signing_parameters(url)

    def _strip_signing_parameters(self, url):
        # Boto3 does not currently support generating URLs that are unsigned. Instead we
        # take the signed URLs and strip any querystring params related to signing and expiration.
        # Note that this may end up with URLs that are still invalid, especially if params are
        # passed in that only work with signed URLs, e.g. response header params.
        # The code attempts to strip all query parameters that match names of known parameters
        # from v2 and v4 signatures, regardless of the actual signature version used.
        split_url = urlsplit(url)
        qs = parse_qsl(split_url.query, keep_blank_values=True)
        blacklist = {'x-amz-algorithm', 'x-amz-credential', 'x-amz-date',
                         'x-amz-expires', 'x-amz-signedheaders', 'x-amz-signature',
                         'x-amz-security-token', 'awsaccesskeyid', 'expires', 'signature'}
        filtered_qs = ((key, val) for key, val in qs if key.lower() not in blacklist)
        # Note: Parameters that did not have a value in the original query string will have
        # an '=' sign appended to it, e.g ?foo&bar becomes ?foo=&bar=
        joined_qs = ('='.join(keyval) for keyval in filtered_qs)
        split_url = split_url._replace(query="&".join(joined_qs))
        return split_url.geturl()

    async def get_available_name(self, name):
        """
        Returns a filename that's free on the target storage system, and
        available for new content to be written to.
        """
        dir_name, file_name = os.path.split(name)
        file_root, file_ext = os.path.splitext(file_name)
        # If the filename already exists, add an underscore and a random 7
        # character alphanumeric string (before the file extension, if one
        # exists) to the filename until the generated filename doesn't exist.
        name_exists = await self.exists(name)
        while name_exists:
            # file_ext includes the dot.
            name = os.path.join(dir_name, "%s_%s%s" % (file_root, get_random_string(7), file_ext))
            name_exists = await self.exists(name)

        return name

    async def save(self, name, content):
        """
        Saves new content to the file specified by name. The content should be
        a proper File object or any python file-like object, ready to be read
        from the beginning.
        """
        # Get the proper name for the file, as it will actually be saved.
        if name is None:
            name = content.name



        name = await self.get_available_name(name)

        cleaned_name = self._clean_name(name)
        name = self._normalize_name(cleaned_name)
        parameters = self.object_parameters.copy()
        _type, encoding = mimetypes.guess_type(name)
        content_type = getattr(content, 'content_type',
                               _type or self.default_content_type)

        # setting the content_type in the key object is not enough.
        parameters.update({'ContentType': content_type})

        if encoding:
            # If the content already has a particular encoding, set it
            parameters.update({'ContentEncoding': encoding})


        parameters.update({"Bucket": self.bucket_name})
        parameters.update({"Key": name})
        parameters.update({"ACL": self.default_acl})
        parameters.update({"Body": content})

        conn = await self.connection

        await conn.put_object(**parameters)
        # '0f/67/0f67193f1a329b321b6c96f1a53806e2.png'

        # Note: In boto3, after a put, last_modified is automatically reloaded
        # the next time it is accessed; no need to specifically reload it.

        name = cleaned_name

        # Store filenames with forward slashes, even on Windows
        return str(name.replace('\\', '/'))

storage = Storage()

