# baidu_parser — Baidu search-result HTML parser

Parses Baidu (wise) search-result HTML — as served to the Baidu
Android app — into structured JSON: organic results, ads, special
cards (weather, knowledge graph, encyclopedia, dictionary, AI answer,
video, live, forum, notes, official accounts), related searches, and
pagination. Pure HTML processing; **no network access**.

```python
from baidu_parser import parse_search_results

page = parse_search_results(html_bytes, query="天气",
                            page_url="https://m.baidu.com/s?word=...")
print(page.to_dict())
```

```bash
python -m baidu_parser --input search.html --query "天气" --output results.json
```

External URLs are reported exactly as the HTML states them; Baidu
redirect (click-tracking) URLs are preserved verbatim in `click_url`
and never rewritten or guessed. Unknown templates are reported as
unknown elements rather than being forced into a category.

Requires Python 3.12 (verified). Runtime dependency: `lxml` only.

This package is not published on PyPI; install it from this
repository as described in the root [README](../README.md).
See [docs/parser/](../docs/parser/) for the HTML structure analysis,
classification rules, URL extraction, and validation report.

License: MIT (original code only; see the repository LICENSE).
