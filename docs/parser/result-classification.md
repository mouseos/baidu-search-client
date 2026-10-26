# 検索結果の分類規則

> パーサー: baidu_parser 1.0.0 / `baidu_parser/classifiers.py`
> 根拠: 2026-10-25 実測HTML 5ページ（天气×3、札幌 天気、weather）

## 分類の第一信号: `tpl` 属性

`.c-result` の `tpl`（サーバ側テンプレートID）が分類の主信号。
CSSクラス単独には依存しない。

## 実測で確認した種類（14種の tpl）

| tpl | 分類 | card_kind / 備考 |
|---|---|---|
| `www_index` | 通常結果 (organic) | レイアウト変種が複数（new_srcid 1599 / 1919 等） |
| `www_specific` | 通常結果 (organic) | title+source のみ、概要なし |
| `www_kv` | 通常結果 (organic) | 画像中心レイアウト |
| `weather_forecast_new_san` | カード | `weather`（天気専用情報カード） |
| `sg_kg_entity_san` | カード | `knowledge_graph`（ナレッジグラフ） |
| `bk_polysemy_san` | カード | `baike`（百度百科エントリ） |
| `fy_sg_dict_new_san` | カード | `dictionary`（辞書・翻訳） |
| `wenda_generate` | カード | `ai_answer`（AI生成回答） |
| `vid_recommend` | カード | `video`（動画） |
| `live_converge_san` | カード | `live`（ライブ配信） |
| `tieba_forumcommentxml_san` | カード | `forum`（贴吧） |
| `note_lead` | カード | `note`（フィード图文） |
| `guanfanghao_san` | カード | `official_account`（公式アカウント） |
| `recommend_list_san` | 関連検索ブロック | 結果ではない。「大家还在搜」のクエリ群を抽出 |

### 種類別の確認根拠

- **AI生成回答カード** (`wenda_generate`): 要素内に
  「内容由AI生成」「以上内容均由AI生成」の明記あり（`ai_generated_marker`）。
  ただし静的HTMLに回答本文は含まれない（「正在思考」のプレースホルダのみ。
  本文は動的生成）。`data-log.mu` は `http://nourl.ubs.baidu.com/279` の
  疑似URLのため `url=null` とする。
- **天気カード** (`weather_forecast_new_san`): `mu` は
  `http://www.baidu.com/weather/101010300`。見出し h3 は「生活服务」。
  気温・チャート等は canvas/chart モジュール描画で、テキストとしての
  構造化は行わない（known-limitations.md）。
- **ナレッジカード** (`sg_kg_entity_san`): h3 タイトルを持たない。
  説明文は長文アンカーのテキストとして存在し、`text` に抽出する。
- **百科カード** (`bk_polysemy_san`): h3 タイトル+説明文アンカー+章リンク
  （现象描述/形成原因 等、サイトリンク相当）。
- **ニュース**: 専用 tpl は実測では**未確認**。ニュース性の結果
  （百家号記事等）も `www_index` として配信され、通常結果に分類される。
  `just_pub` ラベル（刚刚发布 等）や相対日付が付く場合がある。
- **画像・動画**: 画像単独の結果 tpl は未確認。動画は `vid_recommend`
  カードとして確認。画像は通常結果内のサムネイルとして現れる。

## 広告の分類

実測ページに広告結果は存在しなかったため、分類器はページ同梱の
広告スタイルシート `ec_ls_css` が定義する規約に基づく:

- 要素内（自身含む）に `ec_` / `ec-` 始まりのクラス、または
  `ec_wise_ad` / `ec_ad_results` クラスが存在する
- 可視の広告ラベル（テキスト全体が「广告」または「廣告」の葉要素）が存在する

いずれかに該当すれば広告として分類する（tpl 判定より優先。
広告枠も tpl を持ちうるため）。該当しないものを推測で広告にしない。
広告は `ads` に分離し、`organic_rank` を付けない。
テストは合成フィクスチャ（tests/fixtures/synthetic_ad.html、
実測ではないことを明記）で担保する。

## 分類不能要素

未知の `tpl` や `tpl` 欠落の要素は推測で organic にせず、
`unknown_elements` に tpl / srcid / 理由付きで記録する。
実測5ページでは分類不能は0件だった。

## 順位の管理

- `display_position`: HTML の `order` 属性そのもの（表示順）。
- `position_in_page`: `.c-result` の DOM 順の通し番号。
- `organic_rank`: 通常結果のみの通し番号（カード・関連・広告を除く）。
- ページ位置: `page.pn` / `page.page_number`（ページネーション側で管理）。

`order` は通常 1..N だが、末尾の関連ブロックでは `400` になる実測が
あるため、順位の決定に配列インデックスは使わず `order` 属性と
DOM順を併記する。
