# baidu-search-client

Unofficial Python client for Baidu Search with structured results,
pagination, and HTML parsing.

> **Unofficial.** This project is an independent reimplementation based on
> static analysis of the Baidu Android app (`com.baidu.searchbox`
> 15.57.1.10). It is **not** an official Baidu product or API, and it is
> not affiliated with or endorsed by Baidu. Behavior was reproduced from
> the app's own search flow and verified against the live service with a
> small number of anonymous requests; see
> [docs/provenance-and-licensing.md](docs/provenance-and-licensing.md)
> for what is APK-derived, what was measured, and the licensing notes.

## What this repository contains

Two Python packages, developed and versioned together:

| Distribution | Import package | Purpose |
|---|---|---|
| `baidu-search` (in `baidu-search-client/`) | `baidu_search` | End-to-end search client: APK-derived URL generation, `ant_ct` token, HTTP transport with a persistent session, pagination, aggregation to JSON |
| `baidu-parser` (in `baidu-search-parser/`) | `baidu_parser` | Offline parser that turns Baidu (wise) search-result HTML into structured JSON. No network access |

`baidu_search` depends on `baidu_parser`. Neither package is published on
PyPI; install them from this repository as described below.

## Requirements

- Python **3.12** (the only version verified end-to-end so far;
  `requires-python` is declared as `>=3.10`, but other versions are not
  verified)
- Runtime dependencies: `requests`, `pycryptodome` (client),
  `lxml` (parser)

## Installation

`baidu-parser` is **not** available from PyPI, so pip cannot resolve it
from the internet. Build both wheels from this repository and let pip
resolve the dependency locally:

```bash
git clone https://github.com/mouse-soft/baidu-search-client.git
cd baidu-search-client

python3 -m pip install build
python3 -m build --outdir dist baidu-search-parser
python3 -m build --outdir dist baidu-search-client

python3 -m pip install --find-links dist baidu-search
# baidu-parser is resolved from ./dist automatically
```

Tagged releases, when published, are listed on the GitHub Releases
page with prebuilt wheels attached; with both wheel files downloaded
into a directory, the same `pip install --find-links <dir> baidu-search`
command works without building.

To install only the parser:

```bash
python3 -m pip install --find-links dist baidu-parser
```

## Python API

```python
from baidu_search import BaiduSearchClient

with BaiduSearchClient() as client:
    result = client.search(
        "天气",
        max_pages=3,
    )

print(result.to_dict())
```

A single page can be fetched with `client.search_page(query)`, which
returns the parser's structured page object. The parser can also be used
on its own, without any network access:

```python
from baidu_parser import parse_search_results

page = parse_search_results(html_bytes, query="天气",
                            page_url="https://m.baidu.com/s?word=...")
print(page.to_dict())
```

## CLI

```bash
python -m baidu_search \
  --query "天气" \
  --pages 3 \
  --output results.json
```

Options include `--timeout`, `--verbose`, and `--from-html <file>` for
fully offline conversion of a saved HTML page. The parser has its own
CLI: `python -m baidu_parser --input search.html --query "天气" --output results.json`.
Output is UTF-8 JSON with non-ASCII text written as-is
(`ensure_ascii=False`).

## JSON output

The aggregated result of `BaiduSearchClient.search(...)` has this shape
(see [docs/client/json-output-schema.md](docs/client/json-output-schema.md)
for the full schema):

```json
{
  "query": "天气",
  "pages_requested": 3,
  "pages_fetched": 3,
  "results": [],
  "ads": [],
  "cards": [],
  "related_searches": [],
  "unknown_elements": [],
  "pages": [],
  "diagnostics": { "duplicates": 0, "errors": [], "warnings": [] }
}
```

Each result item keeps the fields produced by the parser, including
`display_position`, `organic_rank`, `global_organic_rank`, `title`,
`url` (the external URL exactly as the HTML states it), `click_url`
(the Baidu redirect URL, preserved verbatim), `url_source`, `snippet`,
`site_name`, `date`, and a `duplicate` flag. Values that the HTML does
not provide are `null`; nothing is reconstructed by guessing.

## Pagination

Pagination follows the **server-issued** next-page URL embedded in the
HTML (`page.next_url`). The client never synthesizes `pn=` URLs and
never normalizes the URL, so server-issued parameters (including
`ant_ct`) are passed through untouched. Fetching stops when there is no
next URL, the requested page count is reached, a URL repeats (cycle),
the URL is invalid or points to an unexpected host, a transport error
occurs, or the server returns an access restriction. Duplicates across
pages are detected by exact URL match and flagged, not deleted.

## Cookies and sessions

One `requests.Session` is used for the whole search: cookies set by the
first response are kept and sent on subsequent pages, exactly as in the
validated anonymous measurements. No cookie values are fabricated, and
cookie values never appear in logs, diagnostics, or error messages.
Use the client as a context manager (or call `close()`) to release the
session.

## Error handling

Failures are classified instead of being hidden behind HTTP 200:
connection/DNS errors, TLS errors, timeouts, HTTP errors, access
restrictions (403/429/CAPTCHA or verification pages), responses that are
HTTP 200 but not search-result HTML, HTML parse failures, zero results,
pagination cycles, invalid next-page URLs, and redirects that leave
`*.baidu.com` (rejected). If a later page fails, the pages already
fetched are still returned, with the error recorded in
`diagnostics.errors`. There are no automatic retries.

## Running the tests

The test suites are fully offline (HTTP is mocked; parsing uses
bundled, redacted HTML fixtures). CI never contacts Baidu's servers.

```bash
python3 -m pip install --find-links dist baidu-search pytest
python3 -m pytest baidu-search-parser/tests -q   # 31 tests
python3 -m pytest baidu-search-client/tests -q   # 65 tests
```

The client suite includes consistency tests proving that the vendored
URL builder and `ant_ct` implementation produce byte-identical output
to the original validated probes, kept under
`baidu-search-client/tests/legacy_reference/`.

## Limitations

- The `ant_ct` timestamp uses the APK's calibrated-time formula with
  the calibration offset approximated as 0 (the offset cannot be
  observed outside a device). The timestamp unit is **seconds**.
- Only the statically reproducible subset of the app's request is
  reproduced; device-dependent parameters are not sent. Requests are
  therefore not byte-identical to a real device's.
- Ads are separated by the parser's classifier, which was verified
  against the ad markup conventions present in the measured pages'
  CSS and against a synthetic fixture; no live ad result was present
  in the measured pages.
- Weather-card detail values and AI-answer body text are rendered
  client-side in the app and are not present in the static HTML, so
  they cannot be extracted.
- Dates are returned as the display strings found in the HTML.
- Baidu may change the HTML structure or the request format at any
  time; unknown result templates are reported as `unknown_elements`
  rather than being guessed at.
- Verified only on Linux with Python 3.12.

## Documentation

Design and verification documents are under [`docs/`](docs/):
integration architecture, HTTP integration, pagination integration,
JSON schema, HTML structure analysis, result classification, URL
extraction, dependency audit, security review, and the
provenance/licensing notes.

## License

The original code in this repository is released under the
[MIT License](LICENSE). The MIT License does **not** extend to Baidu's
app, services, or content; see
[docs/provenance-and-licensing.md](docs/provenance-and-licensing.md).
