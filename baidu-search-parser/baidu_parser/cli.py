"""Command line interface: convert a saved search HTML page to JSON.

    python -m baidu_parser --input search.html --query "天气" \
        --output results.json

No network access is performed.
"""

from __future__ import annotations

import argparse
import json
import sys

from .parser import parse_search_results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="baidu_parser",
        description="Parse a saved Baidu (APK/wise) search-result HTML page into JSON.",
    )
    parser.add_argument("--input", required=True, help="saved HTML file")
    parser.add_argument("--query", default=None, help="search query the page belongs to")
    parser.add_argument("--page-url", default=None, help="URL the HTML was fetched from")
    parser.add_argument("--output", default=None, help="write JSON here (default: stdout)")
    args = parser.parse_args(argv)

    with open(args.input, "rb") as fh:
        raw = fh.read()
    page = parse_search_results(raw, query=args.query, page_url=args.page_url)
    text = json.dumps(page.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
