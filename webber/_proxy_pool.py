import asyncio
import typing

from ._proxy import Proxy
from ._exceptions import ProxiesUnavailable, ProxiesExhausted


class ProxyPool:
    def __init__(self, proxies: typing.Collection[Proxy], max_bad_responses: int = 1):
        """
        A proxy pool with rotating proxies. The pool will not allow a proxy to be reused by another client until
        it has been freed. Proxies that get two consecutive 4xx status codes will be removed from the pool.
        A proxy pool can be shared between multiple hosts, but it is generally recommended to keep a separate pool
        for each host (but reusing the same proxies is fine).

        :param proxies: A collection of Proxy objects.
        :param max_bad_responses: The maximum number of consecutive 4xx and 5xx status codes a proxy can get before
                                  being removed from the pool. Proxies will never be removed from the pool if the
                                  value is 0
        """

        if proxies is None:
            raise TypeError("proxies must not be None.")
        elif not proxies:
            raise ValueError("proxies must not be empty.")

        self._available_proxies = dict.fromkeys(proxies, 0)
        self._proxies_in_use = {}
        self._proxies_available_event = asyncio.Event()
        self.max_bad_responses = max_bad_responses

    @property
    def proxies_remaining(self) -> dict[Proxy, int]:
        """
        Get the proxies remaining in the pool (in use ones as well).

        :return: A dictionary of proxies to the number of consecutive 4xx and 5xx responses
        """
        return self._available_proxies | self._proxies_in_use

    def get(self) -> Proxy:
        """
        Retrieve a proxy from the pool.

        This method returns the least recently used proxy from the pool. If all proxies are currently in use,
        it will raise a `ProxiesUnavailable` exception, which includes an `asyncio.Event` that will be set
        when a proxy becomes available. If all proxies have been exhausted, a `ProxiesExhausted` exception will be raised.

        :raises ProxiesUnavailable: If all proxies are in use.
        :raises ProxiesExhausted: If all proxies have been exhausted.
        :return: The least recently used proxy from the pool.
        """
        if not self._available_proxies:
            if self._proxies_in_use:
                self._proxies_available_event.clear()
                raise ProxiesUnavailable("all proxies are in use.", self._proxies_available_event)
            raise ProxiesExhausted("proxies have been exhausted.")

        proxy = next(iter(self._available_proxies))
        self._proxies_in_use[proxy] = self._available_proxies.pop(proxy)
        return proxy

    def add(self, proxy: Proxy) -> bool:
        """
        Add a proxy to the pool.

        :param proxy: The proxy to add.
        :return: True if the proxy was added, False if the proxy is already in the pool.
        """
        if proxy in self:
            return False
        else:
            self._available_proxies[proxy] = 0
            return True

    def remove(self, proxy: Proxy) -> None:
        """
        Remove a proxy from the pool.

        :param proxy:
        :raises ValueError: If the proxy is not in the pool.
        """
        if proxy in self._proxies_in_use:
            del self._proxies_in_use[proxy]
        elif proxy in self._available_proxies:
            del self._available_proxies[proxy]
        else:
            raise ValueError(f"proxy {proxy.url} is not in the pool.")

    def free(self, proxy: Proxy, last_status_code: int | None = None) -> None:
        """
        Free a proxy back to the pool.

        :param proxy: The proxy to free.
        :param last_status_code: The last status code received when using the proxy. If None, the proxy will keep its
                                 current number of consecutive bad responses.
        """
        if proxy not in self._proxies_in_use:
            return

        consecutive_bad_responses = self._proxies_in_use.pop(proxy)
        if last_status_code is not None:
            consecutive_bad_responses = consecutive_bad_responses + 1 if last_status_code >= 400 else 0
        if consecutive_bad_responses <= self.max_bad_responses:
            self._available_proxies[proxy] = consecutive_bad_responses
            self._proxies_available_event.set()

    def __len__(self) -> int:
        return len(self._available_proxies) + len(self._proxies_in_use)

    def __bool__(self) -> bool:
        return bool(self._available_proxies) or bool(self._proxies_in_use)

    def __contains__(self, proxy) -> bool:
        return proxy in self._available_proxies or proxy in self._proxies_in_use
