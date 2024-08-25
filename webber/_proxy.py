import validators

from dataclasses import dataclass


@dataclass(frozen=True, eq=False)
class Proxy:
    """
    A class for representing a proxy.

    :param url: The url of the proxy.
    :param user_agent: a dictionary of user-agent related headers.
    """

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

    def __str__(self):
        return f"Proxy(url={self.url}, user_agent={self.user_agent})"
