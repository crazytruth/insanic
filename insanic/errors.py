from enum import Enum


class GlobalErrorCodes(Enum):
    # authentication errors
    authentication_credentials_missing = 90001
    invalid_authorization_header = 90002
    permission_denied = 90010

    # token related errors
    signature_expired = 90101
    signature_not_decodable = 90102
    invalid_payload = 90103
    invalid_token = 90104
    invalid_signature = 90105

    # database related
    redis_unable_to_process = 90201

    # general errors
    invalid_usage = 90301

    service_unavailable = 99503
    unknown_error = 99999

