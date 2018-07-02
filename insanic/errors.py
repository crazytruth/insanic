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
    invalid_access = 999110

    # user/service related
    inactive_user = 999201
    invalid_service_token = 999250

    # database related
    redis_unable_to_process = 999301

    # general errors
    invalid_usage = 999401
    not_found = 999404

    # request related errors
    method_not_allowed = 999501
    throttled = 999502

    # server related errors
    server_signature_error = 999601
    service_unavailable = 999603
    service_timeout = 999604

    error_unspecified = 999998
    unknown_error = 999999
