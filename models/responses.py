"""JSONPlaceholder APIレスポンスモデル

XSS攻撃防止のため、ユーザー生成コンテンツフィールドに
html.escape()サニタイゼーションを適用したPydanticモデル。
（email・websiteはhtml.escape対象外: emailはEmailStr RFC準拠バリデーション、
websiteはURL形式のためhtmlコンテキスト出力時は呼び出し元でエスケープ）

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
from urllib.parse import ParseResult, quote, urlparse, urlunparse

from pydantic import BaseModel, EmailStr, Field, field_validator

# RFC 3986 準拠のスキーム検出パターン（scheme = ALPHA *( ALPHA / DIGIT / "+" / "-" / "." ) ":"）
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
_INVISIBLE_CATEGORIES = frozenset({"Cf", "Cc", "Mn", "Zs", "Zl", "Zp"})


def _strip_invisible_chars(v: str) -> str:
    """不可視文字・制御文字・Unicode空白をURL文字列から除去

    URLスキームバイパス防止のため、以下のUnicodeカテゴリを除去:

    前処理（_INVISIBLE_CATEGORIESとは別ロジックで先行除去）:
    - Cs: Surrogate（孤立サロゲート U+D800-U+DFFF）— 有効なUnicode文字列に
          含まれるべきでないためnormalize()前に除去（データ整合性）

    _INVISIBLE_CATEGORIESによる除去:
    - Cf: Format文字（Bidi制御, ゼロ幅文字, Word Joiner等）
    - Cc: 制御文字（C0/C1制御文字, DEL等）
    - Mn: 非スペーシングマーク（Mark, Nonspacing）
          （主目的: Variation Selectors U+FE00-U+FE0F によるスキームバイパス防止、
          副次的に結合文字 U+0300等もMnカテゴリへの帰属により除去）
    - Zs: Unicode空白（NBSP, Ogham Space, 全角空白等。U+0020通常スペースは
          Zsカテゴリに属するが、c == " " の特例条件で保持）
          ※ NFKC正規化前にも除去（NFKC後にU+0020へ変換される副作用を防止）
    - Zl: 行区切り（U+2028 Line Separator）
    - Zp: 段落区切り（U+2029 Paragraph Separator）

    Python に同梱の Unicode バージョン内の新規文字に自動対応する。
    （Unicode バージョン自体の更新には Python バージョンアップが必要）
    """
    # Pydantic バリデータ経由で呼ばれるため、フィールド名は Pydantic が付加する
    if not isinstance(v, str):
        raise ValueError(f"文字列が必要です。受け取った型: {type(v).__name__}")
    # Cs（孤立サロゲート U+D800-U+DFFF）はデータ整合性のため先に除去する
    # （有効なUnicode文字列に孤立サロゲートを含めるべきでない）。
    without_surrogates = "".join(c for c in v if unicodedata.category(c) != "Cs")
    # NFKC前に不可視文字を除去（NBSP等のZs文字がNFKC後にU+0020へ変換される副作用防止）
    # 全角英字（Ll/Lu等）はNFKC前に残し、NFKC正規化でASCIIに変換される
    pre_filtered = "".join(
        c
        for c in without_surrogates
        if (unicodedata.category(c) not in _INVISIBLE_CATEGORIES) or (c == " ")
    )
    normalized = unicodedata.normalize("NFKC", pre_filtered)
    # NFKC後も二重チェック（NFKC変換が新たな不可視文字を生成するケースに備える）
    return "".join(
        c
        for c in normalized
        if (unicodedata.category(c) not in _INVISIBLE_CATEGORIES) or (c == " ")
    )


# =============================================================================
# ユーティリティ関数
# =============================================================================


def sanitize_user_content(value: str) -> str:
    """ユーザー生成コンテンツをサニタイズ

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
        v0.x では str | None を受理していたが、現在は str のみ受理する。
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
    """netloc の存在確認と userinfo 禁止チェックを共通化する."""
    if not parsed.netloc:
        raise ValueError("有効なホスト名が含まれていません")
    # 多層防御: parsed.username/password に加え netloc の "@" リテラルも検査
    # （urlparse が特定のエンコード済み入力で username=None を返すエッジケース対策）
    if "@" in parsed.netloc or parsed.username is not None or parsed.password is not None:
        raise ValueError("URLにuserinfo（ユーザー名/パスワード）は指定できません")


def _normalize_url(parsed: ParseResult) -> str:
    """RFC 3986 §6.2.2.1/6.2.2.2: スキームとホスト部を小文字正規化し、パス・クエリをURLエンコードする."""  # noqa: E501
    # ParseResultはnamedtupleだが、tuple直接指定でコードの意図を明示する
    # パス・クエリ・フラグメントのXSS文字をURLエンコード（%を安全文字に含め二重エンコード防止）
    # RFC 3986 §3.3 pchar = unreserved / pct-encoded / sub-delims / ":" / "@"
    safe_path = quote(parsed.path, safe="/:@!$&()*+,;=%")
    # RFC 3986 §3.3 (params は path の一部として扱う)
    safe_params = quote(parsed.params, safe=";=@:!$&()*+,/%")
    # RFC 3986 §3.4 query = *( pchar / "/" / "?" )
    safe_query = quote(parsed.query, safe="=&+:@!$()*,;/%")
    # RFC 3986 §3.5 fragment = *( pchar / "/" / "?" )
    safe_fragment = quote(parsed.fragment, safe=":@!$&()*+,;=/?%-._~")
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            safe_path,
            safe_params,
            safe_query,
            safe_fragment,
        )
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
    email: EmailStr = Field(
        ...,
        max_length=100,
        description="コメント投稿者メールアドレス（RFC構文チェック済み、DNS検証なし）",
    )
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
    websiteフィールドはhtml.escape対象外。不可視文字除去（_strip_invisible_chars）・allowlist方式スキームバリデーション適用。
    emailはEmailStr型でRFC構文チェック（DNS検証なし）。

    Attributes:
        id: ユーザーID（1以上）
        name: ユーザー名（サニタイズ済み、最大100文字）
        username: ユーザー名（英数字、サニタイズ済み、最大50文字）
        email: メールアドレス（EmailStr RFC構文チェック済み・DNS検証なし、最大100文字）
        address: 住所情報（ネストされたAddressモデル）
        phone: 電話番号（サニタイズ済み、最大50文字）
        website: ウェブサイトURL（制御文字除去・前後空白除去・http/httpsスキーム検証済み、
            最大200文字）
        company: 企業情報（ネストされたCompanyモデル）

    """

    id: int = Field(..., ge=1, description="ユーザーID")
    name: str = Field(..., max_length=100, description="ユーザー名")
    username: str = Field(..., max_length=50, description="ユーザー名（英数字）")
    email: EmailStr = Field(
        ...,
        max_length=100,
        description="メールアドレス（RFC構文チェック済み、DNS検証なし）",
    )
    address: Address = Field(..., description="住所情報")
    phone: str = Field(..., max_length=50, description="電話番号")
    website: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="ウェブサイトURL（制御文字除去・前後空白除去済み）",
    )
    company: Company = Field(..., description="企業情報")

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("name", "username", "phone")
    @classmethod
    def sanitize_user_fields(cls, v: str) -> str:
        """ユーザー情報フィールド（name, username, phone）をサニタイズ

        XSS攻撃を防ぐため、ユーザー生成コンテンツから
        危険なHTML特殊文字をエスケープ。

        Args:
            v: サニタイズ対象の文字列

        Returns:
            サニタイズ済み文字列

        """
        return sanitize_user_content(v)

    @field_validator("website", mode="before")
    @classmethod
    def validate_website_scheme(cls, v: str) -> str:
        """websiteフィールドのURLスキーム検証（allowlist方式）

        RFC 3986準拠のスキーム検出で、http://とhttps://のみ許可する。
        スキームなしドメイン（例: hildegard.org）はhttps://を自動補完する。
        domain:portパターン（例: example.com:8080）はスキームが明示されていない
        場合は拒否する（http://example.com:8080 は許可）。
        javascript:, data:, ftp:, file: 等の危険スキームおよびプロトコル相対URL（//）は全て拒否。
        http/httpsスキームおよびホスト部はRFC 3986 Section 6.2.2.1に従い小文字に正規化。

        Args:
            v: バリデーション対象のURL文字列

        Returns:
            バリデーション済みURL文字列（スキームなしの場合はhttps://を補完、
            制御文字除去・前後空白除去済み）

        Raises:
            ValueError: 以下のいずれかの場合:
                - 入力が文字列でない
                - 制御文字除去後にURLが空
                - プロトコル相対URL（//始まり）
                - http/https以外の危険スキーム
                - 有効なホスト名なし
                - userinfoを含む（例: https://user@host — RFC 3986 バイパス防止）
                - スキームなしURLにポートが含まれる（例: example.com:8080）

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
        # プロトコル相対URLを明示的に拒否（攻撃面削減）
        if sanitized.startswith("//"):
            raise ValueError("プロトコル相対URLは許可されていません")
        # RFC 3986 §6.2.2.1: スキーム・ホストのみ小文字正規化対象。パス部は大文字小文字を保持する
        # ため、スキームチェックには lower() 済みの文字列を使いつつ、urlparse にはオリジナルを渡す
        sanitized_lower = sanitized.lower()
        # urlparseは各分岐で1回のみ呼び出す
        # （http/httpsブランチと補完ブランチで入力が異なるため共通化不可）
        if sanitized_lower.startswith(("http://", "https://")):
            # _validate_netloc / _normalize_url の ValueError はそのまま伝播
            parsed = urlparse(sanitized)
            _validate_netloc(parsed)
            return _normalize_url(parsed)
        # RFC 3986スキーム検出: http/https以外のスキームが存在すれば拒否
        # is_domain_portロジックを削除: domain:portはスキームなし扱いのため
        # http(s)://を明示しない限り拒否（例: example.com:8080 → ValueError）
        scheme_match = _SCHEME_RE.match(sanitized)
        if scheme_match:
            raise ValueError("危険なURLスキームが検出されました")
        # スキームなし → https:// を補完して検証
        # _validate_netloc / _normalize_url の ValueError はそのまま伝播
        parsed = urlparse("https://" + sanitized)
        _validate_netloc(parsed)
        if parsed.port is not None:
            raise ValueError(
                "スキームなしURLにポートは指定できません（http(s)://を明示してください）"
            )
        return _normalize_url(parsed)


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

    # mode 未指定（デフォルト after）: Pydantic が str 型強制後にバリデーション実行
    # validate_website_scheme は mode="before" だが、Photo URL は外部API由来のため
    # str 型が保証されており mode="after" で十分
    @field_validator("url", "thumbnail_url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """URLスキームがhttp/httpsであることを検証

        セキュリティのため、javascript:やdata:などの
        潜在的に危険なスキームを拒否。
        不可視文字（Cf/Cs/Cc/Mn/Zs/Zl/Zpカテゴリ）を除去してからスキーム検証を行う。

        Args:
            v: 検証対象のURL文字列

        Returns:
            検証済みURL文字列（制御文字除去・前後空白除去済み）

        Raises:
            ValueError: 以下のいずれかの場合:
                - 制御文字除去後にURLが空
                - http/https以外のスキーム（またはスキームなし）
                - 有効なホスト名なし
                - userinfoを含む（例: https://user@host — RFC 3986 バイパス防止）

        """
        sanitized = _strip_invisible_chars(v).strip()
        if not sanitized:
            raise ValueError("URLが空になりました（制御文字除去後）")
        # RFC 3986 §6.2.2.1: パス部の大文字小文字保持のため urlparse にはオリジナルを渡す
        sanitized_lower = sanitized.lower()
        if not sanitized_lower.startswith(("http://", "https://")):
            raise ValueError("URLはhttp://またはhttps://で始まる必要があります")
        # _validate_netloc / _normalize_url の ValueError はそのまま伝播
        parsed = urlparse(sanitized)
        _validate_netloc(parsed)
        return _normalize_url(parsed)


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
