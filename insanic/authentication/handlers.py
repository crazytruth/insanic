import jwt
import socket

from datetime import datetime
from calendar import timegm

from insanic.conf import settings
from insanic.scopes import get_my_ip


def jwt_decode_handler(token, *, verify=False, key=None, issuer=None):
    options = {
        'verify_exp': settings.JWT_AUTH['JWT_VERIFY_EXPIRATION'],
    }

    decode_kwargs = {
        "jwt": token,
        "verify": verify,
        "options": options
    }

    if verify:
        if key is None:
            raise RuntimeError("If verify is set to True, a key has to be supplied.")
        elif issuer is None:
            raise RuntimeError("If verify is set to True, issuer has to be supplied.")

        decode_kwargs.update({
            'key': key,
            'leeway': settings.JWT_AUTH['JWT_LEEWAY'],
            'audience': settings.JWT_AUTH['JWT_AUDIENCE'],
            'issuer': issuer,
            'algorithms': [settings.JWT_AUTH['JWT_ALGORITHM']]
        })

    return jwt.decode(**decode_kwargs)


def jwt_payload_handler(user, issuer):
    # username = user.email
    user_id = user.id

    payload = {
        'user_id': user_id,
        # 'email': username,
        'level': user.level,
        'iss': issuer,
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


def jwt_service_payload_handler(service):
    payload = {
        "source": settings.SERVICE_NAME,
        "aud": service.service_name,
        "source_ip": get_my_ip(),
        "destination_version": "0.0.1",
        # "user": user
    }
    return payload


def jwt_service_encode_handler(payload):
    return jwt.encode(payload, settings.SERVICE_TOKEN_KEY, settings.JWT_SERVICE_AUTH['JWT_ALGORITHM']).decode('utf-8')
