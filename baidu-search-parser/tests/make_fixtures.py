"""Generate excerpt fixtures from the measured HTML pages.

The originals in ``work/python-validation/response_samples/`` are kept
untouched.  Each fixture contains only the ``#results`` container, the
first ``.new-pagenav`` block and any ``.page-relative`` blocks of the
original page — the parts the parser reads.

Session-identifying values embedded in the HTML are redacted in the
fixtures (the originals are unchanged):

* ``baiduid`` values (click-URL path segments)
* ``ant_ct``, ``rsv_pq``, ``rsv_t``, ``rqid`` parameter values
* ``lid`` / ``fqid`` / ``eqid`` / ``w_qd`` / ``nsrc`` / ``sec`` / ``di``
  parameter values in link URLs
* ``extend_lid`` / ``searchid`` / ``pqid`` values in the various
  (multiply) percent-encoded JSON and URL forms they appear in

Structure-bearing parameters (``pn``, ``word``, ``tn`` …) are preserved
so pagination behaviour stays testable.

Usage:  python tests/make_fixtures.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from lxml import html as lhtml
from lxml import etree

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT.parent / "work" / "python-validation" / "response_samples"
OUT = Path(__file__).resolve().parent / "fixtures"

SOURCES = {
    "tianqi_p1.html": SAMPLES / "additional" / "search_天气.body.html",
    "tianqi_pn10.html": SAMPLES / "additional" / "page_pn10.body.html",
    "tianqi_pn20.html": SAMPLES / "additional" / "page_pn20.body.html",
    "sapporo.html": SAMPLES / "additional" / "search_札幌 天気.body.html",
    "weather_en.html": SAMPLES / "additional" / "search_weather.body.html",
}

REDACTIONS = [
    # baiduid as path segment or query value
    (re.compile(r"baiduid=[^&\"/\s]+"), "baiduid=REDACTED"),
    # server-issued opaque parameters
    (re.compile(r"(ant_ct|rsv_pq|rsv_t|rqid)=[^&\"\s]+"), r"\1=REDACTED"),
    # session / click identifiers in link URLs (& escaped as &amp; in attrs)
    (
        re.compile(r"((?:&amp;|&|\?)(?:lid|fqid|rfqid|pqid|eqid|w_qd|nsrc|sec|di)=)[^&\"\s]+"),
        r"\1REDACTED",
    ),
    # baiduid in percent-encoded URLs
    (re.compile(r"(baiduid%3D)[^%&\"\s]+"), r"\1REDACTED"),
    (re.compile(r"(baiduid%253D)[^%&\"\s]+"), r"\1REDACTED"),
    # extend_lid inside s-data JSON (plain or &quot;-serialised)
    (re.compile(r"(extend_lid[^0-9]{0,16})[0-9]{10,}"), r"\1REDACTED"),
    # "searchid":"<digits>" in &quot;-serialised JSON attributes
    (re.compile(r"((?:searchid|lid)&quot;:&quot;)[0-9]+"), r"\1REDACTED"),
    # percent-encoded lid/fqid inside double-encoded URLs
    (re.compile(r"((?:lid|fqid)%3D)[0-9]+"), r"\1REDACTED"),
    (re.compile(r"((?:lid|fqid)%253D)[0-9]+"), r"\1REDACTED"),
    # "lid":"<digits>" / "searchid":"<digits>" inside (encoded) JSON
    (re.compile(r"((?:lid|searchid)%22%3A%22)[0-9]+"), r"\1REDACTED"),
    (re.compile(r'((?:lid|searchid)"\s*:\s*")[0-9]+'), r"\1REDACTED"),
    # sessionId "lid[<digits>]_si[...]" forms
    (re.compile(r"(lid%5B)[0-9]+"), r"\1REDACTED"),
    (re.compile(r"(lid%255B)[0-9]+"), r"\1REDACTED"),
    (re.compile(r"(lid\[)[0-9]+"), r"\1REDACTED"),
    # double-encoded "lid":"<digits>" / "searchid":"<digits>"
    (re.compile(r"((?:lid|searchid)%2522%253A%2522)[0-9]+"), r"\1REDACTED"),
    # "search_id":"<digits>" / "sc_searchId":"<digits>" (encoded and plain)
    (re.compile(r"((?:sc_searchId|search_id)%22%3A%22)[0-9]+"), r"\1REDACTED"),
    (re.compile(r'((?:sc_searchId|search_id)"\s*:\s*")[0-9]+'), r"\1REDACTED"),
    # session: '<digits>' in inline script data
    (re.compile(r"(session:\s*')[0-9]+"), r"\1REDACTED"),
]


def sanitise(text: str) -> str:
    for pattern, repl in REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def build(source: Path) -> str:
    doc = lhtml.fromstring(source.read_bytes())
    parts = ["<!DOCTYPE html><html><head><meta charset=\"utf-8\">",
             f"<title>fixture excerpt of {source.name}</title></head><body>"]
    results = doc.xpath('//*[@id="results"]')
    if results:
        parts.append(etree.tostring(results[0], encoding="unicode"))
    navs = doc.xpath('//*[contains(@class,"new-pagenav")]')
    if navs:
        parts.append(etree.tostring(navs[0], encoding="unicode"))
    for block in doc.xpath('//*[contains(@class,"page-relative")]'):
        parts.append(etree.tostring(block, encoding="unicode"))
    parts.append("</body></html>")
    return sanitise("".join(parts))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, source in SOURCES.items():
        if not source.exists():
            print(f"MISSING SOURCE: {source}", file=sys.stderr)
            return 1
        text = build(source)
        (OUT / name).write_text(text, encoding="utf-8")
        print(f"wrote {name}: {len(text)} chars")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
