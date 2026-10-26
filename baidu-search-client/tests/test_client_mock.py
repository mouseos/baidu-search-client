"""Mocked-transport client tests: full pipeline, no network.

The FakeSession is injected as the client's session, so requests go
through the real HttpTransport -> validation -> baidu_parser ->
aggregation path; only the socket is fake.
"""

import json

import pytest

from baidu_search import errors
from conftest import fixture_bytes, make_client, tianqi_fixture_map
from fake_http import FakeResponse, FakeSession, pn_router


def tianqi_session(**kwargs):
    return FakeSession(pn_router(tianqi_fixture_map(), **kwargs))


def test_one_page_search():
    session = tianqi_session()
    with make_client(session) as client:
        result = client.search("天气", max_pages=1)
    assert result.pages_fetched == 1
    assert len(result.results) == 5
    assert len(result.cards) == 4
    assert result.ads == []
    assert result.unknown_elements == []
    assert result.to_dict()["diagnostics"]["errors"] == []
    assert len(session.requested_urls) == 1


def test_two_page_search():
    session = tianqi_session()
    with make_client(session) as client:
        result = client.search("天气", max_pages=2)
    assert result.pages_fetched == 2
    assert len(result.results) == 5 + 6
    assert [p.pn for p in result.pages] == [0, 10]


def test_three_page_search_and_natural_end():
    session = tianqi_session()
    with make_client(session) as client:
        # pn20 has no next_url, so even max_pages=5 stops at 3 pages.
        result = client.search("天气", max_pages=5)
    assert result.pages_fetched == 3
    assert len(result.results) == 5 + 6 + 8
    assert [p.pn for p in result.pages] == [0, 10, 20]
    assert result.pages[-1].next_url is None
    assert len(session.requested_urls) == 3


def test_next_url_passed_through_verbatim():
    """The 2nd request must be the exact server-issued next_url string."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "baidu-search-parser"))
    from baidu_parser import parse_search_results

    page1 = parse_search_results(
        fixture_bytes("tianqi_p1.html"), query="天气",
        page_url="https://m.baidu.com/s?word=%E5%A4%A9%E6%B0%94",
    )
    session = tianqi_session()
    with make_client(session) as client:
        client.search("天气", max_pages=2)
    assert session.requested_urls[1] == page1.page.next_url
    # the server-issued ant_ct inside it survived untouched
    assert "ant_ct=" in session.requested_urls[1]


def test_cookie_maintenance_across_pages():
    session = tianqi_session(cookies_to_set={"BAIDUID": "fake-value-not-logged"})
    with make_client(session) as client:
        result = client.search("天气", max_pages=3)
        names = client.cookie_names
    assert result.pages_fetched == 3
    assert "BAIDUID" in names
    # first request went out with no cookies; later ones carried BAIDUID
    assert session.request_cookie_names[0] == []
    assert "BAIDUID" in session.request_cookie_names[1]
    assert "BAIDUID" in session.request_cookie_names[2]
    # cookie values never leak into the JSON output
    assert "fake-value-not-logged" not in json.dumps(result.to_dict())


def test_search_page_single_api():
    session = tianqi_session()
    with make_client(session) as client:
        single = client.search_page("天气")
    assert single.page.query == "天气"
    assert len(single.page.results) == 5
    assert single.page.page.next_url is not None
    assert single.status_code == 200
    data = single.to_dict()
    assert data["fetch"]["status_code"] == 200


def test_japanese_query():
    session = FakeSession(pn_router({0: fixture_bytes("sapporo.html")}))
    with make_client(session) as client:
        result = client.search("札幌 天気", max_pages=1)
    assert result.pages_fetched == 1
    assert len(result.results) == 7
    assert any("札幌" in (r["title"] or "") for r in result.results)


def test_english_query():
    session = FakeSession(pn_router({0: fixture_bytes("weather_en.html")}))
    with make_client(session) as client:
        result = client.search("weather", max_pages=1)
    assert result.pages_fetched == 1
    assert len(result.results) == 3
    assert len(result.cards) == 6


def test_global_rank_is_new_field_and_parser_ranks_preserved():
    session = tianqi_session()
    with make_client(session) as client:
        result = client.search("天气", max_pages=2)
    ranks = [r["global_organic_rank"] for r in result.results]
    assert ranks == list(range(1, len(result.results) + 1))
    page2 = [r for r in result.results if r["page_pn"] == 10]
    # parser's own per-page organic_rank restarts at 1 and is untouched
    assert page2[0]["organic_rank"] == 1
    assert page2[0]["global_organic_rank"] == 6


def test_json_serializable_and_readable_unicode():
    session = tianqi_session()
    with make_client(session) as client:
        result = client.search("天气", max_pages=3)
    text = json.dumps(result.to_dict(), ensure_ascii=False)
    assert "天气" in text  # not \uXXXX-escaped
    parsed = json.loads(text)
    assert parsed["query"] == "天气"
    assert parsed["pages_requested"] == 3
    assert parsed["pages_fetched"] == 3
    for key in ("results", "ads", "cards", "related_searches",
                "unknown_elements", "pages"):
        assert key in parsed
    assert set(parsed["diagnostics"]) >= {"duplicates", "errors", "warnings"}


def test_max_pages_clamped_with_warning():
    session = tianqi_session()
    with make_client(session, max_pages_limit=2) as client:
        result = client.search("天气", max_pages=9)
    assert result.pages_requested == 9
    assert result.pages_fetched == 2
    assert any("clamped" in w for w in result.warnings)


def test_waf_title_warning_not_page_rejection():
    """Measured page 1 contains a result whose stored title is a WAF
    page title; the page itself is valid and must parse, with the
    quirk surfaced as a warning (round-16 finding)."""
    session = tianqi_session()
    with make_client(session) as client:
        result = client.search("天气", max_pages=1)
    assert result.pages_fetched == 1
    assert any(
        w.startswith("waf_title_in_results") for w in result.warnings
    )
