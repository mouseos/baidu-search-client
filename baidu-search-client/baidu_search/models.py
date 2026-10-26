"""Aggregated result model for multi-page searches.

Per-page entries are the ``baidu_parser`` dataclass dicts, reused
verbatim.  Aggregation only *annotates* copies with provenance fields
(``page_number``, ``page_pn``, ``source_page_url`` and, for organic
results, the new ``global_organic_rank``); the parser's own rank
fields (``display_position``, ``position_in_page``, ``organic_rank``)
are never overwritten or reinterpreted.

Duplicates: two organic/ad entries are duplicates when their key —
``url`` if present, else ``click_url`` — is an *exact* string match
(no normalisation whatsoever).  Duplicates are kept in the output
(original data is never dropped); they are flagged with
``"duplicate": true`` and described in ``diagnostics.duplicate_items``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

CLIENT_NAME = "baidu_search"
CLIENT_VERSION = "1.0.0"


@dataclass
class PageRecord:
    """Book-keeping for one fetched page (kept even on failure)."""

    page_number: Optional[int] = None  # 1-based fetch order
    pn: Optional[int] = None
    source_url: Optional[str] = None  # URL that was requested
    final_url: Optional[str] = None  # after redirects
    status_code: Optional[int] = None
    next_url: Optional[str] = None
    counts: dict[str, int] = field(default_factory=dict)
    parser_warnings: list[str] = field(default_factory=list)
    error: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "pn": self.pn,
            "source_url": self.source_url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "next_url": self.next_url,
            "counts": self.counts,
            "parser_warnings": self.parser_warnings,
            "error": self.error,
        }


@dataclass
class SinglePageResult:
    """Result of one ``search_page()`` call (parser page + fetch info)."""

    query: Optional[str]
    source_url: str
    final_url: Optional[str]
    status_code: Optional[int]
    page: Any  # baidu_parser.models.SearchPage
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = self.page.to_dict()
        data["fetch"] = {
            "source_url": self.source_url,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "client_warnings": list(self.warnings),
        }
        return data


@dataclass
class AggregatedSearch:
    query: str
    pages_requested: int
    pages_fetched: int = 0
    results: list[dict[str, Any]] = field(default_factory=list)
    ads: list[dict[str, Any]] = field(default_factory=list)
    cards: list[dict[str, Any]] = field(default_factory=list)
    related_searches: list[dict[str, Any]] = field(default_factory=list)
    unknown_elements: list[dict[str, Any]] = field(default_factory=list)
    pages: list[PageRecord] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "client": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            "query": self.query,
            "pages_requested": self.pages_requested,
            "pages_fetched": self.pages_fetched,
            "results": self.results,
            "ads": self.ads,
            "cards": self.cards,
            "related_searches": self.related_searches,
            "unknown_elements": self.unknown_elements,
            "pages": [p.to_dict() for p in self.pages],
            "diagnostics": {
                "duplicates": len(self.duplicate_items),
                "duplicate_items": self.duplicate_items,
                "errors": self.errors,
                "warnings": self.warnings,
            },
        }


def _annotate(entry: dict[str, Any], single: SinglePageResult) -> dict[str, Any]:
    out = dict(entry)
    out["page_number"] = single.page.page.page_number
    out["page_pn"] = single.page.page.pn
    out["source_page_url"] = single.source_url
    return out


def _dedup_key(entry: dict[str, Any]) -> Optional[str]:
    return entry.get("url") or entry.get("click_url")


def _absorb_ranked(
    target: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    single: SinglePageResult,
    seen: dict[str, dict[str, Any]],
    duplicates: list[dict[str, Any]],
    global_rank_counter: list[int],
    *,
    ranked: bool,
) -> None:
    for entry in entries:
        item = _annotate(entry, single)
        if ranked:
            global_rank_counter[0] += 1
            item["global_organic_rank"] = global_rank_counter[0]
        key = _dedup_key(item)
        if key is not None and key in seen:
            item["duplicate"] = True
            duplicates.append(
                {
                    "key": key,
                    "first_page_number": seen[key]["page_number"],
                    "duplicate_page_number": item["page_number"],
                    "title": item.get("title"),
                }
            )
        else:
            item["duplicate"] = False
            if key is not None:
                seen[key] = item
        target.append(item)


def aggregate(
    query: str,
    pages_requested: int,
    singles: list[SinglePageResult],
    *,
    errors: Optional[list[dict[str, Any]]] = None,
    warnings: Optional[list[str]] = None,
    failed_pages: Optional[list[PageRecord]] = None,
) -> AggregatedSearch:
    """Combine per-page results into one :class:`AggregatedSearch`.

    ``failed_pages`` are PageRecords for pages that could not be
    fetched/parsed; they are interleaved by the caller through
    ``pages`` ordering — here they are simply appended after the
    successful records (fetch order is preserved in ``page_number``).
    """
    agg = AggregatedSearch(query=query, pages_requested=pages_requested)
    agg.errors = list(errors or [])
    agg.warnings = list(warnings or [])

    seen: dict[str, dict[str, Any]] = {}
    rank_counter = [0]
    seen_related: set[str] = set()

    for single in singles:
        page = single.page
        counts = {
            "results": len(page.results),
            "ads": len(page.ads),
            "cards": len(page.cards),
            "related_searches": len(page.related_searches),
            "unknown_elements": len(page.unknown_elements),
        }
        agg.pages.append(
            PageRecord(
                page_number=page.page.page_number,
                pn=page.page.pn,
                source_url=single.source_url,
                final_url=single.final_url,
                status_code=single.status_code,
                next_url=page.page.next_url,
                counts=counts,
                parser_warnings=list(
                    (page.diagnostics or {}).get("warnings", [])
                ),
            )
        )
        _absorb_ranked(
            agg.results,
            [r.to_dict() for r in page.results],
            single,
            seen,
            agg.duplicate_items,
            rank_counter,
            ranked=True,
        )
        _absorb_ranked(
            agg.ads,
            [r.to_dict() for r in page.ads],
            single,
            seen,
            agg.duplicate_items,
            rank_counter,
            ranked=False,
        )
        for card in page.cards:
            agg.cards.append(_annotate(card.to_dict(), single))
        for rel in page.related_searches:
            if rel.query in seen_related:
                continue
            seen_related.add(rel.query)
            item = {"query": rel.query, "url": rel.url, "source": rel.source}
            item.update(
                {
                    "page_number": page.page.page_number,
                    "page_pn": page.page.pn,
                    "source_page_url": single.source_url,
                }
            )
            agg.related_searches.append(item)
        for unk in page.unknown_elements:
            from dataclasses import asdict

            item = _annotate(asdict(unk), single)
            agg.unknown_elements.append(item)
        for warning in single.warnings:
            if warning not in agg.warnings:
                agg.warnings.append(warning)

    if failed_pages:
        agg.pages.extend(failed_pages)
        agg.pages.sort(key=lambda p: (p.page_number is None, p.page_number or 0))

    agg.pages_fetched = len(singles)
    return agg
