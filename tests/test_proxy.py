import pytest

from dataclasses import FrozenInstanceError

from .._proxy import Proxy


@pytest.mark.parametrize(
    "url",
    [
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


def test_equality_and_hash(proxy1, proxy2, proxy3):
    proxy4 = Proxy(proxy2.url, proxy2.user_agent.copy())
    assert proxy1 == proxy2 == proxy4
    assert hash(proxy1) == hash(proxy2) == hash(proxy4)
    assert proxy1 != proxy3
    assert hash(proxy1) != hash(proxy3)


def test_immutability(proxy1):
    with pytest.raises(FrozenInstanceError):
        proxy1.url = "foo"
