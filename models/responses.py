"""JSONPlaceholder APIレスポンスモデル

XSS攻撃防止のため、ユーザー生成コンテンツフィールドに
html.escape()サニタイゼーションを適用したPydanticモデル。
（email・websiteはhtml.escape対象外: emailはEmailStr RFC準拠バリデーション、
websiteはURL形式のためhtmlコンテキスト出力時は呼び出し元でエスケープ）
モデル値はAPIレスポンスの意味論を保つ。HTML等への出力時のエスケープ責務は呼び出し元が持つ。
"""

from typing import Annotated
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from . import sanitization as _sanitization
from .sanitization import (
    normalize_url,
    sanitize_user_content,
    strip_invisible_chars,
    validate_scheme_less_url,
)

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
        URLスキームバイパス防止を目的とする strip_invisible_chars は非適用。
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
    websiteフィールドはhtml.escape対象外。不可視文字除去（strip_invisible_chars）・allowlist方式スキームバリデーション適用。
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
            raise ValueError(f"String required (received type: {type(v).__name__})")

        sanitized = strip_invisible_chars(v).strip()
        # min_length=1 は真の空文字列を、ここでは制御文字のみの文字列を捕捉（2段階チェック）
        if not sanitized:
            raise ValueError("Website became empty after control character removal")
        # CRLF injection防止: パーセントエンコードされた制御文字を拒否（%00-%1f全範囲）
        # strip_invisible_chars は実際の制御文字を除去するが、
        # %0d%0a 等のエンコード形式はバイパスする
        sanitized_lower = sanitized.lower()
        if _sanitization._PERCENT_CTRL_RE.search(sanitized_lower):
            raise ValueError("URL contains percent-encoded control characters")
        # 不完全な%シーケンス検出（全ブランチ共通 — http/httpsおよびスキームなし両対応）
        # validate_scheme_less_url でも同様にチェックするが多層防御として二重確認
        if _sanitization._INCOMPLETE_PCT_RE.search(sanitized):
            raise ValueError("URL contains incomplete percent-encoding")
        # プロトコル相対URLを明示的に拒否（攻撃面削減）
        if sanitized_lower.startswith("//"):
            raise ValueError("Protocol-relative URLs are not allowed")
        # urlparseは各分岐で1回のみ呼び出す
        # （http/httpsブランチと補完ブランチで入力が異なるため共通化不可）
        if sanitized_lower.startswith(("http://", "https://")):
            # _validate_netloc / normalize_url の ValueError はそのまま伝播
            # NOTE: sanitized（元の大文字混在）を使用 — スキーム小文字化は normalize_url に委譲
            # （sanitized_lower は path/query の大文字を失うため使用不可）
            parsed = urlparse(sanitized)
            _sanitization._validate_netloc(parsed)
            return _sanitization._ensure_website_max_length(normalize_url(parsed))
        # RFC 3986スキーム検出: http/https以外のスキームが存在すれば拒否
        # is_domain_portロジックを削除: domain:portはスキームなし扱いのため
        # http(s)://を明示しない限り拒否（例: example.com:8080 → ValueError）
        if _sanitization._SCHEME_RE.match(sanitized_lower):
            raise ValueError("Dangerous URL scheme detected")
        # スキームなし → https:// を補完して検証
        # _validate_netloc / normalize_url の ValueError はそのまま伝播
        # 設計意図: スキームなしURLはドメインのみ許可（パス付きURLは拒否）
        # パーセントエンコード済み %2F によるバイパスも防止
        validate_scheme_less_url(sanitized)
        parsed = urlparse("https://" + sanitized)
        _sanitization._validate_netloc(parsed)
        # スキームなし補完後のポートチェック:
        # IPアドレス:port形式（例: 192.168.1.1:8080）がここに到達する
        # （ドメイン:port形式（例: example.com:8080）は _SCHEME_RE にマッチし
        #  「危険なURLスキーム」として上流で拒否されるため、このチェックに到達しない）
        if parsed.port is not None:
            raise ValueError(
                "Scheme-less URL cannot contain a port (explicitly use http:// or https://)"
            )
        return _sanitization._ensure_website_max_length(normalize_url(parsed))


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
    # validate_by_name/alias=True で alias 経由入力も自動的に同一バリデータを通過
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
        sanitized = strip_invisible_chars(v).strip()
        if not sanitized:
            raise ValueError("URL became empty after control character removal")
        # CRLF injection防止: パーセントエンコードされた制御文字を拒否（%00-%1f全範囲）
        sanitized_lower = sanitized.lower()
        if _sanitization._PERCENT_CTRL_RE.search(sanitized_lower):
            raise ValueError("URL contains percent-encoded control characters")
        # 不完全な%シーケンス（%、%G、%GGなど）はunquoteがリテラル扱いするため個別チェック
        if _sanitization._INCOMPLETE_PCT_RE.search(sanitized):
            raise ValueError("URL contains incomplete percent-encoding")
        if not sanitized_lower.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        # _validate_netloc / normalize_url の ValueError はそのまま伝播
        parsed = urlparse(sanitized)
        _sanitization._validate_netloc(parsed)
        return _sanitization._ensure_website_max_length(normalize_url(parsed))
