import httpx
import pytest

from collections import deque

import respx

from .._proxy_pool import ProxyPool
from .._exceptions import ProxiesUnavailable, ProxiesExhausted


def test_valid_initialization(proxy_pool_3):
    for pool in [
        proxy_pool_3,
        ProxyPool(tuple(proxy_pool_3.proxies_remaining)),
        ProxyPool(set(proxy_pool_3.proxies_remaining)),
        ProxyPool(deque(proxy_pool_3.proxies_remaining))
    ]:
        assert len(pool.proxies_remaining) == 3
        assert all(not failed_last for failed_last in pool.proxies_remaining.values())


@pytest.mark.parametrize("proxies", [None, [], {}, set(), deque()])
def test_invalid_initialization(proxies):
    exception = TypeError if proxies is None else ValueError
    with pytest.raises(exception):
        ProxyPool(proxies)


def test_rotation_when_alternatively_getting_freeing(proxy_pool_3):
    proxy1 = proxy_pool_3.get()
    proxy_pool_3.free(proxy1)
    proxy2 = proxy_pool_3.get()
    assert proxy1 != proxy2
    proxy_pool_3.free(proxy2)
    proxy3 = proxy_pool_3.get()
    assert proxy1 != proxy2 != proxy3
    assert proxy1 == proxy_pool_3.get()


def test_rotation_follows_freeing_order(proxy_pool_3):
    proxy1 = proxy_pool_3.get()
    proxy2 = proxy_pool_3.get()
    proxy3 = proxy_pool_3.get()
    assert proxy1 != proxy2 != proxy3
    proxy_pool_3.free(proxy2)
    proxy_pool_3.free(proxy1)
    proxy_pool_3.free(proxy3)
    assert proxy2 == proxy_pool_3.get()
    assert proxy1 == proxy_pool_3.get()


def test_raises_proxies_unavailable_and_sets_event_when_available(proxies_3):
    pool = ProxyPool(proxies_3)
    for _ in proxies_3:
        pool.get()
    with pytest.raises(ProxiesUnavailable) as exc_info:
        pool.get()

    assert not exc_info.value.proxies_available_event.is_set()
    pool.free(proxies_3[0])
    assert exc_info.value.proxies_available_event.is_set()


def test_raises_proxies_exhausted(proxy_u1a1):
    pool = ProxyPool([proxy_u1a1], 0)
    pool.remove(proxy_u1a1)
    with pytest.raises(ProxiesExhausted):
        pool.get()


def test_proxies_bad_response(proxy_pool_3):
    proxy1 = proxy_pool_3.get()
    proxy2 = proxy_pool_3.get()
    proxy3 = proxy_pool_3.get()

    proxy_pool_3.free(proxy1, 403)
    proxy_pool_3.free(proxy2, 203)
    proxy_pool_3.free(proxy3, 404)

    for _ in range(len(proxy_pool_3)):
        proxy_pool_3.get()

    proxy_pool_3.free(proxy1, 200)
    proxy_pool_3.free(proxy2, 502)
    proxy_pool_3.free(proxy3, 429)

    assert not proxy_pool_3.proxies_remaining[proxy1]
    assert proxy_pool_3.proxies_remaining[proxy2]
    assert proxy3 not in proxy_pool_3


def test_add(proxies_3):
    pool = ProxyPool([proxies_3[0]])
    assert not pool.add(proxies_3[0])
    assert len(pool) == 1
    assert pool.add(proxies_3[1])
    assert len(pool) == 2


def test_remove(proxy_u1a1):
    pool = ProxyPool([proxy_u1a1])
    pool.remove(proxy_u1a1)
    with pytest.raises(ValueError):
        pool.remove(proxy_u1a1)


def test_len(proxy_pool_3):
    assert len(proxy_pool_3) == 3


def test_contains(proxies_3):
    pool = ProxyPool([proxies_3[0]])
    assert proxies_3[0] in pool
    assert proxies_3[1] not in pool


def test_bool(proxy_u1a1):
    pool = ProxyPool([proxy_u1a1])
    assert pool
    pool.remove(proxy_u1a1)
    assert not pool



