import pytest

from dataclasses import FrozenInstanceError

from webber._proxy import Proxy


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com.."
        "https://example..com"
        "https://examplecom",
        "https:/example.com",
        "https:example.com",
        "httpsexample.com",
        "htt://example.com",
        "https.://example.com",
        "https://e..xample.com",
        "https://1.2.3.4:800"
        "https://1.2.3.4:80000"
        "https://www.1.2.3.4"

    ]
)
def test_invalid_url_raises(url, user_agent1):
    with pytest.raises(ValueError):
        Proxy(url, user_agent1)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com",
        "http://example.com",
        "https://api.example.com",
        "https://www.api.example.com",
        "https://www.api.example.com",
        "https://1.2.3.4",
        "https://1.2.3.4:8000",
    ]
)
def test_urls_are_valid(url, user_agent1):
    proxy = Proxy(url, user_agent1)
    assert proxy.url == url
    assert proxy.user_agent == user_agent1


def test_equality(proxy_u1a1, proxy_u1a2, proxy_u2a1):
    assert proxy_u1a1 == proxy_u1a2 != proxy_u2a1


def test_hash(proxy_u1a1, proxy_u1a2, proxy_u2a1):
    assert hash(proxy_u1a1) == hash(proxy_u1a2) != hash(proxy_u2a1)


def test_immutability(proxy_u1a1):
    with pytest.raises(FrozenInstanceError):
        proxy_u1a1.url = "foo"
