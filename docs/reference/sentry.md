# Sentry統合リファレンス

*最終更新: 2026-08-07*

## 🛡️ 概要

Sentry SDKによるエラー監視と、機密データを送信前にスクラブする実装を説明します。Sentry連携は既定で無効なopt-inです。

主要な実装は次の責務に分かれています。

| 責務 | 実装 |
|------|------|
| SDK初期化 | [`utils/sentry_init.py`](../../utils/sentry_init.py) |
| 機密キー定義 | [`SENSITIVE_KEYS`](../../utils/sentry_scrub_primitives.py) |
| イベントスクラブ | [`utils/sentry_scrub_events.py`](../../utils/sentry_scrub_events.py) |
| 値の再帰スクラブ | [`utils/sentry_scrub_values.py`](../../utils/sentry_scrub_values.py) |
| structlog連携 | [`utils/logger.py`](../../utils/logger.py) |
| 設定モデル | [`SentryConfig`](../../config/settings.py) |

## 設定

DSNはリポジトリへ保存せず、実行環境から注入します。

```bash
SENTRY__ENABLED=false
# 有効化する場合は、DSNを実行環境から注入する
SENTRY__ENABLED=true
SENTRY__DSN=<your-dsn>
```

主な設定項目は `SENTRY__ENVIRONMENT`、`SENTRY__TRACES_SAMPLE_RATE`、`SENTRY__PROFILES_SAMPLE_RATE`、`SENTRY__SEND_DEFAULT_PII` です。PII送信は既定で無効です。

Dockerで有効化する場合は、対象サービスへ `SENTRY__DSN` を明示的に渡します。ホスト環境のDSNが自動的にコンテナへ継承される前提にはしません。

## 🚀 初期化

アプリケーションの起動境界で初期化する場合は、SDK初期化の成否を確認します。

```python
from utils.sentry_init import init_sentry

sentry_enabled = init_sentry()
```

このリポジトリでは、実DSNによる本番送信や継続監視の稼働までは確認していません。

## 初期化失敗ポリシー

本番相当環境では初期化失敗をfail-fastとして扱い、開発・テスト環境では警告してアプリケーションを継続します。これは監視設定の欠落を本番で見逃さず、ローカルテストを外部サービス障害へ依存させないためです。

## 送信対象と障害時の挙動

Sentryを有効化している場合、structlogのログはERROR以上（`error` / `critical` / `exception`）が自動的にSentryへ送信されます。structlogの`exception`レベルはSentry側に存在しないため、`error`へ正規化します。

送信判定はstructlogのレベルフィルタより後段で行います。したがって`LOG__LEVEL`をERRORより高く設定すると、ERRORログはSentryにも届きません。ログ量の削減を目的にレベルを引き上げる場合は、エラー監視が同時に無効化される点に注意してください。

送信自体が失敗しても、ネットワーク障害などの運用エラーはアプリケーションを停止させません。失敗は`[SENTRY_ERROR]`としてstderrへ出力し、警告の再出力は5分間隔に制限するため、ERRORが連続してもログを埋め尽くしません。一方で`KeyboardInterrupt`や`MemoryError`などのシステム例外は握りつぶさずに再送出します。監視のための処理がgraceful shutdownやOOM検知を妨げないためです。

## 機密データ保護

44種の機密キーパターンを基準に、イベント・例外・タグ・URLなどを防御的にスクラブします。これは既知のキー名に対する保護であり、任意の個人情報が完全に検出されることを意味しません。新しい外部入力を追加する場合は、送信境界のテストとキー集合の見直しを行ってください。

structlogで`bind`したコンテキストとログ呼び出しのキーワード引数は、いずれもSentryの`extra`として送信されます。除外するのは`event`・`level`・`timestamp`・`exc_info`・`logger`の5キーのみです。スクラブはキー名を基準に判定するため、機密キー集合に無い名前で機密値を渡すと素通しします。

`before_send`によるイベント処理と、トランザクション／スパンの処理は別のSDKフックです。両者を混同しないよう、変更時は [`sentry_scrub_events.py`](../../utils/sentry_scrub_events.py) と関連テストを確認してください。

## 🔎 SDKとSentry MCP

このポートフォリオでは、開発時のエラー調査に Sentry MCP サーバーを利用できます。これは開発者が使うツールであり、アプリケーションが実行時にエラーを送信する Sentry SDK 統合とは別のレイヤーです。

MCPの接続設定は利用するAIコーディングツールのローカル設定で保持するため、本リポジトリには含めません。

公式資料: [Sentry MCP Docs](https://docs.sentry.io/product/sentry-mcp/)

## テスト

Sentry関連の回帰確認は、ネットワーク非依存のfocused regressionとして実行します。

```bash
uv run pytest -k sentry -v --no-cov
```

`--no-cov`はカバレッジ計測を無効にするため、このコマンドはSentry機能の回帰確認であり、プロジェクト全体のカバレッジ品質ゲートではありません。

Sentry名を持つテストファイルは10件です。`-k sentry` は `test_config_settings.py` 内のSentry設定テストも含むため、11モジュール・381テストを収集します。

関連テスト:

- [`tests/unit/test_sentry_init.py`](../../tests/unit/test_sentry_init.py)
- [`tests/unit/test_sentry_scrub_primitives.py`](../../tests/unit/test_sentry_scrub_primitives.py)
- [`tests/unit/test_sentry_scrub_values.py`](../../tests/unit/test_sentry_scrub_values.py)
- [`tests/unit/test_sentry_scrub_events.py`](../../tests/unit/test_sentry_scrub_events.py)
- [`tests/unit/test_sentry_transaction_span.py`](../../tests/unit/test_sentry_transaction_span.py)
- [`tests/unit/test_sentry_scrub_event_helpers.py`](../../tests/unit/test_sentry_scrub_event_helpers.py)
- [`tests/unit/test_logger_sentry_capture.py`](../../tests/unit/test_logger_sentry_capture.py)
- [`tests/unit/test_logger_sentry_pii.py`](../../tests/unit/test_logger_sentry_pii.py)
- [`tests/unit/test_logger_sentry_throttle.py`](../../tests/unit/test_logger_sentry_throttle.py)
- [`tests/integration/test_sentry_logging.py`](../../tests/integration/test_sentry_logging.py)

## 未実施事項

現時点で、次の運用はこのリポジトリの実装範囲外です。

- 本番環境へのSentryデプロイ
- 実DSNによる継続監視
- アラートルールとオンコール運用
- release/deploy連携
