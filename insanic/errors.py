from enum import Enum


class GlobalErrorCodes(Enum):
    # authentication errors
    authentication_credentials_missing = 999001
    invalid_authorization_header = 999002
    permission_denied = 999010

    # token related errors
    signature_expired = 999101
    signature_not_decodable = 999102
    invalid_payload = 999103
    invalid_token = 999104
    invalid_signature = 999105

    # database related
    redis_unable_to_process = 999201

    # general errors
    invalid_usage = 999301

    # server related errors
    server_signature_error = 999001
    service_unavailable = 999503
    service_timeout = 999504
    unknown_error = 999999
