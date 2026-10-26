# 統合アーキテクチャ

## 目的

第1〜16ラウンドの成果（APK解析、検証済みPython通信コード、
`baidu_parser` 1.0.0）を、検索語入力から構造化JSON出力まで
一貫実行できる単一のPythonクライアント `baidu_search` に統合する。
既存コードは正本として再利用し、新規実装は統合層に限定した。

## 構成図

```
                ┌─────────────────────────────────────────────┐
  query ──────▶ │ baidu_search (本パッケージ, 統合層)          │
                │                                             │
                │  search_url.py ── importlib で読み込み ──┐  │
                │  session.py    (requests.Session包摂)    │  │
                │  transport.py  (GET+安全制限+エラー分類)  │  │
                │  client.py     (検証→パース→次ページ)     │  │
                │  pagination.py (次URL検証・循環検出)      │  │
                │  models.py     (複数ページ集約)           │  │
                │  errors.py     (kind付き例外階層)         │  │
                │  cli.py        (python -m baidu_search)  │  │
                └───────┬──────────────────────┬─────────────┘
                        │ 再利用                │ 再利用
            ┌───────────▼───────────┐  ┌───────▼────────────────┐
            │ work/python-validation│  │ baidu-search-parser/   │
            │  search_probe.py      │  │  baidu_parser 1.0.0    │
            │   build_search_url()  │  │  parse_search_results()│
            │  crypto.py            │  │  (変更なし)            │
            │   make_ant_ct()       │  │                        │
            └───────────────────────┘  └────────────────────────┘
```

## モジュールの役割

| ファイル | 役割 |
|---|---|
| `baidu_search/search_url.py` | 検証済み `search_probe.build_search_url` への薄いアダプタ。URL生成・パラメータ・ant_ct を一切再実装しない |
| `baidu_search/session.py` | `requests.Session` の生成（UA・Accept は検証プローブと同一）と Cookie jar の保持、close。Cookie値は外に出さない |
| `baidu_search/transport.py` | 1回のGET。タイムアウト必須、本文ストリーミング＋上限、リクエスト間隔、リダイレクト先ホスト検証、例外→型付きエラー変換。リトライなし |
| `baidu_search/client.py` | 公開API。応答の妥当性検証（検証ページ検出／検索結果ページ判定／空結果／WAFタイトル警告）、パーサー呼び出し、ページネーションループ、集約 |
| `baidu_search/pagination.py` | サーバ発行 next_url の検証（スキーム・ホスト）と完全一致文字列での循環検出。URLは改変しない |
| `baidu_search/models.py` | `SinglePageResult` / `AggregatedSearch` / `PageRecord`。集約時の重複検出と順位注釈 |
| `baidu_search/errors.py` | `kind` 文字列を持つ例外階層（詳細は json-output-schema / known-limitations 参照） |
| `baidu_search/cli.py` | CLI。実通信モードと `--from-html` オフラインモード |
| `baidu_search/_deps.py` | 兄弟プロジェクト（パーサー／検証コード）の所在解決。環境変数で上書き可能 |

## データフロー（search）

1. `build_initial_search_url(query)` で初回URLを生成（従来どおり）。
2. `transport.fetch(url)` で取得。同一 `SearchSession` を全ページで共有。
3. 応答を検証してから `parse_search_results(body, query, page_url=final_url)`。
4. パーサーが返す `page.next_url`（サーバ発行・原文）を検証し、
   未取得なら次ページとして取得。指定ページ数到達／next_url なし／
   循環／不正URL／通信エラー／制限応答で終了。
5. `models.aggregate()` がページ別結果を集約。失敗したページは
   `PageRecord(error=...)` と `diagnostics.errors` に残し、
   取得済みデータは破棄しない。

## 設計上の不変条件

- ant_ct の時刻は**秒**（ミリ秒バグを復活させない。テストで復号して固定検証）。
- 次ページURLは組み立てない・正規化しない。
- TLS検証は常時有効。403/429では再試行しない。
- 推測した端末識別子・パラメータは追加しない（検証コードの出力が上限）。
- パーサーの順位フィールド（display_position / position_in_page /
  organic_rank）は上書きしない。横断順位は新フィールド
  `global_organic_rank` として追加。
