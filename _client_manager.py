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
from ._exceptions import AdjustmentError

# TODO: better http version handling. Either use a mapping of http versions to clients or only allow one version per ClientManager
# TODO: dependency injection - pass ProxyPool as an argument to the constructor (maybe)


class ClientManager:
    """
    A client manager that manages a pool of clients. The manager will automatically create, manage and rotate clients
    when making requests. The manager will also adjust how many requests a client can make based if rate-limiting occurs.
    Client managers are designed to be used with a single host.

    :param proxies: Either an iterable collection of Proxy objects, or a mapping where keys are Proxy objects
                        and values are booleans indicating whether the proxy failed on its last use.
    """

    def __init__(
            self, proxies: typing.Iterable[Proxy] | typing.Mapping[Proxy, bool],
            min_client_requests: int = 4,
            max_client_requests: int = 21
    ):
        if max_client_requests < min_client_requests:
            raise ValueError("max_client_requests cannot be less than min_client_requests.")
        elif min_client_requests < 1:
            raise ValueError("min_client_requests must be a positive integer.")

        atexit.register(self._run_cleanup)
        signal.signal(signal.SIGINT, self._on_sigint)
        self.client_delay = 1.2
        self._proxy_pool = ProxyPool(proxies)
        self._clients = {}
        self._min_client_requests = min_client_requests
        self._max_client_requests = max_client_requests
        self._last_requested = 0

    @property
    def proxy_pool(self) -> ProxyPool:
        return self._proxy_pool

    @property
    def last_requested(self) -> int:
        return self._last_requested

    @property
    def min_client_requests(self) -> int:
        return self._min_client_requests

    @min_client_requests.setter
    def min_client_requests(self, value: int) -> None:
        # min_client_requests must be higher than 1 for implementation reasons
        if value < 2:
            raise ValueError("min_client_requests must be a 2 or higher.")
        elif value > self._max_client_requests:
            raise ValueError(f"min_client_requests must be less than {self._max_client_requests}.")
        self._min_client_requests = value

    @property
    def max_client_requests(self) -> int:
        return self._max_client_requests

    @max_client_requests.setter
    def max_client_requests(self, value: int) -> None:
        if value < 1:
            raise ValueError("max_client_requests must be a positive integer.")
        if value < self._min_client_requests:
            raise ValueError(f"max_client_requests must be greater than {self._min_client_requests}.")
        self._max_client_requests = value

    async def request(
            self,
            url: str,
            headers: httpx._types.HeaderTypes,
            event_hooks: typing.Mapping[str, list[httpx._client.EventHook]] | None = None,
            http2: bool = True,
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
        if client is None or client.http2 is not http2 or self._calc_wait_time(client) > 0:
            client = self._create_client(http2)

        return client

    def _create_client(self, http2: bool) -> Client:
        proxy = self._proxy_pool.get()
        client = Client(proxy=proxy, http2=http2)
        requests_allowed = random.randint(self._min_client_requests, self._max_client_requests)
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
        self._max_client_requests = client_data["requests_allowed"] - client_data["requests_left"] - 1
        if self._max_client_requests < self._min_client_requests:
            raise AdjustmentError(
                f"max_client_requests has fallen below the minimum allowed value of {self._min_client_requests}."
            )

        for client in list(self._clients):
            if self._clients[client]["requests_allowed"] > self._max_client_requests:
                del self._clients[client]

    def _handle_status(self, client: Client, status_code: int):
        if client in self._clients and status_code >= 400:
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
    def _calc_wait_time(client: Client) -> float:
        client_delay = 1.2
        elapsed = time.time() - client.last_requested
        return client_delay - elapsed

