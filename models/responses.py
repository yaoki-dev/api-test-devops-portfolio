"""JSONPlaceholder APIレスポンスモデル

XSS攻撃防止のため、ユーザー生成コンテンツフィールドに
html.escape()サニタイゼーションを適用したPydanticモデル。
（emailはEmailStr RFC準拠バリデーション、websiteはURL形式のためhtml.escape対象外）

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

from pydantic import BaseModel, EmailStr, Field, field_validator

# =============================================================================
# ユーティリティ関数
# =============================================================================


def sanitize_user_content(value: str | None) -> str:
    """ユーザー生成コンテンツをサニタイズ

    XSS攻撃を防ぐため、HTMLエスケープを適用。
    特殊文字（<, >, &, ", '）をHTMLエンティティに変換。

    Args:
        value: サニタイズ対象の文字列（Noneの場合は空文字列を返す）

    Returns:
        サニタイズ済み文字列

    Example:
        >>> sanitize_user_content("<script>alert('XSS')</script>")
        '&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;'

    """
    if not value:
        return ""
    # quote=True: シングルクォート、ダブルクォートもエスケープ
    return html.escape(value, quote=True)


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

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("title", "body")
    @classmethod
    def sanitize_post_content(cls, v: str) -> str:
        """投稿のタイトルと本文をサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
        return sanitize_user_content(v)


class Comment(BaseModel):
    """コメントモデル

    JSONPlaceholder /comments エンドポイントのレスポンス。
    name, bodyフィールドにXSS保護（html.escape）を適用。emailはEmailStr型でRFC準拠バリデーション。

    Attributes:
        id: コメントID（1以上）
        post_id: 親投稿ID（1以上）
        name: コメント投稿者名（サニタイズ済み、最大100文字）
        email: コメント投稿者メールアドレス（EmailStr RFC準拠バリデーション済み、最大100文字）
        body: コメント本文（サニタイズ済み、最大2000文字）

    """

    id: int = Field(..., ge=1, description="コメントID")
    post_id: int = Field(..., ge=1, alias="postId", description="親投稿ID")
    name: str = Field(..., max_length=100, description="コメント投稿者名")
    email: EmailStr = Field(..., max_length=100, description="コメント投稿者メールアドレス")
    body: str = Field(..., max_length=2000, description="コメント本文")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("name", "body")
    @classmethod
    def sanitize_comment_content(cls, v: str) -> str:
        """コメントの名前、本文をサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
        return sanitize_user_content(v)


# =============================================================================
# ユーザー関連モデル
# =============================================================================


class Geo(BaseModel):
    """地理座標モデル

    Addressモデルのネストされたフィールド。
    JSONPlaceholderでは緯度経度が文字列で返される。

    Attributes:
        lat: 緯度（文字列形式、サニタイズ済み）
        lng: 経度（文字列形式、サニタイズ済み）

    """

    lat: str = Field(..., max_length=50, description="緯度")
    lng: str = Field(..., max_length=50, description="経度")

    model_config = {"extra": "forbid"}

    @field_validator("lat", "lng")
    @classmethod
    def sanitize_geo_content(cls, v: str) -> str:
        """地理座標をサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
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

    model_config = {"extra": "forbid"}

    @field_validator("street", "suite", "city", "zipcode")
    @classmethod
    def sanitize_address_content(cls, v: str) -> str:
        """住所情報をサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
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

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("name", "catch_phrase", "bs")
    @classmethod
    def sanitize_company_content(cls, v: str) -> str:
        """企業情報をサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
        return sanitize_user_content(v)


class User(BaseModel):
    """ユーザーモデル

    JSONPlaceholder /users エンドポイントのレスポンス。
    name, username, phoneフィールドにXSS保護（html.escape）を適用。
    websiteフィールドはhtml.escape対象外。危険スキームのみバリデーション。
    emailはEmailStr型でRFC準拠バリデーション。

    Attributes:
        id: ユーザーID（1以上）
        name: ユーザー名（サニタイズ済み、最大100文字）
        username: ユーザー名（英数字、サニタイズ済み、最大50文字）
        email: メールアドレス（EmailStr RFC準拠バリデーション済み、最大100文字）
        address: 住所情報（ネストされたAddressモデル）
        phone: 電話番号（サニタイズ済み、最大50文字）
        website: ウェブサイトURL（最大200文字）
        company: 企業情報（ネストされたCompanyモデル）

    """

    id: int = Field(..., ge=1, description="ユーザーID")
    name: str = Field(..., max_length=100, description="ユーザー名")
    username: str = Field(..., max_length=50, description="ユーザー名（英数字）")
    email: EmailStr = Field(..., max_length=100, description="メールアドレス")
    address: Address = Field(..., description="住所情報")
    phone: str = Field(..., max_length=50, description="電話番号")
    website: str = Field(..., max_length=200, description="ウェブサイトURL")
    company: Company = Field(..., description="企業情報")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("name", "username", "phone")
    @classmethod
    def sanitize_user_fields(cls, v: str) -> str:
        """ユーザー情報フィールドをサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
        return sanitize_user_content(v)

    @field_validator("website")
    @classmethod
    def validate_website_scheme(cls, v: str) -> str:
        """websiteフィールドの危険スキーム検証

        javascript:, data:, vbscript: スキームを拒否する。
        スキームなしドメイン（例: hildegard.org）やhttp/httpsは許可。

        Args:
            v: バリデーション対象のURL文字列

        Returns:
            検証済みURL文字列

        Raises:
            ValueError: 危険なURLスキームが検出された場合

        """
        lower_v = v.strip().lower()
        if lower_v.startswith(("javascript:", "data:", "vbscript:")):
            raise ValueError(f"危険なURLスキームです: {v[:50]}")
        return v


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

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("title")
    @classmethod
    def sanitize_todo_title(cls, v: str) -> str:
        """TODOタイトルをサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
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

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("title")
    @classmethod
    def sanitize_album_title(cls, v: str) -> str:
        """アルバムタイトルをサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
        return sanitize_user_content(v)


class Photo(BaseModel):
    """写真モデル

    JSONPlaceholder /photos エンドポイントのレスポンス。
    titleフィールドにXSS保護を適用。

    Attributes:
        id: 写真ID（1以上）
        album_id: 親アルバムID（1以上）
        title: 写真タイトル（サニタイズ済み、最大200文字）
        url: 写真URL（最大500文字）
        thumbnail_url: サムネイルURL（最大500文字）

    """

    id: int = Field(..., ge=1, description="写真ID")
    album_id: int = Field(..., ge=1, alias="albumId", description="親アルバムID")
    title: str = Field(..., max_length=200, description="写真タイトル")
    url: str = Field(..., max_length=500, description="写真URL")
    thumbnail_url: str = Field(
        ...,
        max_length=500,
        alias="thumbnailUrl",
        description="サムネイルURL",
    )

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("title")
    @classmethod
    def sanitize_photo_title(cls, v: str) -> str:
        """写真タイトルをサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
        return sanitize_user_content(v)

    @field_validator("url", "thumbnail_url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """URLスキームがhttp/httpsであることを検証

        セキュリティのため、javascript:やdata:などの
        潜在的に危険なスキームを拒否。

        Args:
            v: 検証対象のURL文字列

        Returns:
            検証済みURL文字列

        Raises:
            ValueError: URLがhttp/httpsで始まらない場合

        """
        # case-insensitive check (JAVASCRIPT: などのバイパス防止)
        if not v.lower().startswith(("http://", "https://")):
            raise ValueError(f"URL must start with http:// or https://, got: {v[:50]}...")
        return v


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
