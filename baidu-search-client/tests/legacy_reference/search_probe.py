# -*- coding: utf-8 -*-
"""
Baidu公式Androidアプリ (com.baidu.searchbox 15.57.1.10) の検索通信の
Python 実測検証プローブ。

APK静的解析で確定した生成ロジックだけを再現し、実際にHTTPリクエストを
送信して応答と照合する。APK内で確認できない値は捏造せず、
「再現範囲外」として明示する (下記 REPRODUCED / NOT_REPRODUCED 参照)。

再現対象:
  (a) メイン検索 GET URL (bq0.m / SearchUrlGenerator + BaiduIdentityManager)
  (b) クラシック sug POST (o93.j/h -> bf.d -> xg.b -> af.l, HttpManager)
  (c) テンプレート配信カテゴリJSONの取得 (取得先が静的に特定できた場合)

再現するもの:
  - テンプレート既定値 (SearchCategoryControl.f()):
      http://m.baidu.com/s?tn=zbios&pu=sz%401320_480&bd_page_type=1&word=
    w() で processWebSearchUrl を通し、z() で https へ昇格した版を使う
    (u() は非デバッグ時に true = https側)。
  - プレースホルダ "KWD"+currentTimeMillis を URLEncoder.encode(query,"UTF-8")
    で置換 (Java URLEncoder 意味論を再現)。
  - pu マージ BaiduIdentityManager.o(): 既存 pu に ",key@value" を
    Uri.encode して追記。キーが既にあれば何もしない。pu が無ければ新規。
  - processWebSearchUrl のうち静的確定できる pu キー:
      osname=baiduboxapp (固定値)
      cfrom=<getLastTn()> — 初期値は APK同梱 R.raw.tnconfig (res/raw/tnconfig.ini)
        の内容 "1020164n" (D() のフォールバックは "757b"。端末内保存値による
        上書きは実行時境界)
  - p(url, csrc): csrc=app_mainbox_txt を pu マージ。
  - ant_ct: crypto.py (bq0.m.h() の完全再現)。
  - t_samp: bq0.m.f() の LinkedHashMap を "-key_value" 連結。
      tcspeedup=0, fixhttpdns=0, load_async_k=0, Prefetch_NA=101 は固定値。
  - クラシック sug: SUGGESTION_HOST 既定 = HostConfig.getOldSearchboxHostForHttps()
      = https://m.baidu.com、パス /suggest?ctl=sug_prefetch&query=<enc>、
      i0() の v=3、voi=0 (非音声)、wise_csor=<クエリ長>、
      device_time=<現在時刻ms>、span_upgrade=1、event_type=0 (プリフェッチ無し)、
      POSTフォーム項目 data = {} (履歴なし: o93.j.t() は his 空なら空JSON)。

再現しないもの (APK内では端末/実行時状態からの生成であり、値を捏造しない):
  - pu の cuid (DeviceId 由来の暗号化 cuid), cua (端末/アプリ属性文字列),
    cut (プロファイル依存), ctv (端末/バージョン値), cen (cuid/cua の
    有無を表す連結文字列で、元値が無いため付けない), c3_aid (端末広告ID系)
  - トップレベルの from (W() の実行時値), pkgname (IdentityContext 実装値),
    p_sv / mpv / p_nw / network (プロファイル・ネットワーク状態依存),
    processUrlExternal の追加パラメータ (配信設定依存)
  - oq (前回クエリ: 初回検索では付かない), wh (実行時条件)
  - t_samp の aiapps (ce4 の実行時算出値), natab_pd (対象外タブ種別)
  - sug の pq / pt / pwd (前回クエリ系: 初回入力では空), lid / sugid /
    hot_launch / action (セッション・実行時値), sug_mode (条件分岐依存)
  - UA の端末固有部分 (System.getProperty("http.agent") は端末の
    モデル/ビルドを含む実行時プロパティ)。UA は HttpUAManager の
    生成規則の形式に従い、端末固有部分は代表値で置き換えた synthetic な
    値であることをここに明記する。

アクセス制限 (CAPTCHA/認証ページ) が返った場合はそれを記録して止める。
回避は行わない。
"""

import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests

from crypto import make_ant_ct

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "response_samples")
os.makedirs(OUT_DIR, exist_ok=True)

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


# ---------- クラシック sug (o93 経路) ----------

SUGGESTION_HOST = "https://m.baidu.com"  # HostConfig.getOldSearchboxHostForHttps() 既定


def build_sug_request(query: str, now_ms: int):
    """初回入力 (履歴なし・プリフェッチ登録なし・前回クエリなし) の再現"""
    url = (SUGGESTION_HOST + "/suggest?ctl=sug_prefetch&query="
           + java_urlencode(query))
    url = add_param(url, "v", "3")                    # BaiduIdentityManager.i0()
    url = add_param(url, "voi", "0")                  # 非音声
    url = add_param(url, "wise_csor", str(len(query)))
    # lid / sugid はセッション実行時値のため付けない
    # K(): pq / pt / pwd は初回は空。device_time は常時付加
    url = add_param(url, "device_time", str(now_ms))
    # sug_mode / hot_launch / action は条件・実行時値のため付けない
    url = add_param(url, "span_upgrade", "1")
    url = add_param(url, "event_type", "0")           # v(): プリフェッチなし
    form = {"data": "{}"}  # o93.j.t(): his が空なら空JSON "{}"
    return url, form


# ---------- 送受信と記録 ----------

def mask_headers(headers) -> dict:
    out = {}
    for k, v in headers.items():
        if k.lower() == "set-cookie":
            # Cookie名のみ残し、値は除去
            names = [part.split("=", 1)[0].strip()
                     for part in re.split(r", (?=[A-Za-z0-9_\-]+=)", v)]
            out[k] = "<masked; cookie names: {}>".format(", ".join(names))
        else:
            out[k] = v
    return out


def save_sample(name: str, record: dict, body: bytes, content_type: str):
    meta_path = os.path.join(OUT_DIR, name + ".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
    ext = ".html" if "html" in content_type else \
        ".json" if "json" in content_type else ".txt"
    body_path = os.path.join(OUT_DIR, name + ".body" + ext)
    with open(body_path, "wb") as f:
        f.write(body[:2000000])
    return meta_path, body_path


def do_request(session, name, method, url, **kw):
    started = time.time()
    try:
        resp = session.request(method, url, timeout=25, **kw)
    except requests.RequestException as e:
        record = {"name": name, "method": method, "request_url": url,
                  "error": "{}: {}".format(type(e).__name__, e),
                  "elapsed_s": round(time.time() - started, 3)}
        save_sample(name, record, b"", "")
        print(json.dumps(record, ensure_ascii=False))
        return None, record
    elapsed = time.time() - started
    body = resp.content or b""
    record = {
        "name": name,
        "method": method,
        "request_url": url,
        "final_url": resp.url,
        "status": resp.status_code,
        "reason": resp.reason,
        "elapsed_s": round(elapsed, 3),
        "redirects": [{"status": r.status_code,
                       "location": r.headers.get("Location", "")[:300]}
                      for r in resp.history],
        "response_headers": mask_headers(resp.headers),
        "body_bytes": len(body),
        "body_truncated_saved": min(len(body), 2000000),
    }
    save_sample(name, record, body, resp.headers.get("Content-Type", ""))
    print(json.dumps(record, ensure_ascii=False)[:1200])
    return resp, record


def scan_pagination(text: str) -> dict:
    """結果HTML内の pn 系次ページ要素を探す (ページネーション実測)"""
    import html as _html
    un = _html.unescape(text)
    pn_links = re.findall(r'href="([^"]*[?&]pn=\d+[^"]*)"', un)
    pn_values = sorted(set(re.findall(r'[?&]pn=(\d+)', un)),
                       key=lambda x: int(x))
    next_markers = [m for m in ("下一页", "下一頁", "next page")
                    if m in text]
    idx = un.rfind("下一页")
    context = (un[max(0, idx - 500):idx + 120].replace("\n", " ")
               if idx >= 0 else None)
    return {"pn_link_count": len(pn_links),
            "pn_link_samples": pn_links[:5],
            "pn_values": pn_values[:20],
            "next_page_markers": next_markers,
            "last_next_context": context}


def main():
    queries = ["天气"]
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    results = {}

    for q in queries:
        now_ms = int(time.time() * 1000)
        url = build_search_url(q, now_ms)
        print("=== main search URL ===\n" + url)
        resp, rec = do_request(session, "search_main_" + q, "GET", url,
                               headers={"Accept": "text/html,*/*"})
        if resp is not None:
            text = resp.text or ""
            results["search"] = {
                "content_type": resp.headers.get("Content-Type", ""),
                "is_html": "<html" in text[:2000].lower(),
                "has_result_content": ("天气" in text),
                "captcha_markers": [m for m in ("验证码", "captcha", "安全验证",
                                                "wappass", "登陆", "登录")
                                    if m in text],
                "title": (re.search(r"<title>(.*?)</title>", text, re.S)
                          .group(1).strip()[:120]
                          if re.search(r"<title>(.*?)</title>", text, re.S)
                          else None),
                "pagination": scan_pagination(text),
            }
            # 結果ページ側が生成した次ページURLがあれば、その構造を記録する
            # (踏襲アクセスはしない: pn 検証はリンク構造の確認まで)

        # クラシック sug
        now_ms = int(time.time() * 1000)
        sug_url, form = build_sug_request(q, now_ms)
        print("=== classic sug URL ===\n" + sug_url + "  form=" + str(form))
        sresp, srec = do_request(
            session, "sug_classic_" + q, "POST", sug_url, data=form,
            headers={"new-style": "1",
                     "Content-Type": "application/x-www-form-urlencoded"})
        if sresp is not None:
            stext = sresp.text or ""
            parsed = None
            try:
                parsed = json.loads(stext)
            except Exception:
                pass
            results["sug"] = {
                "content_type": sresp.headers.get("Content-Type", ""),
                "json_parsed": parsed is not None,
                "json_top_keys": (list(parsed.keys())
                                  if isinstance(parsed, dict) else None),
                "body_head": stext[:500],
            }

    with open(os.path.join(OUT_DIR, "probe_summary.json"), "w",
              encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("=== summary ===\n" + json.dumps(results, ensure_ascii=False,
                                           indent=2)[:3000])


if __name__ == "__main__":
    main()
