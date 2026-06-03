"""Sentry SDK初期化モジュール

エラー監視サービスSentryとの統合を提供。
structlogと連携し、ERROR以上のログをSentryに送信。

依存関係:
    - config/settings.py: SentryConfig（DSN、有効化フラグ等）
    - sentry-sdk[httpx] >= 2.61.0: before_send / new_scope APIを使用

初期化タイミング:
    アプリケーション起動時、ログ設定後に一度だけ呼び出し。
    structlogのconfigure()後、最初のログ出力前が推奨。

使用例:
    from utils.sentry_init import init_sentry

    # アプリケーション起動時
    if init_sentry():
        logger.info("Sentry monitoring enabled")

デバッグ:
    初期化失敗時は warning ログを常時出力する（本番監視対応）。

セキュリティ:
    - before_sendフックで機密データを自動除外（44種類のキーパターン）
    - DSNはSecretStrで管理（config/settings.py）
    - enabled=Falseで完全無効化可能
"""

from __future__ import annotations

import re
import secrets
import sys
from functools import lru_cache
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

    （PR#347 S-1: dict が常態の現行 SDK では list 分岐は一見 YAGNI に見えるが、
    上記の ``_before_send`` list[tuple] 受け入れ契約をテストが独立に検証しているため
    意図的に維持する。当該契約テスト廃止時にのみ本分岐の削除を検討すること。）

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


_logger = get_logger(__name__)


def _safe_log_warning(event: str, **fields: Any) -> None:
    """PII scrub フロー内で fail-open 用に warning ログを送出する（例外抑止）。

    PR#347 review: ``_scrub_sensitive_data`` / ``_scrub_exception_field`` の 6 箇所に
    重複していた ``try: _logger.warning(...) / except Exception: pass`` パターンを
    DRY 化したヘルパー。関数内で ``# noqa: BLE001, S110`` を 1 箇所に集約し、
    ``try/except Exception: pass`` でロガー例外を抑止する。

    fail-open ロジック内部でのみ使用する想定。``_scrub_sentry_field`` (本ファイル
    下流) の ``print(..., file=sys.stderr)`` フォールバックパターンとは責務が異なる:
    あちらは fail-safe (event drop 防止) のため stderr 通知が必要、こちらは fail-open
    (元データ通過) のため例外抑止のみで十分。

    **PII 漏洩防止**: ``event`` 引数は静的な識別子文字列 (例: "sentry_field_type_unexpected")
    のみを渡すこと。動的なユーザーデータや変数値を直接渡すと、ログ経由で PII が
    漏洩する。動的な値は ``**fields`` の keyword 引数として渡すこと。
    """
    try:
        _logger.warning(event, **fields)
    except (MemoryError, RecursionError):  # fmt: skip
        # MemoryError / RecursionError は Exception 派生のため、再raise しないと
        # 下流の except Exception に捕捉されサイレント隠蔽される。
        # 致命的エラーとして必ず再raise（fail-fast）。
        # `# fmt: skip`: ruff format はタプル括弧を除去するが、Python 3.14 (PEP 758)
        # では括弧なし `except A, B:` も有効な構文（旧 Py2 binding ではない）。
        # 可読性のため括弧付きタプルを保持する（utils/ 全体で統一の規約。PR#347 #2-2）。
        raise
    except Exception as exc:  # noqa: BLE001
        # ロガー失敗 → fail-open（イベント drop 防止）だが、
        # 完全無音は障害を隠蔽するため最低限 stderr に通知する。
        try:
            print(
                f"[sentry_init] _safe_log_warning failed: "
                f"event={event!r} error_type={type(exc).__name__} "
                f"error_module={type(exc).__module__} "
                # fields のキー名は呼び出し元によっては機密語を含みうるため件数のみ出力する
                # （event 名で呼び出し箇所は特定可能, PR#347 review SF-3）。
                f"fields_count={len(fields)}",
                file=sys.stderr,
                flush=True,
            )
        except Exception:  # noqa: BLE001, S110
            # stderr 自体が壊れている場合は本当に何もできない
            pass


def _scrub_exception_frame(frame: Any) -> Any:
    """Sentry exception frame を fail-open でスクラブする。"""
    if not isinstance(frame, dict):
        _safe_log_warning(
            "sentry_exception_frame_unexpected_type",
            actual_type=type(frame).__name__,
            action="skip_frame_scrub",
            pii_leak_risk="HIGH",
        )
        return frame

    scrubbed_frame = dict(frame)
    frame_vars = scrubbed_frame.get("vars")
    if isinstance(frame_vars, dict):
        scrubbed_frame["vars"] = _scrub_sensitive_data(frame_vars)
    elif frame_vars is not None:
        _safe_log_warning(
            "sentry_exception_frame_vars_unexpected_type",
            actual_type=type(frame_vars).__name__,
            action="skip_vars_scrub",
        )
    return scrubbed_frame


def _scrub_exception_stacktrace(stacktrace: dict[str, Any]) -> dict[str, Any]:
    """Sentry exception stacktrace を fail-open でスクラブする。"""
    frames = stacktrace.get("frames")
    if isinstance(frames, list):
        scrubbed_stacktrace = dict(stacktrace)
        scrubbed_stacktrace["frames"] = [_scrub_exception_frame(frame) for frame in frames]
        return scrubbed_stacktrace
    if frames is not None:
        _safe_log_warning(
            "sentry_exception_frames_unexpected_type",
            actual_type=type(frames).__name__,
            action="skip_frames_scrub",
        )
    return stacktrace


def _scrub_exception_value_item_extra_keys(scrubbed_value: dict[str, Any]) -> None:
    """exception value item の value/stacktrace 以外のトップレベルキーを in-place で
    機密スクラブする (PR#347 Q-1)。

    標準 Sentry exception value item は type/module/mechanism 等で PII を含まないが、
    カスタム SDK 統合が token/password 等を value item に直接付与した場合の漏洩を
    防ぐ defense-in-depth。``type`` は ``_is_sensitive_key`` 非該当のため redact されず
    観測性を保つ（S-1 の type 非 redact 方針と両立）。dict 値の反復中に値のみを
    更新する（キーの追加/削除はしないため反復は安全）。
    """
    for key in scrubbed_value:
        if key in ("value", "stacktrace"):
            continue
        item = scrubbed_value[key]
        if _is_sensitive_key(key):
            scrubbed_value[key] = "[REDACTED]"
        elif isinstance(item, dict):
            scrubbed_value[key] = _scrub_sensitive_data(item)
        elif isinstance(item, (list, tuple)):
            scrubbed_value[key] = type(item)(_scrub_list_item(elem, _depth=0) for elem in item)


def _scrub_exception_value_item(value_item: Any) -> Any:
    """Sentry exception values[*] を fail-open でスクラブする。"""
    if not isinstance(value_item, dict):
        if isinstance(value_item, (list, tuple)):
            return type(value_item)(_scrub_list_item(item, _depth=0) for item in value_item)
        _safe_log_warning(
            "sentry_exception_value_item_unexpected_type",
            actual_type=type(value_item).__name__,
            action="skip_item",
        )
        return value_item

    scrubbed_value = dict(value_item)
    if isinstance(scrubbed_value.get("value"), str):
        scrubbed_value["value"] = "[REDACTED]"

    stacktrace = scrubbed_value.get("stacktrace")
    if isinstance(stacktrace, dict):
        scrubbed_value["stacktrace"] = _scrub_exception_stacktrace(stacktrace)
    elif stacktrace is not None:
        _safe_log_warning(
            "sentry_exception_stacktrace_unexpected_type",
            actual_type=type(stacktrace).__name__,
            action="skip_stacktrace_scrub",
        )

    # value / stacktrace 以外のトップレベルキーも機密判定する (PR#347 Q-1)。
    _scrub_exception_value_item_extra_keys(scrubbed_value)

    return scrubbed_value


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
        "authtoken",  # 複合語バリアント — 単語境界検出の false negative 補完 (#4)
        "usertoken",  # 複合語バリアント
        "userpassword",  # 複合語バリアント
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
        "username",  # Sentry user.username は個人識別情報として扱う
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
        "csrf_token",
        "x-refresh-token",
        "x-access-token",
    },
)

# 遅延初期化フラグ
_sentry_initialized: bool = False


# 再帰制限のデフォルト値
MAX_SCRUB_DEPTH: int = 10  # 実測値 2-4、余裕値 10 は infinite recursion 防止用

# before_send / before_send_transaction でスクラブ対象とするイベントフィールド
# （PII漏洩防止の対象集合）。error / transaction 双方が同一 _before_send を通る。
_SCRUBBED_EVENT_FIELDS: frozenset[str] = frozenset(
    {
        "extra",
        "user",
        "contexts",
        "tags",
        "breadcrumbs",
        # transaction イベント固有の子span配列（spans[*].data/description/tags）を
        # スクラブする。before_send_transaction 経路でのみ実在し、error イベントには
        # 当該キーが無いため _scrub_sentry_field の `if field in event_dict` で安全スキップ。
        "spans",
        # values[*].value は _is_sensitive_key の結果に関わらず
        # 無条件 [REDACTED] 置換（PII漏洩防止のため）
        "exception",
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
# 既知の false negative: ssnumber / cvvcode / foopassword 等の複合語は suffix が [a-z] のため
# suffix lookahead で非一致。頻出バリアントは SENSITIVE_KEYS に明示追加済み (#4)。
_NORMALIZED_SENSITIVE_KEYS: frozenset[str] = frozenset(
    sensitive.replace("-", "_") for sensitive in SENSITIVE_KEYS
)
# プレフィックス境界 `(?:^|[_\d])` はハイフンを含まないが、入力キーは _is_sensitive_key の
# ステップ4 (`key_norm.lower().replace("-", "_")`) でハイフンがアンダースコアへ正規化済みのため、
# `x-auth-token` → `x_auth_token` として `_` 境界で正しくマッチする (PR#347 review Q-4)。
# 左境界 `[_\d]` は数字を含むが小文字英字を含まないため非対称: `v2token` → True
# （数字 `2` が左境界）/ `footoken` → False（小文字 `o` は境界外）。これは単語先頭の
# 機密語のみを検出し、複合語中の偶発的な部分一致を避ける意図的設計（テストで担保。
# PR#347 review #2-5）。
_SENSITIVE_KEY_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|[_\d])(?:"
    + "|".join(
        re.escape(sensitive)
        for sensitive in sorted(_NORMALIZED_SENSITIVE_KEYS, key=len, reverse=True)
    )
    + r")(?=[^a-z]|$)"  # suffix-PII(ssnumber/cvvcode等)対応 (PR#347)
)
# 全大文字命名 fallback 用: アンダースコア除去後の完全一致集合 (PR#347)
# APIKEY / ACCESSTOKEN 等は ACRONYM 分割が効かないため別途事前計算
_COMPACT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    sensitive.replace("_", "") for sensitive in _NORMALIZED_SENSITIVE_KEYS
)

# camelCase / ACRONYM 分割用の事前コンパイル済みパターン (PR#347 review)。
# 生リテラル re.sub の re._cache 依存を排し、設計を統一するため、
# すべての正規表現をモジュールレベルで事前コンパイルしています。
_ACRONYM_PATTERN: re.Pattern[str] = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_PATTERN: re.Pattern[str] = re.compile(r"(?<=[a-z])(?=[A-Z])")
# URL パスセグメント内のメールアドレス形式 PII を検出して [REDACTED] に置換する (#16)
_PATH_PII_PATTERN: re.Pattern[str] = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


# maxsize=512 — Sentry イベントが持つユニークキー名は典型的に 50〜200 程度。
# 512 はその 2〜10 倍のマージン。SENSITIVE_KEYS の要素数 (44) とは無関係。
@lru_cache(maxsize=512)
def _is_sensitive_key(key: str) -> bool:
    """機密キーかどうかを判定する（単語境界一致 + ハイフン/アンダースコア正規化）。

    判定アルゴリズム:
        1. ACRONYMWord → ACRONYM_Word 変換（`APIKey` → `API_Key`）
        2. camelCase → snake_case 変換（`accessToken` → `access_Token`）
        3. key を lower-case 化
        4. ハイフン (``-``) およびドット (``.``) をアンダースコア (``_``) へ正規化
           （`database.url` → `database_url`、`x-auth-token` → `x_auth_token`）
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
    key_norm = _CAMEL_PATTERN.sub("_", key_norm)  # wordWord → word_Word（lower()前に分割）
    key_norm = key_norm.lower().replace("-", "_").replace(".", "_")
    if _SENSITIVE_KEY_PATTERN.search(key_norm) is not None:
        return True
    # 全大文字命名 fallback (APIKEY, ACCESSTOKEN 等): ACRONYM 分割が効かない場合に
    # アンダースコア除去後の完全一致で補完 (PR#347)
    return key_norm.replace("_", "") in _COMPACT_SENSITIVE_KEYS


def _scrub_list_item(item: Any, _depth: int) -> Any:
    """tags 以外のフィールド（breadcrumbs / extra / contexts 等）向けの汎用 list 要素スクラブ。
    tags 専用の ``_scrub_tags_item`` と異なり、list[2] を (key, value) ペアとして扱わない
    ため、breadcrumbs 内の2要素 list を誤って tag pair 判定して過剰 redact するリスクがない。
    ``_scrub_sentry_field`` が field!="tags" の場合に本関数を呼ぶこと。

    tags 専用の (key, value) ペア判定は ``_scrub_sentry_field`` の field 単位
    dispatch に集約し、本関数では tuple のみを tag pair として扱う
    （Sentry SDK が tags を list[tuple[str, str]] で渡す場合の互換性のため）。
    list[2] with str[0] のような汎用 list を tag pair と誤判定して
    breadcrumb 等の非 PII 2要素 list を過剰 redact する問題を避ける。
    """
    if _depth >= MAX_SCRUB_DEPTH:
        _safe_log_warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
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


def _scrub_span_item(item: Any, _depth: int) -> Any:
    """Sentry transaction span の単一要素をスクラブする。"""
    if _depth >= MAX_SCRUB_DEPTH:
        _safe_log_warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
        return "[MAX_DEPTH_EXCEEDED]"
    if not isinstance(item, dict):
        return _scrub_list_item(item, _depth + 1)

    scrubbed = _scrub_sensitive_data(item, _depth + 1)
    if not isinstance(scrubbed, dict):
        # _depth+1 が MAX_SCRUB_DEPTH に到達すると _scrub_sensitive_data は
        # "[MAX_DEPTH_EXCEEDED]" (str) を返す。str.get() による AttributeError →
        # _before_send の except 捕捉 → イベントのサイレントドロップを防ぐ防御ガード
        # （PR#347 B-1）。現呼び出し元 _scrub_sentry_field は _depth=0 固定のため到達
        # しないが、将来 _scrub_span_item が深い再帰文脈から呼ばれた場合の保険。
        return scrubbed
    description = scrubbed.get("description")
    if isinstance(description, str):
        method, separator, target = description.partition(" ")
        value_to_scrub = target if separator else description
        if "?" in value_to_scrub or "#" in value_to_scrub:
            scrubbed_description = _scrub_url(value_to_scrub)
        else:
            scrubbed_description = _PATH_PII_PATTERN.sub("[REDACTED]", value_to_scrub)
        scrubbed["description"] = (
            f"{method} {scrubbed_description}" if separator else scrubbed_description
        )
    return scrubbed


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
        # fail-open: 非dict入力はスクラブ不可。警告を残してそのまま返す。
        # _scrub_sentry_field の isinstance(value, dict) ガードと二重防御。
        _safe_log_warning(
            "scrub_sensitive_data_unexpected_type",
            actual_type=type(data).__name__,
            action="return_as_is",
        )
        return data

    # 再帰制限チェック（循環参照対策）
    if _depth >= MAX_SCRUB_DEPTH:
        _safe_log_warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
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


def _scrub_request_field(value: Any) -> Any:
    """Sentry request.* フィールドを fail-closed でスクラブする。"""
    if isinstance(value, dict):
        return _scrub_sensitive_data(value)
    if isinstance(value, list):
        return [_scrub_list_item(item, _depth=0) for item in value]

    _safe_log_warning(
        "sentry_request_field_type_unexpected",
        actual_type=type(value).__name__,
        action="replaced_with_redacted",
    )
    return "[REDACTED]"


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
    """URLのuserinfo/fragmentを除去し、query・pathのPIIをスクラブする。

    - query: `_scrub_query_string` でキーベーススクラブ
    - path: メールアドレス形式のPII (`_PATH_PII_PATTERN`) を [REDACTED] に置換 (#16)
    - params: RFC 2396 パスパラメータ (`;key=value` 形式) はキースクラブを意図的に行わない (#7)
              ただしメールアドレス形式の PII は path 同様に除去する (#16)
    - fragment: 完全除去（PII漏洩防止）
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if hostname is None:
        netloc = ""
    else:
        netloc = f"[{hostname}]" if ":" in hostname else hostname
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
            _PATH_PII_PATTERN.sub("[REDACTED]", parsed.path),
            # RFC 2396 パスパラメータ: query string ではないためキースクラブは不要 (#7)
            # ただしメールアドレス形式の PII は path と同様に除去する (#16)
            _PATH_PII_PATTERN.sub("[REDACTED]", parsed.params) if parsed.params else "",
            _scrub_query_string(parsed.query) if parsed.query else "",
            "",  # fragment を除去（PII 漏洩防止）
        )
    )


def _scrub_tags_item(item: Any, _depth: int = 0) -> Any:
    """tags フィールド専用の要素スクラブ。``_scrub_list_item`` との違いは (key, value)
    ペア判定を list[2] にも拡張している点で、``_scrub_sentry_field`` が field=="tags"
    の場合のみ本関数を呼ぶ。tags 以外のフィールドには ``_scrub_list_item`` を使用すること。

    Sentry SDK 仕様: tags は ``dict[str, str]`` または ``list[tuple[str, str]]``。
    JSON roundtrip で tuple が list 化されるため list[2] も tag pair として扱う。
    加えて非標準だが custom before_send hook 等で生じうる dict / nested list 形態でも
    機密キーを redact する（defense-in-depth）。
    _depth による再帰深さ保護を行い、MAX_SCRUB_DEPTH 超過時は安全サイドに倒す。
    """
    if _depth >= MAX_SCRUB_DEPTH:
        _safe_log_warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
        return "[MAX_DEPTH_EXCEEDED]"
    if isinstance(item, (tuple, list)) and len(item) == 2:
        key = item[0]
        scrubbed_value = (
            "[REDACTED]"
            if (isinstance(key, str) and _is_sensitive_key(key))
            else _scrub_list_item(item[1], _depth + 1)
        )
        # type(item) は tuple/list 両対応の汎用ファクトリ（意図的な動的構築）
        return cast(Any, type(item))([key, scrubbed_value])
    if isinstance(item, dict):
        return _scrub_sensitive_data(item, _depth + 1)
    if isinstance(item, list):
        # nested list は汎用 scrub にフォールバック（深さを引き継ぐ）
        return [_scrub_list_item(child, _depth=_depth + 1) for child in item]
    if isinstance(item, tuple):
        # len != 2 の tuple も _scrub_list_item で汎用スクラブ（list との一貫性）
        return tuple(_scrub_list_item(child, _depth + 1) for child in item)
    return item


def _scrub_exception_field(exception_value: dict[str, Any]) -> dict[str, Any]:
    """Sentry exception フィールドを構造検証付きでスクラブする（fail-open）。

    Sentry の exception 構造:
      {values: [{type, value, stacktrace: {frames: [{vars: {...}}]}}]}

    各階層（values→stacktrace→frames→vars）で型を isinstance で検証し、
    未知の構造では警告を残してスキップする（破壊しない）。
    vars 内の機密キーは _scrub_sensitive_data() で redact する。
    values[*].value は例外メッセージ文字列として全体を `[REDACTED]` に置換する。
    これは PII 保護を観測性より優先する意図的なトレードオフであり、
    PII を含まない FileNotFoundError 等の診断情報も失われる。将来改善する場合は、
    特定キーワードのみをマスクする selective redact へ移行する。

    **values[*].type は意図的に redact しない** (PR#347 review S-1):
        `type` フィールドは例外クラス名 (`ValueError`, `KeyError` 等) を保持し、
        通常 PII を含まない。例外分類は Sentry UI / alert routing / metric 集計の
        primary key として機能するため、redact すると観測性が壊滅的に低下する。
        ただし将来 `type` に PII 文字列が現れる SDK 拡張 / custom exception
        命名規則が導入された場合は本方針を再評価する必要がある。

    設計トレードオフ (fail-open):
        Sentry SDK の将来バージョンや custom integration により未知の exception
        構造が渡された場合、本関数は破壊せず通過させる（observability 優先）。
        この設計には残存リスクが1点存在する:
        **未知構造の内側に機密データが含まれていた場合、scrub されず Sentry に
        到達する可能性がある**。
        最外殻 ``_before_send`` の ``except Exception`` 二重防御は、本関数が
        ``MemoryError`` / ``RecursionError`` 以外の例外を送出した場合にのみ
        ``_emit_scrub_failure_to_sentry`` 経由で event drop に倒すが、
        fail-open ロジックは例外を送出せず正常完了するため、未知構造による
        PII 漏洩は二重防御では検出されない（許容された残存リスク）。
        fail-closed への変更を検討する場合は、観測性低下（正常な例外イベント
        まで drop される）とのトレードオフを評価すること。

    Args:
        exception_value: Sentry イベントの "exception" 辞書

    Returns:
        スクラブ済み exception 辞書（元データは変更しない）

    """
    values = exception_value.get("values")
    if isinstance(values, dict):
        # dict 型 values: _scrub_sensitive_data で内容をスクラブして返す (PR#347 review #6)
        result = dict(exception_value)
        result["values"] = _scrub_sensitive_data(values)
        return result
    if values is None:
        # "values" キー未存在は Sentry exception interface 仕様上の有効な構造
        # (getsentry/sentry interfaces/exception.py: get_path(data, "values",
        # default=[]) で空リスト扱い、Relay schema でも values は必須でない)。
        # よって誤検知 WARNING を出さずに、他キーをベストエフォートスクラブして返す
        # (PR#347 review #8: 正常構造に対するログノイズ抑制)。
        scrubbed = _scrub_sensitive_data(exception_value)
        # _depth=0 開始のため dict 以外（"[MAX_DEPTH_EXCEEDED]"）は構造上発生しないが、
        # cast による型隠蔽を避け isinstance ガードで型安全を明示する（PR#347 Q-2）。
        return scrubbed if isinstance(scrubbed, dict) else {}
    if not isinstance(values, list):
        # str / int 等、None でも list/dict でもない真に予期しない型のみ WARNING。
        _safe_log_warning(
            "sentry_exception_values_unexpected_type",
            actual_type=type(values).__name__,
            action="exception_scrub_fallback",
        )
        # 構造不明でも _scrub_sensitive_data でベストエフォートスクラブ (PR#347)
        scrubbed = _scrub_sensitive_data(exception_value)
        # _depth=0 開始のため dict 以外（"[MAX_DEPTH_EXCEEDED]"）は構造上発生しないが、
        # cast による型隠蔽を避け isinstance ガードで型安全を明示する（PR#347 Q-2）。
        return scrubbed if isinstance(scrubbed, dict) else {}

    result = dict(exception_value)
    result["values"] = [_scrub_exception_value_item(val) for val in values]
    return result


def _scrub_sentry_field(event_dict: dict[str, Any], field: str) -> None:
    """Sentryイベントの単一フィールドをスクラブする（_before_send 専用）。

    dict型の場合は _scrub_sensitive_data() で再帰的にスクラブする
    （``exception`` は _scrub_exception_field で values[*].value REDACTION と
    stackframe scrub を適用）。
    list型の場合は field 単位で dispatch する: ``exception`` は各要素へ
    _scrub_exception_value_item を適用し（defense-in-depth）、``tags`` は
    (key, value) ペア形式、その他（breadcrumbs 等）は dict/list 要素形式として
    スクラブする。非PII のデバッグ情報（リクエストID等）は保持する
    （Sentry SDK 仕様: tags は ``list[tuple[str, str]]`` 形式も許容）。
    上記以外の型の場合は安全サイドに置換する（fail-closed）: ``exception`` は
    Sentry exception interface 準拠の無害なプレースホルダ（``ScrubbedException``）へ、
    それ以外は空dictへ置換し、logger.warning を常時出力する（本番監視対応）。
    _scrub_sensitive_data の内部 non-dict ガードと二重防御を構成する。

    Args:
        event_dict: Sentryイベント辞書（破壊的更新）
        field: スクラブ対象フィールド名

    """
    if field in event_dict:
        value = event_dict[field]
        if isinstance(value, dict):
            if field == "exception":
                event_dict[field] = _scrub_exception_field(value)
            else:
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
            if field == "exception":
                # exception が list 形式（Sentry 標準は dict だが custom before_send
                # 等で生じうる）でも values[*].value の REDACTION と stackframe vars
                # scrub を適用し、PII（例外メッセージ・frame 変数）の素通りを防ぐ
                # （PR#347 #1 blocker: defense-in-depth）。
                # dict 要素は exception 専用スクラブ、非 dict 要素（custom hook が
                # 生成しうる list/tuple/scalar）は汎用 _scrub_list_item で再帰スクラブ
                # する。これにより tags/spans/その他（L697）の list 分岐と同様に
                # 「全分岐で非 dict 要素も再帰スクラブ・素通しゼロ」を満たし、dispatch の
                # 一貫性を保つ（PR#347 codex adversarial review: fail-open 非対称の解消）。
                event_dict[field] = [
                    _scrub_exception_value_item(item)
                    if isinstance(item, dict)
                    else _scrub_list_item(item, _depth=0)
                    for item in value
                ]
            elif field == "tags":
                event_dict[field] = [_scrub_tags_item(item, _depth=0) for item in value]
            elif field == "spans":
                event_dict[field] = [_scrub_span_item(item, _depth=0) for item in value]
            else:
                event_dict[field] = [_scrub_list_item(item, _depth=0) for item in value]
        else:
            # dict/list以外はスクラブ不可能なため、安全サイドに倒して置換する（fail-closed）。
            # exception フィールドは Sentry exception interface 仕様に準拠した
            # 無害なプレースホルダ構造へ置換し PII 素通りを防ぐ（PR#347 review #10）。
            # 他フィールドは空 dict に置換する。
            if field == "exception":
                event_dict[field] = {
                    "values": [
                        {
                            "type": "ScrubbedException",
                            "value": "[REDACTED: unscrubable exception structure]",
                        }
                    ]
                }
                _safe_log_warning(
                    "sentry_field_type_unexpected",
                    field=field,
                    actual_type=type(value).__name__,
                    action="replaced_with_safe_placeholder",
                    event_id=event_dict.get("event_id"),
                )
            else:
                event_dict[field] = {}
                _safe_log_warning(
                    "sentry_field_type_unexpected",
                    field=field,
                    actual_type=type(value).__name__,
                    action="replaced_with_empty_dict",
                    event_id=event_dict.get("event_id"),
                )


def _emit_scrub_failure_to_sentry(exc: BaseException, event_id: str | None = None) -> None:
    """scrub 失敗を内部識別 tag 付きで Sentry へ通知する（fail-safe）。

    sentry_sdk.capture_message は再度 _before_send を通るが、付与した
    _INTERNAL_TAG_KEY=_INTERNAL_TAG_VALUE を冒頭で検出して scrub をスキップ
    通過させるため無限再帰しない。内部 SDK 呼び出し自体が例外を投げた場合は
    最終フォールバックとして stderr へ出力し、メインプロセスをクラッシュさせない。

    **SDK バージョン制約 (PR#347 review #10-SF-3)**:
        再帰防止ガード（_INTERNAL_TAG_KEY による scrub スキップ）は Sentry SDK 2.x
        の内部動作（``Scope._apply_tags_to_event``）に依存する。
        pyproject.toml の ``sentry-sdk<3.0.0`` 制約により 3.x 以降の
        内部変更から保護している。3.x へ移行する際は本ガードの動作を再検証すること。

    **Security constraint (PR#347 review #11-6)**: ``extra`` フィールドに
    PII を含めてはならない。本制約に違反した場合、内部通知イベントが scrub を
    バイパスして PII がそのまま Sentry に到達する。
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
            # SECURITY: set_extra に PII 含む値追加禁止 — _before_send scrub バイパスのため
            scope.set_extra("error_type", type(exc).__qualname__)
            scope.set_extra("error_module", type(exc).__module__)
            scope.set_extra("action", "event_dropped")
            # event_id は UUID 形式のため PII ではない（PR#347 review #12/#28）
            if event_id is not None:
                scope.set_extra("event_id", event_id)
            scope.capture_message("sentry_scrub_failed", level="error")
    except RecursionError:
        # RecursionError も Exception 派生のため、再raise しないと直下の
        # except Exception に捕捉されサイレント隠蔽される（他5箇所と同一方針）。
        # 再raise後は呼び出し元 _before_send の emit 保護 try/except (SF-1, PR#347 #15)
        # が捕捉し、明示的に return None するため fail-closed（PII 非送信）は維持される。
        raise
    except MemoryError:
        # MemoryError も同様に fail-fast。OOM を握り潰さず即座に伝播させ、
        # 呼び出し元 SF-1 の emit 保護が捕捉して return None する。
        raise
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

    # scrub_exc は except 句で捕捉した例外を try ブロックの外へ持ち出すための変数。
    # _emit_scrub_failure_to_sentry を except コンテキスト外で呼ぶことで sys.exc_info() が
    # アクティブな状態を避け、Sentry SDK が元例外(PII 付き)を内部通知イベントに添付する
    # 事故を防ぐ (fail-closed 防御, PR#347 review S-4。詳細は下方 `except Exception` 節を参照)。
    scrub_exc: Exception | None = None
    # cast は実行時 no-op（型システム専用）— try 外に置いても動作変化なし
    event_dict = cast(dict[str, Any], event)
    try:
        # リクエストデータのスクラブ。成功時だけ event["request"] を差し替える。
        # _scrub_sensitive_data / _scrub_query_string / _scrub_url は全て non-destructive で
        # 新しいオブジェクトを返すため、top-level dict の shallow copy で十分。
        # 元 request の non-mutation 契約は既存テスト
        # ``test_before_send_fail_closed_without_partial_request_mutation`` で継続検証。
        if "request" in event_dict:
            request = event_dict["request"]
            if isinstance(request, dict):
                scrubbed_request = dict(request)
                for req_field in ("headers", "data", "cookies", "env"):
                    if req_field in scrubbed_request:
                        scrubbed_request[req_field] = _scrub_request_field(
                            scrubbed_request[req_field]
                        )
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
                _safe_log_warning(
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
        # システム異常（OOM・スタックオーバーフロー）は fail-closed で event を
        # ドロップする。before_send からの例外は Sentry SDK が内部 catch し
        # PII 付きイベントをそのまま送信し続けるリスクがあるため、stderr への
        # 最小通知だけ残して return None で安全に遮断する（CWE-391 対策）。
        try:
            print(
                "[SENTRY_SCRUB_FAILED] before_send system error: MemoryError or RecursionError",
                file=sys.stderr,
                flush=True,
            )
        except Exception:  # noqa: BLE001, S110
            pass
        return None
    except Exception as exc:
        # sys.exc_info() がアクティブな状態で _emit_scrub_failure_to_sentry を
        # 呼ぶと、Sentry SDK が元例外（PII 付き）を内部通知イベントに添付する
        # リスクがあるため、例外コンテキストの外で呼び出す（fail-closed 防御, PR#347）。
        scrub_exc = exc

    if scrub_exc is not None:
        try:
            _logger.error(
                "sentry_before_send_drop_event",
                error_type=type(scrub_exc).__qualname__,
                error_module=type(scrub_exc).__module__,
                event_id=event_dict.get("event_id"),
            )
        except Exception:  # noqa: BLE001
            # ロガー自体が失敗した場合のフォールバック（_safe_log_warningはフォールバック専用）
            _safe_log_warning(
                "sentry_before_send_drop_event",
                error_type=type(scrub_exc).__qualname__,
                error_module=type(scrub_exc).__module__,
            )
        # SF-1 (PR#347 #15): emit 呼び出しを try/except で保護する。
        # _emit_scrub_failure_to_sentry は内部でシステム異常 (MemoryError/RecursionError) を
        # re-raise する設計（emit 自身の except Exception による隠蔽回避のため）。その re-raise が
        # ここで未捕捉のまま伝播すると下方の return None を飛び越え、scrubbing 失敗イベントの
        # fail-closed ドロップが Sentry SDK の capture_internal_exceptions 挙動に依存してしまう。
        # 呼び出し側で全 Exception を捕捉して return None を保証することで、line 881 の
        # (MemoryError, RecursionError) → return None パターンと一貫した fail-closed を SDK 非依存で
        # 確定させる。KeyboardInterrupt / SystemExit は BaseException 直系のため捕捉せず伝播させる。
        try:
            _emit_scrub_failure_to_sentry(scrub_exc, event_id=event_dict.get("event_id"))
        except Exception:  # noqa: BLE001
            try:
                print(
                    "[SENTRY_SCRUB_FAILED] emit failed; event dropped (fail-closed)",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception:  # noqa: BLE001, S110
                pass
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
            # transaction イベントは before_send を通らない（SDK仕様）。同一 scrub 経路へ
            # 配線し、span data / WSGI-ASGI 由来の request を PII スクラブする（PR#347 review）。
            # per-event scrub コストは traces_sample_rate（既定 0.1 = 低サンプリング）で
            # 上限が画定されるため、現設定では累積負荷は許容範囲（PR#347 review #12/P-4）。
            before_send_transaction=_before_send,
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
                f"original_error_type={type(exc).__name__} "
                f"original_error_module={type(exc).__module__} "
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
                f"Sentry initialization failed in production: {type(exc).__name__}",
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
                f"original_error_type={type(exc).__name__} "
                f"original_error_module={type(exc).__module__} "
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
