"""Aggregation semantics: duplicates are detected by exact URL match,
flagged, and never dropped; parser rank fields are preserved.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "baidu-search-parser"))

from baidu_parser import parse_search_results

from baidu_search import models
from baidu_search.models import SinglePageResult
from conftest import fixture_bytes


def _single(name: str, query: str, page_url: str) -> SinglePageResult:
    page = parse_search_results(
        fixture_bytes(name), query=query, page_url=page_url
    )
    return SinglePageResult(
        query=query,
        source_url=page_url,
        final_url=page_url,
        status_code=200,
        page=page,
    )


def test_duplicates_flagged_and_originals_kept():
    url = "https://m.baidu.com/s?word=%E5%A4%A9%E6%B0%94"
    s1 = _single("tianqi_p1.html", "天气", url)
    s2 = _single("tianqi_p1.html", "天气", url)  # same page twice
    agg = models.aggregate("天气", 2, [s1, s2])
    assert len(agg.results) == 10  # nothing dropped
    dupes = [r for r in agg.results if r["duplicate"]]
    assert len(dupes) == 5
    assert agg.to_dict()["diagnostics"]["duplicates"] == 5
    items = agg.to_dict()["diagnostics"]["duplicate_items"]
    assert items[0]["first_page_number"] == items[0]["duplicate_page_number"] == 1
    assert items[0]["key"] == agg.results[0]["url"]


def test_no_false_duplicates_across_real_pages():
    """Exact-match comparison must not merge distinct URLs
    (no aggressive normalisation)."""
    from conftest import tianqi_fixture_map  # noqa: F401  (path setup)

    s1 = _single("tianqi_p1.html", "天气", "https://m.baidu.com/s?word=x")
    s2 = _single("tianqi_pn10.html", "天气", "https://m.baidu.com/s?word=x&pn=10")
    s3 = _single("tianqi_pn20.html", "天气", "https://m.baidu.com/s?word=x&pn=20")
    agg = models.aggregate("天气", 3, [s1, s2, s3])
    assert agg.to_dict()["diagnostics"]["duplicates"] == 0
    assert len(agg.results) == 19


def test_related_searches_deduped_by_query():
    s1 = _single("tianqi_p1.html", "天气", "https://m.baidu.com/s?word=x")
    s2 = _single("tianqi_pn10.html", "天气", "https://m.baidu.com/s?word=x&pn=10")
    agg = models.aggregate("天气", 2, [s1, s2])
    queries = [r["query"] for r in agg.related_searches]
    assert len(queries) == len(set(queries))


def test_ads_and_cards_kept_separate_with_provenance():
    s1 = _single("weather_en.html", "weather", "https://m.baidu.com/s?word=weather")
    agg = models.aggregate("weather", 1, [s1])
    assert len(agg.cards) == 6
    assert all(c["page_pn"] == 0 for c in agg.cards)
    assert agg.ads == []
