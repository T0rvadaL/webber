from __future__ import annotations
import json
import math
import typing
import httpx
import os
import ua_generator
import validators

from ._host_manager import HostManager


class Webber:
    def __init__(
            self,
            non_ua_proxies: list[str] | tuple[str, ...] | set[str] | None = None,
            ua_proxies_path: str | None = None,
            use_proxies: bool = True
    ) -> None:
        if non_ua_proxies is not None:
            if not use_proxies:
                raise ValueError("use_proxies is set to False, but proxies were passed.")
            if ua_proxies_path is None:
                raise ValueError("non_ua_proxies were passed, but ua_proxies_path is missing.")
            for proxy in non_ua_proxies:
                if not validators.url(proxy):
                    proxy = proxy.replace("\n", "\\n")
                    raise ValueError(f"proxy: {proxy} is not a valid url.")

            if os.path.isfile(ua_proxies_path):
                os.replace(ua_proxies_path, ua_proxies_path + ".backup")
            with open(ua_proxies_path, "w") as f:
                self.proxies = {proxy: self._generate_user_agent() for proxy in non_ua_proxies}
                json.dump(self.proxies, f)

        elif ua_proxies_path is not None:
            if not use_proxies:
                raise ValueError("use_proxies is set to False, but proxies were passed.")

            with open(ua_proxies_path) as file:
                self.proxies = json.load(file)

        self._hosts = {}

    async def get(
            self,
            url: str,
            headers: httpx._types.HeaderTypes,
            retries: dict[int | Exception, int] | None = None,
            event_hooks: typing.Mapping[str, list[httpx._client.EventHook]] | None = None,
            http2: bool | None = True
    ) -> None:
        if retries is None:
            retries = {
                403: 5,
                429: 2,
                503: 5,
                httpx.ReadTimeout: 1,
                httpx.ConnectTimeout: math.inf,
                httpx.ConnectError: math.inf,
                httpx.ProxyError: math.inf,
            }

        host_name = httpx.URL(url).host
        host = self._hosts.setdefault(host_name, HostManager(self.proxies))
        response = await host.get(url, headers, event_hooks, http2)

    @staticmethod
    def _generate_user_agent():
        return ua_generator.generate(platform=("windows", "macos"),
                                     browser=("chrome", "edge", "firefox", "safari")
                                     ).headers.get()
