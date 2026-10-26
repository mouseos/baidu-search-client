# baidu_search — Baidu search client (unofficial)

End-to-end Python client that reproduces the Baidu Android app's
web-search flow: APK-derived URL generation with the `ant_ct` token,
HTTP transport with a persistent session, server-driven pagination,
and structured JSON output via the companion
[`baidu-parser`](../baidu-search-parser/) package.

This is an unofficial reimplementation based on static analysis of
`com.baidu.searchbox` 15.57.1.10; it is not an official Baidu API.
See the repository root [README](../README.md) for installation
(including why `baidu-parser` must be installed from this repository
and not from PyPI), usage, limitations, and the
[provenance and licensing notes](../docs/provenance-and-licensing.md).

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

License: MIT (original code only; see the repository LICENSE).
