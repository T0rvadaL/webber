import typing
import httpx
import trio

from ._client_manager import ClientManager
from ._proxy import Proxy


class HostManager:
    """
    A Class that manages requests to a single host.
    The manager will automatically adjust request delays based on response times.

    :param host: The host to manage requests for.
    :param proxies: Either an iterable collection of Proxy objects, or a mapping where keys are Proxy objects
                    and values are booleans indicating whether the proxy failed on its last use.
    """
    def __init__(self, proxies: typing.Collection[Proxy] | typing.Mapping[Proxy, bool]):
        self._client_manager = ClientManager(proxies)
        self._concurrent_requests_limiter = trio.CapacityLimiter(20)

    @property
    def client_manager(self) -> ClientManager:
        return self._client_manager

    async def request(
            self,
            url: str,
            headers: httpx._types.HeaderTypes,
            event_hooks: typing.Mapping[str, list[httpx._client.EventHook]] | None = None,
            http2: bool | None = True,
    ) -> httpx.Response:
        async with self._concurrent_requests_limiter:
            return await self._client_manager.request(url, headers=headers, event_hooks=event_hooks, http2=http2)