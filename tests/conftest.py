import pytest

from .._proxy import Proxy
from .._proxy_pool import ProxyPool
from .._client_manager import ClientManager
from .._host_manager import HostManager


@pytest.fixture
def user_agent1():
    return {
        "User-Agent": "foo"
    }


@pytest.fixture
def user_agent2():
    return {
        "User-Agent": "bar",
        "Sec-Ch-Ua": "baz"
    }


@pytest.fixture
def proxy_u1a1(user_agent1):
    return Proxy("https://example.com", user_agent1)


@pytest.fixture
def proxy_u1a2(user_agent2):
    return Proxy("https://example.com", user_agent2)


@pytest.fixture
def proxy_u2a1(user_agent1):
    return Proxy("https://not.example.com", user_agent1)


@pytest.fixture
def proxy_pool():
    return ProxyPool([
        Proxy("https://example1.com", {"User-Agent": "foo"}),
        Proxy("https://example2.com", {"User-Agent": "bar"}),
        Proxy("https://example3.com", {"User-Agent": "bar"}),
    ])


@pytest.fixture
def proxy_pool_true():
    return ProxyPool({
        Proxy("https://example1.com", {"User-Agent": "foo"}): True,
        Proxy("https://example2.com", {"User-Agent": "bar"}): True,
        Proxy("https://example3.com", {"User-Agent": "bar"}): True
    })


@pytest.fixture
def client_manager(proxy_pool):
    return ClientManager(proxy_pool.available_proxies)

