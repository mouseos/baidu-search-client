import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Fixture name -> (query, page_url).  Excerpt fixtures come from the
# measured pages; see make_fixtures.py for provenance and redactions.
PAGES = {
    "tianqi_p1.html": ("天气", "https://m.baidu.com/s?word=%E5%A4%A9%E6%B0%94"),
    "tianqi_pn10.html": ("天气", "https://m.baidu.com/s?word=%E5%A4%A9%E6%B0%94&pn=10"),
    "tianqi_pn20.html": ("天气", "https://m.baidu.com/s?word=%E5%A4%A9%E6%B0%94&pn=20"),
    "sapporo.html": ("札幌 天気", "https://m.baidu.com/s?word=%E6%9C%AD%E5%B9%8C%20%E5%A4%A9%E6%B0%94"),
    "weather_en.html": ("weather", "https://m.baidu.com/s?word=weather"),
}


def load_fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def parse_fixture(name: str):
    from baidu_parser import parse_search_results

    query, page_url = PAGES[name]
    return parse_search_results(load_fixture(name), query=query, page_url=page_url)
