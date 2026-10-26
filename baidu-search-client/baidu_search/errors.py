"""Error taxonomy for the Baidu search client.

Every failure the client can hit is a :class:`BaiduSearchError` with a
stable ``kind`` string so callers (and the aggregated JSON diagnostics)
can distinguish situations without parsing messages:

* ``dns_error``          – name resolution failed
* ``connection_error``   – TCP connection failed / reset
* ``tls_error``          – TLS handshake / certificate verification failed
* ``timeout``            – connect or read timeout
* ``redirect_error``     – too many redirects or redirect to a
  non-Baidu host
* ``response_too_large`` – body exceeded the configured cap
* ``http_error``         – HTTP status >= 400 (other than 403/429)
* ``access_restricted``  – HTTP 403 / 429
* ``captcha_or_verification`` – HTTP 200 but the body is a Baidu
  verification / CAPTCHA page, not search results
* ``not_search_result``  – HTTP 200 but the HTML has neither a
  ``#results`` container nor any ``.c-result`` element
* ``parse_error``        – the HTML parser itself failed
* ``pagination_cycle``   – a next-page URL re-appeared
* ``invalid_next_url``   – next-page URL has an unexpected scheme/host

``search()`` never raises these for per-page failures: it records them
in ``diagnostics.errors`` and keeps whatever pages were already
fetched.  ``search_page()`` raises them.
"""

from __future__ import annotations

from typing import Any, Optional


class BaiduSearchError(Exception):
    """Base class for all client errors."""

    kind = "baidu_search_error"

    def __init__(
        self,
        message: str,
        *,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.url = url
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "url": self.url,
            "status_code": self.status_code,
        }


class TransportError(BaiduSearchError):
    kind = "transport_error"


class DnsResolutionError(TransportError):
    kind = "dns_error"


class ConnectionFailedError(TransportError):
    kind = "connection_error"


class TlsError(TransportError):
    kind = "tls_error"


class BaiduTimeoutError(TransportError):
    kind = "timeout"


class RedirectError(TransportError):
    kind = "redirect_error"


class ResponseTooLargeError(TransportError):
    kind = "response_too_large"


class HttpStatusError(BaiduSearchError):
    kind = "http_error"


class AccessRestrictedError(HttpStatusError):
    """HTTP 403 / 429.  The client stops; it never retries or evades."""

    kind = "access_restricted"


class CaptchaDetectedError(AccessRestrictedError):
    """HTTP 200 whose body is a verification page, not search results."""

    kind = "captcha_or_verification"


class NotSearchResultError(BaiduSearchError):
    kind = "not_search_result"


class ParseFailedError(BaiduSearchError):
    kind = "parse_error"


class PaginationError(BaiduSearchError):
    kind = "pagination_error"


class PaginationCycleError(PaginationError):
    kind = "pagination_cycle"


class InvalidNextUrlError(PaginationError):
    kind = "invalid_next_url"
