"""URL generation must stay 1:1 with the validated legacy code."""

import urllib.parse

import pytest

from baidu_search import search_url


def _ant_ct_plaintext(url: str) -> str:
    # Round 18: decryption uses the vendored baidu_search.antct (the
    # legacy crypto.py is no longer loaded as a side effect).  The
    # vendored module's byte-identical output vs. the legacy module is
    # asserted separately in test_packaging_consistency.py.
    from baidu_search import antct

    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return antct.antct_decrypt(urllib.parse.unquote(qs["ant_ct"][0]))


def test_ant_ct_time_is_seconds_not_milliseconds():
    url = search_url.build_initial_search_url("天气", now_ms=1_761_400_000_123)
    plaintext = _ant_ct_plaintext(url)
    # t must be the *seconds* value (getCalibratedTime), never millis.
    assert plaintext.startswith("t=1761400000&w=")
    assert "1761400000123" not in plaintext


def test_ant_ct_w_is_md5_of_query():
    import hashlib

    url = search_url.build_initial_search_url("weather", now_ms=1_761_400_000_000)
    plaintext = _ant_ct_plaintext(url)
    assert plaintext.endswith("&w=" + hashlib.md5(b"weather").hexdigest())


def test_url_matches_legacy_builder_exactly():
    legacy = search_url._load_legacy()
    for query in ("天气", "札幌 天気", "weather"):
        assert search_url.build_initial_search_url(
            query, now_ms=1_700_000_000_000
        ) == legacy.build_search_url(query, 1_700_000_000_000)


def test_url_shape():
    url = search_url.build_initial_search_url("天气", now_ms=1_700_000_000_000)
    assert url.startswith("https://m.baidu.com/s?tn=zbios&")
    assert "word=%E5%A4%A9%E6%B0%94" in url
    assert "ant_ct=" in url
    assert "t_samp=" in url
    # device-derived parameters from the APK runtime stay absent
    for forbidden in ("cuid=", "cua=", "pkgname="):
        assert forbidden not in url


def test_user_agent_matches_legacy():
    assert search_url.user_agent() == search_url._load_legacy().USER_AGENT
