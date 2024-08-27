import pickle
import typing
import httpx
import trio
import ua_generator

from ._host_manager import HostManager
from ._proxy import Proxy
from ._request import Request


class Webber:
    def __init__(self, ua_proxies_path: str) -> None:
        if not ua_proxies_path.endswith(".pkl"):
            raise ValueError("ua_proxies_path must be a .pkl file.")
        with open(ua_proxies_path, "rb") as f:
            self.proxies = pickle.load(f)

        self._hosts = {}

    async def get(
            self,
            url: str,
            headers: httpx._types.HeaderTypes,
            event_hooks: typing.Mapping[str, list[httpx._client.EventHook]] | None = None,
            http2: bool | None = False
    ) -> httpx.Response:
        host_name = httpx.URL(url).host
        host = self._hosts.setdefault(host_name, HostManager(self.proxies))

        retries = {
            403: 1,
            429: 1,
            503: 3,
            502: 3,
            httpx.ReadTimeout: 2,
            httpx.ProxyError: 4,
        }

        if event_hooks is not None:
            _event_hooks = {
                "request": list(event_hooks.get("request", [])),
                "response": list(event_hooks.get("response", [])),
            }
        else:
            _event_hooks = {"request": [], "response": []}

        event_hooks["request"].append(self._on_request)
        event_hooks["response"].append(self._on_response)

        while True:
            try:
                response = await host.request(url, headers, event_hooks, http2)
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                retries_left = retries.get(status, 0)
                if retries_left == 0:
                    raise e

                print(f"{url} failed with status {status}. Retrying...")

            except (httpx.ReadTimeout, httpx.ProxyError) as e:
                retries_left = retries.get(type(e), 0)
                if retries_left == 0:
                    raise e

                print(f"{url} failed with {type(e).__name__}. Retrying...")

            except (httpx.ConnectTimeout, httpx.ConnectError) as e:
                print(f"{url} failed with {type(e).__name__}. Retrying...")
                await trio.sleep(1)

    @staticmethod
    def assign_user_agents_to_proxies(proxies: typing.Collection[str], output_path) -> dict[Proxy, str]:
        ua_proxies = [Proxy(proxy, Webber._generate_user_agent()) for proxy in proxies]

        with open(output_path, "wb") as f:
            pickle.dump(ua_proxies, f)

    @staticmethod
    def _generate_user_agent():
        return ua_generator.generate(platform=("windows", "macos"),
                                     browser=("chrome", "edge", "firefox", "safari")
                                     ).headers.get()

    @staticmethod
    async def _on_request(request: Request):
        print(f"Requesting {request.url}")

    @staticmethod
    async def _on_response(response: httpx.Response):
        print(f"{response.url} succeeded.")

