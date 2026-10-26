"""baidu_search — end-to-end Baidu (Android-app flow) search client.

    from baidu_search import BaiduSearchClient

    with BaiduSearchClient() as client:
        result = client.search("天气", max_pages=3)
    print(result.to_dict())

The fetching side embeds the APK-derived URL generation and
``ant_ct`` implementation validated in ``work/python-validation/``
(vendored into :mod:`baidu_search.urlbuild` / :mod:`baidu_search.antct`
in round 18, with output-consistency tests against the originals);
the parsing side uses the ``baidu_parser`` package, declared as a
normal package dependency.
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
