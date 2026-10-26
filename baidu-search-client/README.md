# baidu_search — Baidu search client (unofficial)

Python client for Baidu Search. It builds the same search URLs as
the Baidu Android app, keeps one session across pages, follows the
next-page links the server returns, and returns structured JSON via
the companion [`baidu-parser`](../baidu-search-parser/) package.

Unofficial: an independent implementation, not a Baidu product or
API. See the repository root [README](../README.md) for installation
and usage, and
[docs/provenance-and-licensing.md](../docs/provenance-and-licensing.md)
for what is derived from the app.

Quick start:

```python
from baidu_search import BaiduSearchClient

with BaiduSearchClient() as client:
    result = client.search("天气", max_pages=3)

print(result.to_dict())
```

```bash
python -m baidu_search --query "天气" --pages 3 --output results.json
```

Requires Python 3.12 (verified). Runtime dependencies: `requests`,
`pycryptodome`, `baidu-parser>=1.0.0,<2.0.0`.

License: MIT (see the repository LICENSE).
