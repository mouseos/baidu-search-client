"""HTTP transport: one GET with safety limits and error classification.

Safety properties (all on by default):

* TLS certificate verification is always on (``verify`` is never
  passed as ``False`` anywhere in this package).
* Connect/read timeout is mandatory (a single float).
* The response body is streamed and capped at ``max_bytes``; an
  oversized body aborts the request instead of being buffered whole.
* A minimum interval between requests is enforced; there are no
  automatic retries.
* Redirects are followed by ``requests`` (bounded by its own limit),
  but a redirect chain that leaves ``*.baidu.com`` is rejected.
* HTTP 403 / 429 raise :class:`AccessRestrictedError`; the caller
  stops pagination instead of retrying.
* Proxy configuration is whatever ``requests`` / the environment
  provides (``HTTP_PROXY`` etc.).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import requests

from .errors import (
    AccessRestrictedError,
    BaiduTimeoutError,
    ConnectionFailedError,
    DnsResolutionError,
    HttpStatusError,
    RedirectError,
    ResponseTooLargeError,
    TlsError,
    TransportError,
)

_BAIDU_SUFFIX = "baidu.com"
_CHUNK = 65536


@dataclass
class TransportResponse:
    status_code: int
    final_url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    redirect_count: int = 0


def _is_baidu_host(host: Optional[str]) -> bool:
    return bool(host) and (host == _BAIDU_SUFFIX or host.endswith("." + _BAIDU_SUFFIX))


class HttpTransport:
    """Performs GET requests through an injected session object.

    The session only needs the ``requests.Session`` interface subset
    (``get(url, timeout=…, stream=…, allow_redirects=…)`` returning a
    response with ``status_code`` / ``url`` / ``headers`` /
    ``history`` / ``iter_content`` / ``close``), which is what the
    offline tests fake.
    """

    def __init__(
        self,
        session: Any,
        *,
        timeout: float = 25.0,
        max_bytes: int = 8_000_000,
        min_interval: float = 1.0,
        _sleep: Callable[[float], None] = time.sleep,
        _clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._session = session
        self.timeout = timeout
        self.max_bytes = max_bytes
        self.min_interval = min_interval
        self._sleep = _sleep
        self._clock = _clock
        self._last_request_at: Optional[float] = None

    # -- internals ---------------------------------------------------

    def _respect_interval(self) -> None:
        if self.min_interval <= 0:
            return
        now = self._clock()
        if self._last_request_at is not None:
            wait = self.min_interval - (now - self._last_request_at)
            if wait > 0:
                self._sleep(wait)
        self._last_request_at = self._clock()

    @staticmethod
    def _classify_connection_error(exc: requests.ConnectionError, url: str):
        text = str(exc)
        dns_markers = (
            "Name or service not known",
            "Temporary failure in name resolution",
            "Failed to resolve",
            "NameResolutionError",
            "getaddrinfo failed",
            "nodename nor servname",
        )
        if any(marker in text for marker in dns_markers):
            return DnsResolutionError(
                "DNS resolution failed: {}".format(exc), url=url
            )
        return ConnectionFailedError(
            "connection failed: {}".format(exc), url=url
        )

    # -- public API ----------------------------------------------------

    def fetch(self, url: str) -> TransportResponse:
        """GET ``url`` and return the response, or raise a typed error."""
        self._respect_interval()
        try:
            resp = self._session.get(
                url,
                timeout=self.timeout,
                stream=True,
                allow_redirects=True,
            )
        except requests.exceptions.SSLError as exc:
            raise TlsError("TLS error: {}".format(exc), url=url) from exc
        except requests.exceptions.Timeout as exc:
            raise BaiduTimeoutError(
                "request timed out: {}".format(exc), url=url
            ) from exc
        except requests.exceptions.TooManyRedirects as exc:
            raise RedirectError(
                "too many redirects: {}".format(exc), url=url
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise self._classify_connection_error(exc, url) from exc
        except requests.exceptions.RequestException as exc:
            raise TransportError(
                "transport error: {}".format(exc), url=url
            ) from exc

        try:
            status = int(resp.status_code)
            final_url = getattr(resp, "url", None) or url
            redirect_count = len(getattr(resp, "history", None) or [])
            headers = {str(k): str(v) for k, v in (resp.headers or {}).items()}

            final_host = urlparse(final_url).hostname
            if redirect_count and not _is_baidu_host(final_host):
                raise RedirectError(
                    "redirected to unexpected host: {}".format(final_host),
                    url=final_url,
                    status_code=status,
                )

            body = bytearray()
            for chunk in resp.iter_content(_CHUNK):
                if not chunk:
                    continue
                body.extend(chunk)
                if len(body) > self.max_bytes:
                    raise ResponseTooLargeError(
                        "response body exceeded {} bytes".format(self.max_bytes),
                        url=final_url,
                        status_code=status,
                    )

            if status in (403, 429):
                raise AccessRestrictedError(
                    "access restricted (HTTP {})".format(status),
                    url=final_url,
                    status_code=status,
                )
            if status >= 400:
                raise HttpStatusError(
                    "HTTP error {}".format(status),
                    url=final_url,
                    status_code=status,
                )
            return TransportResponse(
                status_code=status,
                final_url=final_url,
                headers=headers,
                body=bytes(body),
                redirect_count=redirect_count,
            )
        finally:
            close = getattr(resp, "close", None)
            if callable(close):
                close()
