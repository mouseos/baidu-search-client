# Examples

- `python_api.py` — the minimal live-search example using
  `BaiduSearchClient` (performs real HTTP requests).
- `offline_parse.py` — parses a bundled, redacted HTML fixture with
  `baidu_parser` only; no network access. Prints a summary and the
  first organic result.
- `example_output.json` — the full structured JSON produced by
  `baidu_parser` for the `tianqi_p1.html` fixture (query "天气",
  first page), generated offline from the fixture in this repository.
