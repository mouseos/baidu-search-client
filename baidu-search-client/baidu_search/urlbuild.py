# -*- coding: utf-8 -*-
"""
検索 URL 生成処理 (baidu_search パッケージ内蔵版)
対象: Baidu公式Androidアプリ com.baidu.searchbox 15.57.1.10

来歴 (第18ラウンドで正式パッケージへ組み込み):
  本モジュールの関数・定数本体は検証用プローブ
  work/python-validation/search_probe.py のうちメイン検索 URL 生成に
  必要な部分をそのまま移設したものである。移設しなかった部分:
    - クラシック sug の URL 生成 (build_sug_request): 本クライアントの
      検索機能では使わないため検証プローブ側にのみ残置する。
    - 送受信・記録系 (do_request / save_sample / mask_headers /
      scan_pagination / main / OUT_DIR 生成 / import 時の sys.path 操作 /
      requests 依存): 実験用コードであり、HTTP 通信は
      baidu_search.transport の責務。
  make_ant_ct は同一パッケージの baidu_search.antct
  (レガシー crypto.py の移設版) から import する。
  出力一致は tests/test_packaging_consistency.py と
  tests/test_search_url.py がレガシー実装と固定時刻で照合する。
  元ファイルは検証プローブとして残置され、実行時には読み込まれない。

再現範囲・再現しないものの詳細は元プローブの docstring と
dependency-audit.md を参照 (pu の端末由来値 cuid/cua 等は付けない、
という原則は移設後も同一)。
"""

import re

from .antct import make_ant_ct

APP_VERSION = "15.57.1.10"

# HttpUAManager.initDefaultUserAgent の形式:
#   <http.agent をエスケープ> baiduboxapp/<versionName> (Baidu; P1 <Androidリリース>)
# http.agent 部は端末実行時プロパティのため representative な Dalvik 文字列を使う
USER_AGENT = ("Dalvik/2.1.0 (Linux; U; Android 13; SM-S918B Build/TP1A.220624.014) "
              "baiduboxapp/{} (Baidu; P1 13)").format(APP_VERSION)


# ---------- Java/Android 符号化ユーティリティ ----------

def java_urlencode(s: str) -> str:
    """java.net.URLEncoder.encode(s, "UTF-8") の意味論"""
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
    """android.net.Uri.encode(s) の意味論 (許可文字: A-Za-z0-9 _-!.~'()*)"""
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
    """UrlUtil.addParam 相当 (値はそのまま連結。None は付けない)"""
    if value is None:
        return url
    sep = "&" if "?" in url else "?"
    return "{}{}{}={}".format(url, sep, key, value)


def _get_pu(url: str):
    m = re.search(r"[?&]pu=([^&]*)", url)
    return m.group(1) if m else None


def pu_merge(url: str, key: str, value: str) -> str:
    """BaiduIdentityManager.o(url, key, value) の再現"""
    field = _get_pu(url)
    if field is None or field == "":
        return add_param(url, "pu", uri_encode(key + "@" + value))
    probe = key + "@"
    if uri_encode(probe) in field or probe in field:
        return url
    return url.replace("pu=" + field,
                       "pu=" + field + uri_encode("," + probe + value), 1)


# ---------- メイン検索 URL (bq0.m.d 相当) ----------

# SearchCategoryControl.f() の既定テンプレート
DEFAULT_WEB_TEMPLATE = ("http://m.baidu.com/s?tn=zbios&pu=sz%401320_480"
                        "&bd_page_type=1&word=")
# APK同梱 R.raw.tnconfig (res/raw/tnconfig.ini) の内容 = getLastTn() の静的初期値候補
TNCONFIG_VALUE = "1020164n"


def process_web_search_url_static(url: str) -> str:
    """
    processWebSearchUrl(url, 1, false) のうち静的再現可能な部分。
    pu マージ順はAPKコード順: cuid, cua, [cut], osname, ctv, cfrom, [cen], [c3_aid]
    のうち、値が静的に確定する osname と cfrom のみを同順序で適用する。
    """
    url = pu_merge(url, "osname", "baiduboxapp")
    url = pu_merge(url, "cfrom", TNCONFIG_VALUE)
    return url


def build_t_samp() -> str:
    """bq0.m.q(): f() の固定キー分のみ (-key_value 連結)。aiapps は実行時値のため除外"""
    items = [("tcspeedup", "0"),
             # ("aiapps", <ce4 実行時算出値>) は再現範囲外
             ("fixhttpdns", "0"),
             ("load_async_k", "0"),
             ("Prefetch_NA", "101")]
    return "-".join("{}_".format(k) + v for k, v in items) \
        if False else "-".join(k + "_" + v for k, v in items)


def build_search_url(query: str, now_ms: int) -> str:
    """bq0.m.d(query, null, null) の再現 (初回検索・追加Map無し)

    【変更履歴 2026-10-25 追加検証】ant_ct の t は DateTimeUtil
    .getCalibratedTime() の戻り値であり単位は秒 (mDelta=0 で代用)。
    当初版はプレースホルダ用のミリ秒値をそのまま渡していたため、
    秒へ変換するよう訂正した。プレースホルダ "KWD"+currentTimeMillis
    自体はミリ秒のままが APK どおり。
    """
    placeholder = "KWD" + str(now_ms)
    tpl = DEFAULT_WEB_TEMPLATE + placeholder
    tpl = process_web_search_url_static(tpl)
    # z(): http -> https 昇格 (d 側テンプレート)。u() は非デバッグ時 true
    if tpl.startswith("http://"):
        tpl = "https://" + tpl[len("http://"):]
    url = tpl.replace(placeholder, java_urlencode(query))
    # b(): ネットワーク状態依存 (mpv/p_nw/network) は再現範囲外
    # k(): oq は初回検索では付かない
    url = pu_merge(url, "csrc", "app_mainbox_txt")  # p(url, csrc)
    # wh: 実行時条件のため付けない
    ant_ct = make_ant_ct(now_ms // 1000, query)  # t は秒単位 (getCalibratedTime)
    url = add_param(url, "ant_ct", ant_ct)          # k(url, "ant_ct", h(query))
    url = add_param(url, "t_samp", build_t_samp())  # o(url)
    return url
