"""Public client API: query string in, structured JSON-able data out.

Pipeline per page (identical to the validated measurement flow):

    query ─▶ build_initial_search_url (legacy search_probe, ant_ct in
             seconds via legacy crypto)
          ─▶ HttpTransport GET through one SearchSession (cookies kept)
          ─▶ response sanity checks (not just "HTTP 200")
          ─▶ baidu_parser.parse_search_results
          ─▶ page.next_url followed verbatim for further pages

Response sanity checks, beyond the status code handled in the
transport:

* verification pages: strong markers (``wappass`` host references,
  ``安全验证``) in a body that has no ``#results`` container raise
  :class:`CaptchaDetectedError`.  This is deliberately distinct from
  the known quirk where a *single result's stored title* is a WAF
  page title — that case keeps the page usable and is reported as a
  warning instead.
* a 200 page with neither ``#results`` nor any ``.c-result`` raises
  :class:`NotSearchResultError`.
* a valid results page with zero extracted entries produces an
  ``empty_results`` warning, not an exception.
"""

from __future__ import annotations

from typing import Any, Optional

from baidu_parser import parse_search_results

from . import models, pagination, search_url
from .errors import (
    BaiduSearchError,
    CaptchaDetectedError,
    NotSearchResultError,
    ParseFailedError,
)
from .models import AggregatedSearch, PageRecord, SinglePageResult
from .pagination import SeenUrls
from .session import SearchSession
from .transport import HttpTransport, TransportResponse

_VERIFICATION_MARKERS = ("wappass.baidu.com", "wappass", "安全验证")
_WAF_TITLE_MARKERS = ("应用防火墙", "WEB 应用防火墙")


class BaiduSearchClient:
    """End-to-end Baidu (APK-flow) search client.

    Parameters mirror the safety limits: ``timeout`` (seconds,
    connect+read), ``max_pages_limit`` (hard cap for ``search()``),
    ``min_request_interval`` (seconds between requests; no retries
    are ever performed), ``max_response_bytes``.
    A pre-built ``session`` (``requests.Session`` or a test double
    with the same interface) may be injected.
    """

    def __init__(
        self,
        *,
        timeout: float = 25.0,
        max_pages_limit: int = 10,
        min_request_interval: float = 1.0,
        max_response_bytes: int = 8_000_000,
        session: Any = None,
        transport: Optional[HttpTransport] = None,
    ) -> None:
        self._search_session = SearchSession(session)
        self._transport = transport or HttpTransport(
            self._search_session.raw,
            timeout=timeout,
            max_bytes=max_response_bytes,
            min_interval=min_request_interval,
        )
        self.max_pages_limit = max_pages_limit

    # -- lifecycle -----------------------------------------------------

    def close(self) -> None:
        self._search_session.close()

    def __enter__(self) -> "BaiduSearchClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def cookie_names(self) -> list[str]:
        """Cookie names currently held by the session (never values)."""
        return self._search_session.cookie_names()

    # -- single page -----------------------------------------------------

    def search_page(
        self, query: str, *, page_url: Optional[str] = None
    ) -> SinglePageResult:
        """Fetch and parse exactly one results page.

        With ``page_url=None`` the first-page URL is built from
        ``query``; otherwise ``page_url`` is fetched as-is (this is
        how pagination follows server-issued URLs).  Raises typed
        :class:`BaiduSearchError` subclasses on failure.
        """
        url = page_url if page_url is not None else search_url.build_initial_search_url(query)
        response = self._transport.fetch(url)
        return self._parse_response(response, query=query, requested_url=url)

    def _parse_response(
        self,
        response: TransportResponse,
        *,
        query: str,
        requested_url: str,
    ) -> SinglePageResult:
        text = response.body.decode("utf-8", errors="replace")
        if 'id="results"' not in text and any(
            marker in text or marker in response.final_url
            for marker in _VERIFICATION_MARKERS
        ):
            raise CaptchaDetectedError(
                "server returned a verification page instead of search results",
                url=response.final_url,
                status_code=response.status_code,
            )
        try:
            page = parse_search_results(
                response.body, query=query, page_url=response.final_url
            )
        except Exception as exc:  # lxml failures etc.
            raise ParseFailedError(
                "HTML parsing failed: {}".format(exc),
                url=response.final_url,
                status_code=response.status_code,
            ) from exc

        diagnostics = page.diagnostics or {}
        warnings: list[str] = list(diagnostics.get("warnings", []))
        if diagnostics.get("c_result_count", 0) == 0 and any(
            "no #results" in w for w in warnings
        ):
            raise NotSearchResultError(
                "HTTP 200 response is not a search-result page "
                "(no #results container, no .c-result elements)",
                url=response.final_url,
                status_code=response.status_code,
            )

        client_warnings: list[str] = []
        total_entries = (
            len(page.results) + len(page.ads) + len(page.cards)
            + len(page.unknown_elements)
        )
        if total_entries == 0:
            client_warnings.append("empty_results")
        waf_titles = [
            r.title
            for r in list(page.results) + list(page.ads)
            if r.title and any(m in r.title for m in _WAF_TITLE_MARKERS)
        ]
        if waf_titles:
            client_warnings.append(
                "waf_title_in_results: {} result title(s) are WAF page "
                "titles stored by the server; the page itself is a "
                "valid results page".format(len(waf_titles))
            )
        return SinglePageResult(
            query=query,
            source_url=requested_url,
            final_url=response.final_url,
            status_code=response.status_code,
            page=page,
            warnings=client_warnings,
        )

    # -- multi page ------------------------------------------------------

    def search(self, query: str, *, max_pages: int = 3) -> AggregatedSearch:
        """Search ``query`` and follow next-page URLs up to ``max_pages``.

        Per-page failures are recorded in ``diagnostics.errors`` and
        pagination stops; pages already fetched are kept.  This
        method raises only for invalid arguments.
        """
        if max_pages < 1:
            raise ValueError("max_pages must be >= 1")
        requested_pages = max_pages
        warnings: list[str] = []
        if max_pages > self.max_pages_limit:
            warnings.append(
                "max_pages={} clamped to limit {}".format(
                    max_pages, self.max_pages_limit
                )
            )
            max_pages = self.max_pages_limit

        singles: list[SinglePageResult] = []
        failed_pages: list[PageRecord] = []
        errors: list[dict[str, Any]] = []
        seen = SeenUrls()

        url: Optional[str] = search_url.build_initial_search_url(query)
        fetch_index = 0
        while url is not None and len(singles) + len(failed_pages) < max_pages:
            fetch_index += 1
            seen.add(url)
            try:
                single = self.search_page(query, page_url=url)
            except BaiduSearchError as exc:
                err = exc.to_dict()
                err["page_fetch_index"] = fetch_index
                errors.append(err)
                failed_pages.append(
                    PageRecord(
                        page_number=None,
                        pn=None,
                        source_url=url,
                        final_url=exc.url,
                        status_code=exc.status_code,
                        error=err,
                    )
                )
                break
            singles.append(single)

            next_url = single.page.page.next_url
            if not next_url:
                break
            if len(singles) + len(failed_pages) >= max_pages:
                break
            try:
                pagination.validate_next_url(next_url)
                seen.check(next_url)
            except BaiduSearchError as exc:
                err = exc.to_dict()
                err["page_fetch_index"] = fetch_index + 1
                errors.append(err)
                break
            url = next_url

        return models.aggregate(
            query,
            pages_requested=requested_pages,
            singles=singles,
            errors=errors,
            warnings=warnings,
            failed_pages=failed_pages,
        )
