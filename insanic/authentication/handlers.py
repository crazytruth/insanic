from typing import Optional

import jwt

from insanic.conf import settings
from insanic.scopes import get_my_ip


def jwt_decode_handler(
    token: str,
    *,
    verify: Optional[bool] = None,
    key: Optional[str] = None,
    issuer: Optional[str] = None,
):
    options = {
        "verify_exp": settings.JWT_AUTH_VERIFY_EXPIRATION,
    }

    verify = verify or settings.JWT_AUTH_VERIFY

    decode_kwargs = {"jwt": token, "verify": verify, "options": options}

    if verify:
        if key is None:
            raise RuntimeError(
                "If verify is set to True, a key has to be supplied."
            )
        elif issuer is None:
            raise RuntimeError(
                "If verify is set to True, issuer has to be supplied."
            )

        decode_kwargs.update(
            {
                "key": key,
                "leeway": settings.JWT_AUTH_LEEWAY,
                "audience": settings.JWT_AUTH_AUDIENCE,
                "issuer": issuer,
                "algorithms": [settings.JWT_AUTH_ALGORITHM],
            }
        )

    return jwt.decode(**decode_kwargs)


def jwt_service_decode_handler(token):
    return jwt.decode(
        token,
        settings.SERVICE_TOKEN_KEY,
        settings.JWT_SERVICE_AUTH_VERIFY,
        audience=settings.SERVICE_NAME,
        algorithms=[settings.JWT_SERVICE_AUTH_ALGORITHM],
    )


def jwt_service_payload_handler(service):
    payload = {
        "source": settings.SERVICE_NAME,
        "aud": service.service_name,
        "source_ip": get_my_ip(),
    }
    return payload


def jwt_service_encode_handler(payload):
    return jwt.encode(
        payload,
        settings.SERVICE_TOKEN_KEY,
        settings.JWT_SERVICE_AUTH_ALGORITHM,
    ).decode("utf-8")
