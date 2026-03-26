"""
Pydantic レスポンスモデル テスト

学習目標:
- XSS サニタイゼーションの網羅テスト（OWASP準拠）
- Pydantic モデルのバリデーション動作確認
- alias / extra forbid / ネストモデルの検証
- html.escape() の動作理解
"""

import html
from typing import Final, TypedDict

import pytest
from pydantic import ValidationError

from models.responses import (
    Address,
    Album,
    Comment,
    Company,
    Geo,
    Photo,
    Post,
    Todo,
    User,
    sanitize_user_content,
)

pytestmark = pytest.mark.unit

# =============================================================================
# XSS テストベクター（OWASP XSS Prevention Cheat Sheet 準拠）
# Reference: https://cheatsheetseries.owasp.org/cheatsheets/XSS_Filter_Evasion_Cheat_Sheet.html
# =============================================================================

type XSSVector = tuple[str | None, str]  # XSS_TEST_VECTORS 用（None エントリあり）
type XSSModelVector = tuple[str, str]  # _XSS_MODEL_ENTRIES 用（None なし、str のみ）

# XSSテストベクター定数
XSS_TEST_VECTORS: Final[list[XSSVector]] = [
    # ============================================
    # Category 1: Basic Script Tags
    # ============================================
    (
        "<script>alert('XSS')</script>",
        "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;",
    ),
    (
        "<SCRIPT>alert(1)</SCRIPT>",
        "&lt;SCRIPT&gt;alert(1)&lt;/SCRIPT&gt;",
    ),
    # ============================================
    # Category 2: Event Handlers (CRITICAL - most common bypass)
    # ============================================
    (
        "<img src=x onerror=alert(1)>",
        "&lt;img src=x onerror=alert(1)&gt;",
    ),
    (
        "<svg onload=alert(1)>",
        "&lt;svg onload=alert(1)&gt;",
    ),
    (
        "<body onpageshow=alert(1)>",
        "&lt;body onpageshow=alert(1)&gt;",
    ),
    (
        "<input onfocus=alert(1) autofocus>",
        "&lt;input onfocus=alert(1) autofocus&gt;",
    ),
    (
        "<details open ontoggle=alert(1)>",
        "&lt;details open ontoggle=alert(1)&gt;",
    ),
    (
        "<marquee onstart=alert(1)>",
        "&lt;marquee onstart=alert(1)&gt;",
    ),
    # ============================================
    # Category 3: URI Schemes (CRITICAL)
    # ============================================
    (
        '<a href="javascript:alert(1)">',
        "&lt;a href=&quot;javascript:alert(1)&quot;&gt;",
    ),
    (
        '<iframe src="javascript:alert(1)">',
        "&lt;iframe src=&quot;javascript:alert(1)&quot;&gt;",
    ),
    # ============================================
    # Category 4: Attribute Injection
    # ============================================
    (
        '" onclick="alert(1)"',
        "&quot; onclick=&quot;alert(1)&quot;",
    ),
    (
        "' onfocus='alert(1)'",
        "&#x27; onfocus=&#x27;alert(1)&#x27;",
    ),
    # ============================================
    # Category 5: Edge Cases
    # ============================================
    ("", ""),  # Empty string
    (None, ""),  # None handling → empty
    ("Normal text", "Normal text"),  # Passthrough (no XSS)
    (
        "Hello <b>World</b>",
        "Hello &lt;b&gt;World&lt;/b&gt;",
    ),  # Safe HTML
    # ============================================
    # Category 6: Special Characters
    # ============================================
    ("Test & Test", "Test &amp; Test"),  # Ampersand
    ("Test < Test", "Test &lt; Test"),  # Less than
    ("Test > Test", "Test &gt; Test"),  # Greater than
    ('Test "quoted"', "Test &quot;quoted&quot;"),  # Double quote
    ("Test 'quoted'", "Test &#x27;quoted&#x27;"),  # Single quote
]

# 共有定数パターン: (vector_tuple, id) のペアで定義して後から分解する。
# pytest.param ではなく tuple リストで定義し ids=[] で ID を管理する理由:
# pytest.param オブジェクトは tuple unpack（for a, b in list）が不可
#      （ParameterSet.values が3フィールド — ValueError: too many values to unpack）。
# TestCommentModel の内包表記展開で for dirty, expected in _XSS_MODEL_VECTORS を使用するため。
# (vector_tuple, id) ペア定義により同期ズレを構造的に防止。

# モデルテスト専用 XSS ベクター（OWASP 5カテゴリ）
# XSS-01〜03 の parametrize で共有参照
_XSS_MODEL_ENTRIES: Final[list[tuple[XSSModelVector, str]]] = [
    (
        ("<script>alert('XSS')</script>", "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;"),
        "script-basic",
    ),
    (("<img src=x onerror=alert(1)>", "&lt;img src=x onerror=alert(1)&gt;"), "event-img-onerror"),
    (
        ('<a href="javascript:alert(1)">', "&lt;a href=&quot;javascript:alert(1)&quot;&gt;"),
        "uri-javascript-anchor",
    ),
    (('" onclick="alert(1)"', "&quot; onclick=&quot;alert(1)&quot;"), "attr-double-quote"),
    (("Test & Test", "Test &amp; Test"), "char-ampersand"),
]
_XSS_MODEL_VECTORS: Final[list[XSSModelVector]] = [v for v, _ in _XSS_MODEL_ENTRIES]
_XSS_MODEL_IDS: Final[list[str]] = [i for _, i in _XSS_MODEL_ENTRIES]


class _CommentBaseData(TypedDict):
    """TestCommentModel XSS テスト用 Comment 基底データ型."""

    postId: int
    id: int
    name: str
    email: str
    body: str


_COMMENT_BASE: Final[_CommentBaseData] = {
    "postId": 1,
    "id": 1,
    "name": "safe_name",
    "email": "safe@example.com",
    "body": "safe_body",
}


class TestSanitizeUserContent:
    """sanitize_user_content() 関数の網羅テスト"""

    @pytest.mark.parametrize(
        ("input_value", "expected_output"),
        XSS_TEST_VECTORS,
        ids=[
            # Category 1: Script Tags
            "script-basic",
            "script-uppercase",
            # Category 2: Event Handlers
            "event-img-onerror",
            "event-svg-onload",
            "event-body-onpageshow",
            "event-input-onfocus",
            "event-details-ontoggle",
            "event-marquee-onstart",
            # Category 3: URI Schemes
            "uri-javascript-anchor",
            "uri-javascript-iframe",
            # Category 4: Attribute Injection
            "attr-double-quote",
            "attr-single-quote",
            # Category 5: Edge Cases
            "edge-empty",
            "edge-none",
            "edge-passthrough",
            "edge-safe-html",
            # Category 6: Special Characters
            "char-ampersand",
            "char-less-than",
            "char-greater-than",
            "char-double-quote",
            "char-single-quote",
        ],
    )
    def test_sanitize_user_content(
        self,
        input_value: str | None,
        expected_output: str,
    ) -> None:
        """XSSサニタイゼーションの網羅テスト（OWASP準拠）"""
        result = sanitize_user_content(input_value)
        assert result == expected_output

    def test_sanitize_matches_html_escape(self) -> None:
        """sanitize_user_content が html.escape(quote=True) と同等であることを確認"""
        test_input = "<script>alert('XSS')</script>"
        expected = html.escape(test_input, quote=True)

        result = sanitize_user_content(test_input)

        assert result == expected


class TestGeoModel:
    """Geo モデルのテスト

    XSS サニタイゼーション: Geo.lat フィールドが html.escape() でサニタイズされることを確認。
    OWASP カバレッジ: Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
                    Cat.4 Attribute Injection / Cat.6 Special Characters
    """

    def test_geo_basic_creation(self) -> None:
        """基本的な Geo モデル作成"""
        geo = Geo(lat="-37.3159", lng="81.1496")

        assert geo.lat == "-37.3159"
        assert geo.lng == "81.1496"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_geo_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Geo.lat フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        geo = Geo(lat=dirty, lng="normal")
        assert geo.lat == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_geo_lng_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Geo.lng フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        geo = Geo(lat="0", lng=dirty)
        assert geo.lng == expected

    def test_geo_extra_fields_forbidden(self) -> None:
        """Geo モデルが extra フィールドを拒否することを確認"""
        with pytest.raises(ValidationError) as exc_info:
            Geo(lat="0", lng="0", extra="not allowed")  # type: ignore[call-arg]

        assert "extra" in str(exc_info.value).lower()


class TestAddressModel:
    """Address モデルのテスト

    XSS サニタイゼーション: Address.street フィールドが html.escape() でサニタイズされることを確認。
    OWASP カバレッジ: Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
                    Cat.4 Attribute Injection / Cat.6 Special Characters
    """

    @pytest.fixture
    def valid_geo(self) -> Geo:
        """XSS サニタイゼーションテスト専用の Address.geo ダミーインスタンス"""
        return Geo(lat="0", lng="0")

    def test_address_basic_creation(self) -> None:
        """基本的な Address モデル作成"""
        geo = Geo(lat="-37.3159", lng="81.1496")
        address = Address(
            street="Kulas Light",
            suite="Apt. 556",
            city="Gwenborough",
            zipcode="92998-3874",
            geo=geo,
        )

        assert address.street == "Kulas Light"
        assert address.city == "Gwenborough"
        assert address.geo.lat == "-37.3159"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_address_sanitizes_xss(self, valid_geo: Geo, dirty: str, expected: str) -> None:
        """Address.street フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        address = Address(street=dirty, suite="Test", city="City", zipcode="12345", geo=valid_geo)
        assert address.street == expected


class TestCompanyModel:
    """Company モデルのテスト

    XSS サニタイゼーション: Company.name フィールドが html.escape() でサニタイズされることを確認。
    OWASP カバレッジ: Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
                    Cat.4 Attribute Injection / Cat.6 Special Characters
    """

    def test_company_basic_creation(self) -> None:
        """基本的な Company モデル作成"""
        company = Company(
            name="Romaguera-Crona",
            catchPhrase="Multi-layered client-server neural-net",
            bs="harness real-time e-markets",
        )

        assert company.name == "Romaguera-Crona"
        assert company.catch_phrase == "Multi-layered client-server neural-net"

    def test_company_alias_working(self) -> None:
        """Company モデルの alias (catchPhrase → catch_phrase) が機能することを確認"""
        company = Company(
            name="Test",
            catchPhrase="Test Phrase",
            bs="test",
        )

        assert company.catch_phrase == "Test Phrase"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_company_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Company.name フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        company = Company(name=dirty, catchPhrase="Normal", bs="Normal")
        assert company.name == expected


class TestUserModel:
    """User モデルのテスト"""

    @pytest.fixture
    def valid_user_data(self) -> dict:
        """有効な User データを提供するフィクスチャ"""
        return {
            "id": 1,
            "name": "Leanne Graham",
            "username": "Bret",
            "email": "Sincere@april.biz",
            "address": {
                "street": "Kulas Light",
                "suite": "Apt. 556",
                "city": "Gwenborough",
                "zipcode": "92998-3874",
                "geo": {"lat": "-37.3159", "lng": "81.1496"},
            },
            "phone": "1-770-736-8031 x56442",
            "website": "hildegard.org",
            "company": {
                "name": "Romaguera-Crona",
                "catchPhrase": "Multi-layered client-server neural-net",
                "bs": "harness real-time e-markets",
            },
        }

    def test_user_basic_creation(self, valid_user_data: dict) -> None:
        """基本的な User モデル作成"""
        user = User(**valid_user_data)

        assert user.id == 1
        assert user.name == "Leanne Graham"
        assert user.address.city == "Gwenborough"
        assert user.company.name == "Romaguera-Crona"

    def test_user_nested_models(self, valid_user_data: dict) -> None:
        """User モデルのネストされたモデル (Address, Company) が正しく解析されることを確認"""
        user = User(**valid_user_data)

        assert isinstance(user.address, Address)
        assert isinstance(user.address.geo, Geo)
        assert isinstance(user.company, Company)

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_user_name_sanitizes_xss(
        self, valid_user_data: dict, dirty: str, expected: str
    ) -> None:
        """User.name フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        valid_user_data["name"] = dirty
        user = User(**valid_user_data)
        assert user.name == expected

    def test_user_populate_by_name(self, valid_user_data: dict) -> None:
        """User モデルの populate_by_name が有効であることを確認"""
        # User モデルは populate_by_name=True なので、alias で値を設定可能
        user = User(**valid_user_data)
        assert user.company.catch_phrase == "Multi-layered client-server neural-net"

    def test_user_extra_fields_forbidden(self, valid_user_data: dict) -> None:
        """User モデルが extra フィールドを拒否することを確認"""
        valid_user_data["extra_field"] = "not allowed"

        with pytest.raises(ValidationError) as exc_info:
            User(**valid_user_data)

        assert "extra" in str(exc_info.value).lower()

    def test_user_email_must_be_valid_format(self, valid_user_data: dict) -> None:
        """User.email が EmailStr 型により無効なメールアドレスを拒否すること"""
        valid_user_data["email"] = "not-an-email"
        with pytest.raises(ValidationError):
            User(**valid_user_data)

    def test_user_email_max_length_valid(self, valid_user_data: dict) -> None:
        """User.email=100文字（max_length 上限）で正常作成できること"""
        valid_user_data["email"] = "a" * 88 + "@example.com"  # 100文字
        user = User(**valid_user_data)
        assert len(user.email) == 100

    def test_user_email_max_length_invalid(self, valid_user_data: dict) -> None:
        """User.email=101文字（max_length 超過）で ValidationError が発生すること"""
        valid_user_data["email"] = "a" * 89 + "@example.com"  # 101文字
        with pytest.raises(ValidationError):
            User(**valid_user_data)

    def test_user_website_is_not_html_escaped(self, valid_user_data: dict) -> None:
        """websiteはhtml.escape対象外（URL内の&がエスケープされない）"""
        value = "example.com/page?a=1&b=2"
        valid_user_data["website"] = value
        user = User(**valid_user_data)
        assert user.website == value  # &amp; にならないことを確認

    def test_user_website_is_not_modified(self, valid_user_data: dict) -> None:
        """websiteはサニタイズ対象外（そのまま保持される）"""
        value = "example.com/page?a=1&b=2"
        valid_user_data["website"] = value
        user = User(**valid_user_data)
        assert user.website == value


class TestPostModel:
    """Post モデルのテスト"""

    def test_post_basic_creation(self) -> None:
        """基本的な Post モデル作成"""
        post = Post(userId=1, id=1, title="Test Title", body="Test Body")

        assert post.user_id == 1
        assert post.title == "Test Title"

    def test_post_alias_working(self) -> None:
        """Post モデルの alias (userId → user_id) が機能することを確認"""
        post = Post(userId=5, id=1, title="Test", body="Test")

        assert post.user_id == 5

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_post_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Post.title フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        post = Post(userId=1, id=1, title=dirty, body="Normal body")
        assert post.title == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_post_body_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Post.body フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        post = Post(userId=1, id=1, title="Normal title", body=dirty)
        assert post.body == expected

    @pytest.mark.parametrize(
        "invalid_id",
        [
            pytest.param(0, id="zero"),
            pytest.param(-1, id="negative"),
        ],
    )
    def test_post_invalid_id_raises_validation_error(self, invalid_id: int) -> None:
        """id が ge=1 制約（id は1以上）に違反した場合 ValidationError が発生する"""
        with pytest.raises(ValidationError) as exc_info:
            Post(id=invalid_id, userId=1, title="Test", body="Body")
        assert "id" in str(exc_info.value)

    def test_post_title_max_length_valid(self) -> None:
        """title=200文字（max_length 上限）で正常作成できること"""
        post = Post(id=1, userId=1, title="a" * 200, body="Body")
        assert len(post.title) == 200

    def test_post_title_max_length_invalid(self) -> None:
        """title=201文字（max_length 超過）で ValidationError が発生すること"""
        with pytest.raises(ValidationError) as exc_info:
            Post(id=1, userId=1, title="a" * 201, body="Body")
        assert "title" in str(exc_info.value)


class TestCommentModel:
    """Comment モデルのテスト

    XSS サニタイゼーション: Comment の name/body 2フィールドが
                    html.escape() でサニタイズされることを確認。
    OWASP カバレッジ: Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
                    Cat.4 Attribute Injection / Cat.6 Special Characters
    """

    def test_comment_basic_creation(self) -> None:
        """基本的な Comment モデル作成"""
        comment = Comment(
            postId=1,
            id=1,
            name="Test Name",
            email="test@example.com",
            body="Test Comment",
        )

        assert comment.post_id == 1
        assert comment.email == "test@example.com"

    @pytest.mark.parametrize(
        ("field", "dirty", "expected"),
        [
            (field, dirty, expected)
            for field in ("name", "body")
            for dirty, expected in _XSS_MODEL_VECTORS
        ],
        ids=[f"{field}-{vid}" for field in ("name", "body") for vid in _XSS_MODEL_IDS],
    )
    def test_comment_sanitizes_xss(self, field: str, dirty: str, expected: str) -> None:
        """Comment モデル全フィールドの XSS サニタイゼーション（2フィールド x OWASP 5カテゴリ）"""
        data: dict[str, str | int] = {**_COMMENT_BASE, field: dirty}
        comment = Comment.model_validate(data)
        assert getattr(comment, field) == expected

    def test_comment_email_must_be_valid_format(self) -> None:
        """Comment.email が EmailStr 型により無効なメールアドレスを拒否すること"""
        with pytest.raises(ValidationError):
            Comment(postId=1, id=1, name="Name", email="not-an-email", body="Body")

    def test_comment_email_max_length_valid(self) -> None:
        """Comment.email=100文字（max_length 上限）で正常作成できること"""
        long_email = "a" * 88 + "@example.com"  # 100文字
        comment = Comment(postId=1, id=1, name="Name", email=long_email, body="Body")
        assert len(comment.email) == 100

    def test_comment_email_max_length_invalid(self) -> None:
        """Comment.email=101文字（max_length 超過）で ValidationError が発生すること"""
        long_email = "a" * 89 + "@example.com"  # 101文字
        with pytest.raises(ValidationError):
            Comment(postId=1, id=1, name="Name", email=long_email, body="Body")


class TestTodoModel:
    """Todo モデルのテスト"""

    def test_todo_basic_creation(self) -> None:
        """基本的な Todo モデル作成"""
        todo = Todo(userId=1, id=1, title="Test TODO", completed=False)

        assert todo.user_id == 1
        assert todo.title == "Test TODO"
        assert todo.completed is False

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_todo_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Todo.title フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        todo = Todo(userId=1, id=1, title=dirty, completed=False)
        assert todo.title == expected


class TestAlbumModel:
    """Album モデルのテスト"""

    def test_album_basic_creation(self) -> None:
        """基本的な Album モデル作成"""
        album = Album(userId=1, id=1, title="Test Album")

        assert album.user_id == 1
        assert album.title == "Test Album"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_album_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Album.title フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        album = Album(userId=1, id=1, title=dirty)
        assert album.title == expected


class TestPhotoModel:
    """Photo モデルのテスト"""

    def test_photo_basic_creation(self) -> None:
        """基本的な Photo モデル作成"""
        photo = Photo(
            albumId=1,
            id=1,
            title="Test Photo",
            url="https://via.placeholder.com/600/92c952",
            thumbnailUrl="https://via.placeholder.com/150/92c952",
        )

        assert photo.album_id == 1
        assert photo.title == "Test Photo"
        assert photo.thumbnail_url == "https://via.placeholder.com/150/92c952"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_VECTORS,
        ids=_XSS_MODEL_IDS,
    )
    def test_photo_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Photo.title フィールドの XSS サニタイゼーション（OWASP 5カテゴリ）"""
        photo = Photo(
            albumId=1,
            id=1,
            title=dirty,
            url="https://example.com/photo.jpg",
            thumbnailUrl="https://example.com/thumb.jpg",
        )
        assert photo.title == expected

    def test_photo_rejects_javascript_url(self) -> None:
        """Photo モデルが javascript: スキームを拒否することを確認"""
        with pytest.raises(ValidationError) as exc_info:
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="javascript:alert('XSS')",
                thumbnailUrl="https://example.com/thumb.jpg",
            )

        assert "url must start with http://" in str(exc_info.value).lower()

    def test_photo_rejects_data_url(self) -> None:
        """Photo モデルが data: スキームを拒否することを確認"""
        with pytest.raises(ValidationError) as exc_info:
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnailUrl="data:image/png;base64,iVBORw0KGgo=",
            )

        assert "url must start with http://" in str(exc_info.value).lower()


class TestExtraFieldsForbidden:
    """全モデルの extra="forbid" 設定確認"""

    @pytest.mark.parametrize(
        ("model_class", "valid_data", "extra_field"),
        [
            pytest.param(
                Geo,
                {"lat": "0", "lng": "0"},
                {"extra": "not_allowed"},
                id="Geo",
            ),
            pytest.param(
                Company,
                {"name": "Test", "catchPhrase": "Test", "bs": "test"},
                {"extra": "not_allowed"},
                id="Company",
            ),
            pytest.param(
                Post,
                {"userId": 1, "id": 1, "title": "Test", "body": "Test"},
                {"extra": "not_allowed"},
                id="Post",
            ),
            pytest.param(
                Comment,
                {
                    "postId": 1,
                    "id": 1,
                    "name": "Test",
                    "email": "test@test.com",
                    "body": "Test",
                },
                {"extra": "not_allowed"},
                id="Comment",
            ),
            pytest.param(
                Todo,
                {"userId": 1, "id": 1, "title": "Test", "completed": False},
                {"extra": "not_allowed"},
                id="Todo",
            ),
            pytest.param(
                Album,
                {"userId": 1, "id": 1, "title": "Test"},
                {"extra": "not_allowed"},
                id="Album",
            ),
            pytest.param(
                Photo,
                {
                    "albumId": 1,
                    "id": 1,
                    "title": "Test",
                    "url": "http://test.com",
                    "thumbnailUrl": "http://test.com",
                },
                {"extra": "not_allowed"},
                id="Photo",
            ),
        ],
    )
    def test_extra_fields_forbidden(
        self,
        model_class: type,
        valid_data: dict,
        extra_field: dict,
    ) -> None:
        """全モデルが extra フィールドを拒否することを確認"""
        invalid_data = {**valid_data, **extra_field}

        with pytest.raises(ValidationError) as exc_info:
            model_class(**invalid_data)

        assert "extra" in str(exc_info.value).lower()


# =============================================================================
# 学習ポイント:
#
# 1. XSS サニタイゼーション:
#    - html.escape(quote=True) で <, >, &, ", ' をエスケープ
#    - OWASP Cheat Sheet 準拠のテストベクター
#    - 入力バリデーション + 出力エスケープの Defense in Depth
#
# 2. Pydantic モデル設計:
#    - field_validator でカスタムバリデーション
#    - alias で JSONキー名 → Python属性名のマッピング
#    - extra="forbid" で未知フィールドを拒否
#
# 3. ネストモデル:
#    - Geo → Address → User の階層構造
#    - 各レベルでサニタイゼーションが適用
#
# 4. パラメータ化テスト:
#    - pytest.param + ids で可読性向上
#    - XSSベクターの網羅的テスト
#    - 全モデルの extra forbid 一括テスト
#
# 5. テストフィクスチャ:
#    - 複雑なデータ構造の再利用
#    - テスト間の独立性確保
# =============================================================================
