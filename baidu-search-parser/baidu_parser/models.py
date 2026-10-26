"""Data models for parsed Baidu (APK / wise) search result pages.

Plain dataclasses with ``to_dict()`` so the whole page serialises to JSON
without custom encoders.  Unknown values are ``None``; absent collections
are empty lists.  Nothing is ever synthesised: every field is copied from
the source HTML or left ``None``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


@dataclass
class SiteLink:
    text: str
    url: Optional[str] = None  # click URL exactly as found in the HTML


@dataclass
class CardItem:
    """One entry inside a list-style card (video list, account articles…)."""

    title: Optional[str] = None
    url: Optional[str] = None  # click URL exactly as found in the HTML
    thumbnail: Optional[str] = None


@dataclass
class ResultEntry:
    """A single ``.c-result`` element classified as organic or ad."""

    type: str  # "organic" | "ad"
    display_position: Optional[int] = None  # `order` attribute in the HTML
    position_in_page: Optional[int] = None  # 1-based index among .c-result
    organic_rank: Optional[int] = None  # 1-based among organic results only
    tpl: Optional[str] = None
    srcid: Optional[str] = None
    new_srcid: Optional[str] = None
    title: Optional[str] = None
    url: Optional[str] = None  # external URL explicitly present in the HTML
    url_source: Optional[str] = None  # "data_log.mu" | "data_click_info.extra.url"
    click_url: Optional[str] = None  # URL the title link actually points to
    click_url_kind: Optional[str] = None  # see urls.classify_click_url
    is_baidu_redirect: bool = False
    display_url: Optional[str] = None  # as displayed (fusion_site / domain)
    domain: Optional[str] = None  # host of `url`
    snippet: Optional[str] = None
    site_name: Optional[str] = None
    date: Optional[str] = None  # date string as displayed in the HTML
    date_source: Optional[str] = None  # "source_sdata" | "abstract_prefix_time"
    thumbnail: Optional[str] = None
    sitelinks: list[SiteLink] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CardEntry:
    """A single ``.c-result`` element classified as a special card."""

    type: str = "card"
    card_kind: Optional[str] = None  # weather | knowledge_graph | ai_answer …
    display_position: Optional[int] = None
    position_in_page: Optional[int] = None
    tpl: Optional[str] = None
    srcid: Optional[str] = None
    new_srcid: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None  # main body text when present in static HTML
    url: Optional[str] = None  # data-log.mu when it is a real http(s) URL
    click_url: Optional[str] = None
    thumbnail: Optional[str] = None
    site_name: Optional[str] = None
    date: Optional[str] = None
    ai_generated_marker: bool = False  # page itself states AI generation
    items: list[CardItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RelatedSearch:
    query: str
    url: Optional[str] = None  # search click URL exactly as found
    source: Optional[str] = None  # "recommend_list" | "page_relative"


@dataclass
class UnknownElement:
    display_position: Optional[int] = None
    position_in_page: Optional[int] = None
    tpl: Optional[str] = None
    srcid: Optional[str] = None
    reason: str = ""


@dataclass
class PageInfo:
    pn: int = 0
    page_number: int = 1
    is_first_page: bool = True
    next_url: Optional[str] = None  # server-issued URL, kept verbatim
    previous_url: Optional[str] = None
    first_url: Optional[str] = None
    next_pn: Optional[int] = None
    previous_pn: Optional[int] = None


@dataclass
class SearchPage:
    parser_name: str = "baidu_parser"
    parser_version: str = ""
    query: Optional[str] = None
    source_url: Optional[str] = None
    page: PageInfo = field(default_factory=PageInfo)
    results: list[ResultEntry] = field(default_factory=list)
    ads: list[ResultEntry] = field(default_factory=list)
    cards: list[CardEntry] = field(default_factory=list)
    related_searches: list[RelatedSearch] = field(default_factory=list)
    unknown_elements: list[UnknownElement] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "parser": {"name": self.parser_name, "version": self.parser_version},
            "query": self.query,
            "source_url": self.source_url,
            "page": asdict(self.page),
            "results": [r.to_dict() for r in self.results],
            "ads": [r.to_dict() for r in self.ads],
            "cards": [c.to_dict() for c in self.cards],
            "related_searches": [asdict(r) for r in self.related_searches],
            "unknown_elements": [asdict(u) for u in self.unknown_elements],
            "diagnostics": self.diagnostics,
        }
