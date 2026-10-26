"""Error taxonomy: each failure mode is distinguished, and HTTP 200
alone never counts as success.
"""

import pytest
import requests

from baidu_search import errors
from conftest import fixture_bytes, make_client
from fake_http import FakeResponse, FakeSession


def _client_returning(outcome, **client_kwargs):
    def route(url: str):
        if isinstance(outcome, Exception):
            return outcome
        return outcome

    return make_client(FakeSession(route), **client_kwargs)


def test_http_403_is_access_restricted_and_stops():
    client = _client_returning(FakeResponse(b"forbidden", status=403))
    with pytest.raises(errors.AccessRestrictedError):
        client.search_page("天气")
    result = client.search("天气", max_pages=3)
    assert result.pages_fetched == 0
    errs = result.to_dict()["diagnostics"]["errors"]
    assert errs[0]["kind"] == "access_restricted"
    assert errs[0]["status_code"] == 403


def test_http_429_is_access_restricted():
    client = _client_returning(FakeResponse(b"slow down", status=429))
    with pytest.raises(errors.AccessRestrictedError):
        client.search_page("天气")


def test_http_500_is_http_error():
    client = _client_returning(FakeResponse(b"oops", status=500))
    with pytest.raises(errors.HttpStatusError) as excinfo:
        client.search_page("天气")
    assert excinfo.value.kind == "http_error"
    assert not isinstance(excinfo.value, errors.AccessRestrictedError)


def test_timeout():
    client = _client_returning(requests.ReadTimeout("read timed out"))
    with pytest.raises(errors.BaiduTimeoutError):
        client.search_page("天气")
    result = client.search("天气", max_pages=2)
    assert result.to_dict()["diagnostics"]["errors"][0]["kind"] == "timeout"


def test_dns_error():
    client = _client_returning(
        requests.ConnectionError(
            "HTTPSConnectionPool: Failed to resolve 'm.baidu.com' "
            "([Errno -2] Name or service not known)"
        )
    )
    with pytest.raises(errors.DnsResolutionError):
        client.search_page("天气")


def test_connection_error():
    client = _client_returning(
        requests.ConnectionError("Connection reset by peer")
    )
    with pytest.raises(errors.ConnectionFailedError):
        client.search_page("天气")


def test_tls_error():
    client = _client_returning(
        requests.exceptions.SSLError("certificate verify failed")
    )
    with pytest.raises(errors.TlsError):
        client.search_page("天气")


def test_too_many_redirects():
    client = _client_returning(
        requests.exceptions.TooManyRedirects("Exceeded 30 redirects")
    )
    with pytest.raises(errors.RedirectError):
        client.search_page("天气")


def test_response_too_large():
    session_client = make_client(
        FakeSession(lambda url: FakeResponse(fixture_bytes("tianqi_p1.html"))),
        max_response_bytes=1024,
    )
    with pytest.raises(errors.ResponseTooLargeError):
        session_client.search_page("天气")


def test_not_search_result_html():
    client = _client_returning(
        FakeResponse(b"<html><body><p>just a page</p></body></html>")
    )
    with pytest.raises(errors.NotSearchResultError):
        client.search_page("天气")


def test_captcha_page_is_distinguished_from_results():
    body = (
        "<html><body><div>安全验证</div>"
        "<script src='https://wappass.baidu.com/static/captcha.js'>"
        "</script></body></html>"
    ).encode("utf-8")
    client = _client_returning(FakeResponse(body))
    with pytest.raises(errors.CaptchaDetectedError):
        client.search_page("天气")
    result = client.search("天气", max_pages=1)
    assert (
        result.to_dict()["diagnostics"]["errors"][0]["kind"]
        == "captcha_or_verification"
    )


def test_empty_results_page_is_data_not_exception():
    body = b'<html><body><div id="results"></div></body></html>'
    client = _client_returning(FakeResponse(body))
    single = client.search_page("存在しないクエリxyz")
    assert single.page.results == []
    result = client.search("存在しないクエリxyz", max_pages=1)
    assert result.pages_fetched == 1
    assert result.results == []
    assert "empty_results" in result.warnings
