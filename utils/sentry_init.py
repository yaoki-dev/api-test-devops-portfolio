"""Sentry SDK初期化モジュール

エラー監視サービスSentryとの統合を提供。
structlogと連携し、ERROR以上のログをSentryに送信。

依存関係:
    - config/settings.py: SentryConfig（DSN、有効化フラグ等）
    - sentry-sdk >= 2.0.0: before_send APIを使用

初期化タイミング:
    アプリケーション起動時、ログ設定後に一度だけ呼び出し。
    structlogのconfigure()後、最初のログ出力前が推奨。

使用例:
    from utils.sentry_init import init_sentry

    # アプリケーション起動時
    if init_sentry():
        logger.info("Sentry monitoring enabled")

デバッグ:
    環境変数 SENTRY_DEBUG=true で初期化失敗の警告を有効化。

セキュリティ:
    - before_sendフックで機密データを自動除外（39種類のキーパターン）
    - DSNはSecretStrで管理（config/settings.py）
    - enabled=Falseで完全無効化可能
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from config.settings import get_settings
from utils.logger import get_logger

# 再帰防止用の内部識別子。scrub 失敗を Sentry に通知する際にこの tag を付与し、
# _before_send 冒頭で検出して scrub をスキップ通過させることで無限ループ
# (capture_message → _before_send → 例外 → capture_message ...) を遮断する。
_INTERNAL_TAG_KEY: str = "sentry_internal_event"
_INTERNAL_TAG_VALUE: str = "scrub_failure"


def _has_internal_tag(tags: Any) -> bool:
    """内部識別 tag の有無を dict / list[tuple] 両形式で検出する。

    Sentry SDK の現行版 (sentry-sdk >= 2.x) では ``scope.set_tag`` 経由で event に
    到達する ``tags`` は常に dict 形式 (``Scope._apply_tags_to_event`` 参照)。
    ただし ``_before_send`` 自体は SDK 仕様に従い list[tuple[str, str]] 形式も
    受け入れる契約 (``test_before_send_list_tags_redacts_sensitive_key``) のため、
    防御の対称性として recursion guard も両形式に対応する (defense-in-depth)。

    判定仕様:
        - dict 形式: ``tags[_INTERNAL_TAG_KEY] == _INTERNAL_TAG_VALUE`` で判定。
        - list 形式: ``(_INTERNAL_TAG_KEY, _INTERNAL_TAG_VALUE)`` タプルの完全一致
          で判定 (key のみ一致 / value が異なるペアは通常 event として扱い、
          recursion guard は発火しない)。
        - 上記以外 (None, str, int 等): 常に False。

    Args:
        tags: event["tags"] 相当の値 (dict / list / その他)。

    Returns:
        内部識別 tag が検出された場合 True。
    """
    if isinstance(tags, dict):
        return tags.get(_INTERNAL_TAG_KEY) == _INTERNAL_TAG_VALUE
    if isinstance(tags, list):
        return (_INTERNAL_TAG_KEY, _INTERNAL_TAG_VALUE) in tags
    return False


# デバッグモード（環境変数で有効化）
SENTRY_DEBUG: bool = os.environ.get("SENTRY_DEBUG", "").lower() in ("true", "1", "yes")

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint

# 機密データキーのパターン（Security Auditor推奨を反映）
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        # 認証系（基本）
        "password",
        "token",
        "secret",
        "api_key",
        "dsn",
        "authorization",
        "cookie",
        "session",
        "credential",
        # 認証系（拡張）
        "bearer",
        "jwt",
        "access_token",
        "refresh_token",
        "private_key",
        "client_secret",
        "x-api-key",
        "auth_token",
        "passwd",
        # 暗号化
        "encryption_key",
        "cipher_key",
        # OAuth
        "oauth_token",
        # 二要素認証
        "otp",
        "mfa",
        "totp",
        # 個人情報
        "email",  # GDPR/個人情報保護法: メールアドレスは個人識別情報
        "ip_address",  # Sentry user.ip_address は個人識別情報として扱う
        "database_url",
        "ssn",
        "credit_card",
        "cvv",
        "card_number",
        # HTTPレスポンスプレビュー: _before_send は capture_exception / capture_message の
        # 両方で適用され、body_preview は extra 経由のペイロードをスクラブする。
        "body_preview",
        "access_key",
        "proxy-authorization",
        "set-cookie",
        "x-auth-token",
        "x-csrf-token",
        "x-refresh-token",
        "x-access-token",
    },
)

# 遅延初期化フラグ
_sentry_initialized: bool = False


# 再帰制限のデフォルト値
MAX_SCRUB_DEPTH: int = 10

# before_send でスクラブ対象とするイベントフィールド（PII漏洩防止の対象集合）
_SCRUBBED_EVENT_FIELDS: frozenset[str] = frozenset(
    {"extra", "user", "contexts", "tags", "breadcrumbs"}
)

# defense-in-depth: ハイフン/アンダースコア表記揺れを吸収するため、
# SENSITIVE_KEYS と検査対象キー双方をハイフン→アンダースコアへ正規化してから
# substring 一致で判定する。これにより以下を同一視できる:
#   - X-Auth-Token / x-auth-token / x_auth_token
#   - Set-Cookie / set_cookie
# また composite key (例: user_password, email_address, session_id, auth_token_v2,
# customer_jwt) も substring 一致で redact される。
_NORMALIZED_SENSITIVE_KEYS: frozenset[str] = frozenset(
    sensitive.replace("-", "_") for sensitive in SENSITIVE_KEYS
)


def _is_sensitive_key(key: str) -> bool:
    """機密キーかどうかを判定する（substring 一致 + ハイフン/アンダースコア正規化）。

    判定アルゴリズム:
        1. key を lower-case 化
        2. ハイフン (``-``) をアンダースコア (``_``) へ正規化
        3. ``_NORMALIZED_SENSITIVE_KEYS`` の各要素を substring として検索

    これにより `user_password`, `email_address`, `X-Auth-Token` 等の
    composite key / HTTP header variant も redact される (defense-in-depth)。

    Args:
        key: 判定対象のキー文字列。

    Returns:
        機密キーと判定された場合 True。

    """
    key_norm = key.lower().replace("-", "_")
    return any(sensitive in key_norm for sensitive in _NORMALIZED_SENSITIVE_KEYS)


def _scrub_list_item(item: Any, _depth: int) -> Any:
    """list要素を深さ上限を守ってスクラブする。"""
    if _depth >= MAX_SCRUB_DEPTH:
        return "[MAX_DEPTH_EXCEEDED]"
    if isinstance(item, dict):
        return _scrub_sensitive_data(item, _depth)
    if isinstance(item, list):
        return [_scrub_list_item(child, _depth + 1) for child in item]
    return item


def _scrub_sensitive_data(data: Any, _depth: int = 0) -> Any:
    """機密データを再帰的にスクラブ

    Args:
        data: スクラブ対象のデータ
        _depth: 現在の再帰深度（内部使用）

    Returns:
        スクラブ済みデータ（元データは変更しない）

    Note:
        MAX_SCRUB_DEPTH（デフォルト10）を超えると再帰を停止し、
        循環参照による無限ループを防止する。

    """
    if not isinstance(data, dict):
        return data

    # 再帰制限チェック（循環参照対策）
    if _depth >= MAX_SCRUB_DEPTH:
        return "[MAX_DEPTH_EXCEEDED]"

    result: dict[str, Any] = {}
    for key, value in data.items():
        if _is_sensitive_key(key):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _scrub_sensitive_data(value, _depth + 1)
        elif isinstance(value, list):
            result[key] = [_scrub_list_item(item, _depth + 1) for item in value]
        else:
            result[key] = value
    return result


def _scrub_query_string(query_string: str) -> str:
    """重複キーを保持したままクエリ文字列をスクラブする。"""
    pairs = parse_qsl(query_string, keep_blank_values=True)
    scrubbed_pairs = [
        (key, "[REDACTED]" if _is_sensitive_key(key) else value) for key, value in pairs
    ]
    return urlencode(scrubbed_pairs)


def _scrub_url(url: str) -> str:
    """URLのuserinfo/fragmentを除去し、queryをスクラブする。"""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        netloc = ""
    else:
        netloc = f"[{hostname}]" if ":" in hostname and not hostname.startswith("[") else hostname
        try:
            port = parsed.port
        except ValueError:
            port = None
        if port is not None:
            netloc = f"{netloc}:{port}"
    return urlunparse(
        parsed._replace(
            netloc=netloc,
            query=_scrub_query_string(parsed.query) if parsed.query else "",
            fragment="",
        )
    )


def _scrub_tag_pair(item: Any) -> Any:
    """tags の (key, value) ペアをスクラブする（list 形式 tags 用）。"""
    if isinstance(item, (tuple, list)) and len(item) == 2:
        key = item[0]
        if isinstance(key, str) and _is_sensitive_key(key):
            return (key, "[REDACTED]")
    return item


def _scrub_sentry_field(event_dict: dict[str, Any], field: str) -> None:
    """Sentryイベントの単一フィールドをスクラブする（_before_send 専用）。

    dict型の場合は _scrub_sensitive_data() で再帰的にスクラブする。
    list型の場合は (key, value) ペア形式と見なして各ペアをスクラブし、非PII の
    デバッグ情報（リクエストID等）は保持する（Sentry SDK 仕様: tags は
    ``list[tuple[str, str]]`` 形式も許容）。
    上記以外の型の場合は空dictに置換し（安全サイド）、SENTRY_DEBUG の値に関わらず
    logger.warning を常時出力する（本番監視対応）。
    _scrub_sensitive_data の内部 non-dict ガードと二重防御を構成する。

    Args:
        event_dict: Sentryイベント辞書（破壊的更新）
        field: スクラブ対象フィールド名

    """
    if field in event_dict:
        value = event_dict[field]
        if isinstance(value, dict):
            event_dict[field] = _scrub_sensitive_data(value)
        elif isinstance(value, list):
            event_dict[field] = [_scrub_tag_pair(item) for item in value]
        else:
            # dict/list以外はスクラブ不可能。空dictに置換して安全サイドに倒す。
            event_dict[field] = {}
            _logger.warning(
                "sentry_field_type_unexpected",
                field=field,
                actual_type=type(value).__name__,
                action="replaced_with_empty_dict",
            )


def _emit_scrub_failure_to_sentry(exc: BaseException) -> None:
    """scrub 失敗を内部識別 tag 付きで Sentry へ通知する（fail-safe）。

    sentry_sdk.capture_message は再度 _before_send を通るが、付与した
    _INTERNAL_TAG_KEY=_INTERNAL_TAG_VALUE を冒頭で検出して scrub をスキップ
    通過させるため無限再帰しない。内部 SDK 呼び出し自体が例外を投げた場合は
    最終フォールバックとして stderr へ出力し、メインプロセスをクラッシュさせない。
    """
    try:
        sentry_sdk = sys.modules.get("sentry_sdk")
        if sentry_sdk is None:
            # SDK 未ロード（テスト・未インストール環境）: stderr フォールバック
            print(
                f"[SENTRY_SCRUB_FAILED] sentry_sdk_not_loaded "
                f"error_type={type(exc).__qualname__} "
                f"error_module={type(exc).__module__}",
                file=sys.stderr,
            )
            return
        with sentry_sdk.new_scope() as scope:
            scope.set_tag(_INTERNAL_TAG_KEY, _INTERNAL_TAG_VALUE)
            scope.set_level("error")
            scope.set_extra("error_type", type(exc).__qualname__)
            scope.set_extra("error_module", type(exc).__module__)
            scope.set_extra("action", "event_dropped")
            sentry_sdk.capture_message("sentry_scrub_failed", level="error")
    except Exception as inner_exc:  # noqa: BLE001
        # Sentry 通知自体が失敗 → stderr へ最終フォールバック
        print(
            f"[SENTRY_SCRUB_FAILED] inner_error_type={type(inner_exc).__qualname__} "
            f"inner_error_module={type(inner_exc).__module__} "
            f"original_error_type={type(exc).__qualname__} "
            f"original_error_module={type(exc).__module__}",
            file=sys.stderr,
        )


def _before_send(event: Event, hint: Hint) -> Event | None:  # noqa: ARG001
    """Sentry送信前フック（機密データ除外）

    再帰防止: scrub 失敗時に発火する内部通知イベント（_INTERNAL_TAG_KEY
    が付与されている）は冒頭で検出し、scrub をスキップして通過させる。
    これにより capture_message → _before_send → 例外 → capture_message
    の無限ループを遮断する（_emit_scrub_failure_to_sentry 参照）。

    Args:
        event: Sentryイベント
        hint: 追加コンテキスト（未使用）

    Returns:
        処理済みイベント、またはNone（送信キャンセル）

    """
    # 再帰防止ガード: 内部通知イベントは scrub をスキップして通過させる
    # dict / list[tuple] 両形式に対応 (defense-in-depth, _has_internal_tag 参照)
    if _has_internal_tag(event.get("tags")):
        return event

    try:
        # リクエストデータのスクラブ。成功時だけ event["request"] を差し替える。
        # _scrub_sensitive_data / _scrub_query_string / _scrub_url は全て non-destructive で
        # 新しいオブジェクトを返すため、top-level dict の shallow copy で十分。
        # 元 request の non-mutation 契約は既存テスト
        # ``test_before_send_fail_closed_without_partial_request_mutation`` で継続検証。
        if "request" in event:
            request = event["request"]
            if isinstance(request, dict):
                scrubbed_request = dict(request)
                if "headers" in scrubbed_request:
                    scrubbed_request["headers"] = _scrub_sensitive_data(scrubbed_request["headers"])
                if "data" in scrubbed_request:
                    scrubbed_request["data"] = _scrub_sensitive_data(scrubbed_request["data"])
                if "query_string" in scrubbed_request and isinstance(
                    scrubbed_request["query_string"], str
                ):
                    scrubbed_request["query_string"] = _scrub_query_string(
                        scrubbed_request["query_string"]
                    )
                if "url" in scrubbed_request and isinstance(scrubbed_request["url"], str):
                    scrubbed_request["url"] = _scrub_url(scrubbed_request["url"])
                event["request"] = scrubbed_request

        # 追加データのスクラブ（2層防御）
        # _scrub_sentry_field: 非dict型フィールドを空dictに置換（型安全化・PII漏洩防止）
        # _scrub_sensitive_data: dict内の機密キーを [REDACTED] に置換（PII除外）
        event_dict = cast(dict[str, Any], event)
        for field in _SCRUBBED_EVENT_FIELDS:
            _scrub_sentry_field(event_dict, field)
    except Exception as exc:
        # 元イベントは PII 漏洩防止のため確実にドロップする (return None)
        # その上で scrub 失敗を Sentry に通知する。内部通知失敗時は stderr へ
        # フォールバックし、メインプロセスはクラッシュさせない。
        _emit_scrub_failure_to_sentry(exc)
        return None

    return event


def init_sentry() -> bool:
    """Sentry SDK初期化

    config/settings.pyのSentryConfigに基づいて初期化。
    enabled=Falseまたは空DSNの場合はスキップ。

    Returns:
        True: 初期化成功
        False: スキップまたは失敗

    Example:
        if init_sentry():
            logger.info("Sentry monitoring enabled")

    """
    global _sentry_initialized  # noqa: PLW0603

    # 二重初期化防止
    if _sentry_initialized:
        return True

    settings = get_settings()
    sentry_config = settings.sentry

    # 無効化チェック
    if not sentry_config.enabled:
        return False

    # DSN取得・検証
    dsn = sentry_config.dsn.get_secret_value()
    if not dsn:
        return False

    # 環境名（フォールバック）
    # Note: DSN検証はsentry_sdk.init()に委任（SDK内部でバリデーション実施）
    environment = sentry_config.environment or settings.environment.value

    # is_production_like() を関数先頭で一度だけ評価しローカル変数に保持。
    # except 内で get_settings() を再呼び出しすると、環境変数変化や reload_settings()
    # の race により ValidationError が発生し、元の例外（ImportError / 初期化失敗）を
    # マスクしてデバッグを困難化するリスクがあるため (CWE-755 例外マスク防止)。
    is_production_like = settings.is_production_like()

    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=sentry_config.traces_sample_rate,
            profiles_sample_rate=sentry_config.profiles_sample_rate,
            send_default_pii=sentry_config.send_default_pii,
            before_send=_before_send,
        )

        _sentry_initialized = True
        return True

    except ImportError as exc:
        # sentry-sdk未インストール
        # 本番環境では必須 → Fail-Fast（依存関係漏れを即座に検出）
        if is_production_like:
            raise RuntimeError(
                f"Sentry SDK not installed in production: {exc}. Add 'sentry-sdk' to dependencies.",
            ) from exc

        # 開発/テスト環境では許容（警告のみ）
        if SENTRY_DEBUG:
            warnings.warn(
                f"Sentry SDK not installed: {exc}",
                UserWarning,
                stacklevel=2,
            )
        return False

    except Exception as exc:
        # その他の初期化失敗 - 本番環境では例外を発生させる（Fail-Fast）
        if is_production_like:
            raise RuntimeError(
                f"Sentry initialization failed in production: {type(exc).__name__}: {exc}",
            ) from exc

        # 開発/テスト環境では警告のみ
        if SENTRY_DEBUG:
            warnings.warn(
                f"Sentry initialization failed: {type(exc).__name__}: {exc}",
                UserWarning,
                stacklevel=2,
            )
        return False


def is_sentry_initialized() -> bool:
    """Sentry初期化状態の確認

    Returns:
        True: 初期化済み
        False: 未初期化

    """
    return _sentry_initialized


def reset_sentry_state() -> None:
    """Sentry状態リセット（テスト用）

    Warning:
        本番コードでは使用しないでください。

    """
    global _sentry_initialized  # noqa: PLW0603
    _sentry_initialized = False
