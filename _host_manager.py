import asyncio
import time
import typing
import httpx
import validators

from collections import deque

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
    def __init__(self, host: str, proxies: typing.Collection[Proxy] | typing.Mapping[Proxy, bool]):
        if not (validators.domain(host) or validators.ipv4(host)):
            raise ValueError(f"host: {host} is not a valid host.")
        self._client_manager = ClientManager(proxies)
        self.host = host
        self._last_requested = 0
        self._host_delay = 1.0
        self._requests_semaphore = asyncio.Semaphore(50)
        self._host_timeout_lock = asyncio.Lock()
        self._recent_response_times = deque(maxlen=100)

    async def get(
            self,
            url: str,
            headers: httpx._types.HeaderTypes,
            event_hooks: typing.Mapping[str, list[httpx._client.EventHook]] | None = None,
            http2: bool | None = True,
    ) -> httpx.Response:
        async with self._requests_semaphore:
            await self.timeout(url)
            self._last_requested = time.time()
            return await self._client_manager.request(url, headers=headers, event_hooks=event_hooks, http2=http2)

    async def timeout(self, url: str) -> None:
        async with self._host_timeout_lock:
            elapsed = time.time() - self._last_requested
            timeout = self._host_delay - elapsed

            if timeout > 0:
                print(f"Waiting {timeout} seconds before requesting {url}")
                await asyncio.sleep(timeout)
