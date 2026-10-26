# baidu-search-client

Python client for Baidu Search. It fetches search-result pages the way the Baidu Android app does, follows the next-page links the server returns, and gives back structured JSON: organic results, ads, special cards, and related searches, kept separate.

This is an unofficial, independent implementation. It is not a Baidu product or API.

## Packages

| Distribution | Import | Contents |
|---|---|---|
| `baidu-search` | `baidu_search` | Search client: URL generation, HTTP transport, pagination, JSON aggregation |
| `baidu-parser` | `baidu_parser` | Offline parser for Baidu search-result HTML. No network access |

`baidu_search` depends on `baidu_parser`. Neither package is on PyPI.

## Install

Python 3.12 is the verified version (`requires-python` declares >=3.10). Runtime dependencies are `requests` and `pycryptodome` for the client, `lxml` for the parser.

Build both wheels from this repository, then install with the local `dist` directory as the package source:

```bash
git clone https://github.com/mouseos/baidu-search-client.git
cd baidu-search-client

python3 -m pip install build
python3 -m build --outdir dist baidu-search-parser
python3 -m build --outdir dist baidu-search-client

python3 -m pip install --find-links dist baidu-search
```

Prebuilt wheels are attached to the [v1.0.0 release](https://github.com/mouseos/baidu-search-client/releases/tag/v1.0.0). Download both wheel files into one directory and run the same `pip install --find-links <dir> baidu-search` command there. To install only the parser, use `pip install --find-links dist baidu-parser`.

## Usage

```python
from baidu_search import BaiduSearchClient

with BaiduSearchClient() as client:
    result = client.search("天气", max_pages=3)

print(result.to_dict())
```

`client.search_page(query)` fetches a single page. The output of `search()` contains `query`, `pages_requested`, `pages_fetched`, `results`, `ads`, `cards`, `related_searches`, `unknown_elements`, `pages`, and `diagnostics`. Each result carries `title`, `url` (the external URL as written in the HTML), `click_url` (the Baidu redirect URL, kept as-is), `snippet`, `site_name`, `date`, and rank fields (`display_position`, `organic_rank`, `global_organic_rank`). Fields the HTML does not provide are `null`.

CLI:

```bash
python -m baidu_search --query "天气" --pages 3 --output results.json
```

Options: `--timeout`, `--verbose`, and `--from-html <file>` to convert a saved HTML page offline. Output is UTF-8 JSON with non-ASCII text written as-is.

The parser also works on its own, on saved HTML:

```python
from baidu_parser import parse_search_results

page = parse_search_results(html, query="天气", page_url=source_url)
print(page.to_dict())
```

## Behavior

The client makes HTTPS requests to `m.baidu.com` and keeps one session per search: cookies from the first response are sent with later pages, and no cookie values are written to logs or output. Pagination follows the next-page URL found in each page's HTML; the client does not build `pn=` URLs itself, and it stops at the requested page count, when no next URL exists, when a URL repeats, or on an error or access restriction (403, 429, CAPTCHA). If a later page fails, the pages already fetched are returned with the error recorded in `diagnostics.errors`. There are no automatic retries.

## Limitations

- Requests reproduce the app behavior that could be determined statically. Device-dependent parameters are not sent, so requests are not identical to a real device's.
- One approximation: the signed timestamp uses the current Unix time in seconds, with the app's calibration offset taken as 0 because the offset cannot be observed off-device.
- The ad classifier was checked against saved pages and a synthetic fixture. No live ad result appeared in the saved pages, so ad separation has not been verified against live ads.
- Weather-card values and AI-answer text are drawn by the app at runtime and are not in the HTML, so the parser cannot return them.
- Dates come back as the display strings in the HTML.
- Baidu can change its HTML or request format at any time. Result layouts the parser does not know are reported under `unknown_elements`.
- Verified on Linux with Python 3.12 only.

## Tests

Both suites run offline (HTTP is mocked, parsing uses saved fixtures):

```bash
python3 -m pytest baidu-search-parser/tests -q   # 31 tests
python3 -m pytest baidu-search-client/tests -q   # 65 tests
```

Design notes, the full JSON schema, the HTML structure analysis, and the security review are in [docs/](docs/).

## License

MIT, for the original code in this repository only. It does not cover Baidu's app, services, or content. Which parts are derived from the app and what to check before redistributing are recorded in [docs/provenance-and-licensing.md](docs/provenance-and-licensing.md).
