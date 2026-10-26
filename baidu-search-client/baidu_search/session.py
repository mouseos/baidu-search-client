"""HTTP session / cookie management.

One :class:`SearchSession` wraps one ``requests.Session``.  Cookies
set by the server are kept in the session's jar and automatically
sent with subsequent page requests (that is how ``requests`` works);
the client never invents cookie values.  Only cookie *names* are ever
exposed for diagnostics — values are never logged or serialised.
"""

from __future__ import annotations

from typing import Optional

import requests

from . import search_url

_DEFAULT_HEADERS = {
    "Accept": "text/html,*/*",  # same Accept as the validated probes
}


class SearchSession:
    """A closeable wrapper around ``requests.Session``."""

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        if session is None:
            session = requests.Session()
            session.headers.update(
                {"User-Agent": search_url.user_agent(), **_DEFAULT_HEADERS}
            )
        self._session = session

    @property
    def raw(self) -> requests.Session:
        """The underlying session (used by the transport layer)."""
        return self._session

    def cookie_names(self) -> list[str]:
        """Sorted cookie names currently held (values are never read)."""
        try:
            return sorted({c.name for c in self._session.cookies})
        except Exception:
            return []

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "SearchSession":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
