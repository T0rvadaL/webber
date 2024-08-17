import pytest

from collections import deque

from .._proxy_pool import ProxyPool
from .._exceptions import ProxiesUnavailable, ProxiesExhausted


def test_initialization(proxy_pool, proxy_pool_true):
    with pytest.raises(ValueError):
        ProxyPool(None)
        ProxyPool([])
        ProxyPool({})

    for pool in [
        proxy_pool,
        ProxyPool(tuple(proxy_pool.available_proxies)),
        ProxyPool(set(proxy_pool.available_proxies)),
        ProxyPool(deque(proxy_pool.available_proxies))
    ]:
        assert not pool.proxies_in_use
        assert len(pool.available_proxies) == 3
        assert all(not failed_last for failed_last in pool.available_proxies.values())

    assert not proxy_pool_true.proxies_in_use
    assert len(proxy_pool_true.available_proxies) == 3
    assert all(failed_last for failed_last in proxy_pool_true.available_proxies.values())


def test_rotation(proxy_pool):
    proxy1 = proxy_pool.get_proxy()
    assert proxy1 not in proxy_pool.available_proxies
    assert proxy1 in proxy_pool.proxies_in_use
    assert len(proxy_pool.available_proxies) == 2
    proxy_pool.free(proxy1)
    assert proxy_pool.available_proxies.popitem()[0] == proxy1


def test_raises_proxies_unavailable_and_sets_event_when_available(proxy_pool):
    proxies = list(proxy_pool.available_proxies)
    for _ in proxies:
        proxy_pool.get_proxy()

    with pytest.raises(ProxiesUnavailable) as exc_info:
        proxy_pool.get_proxy()

    assert not exc_info.value.proxies_available_event.is_set()
    proxy_pool.free(proxies[0])
    assert exc_info.value.proxies_available_event.is_set()


def test_raises_proxies_exhausted(proxy_pool):
    proxy_pool.available_proxies.clear()
    with pytest.raises(ProxiesExhausted):
        proxy_pool.get_proxy()


def test_raises_value_error_when_freeing_twice_consecutively(proxy_pool):
    proxy = proxy_pool.get_proxy()
    proxy_pool.free(proxy)
    with pytest.raises(ValueError):
        proxy_pool.free(proxy)


def test_proxies_removal(proxy_pool):
    proxy1 = proxy_pool.get_proxy()
    proxy2 = proxy_pool.get_proxy()
    proxy3 = proxy_pool.get_proxy()

    proxy_pool.free(proxy1, 403)
    proxy_pool.free(proxy2, 500)
    proxy_pool.free(proxy3, 404)

    available_proxies = proxy_pool.available_proxies
    assert available_proxies[proxy1]
    assert not available_proxies[proxy2]
    assert available_proxies[proxy3]

    for _ in range(len(available_proxies)):
        proxy_pool.get_proxy()

    proxy_pool.free(proxy1, 200)
    proxy_pool.free(proxy2, 403)
    proxy_pool.free(proxy3, 429)

    assert not available_proxies[proxy1]
    assert available_proxies[proxy2]
    assert proxy3 not in [available_proxies, proxy_pool.proxies_in_use]




