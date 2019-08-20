import pytest

from multidict import CIMultiDict

from insanic.conf import settings
from insanic.request import Request


def ip_generator(count, reverse=False):
    ips = [f"{i}.{i}.{i}.{i}" for i in range(1, 1 + count)]
    if reverse:
        ips = reversed(ips)
    return ", ".join(ips)


class TestInsanicRequest:

    @pytest.mark.parametrize(
        "headers,expected", (
                ({}, ""),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(1)}, "1.1.1.1"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(2)}, "1.1.1.1"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(2, True)}, "2.2.2.2"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(3)}, "1.1.1.1"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(3, True)}, "3.3.3.3")

        )
    )
    def test_remote_addr(self, headers, expected):
        headers = CIMultiDict(headers)

        request = Request(b"/", headers, None, 'GET', "", app=object())

        assert request.remote_addr == expected

    @pytest.fixture()
    def set_proxies_count(self, monkeypatch):
        monkeypatch.setattr(settings, 'PROXIES_COUNT', 1, raising=False)

    @pytest.mark.parametrize(
        "headers,expected", (
                ({}, ""),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(1)}, "1.1.1.1"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(2)}, "2.2.2.2"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(2, True)}, "1.1.1.1"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(3)}, "3.3.3.3"),
                ({settings.FORWARDED_FOR_HEADER: ip_generator(3, True)}, "1.1.1.1")

        )
    )
    def test_remote_addr_with_proxies(self, set_proxies_count, headers, expected):
        headers = CIMultiDict(headers)

        request = Request(b"/", headers, None, 'GET', "", app=object())

        assert request.remote_addr == expected
