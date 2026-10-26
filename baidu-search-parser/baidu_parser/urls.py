"""URL handling.

Rules (from the measured HTML, see ../url-extraction.md):

* URLs are kept **verbatim** as found in the HTML (after HTML entity
  decoding, which the DOM parser already performs).  Tracking parameters
  are never stripped and redirect targets are never guessed.
* Relative hrefs are resolved against the page URL with ``urljoin`` —
  the only transformation applied.
* The external ("real") URL of a result is taken only when the HTML
  itself states it (``data-log.mu`` or the ``url`` member of the
  ``data-click-info`` JSON).  Otherwise it stays ``None``.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urljoin, urlparse, parse_qs

_BAIDU_SUFFIX = "baidu.com"


def resolve(href: Optional[str], base: Optional[str]) -> Optional[str]:
    """Resolve a possibly-relative href against the page URL."""
    if href is None:
        return None
    href = href.strip()
    if not href:
        return None
    if base:
        return urljoin(base, href)
    return href


def host_of(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return urlparse(url).hostname
    except ValueError:
        return None


def is_baidu_host(host: Optional[str]) -> bool:
    return bool(host) and (host == _BAIDU_SUFFIX or host.endswith("." + _BAIDU_SUFFIX))


def classify_click_url(url: Optional[str]) -> Optional[str]:
    """Classify the URL a result link actually points to.

    Returns one of:
      * ``baidu_redirect``  – http(s) URL on a Baidu host whose path ends
        with the ``/tc`` click-tracking segment (the wise click-through
        endpoint observed in the measured pages).
      * ``baidu_app_scheme`` – ``baiduboxapp://`` deep link into the app.
      * ``baidu_internal``  – other http(s) URL on a Baidu host.
      * ``direct_external`` – http(s) URL on a non-Baidu host.
      * ``other_scheme``    – anything else (tel:, javascript:, …).
    """
    if not url:
        return None
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme == "baiduboxapp":
        return "baidu_app_scheme"
    if scheme in ("http", "https"):
        host = parsed.hostname
        if is_baidu_host(host):
            if parsed.path.rstrip("/").endswith("/tc"):
                return "baidu_redirect"
            return "baidu_internal"
        return "direct_external"
    return "other_scheme"


def is_baidu_redirect(url: Optional[str]) -> bool:
    return classify_click_url(url) == "baidu_redirect"


_PN_RE = re.compile(r"[?&]pn=(\d+)")


def pn_of(url: Optional[str]) -> Optional[int]:
    """Extract the ``pn`` query parameter of a server-issued page URL."""
    if not url:
        return None
    qs = parse_qs(urlparse(url).query)
    values = qs.get("pn")
    if values:
        try:
            return int(values[0])
        except ValueError:
            return None
    # Server-issued previous/first-page URLs omit pn entirely (means 0).
    return None


def word_of(url: Optional[str]) -> Optional[str]:
    """Extract the decoded ``word`` (query) parameter of a page URL."""
    if not url:
        return None
    qs = parse_qs(urlparse(url).query)
    values = qs.get("word")
    return values[0] if values else None
