# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

- **BREAKING (observability)**: `tests/performance/test_api_performance.py` の
  `PerformanceMetrics.get_summary()` が返す `cpu_usage.start_percent` の型を
  `float` (`0.0` 固定) から `float | None` (常に `None`) に変更.
  - **設計意図**: `start_monitoring` 時の `psutil.cpu_percent(interval=None)`
    は warmup として呼び出し戻り値を破棄する仕様 (blocking なしで
    `start_time` 精度を毀損しない). 旧仕様 `0.0` は「未計測」と
    「実測値 0」を区別できず観測性が低下するため `None` で明示.
  - **影響範囲**: `external` marker により PR CI からは除外済み.
    開発者ローカル / 週次 CI のログ出力で `cpu_start_percent: null` が
    出力される.
  - **利用者対応**:
    - structlog 経由の log 消費者 (Datadog / Loki / Splunk / CloudWatch 等)
      で `cpu_start_percent` を numeric field と定義している場合、
      `null` 値で型 mismatch を起こす可能性あり.
    - 対応: nullable numeric として log schema を再定義するか、log consumer
      側で `null → 0` 等の変換ルールを適用する.

### Security

- **Changed (security behavior)**: `utils/sentry_init.py` の機密データ判定を
  正規化付き単語境界 match (`_is_sensitive_key()`) に変更.
  - **変更内容**:
    - 旧: `any(sensitive in key.lower() for sensitive in SENSITIVE_KEYS)`
    - 新: `key.lower().replace("-", "_")` と正規化済み key 集合を
      先頭/末尾/アンダースコア境界で正規表現比較
  - **設計意図 (Senior 視点 — KISS + threat model 駆動)**:
    - **variant key 対応**: `x-auth-token`, `api-key-v2`,
      `aws-access-key-id` のような表記揺れを redact 対象に含める.
    - **defense-in-depth**: Sentry payload は外部 SDK 由来の任意 dict を含むため、
      完全一致より複合キー対応を維持する方が漏洩防止に強い.
  - **影響範囲 (regression リスク)**:
    - `photo_url`, `prototype`, `option` のような unrelated substring は保持し、
      `user_otp`, `otp_secret` のような複合キーは redact する.
    - hyphen / underscore の表記揺れにより redact 漏れになるリスクを低減.
  - **利用者対応**:
    - 新規外部サービス統合時 (AWS / GCP / Azure / Stripe / Auth0 等) は
      当該サービスの credential key 名を SENSITIVE_KEYS に追加する.
    - 詳細は `utils/sentry_init.py` の `SENSITIVE_KEYS` frozenset 定義と
      `_NORMALIZED_SENSITIVE_KEYS` 周辺コメントを参照.
  - **追加された redact key (32 → 39, +7件)**
    （※ 32 は PR#340 で email/ip_address/body_preview 追加後の件数。
    　PR#340 前起点では 29 → 39（+10件））:
    - 認証系: `access_key`
    - HTTP headers: `proxy-authorization`, `set-cookie`, `x-auth-token`,
      `x-csrf-token`, `x-refresh-token`, `x-access-token`
  - **追加されたスクラブ対象フィールド (4 → 5)**: `breadcrumbs` を
    `_SCRUBBED_EVENT_FIELDS` に追加.
  - **意図的に追加しなかった variant (KISS + threat model 駆動)**:
    実証検索 (grep / ast-grep / serena) で payload 経路不在を確認した上で
    以下を SENSITIVE_KEYS から除外. dead config を生まない方針.
    - `aws_secret_access_key` / `aws_session_token`: 本プロジェクト AWS 未使用
      (`.env` に AWS env 不在、AWS SDK / boto3 不導入).
    - `gitlab_token`: GitLab 統合不在.
    - `slack_token`: Slack 統合不在 (`scripts/error_tracker.py` の Slack regex
      は別レイヤーの汎用 CI ログマスキングで本実装と独立).
    - `github_token`: 本プロジェクトで使用中だが Authorization header 経由で
      送信されるため、既存 `authorization` キー redact で防御済.
      独立 key 名での payload 流出経路は実証検索で 0 件 (重複防御不要).
    - 新規外部サービス統合時 (AWS / GCP / Azure / Stripe / Auth0 等) は
      上記方針に従い当該 variant の追加是非を再評価する.

- **Changed (BREAKING for observability contract)**: `utils/sentry_init.py` の
  `_before_send` がスクラブ失敗時に `event` (fail-open) ではなく `None`
  (fail-closed) を返すようになり、scrub 中の orig request dict 変更を排除する
  atomic per-field swap パターンに変更.
  - **変更理由**:
    1. **PII 漏洩経路の遮断 (fail-closed)**: partial-scrub failure mode では
       headers のみ scrub 済み + data / query_string / url は未 scrub の状態で
       event が Sentry に送信され PII 漏洩経路となるため、PII 保護を Sentry
       観測性より優先.
    2. **orig dict 不変性の保証 (atomic swap)**: 旧 mutation pattern
       (`request["headers"] = _scrub_sensitive_data(...)`) では scrub 中に
       例外が発生すると partial-mutate された orig dict が Sentry SDK 内部の
       他経路 (breadcrumb 添付・retry queue 等) で漏洩するリスクが残る. 新 dict
       を build して `event["request"] = new_request` で atomic swap する
       ことで orig dict を不変に保ち、fail-closed 契約を実装層で保証.
  - **影響範囲**: スクラブ失敗時 Sentry 側でエラー event を受信できなくなる.
    失敗の事実は warning log (`sentry_scrub_failed`) で観測可能.
    成功時の挙動は不変 (`event["request"]` の dict identity は変わる).
    Sentry SDK は event 全体を serialize して送信するため、本実装変更が観測可能な
    挙動差を生む経路は確認していない (Sentry SDK source 未検証 — 推察). 万一
    identity 依存経路が判明した場合は git history / commit log を参照。
  - **運用上の留意 (operational concern)**:
    本 BREAKING change により、production の real error が scrub edge case で
    drop され operator が原 error を観測できないリスクが残る.
    導入後の監視推奨:
    1. `sentry_scrub_failed` warning log の発生率を log aggregator
       (Datadog / Loki / CloudWatch 等) で metric 化.
    2. 異常な発生率上昇時は SENSITIVE_KEYS / scrub logic の defect 兆候として
       triage. payload 構造を sanitized form でローカル再現し原因特定.


- **Changed**: `utils/sentry_init.py` の `init_sentry()` の `except Exception`
  分岐で `warnings.warn` を `_logger.warning("sentry_init_failed", ...)` に変更.
  - **変更理由 (Finding #3)**: `filterwarnings('error')` 環境 (pytest -W error)
    で `warnings.warn` が UserWarning を raise → except block 内で CPython が
    `__context__` に元 exc を populate → DSN 漏洩経路となる.
  - **Finding #7**: `SENTRY_DEBUG=False` の非本番環境でも観測性を確保.
  - **二重防御**: ロガー自体の失敗時も静観 (`try/except Exception: pass`) で
    `__context__` 経由 DSN 漏洩を遮断.

- **Fixed**: `utils/sentry_init.py` の `_scrub_sensitive_data` が list の中の
  list (nested list) を再帰的にスクラブするようになった.
  - **変更前**: list 中の dict のみ再帰し、list 中の list はそのまま素通し
    → ネスト構造で PII が含まれる場合スクラブ漏れ.
  - `_scrub_list_item` ヘルパー追加 (循環参照対策の MAX_SCRUB_DEPTH guard 含む).

- **Changed**: `utils/sentry_init.py` の `_is_sensitive_key` から
  `@lru_cache(maxsize=512)` を削除.
  - **変更理由 (KISS)**: SENSITIVE_KEYS は 39 要素で、正規化済み集合は
    module load 時に一度だけ構築される. 現状の呼び出し規模では cache の
    memory cost と invalidation complexity を正当化できない.

- **Fixed**: `utils/github_client.py` および `utils/api_client.py` の
  `__aexit__` で `aclose()` 例外を `try/except Exception` で wrap.
  - **変更理由**: CPython 仕様上、`__aexit__` 内で raise すると body 例外
    (`exc_val`) を visible exception が close 例外で上書き (`__context__` には
    body 例外が入るが視認しづらい).
  - close 失敗時は warning log (`*_aclose_failed`, error_type のみ記録) を
    出力し、re-raise しない. 両ファイル一貫適用.

- **Changed**: `tests/unit/test_sentry_init.py` の Sentry init exception 経路
  test で、DSN 非漏洩 assertion を強化.
  - positional / kwargs 両方の引数で DSN / exception value が漏洩しないことを
    assertion.
  - `error_module` キーが必須として記録されていることを assertion.

- **Added**: `utils/sentry_init.py` に URL スクラブ機能を追加.
  - `_scrub_url`: userinfo 除去 + fragment 除去 + クエリパラメータの
    機密キーを `[REDACTED]` 置換.
  - IPv6 hostname (`[::1]:8080`) のブラケット保持に対応.
  - 不正ポート番号 (非整数) は `ValueError` を局所化して継続処理.

- **Added (defense-in-depth)**: `utils/sentry_init.py` に `_has_internal_tag`
  ヘルパーを追加し、`_before_send` の recursion guard を dict / list[tuple] 両形式
  対応へ拡張.
  - **変更理由**: Sentry SDK 現行版 (sentry-sdk >= 2.x) では `scope.set_tag`
    経由の event["tags"] は常に dict 形式 (`Scope._apply_tags_to_event`
    `event.setdefault("tags", {}).update(self._tags)` 参照) のため現状 functional bug
    は無いが、`_before_send` 自体は SDK 仕様に従い list[tuple[str, str]] 形式も
    受け入れる契約 (`test_before_send_list_tags_redacts_sensitive_key`) のため、
    将来 SDK 仕様変更 / 別経路 emit への防御対称性を確保.
  - **新規テスト**: `test_before_send_skips_scrub_for_list_form_internal_tagged_event`
    で list-form 内部 tag 検出を回帰防止. Red-green TDD で test の effectiveness
    実証済 (revert 時 1 failed, restore 時 127 passed).

---

## Reference

- Format spec: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- Versioning: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html)
