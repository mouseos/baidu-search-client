import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Reuse the parser project's measured fixtures verbatim.
PARSER_FIXTURES = (
    ROOT.parent / "baidu-search-parser" / "tests" / "fixtures"
)

TIANQI_PAGES = {
    0: "tianqi_p1.html",
    10: "tianqi_pn10.html",
    20: "tianqi_pn20.html",
}


def fixture_bytes(name: str) -> bytes:
    return (PARSER_FIXTURES / name).read_bytes()


def tianqi_fixture_map() -> dict[int, bytes]:
    return {pn: fixture_bytes(name) for pn, name in TIANQI_PAGES.items()}


def make_client(session, **kwargs):
    from baidu_search import BaiduSearchClient

    kwargs.setdefault("min_request_interval", 0)
    return BaiduSearchClient(session=session, **kwargs)
