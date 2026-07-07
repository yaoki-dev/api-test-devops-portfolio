"""Sanitization helpers for response models."""

import html
import re
import unicodedata
from urllib.parse import ParseResult, quote, unquote, urlunparse

_SCHEME_RE: re.Pattern[str] = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_HTML_META_RE: re.Pattern[str] = re.compile(r'[<>"\'&]')
_PERCENT_CTRL_RE: re.Pattern[str] = re.compile(
    r"%[01][0-9a-f]|%7f",  # C0制御文字(%00-%1f)およびDEL(%7f)を検出
    # 注: C1制御文字(%80-%9f)は対象外。
    # UTF-8/IRI由来のpercent-encoded内容と重複するため、グローバル拒否ではなく
    # netlocのみunquote(errors="strict")で不正UTF-8として検出する。
    # 注: %20(スペース)は制御文字ではないため非対象
    re.IGNORECASE,
)
# 不完全な%シーケンス検出 — unquoteがリテラル扱いするためUnicodeDecodeErrorが発生しない
# IGNORECASE flag で大文字小文字を統合（可読性目的、機能等価: r"%(?![0-9a-fA-F]{2})" と同一）
_INCOMPLETE_PCT_RE: re.Pattern[str] = re.compile(r"%(?![0-9a-f]{2})", re.IGNORECASE)
_ASCII_WHITESPACE_RE: re.Pattern[str] = re.compile(r"[ \t\n\r\f\v]")
_VARIATION_SELECTORS: frozenset[str] = frozenset(
    {chr(codepoint) for codepoint in range(0xFE00, 0xFE10)}
    | {chr(codepoint) for codepoint in range(0xE0100, 0xE01F0)}
)
WEBSITE_NORMALIZED_MAX_LENGTH: int = 2048
_INVISIBLE_CATEGORIES = frozenset({"Cf", "Cc", "Zs", "Zl", "Zp"})
# Cs（孤立サロゲート）を _INVISIBLE_CATEGORIES と合算した除去セット（1回目パスで使用）
_STRIP_CATEGORIES = _INVISIBLE_CATEGORIES | frozenset({"Cs"})


def _is_strippable_char(c: str, categories: frozenset[str]) -> bool:
    """不可視文字として除去すべき文字か判定する。

    Variation Selectors は Mn に分類されるが、結合文字（例: U+0301）は保持し、
    NFD由来のホスト名をサイレントに別文字列へ改変しない。
    """
    return c != " " and (unicodedata.category(c) in categories or c in _VARIATION_SELECTORS)


def strip_invisible_chars(v: str) -> str:
    """不可視文字・制御文字・Unicode空白をURL文字列から除去（NFKC正規化含む2パス処理）

    URLスキームバイパス防止のため、_STRIP_CATEGORIES（= _INVISIBLE_CATEGORIES | {"Cs"}）
    に属するUnicodeカテゴリを2パスの内包表記で除去する
    （パス1: NFKC正規化前・Cs含む全カテゴリ、パス2: NFKC正規化後・Cs除外）:

    - Cs: Surrogate（孤立サロゲート U+D800-U+DFFF）— 有効なUnicode文字列に
          含まれるべきでないためnormalize()前に除去（データ整合性）
    - Cf: Format文字（Bidi制御, ゼロ幅文字, Word Joiner等）
    - Cc: 制御文字（C0/C1制御文字, DEL等）
    - Mn: 非スペーシングマーク（Variation Selectors U+FE00-U+FE0F と
          Variation Selectors Supplement U+E0100-U+E01EF は個別除去。
          結合文字 U+0300等は保持し、NFD由来のホスト名改変を避ける）
    - Zs: Unicode空白（NBSP, Ogham Space, 全角空白等。U+0020通常スペースは
          Zsカテゴリに属するが、c == " " の特例条件で保持）
          ※ NFKC正規化前にも除去（U+3000等はNFKC後にU+0020へ変換される副作用を防止。
          U+1680等はNFKC変換対象外だが一括除去でスキームバイパスを防止）
    - Zl: 行区切り（U+2028 Line Separator）
    - Zp: 段落区切り（U+2029 Paragraph Separator）

    Python に同梱の Unicode バージョン内の新規文字に自動対応する。
    （Unicode バージョン自体の更新には Python バージョンアップが必要）
    """
    # パス1: Cs（孤立サロゲート）と不可視文字を一括除去
    # _STRIP_CATEGORIES = _INVISIBLE_CATEGORIES | {"Cs"} で Cs の個別除去を統合
    # NFKC前にZs等を除去（NFKC後にU+0020へ変換される副作用防止）
    # 全角英字（Ll/Lu等）はNFKC前に残し、NFKC正規化でASCIIに変換される
    pre_filtered = "".join(c for c in v if not _is_strippable_char(c, _STRIP_CATEGORIES))
    normalized = unicodedata.normalize("NFKC", pre_filtered)
    # パス2: NFKC後に新たに生成された不可視文字を除去
    # （Csは再出現しないため_INVISIBLE_CATEGORIESのみ）
    return "".join(c for c in normalized if not _is_strippable_char(c, _INVISIBLE_CATEGORIES))


def sanitize_user_content(value: str) -> str:
    """ユーザー生成コンテンツをHTMLエスケープでサニタイズ

    XSS攻撃を防ぐため、HTMLエスケープを適用。
    特殊文字（<, >, &, ", '）をHTMLエンティティに変換。

    Args:
        value: サニタイズ対象の文字列

    Returns:
        サニタイズ済み文字列

    Raises:
        ValueError: value が str 型でない場合

    Note:
        主にPydantic field_validator経由で使用されます。
        以前は str | None を受理していたが、現在は str のみ受理する。
        None を渡した場合は ValueError が発生する。

    Examples:
        >>> sanitize_user_content("<script>alert('XSS')</script>")
        '&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;'

    """
    if not isinstance(value, str):
        raise ValueError(f"文字列が必要です（受け取った型: {type(value).__name__}）")
    # quote=True: シングルクォート、ダブルクォートもエスケープ
    return html.escape(value, quote=True)


def _validate_netloc(parsed: ParseResult) -> None:
    """netloc のバリデーション.

    存在確認・空白文字拒否・不正percent decode拒否・userinfo禁止・
    HTMLメタ文字拒否・hostname解決チェックを行う。
    """
    if not parsed.netloc:
        raise ValueError("有効なホスト名が含まれていません")
    # 不正ポート文字列バイパス対策: parsed.port は整数でない場合 ValueError を送出する
    # （例: https://example.com:abc/path は netloc チェックをパスするが port アクセスで検出）
    try:
        _ = parsed.port
    except ValueError as e:
        raise ValueError("ポートが無効です（整数値でなければなりません）") from e
    # 多層防御: parsed.username/password に加え netloc の "@" リテラルも検査
    # （urlparse が特定のエンコード済み入力で username=None を返すエッジケース対策）
    try:
        decoded_netloc = unquote(parsed.netloc, errors="strict")
    except UnicodeDecodeError as e:
        raise ValueError(f"URLに不正なパーセントエンコードが含まれています: {e}") from e
    # raw と decoded 両方をチェック（%エンコードバイパス対策: https://example.com%20evil.com 等）
    if _ASCII_WHITESPACE_RE.search(parsed.netloc) or _ASCII_WHITESPACE_RE.search(decoded_netloc):
        raise ValueError("ホスト名に空白文字が含まれています")
    has_at = "@" in parsed.netloc or "@" in decoded_netloc
    if has_at:
        raise ValueError("URLにuserinfo（ユーザー名/パスワード）は指定できません")
    # @が含まれない場合のみ username/password を確認（urlparseのエッジケース補完）
    # （urlparse が特定のエンコード済み入力で username=None を返すエッジケース対策）
    try:
        has_userinfo = parsed.username is not None or parsed.password is not None
    except (ValueError, OverflowError) as e:  # fmt: skip
        # parsed.username/password は内部で独自にunquoteするため、L135-137のチェックとは独立
        raise ValueError(f"URLのuserinfoパースに失敗しました（netloc={parsed.netloc!r}）") from e
    if has_userinfo:
        raise ValueError("URLにuserinfo（ユーザー名/パスワード）は指定できません")
    # ホスト部にHTMLメタ文字（<, >, ", ', &）が含まれる場合は拒否
    if _HTML_META_RE.search(parsed.netloc) or _HTML_META_RE.search(decoded_netloc):
        raise ValueError("ホスト名に不正な文字が含まれています")
    # hostname が None になるケース（例: 不正な IPv6 形式）を normalize_url に渡す前に排除
    if not parsed.hostname:
        raise ValueError("有効なホスト名が含まれていません")


def normalize_url(parsed: ParseResult) -> str:
    """RFC 3986 §6.2.2.1（Case Normalization）に従いスキームとホスト部を小文字正規化する。

    パス・パラメータ・クエリ・フラグメントは RFC 3986 §3.3–§3.5 の構文定義に従い
    URLエンコードする。§6.2.2.2 の既存 %xx シーケンスのヘックス大文字化は未実施
    （新規エンコード分は quote() が UPPERCASE で出力する）。
    """
    # ParseResultはnamedtupleだが、tuple直接指定でコードの意図を明示する
    # パス・クエリ・フラグメントのXSS文字をURLエンコード（%を安全文字に含め二重エンコード防止）
    # RFC 3986 §3.3 pchar = unreserved / pct-encoded / sub-delims / ":" / "@"
    # XSS防止: ' (single quote) を safe から除外 → %27 にエンコード
    # &はquery/fragmentでパラメータ区切りとして必要なため保持（HTML出力時は呼び出し元でエスケープ）
    # -._~ は Python quote() の _ALWAYS_SAFE に含まれるが、RFC 仕様との対応を明示
    safe_path = quote(parsed.path, safe="/:@!$()*+,;=%-._~")
    # RFC 3986 §3.3 (params は path の一部として扱う)
    safe_params = quote(parsed.params, safe=";=@:!$()*+,/%-._~")
    # RFC 3986 §3.4 query = *( pchar / "/" / "?" )
    safe_query = quote(parsed.query, safe="=&+:@!$()*,;/?%-._~")
    # RFC 3986 §3.5 fragment = *( pchar / "/" / "?" )
    # フラグメントは path/query より "&" と "?" を緩く扱い、unreserved 文字は過剰エンコードしない
    safe_fragment = quote(parsed.fragment, safe=":@!$&()*+,;=/?%-._~")
    # hostname は urlparse が自動小文字化済み。netloc.lower() ではなく
    # hostname + port で再構成し、percent-encoded 文字の大文字16進を保持する
    hostname = parsed.hostname
    if not hostname:
        # _validate_netloc の `not parsed.hostname` で空文字列・None ケースは排除済み
        # ここは直接呼び出し時のセーフガード（通常パスでは到達しない）
        raise ValueError(f"ホスト名の解決に失敗しました（netloc={parsed.netloc!r}）")
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = f"{hostname}:{parsed.port}" if parsed.port is not None else hostname
    return urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            safe_path,
            safe_params,
            safe_query,
            safe_fragment,
        )
    )


def _ensure_website_max_length(url: str) -> str:
    """正規化後URL長の上限チェック（WEBSITE_NORMALIZED_MAX_LENGTH文字）."""
    if len(url) > WEBSITE_NORMALIZED_MAX_LENGTH:
        raise ValueError(
            f"URL補完後の長さが上限{WEBSITE_NORMALIZED_MAX_LENGTH}文字を超過しています（{len(url)}文字）"
        )
    return url


def validate_scheme_less_url(sanitized: str) -> None:
    """スキームなしURLのバリデーション: パーセントエンコード・パス・フラグメント・クエリを検証する。

    Args:
        sanitized: 前処理済み（不可視文字除去・strip済み）のURL文字列

    Raises:
        ValueError: 不正なパーセントエンコード、パス、フラグメント、クエリが含まれる場合
    """
    # errors='strict': 不正なパーセントエンコードをサイレント置換せず明示的エラーとして扱う
    try:
        decoded = unquote(sanitized, errors="strict")
    except UnicodeDecodeError as e:
        raise ValueError(f"URLに不正なパーセントエンコードが含まれています: {e}") from e
    # 不完全な%シーケンス（例: %、%GG）はunquoteがリテラル扱いするため個別チェック
    if _INCOMPLETE_PCT_RE.search(sanitized):
        raise ValueError("URLに不完全なパーセントエンコードが含まれています")
    if "/" in sanitized or "/" in decoded:
        raise ValueError("スキームなしURLにパスは指定できません")
    # %23（#）と %3F（?）のバイパス検出: decoded に含まれる#/?も検出
    if "#" in sanitized or "#" in decoded:
        raise ValueError("スキームなしURLにフラグメントは指定できません")
    if "?" in sanitized or "?" in decoded:
        raise ValueError("スキームなしURLにクエリは指定できません")
