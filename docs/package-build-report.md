# パッケージビルド報告（第18ラウンド）

実施日: 2026-10-26（JST）
ビルド環境: Python 3.12.3、`python -m build` 1.6.1（PEP 517/518、
ビルドバックエンド `setuptools.build_meta`、`setuptools>=68`）

## 1. パッケージ構成

| 配布名 | import 名 | バージョン | 対応 Python | ランタイム依存 |
|---|---|---|---|---|
| baidu-parser | `baidu_parser` | 1.0.0 | >=3.10 | `lxml>=4.9` |
| baidu-search | `baidu_search` | 1.0.0 | >=3.10 | `requests>=2.31`、`pycryptodome>=3.19`、`baidu-parser>=1.0.0,<2.0.0` |

- 開発用依存（pytest）は両者とも `test` extra へ分離。
- レイアウトは既存のフラット構成を維持（公開 API を変えないため
  src/ レイアウトへは移行しなかった）。
- `baidu_search` をインストールすると `baidu-parser` が依存として
  自動解決される（クリーン環境検証で実証）。

## 2. 実行コマンドと結果

```bash
python3 -m venv /tmp/buildenv && /tmp/buildenv/bin/pip install build setuptools wheel
/tmp/buildenv/bin/python -m build --outdir dist baidu-search-parser   # exit 0
/tmp/buildenv/bin/python -m build --outdir dist baidu-search-client   # exit 0
```

生成物（`~/workspace/baidu-search-analysis/dist/`）:

| ファイル | サイズ |
|---|---|
| `baidu_parser-1.0.0-py3-none-any.whl` | 17,058 B |
| `baidu_parser-1.0.0.tar.gz` | 312,132 B（テストフィクスチャ含む） |
| `baidu_search-1.0.0-py3-none-any.whl` | 27,408 B |
| `baidu_search-1.0.0.tar.gz` | 36,554 B |

（README のパッケージング説明を更新したため最終版として再ビルドした。
コードファイルは初回ビルドから無変更であり、再ビルド後も sdist
再ビルドとのコード一致とクリーン環境オフライン検証 8/8 を再確認した。）

## 3. wheel 内容検証

両 wheel とも「パッケージの .py ファイル + dist-info」のみで構成され、
次が含まれないことを目視＋一覧で確認した:

- テスト、サンプル、JSON 出力、開発用ログ
- APK 本体、逆コンパイル結果、通信キャプチャ
- 個人情報、認証情報、Cookie 実値

wheel の METADATA は宣言どおり（Name / Version / Requires-Python /
Requires-Dist を抽出確認）。

## 4. 混入スキャン

wheel と sdist を展開し、次を grep で全数スキャンした: 絶対パス
（`/home/hatch`）、`.apk`、Cookie 値らしき文字列（`BAIDUID=<値>`、
`Set-Cookie: <名前>=`）。**いずれも検出なし**。
sdist に含まれるパーサーのテストフィクスチャは第16ラウンドで
セッション識別値を除去済みのもの（`REDACTED` マーカー入り）である
ことを確認した。

## 5. sdist からの再ビルド

```bash
tar xzf dist/baidu_parser-1.0.0.tar.gz -C /tmp/rebuild
tar xzf dist/baidu_search-1.0.0.tar.gz -C /tmp/rebuild
python -m build --wheel --outdir dist/rebuilt /tmp/rebuild/baidu_parser-1.0.0   # exit 0
python -m build --wheel --outdir dist/rebuilt /tmp/rebuild/baidu_search-1.0.0   # exit 0
```

再ビルドした wheel（`dist/rebuilt/`）は、元の wheel と
ファイル一覧が一致し、コードファイルの内容も**全てバイト一致**
した（RECORD / METADATA を除く）。

## 6. ビルド時に発生した問題と修正

- 初回ビルド前、移設した `antct.py` / `urlbuild.py` の書き込みで
  インデント欠落が発生したため、原本からの機械的コピー＋抽出に
  やり直した（アルゴリズムの手写しを避ける意味でも正しい方法）。
  その後 `ast.parse` と全テストで健全性を確認した。
- CLI テストがサブプロセス経由のため、開発 venv へ
  `pip install -e ../baidu-search-parser` が必要だった。これは
  パッケージ化後の正規の姿（依存はインストールで解決）であり、
  テスト側の変更ではなく環境側の是正として実施した。
