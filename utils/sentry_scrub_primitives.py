"""Sentry event scrub primitive helpers."""

from __future__ import annotations

import re
import sys
from functools import lru_cache
from typing import Any

from utils.logger import get_logger

_logger = get_logger(__name__)

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
# `x-auth-token` → `x_auth_token` として `_` 境界で正しくマッチする。
# 左境界 `[_\d]` は数字を含むが小文字英字を含まないため非対称: `v2token` → True
# （数字 `2` が左境界）/ `footoken` → False（小文字 `o` は境界外）。これは単語先頭の
# 機密語のみを検出し、複合語中の偶発的な部分一致を避ける意図的設計（テストで担保。
_SENSITIVE_KEY_PATTERN: re.Pattern[str] = re.compile(
    r"(?:^|[_\d])(?:"
    + "|".join(
        re.escape(sensitive)
        for sensitive in sorted(_NORMALIZED_SENSITIVE_KEYS, key=len, reverse=True)
    )
    + r")(?=[^a-z]|$)"  # suffix-PII(ssnumber/cvvcode等)対応
)
# 全大文字命名 fallback 用: アンダースコア除去後の完全一致集合
# APIKEY / ACCESSTOKEN 等は ACRONYM 分割が効かないため別途事前計算
_COMPACT_SENSITIVE_KEYS: frozenset[str] = frozenset(
    sensitive.replace("_", "") for sensitive in _NORMALIZED_SENSITIVE_KEYS
)

# camelCase / ACRONYM 分割用の事前コンパイル済みパターン
# 生リテラル re.sub の re._cache 依存を排し、設計を統一するため、
# すべての正規表現をモジュールレベルで事前コンパイルしています。
_ACRONYM_PATTERN: re.Pattern[str] = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_PATTERN: re.Pattern[str] = re.compile(r"(?<=[a-z])(?=[A-Z])")
# URL パスセグメント内のメールアドレス形式 PII を検出して [REDACTED] に置換する (#16)
_PATH_PII_PATTERN: re.Pattern[str] = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _safe_log_warning(event: str, **fields: Any) -> None:
    """PII scrub フロー内で fail-open 用に warning ログを送出する（例外抑止）。

    ``_scrub_sensitive_data`` / ``_scrub_exception_field`` の 6 箇所に重複していた
    ``try: _logger.warning(...) / except Exception: pass` パターンをDRY 化したヘルパー。
    関数内で ``# noqa: BLE001, S110`` を 1 箇所に集約し、
    ``try/except Exception: pass`` でロガー例外を抑止する。

    fail-open ロジック内部でのみ使用する想定。logger 失敗時は完全無音を避け、
    最低限 stderr へ通知する（障害隠蔽防止）。``except Exception`` は抑止するが
    MemoryError / RecursionError は fail-fast で再 raise する。

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
        # 可読性のため括弧付きタプルを保持する（utils/ 全体で統一の規約）。
        raise
    except Exception as exc:  # noqa: BLE001
        # ロガー失敗 → fail-open（イベント drop 防止）だが、
        # 完全無音は障害を隠蔽するため最低限 stderr に通知する。
        try:
            print(
                f"[SENTRY_WARN] _safe_log_warning failed: "
                f"event={event!r} error_type={type(exc).__name__} "
                f"error_module={type(exc).__module__} "
                # fields のキー名は呼び出し元によっては機密語を含みうるため件数のみ出力する
                # （event 名で呼び出し箇所は特定可能）。
                f"fields_count={len(fields)}",
                file=sys.stderr,
                flush=True,
            )
        except Exception:  # noqa: BLE001, S110
            # stderr 自体が壊れている場合は本当に何もできない
            pass


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
    key_norm = _ACRONYM_PATTERN.sub(r"\1_\2", key)  # ACRONYMWord → ACRONYM_Word
    key_norm = _CAMEL_PATTERN.sub("_", key_norm)  # wordWord → word_Word（lower()前に分割）
    key_norm = key_norm.lower().replace("-", "_").replace(".", "_")
    if _SENSITIVE_KEY_PATTERN.search(key_norm) is not None:
        return True
    # 全大文字命名 fallback (APIKEY, ACCESSTOKEN 等): ACRONYM 分割が効かない場合に
    # アンダースコア除去後の完全一致で補完
    return key_norm.replace("_", "") in _COMPACT_SENSITIVE_KEYS
