"""Field extraction from one ``.c-result`` element.

Extraction is DOM-based (lxml).  Identifiers combine several signals —
``data-module`` attributes, class-token prefixes, ancestor relations and
the SSR ``<!--s-data:{...}-->`` JSON comments the San framework embeds —
instead of relying on a single CSS class.

Text normalisation: descendant text nodes are concatenated, HTML
entities are already decoded by the parser, and every run of whitespace
(including full-width spaces and newlines) collapses to one space.
Emphasis markup (``<em>`` etc.) contributes its text, never markup.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional
from urllib.parse import unquote

from . import urls as urltools

_WS_RE = re.compile(r"[\s\u3000]+")


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = _WS_RE.sub(" ", value).strip()
    return text or None


def _is_comment(node) -> bool:
    # In lxml, comment nodes have a callable ``tag``.
    return not isinstance(node.tag, str)


def element_text(el) -> Optional[str]:
    """Visible text of an element, skipping comments/scripts/styles/TTS."""
    if el is None:
        return None
    parts: list[str] = []

    def walk(node):
        if _is_comment(node):
            return
        if node.tag in ("script", "style"):
            return
        cls = node.get("class") or ""
        if "cosc-tts" in cls:  # text-to-speech controls are not content
            return
        if node.text:
            parts.append(node.text)
        for child in node:
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(el)
    return normalize_text("".join(parts))


def parse_json_attr(el, name: str) -> dict[str, Any]:
    raw = el.get(name)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (ValueError, TypeError):
        return {}


def sdata_json(el) -> dict[str, Any]:
    """Parse the first ``<!--s-data:{...}-->`` SSR comment inside ``el``."""
    if el is None:
        return {}
    for node in el.iter():
        if _is_comment(node):
            text = (node.text or "").strip()
            if text.startswith("s-data:"):
                try:
                    data = json.loads(text[len("s-data:"):])
                    return data if isinstance(data, dict) else {}
                except ValueError:
                    return {}
    return {}


def find_module(el, name: str):
    found = el.xpath(f'.//*[@data-module="{name}"]')
    return found[0] if found else None


# ---------------------------------------------------------------- titles

def extract_title(el) -> Optional[str]:
    h3 = el.xpath(".//h3")
    if h3:
        return element_text(h3[0])
    top = find_module(el, "top_title")
    if top is not None:
        return element_text(top)
    return None


# ---------------------------------------------------------------- snippet

def _summary_from(module) -> tuple[Optional[str], Optional[str]]:
    """(snippet, prefix_date) from an abstract / pure-summary module."""
    if module is None:
        return None, None
    prefix = module.xpath('.//*[contains(@class,"prefix-time")]')
    prefix_text = element_text(prefix[0]) if prefix else None
    spans = module.xpath('.//*[contains(@class,"summary-text")]')
    if spans:
        return element_text(spans[0]), prefix_text
    # Fallback: whole module text with the prefix-time part removed.
    text = element_text(module)
    if text and prefix_text and text.startswith(prefix_text):
        text = normalize_text(text[len(prefix_text):])
    return text, prefix_text


def extract_snippet(el) -> tuple[Optional[str], Optional[str]]:
    """Return (snippet, relative date label shown before the snippet)."""
    module = find_module(el, "abstract")
    snippet, prefix = _summary_from(module)
    if snippet:
        return snippet, prefix
    module = find_module(el, "pure-summary")
    snippet, prefix = _summary_from(module)
    if snippet:
        return snippet, prefix
    # Last resort: the SSR summaryData in the abstract module comment.
    abstract = find_module(el, "abstract")
    data = sdata_json(abstract) if abstract is not None else {}
    summary = data.get("summaryData") or {}
    texts = summary.get("summaryText") or []
    if texts:
        return normalize_text(texts[0]), prefix
    return None, prefix


# ---------------------------------------------------------------- source

def extract_source(el) -> tuple[Optional[str], Optional[str]]:
    """(site_name, absolute date) from the source module's SSR data."""
    module = find_module(el, "source")
    if module is None:
        return None, None
    data = sdata_json(module)
    source = data.get("sourceData") or {}
    site = normalize_text(source.get("text"))
    date = normalize_text(source.get("time"))
    return site, date


# ---------------------------------------------------------------- links

def extract_click_url(el, title: Optional[str]) -> Optional[str]:
    """The URL the result's main link points to, exactly as in the HTML."""
    articles = el.xpath(".//article[@rl-link-href]")
    if articles:
        return articles[0].get("rl-link-href")
    # Anchor wrapping the title heading.
    wrapped = el.xpath(".//a[.//h3]/@href")
    if wrapped:
        return wrapped[0]
    # Anchor whose visible text is the title.
    if title:
        for a in el.xpath(".//a[@href]"):
            if element_text(a) == title:
                return a.get("href")
    return None


def extract_external_url(el) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(url, url_source, fusion_site) — only values the HTML itself states.

    Primary: ``data-log`` JSON member ``mu``.
    Secondary (www_index cards): the ``url`` member of the article's
    ``data-click-info`` JSON ``extra`` object, percent-decoded twice.
    """
    log = parse_json_attr(el, "data-log")
    mu = log.get("mu")
    fusion_site = None
    articles = el.xpath(".//article[@data-click-info]")
    extra: dict[str, Any] = {}
    if articles:
        info = parse_json_attr(articles[0], "data-click-info")
        raw_extra = info.get("extra")
        if isinstance(raw_extra, str):
            try:
                extra = json.loads(raw_extra)
            except ValueError:
                extra = {}
        elif isinstance(raw_extra, dict):
            extra = raw_extra
        fusion_site = normalize_text(extra.get("fusion_site"))
    if isinstance(mu, str) and mu.startswith(("http://", "https://")):
        return mu, "data_log.mu", fusion_site
    encoded = extra.get("url")
    if isinstance(encoded, str) and encoded:
        decoded = unquote(unquote(encoded))
        if decoded.startswith(("http://", "https://")):
            return decoded, "data_click_info.extra.url", fusion_site
    return None, None, fusion_site


# ---------------------------------------------------------------- media

def extract_thumbnail(el) -> Optional[str]:
    source_module = find_module(el, "source")
    for img in el.xpath(".//img"):
        if source_module is not None and img in source_module.iter():
            continue  # source avatars are not result thumbnails
        cls = img.get("class") or ""
        if "avatar" in cls:
            continue
        src = img.get("src") or img.get("data-src")
        if src:
            return src
    return None


# ---------------------------------------------------------------- sitelinks

def extract_sitelinks(el, base_url: Optional[str]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    seen: set[str] = set()
    anchors = el.xpath(
        './/a[starts-with(@data-module,"subpos")]'
        ' | .//a[contains(@class,"sc-sublink")]'
    )
    for a in anchors:
        text = element_text(a)
        if not text or text in seen:
            continue
        seen.add(text)
        links.append({"text": text, "url": urltools.resolve(a.get("href"), base_url)})
    return links


# ---------------------------------------------------------------- cards

_AI_MARKERS = ("内容由AI生成", "由AI生成", "以上内容均由AI生成")


def has_ai_marker(el) -> bool:
    text = element_text(el) or ""
    return any(marker in text for marker in _AI_MARKERS)


def extract_card_text(el) -> Optional[str]:
    """Main body text of a card, when present as static HTML text.

    Baike / knowledge-graph cards carry the description inside a long
    anchor; that anchor's text is the description.  Other kinds return
    ``None`` here and are handled (or explicitly not handled) per kind
    in the parser documentation.
    """
    best: Optional[str] = None
    for a in el.xpath(".//a[@href]"):
        text = element_text(a)
        if text and len(text) >= 50 and (best is None or len(text) > len(best)):
            best = text
    return best


def extract_card_items(el, base_url: Optional[str]) -> list[dict[str, Any]]:
    """List entries of a card: anchors with meaningful text, in order."""
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, Optional[str]]] = set()
    source_module = find_module(el, "source")
    for a in el.xpath(".//a[@href]"):
        if source_module is not None and a in source_module.iter():
            continue
        text = element_text(a)
        if not text or len(text) < 4:
            continue
        href = urltools.resolve(a.get("href"), base_url)
        key = (text, href)
        if key in seen:
            continue
        seen.add(key)
        items.append({"title": text, "url": href, "thumbnail": None})
        if len(items) >= 20:
            break
    return items


# ---------------------------------------------------------------- related

def extract_related_from_block(el, base_url: Optional[str]) -> list[dict[str, Any]]:
    """Related searches from one recommend_list element or page-relative."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for a in el.xpath(".//a[@href]"):
        text = element_text(a)
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(
            {"query": text, "url": urltools.resolve(a.get("href"), base_url)}
        )
    return out
