# URL抽出の規則

> パーサー: baidu_parser 1.0.0 / `baidu_parser/urls.py`, `extractors.py`

## 3種類のURLを混同しない

| フィールド | 意味 | 所在 |
|---|---|---|
| `url` | 結果が指す外部URL（HTMLに明示されたものだけ） | `data-log` の `mu`、または `data-click-info.extra.url` |
| `click_url` | タイトルリンクが実際に指すURL（そのまま保持） | `article[rl-link-href]`、またはタイトルを包む `a[href]` |
| `display_url` | 表示用ドメイン | `data-click-info.extra.fusion_site` |

## `url`（外部URL）の根拠

1. 第一根拠: `.c-result` の `data-log` 属性JSONの `mu`。
   サーバが結果ごとに記録した実URL。全サンプルの通常結果で存在した。
2. 第二根拠: `article[data-click-info]` の `extra.url`
   （二重パーセントエンコードを2回デコード）。`url_source` に
   どちらの根拠か（`data_log.mu` / `data_click_info.extra.url`）を記録する。
3. どちらも無い場合は `url=null`。**リダイレクト先を推測で作らない。**
   疑似URL（`nourl.ubs.baidu.com` 等）はカードの `url` に採用しない。

## `click_url` の分類（`click_url_kind`）

| 値 | 条件 | 実測例 |
|---|---|---|
| `baidu_redirect` | Baiduドメイン上の http(s) で、パス末尾が `/tc`（クリック計測エンドポイント） | `https://m.baidu.com/from=0/.../t=zbios/l=1/tc?...` |
| `baidu_app_scheme` | `baiduboxapp://` スキーム（アプリ内遷移） | 百家号フィード、百科 swan、動画等 |
| `baidu_internal` | その他の Baiduドメイン http(s) | `https://baike.baidu.com/...` |
| `direct_external` | Baidu以外の http(s) | （サンプル内では少数） |
| `other_scheme` | その他 | — |

`is_baidu_redirect` は `click_url_kind == "baidu_redirect"` と同値の便利フラグ。
クリックURLのトラッキングパラメータ（`lid`, `eqid`, `clk_info` 等）は
**削除せず原文どおり**保持する。

## 相対URL

`href` が相対パスの場合は `page_url` を基底に `urljoin` で絶対化する
（これが唯一の変換）。実測ページ内の結果リンクは全て絶対URLだったため、
相対URLの扱いは合成フィクスチャでテストしている。

## 注意点（実測で観測した癖）

- `data-click-info.extra.url` のデコード結果には、サーバ側の都合で
  `?aldtype=85&#en/zh/weather` のような形（フラグメント直前に `&` が
  入る）が現れることがある。原文どおり記録し、整形しない。
- `mu` が Baidu内部ページ（`mc.baidu.com` の検索ページ等）を指す
  通常結果も存在する。その場合も `url` は `mu` のまま、
  `domain` はそのホストになる。
- サイトリンク・カード内リンクのURLもクリックURL形式
  （m.baidu.com 経由または baiduboxapp）であり、外部URLへは変換しない。
