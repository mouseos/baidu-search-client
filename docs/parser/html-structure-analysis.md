# Baidu検索結果HTML 構造解析（APK / wise 版）

> 対象: com.baidu.searchbox 15.57.1.10 の検索URL生成処理で取得した
> 検索結果HTML（2026-10-25 実測、`work/python-validation/response_samples/`）
> サンプル: 「天气」初回 / pn=10 / pn=20、「札幌 天気」、「weather」
> パーサー: baidu_parser 1.0.0（本ディレクトリ）

## 1. ページ全体の構造

```
html
└─ body.android.cos-wise.cos-android.cos-baiduapp
   └─ div#page.search-page
      └─ div#page-bd.se-page-bd (.first-page は1ページ目のみ)
         ├─ div#results.results          ← 検索結果一覧の親要素
         │   ├─ div.c-result.result ×N   ← 結果・カード・関連ブロック
         │   └─ (style / script / firstpaint 等の非結果ノード)
         ├─ div.new-pagenav              ← ページネーション（後述）
         └─ div.page-relative            ← 「大家还在搜」関連検索（ページ下部）
```

- 検索結果は全て `#results` 直下の `.c-result` 要素として並ぶ。
  `#results` の子で `.c-result` でないものは style/script 等のみ（実測全ページ）。
- レンダリングは San フレームワークの SSR（`data-sanssr`、`san-root`、
  `cosc-` プレフィックスのクラス群、`<!--s-data:{...}-->` コメントに
  コンポーネントの元データJSONが埋め込まれる）。

## 2. `.c-result` の役割と属性

`.c-result` は「結果1件」ではなく「表示ブロック1件」の単位である。
通常結果・特殊カード・関連検索ブロックが混在するため、要素数を
通常検索結果の件数として扱ってはならない（実測: 天気1ページ目は
11要素中、通常結果は5件）。

全要素が持つ属性:

| 属性 | 意味 | 例 |
|---|---|---|
| `order` | HTML上の表示順（1始まり。ただし末尾の関連ブロックは `400` のような大きな値になる実測あり） | `3`, `400` |
| `tpl` | サーバ側テンプレートID。分類の第一信号 | `www_index` |
| `srcid` | データソースID（多くは tpl と同値。数値IDの場合もある） | `34689` |
| `new_srcid` | リソース種別ID | `1599` |
| `data-log` | JSON。`mu`（実URL）・`ensrcid`・`order` を含む | 下記 |
| `data-url-sign` / `url_sign` | 結果の署名ID（一部要素のみ） | — |
| `nr`, `card-runtime` | 表示制御用 | — |

`data-log` の実例（天気1ページ目 order=3）:

```json
{"fm":"alop","ensrcid":"www_index","order":3,
 "mu":"http://weather.cma.cn/",
 "logCommonInfo":{"exposureInfo":{"con_type":"official_web"}}}
```

- `mu` = その結果が指す実URL（サーバが記録した値）。関連ブロックでは
  `http://34689.recommend_list.baidu.com` のような疑似URL、note_lead 等では
  空文字になる。

## 3. 通常検索結果（www_index 系）の内部構造

```
div.c-result[tpl=www_index]
└─ div.c-result-content[san-root]
   └─ article.cosc-card[rl-link-href=<クリックURL>]
        [data-click-info={clk_info, extra:{fusion_site, url, ...}}]
      ├─ div[data-module=title] > h3.cosc-title > span.cosc-title-a
      │     > span.cosc-title-slot > span.tts-b-hl （タイトル文字列）
      ├─ div[data-module=abstract] （概要。pure-summary が包む場合あり）
      │     span.prefix-time_* （相対日付ラベル。例「4小时前」）
      │     span.summary-text_* （概要文。<em> で強調）
      ├─ a[data-module=subpos_1..4].sublink-wrapper_* （サイトリンク）
      ├─ div[data-module=source].cosc-card-footer
      │     <!--s-data:{"sourceData":{"text":<サイト名>,
      │        "time":<日付>, "label":{...}, "avatar":<URL>}}-->
      └─ img （サムネイル。source 内の avatar は除く）
```

識別条件:
- タイトル: `.//h3` のテキスト（`cosc-title-a` 配下）。
- クリックURL: `article[rl-link-href]`。スキームは
  `https://m.baidu.com/...`（リダイレクト）または `baiduboxapp://`（アプリ内遷移）。
- 表示ドメイン: `data-click-info.extra.fusion_site`（例 `weather.cma.cn`）。
- 実URLの第二の所在: `data-click-info.extra.url`（二重パーセントエンコード）。
- サイト名・日付: source モジュールの `s-data` コメント内 `sourceData`。
- 相対日付は abstract 内の `.prefix-time` 要素にも表示される。
- TTS（読み上げ）コントロールの文言（暂停/收听/听）は本文ではないため除外する。

レイアウト変種（いずれも通常結果）:
- `www_specific`: title と source のみ。abstract が存在しない（概要なしが正）。
- `www_kv`: 画像中心レイアウト。title / source / multi-image モジュール。

## 4. 埋め込みJSON・data属性

- `<!--s-data:{...}-->` コメント: San SSR のコンポーネントデータ。
  source モジュール（`sourceData`）と abstract モジュール
  （`summaryData.summaryText`）で抽出に使用。
- `data-log`（属性JSON）: `mu` 等。
- `data-click-info`（article 属性JSON）: `extra` は文字列化JSONで
  `fusion_site` と二重エンコードされた `url` を含む。
- `data-channel-search-datastore` 等の属性にも landingPageUrl を含む
  JSONがあるが、抽出の主経路は上記で足りるため未使用。

## 5. 関連検索

2か所に存在する:
1. `.c-result[tpl=recommend_list_san]`（結果リスト内。見出し「大家还在搜」+
   クエリへのリンク群 `a > span.content-link_*`）
2. `div.page-relative`（ページ下部。同見出し+リンク群）

両者を統合し、クエリ文字列で重複排除する（順序は出現順を保持）。

## 6. ページネーション

`div.new-pagenav`（詳細は pagination-structure.md）。1ページ目は
`a.new-nextpage-only` のみ、2ページ目以降は SSR で同ブロックが
複数回（実測4回）繰り返され、`a.new-prepage` / `a.new-firstpage` /
`a.new-nextpage` / `span.new-nowpage`（「第 N 页」）を持つ。

## 7. 広告について

実測した全サンプルページに広告結果は**存在しなかった**。
ページには広告用スタイルシート `<style id="ec_ls_css">` が同梱され、
広告コンテナの規約（`.ec_ad_results`、`.ec_wise_ad`、
`.ec-material_*`、`div[class^="ec_r"]`）が定義されているのみ。
ページ内の「广告」の出現は、全て関連検索クエリ
「没有广告的天气预报官方版」の文字列だった。
分類器はこのCSS規約と可視の「广告」ラベルを広告信号として実装し、
合成フィクスチャでテストしている（result-classification.md 参照）。
