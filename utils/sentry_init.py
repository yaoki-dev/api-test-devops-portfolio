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
    初期化失敗時は SENTRY_DEBUG の値に関わらず warning ログを常時出力する。
    （SENTRY_DEBUG は将来の拡張用に定義済みだが、現行 init_sentry() では参照しない）

セキュリティ:
    - before_sendフックで機密データを自動除外（39種類のキーパターン）
    - DSNはSecretStrで管理（config/settings.py）
    - enabled=Falseで完全無効化可能
"""

from __future__ import annotations

import os
import re
import secrets
import sys
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from config.settings import get_settings
from utils.logger import get_logger

# 再帰防止用の内部識別子。scrub 失敗を Sentry に通知する際にこの tag を付与し、
# _before_send 冒頭で検出して scrub をスキップ通過させることで無限ループ
# (capture_message → _before_send → 例外 → capture_message ...) を遮断する。
# value はプロセス起動ごとにランダム生成し、OSS で公開された固定値を悪用した
# scrub バイパス (任意 event tag への注入で _before_send を素通りさせる攻撃) を
# 防ぐ (PR#347 review)。_has_internal_tag / _emit_scrub_failure_to_sentry は
# 同一モジュール global を参照するため一貫して機能する。
_INTERNAL_TAG_KEY: str = "sentry_internal_event"
_INTERNAL_TAG_VALUE: str = secrets.token_hex(16)


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
    {
        "extra",
        "user",
        "contexts",
        "tags",
        "breadcrumbs",
        "exception",  # スタックフレームのlocal vars (frames[*].vars) のスクラブ対象 (PR#347)
        # 注: キー名が _is_sensitive_key で True の場合のみ scrub。非機密キー名の機密値は対象外
    }
)

# defense-in-depth: ハイフン/アンダースコア表記揺れを吸収するため、
# SENSITIVE_KEYS と検査対象キー双方をハイフン→アンダースコアへ正規化してから
# 単語境界（先頭/末尾/アンダースコア）で判定する。これにより以下を同一視できる:
#   - X-Auth-Token / x-auth-token / x_auth_token
#   - Set-Cookie / set_cookie
# また composite key (例: user_password, email_address, session_id, auth_token_v2,
# customer_jwt) も単語単位で redact される一方、photo_url / prototype 等の
# unrelated substring は過剰 redact しない。
_NORMALIZED_SENSITIVE_KEYS: frozenset[str] = frozenset(
    sensitive.replace("-", "_") for sensitive in SENSITIVE_KEYS
)
_SENSITIVE_KEY_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|[_\d])(?:"
    + "|".join(re.escape(sensitive) for sensitive in sorted(_NORMALIZED_SENSITIVE_KEYS))
    + r")(?:[_\d]|$)"  # 数字境界 (v2token, password2, api_key2 等) も扱う
)
# 全大文字命名 fallback 用: アンダースコア除去後の完全一致集合 (PR#347)
# APIKEY / ACCESSTOKEN 等は ACRONYM 分割が効かないため別途事前計算
_COMPACT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    sensitive.replace("_", "") for sensitive in _NORMALIZED_SENSITIVE_KEYS
)

# camelCase / ACRONYM 分割用の事前コンパイル済みパターン (PR#347 review)。
# 生リテラル re.sub の re._cache 依存を排し、設計を統一するため、
# すべての正規表現をモジュールレベルで事前コンパイルしています。
# (注: Pythonレイヤーでのハッシュルックアップ・オーバーヘッドを避けるため、
#  関数自体への @lru_cache 適用はあえて行わず、Cレイヤーの正規表現マッチのみで高速処理します)
_ACRONYM_PATTERN: re.Pattern[str] = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_PATTERN: re.Pattern[str] = re.compile(r"(?<=[a-z])(?=[A-Z])")


def _is_sensitive_key(key: str) -> bool:
    """機密キーかどうかを判定する（単語境界一致 + ハイフン/アンダースコア正規化）。

    判定アルゴリズム:
        1. ACRONYMWord → ACRONYM_Word 変換（`APIKey` → `API_Key`）
        2. camelCase → snake_case 変換（`accessToken` → `access_Token`）
        3. key を lower-case 化
        4. ハイフン (``-``) をアンダースコア (``_``) へ正規化
        5. ``_NORMALIZED_SENSITIVE_KEYS`` の各要素を単語境界で検索
        6. 全大文字命名 fallback: アンダースコア除去後の完全一致
           （`APIKEY` → `apikey` == `api_key` compact → True）

    これにより `user_password`, `email_address`, `X-Auth-Token` 等の
    composite key / HTTP header variant を redact しつつ、`photo_url`,
    `prototype`, `option` 等の unrelated substring は保持する。
    camelCase キー (`accessToken`, `apiKey`, `emailAddress`) も正規化後に
    snake_case として検出される。
    全大文字命名 (`APIKEY`, `ACCESSTOKEN`) は ACRONYM 分割が効かないため
    compact fallback（アンダースコア除去後の完全一致）で補完する。
    compact fallback は substring 一致ではなく完全一致のため、
    `PHOTOURL` (compact: photourl) が `url` にマッチして過剰 redact する問題は発生しない。

    Args:
        key: 判定対象のキー文字列。

    Returns:
        機密キーと判定された場合 True。

    """
    key_norm = _ACRONYM_PATTERN.sub(r"\1_\2", key)  # ACRONYMWord → ACRONYM_Word (PR#347)
    key_norm = _CAMEL_PATTERN.sub("_", key_norm)  # wordWord → word_Word
    key_norm = key_norm.lower().replace("-", "_")
    if _SENSITIVE_KEY_PATTERN.search(key_norm) is not None:
        return True
    # 全大文字命名 fallback (APIKEY, ACCESSTOKEN 等): ACRONYM 分割が効かない場合に
    # アンダースコア除去後の完全一致で補完 (PR#347)
    return key_norm.replace("_", "") in _COMPACT_SENSITIVE_KEYS


def _scrub_list_item(item: Any, _depth: int) -> Any:
    """list要素を深さ上限を守ってスクラブする（汎用 element scrubber）。

    tags 専用の (key, value) ペア判定は ``_scrub_sentry_field`` の field 単位
    dispatch に集約し、本関数では tuple のみを tag pair として扱う
    （Sentry SDK が tags を list[tuple[str, str]] で渡す場合の互換性のため）。
    list[2] with str[0] のような汎用 list を tag pair と誤判定して
    breadcrumb 等の非 PII 2要素 list を過剰 redact する問題を避ける。
    """
    if _depth >= MAX_SCRUB_DEPTH:
        _logger.warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
        return "[MAX_DEPTH_EXCEEDED]"
    if isinstance(item, tuple):
        if len(item) == 2:
            key = item[0]
            if isinstance(key, str) and _is_sensitive_key(key):
                return (key, "[REDACTED]")
        # len==2 非機密キー tuple を含む全 tuple の各要素を再帰スクラブし、
        # ネストされた dict/list 内の機密キーの漏洩を防ぐ。
        # 注: 素の str/数値要素はキーコンテキストを持たないため redact 対象外
        # （キーベース scrub の仕様限界）。
        return tuple(_scrub_list_item(elem, _depth + 1) for elem in item)
    if isinstance(item, dict):
        return _scrub_sensitive_data(item, _depth + 1)
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
        _logger.warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
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


def _scrub_request_query_string(query_string: str | bytes) -> str:
    """Sentry request.query_string の str/bytes 値を安全にスクラブする。"""
    if isinstance(query_string, bytes):
        query_string = query_string.decode("utf-8", errors="ignore")
    return _scrub_query_string(query_string)


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
    # tuple 6 要素を全フィールド明示で構築する
    # (vs `parsed._replace(...)`): ParseResult に新フィールドが追加された場合、
    # 暗黙保持で意図しないフィールドが残るリスクを排除する fail-safe 設計。
    # フィールド順は ParseResult 定義に従う: (scheme, netloc, path, params, query, fragment)
    return urlunparse(
        (
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            _scrub_query_string(parsed.query) if parsed.query else "",
            "",  # fragment を除去（PII 漏洩防止）
        )
    )


def _scrub_tags_item(item: Any, _depth: int = 0) -> Any:
    """tags フィールド要素を Sentry spec + defense-in-depth でスクラブする。

    Sentry SDK 仕様: tags は ``dict[str, str]`` または ``list[tuple[str, str]]``。
    JSON roundtrip で tuple が list 化されるため list[2] も tag pair として扱う。
    加えて非標準だが custom before_send hook 等で生じうる dict / nested list 形態でも
    機密キーを redact する（defense-in-depth）。
    _depth による再帰深さ保護を行い、MAX_SCRUB_DEPTH 超過時は安全サイドに倒す。
    """
    if _depth >= MAX_SCRUB_DEPTH:
        _logger.warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
        return "[MAX_DEPTH_EXCEEDED]"
    if isinstance(item, (tuple, list)) and len(item) == 2:
        key = item[0]
        if isinstance(key, str) and _is_sensitive_key(key):
            return (key, "[REDACTED]")
        # 非機密キー: value を _scrub_list_item で汎用スクラブする。
        # _scrub_tags_item 自身を再帰させると、value 内の2要素リスト
        # （例: ["email", "user@example.com"]）をタグペアと誤認し
        # "email" を機密キーとして過剰 redact するため、タグペア
        # コンテキストを持たない _scrub_list_item を使用する。
        return (key, _scrub_list_item(item[1], _depth + 1))
    if isinstance(item, dict):
        return _scrub_sensitive_data(item, _depth + 1)
    if isinstance(item, list):
        # nested list は汎用 scrub にフォールバック（深さを引き継ぐ）
        return [_scrub_list_item(child, _depth=_depth + 1) for child in item]
    if isinstance(item, tuple):
        # len != 2 の tuple も _scrub_list_item で汎用スクラブ（list との一貫性）
        return tuple(_scrub_list_item(child, _depth + 1) for child in item)
    return item


def _scrub_sentry_field(event_dict: dict[str, Any], field: str) -> None:
    """Sentryイベントの単一フィールドをスクラブする（_before_send 専用）。

    dict型の場合は _scrub_sensitive_data() で再帰的にスクラブする。
    list型の場合は (key, value) ペア形式の tags と dict/list 要素形式の
    breadcrumbs の両方をスクラブし、非PII のデバッグ情報（リクエストID等）は
    保持する（Sentry SDK 仕様: tags は ``list[tuple[str, str]]`` 形式も許容）。
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
            # field 単位 dispatch: tags は Sentry spec 上 list[tuple[str, str]]
            # （JSON経由で list[list[str, str]] にもなり得る）なので tag pair として処理。
            # 加えて非標準だが custom before_send hook 等で生じうる list[dict] / list[list]
            # 形態でも defense-in-depth で内部の機密キーを redact する
            # （PR #347 review reflexion iter2: tags-as-list-of-dicts 退行修正）。
            # 他フィールド（breadcrumbs/contexts/extra/user）は汎用要素として
            # 処理し、list[2] with str[0] の偶発的 tag-pair 誤判定で過剰 redact
            # しない（PR #347 review: KP-003 / T3 対応）。
            if field == "tags":
                event_dict[field] = [_scrub_tags_item(item) for item in value]
            else:
                event_dict[field] = [_scrub_list_item(item, _depth=0) for item in value]
        else:
            # dict/list以外はスクラブ不可能。空dictに置換して安全サイドに倒す。
            event_dict[field] = {}
            try:
                _logger.warning(
                    "sentry_field_type_unexpected",
                    field=field,
                    actual_type=type(value).__name__,
                    action="replaced_with_empty_dict",
                    event_id=event_dict.get("event_id"),
                )
            except Exception as logging_exc:  # noqa: BLE001
                # ログ失敗で Sentry イベント自体を drop しない。
                # 同モジュール内 stderr 出力スタイルを print(..., file=sys.stderr) に統一。
                print(
                    "[SENTRY_FIELD_WARNING_FAILED] "
                    f"field={field} logger_error_type={type(logging_exc).__name__}",
                    file=sys.stderr,
                    flush=True,
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
                flush=True,
            )
            return
        with sentry_sdk.new_scope() as scope:
            scope.set_tag(_INTERNAL_TAG_KEY, _INTERNAL_TAG_VALUE)
            scope.set_level("error")
            scope.set_extra("error_type", type(exc).__qualname__)
            scope.set_extra("error_module", type(exc).__module__)
            scope.set_extra("action", "event_dropped")
            scope.capture_message("sentry_scrub_failed", level="error")
    except Exception as inner_exc:  # noqa: BLE001
        # Sentry 通知自体が失敗 → stderr へ最終フォールバック
        print(
            f"[SENTRY_SCRUB_FAILED] inner_error_type={type(inner_exc).__qualname__} "
            f"inner_error_module={type(inner_exc).__module__} "
            f"original_error_type={type(exc).__qualname__} "
            f"original_error_module={type(exc).__module__}",
            file=sys.stderr,
            flush=True,
        )


def _before_send(event: Event, hint: Hint) -> Event | None:  # noqa: ARG001, C901
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

    scrub_exc: Exception | None = None
    try:
        # リクエストデータのスクラブ。成功時だけ event["request"] を差し替える。
        # _scrub_sensitive_data / _scrub_query_string / _scrub_url は全て non-destructive で
        # 新しいオブジェクトを返すため、top-level dict の shallow copy で十分。
        # 元 request の non-mutation 契約は既存テスト
        # ``test_before_send_fail_closed_without_partial_request_mutation`` で継続検証。
        event_dict = cast(dict[str, Any], event)
        if "request" in event_dict:
            request = event_dict["request"]
            if isinstance(request, dict):
                scrubbed_request = dict(request)
                if "headers" in scrubbed_request:
                    scrubbed_request["headers"] = _scrub_sensitive_data(scrubbed_request["headers"])
                if "data" in scrubbed_request:
                    scrubbed_request["data"] = _scrub_sensitive_data(scrubbed_request["data"])
                if "query_string" in scrubbed_request and isinstance(
                    scrubbed_request["query_string"], (str, bytes)
                ):
                    scrubbed_request["query_string"] = _scrub_request_query_string(
                        scrubbed_request["query_string"]
                    )
                if "url" in scrubbed_request and isinstance(scrubbed_request["url"], str):
                    scrubbed_request["url"] = _scrub_url(scrubbed_request["url"])
                event_dict["request"] = scrubbed_request
            else:
                event_dict["request"] = {}
                _logger.warning(
                    "sentry_request_type_unexpected",
                    actual_type=type(request).__name__,
                    action="replaced_with_empty_dict",
                    event_id=event_dict.get("event_id"),
                )

        # 追加データのスクラブ（2層防御）
        # _scrub_sentry_field: 非dict型フィールドを空dictに置換（型安全化・PII漏洩防止）
        # _scrub_sensitive_data: dict内の機密キーを [REDACTED] に置換（PII除外）
        for field in _SCRUBBED_EVENT_FIELDS:
            _scrub_sentry_field(event_dict, field)
    except (MemoryError, RecursionError):  # fmt: skip
        # システム異常（OOM・スタックオーバーフロー）は吸収せず再 raise する。
        # scrub 失敗の silent absorption で PII ドロップが遅延するリスクより
        # プロセス異常終了を優先させる（CWE-391 対策）。
        raise
    except Exception as exc:
        # sys.exc_info() がアクティブな状態で _emit_scrub_failure_to_sentry を
        # 呼ぶと、Sentry SDK が元例外（PII 付き）を内部通知イベントに添付する
        # リスクがあるため、例外コンテキストの外で呼び出す（fail-closed 防御, PR#347）。
        scrub_exc = exc

    if scrub_exc is not None:
        _emit_scrub_failure_to_sentry(scrub_exc)
        return None

    return event


def init_sentry() -> bool:  # noqa: C901
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

        # 開発/テスト環境では許容（ログ警告のみ）
        # warnings.warn は filterwarnings('error') 環境で UserWarning を raise し、
        # __context__ 経由で DSN が漏洩するリスクがあるため _logger.warning に変更。
        try:
            _logger.warning(
                "sentry_sdk_not_installed",
                error_type=type(exc).__name__,
                error_module=type(exc).__module__,
            )
        except Exception as logger_exc:  # noqa: BLE001
            # ロガー失敗時は stderr へフォールバック（PII 非露出）。
            # _emit_scrub_failure_to_sentry と同様にエラー型/モジュールを記録し設計を統一 (PR#347)。
            print(
                "[SENTRY_WARN] sentry_sdk_not_installed "
                f"logger_error_type={type(logger_exc).__name__} "
                f"logger_error_module={type(logger_exc).__module__}",
                file=sys.stderr,
                flush=True,
            )
        return False

    except Exception as exc:
        # その他の初期化失敗 - 本番環境では例外を発生させる（Fail-Fast）
        if is_production_like:
            raise RuntimeError(
                f"Sentry initialization failed in production: {type(exc).__name__}: {exc}",
            ) from exc

        # 開発/テスト環境ではログ警告のみ
        # warnings.warn は filterwarnings('error') 環境で UserWarning を raise し、
        # __context__ 経由で DSN が漏洩するリスクがあるため _logger.warning に変更。
        try:
            _logger.warning(
                "sentry_init_failed",
                error_type=type(exc).__name__,
                error_module=type(exc).__module__,
            )
        except Exception as logger_exc:  # noqa: BLE001
            # ロガー失敗時は stderr へフォールバック（PII 非露出）。
            # _emit_scrub_failure_to_sentry と同様にエラー型/モジュールを記録し設計を統一 (PR#347)。
            print(
                "[SENTRY_WARN] sentry_init_failed "
                f"logger_error_type={type(logger_exc).__name__} "
                f"logger_error_module={type(logger_exc).__module__}",
                file=sys.stderr,
                flush=True,
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
