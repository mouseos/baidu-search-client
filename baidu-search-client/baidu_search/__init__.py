"""baidu_search — Python client for Baidu Search.

    from baidu_search import BaiduSearchClient

    with BaiduSearchClient() as client:
        result = client.search("天气", max_pages=3)
    print(result.to_dict())

URL generation and the ``ant_ct`` token live in
:mod:`baidu_search.urlbuild` and :mod:`baidu_search.antct`; HTML
parsing is done by the ``baidu_parser`` package.
"""

from . import errors
from .client import BaiduSearchClient
from .errors import BaiduSearchError
from .models import (
    CLIENT_NAME,
    CLIENT_VERSION,
    AggregatedSearch,
    PageRecord,
    SinglePageResult,
)

__version__ = CLIENT_VERSION

__all__ = [
    "BaiduSearchClient",
    "BaiduSearchError",
    "AggregatedSearch",
    "SinglePageResult",
    "PageRecord",
    "errors",
    "__version__",
]
