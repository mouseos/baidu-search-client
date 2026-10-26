"""Pagination extraction from ``div.new-pagenav``.

Measured structure (see ../pagination-structure.md):

* First page: one ``.new-pagenav`` block with only a next-page anchor
  (``pn=10``).  No current-page label.
* Later pages: the block is repeated by SSR (observed 4 copies) — only
  the first is used.  ``a.new-prepage`` = previous page,
  ``a.new-firstpage`` = first page (present from page 3),
  ``a.new-nextpage`` = next page, ``span.new-nowpage`` shows
  ``第 N 页``.  On the last measured page the right cell is empty,
  i.e. there is no next page.
* Server-issued URLs are kept verbatim (they contain server-generated
  ``ant_ct`` / ``rsv_pq`` values; nothing is regenerated).
"""

from __future__ import annotations

import re
from typing import Optional

from . import urls as urltools
from .models import PageInfo

_NOWPAGE_RE = re.compile(r"第\s*(\d+)\s*页")


def _first_anchor(nav, cls: str):
    found = nav.xpath(f'.//a[contains(@class,"{cls}")]')
    return found[0] if found else None


def extract_pagination(doc, source_url: Optional[str]) -> PageInfo:
    page = PageInfo()
    navs = doc.xpath('//*[contains(@class,"new-pagenav")]')
    nav = navs[0] if navs else None

    next_url = prev_url = first_url = None
    page_number: Optional[int] = None
    if nav is not None:
        anchor = _first_anchor(nav, "new-nextpage")
        if anchor is None:
            anchor = _first_anchor(nav, "new-nextpage-only")
        if anchor is not None:
            next_url = urltools.resolve(anchor.get("href"), source_url)
        anchor = _first_anchor(nav, "new-prepage")
        if anchor is not None:
            prev_url = urltools.resolve(anchor.get("href"), source_url)
        anchor = _first_anchor(nav, "new-firstpage")
        if anchor is not None:
            first_url = urltools.resolve(anchor.get("href"), source_url)
        labels = nav.xpath('.//*[contains(@class,"new-nowpage")]')
        if labels:
            text = "".join(labels[0].itertext())
            match = _NOWPAGE_RE.search(text)
            if match:
                page_number = int(match.group(1))


    source_pn = urltools.pn_of(source_url)
    if page_number is None:
        page_number = (source_pn // 10 + 1) if source_pn else 1

    page.page_number = page_number
    page.pn = source_pn if source_pn is not None else (page_number - 1) * 10
    page.is_first_page = page.pn == 0
    page.next_url = next_url
    page.previous_url = prev_url
    page.first_url = first_url
    page.next_pn = urltools.pn_of(next_url)
    if page.next_url and page.next_pn is None and "pn=" not in page.next_url:
        page.next_pn = None
    page.previous_pn = urltools.pn_of(prev_url)
    if prev_url and page.previous_pn is None:
        page.previous_pn = 0  # server omits pn for the first page
    return page
