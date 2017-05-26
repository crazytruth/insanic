import datetime

SECRET_KEY = ''

ADMINS = (
    ('Name', 'Email')
)

DEBUG = False

SERVER_EMAIL = "support@mymusictaste.com"
SERVER_ERROR_EMAIL = "admin@mymusictaste.com"
EMAIL_SUBJECT_PREFIX = "[MyMusicTaste]"

TWILIO_ACCOUNT_SID = ""
TWILIO_AUTH_TOKEN = ""
TWILIO_SERVICE_SID = ""

WEB_MYSQL_DATABASE = ""
WEB_MYSQL_HOST = ""
WEB_MYSQL_PORT = ""
WEB_MYSQL_USER = ""
WEB_MYSQL_PASS = ""

REDIS_HOST = ""
REDIS_PORT = None
REDIS_DB = None

JWT_AUTH = {
    'JWT_ENCODE_HANDLER':
    'rest_framework_jwt.utils.jwt_encode_handler',

    'JWT_DECODE_HANDLER':
    'rest_framework_jwt.utils.jwt_decode_handler',

    'JWT_PAYLOAD_HANDLER':
    'rest_framework_jwt.utils.jwt_payload_handler',

    'JWT_PAYLOAD_GET_USER_ID_HANDLER':
    'rest_framework_jwt.utils.jwt_get_user_id_from_payload_handler',

    'JWT_RESPONSE_PAYLOAD_HANDLER':
    'rest_framework_jwt.utils.jwt_response_payload_handler',

    'JWT_SECRET_KEY': SECRET_KEY,
    'JWT_PUBLIC_KEY': None,
    'JWT_PRIVATE_KEY': None,
    'JWT_ALGORITHM': 'HS256',
    'JWT_VERIFY': True,
    'JWT_VERIFY_EXPIRATION': True,
    'JWT_LEEWAY': 0,
    'JWT_EXPIRATION_DELTA': datetime.timedelta(days=7),
    'JWT_AUDIENCE': 'pita',
    'JWT_ISSUER': 'mmt',

    'JWT_ALLOW_REFRESH': True,
    'JWT_REFRESH_EXPIRATION_DELTA': datetime.timedelta(days=7),

    'JWT_AUTH_HEADER_PREFIX': 'MMT',
}

API_GATEWAY_SCHEME = "http"
API_GATEWAY_HOST = "localhost"

INTERNAL_IPS = ()

PICKLE_SHARED_KEY = 'm46jeEaH3Ld7o3BSfcZRZzPKjcCzW4P9fwQJpcJpsjfBWkfyxANBEvIFPY2mV05OYIB4UPycx96aosyAqIq4C4pn411dvqMElMx5'