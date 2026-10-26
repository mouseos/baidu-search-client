# baidu-search-client

Python client for Baidu Search with pagination and structured results. It fetches search-result pages, follows the next-page links the server returns, and parses each page into JSON with organic results, ads, and special cards kept separate.

Unofficial and independent; not a Baidu product or API.

## Installation

The repository contains two packages: `baidu-search` (the client, import name `baidu_search`) and `baidu-parser` (the HTML parser, import name `baidu_parser`, no network access). `baidu_search` depends on `baidu_parser`. Neither package is on PyPI.

Requires Python 3.12 (verified; `requires-python` declares >=3.10). Install both from a clone:

```bash
git clone https://github.com/mouseos/baidu-search-client.git
cd baidu-search-client
python3 -m pip install ./baidu-search-parser ./baidu-search-client
```

pip installs `requests` and `pycryptodome` (client) and `lxml` (parser) from PyPI, and `baidu-parser` from the local directory. To install only the parser, run `python3 -m pip install ./baidu-search-parser`.

Building wheels instead, and installing from the wheels attached to the v1.0.0 release, are covered in [docs/development.md](docs/development.md).

## Usage

```python
from baidu_search import BaiduSearchClient

with BaiduSearchClient() as client:
    results = client.search("天气", max_pages=3)

print(results.to_dict())
```

`client.search_page(query)` fetches a single page.

```bash
python -m baidu_search --query "天气" --pages 3 --output results.json
```

Without `--output`, the JSON goes to stdout. `--from-html <file>` parses a saved HTML page offline, through the same pipeline. The parser can also be used on its own: `from baidu_parser import parse_search_results`.

The client sends HTTPS requests to `m.baidu.com`. It keeps one session per search, so cookies from the first response are sent with later pages. It does not retry: on an access restriction (403, 429, or a verification page) it stops and records the error in `diagnostics.errors`, returning any pages already fetched.

## Output

`search()` returns an object; `to_dict()` gives:

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

Each result has `title`, `url` (the external URL as written in the HTML), `click_url` (the Baidu redirect URL, kept unchanged), `snippet`, `site_name`, `date`, and rank fields (`display_position`, `organic_rank`, `global_organic_rank`). Values the HTML does not provide are `null`. The full schema is in [docs/client/json-output-schema.md](docs/client/json-output-schema.md).

Notes:

- Pagination follows the next-page URL found in each page's HTML; the client does not build page URLs itself. Results that appear on more than one page are flagged as duplicates, not removed.
- Dates are the display strings found in the HTML.
- Weather-card values and AI-answer text are drawn by the app at runtime and are not in the HTML, so they are never returned.
- Page layouts the parser does not know are reported under `unknown_elements`.

## Development / Tests

Both test suites run offline:

```bash
python3 -m pytest baidu-search-parser/tests -q   # 31 tests
python3 -m pytest baidu-search-client/tests -q   # 65 tests
```

Design notes, the HTML structure analysis, and the security review are in [docs/](docs/).

## License

MIT — see [LICENSE](LICENSE). It covers the code in this repository only, not Baidu's app, services, or content; see [docs/provenance-and-licensing.md](docs/provenance-and-licensing.md).
