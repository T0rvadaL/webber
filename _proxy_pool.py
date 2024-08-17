import asyncio
import typing
import collections.abc

from ._proxy import Proxy
from ._exceptions import ProxiesUnavailable, ProxiesExhausted


class ProxyPool:
    def __init__(self, proxies: typing.Iterable[Proxy] | typing.Mapping[Proxy, bool]):
        if isinstance(proxies, collections.abc.Mapping):
            self._available_proxies = dict(proxies)
        else:
            self._available_proxies = dict.fromkeys(proxies, False)

        self._proxies_in_use = {}
        self._proxies_available_event = asyncio.Event()

    @property
    def available_proxies(self) -> dict[Proxy, bool]:
        return self._available_proxies

    @property
    def proxies_in_use(self) -> dict[Proxy, bool]:
        return self._proxies_in_use

    def get_proxy(self) -> Proxy:
        if not self._available_proxies:
            if self._proxies_in_use:
                self._proxies_available_event.clear()
                raise ProxiesUnavailable("all proxies are in use.", self._proxies_available_event)
            raise ProxiesExhausted("proxies have been exhausted.")

        proxy = next(iter(self._available_proxies))
        self._available_proxies[proxy] = None
        return proxy

    def free(self, proxy: Proxy, last_status_code: int | None = None) -> None:
        failed_last_time = self._proxies_in_use.pop(proxy)
        failed = failed_last_time if last_status_code is None else 400 <= last_status_code < 500

        if not failed or last_status_code is None or not failed_last_time:
            self._available_proxies[proxy] = failed
            self._proxies_available_event.set()
