# エラー処理・セキュリティ監査（第18ラウンド）

実施日: 2026-10-26（JST）
方針: 第17ラウンドまでの安全制限は一切弱めていない。本ラウンドの
変更（パッケージ内蔵化）は通信・検証ロジックに触れていないため、
監査は「既存の制限がパッケージ化後も有効であることの再確認」が
中心である。

## 1. 項目別の確認結果

| 項目 | 実装 | 検証 |
|---|---|---|
| 通信タイムアウト | transport が必須の timeout を持ち、超過は `timeout` エラー | `test_timeout` |
| TLS エラー | `verify` を False にする箇所はパッケージ内に存在しない（grep で確認）。SSLError は `tls_error` に分類 | `test_tls_error` |
| DNS エラー | ConnectionError の文面から DNS 系を判別し `dns_error` に分類 | `test_dns_error` |
| 接続エラー | `connection_error` に分類 | `test_connection_error` |
| HTTP 403 / 429 | `access_restricted` を送出し、ページネーションは停止。再試行・回避はしない | `test_http_403_is_access_restricted_and_stops`、`test_http_429_is_access_restricted` |
| HTTP その他エラー | `http_error`（例: 500） | `test_http_500_is_http_error` |
| CAPTCHA・検証ページ | 200 でも `#results` が無く検証マーカーがある場合は `captcha_or_verification`。個別結果の WAF タイトルの混入（実測済みの事象）とは区別し、後者は警告 | `test_captcha_page_is_distinguished_from_results`、`test_waf_title_warning_not_page_rejection` |
| HTTP 200 だが不正な本文 | `#results` も `.c-result` も無い場合は `not_search_result` | `test_not_search_result_html` |
| HTML パースエラー | パーサー例外を `parse_error` に包む | エラーテスト群 |
| ページネーション循環 | 次ページ URL の完全一致で再出現を検出し `pagination_cycle` | `test_cycle_detection` |
| 想定外ホストへの next_url | スキーム（http/https のみ）とホスト（baidu.com またはそのサブドメイン）を検証し `invalid_next_url` | `test_invalid_next_url_external_host`、`test_invalid_next_url_scheme`、`test_validate_next_url_verbatim_and_hosts` |
| リダイレクト先の検証 | **各段階の最終到達先**だけでなく、リダイレクトが発生した場合は最終 URL のホストが Baidu 系でなければ `redirect_error`。リダイレクト過多も `redirect_error` | `test_redirect_to_foreign_host_rejected`、`test_too_many_redirects`、第18ラウンド追加 `test_redirect_to_external_host_is_rejected`（履歴1段＋外部ホスト最終 URL のケース） |
| 過大レスポンス | ストリーミングで上限（既定 8MB）を超えたら `response_too_large` で中断 | `test_response_too_large` |
| 不正な JSON 入力 | パーサーは埋め込み JSON の解釈に失敗しても例外で落とさず、抽出可能な範囲と診断情報で返す（第16ラウンドの設計を維持） | パーサーテスト31件 |
| 検索語の文字種 | 日本語・中国語・空白・記号（`C++ 入門 & テスト?` 等）を含む検索語で URL 生成がレガシーと一致し、検索が動作する | `test_japanese_query`、`test_english_query`、第18ラウンド追加の固定ベクタ |
| 途中ページのエラー | 取得済みページを破棄せず、エラーは `diagnostics.errors` に分離記録 | `test_mid_pagination_http_error_keeps_fetched_pages` |
| 空の検索結果 | 例外ではなく「0件＋警告」として返す | `test_empty_results_page_is_data_not_exception` |

注: transport のリダイレクト検証は、requests が辿った後の最終 URL
と履歴件数に基づく（各段の Location を個別に検査する仕組みでは
ない）。ただし想定外ホストへ**到達した**時点で必ず拒否されるため、
「意図しない外部ホストの内容を検索結果として取り込む」ことは
起きない。中間ホストへのリクエスト自体を防ぎたい場合は
allow_redirects の手動制御が必要で、現行の制限範囲を超えるため
未実施（release-readiness.md の残課題に記載）。

## 2. 秘密情報の非露出

- Cookie はセッション内にのみ保持し、クライアントが公開するのは
  **名前だけ**（`cookie_names`）。値はログ・例外・JSON のどこにも
  出ない設計であり、第18ラウンドで専用テストを追加した:
  403 応答に Set-Cookie の番兵値を仕込んでも、集約 JSON と
  エラー記録に値が現れないことを assert する
  （`test_cookie_values_never_leak_into_errors`）。
- エラーオブジェクト（`to_dict()`）に含まれるのは kind / message /
  url / status_code のみで、ヘッダ値は含まれない。
- CLI の `--verbose` 出力は件数サマリのみ。
- wheel / sdist への秘密情報混入スキャンは package-build-report.md
  §4 のとおり検出なし。

## 3. 外部 HTML の取り扱い

- 取得した HTML は lxml でデータとして解析するのみで、コードとして
  実行する経路は無い（`eval` / `exec` / テンプレート実行などは
  パッケージ内に存在しないことを grep で確認）。
- 外部 URL は表示・記録用に保持するだけで、パーサー側が自動で
  辿ることは無い。クライアントが自動アクセスするのは検証済みの
  Baidu 系次ページ URL のみ（§1）。

## 4. その他の不変条件

- TLS 証明書検証の無効化: なし（第18ラウンドでも導入していない）。
- 未知の端末識別子・認証情報の生成: なし（URL 生成は静的確定範囲
  のみ、という第1〜17ラウンドの方針を内蔵版でも維持）。
- 無制限リトライ: なし（リトライ自体を行わない）。
- プロキシ: requests の標準解決（環境変数）を使う正規経路のみ。
