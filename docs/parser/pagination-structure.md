# ページネーションの構造

> パーサー: baidu_parser 1.0.0 / `baidu_parser/pagination.py`
> 実測: 「天气」の pn=0相当（初回）/ pn=10 / pn=20

## DOM構造

```
div.new-pagenav.c-flexbox
├─ div.new-pagenav-left
│   ├─ a.new-firstpage   （3ページ目以降。1ページ目へのURL）
│   └─ a.new-prepage       （前ページへのURL）
├─ div.new-pagenav-center
│   └─ span.new-nowpage    「第 N 页」（現在ページ表示）
└─ div.new-pagenav-right
    └─ a.new-nextpage      （次ページへのURL）
```

変種・癖（実測）:
- **1ページ目**: ナビは1つだけで、中身は `a.new-nextpage-only`
  （pn=10 へのリンク）のみ。前ページ・現在ページ表示はない。
- **2ページ目以降**: SSR の都合で `.new-pagenav` ブロックが
  同一内容で**4回繰り返される**。パーサーは最初の1つだけを使う。
- **最終ページ相当（pn=20）**: `new-pagenav-right` が空 = 次ページなし。
  JSON では `next_url=null, next_pn=null` で表現する。
- 前ページ・1ページ目へのURLは `pn` パラメータを**含まない**
  （pn=0 の意味）。`previous_pn` はこの場合 0 と解釈する。

## サーバ発行URLの扱い

- 次/前ページURLはサーバが発行した完成形を**そのまま保持**する。
  `ant_ct`・`rsv_pq`・`fqid` 等は再生成・改変しない。
- URLには検索語が `word=%E5%A4%A9%E6%B0%94` の形で引き継がれる。
  パーサーは `word` と指定クエリの一致を診断情報で検証する
  （不一致なら warnings に記録）。
- ページ番号は `span.new-nowpage` の「第 N 页」を第一根拠とし、
  無い場合はソースURLの `pn`（pn=10 → 2ページ目）から求める。

## ページ間の重複（実測）

天気の pn=0/10/20 の通常結果について、`url`（data-log.mu）の
重複は**0件**だった（テスト `test_no_cross_page_duplicates` で担保）。
同一サイトの別ページ（例: 湖南省と別の都市の天気ページ）は
URLが異なるため重複ではない。

## Cookieとの関係

ページネーションリンク自体は Cookie を含まない。リンクの辿りは
サーバ発行URLの完全形で行われ、セッション継続はブラウザ/WebView側の
Cookie ストアに依存する（パーサーはHTTP送信を行わないため対象外）。
