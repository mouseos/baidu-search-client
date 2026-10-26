"""Classification of ``.c-result`` elements.

Primary signal: the server-side template id in the ``tpl`` attribute,
which the measured pages (2026-10-25, com.baidu.searchbox 15.57.1.10)
use consistently.  Secondary signal for ads: the EC ad markup
conventions defined by the ad stylesheet (``<style id="ec_ls_css">``)
that Baidu ships inside every measured page — ad containers use
``ec_*`` classes (``.ec_ad_results``, ``.ec_wise_ad``,
``.ec-material_*``) and carry a visible ``广告`` label.

No measured sample page contained an actual ad result, so the ad branch
is covered by a synthetic fixture test only (see tests and
../result-classification.md).  Elements whose template is unknown are
reported as unknown — never guessed into ``organic``.
"""

from __future__ import annotations

# tpl -> classification
ORGANIC_TPLS = {
    "www_index",     # standard web result (several layout variants)
    "www_specific",  # web result, compact layout (title + source only)
    "www_kv",        # web result, image / key-value layout
}

CARD_KINDS = {
    "weather_forecast_new_san": "weather",          # dedicated weather card
    "sg_kg_entity_san": "knowledge_graph",          # knowledge-graph entity
    "bk_polysemy_san": "baike",                     # Baidu Baike entry card
    "fy_sg_dict_new_san": "dictionary",             # dictionary / translation
    "wenda_generate": "ai_answer",                  # AI-generated answer
    "vid_recommend": "video",                       # video recommendation
    "live_converge_san": "live",                    # live-stream aggregation
    "tieba_forumcommentxml_san": "forum",           # Tieba forum card
    "note_lead": "note",                            # feed note (图文) card
    "guanfanghao_san": "official_account",          # official account card
}

RELATED_TPLS = {
    "recommend_list_san",  # "大家还在搜" related-search block
}

AD_LABEL_TEXTS = {"广告", "廣告"}
# Class tokens that mark EC (ads) markup, per the in-page ec_ls_css rules.
AD_CLASS_PREFIXES = ("ec_", "ec-")
AD_CLASS_TOKENS = {"ec_wise_ad", "ec_ad_results"}


def _class_tokens(el) -> set[str]:
    tokens: set[str] = set()
    for node in el.iter():
        cls = node.get("class") if hasattr(node, "get") else None
        if cls:
            tokens.update(cls.split())
    return tokens


def has_ad_signals(el) -> tuple[bool, str]:
    """Return (is_ad, evidence) using only structural signals in the HTML."""
    # 1) Visible ad label: a leaf element whose entire text is 广告/廣告.
    for node in el.iter():
        if not hasattr(node, "get"):
            continue
        if len(node) == 0:
            text = (node.text or "").strip()
            if text in AD_LABEL_TEXTS:
                return True, f"visible ad label '{text}'"
    # 2) EC ad markup classes anywhere inside the result element.
    for token in _class_tokens(el):
        if token in AD_CLASS_TOKENS or token.startswith(AD_CLASS_PREFIXES):
            return True, f"ec ad class '{token}'"
    return False, ""


def classify(el) -> tuple[str, str]:
    """Classify one ``.c-result`` element.

    Returns (category, detail):
      * ("organic", tpl)
      * ("ad", evidence)
      * ("card", card_kind)
      * ("related", tpl)
      * ("unknown", reason)
    """
    ad, evidence = has_ad_signals(el)
    if ad:
        return "ad", evidence
    tpl = el.get("tpl")
    if tpl in ORGANIC_TPLS:
        return "organic", tpl
    if tpl in CARD_KINDS:
        return "card", CARD_KINDS[tpl]
    if tpl in RELATED_TPLS:
        return "related", tpl
    if tpl is None:
        return "unknown", "missing tpl attribute"
    return "unknown", f"unrecognised tpl '{tpl}'"
