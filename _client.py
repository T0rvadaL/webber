import time
import typing
import warnings

from httpx import AsyncClient, URL, Response, TooManyRedirects
from httpx._client import EventHook, UseClientDefault, USE_CLIENT_DEFAULT
from httpx._config import DEFAULT_MAX_REDIRECTS, Timeout
from httpx._types import AuthTypes, QueryParamTypes, HeaderTypes, CookieTypes, TimeoutTypes, \
    RequestExtensions, RequestContent, RequestData, RequestFiles

from ._proxy import Proxy
from ._request import Request


class Client(AsyncClient):
    def __init__(
            self,
            *,
            proxy: Proxy | None = None,
            http2: bool = False,
            follow_redirects: bool = False,
            max_redirects: int = DEFAULT_MAX_REDIRECTS,
            event_hooks: (typing.Mapping[str, list[EventHook]]) | None = None,
    ) -> None:
        super().__init__(
            http2=http2,
            proxy=proxy.url,
            follow_redirects=follow_redirects,
            max_redirects=max_redirects,
            event_hooks=event_hooks,
        )

        self._pending_requests = 0
        self._last_requested = 0
        self._proxy = proxy

    @property
    def pending_requests(self) -> int:
        return self._pending_requests

    @property
    def last_requested(self) -> int:
        return self._last_requested

    @property
    def proxy(self) -> Proxy | None:
        return self._proxy

    def build_request(
            self,
            method: str,
            url: URL | str,
            *,
            content: RequestContent | None = None,
            data: RequestData | None = None,
            files: RequestFiles | None = None,
            json: typing.Any | None = None,
            params: QueryParamTypes | None = None,
            headers: HeaderTypes | None = None,
            cookies: CookieTypes | None = None,
            timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
            extensions: RequestExtensions | None = None,
            event_hooks: (typing.Mapping[str, list[EventHook]]) | None = None
    ) -> Request:
        """
        Build and return a request instance.

        * The `params`, `headers` and `cookies` arguments
        are merged with any values set on the client.
        * The `url` argument is merged with any `base_url` set on the client.

        See also: [Request instances][0]

        [0]: /advanced/clients/#request-instances
        """
        url = self._merge_url(url)
        headers = self._merge_headers(headers)
        headers.update(self.proxy.user_agent)  # Added
        cookies = self._merge_cookies(cookies)
        params = self._merge_queryparams(params)
        extensions = {} if extensions is None else extensions
        if "timeout" not in extensions:
            timeout = (
                self.timeout
                if isinstance(timeout, UseClientDefault)
                else Timeout(timeout)
            )
            extensions = dict(**extensions, timeout=timeout.as_dict())
        if event_hooks is not None:
            _event_hooks = {
                "request": list(event_hooks.get("request", [])),
                "response": list(event_hooks.get("response", [])),
            }
        else:
            _event_hooks = self._event_hooks

        return Request(
            method,
            url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            extensions=extensions,
            event_hooks=_event_hooks,
        )

    async def request(
            self,
            method: str,
            url: URL | str,
            *,
            content: RequestContent | None = None,
            data: RequestData | None = None,
            files: RequestFiles | None = None,
            json: typing.Any | None = None,
            params: QueryParamTypes | None = None,
            headers: HeaderTypes | None = None,
            cookies: CookieTypes | None = None,
            auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
            follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
            timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
            extensions: RequestExtensions | None = None,
            event_hooks: (typing.Mapping[str, list[EventHook]]) | None = None

    ) -> Response:
        """
        Build and send a request.

        Equivalent to:

        ```python
        request = client.build_request(...)
        response = await client.send(request, ...)
        ```

        See `AsyncClient.build_request()`, `AsyncClient.send()`
        and [Merging of configuration][0] for how the various parameters
        are merged with client-level configuration.

        [0]: /advanced/clients/#merging-of-configuration
        """

        if cookies is not None:  # pragma: no cover
            message = (
                "Setting per-request cookies=<...> is being deprecated, because "
                "the expected behaviour on cookie persistence is ambiguous. Set "
                "cookies directly on the client instance instead."
            )
            warnings.warn(message, DeprecationWarning)

        request = self.build_request(
            method=method,
            url=url,
            content=content,
            data=data,
            files=files,
            json=json,
            params=params,
            headers=headers,
            cookies=cookies,
            timeout=timeout,
            extensions=extensions,
            event_hooks=event_hooks,
        )
        return await self.send(request, auth=auth, follow_redirects=follow_redirects)

    async def get(
            self,
            url: URL | str,
            *,
            params: QueryParamTypes | None = None,
            headers: HeaderTypes | None = None,
            cookies: CookieTypes | None = None,
            auth: AuthTypes | UseClientDefault | None = USE_CLIENT_DEFAULT,
            follow_redirects: bool | UseClientDefault = USE_CLIENT_DEFAULT,
            timeout: TimeoutTypes | UseClientDefault = USE_CLIENT_DEFAULT,
            extensions: RequestExtensions | None = None,
            event_hooks: (typing.Mapping[str, list[EventHook]]) | None = None
    ) -> Response:
        try:
            return await self.request(
                "GET",
                url,
                params=params,
                headers=headers,
                cookies=cookies,
                auth=auth,
                follow_redirects=follow_redirects,
                timeout=timeout,
                extensions=extensions,
                event_hooks=event_hooks
            )
        finally:
            self._pending_requests -= 1
            if self._pending_requests < 0:
                raise RuntimeError("INTERNAL ERROR. Client has negative number of pending requests.")

    async def _send_handling_redirects(
            self,
            request: Request,
            follow_redirects: bool,
            history: list[Response],
    ) -> Response:
        while True:
            if len(history) > self.max_redirects:
                raise TooManyRedirects(
                    "Exceeded maximum allowed redirects.", request=request
                )

            for hook in request.event_hooks["request"]:  # Changed
                await hook(request)

            self._last_requested = time.time()  # Added
            self._pending_requests += 1     # Added

            response = await self._send_single_request(request)

            try:
                for hook in request.event_hooks["response"]:  # Changed
                    await hook(response)

                response.history = list(history)

                if not response.has_redirect_location:
                    return response

                request = self._build_redirect_request(request, response)
                history = history + [response]

                if follow_redirects:
                    await response.aread()
                else:
                    response.next_request = request
                    return response

            except BaseException as exc:
                await response.aclose()
                raise exc
