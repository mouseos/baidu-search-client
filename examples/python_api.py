"""Live search example (performs real HTTP requests to Baidu).

Install first (see the repository README), then run:

    python examples/python_api.py
"""

import json

from baidu_search import BaiduSearchClient


def main() -> None:
    with BaiduSearchClient() as client:
        result = client.search(
            "天气",
            max_pages=3,
        )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
