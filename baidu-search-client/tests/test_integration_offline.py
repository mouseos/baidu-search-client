"""Offline integration: saved measured HTML flows through the whole
client stack (transport with cookie jar -> validation -> parser ->
pagination -> JSON aggregation), exactly as a live response would,
plus field-level quality metrics over the aggregated output.
"""

import json

from conftest import make_client, tianqi_fixture_map
from fake_http import FakeSession, pn_router


def test_full_pipeline_three_pages_metrics():
    session = FakeSession(pn_router(tianqi_fixture_map()))
    with make_client(session) as client:
        result = client.search("天气", max_pages=3)

    data = result.to_dict()
    # JSON round trip must be lossless
    assert json.loads(json.dumps(data, ensure_ascii=False)) == data

    assert data["pages_fetched"] == 3
    assert len(data["results"]) == 19
    assert len(data["cards"]) == 8
    assert data["ads"] == []
    assert len(data["unknown_elements"]) == 0
    assert data["diagnostics"]["duplicates"] == 0
    assert data["diagnostics"]["errors"] == []

    results = data["results"]
    title_rate = sum(1 for r in results if r["title"]) / len(results)
    url_rate = sum(1 for r in results if r["url"]) / len(results)
    snippet_rate = sum(1 for r in results if r["snippet"]) / len(results)
    assert title_rate == 1.0
    assert url_rate == 1.0
    # measured: 15 of 19 organic results carry an abstract in the
    # saved pages; the other 4 have none in the HTML itself.
    assert sum(1 for r in results if r["snippet"]) == 15

    # page provenance and server-issued chain are preserved in the output
    assert [p["pn"] for p in data["pages"]] == [0, 10, 20]
    assert data["pages"][0]["next_url"] == data["pages"][1]["source_url"]
    assert data["pages"][1]["next_url"] == data["pages"][2]["source_url"]
    assert data["pages"][2]["next_url"] is None


def test_offline_fixture_reuse_all_languages():
    from conftest import fixture_bytes

    cases = {
        "札幌 天気": ("sapporo.html", 7, 2),
        "weather": ("weather_en.html", 3, 6),
        "天气": ("tianqi_p1.html", 5, 4),
    }
    for query, (name, n_results, n_cards) in cases.items():
        session = FakeSession(pn_router({0: fixture_bytes(name)}))
        with make_client(session) as client:
            result = client.search(query, max_pages=1)
        assert result.pages_fetched == 1, query
        assert len(result.results) == n_results, query
        assert len(result.cards) == n_cards, query
