"""Synthetic-fixture tests: ads, entities, edge cases.

The ad fixture is hand-written (marked as such in the file) because
the measured pages contain no ad results; it follows the ad markup
conventions of Baidu's in-page ``ec_ls_css`` stylesheet.
"""

import json

from baidu_parser import parse_search_results
from baidu_parser.urls import classify_click_url, pn_of, resolve
from conftest import FIXTURES, load_fixture

PAGE_URL = "https://m.baidu.com/s?word=test"


def test_ad_separation_and_entities():
    page = parse_search_results(
        load_fixture("synthetic_ad.html"), query="test", page_url=PAGE_URL
    )
    # one organic result, one ad, one unknown template
    assert len(page.results) == 2  # positions 1 (organic) and 4 (relative link)
    assert len(page.ads) == 1
    assert len(page.unknown_elements) == 1
    assert page.unknown_elements[0].tpl == "some_future_tpl"

    organic = page.results[0]
    assert organic.title == "Organic & Title"  # &amp; decoded
    assert organic.snippet == "An organic snippet with emphasis kept."
    assert organic.organic_rank == 1

    ad = page.ads[0]
    assert ad.title == "Sponsored Thing"
    assert ad.url == "https://ads.example.com/landing"
    assert ad.organic_rank is None  # ads never consume an organic rank
    assert page.results[1].organic_rank == 2


def test_relative_url_resolution():
    page = parse_search_results(
        load_fixture("synthetic_ad.html"), query="test", page_url=PAGE_URL
    )
    relative = page.results[1]
    assert relative.title == "Relative Link Title"
    assert relative.click_url == "https://m.baidu.com/s?word=rel"
    assert resolve("/s?word=x", PAGE_URL) == "https://m.baidu.com/s?word=x"
    assert resolve(None, PAGE_URL) is None


def test_click_url_classification():
    assert classify_click_url("https://m.baidu.com/from=0/x/t=zbios/l=1/tc?a=1") == "baidu_redirect"
    assert classify_click_url("baiduboxapp://v1/browser/open?url=x") == "baidu_app_scheme"
    assert classify_click_url("https://baike.baidu.com/item/x") == "baidu_internal"
    assert classify_click_url("https://example.com/") == "direct_external"
    assert classify_click_url(None) is None
    assert pn_of("https://m.baidu.com/s?pn=30&word=x") == 30
    assert pn_of("https://m.baidu.com/s?word=x") is None


def test_empty_and_broken_pages():
    empty = parse_search_results("<html><body></body></html>", query="x")
    assert empty.results == [] and empty.ads == [] and empty.cards == []
    assert empty.page.next_url is None
    assert any("c-result" in w for w in empty.diagnostics["warnings"])
    json.dumps(empty.to_dict(), ensure_ascii=False)

    no_results_div = parse_search_results(
        '<html><body><div id="results"></div></body></html>'
    )
    assert no_results_div.diagnostics["c_result_count"] == 0


def test_missing_attributes_do_not_crash():
    html = (
        '<html><body><div id="results">'
        '<div class="c-result result" tpl="www_index">'
        "<h3>No attributes at all</h3></div>"
        '<div class="c-result result"><h3>No tpl</h3></div>'
        "</div></body></html>"
    )
    page = parse_search_results(html, query="x", page_url=PAGE_URL)
    assert len(page.results) == 1
    assert page.results[0].title == "No attributes at all"
    assert page.results[0].display_position is None
    assert page.results[0].url is None
    assert len(page.unknown_elements) == 1
    assert "tpl" in page.unknown_elements[0].reason
    assert any("order" in w for w in page.diagnostics["warnings"])
    json.dumps(page.to_dict(), ensure_ascii=False)


def test_utf8_input_forms():
    raw = load_fixture("synthetic_ad.html")
    as_str = parse_search_results(raw.decode("utf-8"), query="test", page_url=PAGE_URL)
    as_bytes = parse_search_results(raw, query="test", page_url=PAGE_URL)
    assert as_str.to_dict() == as_bytes.to_dict()
