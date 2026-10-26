# 統合JSON出力スキーマ

`AggregatedSearch.to_dict()` の構造。要素はすべて既存
`baidu_parser` のデータモデル（`ResultEntry` / `CardEntry` 等）の
辞書形を再利用し、集約側は来歴フィールドだけを付加する。
不明な情報は推測で埋めず `null` のままにする。

```json
{
  "client": {"name": "baidu_search", "version": "1.0.0"},
  "query": "天气",
  "pages_requested": 3,
  "pages_fetched": 3,
  "results":      [ /* 通常結果 (baidu_parser ResultEntry + 注釈) */ ],
  "ads":          [ /* 広告 (同上) */ ],
  "cards":        [ /* 特殊カード (CardEntry + 注釈) */ ],
  "related_searches": [ {"query": "...", "url": "...", "source": "...",
                          "page_number": 1, "page_pn": 0,
                          "source_page_url": "..."} ],
  "unknown_elements": [ /* 分類不明要素 (UnknownElement + 注釈) */ ],
  "pages": [
    {"page_number": 1, "pn": 0,
     "source_url": "https://m.baidu.com/s?...",
     "final_url": "https://m.baidu.com/s?...",
     "status_code": 200,
     "next_url": "https://m.baidu.com/.../s?...pn=10...",
     "counts": {"results": 5, "ads": 0, "cards": 4,
                "related_searches": 10, "unknown_elements": 0},
     "parser_warnings": [],
     "error": null}
  ],
  "diagnostics": {
    "duplicates": 0,
    "duplicate_items": [
      {"key": "<url>", "first_page_number": 1,
       "duplicate_page_number": 2, "title": "..."}
    ],
    "errors":   [ {"kind": "http_error", "message": "...",
                   "url": "...", "status_code": 500,
                   "page_fetch_index": 2} ],
    "warnings": [ "waf_title_in_results: ..." ]
  }
}
```

## 集約側が付加する注釈フィールド

| フィールド | 対象 | 意味 |
|---|---|---|
| `page_number` | 全要素 | 何ページ目（取得順、1始まり）から来たか |
| `page_pn` | 全要素 | そのページの pn |
| `source_page_url` | 全要素 | 実際にリクエストしたページURL |
| `global_organic_rank` | results のみ | 複数ページ横断の通常結果順位（**新設**） |
| `duplicate` | results / ads | 完全一致URLの重複フラグ（要素は削除されない） |

パーサー既存の順位フィールド `display_position`（HTMLの order 属性）、
`position_in_page`（ページ内 .c-result 通し番号）、
`organic_rank`（ページ内の通常結果順位）は意味を変えずそのまま保持する。

## ページ単位の失敗

取得・解析に失敗したページは `pages` に
`error`（`{"kind", "message", "url", "status_code"}`）付きで残り、
同じ内容が `diagnostics.errors` にも入る。成功したページの
データは失敗の影響を受けない。1ページも取得できなかった場合
`pages_fetched` は 0 で、各配列は空になる。

## シリアライズ

- `json.dumps(..., ensure_ascii=False)` で UTF-8 のまま出力
  （日本語・中国語が `\uXXXX` 化しない）。
- 全フィールドが標準型のみで構成され、往復変換（dumps→loads）が
  無損失であることをテストで確認している。
