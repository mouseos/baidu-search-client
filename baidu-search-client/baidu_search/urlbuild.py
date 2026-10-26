# -*- coding: utf-8 -*-
"""
Search URL generation, as implemented by the Baidu Android app
(com.baidu.searchbox 15.57.1.10).

This module builds the main web-search URL only: the default
template, the ``processWebSearchUrl`` merges whose values are
statically determined, and the ``ant_ct`` token (from
:mod:`baidu_search.antct`).  Device-dependent ``pu`` values such as
cuid and cua are not added, because they cannot be determined
outside the app.  HTTP transport is ``baidu_search.transport``'s
responsibility, not this module's.
"""

import re

from .antct import make_ant_ct

APP_VERSION = "15.57.1.10"

# Format produced by HttpUAManager.initDefaultUserAgent:
#   <escaped http.agent> baiduboxapp/<versionName> (Baidu; P1 <Android release>)
# http.agent is a runtime device property, so a representative
# Dalvik string is used for that part.
USER_AGENT = ("Dalvik/2.1.0 (Linux; U; Android 13; SM-S918B Build/TP1A.220624.014) "
              "baiduboxapp/{} (Baidu; P1 13)").format(APP_VERSION)


# ---------- Java/Android encoding helpers ----------

def java_urlencode(s: str) -> str:
    """Semantics of java.net.URLEncoder.encode(s, "UTF-8")."""
    out = []
    for ch in s:
        if ch.isascii() and (ch.isalnum() or ch in ".-*_"):
            out.append(ch)
        elif ch == " ":
            out.append("+")
        else:
            for b in ch.encode("utf-8"):
                out.append("%%%02X" % b)
    return "".join(out)


def uri_encode(s: str) -> str:
    """Semantics of android.net.Uri.encode(s) (allowed: A-Za-z0-9 _-!.~'()*)."""
    allow = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-!.~'()*")
    out = []
    for ch in s:
        if ch in allow:
            out.append(ch)
        else:
            for b in ch.encode("utf-8"):
                out.append("%%%02X" % b)
    return "".join(out)


def add_param(url: str, key: str, value):
    """Equivalent of UrlUtil.addParam (value appended as-is; None adds nothing)."""
    if value is None:
        return url
    sep = "&" if "?" in url else "?"
    return "{}{}{}={}".format(url, sep, key, value)


def _get_pu(url: str):
    m = re.search(r"[?&]pu=([^&]*)", url)
    return m.group(1) if m else None


def pu_merge(url: str, key: str, value: str) -> str:
    """Reproduces BaiduIdentityManager.o(url, key, value)."""
    field = _get_pu(url)
    if field is None or field == "":
        return add_param(url, "pu", uri_encode(key + "@" + value))
    probe = key + "@"
    if uri_encode(probe) in field or probe in field:
        return url
    return url.replace("pu=" + field,
                       "pu=" + field + uri_encode("," + probe + value), 1)


# ---------- Main search URL (equivalent of bq0.m.d) ----------

# Default template from SearchCategoryControl.f().
DEFAULT_WEB_TEMPLATE = ("http://m.baidu.com/s?tn=zbios&pu=sz%401320_480"
                        "&bd_page_type=1&word=")
# Contents of the bundled R.raw.tnconfig (res/raw/tnconfig.ini):
# the static initial candidate for getLastTn().
TNCONFIG_VALUE = "1020164n"


def process_web_search_url_static(url: str) -> str:
    """
    The statically reproducible part of processWebSearchUrl(url, 1, false).

    The pu merge order in the app is cuid, cua, [cut], osname, ctv,
    cfrom, [cen], [c3_aid].  Only osname and cfrom have statically
    determined values, so only those two are applied, in that order.
    """
    url = pu_merge(url, "osname", "baiduboxapp")
    url = pu_merge(url, "cfrom", TNCONFIG_VALUE)
    return url


def build_t_samp() -> str:
    """bq0.m.q(): only the fixed-key part ("-key_value" joined).

    aiapps is a runtime value and is excluded.
    """
    items = [("tcspeedup", "0"),
             # ("aiapps", <computed at runtime by ce4>) is excluded
             ("fixhttpdns", "0"),
             ("load_async_k", "0"),
             ("Prefetch_NA", "101")]
    return "-".join("{}_".format(k) + v for k, v in items) \
        if False else "-".join(k + "_" + v for k, v in items)


def build_search_url(query: str, now_ms: int) -> str:
    """Reproduces bq0.m.d(query, null, null) (first search, no extra map).

    The ant_ct ``t`` value is DateTimeUtil.getCalibratedTime(), which
    is in seconds (with mDelta taken as 0), so now_ms is converted to
    seconds for ant_ct.  The "KWD" + currentTimeMillis placeholder
    itself stays in milliseconds, as in the app.
    """
    placeholder = "KWD" + str(now_ms)
    tpl = DEFAULT_WEB_TEMPLATE + placeholder
    tpl = process_web_search_url_static(tpl)
    # z(): upgrade the template to https (u() is true in release builds)
    if tpl.startswith("http://"):
        tpl = "https://" + tpl[len("http://"):]
    url = tpl.replace(placeholder, java_urlencode(query))
    # b(): network-state parameters (mpv/p_nw/network) are out of scope
    # k(): oq is not added on the first search
    url = pu_merge(url, "csrc", "app_mainbox_txt")  # p(url, csrc)
    # wh depends on runtime conditions and is not added
    ant_ct = make_ant_ct(now_ms // 1000, query)  # t is in seconds (getCalibratedTime)
    url = add_param(url, "ant_ct", ant_ct)          # k(url, "ant_ct", h(query))
    url = add_param(url, "t_samp", build_t_samp())  # o(url)
    return url
