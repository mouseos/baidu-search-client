# JSON スキーマ互換性（第18ラウンド）

実施日: 2026-10-26（JST）

## 1. 結論

第16〜17ラウンドで確定した構造化 JSON の形式は**変更していない**。
スキーマ変更は不要だったため、旧形式との互換性は完全に維持される。

## 2. 検証方法

保存済みサンプルと、新パッケージで生成した JSON を比較した
（`tests/test_packaging_consistency.py` に恒常テストとして実装）。

### 集約 JSON（baidu_search）

- 比較対象: 第17ラウンド保存の
  `baidu-search-client/samples/tianqi_multipage_offline.json` と、
  同じフィクスチャ・同じフェイク transport で新規生成した出力。
- 比較から分離した動的値: 1ページ目の生成 URL（現在時刻から作る
  ant_ct を含む）に由来する `pages[0].source_url` /
  `pages[0].final_url` / 1ページ目要素の `source_page_url` のみ。
  これら以外は**全文一致**した。
- 一致を確認した内容: トップレベルキー集合と順序、`diagnostics`
  のキー集合、結果の順序・タイトル・URL・概要・カード分類・
  ページ情報（pn / 件数 / next_url）、重複判定。

### パーサー JSON（baidu_parser）

- 比較対象: 第16ラウンド保存の `samples/tianqi_p1.results.json` /
  `weather_en.results.json` と、同じフィクスチャの新規パース結果。
- キー集合、結果の (type, title, url, display_position,
  organic_rank) の並び、カードの並び、`page.pn` / `page.next_pn`
  が一致した。保存サンプル側で秘匿化された `next_url` 内の
  セッション値は比較対象から外している。

## 3. 維持を確認した主な項目

トップレベル: `client`（name/version）、`query`、`pages_requested`、
`pages_fetched`、`results`、`ads`、`cards`、`related_searches`、
`unknown_elements`、`pages`、`diagnostics`（`duplicates` /
`duplicate_items` / `errors` / `warnings`）。

結果要素: `display_position`、`position_in_page`、`organic_rank`、
`global_organic_rank`（複数ページ横断の通し順位、第17ラウンドで
追加された新フィールド）、`title`、`url`、`click_url`、
`click_url_kind`、`url_source`、`display_url`、`domain`、
`is_baidu_redirect`、`snippet`、`site_name`、`date`、`thumbnail`、
`sitelinks`、`tpl`、`srcid`、`duplicate`（重複フラグ、要素は
削除されない）。

クリーン環境の実通信出力（`live_clean_install_tianqi_2pages.json`）
も同じキー構造であることを目視確認した。
