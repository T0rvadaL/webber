import asyncio


class InternalError(Exception):
    """Raise this exception when an internal error occurs"""


class ProxiesUnavailable(Exception):
    """Raise this exception when no proxies are available"""

    def __init__(self, message: str, proxies_available_event: asyncio.Event | None = None):
        super().__init__(message)
        self.proxies_available_event = proxies_available_event


class ProxiesExhausted(Exception):
    """Raise this exception when all proxies have been exhausted"""
