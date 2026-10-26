# 依存関係監査（第18ラウンド）

実施日: 2026-10-26（JST）
対象: `baidu-search-client/`、`baidu-search-parser/`、
`work/python-validation/search_probe.py` / `crypto.py`、
各 `pyproject.toml` / `requirements.txt`

監査方法: 全ソースを対象に `sys.path` / `importlib` / `os.environ` /
`__file__` 由来パス / 絶対パス / ファイル open を grep で全数確認し、
import 文を分類した。ベースラインとして監査前に既存テストを再実行し、
パーサー31件・クライアント44件の全合格を確認した。

## 1. 監査で見つかったワークスペース依存（すべて実行時依存）

| # | 場所 | 依存の種類 | 内容 | 区分 |
|---|---|---|---|---|
| D1 | `baidu_search/_deps.py` | 相対パス（`__file__` 由来）＋ `sys.path` 動的変更 | 兄弟ディレクトリ `../baidu-search-parser/` を探して `sys.path` へ挿入し `baidu_parser` を import 可能にしていた | 実行時 |
| D2 | `baidu_search/_deps.py` | 環境変数への暗黙依存 | `BAIDU_PARSER_DIR` / `BAIDU_LEGACY_VALIDATION_DIR` で場所を上書き可能だった | 実行時 |
| D3 | `baidu_search/search_url.py` | `importlib` による外部ファイル読み込み | `../work/python-validation/search_probe.py` をファイルパス指定でロードしていた | 実行時 |
| D4 | `work/python-validation/search_probe.py`（ロード側） | `sys.path` 動的変更＋副作用 | import 時に自ディレクトリを `sys.path` へ挿入、`crypto` を通常 import、さらに `response_samples/` ディレクトリを生成していた | 実行時（D3経由） |
| D5 | `baidu_search/client.py` | import 時副作用 | モジュール import 時に `_deps.ensure_parser_importable()` を実行していた | 実行時 |
| D6 | `baidu-search-client/pyproject.toml` | メタデータ不整合 | 実質的に必要な `baidu_parser` が依存として宣言されず、逆にクライアント自身が直接使わない `lxml` を宣言していた（コメントで「再利用部品が使う」と説明） | 実行時（宣言） |

## 2. 監査で見つかった開発・検証時のみの依存（実行時には不要）

| # | 場所 | 内容 |
|---|---|---|
| V1 | 両プロジェクトの `tests/conftest.py` | `sys.path` へプロジェクトルートを挿入。クライアント側は兄弟プロジェクトのフィクスチャ (`../baidu-search-parser/tests/fixtures`) を相対参照 |
| V2 | `baidu_search/search_url.py::_load_legacy` | 旧 `search_url.py` では実行時経路そのものだったが、第18ラウンドで「テスト専用サポート」へ降格（下記 §4） |
| V3 | `samples/make_offline_sample.py` 等 | `sys.path` 操作とテスト用モジュールの import（サンプル再生成専用） |
| V4 | プロキシ環境変数 | `requests` の標準動作として `HTTP_PROXY` 等を参照する。これは正規の利用であり暗黙依存として記録する（値は成果物に記録しない） |

## 3. パッケージ外の設定・データファイル

- 実行時に読む設定ファイル・データファイルは**無い**（監査で確認）。
  `baidu_parser` は入力 HTML のみ、`baidu_search` はコード内定数
  （URLテンプレート、tnconfig 静的値、鍵・IV リテラル）のみで動作する。
- テストフィクスチャ（HTML）は実行時依存ではなく検証用資産。

## 4. 排除の実施内容

| 依存 | 対応 |
|---|---|
| D1, D2, D5 | `_deps.py` を**削除**。`client.py` は通常の `from baidu_parser import parse_search_results` のみ。環境変数による場所指定も廃止 |
| D3, D4 | 検証済み処理をパッケージ内へ移設（`baidu_search/antct.py` = crypto.py、`baidu_search/urlbuild.py` = search_probe.py の URL 生成部）。実行時経路は外部ファイルを一切読まない |
| D6 | `pyproject.toml` を是正: 配布名 `baidu-search`、依存は `requests>=2.31` / `pycryptodome>=3.19` / `baidu-parser>=1.0.0,<2.0.0`（`lxml` は baidu-parser の依存として推移的に入る）。開発用依存は `test` extra へ分離 |
| V2 | `search_url._load_legacy()` は出力一致テスト専用として残置（docstring に明記）。実行時コードからは呼ばれないことは `test_runtime_does_not_load_legacy_modules` が検証 |

移設の記録（コピー元と変更内容）:

- `antct.py`: `crypto.py` の全文コピー。変更はモジュール docstring への
  来歴追記のみ。定数（鍵・IV の Base64 リテラル）・関数本体は無変更。
- `urlbuild.py`: `search_probe.py` から `APP_VERSION` / `USER_AGENT` /
  符号化ユーティリティ / pu マージ / テンプレート定数 /
  `process_web_search_url_static` / `build_t_samp` / `build_search_url`
  を機械的に抽出。関数本体は無変更。移設しなかったもの:
  クラシック sug 生成（本クライアント未使用）、送受信・記録系、
  `sys.path` 操作、`requests` import、`OUT_DIR` 生成。
  `make_ant_ct` は相対 import（`from .antct import`）へ変更。
- `search_url.py`: 内蔵 `urlbuild` への薄いアダプタへ書き換え。
  公開関数 `user_agent()` / `build_initial_search_url(query, now_ms=None)`
  のシグネチャと意味は不変。時刻は引き続き**秒**単位
  （`now_ms // 1000`、ミリ秒版ロジックは復活させていない）。

## 5. 移設後の第三者ライブラリ依存（実行時）

| パッケージ | 直接 import するもの | 用途 |
|---|---|---|
| baidu-parser 1.0.0 | `lxml` のみ（他は標準ライブラリ） | HTML の DOM 解析。HTTP 依存なし |
| baidu-search 1.0.0 | `requests`、`pycryptodome`（`Crypto.Cipher.AES`）、`baidu-parser` | HTTP 通信、ant_ct の AES-128-CBC、HTML 構造化 |

## 6. 結論

監査で特定した実行時のワークスペース依存（D1〜D6）はすべて排除した。
残るワークスペース参照はテスト・サンプル生成コード（V1・V3）と、
一致検証専用の `_load_legacy`（V2）のみであり、いずれもインストール
されたパッケージの実行には不要である。クリーン環境検証
（clean-install-validation.md）で、ワークスペース外・`PYTHONPATH`
未設定・元ソース参照不可の条件で動作することを実証した。
