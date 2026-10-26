"""Pagination guards: cycle detection, next-URL validation, and the
mid-pagination failure policy (keep fetched pages, record the error).

Note: the client's first request always goes to the URL built by
``build_initial_search_url``; the routers below therefore answer the
first request with a synthetic page A and route later requests by
exact URL.
"""

import pytest

from baidu_search import errors
from conftest import make_client, tianqi_fixture_map
from fake_http import FakeResponse, FakeSession

PAGE_B_URL = "https://m.baidu.com/s?word=x&pn=10"


def _page_html(next_href: str | None) -> bytes:
    nav = ""
    if next_href is not None:
        nav = (
            '<div class="new-pagenav"><a class="new-nextpage" '
            'href="{}">下一页</a></div>'.format(next_href)
        )
    return (
        '<html><body><div id="results"></div>{}</body></html>'.format(nav)
    ).encode("utf-8")


class FirstPageRouter:
    """First request -> page A (with the given next href); later
    requests are delegated to ``rest`` (url -> bytes | FakeResponse)."""

    def __init__(self, first_next_href, rest=None):
        self.first_next_href = first_next_href
        self.rest = rest or {}
        self.first_url = None

    def __call__(self, url: str):
        if self.first_url is None:
            self.first_url = url
            return FakeResponse(_page_html(self.first_next_href), url=url)
        outcome = self.rest.get(url)
        if outcome is None:
            return FakeResponse(b"missing", status=404, url=url)
        if isinstance(outcome, FakeResponse):
            return outcome
        return FakeResponse(outcome, url=url)


def test_cycle_detection():
    router = FirstPageRouter(PAGE_B_URL)
    # page B links back to the (runtime-known) first URL -> cycle
    original_call = router.__call__

    def route(url: str):
        if url == PAGE_B_URL:
            return FakeResponse(_page_html(router.first_url), url=url)
        return original_call(url)

    session = FakeSession(route)
    with make_client(session) as client:
        result = client.search("x", max_pages=5)
    assert result.pages_fetched == 2
    kinds = [e["kind"] for e in result.to_dict()["diagnostics"]["errors"]]
    assert kinds == ["pagination_cycle"]
    assert len(session.requested_urls) == 2  # looped URL is not re-fetched


def test_invalid_next_url_external_host():
    router = FirstPageRouter("https://evil.example.com/s?pn=10")
    session = FakeSession(router)
    with make_client(session) as client:
        result = client.search("x", max_pages=3)
    assert result.pages_fetched == 1
    kinds = [e["kind"] for e in result.to_dict()["diagnostics"]["errors"]]
    assert kinds == ["invalid_next_url"]
    assert len(session.requested_urls) == 1
    assert all("evil.example.com" not in u for u in session.requested_urls)


def test_invalid_next_url_scheme():
    router = FirstPageRouter("javascript:void(0)")
    session = FakeSession(router)
    with make_client(session) as client:
        result = client.search("x", max_pages=3)
    kinds = [e["kind"] for e in result.to_dict()["diagnostics"]["errors"]]
    assert kinds == ["invalid_next_url"]
    assert len(session.requested_urls) == 1


def test_mid_pagination_http_error_keeps_fetched_pages():
    routes = tianqi_fixture_map()

    def route(url: str):
        from urllib.parse import parse_qs, urlparse

        pn = int(parse_qs(urlparse(url).query).get("pn", ["0"])[0])
        if pn == 10:
            return FakeResponse(b"server error", status=500, url=url)
        return FakeResponse(routes[pn], url=url)

    session = FakeSession(route)
    with make_client(session) as client:
        result = client.search("天气", max_pages=3)
    assert result.pages_fetched == 1
    assert len(result.results) == 5  # page 1 data is not discarded
    errs = result.to_dict()["diagnostics"]["errors"]
    assert len(errs) == 1
    assert errs[0]["kind"] == "http_error"
    assert errs[0]["status_code"] == 500


def test_redirect_to_foreign_host_rejected():
    def route(url: str):
        return FakeResponse(
            b"<html></html>",
            url="https://phishing.example.net/landing",
            history=[FakeResponse(status=302)],
        )

    session = FakeSession(route)
    with make_client(session) as client:
        with pytest.raises(errors.RedirectError):
            client.search_page("天气")


def test_validate_next_url_verbatim_and_hosts():
    from baidu_search.pagination import validate_next_url

    url = "https://m.baidu.com/s?pn=10&ant_ct=Ab%2FCd%3D"
    assert validate_next_url(url) == url  # unchanged, no normalisation
    with pytest.raises(errors.InvalidNextUrlError):
        validate_next_url("https://baidu.com.evil.example/s")
    with pytest.raises(errors.InvalidNextUrlError):
        validate_next_url("ftp://m.baidu.com/s")
    with pytest.raises(errors.InvalidNextUrlError):
        validate_next_url("")
