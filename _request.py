import typing

import httpx
from httpx import URL
from httpx._client import EventHook
from httpx._types import QueryParamTypes, HeaderTypes, CookieTypes, RequestContent, RequestData, RequestFiles, \
    SyncByteStream, AsyncByteStream, RequestExtensions


class Request(httpx.Request):
    def __init__(
            self,
            method: str | bytes,
            url: URL | str,
            *,
            params: QueryParamTypes | None = None,
            headers: HeaderTypes | None = None,
            cookies: CookieTypes | None = None,
            content: RequestContent | None = None,
            data: RequestData | None = None,
            files: RequestFiles | None = None,
            json: typing.Any | None = None,
            stream: SyncByteStream | AsyncByteStream | None = None,
            extensions: RequestExtensions | None = None,
            event_hooks: None | (typing.Mapping[str, list[EventHook]]) = None
    ) -> None:
        super().__init__(
            method=method,
            url=url,
            params=params,
            headers=headers,
            cookies=cookies,
            content=content,
            data=data,
            files=files,
            json=json,
            stream=stream,
            extensions=extensions,
        )
        self.event_hooks = event_hooks


