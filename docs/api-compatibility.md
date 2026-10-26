# API 互換性（第18ラウンド）

実施日: 2026-10-26（JST）

第17ラウンドまでの公開 API はすべて維持した。パッケージ内部の
配置（検証済み処理の内蔵化、`_deps.py` の削除、配布名の変更）は
利用者側の呼び出し方に影響しない。

## 1. Python API

| API | 状態 | 確認方法 |
|---|---|---|
| `from baidu_search import BaiduSearchClient` | 維持 | 既存テスト全件 + クリーン環境 import |
| `BaiduSearchClient()`（キーワード引数: timeout / max_pages_limit / min_request_interval / max_response_bytes / session / transport） | 維持（無変更） | 既存テスト |
| `client.search(query, max_pages=...)` → `AggregatedSearch` | 維持 | モックテスト（1〜3ページ）+ オフライン統合 + 実通信 |
| `client.search_page(query)` → `SinglePageResult` | 維持 | `test_search_page_single_api` + 実通信 |
| `result.to_dict()` | 維持（出力形式は json-schema-compatibility.md） | スキーマ互換テスト |
| `client.close()` / `with` 文（コンテキストマネージャ） | 維持 | 既存テスト |
| `client.cookie_names`（名前のみ、値は出さない） | 維持 | 既存テスト |
| `from baidu_parser import parse_search_results(html, query=..., page_url=...)` | 維持 | パーサー既存31テスト + 単独インストール検証 |
| `baidu_search.errors` の例外階層と `kind` 文字列 | 維持（無変更） | エラーテスト12件 |

## 2. CLI

| 呼び出し | 状態 |
|---|---|
| `python -m baidu_search --query "天气" --pages 2 --output results.json` | 維持。クリーン環境でも動作（オフライン経路で実証、実通信は API 経由で実証） |
| `--timeout` / `--verbose` | 維持 |
| `--from-html FILE`（オフライン入力）/ `--page-url` | 維持。クリーン環境の検証5で使用 |
| コンソールスクリプト `baidu-search` | 維持（pyproject の entry point は従来どおり）。検証6で動作確認 |
| `python -m baidu_parser` / コンソールスクリプト `baidu-parser` | 第18ラウンドで entry point を正式宣言（従来は `__main__` のみ） |
| 終了コード規約（0=1ページ以上成功、2=取得完全失敗、1=引数エラー） | 維持 |

## 3. 変更した内部事項（公開 API ではない）

- `baidu_search._deps` モジュールを削除した（内部ヘルパーであり、
  公開 API として文書化されていない）。環境変数
  `BAIDU_PARSER_DIR` / `BAIDU_LEGACY_VALIDATION_DIR` による
  場所指定は廃止した（後者はテスト専用の `_load_legacy` 内でのみ
  参照される）。
- 配布名を `baidu-search-client` から `baidu-search` へ変更した
  （import 名 `baidu_search` は不変）。
- `search_url._load_legacy()` は残置したが、用途を「開発ワーク
  スペースでの出力一致テスト専用」に限定した。実行時経路からは
  呼ばれない。
- テスト側の最小修正が1件ある: `tests/test_search_url.py` の
  ant_ct 復号ヘルパーが、暗黙の副作用でロードされていたレガシー
  `crypto` モジュールに依存していたため、内蔵 `baidu_search.antct`
  を使うよう変更した。アサーション（t が秒であること、w が MD5 で
  あること）は一切変更していない。内蔵版とレガシー版の出力一致は
  専用テスト（test_packaging_consistency.py）が固定ベクタで担保する。

## 4. 時刻固定テストの仕組み

従来どおり `build_initial_search_url(query, now_ms=...)` /
`urlbuild.build_search_url(query, now_ms)` で時刻を固定でき、
ant_ct の t が秒単位であることを固定ベクタで検証している
（ミリ秒版ロジックは存在しない）。
