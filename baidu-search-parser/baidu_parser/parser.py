"""Entry point: parse a Baidu (APK / wise) search-result HTML page.

Usage::

    from baidu_parser import parse_search_results
    page = parse_search_results(html, query="天气", page_url=source_url)
    data = page.to_dict()

The parser performs no network access.  It expects the HTML produced by
the mobile ("wise") search endpoint the Android app renders.
"""

from __future__ import annotations

from typing import Optional, Union

from lxml import html as lhtml

from . import classifiers, extractors
from . import urls as urltools
from .models import (
    CardEntry,
    CardItem,
    PageInfo,
    RelatedSearch,
    ResultEntry,
    SearchPage,
    SiteLink,
    UnknownElement,
)
from .pagination import extract_pagination

PARSER_VERSION = "1.0.0"

_CRESULT_XPATH = (
    '//*[contains(concat(" ",normalize-space(@class)," ")," c-result ")]'
)


def _int_or_none(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_result(el, category: str, detail: str, base_url, position: int) -> ResultEntry:
    title = extractors.extract_title(el)
    url, url_source, fusion_site = extractors.extract_external_url(el)
    snippet, prefix_date = extractors.extract_snippet(el)
    site_name, sdata_date = extractors.extract_source(el)
    click_raw = extractors.extract_click_url(el, title)
    click_url = urltools.resolve(click_raw, base_url)
    domain = urltools.host_of(url)
    if sdata_date:
        date, date_source = sdata_date, "source_sdata"
    elif prefix_date:
        date, date_source = prefix_date, "abstract_prefix_time"
    else:
        date, date_source = None, None
    return ResultEntry(
        type="ad" if category == "ad" else "organic",
        display_position=_int_or_none(el.get("order")),
        position_in_page=position,
        tpl=el.get("tpl"),
        srcid=el.get("srcid"),
        new_srcid=el.get("new_srcid"),
        title=title,
        url=url,
        url_source=url_source,
        click_url=click_url,
        click_url_kind=urltools.classify_click_url(click_url),
        is_baidu_redirect=urltools.is_baidu_redirect(click_url),
        display_url=fusion_site or domain,
        domain=domain,
        snippet=snippet,
        site_name=site_name,
        date=date,
        date_source=date_source,
        thumbnail=urltools.resolve(extractors.extract_thumbnail(el), base_url),
        sitelinks=[
            SiteLink(text=s["text"], url=s["url"])
            for s in extractors.extract_sitelinks(el, base_url)
        ],
    )


def _build_card(el, kind: str, base_url, position: int) -> CardEntry:
    title = extractors.extract_title(el)
    url, _src, _fusion = extractors.extract_external_url(el)
    site_name, sdata_date = extractors.extract_source(el)
    _snippet, prefix_date = extractors.extract_snippet(el)
    # Pseudo targets such as nourl.ubs.baidu.com (AI-answer card) are
    # placeholders, not content URLs; real card targets (baike, fanyi,
    # bilibili, author pages…) are kept as recorded in data-log.mu.
    if url and (urltools.host_of(url) or "").endswith(".ubs.baidu.com"):
        url = None
    items = []
    if kind in ("video", "live", "official_account", "forum", "note"):
        items = [
            CardItem(title=i["title"], url=i["url"], thumbnail=i["thumbnail"])
            for i in extractors.extract_card_items(el, base_url)
        ]
    return CardEntry(
        card_kind=kind,
        display_position=_int_or_none(el.get("order")),
        position_in_page=position,
        tpl=el.get("tpl"),
        srcid=el.get("srcid"),
        new_srcid=el.get("new_srcid"),
        title=title,
        text=extractors.extract_card_text(el) if kind in ("baike", "knowledge_graph") else None,
        url=url,
        click_url=urltools.resolve(extractors.extract_click_url(el, title), base_url),
        thumbnail=urltools.resolve(extractors.extract_thumbnail(el), base_url),
        site_name=site_name,
        date=sdata_date or prefix_date,
        ai_generated_marker=(kind == "ai_answer" and extractors.has_ai_marker(el)),
        items=items,
    )


def parse_search_results(
    html: Union[str, bytes],
    query: Optional[str] = None,
    page_url: Optional[str] = None,
) -> SearchPage:
    """Parse one search-result HTML page into a :class:`SearchPage`."""
    if isinstance(html, str):
        raw = html.encode("utf-8")
    else:
        raw = html
    doc = lhtml.fromstring(raw)

    page = SearchPage(parser_version=PARSER_VERSION, query=query, source_url=page_url)
    warnings: list[str] = []

    results_container = doc.xpath('//*[@id="results"]')
    if not results_container:
        warnings.append("no #results container found")
    elements = doc.xpath(_CRESULT_XPATH)
    if not elements:
        warnings.append("no .c-result elements found")

    related: list[RelatedSearch] = []
    seen_related: set[str] = set()

    def add_related(entries, source: str):
        for entry in entries:
            if entry["query"] not in seen_related:
                seen_related.add(entry["query"])
                related.append(
                    RelatedSearch(query=entry["query"], url=entry["url"], source=source)
                )

    organic_rank = 0
    counts = {"organic": 0, "ad": 0, "card": 0, "related_block": 0, "unknown": 0}
    card_kinds: dict[str, int] = {}

    for position, el in enumerate(elements, start=1):
        if el.get("order") is None:
            warnings.append(f"c-result at position {position} has no order attribute")
        category, detail = classifiers.classify(el)
        if category == "organic":
            entry = _build_result(el, category, detail, page_url, position)
            organic_rank += 1
            entry.organic_rank = organic_rank
            page.results.append(entry)
            counts["organic"] += 1
        elif category == "ad":
            entry = _build_result(el, category, detail, page_url, position)
            page.ads.append(entry)
            counts["ad"] += 1
        elif category == "card":
            card = _build_card(el, detail, page_url, position)
            page.cards.append(card)
            counts["card"] += 1
            card_kinds[detail] = card_kinds.get(detail, 0) + 1
        elif category == "related":
            add_related(extractors.extract_related_from_block(el, page_url), "recommend_list")
            counts["related_block"] += 1
        else:
            page.unknown_elements.append(
                UnknownElement(
                    display_position=_int_or_none(el.get("order")),
                    position_in_page=position,
                    tpl=el.get("tpl"),
                    srcid=el.get("srcid"),
                    reason=detail,
                )
            )
            counts["unknown"] += 1

    # Related searches also appear in the page footer block.
    for block in doc.xpath('//*[contains(@class,"page-relative")]'):
        add_related(extractors.extract_related_from_block(block, page_url), "page_relative")

    page.related_searches = related
    page.page = extract_pagination(doc, page_url)

    if query and page.page.next_url:
        next_word = urltools.word_of(page.page.next_url)
        if next_word is not None and next_word != query:
            warnings.append(
                f"next_url word '{next_word}' differs from query '{query}'"
            )

    page.diagnostics = {
        "c_result_count": len(elements),
        "classified": counts,
        "card_kinds": card_kinds,
        "warnings": warnings,
    }
    return page
