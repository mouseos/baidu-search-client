"""Command line interface.

Live mode::

    python -m baidu_search --query "天气" --pages 3 --output results.json

Offline mode (no network; parse a saved HTML page through the same
aggregation pipeline)::

    python -m baidu_search --from-html page.html --query "天气"

JSON is written as UTF-8 with ``ensure_ascii=False`` so Japanese /
Chinese text stays readable.  Without ``--output`` the JSON goes to
stdout.  Exit status is 0 when at least one page was fetched and
parsed, 2 when fetching failed completely (details are in
``diagnostics.errors`` of the emitted JSON), 1 for usage errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from . import models
from .client import BaiduSearchClient
from .models import AggregatedSearch, SinglePageResult
from .transport import TransportResponse


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="baidu_search",
        description="Baidu (Android-app flow) search client: "
        "fetch result pages and emit structured JSON.",
    )
    parser.add_argument("--query", required=True, help="search query text")
    parser.add_argument(
        "--pages",
        type=int,
        default=1,
        help="maximum number of result pages to fetch (default: 1)",
    )
    parser.add_argument(
        "--output",
        help="write JSON to this file (UTF-8); default: stdout",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=25.0,
        help="HTTP timeout in seconds (default: 25)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print a short diagnostics summary to stderr",
    )
    parser.add_argument(
        "--from-html",
        metavar="FILE",
        help="offline mode: parse a saved search-result HTML file "
        "instead of fetching (single page)",
    )
    parser.add_argument(
        "--page-url",
        help="source URL of the --from-html file (for relative-URL "
        "resolution and pn detection)",
    )
    return parser


def _offline_search(args) -> AggregatedSearch:
    raw = Path(args.from_html).read_bytes()
    page_url = args.page_url or "https://m.baidu.com/s"
    with BaiduSearchClient(min_request_interval=0) as client:
        response = TransportResponse(
            status_code=200, final_url=page_url, headers={}, body=raw
        )
        try:
            single = client._parse_response(
                response, query=args.query, requested_url=page_url
            )
            singles = [single]
            errors: list = []
        except Exception as exc:  # BaiduSearchError and friends
            from .errors import BaiduSearchError

            if isinstance(exc, BaiduSearchError):
                errors = [exc.to_dict()]
            else:
                errors = [
                    {"kind": "error", "message": str(exc), "url": page_url,
                     "status_code": None}
                ]
            singles = []
    return models.aggregate(
        args.query, pages_requested=1, singles=singles, errors=errors
    )


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.from_html:
        result = _offline_search(args)
    else:
        with BaiduSearchClient(
            timeout=args.timeout, min_request_interval=1.0
        ) as client:
            result = client.search(args.query, max_pages=args.pages)

    payload = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload + "\n", encoding="utf-8")
    else:
        sys.stdout.write(payload + "\n")

    if args.verbose:
        diag = result.to_dict()["diagnostics"]
        print(
            "pages_fetched={} results={} ads={} cards={} unknown={} "
            "duplicates={} errors={}".format(
                result.pages_fetched,
                len(result.results),
                len(result.ads),
                len(result.cards),
                len(result.unknown_elements),
                diag["duplicates"],
                len(diag["errors"]),
            ),
            file=sys.stderr,
        )
    return 0 if result.pages_fetched >= 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
