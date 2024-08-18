import httpx
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
    return Proxy("https://proxy1.com", user_agent1)

@pytest.fixture
def proxy_u1a2(user_agent2):
    return Proxy("https://proxy1.com", user_agent2)


@pytest.fixture
def proxy_u2a1(user_agent1):
    return Proxy("https://proxy2.com", user_agent1)


@pytest.fixture
def url():
    return "https://example.com"


@pytest.fixture
def url_obj(url):
    return httpx.URL(url)


@pytest.fixture
def proxies_3():
    return [Proxy(f"https://proxy{i}.com", {}) for i in range(3)]


@pytest.fixture
def proxies_1000():
    return [Proxy(f"https://proxy{i}.com", {}) for i in range(1000)]


@pytest.fixture
def proxy_pool_3(proxies_3):
    return ProxyPool(proxies_3)


def proxy_pool_1000(proxies_1000):
    return ProxyPool(proxies_1000)


@pytest.fixture
def client_manager_default(proxy_pool):
    return ClientManager(proxy_pool.available_proxies, 1, 2)

@pytest.fixture
def client_manager_2_3(proxies_3):
    return ClientManager(proxies_3, 2, 3)


@pytest.fixture
def codes_success():
    return [200, 201, 202, 203, 204, 205, 206, 207, 208, 226]

@pytest.fixture
def codes_400x_500x():
    return [400, 401, 402, 403, 404, 405, 406, 407, 408, 409, 410, 411, 412, 413, 414, 415, 416, 417, 418, 421, 422,
            423, 424, 425, 426, 428, 429, 431, 451, 500, 501, 502, 503, 504, 505, 506, 507, 508, 510, 511]


@pytest.fixture
def status_sequence_mock(request):
    status_codes = request.param
    yield next(status_codes)