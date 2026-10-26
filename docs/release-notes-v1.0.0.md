# Release notes — v1.0.0 (draft for the GitHub Release)

First public release of the unofficial Baidu Search client and parser.

## Contents

- `baidu-search` 1.0.0 (`baidu_search`): end-to-end search client —
  APK-derived URL generation and `ant_ct`, persistent-session HTTP
  transport, server-issued-URL pagination, multi-page aggregation to
  structured JSON, CLI (`python -m baidu_search`).
- `baidu-parser` 1.0.0 (`baidu_parser`): offline parser for Baidu
  (wise) search-result HTML — organic results, ads, 10 kinds of
  special cards, related searches, pagination.

## Verification at release time

- 96 automated tests pass (31 parser + 65 client), all offline
  (mocked HTTP, redacted fixtures).
- Wheels and sdists build cleanly; a clean virtual environment can
  install `baidu-search` from the wheels alone (`--find-links`) and
  run the API and CLI outside the source tree.
- Live end-to-end search was verified from the installed wheels
  (query "天气", up to 2 pages) during the packaging round.

## Notes

- Unofficial reimplementation based on static analysis of
  `com.baidu.searchbox` 15.57.1.10; not a Baidu product or API.
- `baidu-parser` is not on PyPI; install both wheels from this
  release (or build from source) so the dependency resolves locally.
- Verified on Linux / Python 3.12 only.
- Known limitations are listed in the repository README and
  `docs/client/known-limitations.md` / `docs/parser/known-limitations.md`.

## Assets

- `baidu_search-1.0.0-py3-none-any.whl`
- `baidu_parser-1.0.0-py3-none-any.whl`
