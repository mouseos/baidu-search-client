"""Offline HTTP test doubles implementing the requests.Session subset
that HttpTransport uses.  No network is ever touched.

``FakeSession.get`` routes either by an explicit URL->response/exception
mapping or by a callable.  Cookies set via a response's
``cookies_to_set`` are stored in a real ``RequestsCookieJar`` and their
*names* are snapshotted before every request, so tests can prove the
session carried them across pages (values are never asserted on or
printed).
"""

from __future__ import annotations

from typing import Callable, Union
from urllib.parse import parse_qs, urlparse

import requests
from requests.cookies import RequestsCookieJar

ResponseOrError = Union["FakeResponse", Exception]


class FakeResponse:
    def __init__(
        self,
        body: bytes = b"",
        *,
        status: int = 200,
        url: str = "",
        headers: dict | None = None,
        cookies_to_set: dict | None = None,
        history: list | None = None,
    ) -> None:
        self._body = body
        self.status_code = status
        self.url = url
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.cookies_to_set = cookies_to_set or {}
        self.history = history or []
        self.closed = False

    def iter_content(self, chunk_size: int = 65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]

    @property
    def content(self) -> bytes:
        return self._body

    def close(self) -> None:
        self.closed = True


class FakeSession:
    """Routes GETs. ``router`` maps a URL to FakeResponse or Exception."""

    def __init__(self, router: Callable[[str], ResponseOrError]) -> None:
        self._router = router
        self.cookies = RequestsCookieJar()
        self.headers = {}
        self.requested_urls: list[str] = []
        self.request_cookie_names: list[list[str]] = []
        self.closed = False

    def get(self, url: str, **kwargs) -> FakeResponse:
        self.requested_urls.append(url)
        self.request_cookie_names.append(
            sorted({c.name for c in self.cookies})
        )
        outcome = self._router(url)
        if isinstance(outcome, Exception):
            raise outcome
        if not outcome.url:
            outcome.url = url
        for name, value in outcome.cookies_to_set.items():
            self.cookies.set(name, value)
        return outcome

    def close(self) -> None:
        self.closed = True


def pn_router(fixture_bytes: dict[int, bytes], **response_kwargs):
    """Route by the ``pn`` query parameter of the requested URL."""

    def route(url: str) -> FakeResponse:
        qs = parse_qs(urlparse(url).query)
        pn = int(qs.get("pn", ["0"])[0])
        if pn not in fixture_bytes:
            return FakeResponse(b"not found", status=404, url=url)
        return FakeResponse(fixture_bytes[pn], url=url, **response_kwargs)

    return route


def requests_connection_error(message: str) -> requests.ConnectionError:
    return requests.ConnectionError(message)
