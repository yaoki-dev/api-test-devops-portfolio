"""Sentry event value scrub helpers."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qsl, unquote, urlencode, urlparse, urlunparse

from utils.sentry_scrub_primitives import _PATH_PII_PATTERN, _is_sensitive_key, _safe_log_warning

__all__ = ["MAX_SCRUB_DEPTH"]

# 再帰制限のデフォルト値
MAX_SCRUB_DEPTH: int = 10  # 実測値 2-4、余裕値 10 は infinite recursion 防止用


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


def _scrub_path_params(params: str) -> str:
    """RFC 2396 パスパラメータ (`;key=value` 形式) をスクラブする。

    query string (_scrub_query_string) と同じ機密キー分類を使い、path 固有の
    email PII 除去も行う

    アルゴリズム:
        - params を ";" で split。
        - 各 part に "=" を含む場合は partition で key を抽出。
      - `_is_sensitive_key(unquote(key))` が True → `{key}=[REDACTED]` に置換。
          - False → email PII (_PATH_PII_PATTERN) を [REDACTED] に置換して保持。
        - "=" を含まない part → email PII を [REDACTED] に置換して保持。
        - ";" で再結合して返す。

    Args:
        params: urlparse の params フィールド（先頭の `;` を除いた文字列）。

    Returns:
        スクラブ済みパスパラメータ文字列。
    """
    scrubbed_parts: list[str] = []
    for part in params.split(";"):
        if "=" in part:
            key, sep, val = part.partition("=")
            scrubbed_key = _PATH_PII_PATTERN.sub("[REDACTED]", key)
            if not key or _is_sensitive_key(unquote(key)):
                scrubbed_parts.append(f"{scrubbed_key}{sep}[REDACTED]")
            else:
                # 非機密キーでも値中の email PII は除去（防御維持）
                scrubbed_parts.append(
                    f"{scrubbed_key}{sep}{_PATH_PII_PATTERN.sub('[REDACTED]', val)}"
                )
        else:
            # "=" を含まないセグメントは email PII のみ除去
            scrubbed_parts.append(_PATH_PII_PATTERN.sub("[REDACTED]", part))
    return ";".join(scrubbed_parts)


def _scrub_request_query_string(query_string: str | bytes) -> str:
    """Sentry request.query_string の str/bytes 値を安全にスクラブする。"""
    if isinstance(query_string, bytes):
        query_string = query_string.decode("utf-8", errors="ignore")
    return _scrub_query_string(query_string)


def _scrub_url(url: str) -> str:
    """URLのuserinfo/fragmentを除去し、query・pathのPIIをスクラブする。

    - query: `_scrub_query_string` でキーベーススクラブ
    - path: メールアドレス形式のPII (`_PATH_PII_PATTERN`) を [REDACTED] に置換 (#16)
    - params: RFC 2396 パスパラメータ (`;key=value` 形式) を `_scrub_path_params` で
              キーベーススクラブ + email PII 除去
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
            # RFC 2396 パスパラメータ: キーベーススクラブ + email PII 除去
            _scrub_path_params(parsed.params) if parsed.params else "",
            _scrub_query_string(parsed.query) if parsed.query else "",
            "",  # fragment を除去（PII 漏洩防止）
        )
    )
