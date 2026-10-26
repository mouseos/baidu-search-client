# HTTP通信の統合

## 初回検索リクエストの生成（再利用）

`search_url.build_initial_search_url(query)` は、検証ラウンドで
実測成功した `work/python-validation/search_probe.py` の
`build_search_url(query, now_ms)` をそのまま呼ぶ。生成内容は
APK（bq0.m / BaiduIdentityManager.processWebSearchUrl）の静的再現で:

- テンプレート `http://m.baidu.com/s?tn=zbios&pu=sz%401320_480&bd_page_type=1&word=`
  + プレースホルダ `KWD<現在時刻ms>` を Java URLEncoder 済みクエリで置換
- 静的に確定できる pu マージのみ（osname=baiduboxapp、cfrom=tnconfig値、
  csrc=app_mainbox_txt）
- https 昇格、`ant_ct`、`t_samp`（固定キー分）付加

端末固有値（cuid、cua、from、pkgname 等）は従来どおり付けない。
本クライアントが追加したパラメータは存在しない。

## ant_ct と時刻

`crypto.make_ant_ct(now_ms // 1000, query)`（既存 crypto.py を利用、
再実装なし）。APKの `DateTimeUtil.getCalibratedTime()` は
「端末時刻の秒＋校正オフセット mDelta」を返す。Python側では
オフセットを観測できないため、従来の実測と同様に現在の
Unix時刻の**秒**値を mDelta=0 の近似として使う（近似であることは
`search_url.py` のドキュメントにも明記）。
ミリ秒はプレースホルダ `KWD<ms>` 専用であり、過去に訂正した
ミリ秒版 t のロジックは復活させていない（テスト
`test_ant_ct_time_is_seconds_not_milliseconds` が ant_ct を復号して
秒であることを固定検証する）。

## ヘッダーとセッション

- User-Agent は検証プローブの `USER_AGENT` をそのまま使用
  （端末固有部分が代表値である点もプローブ側に明記済みのとおり）。
- `Accept: text/html,*/*`（プローブの検索リクエストと同一）。
- 1つの `requests.Session` を生成し、検索内の全ページで共有する。
  初回応答の Set-Cookie は jar に保持され、後続ページへ自動送信される。
  手動で Cookie 値を生成することはしない。
- `close()` / コンテキストマネージャでセッションを閉じる。
- ログ・JSON・テストのどこにも Cookie の**値**は出さない
  （診断に出るのは名前のみ。モックテストで値がJSONに混入しない
  ことも検証済み）。

## 安全性・安定性（transport.py）

| 項目 | 実装 |
|---|---|
| タイムアウト | 必須（既定25秒、CLI `--timeout` / API引数で変更可） |
| リクエスト間隔 | 既定1.0秒の最小間隔を強制 |
| リトライ | **なし**（無制限リトライ禁止。403/429では即停止） |
| TLS | 証明書検証は常時有効（`verify=False` はコード内に存在しない） |
| 本文上限 | ストリーミング読み取りで既定8MBを超えたら中断し `response_too_large` |
| リダイレクト | requests 標準（上限あり）。Baidu 以外のホストへ転送された場合は `redirect_error` |
| プロキシ | requests 標準の環境変数ベース設定をそのまま利用（正規経路） |
| ログ | URLとステータス・cookie名のみ。秘密情報は扱わない |

## 応答の妥当性検証（client.py）

HTTP 200 だけでは成功としない。順に:

1. 検証ページマーカー（`wappass` 参照・`安全验证`）があり
   `#results` が無い → `captcha_or_verification`。
2. パース後、`.c-result` が0件かつ `#results` コンテナが無い →
   `not_search_result`。
3. 結果ページだが抽出0件 → 例外にせず `empty_results` 警告。
4. 個別結果のタイトルが「WEB 应用防火墙」等のWAF名 → ページは
   有効として処理し `waf_title_in_results` 警告を付ける
   （ページ全体の制限画面とは区別する。第16ラウンドで実測した
   サーバ格納タイトルの事象）。

## 実通信での確認（2026-10-26、合計4リクエスト）

- `search_page("天气")`: HTTP 200、通常結果5件・カード4件、
  next_url あり、セッションに Cookie 7種の名前を確認（値は未記録）。
- `search("天气", max_pages=2)`: 2ページ取得、結果13件に集約、
  重複0、エラーなし。
- CLI `python -m baidu_search --query "天气" --pages 1 --output …`:
  終了コード0、同内容のJSONを UTF-8 で保存。

詳細は `integration-test-report.md` と `samples/live_check_report.json`。
