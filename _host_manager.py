import asyncio
import json
import os
import time
import typing
import atexit
import signal
import httpx

from collections import deque

from ._client_manager import ClientManager
from ._proxy import Proxy


class HostManager:
    def __init__(self, host: str, proxies: typing.Collection[Proxy] | typing.Mapping[Proxy: bool]):
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
