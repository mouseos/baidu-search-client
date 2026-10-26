# ページネーション統合

## 原則

次ページURLは**サーバがHTML内に発行したものを原文のまま**使う。
パーサー（`baidu_parser`）が `div.new-pagenav` から抽出した
`page.next_url` が唯一の情報源であり、クライアント側で
`pn=10` / `pn=20` のURLを組み立てることはしない。
URLの正規化もしない（サーバ発行の `ant_ct` / `rsv_pq` 等を
壊さないため）。モックテスト
`test_next_url_passed_through_verbatim` が、2回目のリクエストURLが
パーサー抽出の next_url と完全一致することを固定検証している。

## 処理フロー

```
url = build_initial_search_url(query)
loop:
    page = fetch(url) -> parse
    aggregate(page)
    next = page.page.next_url
    if next is None: 終了（最終ページ）
    if 取得ページ数 == max_pages: 終了
    validate_next_url(next)   # スキーム http/https、ホスト *.baidu.com
    if next in seen_urls: 循環エラーとして記録し終了
    url = next
```

## 終了条件と扱い

| 条件 | 扱い |
|---|---|
| 次ページURLが存在しない | 正常終了 |
| 指定ページ数に到達 | 正常終了 |
| 同一URLが再出現（循環） | `pagination_cycle` を diagnostics.errors に記録して終了。ループURLは再取得しない |
| 不正な次ページURL（想定外ホスト・スキーム） | `invalid_next_url` を記録して終了。そのURLへはアクセスしない |
| 通信エラー（途中ページ） | エラーを記録して終了。**取得済みページの結果は保持** |
| アクセス制限（403/429・検証ページ） | 同上（再試行しない） |

## Cookieとの関係

全ページで同一セッションを使うため、初回応答の Cookie は
後続ページでも送信される（追加の手続きは不要。requests の
標準動作）。実通信でも2ページ取得を通じて Cookie が保持される
ことを確認した（名前のみ記録）。

## ページ間の重複

集約時に通常結果・広告について、キー（`url`、無ければ
`click_url`）の**完全一致**で重複を検出する。正規化は一切しない
ため、異なるURLが誤って同一扱いされることはない。
重複した要素は削除せず `duplicate: true` を付けて残し、
`diagnostics.duplicate_items` に初出ページと重複ページを記録する。
実測フィクスチャ3ページ（pn=0/10/20）では重複0件、
同一ページを二重投入した合成テストでは5件すべて検出される。

## 実測フィクスチャでの連鎖

| ページ | pn | next_url |
|---|---|---|
| tianqi_p1 | 0 | あり（pn=10） |
| tianqi_pn10 | 10 | あり（pn=20） |
| tianqi_pn20 | 20 | なし → `next_url: null` で表現し正常終了 |
