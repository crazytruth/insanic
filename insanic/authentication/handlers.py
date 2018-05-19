import jwt
import socket

from datetime import datetime
from calendar import timegm

from insanic.conf import settings


def jwt_decode_handler(token):
    options = {
        'verify_exp': settings.JWT_AUTH['JWT_VERIFY_EXPIRATION'],
    }

    decoded = jwt.decode(token, verify=False, options=options)

    return decoded


def jwt_payload_handler(user, key):
    username = user.email
    user_id = user.id

    payload = {
        'user_id': user_id,
        'email': username,
        'level': user.level,
        'iss': key,
        'exp': datetime.utcnow() + settings.JWT_AUTH['JWT_EXPIRATION_DELTA'],
    }

    # Include original issued at time for a brand new token,
    # to allow token refresh
    if settings.JWT_AUTH['JWT_ALLOW_REFRESH']:
        payload['orig_iat'] = timegm(datetime.utcnow().utctimetuple())

    if settings.JWT_AUTH['JWT_AUDIENCE'] is not None:
        payload['aud'] = settings.JWT_AUTH['JWT_AUDIENCE']

    if settings.JWT_AUTH.get('JWT_ROLE') is not None:
        payload['rol'] = settings.JWT_AUTH['JWT_ROLE']

    return payload


def jwt_encode_handler(payload, secret, algorithm):
    return jwt.encode(
        payload,
        secret,
        algorithm
    ).decode('utf-8')


def jwt_service_decode_handler(token):
    return jwt.decode(
        token,
        settings.SERVICE_TOKEN_KEY,
        settings.JWT_SERVICE_AUTH['JWT_VERIFY'],
        audience=settings.SERVICE_NAME,
        algorithms=[settings.JWT_SERVICE_AUTH['JWT_ALGORITHM']]
    )


def jwt_service_payload_handler(service, user):
    payload = {
        "source": settings.SERVICE_NAME,
        "aud": service.service_name,
        "source_ip": socket.gethostbyname(socket.gethostname()),
        "destination_version": "0.0.1",
        "user": user
    }
    return payload


def jwt_service_encode_handler(payload):
    return jwt.encode(payload, settings.SERVICE_TOKEN_KEY, settings.JWT_SERVICE_AUTH['JWT_ALGORITHM']).decode('utf-8')
