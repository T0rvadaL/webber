import asyncio
import atexit
import random
import signal
import time
import typing
import httpx

from ._proxy_pool import ProxyPool
from ._proxy import Proxy
from ._client import Client
from ._exceptions import InternalError


class ClientManager:
    _MIN_CLIENT_REQUESTS = 4

    def __init__(self, proxies: typing.Iterable[Proxy] | typing.Mapping[Proxy, bool]):
        atexit.register(self._run_cleanup)
        signal.signal(signal.SIGINT, self._on_sigint)
        self._proxy_pool = ProxyPool(proxies)
        self._clients = {}
        self._max_client_requests = 21
        self._last_requested = 0

    @property
    def proxy_pool(self) -> ProxyPool:
        return self._proxy_pool

    @property
    def clients(self) -> dict[Client, dict[str, int]]:
        return self._clients

    async def request(
            self,
            url: str,
            headers: httpx._types.HeaderTypes,
            event_hooks: typing.Mapping[str, list[httpx._client.EventHook]] | None = None,
            http2: bool | None = True,
    ) -> httpx.Response:
        client = self._get_client(http2)
        self._prepare_client(client)
        status_code = None
        try:
            response = await client.get(url, headers=headers, event_hooks=event_hooks)
            status_code = response.status_code
            self._handle_status(client, response.status_code)
            return response

        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            self._handle_status(client, status_code)
            raise e

        finally:
            if not (client in self._clients or client.pending_requests):
                await client.aclose()
                self._proxy_pool.free(client.proxy, status_code)

    def _get_client(self, http2: bool) -> Client:
        client = next(iter(self._clients), None)
        if client is None or self._on_timeout(client) or client.http2 is not http2:
            client = self._create_client(http2)

        return client

    def _create_client(self, http2: bool) -> Client:
        proxy = self._proxy_pool.get_proxy()
        client = Client(proxy=proxy, http2=http2)
        requests_allowed = random.randint(self._MIN_CLIENT_REQUESTS, self._max_client_requests)
        self._clients[client] = {"requests_allowed": requests_allowed, "requests_left": requests_allowed}
        return client

    def _prepare_client(self, client):
        client_data = self._clients.pop(client)
        if client_data["requests_left"] > 1:
            client_data["requests_left"] -= 1
            self._clients[client] = client_data
        else:
            assert client_data["requests_left"] == 1

    def _handle_429(self, client_data: dict[str, int]) -> None:
        self._max_client_requests = client_data["allowed_requests"] - 1
        min_acceptable_range = 4
        if self._max_client_requests < self._MIN_CLIENT_REQUESTS + min_acceptable_range:
            raise InternalError("After continuous client delay adjustments, server is still rate limiting")
        for client in list(self._clients):
            if self._clients[client]["allowed_requests"] > self._max_client_requests:
                del self._clients[client]

    def _handle_status(self, client: Client, status_code: int):
        if client in self._clients and 400 <= status_code < 500:
            client_data = self._clients.pop(client)
            if status_code == 429:
                self._handle_429(client_data)

    async def _cleanup(self):
        for client in self._clients:
            await client.aclose()
            self._proxy_pool.free(client)

    def _run_cleanup(self):
        asyncio.run(self._cleanup())

    def _on_sigint(self, sig, frame):
        self._run_cleanup()
        raise SystemExit(0)

    @staticmethod
    def _on_timeout(client: Client) -> bool:
        client_delay = 1.2
        elapsed = time.time() - client.last_requested
        return client_delay < elapsed

