"""Client-side pagination control.

The next-page URL always comes from the parser
(``SearchPage.page.next_url``), i.e. the URL the server itself
embedded in the HTML.  It is used **verbatim**: this module never
rebuilds a ``pn=`` URL and never normalises the string (server-issued
``ant_ct`` / ``rsv_pq`` values in it must survive untouched).

Before a next URL is followed it is only *validated*:

* scheme must be ``http`` or ``https``;
* host must be ``baidu.com`` or a subdomain of it;
* the exact string must not have been fetched already (cycle guard).
"""

from __future__ import annotations

from urllib.parse import urlparse

from .errors import InvalidNextUrlError, PaginationCycleError

_ALLOWED_SCHEMES = {"http", "https"}
_BAIDU_SUFFIX = "baidu.com"


def validate_next_url(url: str) -> str:
    """Return ``url`` unchanged, or raise :class:`InvalidNextUrlError`."""
    if not url or not isinstance(url, str):
        raise InvalidNextUrlError("next-page URL is empty or not a string")
    parsed = urlparse(url)
    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        raise InvalidNextUrlError(
            "next-page URL has unexpected scheme: {!r}".format(parsed.scheme),
            url=url,
        )
    host = parsed.hostname
    if not host or not (host == _BAIDU_SUFFIX or host.endswith("." + _BAIDU_SUFFIX)):
        raise InvalidNextUrlError(
            "next-page URL has unexpected host: {!r}".format(host),
            url=url,
        )
    return url


class SeenUrls:
    """Exact-string set of already-fetched URLs (cycle detection)."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def add(self, url: str) -> None:
        self._seen.add(url)

    def __contains__(self, url: str) -> bool:
        return url in self._seen

    def check(self, url: str) -> None:
        """Raise :class:`PaginationCycleError` if ``url`` was seen."""
        if url in self._seen:
            raise PaginationCycleError(
                "pagination cycle: URL re-appeared", url=url
            )
