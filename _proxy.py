import validators

from dataclasses import dataclass
from collections import deque


@dataclass(frozen=True, eq=False)
class Proxy:
    url: str
    user_agent: dict[str, str]

    def __post_init__(self):
        if not validators.url(self.url):
            raise ValueError(f"proxy: {repr(self.url)} is not a valid url.")

    def __eq__(self, other):
        if isinstance(other, Proxy):
            return self.url == other.url
        return False

    def __hash__(self):
        return hash(self.url)
