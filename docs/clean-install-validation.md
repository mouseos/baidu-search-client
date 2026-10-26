# クリーン環境インストール検証（第18ラウンド）

実施日: 2026-10-26（JST）
検証スクリプト: `verify_clean_install.py`（本ディレクトリ）
生レポート: `clean-install-report.json`（同スクリプトがコピーを保存）

## 1. 検証条件

- 新規一時ディレクトリ配下に venv を2つ作成（クライアント用 /
  パーサー単独用）。既存の `.venv` は使わない。
- インストールは `dist/` の wheel のみを `--find-links` で与え、
  依存はパッケージメタデータから解決させる。
- 実行時の cwd は一時ディレクトリ内の `site/`（ワークスペース外）。
- 環境変数 `PYTHONPATH`、`BAIDU_PARSER_DIR`、
  `BAIDU_LEGACY_VALIDATION_DIR` は除去して実行する。
- import されたモジュールの実パスが venv の `site-packages` 内で
  あることを assert で確認する（元ソースを参照していない証明）。
- オフライン用フィクスチャは、ワークスペースではなく検証用
  ディレクトリへコピーしたものを使う。

## 2. 結果（オフライン 8/8、実通信込み 9/9）

| # | 検証項目 | 結果 |
|---|---|---|
| 1 | `pip install baidu-search==1.0.0`（find-links=dist） | OK。`baidu-parser-1.0.0`、`requests`、`pycryptodome`、`lxml` 等が依存解決されて入った |
| 2 | `baidu-parser` が依存として入ったこと | OK（pip show で Version 1.0.0 と Location=site-packages を確認） |
| 3 | ワークスペース外からの import | OK（両モジュールとも site-packages からロード、`sys.path` に python-validation を含まないことも確認） |
| 4 | Python API（オフライン、スタブセッションで2ページ） | OK。pages_fetched=2、results=11、cards=8。結果要素に `global_organic_rank` / `duplicate` 等の必須キーが揃う |
| 5 | CLI（`python -m baidu_search --from-html` でコピー済みフィクスチャを処理） | OK。終了コード0、pages_fetched=1、results=5、verbose 診断も出力 |
| 6 | コンソールスクリプト `baidu-search`（オフライン、英語フィクスチャ） | OK。標準出力 JSON が妥当（query=weather、pages_fetched=1） |
| 7 | `baidu-parser` 単独インストール | OK（wheel 直接指定。依存は lxml のみ解決） |
| 8 | パーサー単独でフィクスチャをパースし第16ラウンド保存サンプルと一致 | OK（results=5、cards=4、順序・タイトル・URL・next_pn が一致）。同時に、この venv では `baidu_search` が import **できない**ことも確認（単独性） |
| 9 | 実通信（--live、次節） | OK |

## 3. 実通信検証（インストール済み wheel から）

条件: オフライン検証が全て成功した後に、同じクリーン venv の
インストール済みパッケージから実行。リクエストは合計3回
（`search_page("天气")` 1回 + `search("天气", max_pages=2)` の2ページ）。

結果:

- `search_page("天气")`: HTTP 200、結果5件を JSON に格納。
- `search("天气", max_pages=2)`: pages_fetched=2、結果9件、
  カード9件、エラー0件。制限応答・CAPTCHA は発生しなかった。
- 出力サンプル: `baidu-search-client/samples/live_clean_install_tianqi_2pages.json`

実通信の結果件数はフィクスチャ（実測保存分）とは一致しない
（ライブの検索結果は変動するため）。オフライン検証の結果とは
区別して記録する。

## 4. 実行コマンド

```bash
python3 verify_clean_install.py            # オフライン 8/8 OK, exit 0
python3 verify_clean_install.py --live     # 実通信込み 9/9 OK, exit 0
```

初回実行ではスタブセッションの `iter_content` 実装不備で検証4が
失敗した（transport が要求する最小インターフェースを直接実装する
形にスクリプトを修正し、再実行で解消）。パッケージ側の問題では
なかった。
