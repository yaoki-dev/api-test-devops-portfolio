"""
Pydantic レスポンスモデル テスト

学習目標:
- XSS サニタイゼーションの網羅テスト（XSSカバレッジ: OWASP Cheat Sheetベース・プロジェクト独自分類）
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
# XSS テストベクター（OWASP Cheat Sheetベース・プロジェクト独自分類）
# Reference: https://cheatsheetseries.owasp.org/cheatsheets/XSS_Filter_Evasion_Cheat_Sheet.html
# =============================================================================

type XSSVector = tuple[str, str]  # XSS_TEST_VECTORS 用

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

# モデルテスト専用 XSS ベクター（OWASP Cheat Sheetベース・独自5分類）
# 生データ: (dirty, expected, id) タプル形式
_XSS_RAW_VECTORS: Final[list[tuple[str, str, str]]] = [
    (
        "<script>alert('XSS')</script>",
        "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;",
        "script-basic",
    ),
    (
        "<img src=x onerror=alert(1)>",
        "&lt;img src=x onerror=alert(1)&gt;",
        "event-img-onerror",
    ),
    (
        '<a href="javascript:alert(1)">',
        "&lt;a href=&quot;javascript:alert(1)&quot;&gt;",
        "uri-javascript-anchor",
    ),
    (
        '" onclick="alert(1)"',
        "&quot; onclick=&quot;alert(1)&quot;",
        "attr-double-quote",
    ),
    ("Test & Test", "Test &amp; Test", "char-ampersand"),
]

# 既存互換: pytest.param 形式（他テストクラスで直接使用）
_XSS_MODEL_PARAMS: Final = [
    pytest.param(dirty, expected, id=xss_id) for dirty, expected, xss_id in _XSS_RAW_VECTORS
]


class _GeoData(TypedDict):
    """Geo モデル入力データ型."""

    lat: str
    lng: str


class _AddressData(TypedDict):
    """Address モデル入力データ型."""

    street: str
    suite: str
    city: str
    zipcode: str
    geo: _GeoData


class _CompanyData(TypedDict):
    """Company モデル入力データ型."""

    name: str
    catchPhrase: str
    bs: str


class _UserData(TypedDict):
    """User モデル入力データ型."""

    id: int
    name: str
    username: str
    email: str
    address: _AddressData
    phone: str
    website: str
    company: _CompanyData


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
        input_value: str,
        expected_output: str,
    ) -> None:
        """XSSサニタイゼーションの網羅テスト（OWASP Cheat Sheetベース・プロジェクト独自分類）"""
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
    XSS カバレッジ（OWASP Cheat Sheetベース・プロジェクト独自分類）:
        Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
        Cat.4 Attribute Injection / Cat.6 Special Characters
    """

    def test_geo_basic_creation(self) -> None:
        """基本的な Geo モデル作成"""
        geo = Geo(lat="-37.3159", lng="81.1496")

        assert geo.lat == "-37.3159"
        assert geo.lng == "81.1496"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_geo_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Geo.lat フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
        geo = Geo(lat=dirty, lng="normal")
        assert geo.lat == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_geo_lng_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Geo.lng フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
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
    XSS カバレッジ（OWASP Cheat Sheetベース・プロジェクト独自分類）:
        Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
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
        _XSS_MODEL_PARAMS,
    )
    def test_address_sanitizes_xss(self, valid_geo: Geo, dirty: str, expected: str) -> None:
        """Address.street の XSS サニタイゼーション（OWASP CS・独自5分類）"""
        address = Address(street=dirty, suite="Test", city="City", zipcode="12345", geo=valid_geo)
        assert address.street == expected


class TestCompanyModel:
    """Company モデルのテスト

    XSS サニタイゼーション: Company.name フィールドが html.escape() でサニタイズされることを確認。
    XSS カバレッジ（OWASP Cheat Sheetベース・プロジェクト独自分類）:
        Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
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
        _XSS_MODEL_PARAMS,
    )
    def test_company_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Company.name フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
        company = Company(name=dirty, catchPhrase="Normal", bs="Normal")
        assert company.name == expected


class TestUserModel:
    """User モデルのテスト

    XSS サニタイゼーション: User.name フィールドが html.escape() でサニタイズされることを確認。
    websiteフィールドは危険スキーム（javascript:, data:, vbscript:）バリデーション。
    XSS カバレッジ（OWASP Cheat Sheetベース・プロジェクト独自分類）:
        Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
        Cat.4 Attribute Injection / Cat.6 Special Characters
    """

    @pytest.fixture
    def valid_user_data(self) -> _UserData:
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

    def test_user_basic_creation(self, valid_user_data: _UserData) -> None:
        """基本的な User モデル作成"""
        user = User(**valid_user_data)

        assert user.id == 1
        assert user.name == "Leanne Graham"
        assert user.address.city == "Gwenborough"
        assert user.company.name == "Romaguera-Crona"

    def test_user_nested_models(self, valid_user_data: _UserData) -> None:
        """User モデルのネストされたモデル (Address, Company) が正しく解析されることを確認"""
        user = User(**valid_user_data)

        assert isinstance(user.address, Address)
        assert isinstance(user.address.geo, Geo)
        assert isinstance(user.company, Company)

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_user_name_sanitizes_xss(
        self, valid_user_data: _UserData, dirty: str, expected: str
    ) -> None:
        """User.name フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
        valid_user_data["name"] = dirty
        user = User(**valid_user_data)
        assert user.name == expected

    def test_user_populate_by_name(self, valid_user_data: _UserData) -> None:
        """User モデルの populate_by_name が有効であることを確認"""
        # User モデルは populate_by_name=True なので、alias で値を設定可能
        user = User(**valid_user_data)
        assert user.company.catch_phrase == "Multi-layered client-server neural-net"

    def test_user_extra_fields_forbidden(self, valid_user_data: _UserData) -> None:
        """User モデルが extra フィールドを拒否することを確認"""
        valid_user_data["extra_field"] = "not allowed"  # type: ignore[typeddict-unknown-key]

        with pytest.raises(ValidationError) as exc_info:
            User(**valid_user_data)

        assert "extra" in str(exc_info.value).lower()

    def test_user_email_must_be_valid_format(self, valid_user_data: _UserData) -> None:
        """User.email が EmailStr 型により無効なメールアドレスを拒否すること"""
        valid_user_data["email"] = "not-an-email"
        with pytest.raises(ValidationError):
            User(**valid_user_data)

    def test_user_email_max_length_valid(self, valid_user_data: _UserData) -> None:
        """User.email=100文字（max_length 上限）で正常作成できること"""
        # 52 + "@"(1) + 35 + ".example.com"(12) = 100文字（local≤64: RFC5321準拠）
        valid_user_data["email"] = "a" * 52 + "@" + "b" * 35 + ".example.com"
        user = User(**valid_user_data)
        assert len(user.email) == 100

    def test_user_email_max_length_invalid(self, valid_user_data: _UserData) -> None:
        """User.email=101文字（max_length 超過）で ValidationError が発生すること"""
        # 52 + "@"(1) + 36 + ".example.com"(12) = 101文字（local≤64: RFC5321準拠）
        valid_user_data["email"] = "a" * 52 + "@" + "b" * 36 + ".example.com"
        with pytest.raises(ValidationError):
            User(**valid_user_data)

    def test_user_website_is_not_html_escaped(self, valid_user_data: _UserData) -> None:
        """websiteはhtml.escape対象外（URL内の&がエスケープされない）"""
        value = "example.com/page?a=1&b=2"
        valid_user_data["website"] = value
        user = User(**valid_user_data)
        assert user.website == value  # &amp; にならないことを確認

    @pytest.mark.parametrize(
        "dangerous_url",
        [
            "javascript:alert(1)",
            "JAVASCRIPT:alert(1)",
            "javascript:void(0)",
            "data:text/html,<script>alert(1)</script>",
            "Data:image/png;base64,abc",
            "vbscript:msgbox(1)",
            " javascript:alert(1)",
            "\tjavascript:void(0)",
            "\u200bjavascript:alert(1)",
            "java\u200bscript:alert(1)",
            "\u202ejavascript:alert(1)",
            "j\u00a0avascript:alert(1)",
            "\u2060javascript:alert(1)",
            "\u2066javascript:alert(1)",
            "\u2069javascript:alert(1)",
            "vbs\u200bcript:msgbox(1)",
            "da\u200bta:text/html,x",
            "vbscript\u202e:msgbox(1)",
            "da\u200bta:image/png;base64,abc",
            "java\u2028script:alert(1)",
            "java\u2029script:alert(1)",
            "ftp://evil.com",
            "file:///etc/passwd",
            "blob:https://evil.com/uuid",
        ],
        ids=[
            "js_basic",
            "js_uppercase",
            "js_void",
            "data_html",
            "data_image",
            "vbscript",
            "js_leading_space",
            "js_leading_tab",
            "js_zwsp_prefix",
            "js_zwsp_mid_scheme",
            "js_bidi_override",
            "js_nbsp_mid_scheme",
            "js_word_joiner_prefix",
            "js_lri_prefix",
            "js_pdi_prefix",
            "vbscript_zwsp_mid",
            "data_zwsp_mid",
            "vbscript_bidi_override",
            "data_zwsp_mid_image",
            "js_line_separator_mid",
            "js_paragraph_separator_mid",
            "ftp_scheme",
            "file_scheme",
            "blob_scheme",
        ],
    )
    def test_user_website_rejects_dangerous_scheme(
        self, valid_user_data: _UserData, dangerous_url: str
    ) -> None:
        """User.website が危険なURLスキームを拒否すること"""
        valid_user_data["website"] = dangerous_url
        with pytest.raises(ValidationError):
            User(**valid_user_data)

    def test_user_website_rejects_protocol_relative_url(self, valid_user_data: _UserData) -> None:
        """User.website がプロトコル相対URLを明示的なエラーで拒否すること"""
        valid_user_data["website"] = "//cdn.example.com/image.jpg"
        with pytest.raises(ValidationError, match="プロトコル相対URLは許可されていません"):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        "safe_url",
        [
            "hildegard.org",
            "example.com/page?a=1&b=2",
            "https://valid.com",
            "http://valid.com",
            "example.com:8080",
            "sub.domain.com:443/path",
            "example.com:8080/path?query=1",
            "http://example.com:8080",
        ],
        ids=[
            "no_scheme_domain",
            "no_scheme_with_query",
            "https",
            "http",
            "domain_port",
            "subdomain_port_path",
            "domain_port_path_query",
            "http_with_port",
        ],
    )
    def test_user_website_allows_safe_url(self, valid_user_data: _UserData, safe_url: str) -> None:
        """User.website が安全なURL形式を受け入れること"""
        valid_user_data["website"] = safe_url
        user = User(**valid_user_data)
        assert user.website == safe_url

    @pytest.mark.parametrize(
        ("dirty_safe_url", "expected"),
        [
            pytest.param(
                "\u200bhttps://example.com", "https://example.com", id="zwsp_prefix_stripped"
            ),
            pytest.param(
                "https://example.com\u00a0", "https://example.com", id="nbsp_suffix_stripped"
            ),
            pytest.param("\u2060https://valid.com", "https://valid.com", id="word_joiner_stripped"),
        ],
    )
    def test_user_website_sanitizes_control_chars_in_safe_url(
        self, valid_user_data: _UserData, dirty_safe_url: str, expected: str
    ) -> None:
        """User.website が安全なURLに含まれる制御文字を除去して返却すること"""
        valid_user_data["website"] = dirty_safe_url
        user = User(**valid_user_data)
        assert user.website == expected

    @pytest.mark.parametrize(
        "control_only",
        [
            pytest.param("\u2060", id="word_joiner_only"),
            pytest.param("\u200b", id="zwsp_only"),
            pytest.param("  \u2060  ", id="spaces_and_word_joiner_only"),
            pytest.param("\u200b\u200c\u200d", id="zwsp_zwnj_zwj_only"),
            pytest.param("\u2060\u2061", id="word_joiner_invisible_times_only"),
            pytest.param("\ufeff", id="bom_only"),
            pytest.param("\x00\x01\x02", id="c0_control_only"),
        ],
    )
    def test_user_website_control_char_only_raises(
        self, valid_user_data: _UserData, control_only: str
    ) -> None:
        """制御文字のみのwebsiteはサニタイズ後に空文字列となりValidationErrorになること"""
        valid_user_data["website"] = control_only
        with pytest.raises(ValidationError):
            User(**valid_user_data)


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
        _XSS_MODEL_PARAMS,
    )
    def test_post_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Post.title フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
        post = Post(userId=1, id=1, title=dirty, body="Normal body")
        assert post.title == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_post_body_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Post.body フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
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
    XSS カバレッジ（OWASP Cheat Sheetベース・プロジェクト独自分類）:
        Cat.1 Script Tags / Cat.2 Event Handlers / Cat.3 URI Schemes /
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
            pytest.param(field, dirty, expected, id=f"{field}-{xss_id}")
            for field in ("name", "body")
            for dirty, expected, xss_id in _XSS_RAW_VECTORS
        ],
    )
    def test_comment_sanitizes_xss(self, field: str, dirty: str, expected: str) -> None:
        """Comment XSS サニタイゼーション（name/body x OWASP CS・独自5分類）"""
        data: dict[str, str | int] = {**_COMMENT_BASE, field: dirty}
        comment = Comment.model_validate(data)
        assert getattr(comment, field) == expected

    def test_comment_email_must_be_valid_format(self) -> None:
        """Comment.email が EmailStr 型により無効なメールアドレスを拒否すること"""
        with pytest.raises(ValidationError):
            Comment(postId=1, id=1, name="Name", email="not-an-email", body="Body")

    def test_comment_email_max_length_valid(self) -> None:
        """Comment.email=100文字（max_length 上限）で正常作成できること"""
        # 52 + "@"(1) + 35 + ".example.com"(12) = 100文字（local≤64: RFC5321準拠）
        long_email = "a" * 52 + "@" + "b" * 35 + ".example.com"
        comment = Comment(postId=1, id=1, name="Name", email=long_email, body="Body")
        assert len(comment.email) == 100

    def test_comment_email_max_length_invalid(self) -> None:
        """Comment.email=101文字（max_length 超過）で ValidationError が発生すること"""
        # 52 + "@"(1) + 36 + ".example.com"(12) = 101文字（local≤64: RFC5321準拠）
        long_email = "a" * 52 + "@" + "b" * 36 + ".example.com"
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
        _XSS_MODEL_PARAMS,
    )
    def test_todo_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Todo.title フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
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
        _XSS_MODEL_PARAMS,
    )
    def test_album_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Album.title フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
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
        ("url", "thumbnail_url"),
        [
            pytest.param(
                "https://via.placeholder.com/600/92c952",
                "https://via.placeholder.com/150/92c952",
                id="both_https",
            ),
            pytest.param(
                "http://via.placeholder.com/600/92c952",
                "http://via.placeholder.com/150/92c952",
                id="both_http",
            ),
            pytest.param(
                "https://via.placeholder.com/600/92c952",
                "http://via.placeholder.com/150/92c952",
                id="mixed_https_http",
            ),
        ],
    )
    def test_photo_url_scheme_allows_http_https(self, url: str, thumbnail_url: str) -> None:
        """Photo.validate_url_scheme が http/https URLを許可すること"""
        photo = Photo(
            albumId=1,
            id=1,
            title="Test",
            url=url,
            thumbnailUrl=thumbnail_url,
        )
        assert photo.url == url
        assert photo.thumbnail_url == thumbnail_url

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_photo_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        """Photo.title フィールドの XSS サニタイゼーション（OWASP Cheat Sheetベース・独自5分類）"""
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

        assert "URLはhttp://またはhttps://で始まる必要があります" in str(exc_info.value)

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

        assert "URLはhttp://またはhttps://で始まる必要があります" in str(exc_info.value)

    def test_photo_rejects_schemeless_url(self) -> None:
        """Photo.url がスキームなしURLを拒否すること"""
        with pytest.raises(ValidationError):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="example.com/photo.jpg",
                thumbnailUrl="https://example.com/thumb.jpg",
            )

    def test_photo_rejects_schemeless_thumbnail_url(self) -> None:
        """Photo.thumbnail_url がスキームなしURLを拒否すること"""
        with pytest.raises(ValidationError):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnailUrl="example.com/thumb.jpg",
            )

    def test_photo_rejects_control_char_only_url(self) -> None:
        """制御文字のみのPhoto.urlが空文字エラーで拒否されること"""
        with pytest.raises(ValidationError, match="URLが空になりました"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="\u200b\u200c\u200d",
                thumbnailUrl="https://example.com/thumb.jpg",
            )


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
            pytest.param(
                Address,
                {
                    "street": "Test St",
                    "suite": "Apt 1",
                    "city": "TestCity",
                    "zipcode": "12345",
                    "geo": {"lat": "0", "lng": "0"},
                },
                {"extra": "not_allowed"},
                id="Address",
            ),
            pytest.param(
                User,
                {
                    "id": 1,
                    "name": "Test User",
                    "username": "testuser",
                    "email": "test@example.com",
                    "address": {
                        "street": "123 Test St",
                        "suite": "Apt 1",
                        "city": "TestCity",
                        "zipcode": "12345",
                        "geo": {"lat": "0", "lng": "0"},
                    },
                    "phone": "555-1234",
                    "website": "example.com",
                    "company": {
                        "name": "Test Co",
                        "catchPhrase": "Testing",
                        "bs": "tests",
                    },
                },
                {"extra": "not_allowed"},
                id="User",
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
#    - OWASP Cheat Sheet ベースのテストベクター（プロジェクト独自分類）
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
