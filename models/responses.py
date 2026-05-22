"""JSONPlaceholder APIレスポンスモデル

XSS攻撃防止のため、ユーザー生成コンテンツフィールドに
html.escape()サニタイゼーションを適用したPydanticモデル。
（email・websiteはhtml.escape対象外: emailはEmailStr RFC準拠バリデーション、
websiteはURL形式のためhtmlコンテキスト出力時は呼び出し元でエスケープ）
モデル値はAPIレスポンスの意味論を保つ。HTML等への出力時のエスケープ責務は呼び出し元が持つ。

実務推奨パターン:
1. Defense in Depth: 型検証 + サニタイゼーション + 長さ制限
2. Fail-Safe: バリデーションエラーは明確なエラーメッセージで
3. 最小権限: 必要最小限のフィールドのみ公開

学習目標:
- Pydantic field_validatorによるカスタムバリデーション
- XSS保護のベストプラクティス
- 型安全なAPIレスポンス処理
"""

import html
import re
import unicodedata
from functools import lru_cache
from typing import Annotated
from urllib.parse import ParseResult, quote, unquote, urlparse, urlunparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# RFC 3986 準拠のスキーム検出パターン（scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." ) ":"）
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
_INCOMPLETE_PCT_RE: re.Pattern[str] = re.compile(r"%(?![0-9a-f]{2})", re.IGNORECASE)
_ASCII_WHITESPACE_RE: re.Pattern[str] = re.compile(r"[ \t\n\r\f\v]")
_VARIATION_SELECTORS: frozenset[str] = frozenset(
    {chr(codepoint) for codepoint in range(0xFE00, 0xFE10)}
    | {chr(codepoint) for codepoint in range(0xE0100, 0xE01F0)}
)
_WEBSITE_NORMALIZED_MAX_LENGTH: int = 2048
_INVISIBLE_CATEGORIES = frozenset({"Cf", "Cc", "Zs", "Zl", "Zp"})
# Cs（孤立サロゲート）を _INVISIBLE_CATEGORIES と合算した除去セット（1回目パスで使用）
_STRIP_CATEGORIES = _INVISIBLE_CATEGORIES | frozenset({"Cs"})


@lru_cache(maxsize=2048)
def _unicode_category(c: str) -> str:
    """Unicodeカテゴリ取得をキャッシュする。"""
    return unicodedata.category(c)


def _is_strippable_char(c: str, categories: frozenset[str]) -> bool:
    """不可視文字として除去すべき文字か判定する。

    Variation Selectors は Mn に分類されるが、結合文字（例: U+0301）は保持し、
    NFD由来のホスト名をサイレントに別文字列へ改変しない。
    """
    return c != " " and (_unicode_category(c) in categories or c in _VARIATION_SELECTORS)


def _strip_invisible_chars(v: str) -> str:
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


# =============================================================================
# ユーティリティ関数
# =============================================================================


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
    # hostname が None になるケース（例: 不正な IPv6 形式）を _normalize_url に渡す前に排除
    if not parsed.hostname:
        raise ValueError("有効なホスト名が含まれていません")


def _normalize_url(parsed: ParseResult) -> str:
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
    """正規化後URL長の上限チェック（_WEBSITE_NORMALIZED_MAX_LENGTH文字）."""
    if len(url) > _WEBSITE_NORMALIZED_MAX_LENGTH:
        raise ValueError(
            f"URL補完後の長さが上限{_WEBSITE_NORMALIZED_MAX_LENGTH}文字を超過しています（{len(url)}文字）"
        )
    return url


def _validate_scheme_less_url(sanitized: str) -> None:
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


# =============================================================================
# 投稿関連モデル
# =============================================================================


class Post(BaseModel):
    """ブログ投稿モデル

    JSONPlaceholder /posts エンドポイントのレスポンス。
    title, bodyフィールドにXSS保護を適用。

    Attributes:
        id: 投稿ID（1以上）
        user_id: 投稿者ユーザーID（1以上）
        title: 投稿タイトル（サニタイズ済み、最大200文字）
        body: 投稿本文（サニタイズ済み、最大5000文字）

    """

    id: int = Field(..., ge=1, description="投稿ID")
    user_id: int = Field(..., ge=1, alias="userId", description="投稿者ユーザーID")
    title: str = Field(..., max_length=200, description="投稿タイトル")
    body: str = Field(..., max_length=5000, description="投稿本文")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")

    @field_validator("title", "body")
    @classmethod
    def sanitize_post_content(cls, v: str) -> str:
        """投稿のタイトルと本文をサニタイズする。"""
        return sanitize_user_content(v)


class Comment(BaseModel):
    """コメントモデル

    JSONPlaceholder /comments エンドポイントのレスポンス。
    name, bodyフィールドにXSS保護（html.escape）を適用。
    emailはEmailStr型でRFC構文チェックのみ（html.escape非適用）。

    Attributes:
        id: コメントID（1以上）
        post_id: 親投稿ID（1以上）
        name: コメント投稿者名（サニタイズ済み、最大100文字）
        email: コメント投稿者メールアドレス
            （RFC構文チェック済み・DNS検証なし、最大100文字。
            html.escape 非適用 — HTML出力時は呼び出し元で html.escape(email) 必須）
        body: コメント本文（サニタイズ済み、最大2000文字）

    """

    id: int = Field(..., ge=1, description="コメントID")
    post_id: int = Field(..., ge=1, alias="postId", description="親投稿ID")
    name: str = Field(..., max_length=100, description="コメント投稿者名")
    email: Annotated[
        EmailStr,
        Field(
            max_length=100,
            description="コメント投稿者メールアドレス（RFC構文チェック済み、DNS検証なし）",
        ),
    ]
    body: str = Field(..., max_length=2000, description="コメント本文")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")

    @field_validator("name", "body")
    @classmethod
    def sanitize_comment_content(cls, v: str) -> str:
        """コメントの名前、本文をサニタイズする。"""
        return sanitize_user_content(v)


# =============================================================================
# ユーザー関連モデル
# =============================================================================


class Geo(BaseModel):
    """地理座標モデル

    Addressモデルのネストされたフィールド。
    JSONPlaceholderでは緯度経度が文字列で返される。

    Attributes:
        lat: 緯度（文字列形式、サニタイズ済み、最大50文字）
        lng: 経度（文字列形式、サニタイズ済み、最大50文字）

    Note:
        lat/lngは数値座標文字列（例: "-40.7128"）のため、
        URLスキームバイパス防止を目的とする _strip_invisible_chars は非適用。
        XSSはhtml.escape（sanitize_user_content経由）で対処。

    Raises:
        ValueError: lat/lng が str 型でない場合

    """

    lat: str = Field(..., max_length=50, description="緯度")
    lng: str = Field(..., max_length=50, description="経度")

    model_config = ConfigDict(extra="forbid")

    @field_validator("lat", "lng")
    @classmethod
    def sanitize_geo_content(cls, v: str) -> str:
        """地理座標をサニタイズする。"""
        return sanitize_user_content(v)


class Address(BaseModel):
    """住所モデル

    Userモデルのネストされたフィールド。
    street, suite, city, zipcodeフィールドにXSS保護を適用。

    Attributes:
        street: 通り名（サニタイズ済み、最大200文字）
        suite: 部屋番号/建物名（サニタイズ済み、最大100文字）
        city: 市区町村（サニタイズ済み、最大100文字）
        zipcode: 郵便番号（サニタイズ済み、最大20文字）
        geo: 地理座標（ネストされたGeoモデル）

    """

    street: str = Field(..., max_length=200, description="通り名")
    suite: str = Field(..., max_length=100, description="部屋番号/建物名")
    city: str = Field(..., max_length=100, description="市区町村")
    zipcode: str = Field(..., max_length=20, description="郵便番号")
    geo: Geo = Field(..., description="地理座標")

    model_config = ConfigDict(extra="forbid")

    @field_validator("street", "suite", "city", "zipcode")
    @classmethod
    def sanitize_address_content(cls, v: str) -> str:
        """住所情報をサニタイズする。"""
        return sanitize_user_content(v)


class Company(BaseModel):
    """企業情報モデル

    Userモデルのネストされたフィールド。
    name, catch_phrase, bsフィールドにXSS保護を適用。

    Attributes:
        name: 企業名（サニタイズ済み、最大100文字）
        catch_phrase: キャッチフレーズ（サニタイズ済み、最大200文字）
        bs: ビジネススローガン（サニタイズ済み、最大200文字）

    """

    name: str = Field(..., max_length=100, description="企業名")
    catch_phrase: str = Field(
        ...,
        max_length=200,
        alias="catchPhrase",
        description="キャッチフレーズ",
    )
    bs: str = Field(..., max_length=200, description="ビジネススローガン")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")

    @field_validator("name", "catch_phrase", "bs")
    @classmethod
    def sanitize_company_content(cls, v: str) -> str:
        """企業情報をサニタイズする。"""
        return sanitize_user_content(v)


class User(BaseModel):
    """ユーザーモデル

    JSONPlaceholder /users エンドポイントのレスポンス。
    name, username, phoneフィールドにXSS保護（html.escape）を適用。
    websiteフィールドはhtml.escape対象外。不可視文字除去（_strip_invisible_chars）・allowlist方式スキームバリデーション適用。
    emailはEmailStr型でRFC構文チェック（DNS検証なし）。

    Attributes:
        id: ユーザーID（1以上）
        name: ユーザー名（サニタイズ済み、最大100文字）
        username: ユーザー名（英数字、サニタイズ済み、最大50文字）
        email: メールアドレス（EmailStr RFC構文チェック済み・DNS検証なし、最大100文字。
            html.escape 非適用。HTML出力時は呼び出し元で html.escape(email) 必須）
        address: 住所情報（ネストされたAddressモデル）
        phone: 電話番号（サニタイズ済み、最大50文字）
        website: ウェブサイトURL（制御文字除去・前後空白除去・http/httpsスキーム検証済み、
            入力時最大2048文字・正規化後2048文字以内）
        company: 企業情報（ネストされたCompanyモデル）

    """

    id: int = Field(..., ge=1, description="ユーザーID")
    name: str = Field(..., max_length=100, description="ユーザー名")
    username: str = Field(..., max_length=50, description="ユーザー名（英数字）")
    email: Annotated[
        EmailStr,
        Field(max_length=100, description="メールアドレス（RFC構文チェック済み、DNS検証なし）"),
    ]
    address: Address = Field(..., description="住所情報")
    phone: str = Field(..., max_length=50, description="電話番号")
    website: str = Field(
        ...,
        min_length=1,
        max_length=2048,
        description="ウェブサイトURL（入力時最大2048文字・正規化後2048文字以内、制御文字除去・前後空白除去・http/httpsスキーム検証済み）",
    )
    company: Company = Field(..., description="企業情報")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")

    @field_validator("name", "username", "phone")
    @classmethod
    def sanitize_user_fields(cls, v: str) -> str:
        """ユーザー情報フィールド（name, username, phone）をサニタイズする。"""
        return sanitize_user_content(v)

    @field_validator("website", mode="before")
    @classmethod
    def validate_website_scheme(cls, v: object) -> str:
        """websiteフィールドのURLスキーム検証（allowlist方式）

        RFC 3986準拠のスキーム検出で、http://とhttps://のみ許可する。
        スキームなしドメイン（例: hildegard.org）はhttps://を自動補完する。
        domain:portパターン（例: example.com:8080）はスキームが明示されていない
        場合は拒否する（http://example.com:8080 は許可）。
        javascript:, data:, ftp:, file: 等の危険スキームおよびプロトコル相対URL（//）は全て拒否。
        http/httpsスキームおよびホスト部はRFC 3986 Section 6.2.2.1に従い小文字に正規化。

        Args:
            v: バリデーション対象の値（mode="before"のため任意型。
               str以外の場合はValueErrorを送出）

        Returns:
            バリデーション済みURL文字列（スキームなしの場合はhttps://を補完、
            制御文字除去・前後空白除去・RFC 3986 §6.2.2.1正規化済み、
            最大2048文字以内）

        Raises:
            ValueError: 以下のいずれかの場合:
                - 入力が文字列でない
                - 制御文字除去後にURLが空
                - パーセントエンコードされた制御文字（%00-%1f および %7f(DEL)）を含む
                - プロトコル相対URL（//始まり）
                - http/https以外の危険スキーム
                - 有効なホスト名なし
                - ホスト名にHTMLメタ文字（<, >, ", ', &）を含む
                - ポートが無効（整数値でない）
                - userinfoを含む（例: https://user@host — RFC 3986 バイパス防止）
                - スキームなしURLにパス（/）が含まれる（ドメインのみ許可）
                - スキームなしURLにポートが含まれる
                  （例: 192.168.1.1:8080 — IPアドレス:portはスキームなしとして検出。
                  ドメイン名:port（例: example.com:8080）は_SCHEME_REがスキームとして
                  構文マッチするため「危険なURLスキーム」として先に拒否される）
                - スキームなしURLに不正なパーセントエンコードが含まれる
                  （例: example.com%80 — UTF-8として不正なバイト列）
                - 不完全なパーセントエンコードが含まれる（スキーム有無を問わず）
                  （例: % 単独、%GG 等の不正な16進シーケンス）

        Note:
            websiteフィールドの値をHTMLコンテキストへ出力する際は、
            呼び出し元で html.escape() を適用すること（URLはhtml.escape対象外のため）。

        """
        if not isinstance(v, str):
            raise ValueError(f"文字列が必要です（受け取った型: {type(v).__name__}）")

        sanitized = _strip_invisible_chars(v).strip()
        # min_length=1 は真の空文字列を、ここでは制御文字のみの文字列を捕捉（2段階チェック）
        if not sanitized:
            raise ValueError("websiteが空になりました（制御文字除去後）")
        # CRLF injection防止: パーセントエンコードされた制御文字を拒否（%00-%1f全範囲）
        # _strip_invisible_chars は実際の制御文字を除去するが、
        # %0d%0a 等のエンコード形式はバイパスする
        sanitized_lower = sanitized.lower()
        if _PERCENT_CTRL_RE.search(sanitized_lower):
            raise ValueError("URLにパーセントエンコードされた制御文字が含まれています")
        # 不完全な%シーケンス検出（全ブランチ共通 — http/httpsおよびスキームなし両対応）
        # _validate_scheme_less_url でも同様にチェックするが多層防御として二重確認
        if _INCOMPLETE_PCT_RE.search(sanitized):
            raise ValueError("URLに不完全なパーセントエンコードが含まれています")
        # プロトコル相対URLを明示的に拒否（攻撃面削減）
        if sanitized_lower.startswith("//"):
            raise ValueError("プロトコル相対URLは許可されていません")
        # urlparseは各分岐で1回のみ呼び出す
        # （http/httpsブランチと補完ブランチで入力が異なるため共通化不可）
        if sanitized_lower.startswith(("http://", "https://")):
            # _validate_netloc / _normalize_url の ValueError はそのまま伝播
            # NOTE: sanitized（元の大文字混在）を使用 — スキーム小文字化は _normalize_url に委譲
            # （sanitized_lower は path/query の大文字を失うため使用不可）
            parsed = urlparse(sanitized)
            _validate_netloc(parsed)
            return _ensure_website_max_length(_normalize_url(parsed))
        # RFC 3986スキーム検出: http/https以外のスキームが存在すれば拒否
        # is_domain_portロジックを削除: domain:portはスキームなし扱いのため
        # http(s)://を明示しない限り拒否（例: example.com:8080 → ValueError）
        if _SCHEME_RE.match(sanitized_lower):
            raise ValueError("危険なURLスキームが検出されました")
        # スキームなし → https:// を補完して検証
        # _validate_netloc / _normalize_url の ValueError はそのまま伝播
        # 設計意図: スキームなしURLはドメインのみ許可（パス付きURLは拒否）
        # パーセントエンコード済み %2F によるバイパスも防止
        _validate_scheme_less_url(sanitized)
        parsed = urlparse("https://" + sanitized)
        _validate_netloc(parsed)
        # スキームなし補完後のポートチェック:
        # IPアドレス:port形式（例: 192.168.1.1:8080）がここに到達する
        # （ドメイン:port形式（例: example.com:8080）は _SCHEME_RE にマッチし
        #  「危険なURLスキーム」として上流で拒否されるため、このチェックに到達しない）
        if parsed.port is not None:
            raise ValueError(
                "スキームなしURLにポートは指定できません（http(s)://を明示してください）"
            )
        return _ensure_website_max_length(_normalize_url(parsed))


# =============================================================================
# TODO・アルバム・写真モデル
# =============================================================================


class Todo(BaseModel):
    """TODOモデル

    JSONPlaceholder /todos エンドポイントのレスポンス。
    titleフィールドにXSS保護を適用。

    Attributes:
        id: TODO ID（1以上）
        user_id: 所有者ユーザーID（1以上）
        title: TODOタイトル（サニタイズ済み、最大200文字）
        completed: 完了フラグ

    """

    id: int = Field(..., ge=1, description="TODO ID")
    user_id: int = Field(..., ge=1, alias="userId", description="所有者ユーザーID")
    title: str = Field(..., max_length=200, description="TODOタイトル")
    completed: bool = Field(..., description="完了フラグ")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")

    @field_validator("title")
    @classmethod
    def sanitize_todo_title(cls, v: str) -> str:
        """TODOタイトルをサニタイズする。"""
        return sanitize_user_content(v)


class Album(BaseModel):
    """アルバムモデル

    JSONPlaceholder /albums エンドポイントのレスポンス。
    titleフィールドにXSS保護を適用。

    Attributes:
        id: アルバムID（1以上）
        user_id: 所有者ユーザーID（1以上）
        title: アルバムタイトル（サニタイズ済み、最大200文字）

    """

    id: int = Field(..., ge=1, description="アルバムID")
    user_id: int = Field(..., ge=1, alias="userId", description="所有者ユーザーID")
    title: str = Field(..., max_length=200, description="アルバムタイトル")

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")

    @field_validator("title")
    @classmethod
    def sanitize_album_title(cls, v: str) -> str:
        """アルバムタイトルをサニタイズする。"""
        return sanitize_user_content(v)


class Photo(BaseModel):
    """写真モデル

    JSONPlaceholder /photos エンドポイントのレスポンス。
    titleフィールドにXSS保護を適用。url・thumbnail_urlはhttp/httpsスキーム必須、
    不可視文字除去・RFC 3986 §6.2.2.1正規化（スキーム・ホスト小文字化）を適用。

    Attributes:
        id: 写真ID（1以上）
        album_id: 親アルバムID（1以上）
        title: 写真タイトル（サニタイズ済み、最大200文字）
        url: 写真URL（http/https必須・不可視文字除去・userinfo禁止・RFC 3986正規化済み、
            最大2048文字）
        thumbnail_url: サムネイルURL（http/https必須・不可視文字除去・userinfo禁止・
            RFC 3986正規化済み、最大2048文字）

    """

    id: int = Field(..., ge=1, description="写真ID")
    album_id: int = Field(..., ge=1, alias="albumId", description="親アルバムID")
    title: str = Field(..., max_length=200, description="写真タイトル")
    url: str = Field(..., max_length=2048, description="写真URL")
    thumbnail_url: str = Field(
        ...,
        max_length=2048,
        alias="thumbnailUrl",
        description="サムネイルURL",
    )

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True, extra="forbid")

    @field_validator("title")
    @classmethod
    def sanitize_photo_title(cls, v: str) -> str:
        """写真タイトルをサニタイズする。"""
        return sanitize_user_content(v)

    # mode 未指定（デフォルト after）: Pydantic が str 型強制後にバリデーション実行
    # validate_website_scheme は mode="before" だが、Photo URL は外部API由来のため
    # str 型が保証されており mode="after" で十分
    @field_validator("url", "thumbnail_url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """URLスキームがhttp/httpsであることを検証

        セキュリティのため、javascript:やdata:などの
        潜在的に危険なスキームを拒否。
        不可視文字（Cf/Cs/Cc/Zs/Zl/Zpカテゴリ）と Variation Selector を除去してから
        スキーム検証を行う。Mn 文字のうち結合文字は保持し、NFD由来のホスト名を
        サイレントに別文字列へ改変しない。

        Args:
            v: 検証対象のURL文字列

        Returns:
            検証済みURL文字列（制御文字除去・前後空白除去・RFC 3986正規化済み、
            最大2048文字以内）

        Raises:
            ValueError: 以下のいずれかの場合:
                - 制御文字除去後にURLが空
                - パーセントエンコードされた制御文字（%00-%1f および %7f(DEL)）を含む
                - http/https以外のスキーム（またはスキームなし）
                - 有効なホスト名なし
                - ホスト名にHTMLメタ文字（<, >, ", ', &）を含む
                - ポートが無効（整数値でない）
                - userinfoを含む（例: https://user@host — RFC 3986 バイパス防止）
                - 正規化後URL長が2048文字を超える

        Note:
            User.validate_website_scheme と異なり、スキームなしURLへの自動補完は行わない。
            外部API由来URLのためスキームは必須。
            HTMLコンテキストへ出力する場合は、呼び出し元で html.escape() による
            エスケープが必須。

        """
        sanitized = _strip_invisible_chars(v).strip()
        if not sanitized:
            raise ValueError("URLが空になりました（制御文字除去後）")
        # CRLF injection防止: パーセントエンコードされた制御文字を拒否（%00-%1f全範囲）
        sanitized_lower = sanitized.lower()
        if _PERCENT_CTRL_RE.search(sanitized_lower):
            raise ValueError("URLにパーセントエンコードされた制御文字が含まれています")
        # 不完全な%シーケンス（%、%G、%GGなど）はunquoteがリテラル扱いするため個別チェック
        if _INCOMPLETE_PCT_RE.search(sanitized):
            raise ValueError("URLに不完全なパーセントエンコードが含まれています")
        if not sanitized_lower.startswith(("http://", "https://")):
            raise ValueError("URLはhttp://またはhttps://で始まる必要があります")
        # _validate_netloc / _normalize_url の ValueError はそのまま伝播
        parsed = urlparse(sanitized)
        _validate_netloc(parsed)
        return _ensure_website_max_length(_normalize_url(parsed))


# =============================================================================
# 学習ポイント:
#
# 1. XSS保護の実務パターン:
#    - Defense in Depth: 型検証 + サニタイゼーション + 長さ制限
#    - html.escape(quote=True): シングル/ダブルクォートもエスケープ
#    - 明確なエラーメッセージで問題を早期発見
#
# 2. Pydantic field_validator活用:
#    - @classmethod デコレータで型安全なバリデーション
#    - 複数フィールドに同一バリデータを適用可能
#    - カスタムエラーメッセージで開発者体験向上
#
# 3. 日本語ドキュメント:
#    - docstring: 機能の説明、引数、戻り値を明確に
#    - Field description: フィールドの意味を簡潔に
#    - コメント: 実装の意図や注意点を記載
#
# 4. 実務推奨設計:
#    - ネストモデル（Company）で複雑なJSONに対応
#    - alias設定（userId → user_id）でPythonic命名
#    - 長さ制限で異常データからシステムを保護
# =============================================================================
