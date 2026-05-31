# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Changed

- **Fixed (fail-fast)**: `utils/api_client.py` の
  `AsyncAPIClient._close_async_client` (`aclose()` / `__aexit__` 共有 close 処理)
  および `utils/github_client.py` の `AsyncGitHubClient.__aexit__` close 処理
  で `MemoryError` / `RecursionError` が `except Exception` に捕捉され
  サイレント隠蔽される問題を修正。
  - **背景**: 旧コメントにおいて「`MemoryError` は `except Exception` の境界外」と
    記述していた。しかし、`MemoryError` が `Exception` 直系・`RecursionError` が
    `RuntimeError` 派生のため、実際に `except Exception` が捕捉していた。特に
    `suppress_unexpected=True` 経路 (`aclose()` 直接呼出) では warning ログのみ
    記録して握りつぶし、回復不能エラーが上位に伝播しなかった。
  - **変更内容**: `except Exception` の前に `except RecursionError: raise` /
    `except MemoryError: raise` を追加し fail-fast 化。コメントを実装へ整合。
    `utils/github_client.py` (`_update_etag_cache`) / `utils/sentry_init.py`
    (`_safe_log_warning`) の broad-except cleanup と同一方針で、close/cleanup
    例外ハンドリングを統一。`ASYNC_FATAL_EXCEPTIONS` は `RecursionError` を
    含まずかつ retry/health 文脈専用のため本 site では不採用 (broad-except
    境界の Exception 派生 fatal のみを明示再 raise)。
  - **影響**: ログ schema 不変。メモリ枯渇 / スタック枯渇が `aclose()` /
    `__aexit__` から正しく伝播するようになる (上位で観測可能化)。`RuntimeError`
    等の通常例外の suppress 挙動は不変。
  - **テスト**: `tests/unit/test_async_client.py` および
    `tests/unit/test_github_client.py` に `MemoryError` / `RecursionError`
    伝播の回帰防止テストを追加。github_client は `__aexit__` body 例外併発下での
    fatal 伝播を Red-Green で実証。

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

- **Dependency upgrade**: `sentry-sdk[httpx]` の最小バージョンを
  `>=2.58.0` → `>=2.60.0,<3.0.0` に引き上げ (PR#347 review D-2).
  - **変更理由**: `utils/sentry_init.py:_emit_scrub_failure_to_sentry`
    で使用する `sentry_sdk.new_scope()` API は sentry-sdk 2.x で
    `push_scope()` から正式置換された推奨 API。`new_scope()` は
    context manager として scope の lifetime を明示し、recursion guard
    用 internal tag (`_INTERNAL_TAG_KEY`) の正確な scrub バイパス
    通知を実現する。
  - **影響範囲**: `pyproject.toml:33` (依存定義) と
    `PROJECT_INDEX.md:175` (技術スタック一覧) は更新済。
    アプリ側 API surface 変更なし (内部実装の更新のみ)。
  - **利用者対応**: `uv sync` または `uv lock --upgrade` で
    新しい lockfile を生成すること。

- **Observability contract expansion**: `AsyncAPIClient.aclose()`
  単独呼出経路でも `async_api_client_closed` ログを出力するよう変更
  (PR#347 review Q-1).
  - **変更内容**: 旧仕様では `async with` パターン経由の `__aexit__` else 節
    完了時のみログ出力。新仕様では `aclose()` 内 `_client.aclose()` 直後で
    ログ出力 → `async with` / 明示的 `await client.aclose()` の両経路で
    `async_api_client_closed` イベントが発火する。
  - **設計意図**: `SyncAPIClient.close()` (utils/api_client.py:395) と
    observability 対称性を確保。K8s graceful shutdown / debug 用途で
    `aclose()` を直接呼ぶケース (CLI / バックグラウンドタスク等) の
    可観測性向上。
  - **影響範囲**: log consumer (Datadog / Loki / Splunk / CloudWatch 等)
    で同イベント受信頻度が変化する可能性。`async with` のみ使用していた
    既存環境では event 数に変化なし。`aclose()` 直接呼出箇所では新規発火。
  - **互換性**: ログ schema (event 名 `async_api_client_closed`、フィールド
    なし) は不変。既存 alert rule / dashboard への破壊的影響なし。

- **BREAKING (log event name)**: `utils/github_client.py` の `AsyncGitHubClient`
  正常クローズ時のログイベント名を自然言語形式 `"AsyncGitHubClient closed"` から
  structlog 規約 (snake_case) 準拠の `"async_github_client_closed"` に変更
  (PR#347 review #4-[2]).
  - **変更理由**: `utils/api_client.py` の `async_api_client_closed` と命名整合を
    取り、プロジェクト全体の structlog イベント命名規約を統一する。
  - **対象**: `AsyncGitHubClient.__aexit__` の正常 close ログ (utils/github_client.py:308)。
  - **影響範囲**: log consumer (Datadog / Loki / Splunk / CloudWatch 等) で
    旧イベント名 `"AsyncGitHubClient closed"` を grep / filter 設定している場合
    マッチしなくなる。既存 alert rule / dashboard / log query を
    `"async_github_client_closed"` に更新すること。
  - **追従対応**: `tests/unit/test_github_client.py` の対応 assertion (4箇所)
    を新イベント名に更新済み。

- **Hardened**: `utils/sentry_init.py` の `_safe_log_warning()` ヘルパーを
  完全サイレント (`except Exception: pass`) から段階的 fail-open に強化
  (PR#347 review #1)。
  - **変更内容**:
    - `RecursionError` / `MemoryError` は再raise (fail-fast、上位で観測可能化)
    - 通常 `Exception` は stderr に `event` 名 + `error_type` + `error_module`
      を fallback 通知してから黙過 (fail-open + 最小限の障害可視化)
    - stderr 自体が壊れた場合のみ完全黙過（真の最終手段）
  - **背景**: 旧実装はロガー側の `RecursionError` (構造化ログでよく発生する) を
    完全に隠蔽し、Sentry PII scrub フロー内で起きた重大障害が無音化していた。
  - **影響**: ログ schema 不変、Sentry イベント送信フロー (`before_send`) の
    動作不変。stderr へ新規 1 行が稀に出力される可能性あり (障害発生時のみ)。

- **Documented**: `utils/github_client.py` の `_request` 防御的パス
  (L958+ `if http_status_response is not None`) における 5xx/404/429/403 分岐の
  unreachable 性を明示するコメント追加 (PR#347 review #4-[10])。
  - **背景**: `raise_for_status()` が HTTPStatusError を raise する条件下では、
    5xx/404/429/403 は既に main path (L843/L847/L859/L871) で先行処理済み。
    防御パスが起動するのは 401/400/405 等の other 4xx (`else` 分岐) のみ。
  - **コード削除を見送った理由**: テスト (`test_github_client.py` L884/L1597/L2180)
    が `httpx.HTTPStatusError` 直接 mock 注入で防御パス到達を検証中。
    削除すると mock-based regression test が破壊されるため、安全網として残置。
  - **影響**: コードロジック不変、コメントのみ追加。

- **Observability field addition**: `__aexit__` の `aclose()` 例外パスで
  `body_exception_type` フィールドを追加 (PR#347 review SF-2).
  - **対象**: `AsyncAPIClient.__aexit__` および `AsyncGitHubClient.__aexit__` の
    `*_aclose_unexpected_error` ログ。
  - **変更内容**: `body_exception_type=exc_type.__qualname__ if exc_type is not None else None`
    を追加。`close_exc` が body 例外 `__context__` を上書きしないため切断される
    例外チェーンを log 内で補完。
  - **PII 保護**: `__qualname__` はクラス名 (`ValueError`, `RuntimeError` 等)
    のみで PII を含まない。
  - **互換性**: 既存フィールド (`error_type`, `error_module`, `has_body_exception`,
    `exc_info`) は不変。log consumer 側で新規 nullable string field として
    追加扱いされる。

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
  - **追加された redact key (32 → 43（+11件）)**
    （※ 32 は PR#340 で email/ip_address/body_preview 追加後の件数。
    　PR#340 前起点では 29 → 43（+14件））:
    - 認証系: `access_key`
    - HTTP headers: `proxy-authorization`, `set-cookie`, `x-auth-token`,
      `csrf_token`, `x-csrf-token`, `x-refresh-token`, `x-access-token`
    - 複合語バリアント: `authtoken`, `usertoken`, `userpassword`
  - **追加されたスクラブ対象フィールド (4 → 6)**: `breadcrumbs` および `exception` を
    `_SCRUBBED_EVENT_FIELDS` に追加.
    - `breadcrumbs`: ブレッドクラム内の機密キーを redact.
    - `exception`: スタックフレームの local vars (`frames[*].vars`) 経由の PII 漏洩防止.
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
    失敗の事実は二経路で観測可能 (両者は fail-closed パスで同時発火):
    (a) Sentry: `sentry_scrub_failed` message event (error レベル,
    `capture_message` 経由). Sentry SDK 未ロード時は stderr にフォールバック.
    (b) structlog: `sentry_before_send_drop_event` error log（ロガー障害時のみ warning フォールバック）
    (`error_type` / `error_module` を構造化フィールドとして記録).
    成功時の挙動は不変 (`event["request"]` の dict identity は変わる).
    Sentry SDK は event 全体を serialize して送信するため、本実装変更が観測可能な
    挙動差を生む経路は確認していない (Sentry SDK source 未検証 — 推察). 万一
    identity 依存経路が判明した場合は git history / commit log を参照。
  - **運用上の留意 (operational concern)**:
    本 BREAKING change により、production の real error が scrub edge case で
    drop され operator が原 error を観測できないリスクが残る.
    導入後の監視推奨 (二経路を併用):
    1. Sentry 側: `sentry_scrub_failed` message event (error レベル) の発生率を
       Sentry で metric 化. SDK 未ロード時の stderr fallback はコンテナログで確認.
    2. log aggregator 側 (Datadog / Loki / CloudWatch 等):
       `sentry_before_send_drop_event` error log（ロガー障害時のみ warning フォールバック）の `error_type` /
       `error_module` 分布を集計し、特定例外型の偏在で defect 兆候を早期検知.
    3. 異常な発生率上昇時は SENSITIVE_KEYS / scrub logic の defect 兆候として
       triage. payload 構造を sanitized form でローカル再現し原因特定.


- **Added (security)**: `utils/github_client.py` に `_SanitizedJSONDecodeError`
  カスタム例外クラスを追加.
  - **目的**: `json.JSONDecodeError` のエラーメッセージに含まれる可能性のある
    レスポンスボディ断片（PII を含む場合あり）を Sentry / ログに送信しないよう
    エラーメッセージをサニタイズする。
  - **実装**: `Exception` を継承し、`error_type`, `pos`, `lineno` のみ保持
    （レスポンス本文は破棄 — PII非露出）。
  - **影響範囲**: `github_client.py` 内で JSON パースに失敗した場合、
    この例外が raise されるようになる。メッセージ形式が変わるため、
    メッセージ内容に依存する catch ロジックは更新が必要。

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

- **Changed**: `utils/sentry_init.py` の `_is_sensitive_key` に
  `@lru_cache(maxsize=512)` を維持.
  - **維持理由**: SENSITIVE_KEYS は 43 要素だが、キーの正規化処理 (``sub()`` による
    camelCase / acronym 分割) の計算コストを低減するため cache を適用.
    コード内コメント (L210-211) と設計判断を一致させる修正.

- **Fixed**: `utils/github_client.py` および `utils/api_client.py` の
  `__aexit__` で `aclose()` 例外を `try/except Exception` で wrap.
  - **変更理由**: CPython 仕様上、`__aexit__` 内で raise すると body 例外
    (`exc_val`) を visible exception が close 例外で上書き (`__context__` には
    body 例外が入るが視認しづらい).
  - 既知の close 失敗 (`httpx.CloseError`, `OSError`): warning log
    (`*_aclose_failed`, error_type のみ記録) を出力し、re-raise しない.
  - 予期しない close 失敗 (その他の `Exception`): error log
    (`*_aclose_unexpected_error`, `has_body_exception`, `exc_info=True`) を記録し、
    body 例外がない場合のみ実装バグとして re-raise する (body 例外がある場合は
    本質的原因の上書きを防ぐため re-raise しない).
  - 上記の close 例外ハンドリングは両ファイル (`github_client.py` /
    `api_client.py`) で一貫適用.

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

- **Fixed**: `utils/github_client.py` の ETagキャッシュキーをエンドポイント単体から
  クエリパラメータ込みに変更（`_cache_key()` スタティックメソッド追加）。
  同一エンドポイント・異なるクエリパラメータ（sort/per_page等）のキャッシュが
  正しく分離されるようになった（`urlencode(sorted_params, quote_via=quote)`）。

---

## Reference

- Format spec: [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- Versioning: [SemVer 2.0.0](https://semver.org/spec/v2.0.0.html)
