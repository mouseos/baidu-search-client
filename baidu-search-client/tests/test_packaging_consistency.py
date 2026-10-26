"""Round-18 packaging tests.

* The vendored ``baidu_search.antct`` / ``baidu_search.urlbuild``
  must produce byte-identical output to the validated legacy modules
  in ``work/python-validation/`` (``crypto.py`` / ``search_probe.py``)
  on fixed test vectors.
* The runtime path must not depend on the development workspace:
  importing ``baidu_search`` and building a URL must not load the
  legacy modules nor put the validation directory on ``sys.path``.
* The aggregated JSON must stay compatible with the round-17 saved
  sample (structure and stable content identical; only time-dependent
  fields — the first page's built source URL — are masked).
* Secrets (cookie values) must never leak into errors/diagnostics.
* A redirect chain that leaves ``*.baidu.com`` must be rejected.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from baidu_search import antct, search_url, urlbuild

ROOT = Path(__file__).resolve().parent.parent
_DEV_LEGACY_DIR = ROOT.parent / "work" / "python-validation"
_VENDORED_LEGACY_DIR = ROOT / "tests" / "legacy_reference"
LEGACY_DIR = (
    _DEV_LEGACY_DIR
    if (_DEV_LEGACY_DIR / "crypto.py").exists()
    else _VENDORED_LEGACY_DIR
)
PARSER_PROJECT = ROOT.parent / "baidu-search-parser"
CLIENT_SAMPLE = ROOT / "samples" / "tianqi_multipage_offline.json"

pytestmark = pytest.mark.skipif(
    not (LEGACY_DIR / "crypto.py").exists(),
    reason="legacy validation modules not present (neither development workspace nor vendored reference copies)",
)


def _load_legacy_crypto():
    spec = importlib.util.spec_from_file_location(
        "legacy_crypto_for_consistency", LEGACY_DIR / "crypto.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# ant_ct: vendored vs legacy, fixed vectors
# ---------------------------------------------------------------------------

VECTORS = [
    (1761400000, "天气"),
    (1761400000, "札幌 天気"),
    (1700000000, "weather"),
    (1700000000, "a b+c/d=e&f"),
    (1, ""),
]


@pytest.mark.parametrize("t,query", VECTORS)
def test_antct_make_matches_legacy(t, query):
    legacy = _load_legacy_crypto()
    assert antct.make_ant_ct(t, query) == legacy.make_ant_ct(t, query)


@pytest.mark.parametrize("t,query", VECTORS)
def test_antct_plaintext_and_encrypt_match_legacy(t, query):
    legacy = _load_legacy_crypto()
    assert antct.build_plaintext(t, query) == legacy.build_plaintext(t, query)
    pt = antct.build_plaintext(t, query)
    assert antct.antct_encrypt(pt) == legacy.antct_encrypt(pt)
    # cross-decrypt: each implementation decrypts the other's output
    assert antct.antct_decrypt(legacy.antct_encrypt(pt)) == pt
    assert legacy.antct_decrypt(antct.antct_encrypt(pt)) == pt


def test_antct_constants_match_legacy():
    legacy = _load_legacy_crypto()
    assert antct.KEY_B64_LITERAL == legacy.KEY_B64_LITERAL
    assert antct.IV_B64_LITERAL == legacy.IV_B64_LITERAL
    assert antct.md5_hex_lower("天气".encode("utf-8")) == legacy.md5_hex_lower(
        "天气".encode("utf-8")
    )


# ---------------------------------------------------------------------------
# URL building: vendored vs legacy, fixed clock
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query,now_ms",
    [
        ("天气", 1761400000123),
        ("札幌 天気", 1761400000456),
        ("weather", 1700000000000),
        ("C++ 入門 & テスト?", 1700000000999),
    ],
)
def test_urlbuild_matches_legacy(query, now_ms):
    legacy = search_url._load_legacy()
    assert urlbuild.build_search_url(query, now_ms) == legacy.build_search_url(
        query, now_ms
    )
    assert search_url.build_initial_search_url(
        query, now_ms=now_ms
    ) == legacy.build_search_url(query, now_ms)


def test_urlbuild_helpers_match_legacy():
    legacy = search_url._load_legacy()
    assert urlbuild.USER_AGENT == legacy.USER_AGENT
    assert urlbuild.build_t_samp() == legacy.build_t_samp()
    for s in ("天气 test", "a+b", "札幌 駅/ホーム"):
        assert urlbuild.java_urlencode(s) == legacy.java_urlencode(s)
        assert urlbuild.uri_encode(s) == legacy.uri_encode(s)


# ---------------------------------------------------------------------------
# Runtime independence from the development workspace
# ---------------------------------------------------------------------------

def test_runtime_does_not_load_legacy_modules():
    code = (
        "import sys\n"
        "from baidu_search import search_url\n"
        "url = search_url.build_initial_search_url('天气', now_ms=1700000000000)\n"
        "assert 'crypto' not in sys.modules\n"
        "assert 'baidu_legacy_search_probe' not in sys.modules\n"
        "assert not any('python-validation' in p for p in sys.path)\n"
        "assert url.startswith('https://m.baidu.com/s?tn=zbios&')\n"
        "print('ok')\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        timeout=60,
    )
    assert proc.returncode == 0, proc.stderr
    assert "ok" in proc.stdout


# ---------------------------------------------------------------------------
# JSON schema compatibility with the round-17 saved sample
# ---------------------------------------------------------------------------

def _mask_time_dependent(data):
    """Mask fields that embed the (time-dependent) first-page URL."""
    data = json.loads(json.dumps(data, ensure_ascii=False))
    for page in data.get("pages", []):
        if page.get("page_number") == 1:
            page["source_url"] = "<masked>"
            page["final_url"] = "<masked>"
    for key in ("results", "ads", "cards", "unknown_elements"):
        for item in data.get(key, []):
            if item.get("page_number") == 1:
                item["source_page_url"] = "<masked>"
    for item in data.get("related_searches", []):
        if item.get("page_number") == 1:
            item["source_page_url"] = "<masked>"
    return data


def test_aggregated_json_matches_round17_sample():
    from conftest import make_client, tianqi_fixture_map
    from fake_http import FakeSession, pn_router

    saved = json.loads(CLIENT_SAMPLE.read_text(encoding="utf-8"))
    session = FakeSession(pn_router(tianqi_fixture_map()))
    with make_client(session) as client:
        result = client.search("天气", max_pages=3)
    current = result.to_dict()
    assert list(current.keys()) == list(saved.keys())
    assert list(current["diagnostics"].keys()) == list(
        saved["diagnostics"].keys()
    )
    assert _mask_time_dependent(current) == _mask_time_dependent(saved)


def test_parser_output_matches_round16_samples():
    from baidu_parser import parse_search_results

    samples_dir = PARSER_PROJECT / "samples"
    fixtures_dir = PARSER_PROJECT / "tests" / "fixtures"
    cases = [
        ("tianqi_p1.results.json", "tianqi_p1.html", "天气"),
        ("weather_en.results.json", "weather_en.html", "weather"),
    ]
    for sample_name, fixture_name, query in cases:
        saved = json.loads((samples_dir / sample_name).read_text(encoding="utf-8"))
        page = parse_search_results(
            (fixtures_dir / fixture_name).read_bytes(),
            query=query,
            page_url="https://m.baidu.com/s",
        )
        current = page.to_dict()
        assert list(current.keys()) == list(saved.keys())
        # Order, titles, URLs, ranks and card types must be identical.
        def signature(entries):
            return [
                (
                    e.get("type"),
                    e.get("title"),
                    e.get("url"),
                    e.get("display_position"),
                    e.get("organic_rank"),
                )
                for e in entries
            ]

        assert signature(current["results"]) == signature(saved["results"])
        assert signature(current["cards"]) == signature(saved["cards"])
        assert current["page"]["pn"] == saved["page"]["pn"]
        assert current["page"]["next_pn"] == saved["page"]["next_pn"]


# ---------------------------------------------------------------------------
# Security: no secret leakage, redirect host enforcement
# ---------------------------------------------------------------------------

def test_cookie_values_never_leak_into_errors():
    from conftest import make_client
    from fake_http import FakeResponse, FakeSession

    sentinel = "SECRET_COOKIE_VALUE_12345"

    def router(url):
        return FakeResponse(
            b"forbidden",
            status=403,
            url=url,
            headers={
                "Content-Type": "text/html",
                "Set-Cookie": "BAIDUID={}; path=/".format(sentinel),
            },
            cookies_to_set={"BAIDUID": sentinel},
        )

    session = FakeSession(router)
    with make_client(session) as client:
        result = client.search("天气", max_pages=2)
    blob = json.dumps(result.to_dict(), ensure_ascii=False)
    assert sentinel not in blob
    assert result.pages_fetched == 0
    assert result.errors[0]["kind"] == "access_restricted"


def test_redirect_to_external_host_is_rejected():
    from conftest import make_client
    from baidu_search.errors import RedirectError
    from fake_http import FakeResponse, FakeSession

    def router(url):
        return FakeResponse(
            b"<html></html>",
            status=200,
            url="https://evil.example.com/landing",
            history=[object()],  # one redirect hop happened
        )

    session = FakeSession(router)
    with make_client(session) as client:
        with pytest.raises(RedirectError):
            client.search_page("天气")
