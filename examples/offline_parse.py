"""Offline parsing example: no network access.

Parses one of the bundled, redacted HTML fixtures with baidu_parser
and prints a short summary plus the first organic result.

    python examples/offline_parse.py
"""

import json
from pathlib import Path

from baidu_parser import parse_search_results

FIXTURE = (
    Path(__file__).resolve().parent.parent
    / "baidu-search-parser"
    / "tests"
    / "fixtures"
    / "tianqi_p1.html"
)


def main() -> None:
    page = parse_search_results(
        FIXTURE.read_bytes(),
        query="天气",
        page_url="https://m.baidu.com/s?word=%E5%A4%A9%E6%B0%94",
    )
    data = page.to_dict()
    print("results:", len(data["results"]))
    print("cards:", len(data["cards"]))
    print("related_searches:", len(data["related_searches"]))
    print("next_url present:", data["page"]["next_url"] is not None)
    if data["results"]:
        print(json.dumps(data["results"][0], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
