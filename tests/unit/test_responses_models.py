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
    _strip_invisible_chars,  # noqa: PLC2701
    sanitize_user_content,  # noqa: PLC2701
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
# (dirty, expected, id) のタプルリスト（pytest内部APIを使わない形式）
_XSS_PAIRS: Final[list[tuple[str, str, str]]] = [
    (
        "<script>alert('XSS')</script>",
        "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;",
        "script_basic",
    ),
    ("<img src=x onerror=alert(1)>", "&lt;img src=x onerror=alert(1)&gt;", "event_img_onerror"),
    (
        '<a href="javascript:alert(1)">',
        "&lt;a href=&quot;javascript:alert(1)&quot;&gt;",
        "uri_scheme_js",
    ),
    ('" onclick="alert(1)"', "&quot; onclick=&quot;alert(1)&quot;", "attr_injection"),
    ("Test & Test", "Test &amp; Test", "special_chars_amp"),
]

# 単一フィールド parametrize 用（ID付き pytest.param リスト）
# 複数フィールド複合パラメータ化が必要な箇所は _XSS_PAIRS を直接使用すること
_XSS_MODEL_PARAMS: Final = [
    pytest.param(dirty, expected, id=id_) for dirty, expected, id_ in _XSS_PAIRS
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

    def test_sanitize_user_content_rejects_none(self) -> None:
        """None を渡すと ValueError が発生すること（型チェックの契約確認）

        Note:
            Pydantic field_validator は ValueError/AssertionError のみ
            ValidationError に変換するため、明示的に ValueError を raise する。
        """
        with pytest.raises(ValueError, match="文字列が必要です"):
            sanitize_user_content(None)  # type: ignore[arg-type]


def test_strip_invisible_chars_preserves_ascii_space() -> None:
    """_strip_invisible_chars がASCIIスペース(U+0020)を保持することを検証。

    U+0020はZsカテゴリだが、URLクエリパラメータ等に含まれる正常な文字として保持される。
    NBSP (U+00A0) 等の他のZs文字は除去される。
    """
    # ASCII スペースは保持される
    assert (
        _strip_invisible_chars("https://example.com/path?a=1 b=2")
        == "https://example.com/path?a=1 b=2"
    )
    # NBSP (U+00A0: Zs) はNFKC前に除去される（NFKC変換前にZsフィルタが適用されるため）
    assert _strip_invisible_chars("https://\u00a0example.com") == "https://example.com"
    # 全角スペース (U+3000: Zs) はNFKC前に除去される
    assert _strip_invisible_chars("https://\u3000example.com") == "https://example.com"
    # Variation Selector-1 (U+FE00: Mn) は除去される
    assert _strip_invisible_chars("java\ufe00script:alert(1)") == "javascript:alert(1)"
    # Line Separator (U+2028: Zl) は除去される
    assert _strip_invisible_chars("java\u2028script:alert(1)") == "javascript:alert(1)"
    # Paragraph Separator (U+2029: Zp) は除去される
    assert _strip_invisible_chars("java\u2029script:alert(1)") == "javascript:alert(1)"


def test_strip_invisible_chars_removes_surrogate_codepoint() -> None:
    """_strip_invisible_chars が孤立サロゲート(Cs)をnormalize前に除去することを検証。

    孤立サロゲート(U+D800-U+DFFF)は unicodedata.normalize() で ValueError を
    送出するため、事前除去が必要。
    """
    # 孤立サロゲートが除去され、残りの文字列が返される
    assert _strip_invisible_chars("https://\ud800example.com") == "https://example.com"
    # サロゲートのみの入力は空文字列になる
    assert _strip_invisible_chars("\ud800\udbff\udfff") == ""
    # サロゲートが混在しても正常な文字は保持される
    assert _strip_invisible_chars("abc\ud800def") == "abcdef"


def test_strip_invisible_chars_returns_empty_for_empty_input() -> None:
    """_strip_invisible_chars に空文字列を渡すと空文字列が返ること。"""
    assert _strip_invisible_chars("") == ""


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

    XSS サニタイゼーション: User.name, username, phone フィールドが
    html.escape() でサニタイズされることを確認。
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
        ("field", "dirty", "expected"),
        [
            pytest.param(field, dirty, expected, id=f"{field}-{id_}")
            for field in ("name", "username", "phone")
            for dirty, expected, id_ in _XSS_PAIRS
        ],
    )
    def test_user_sanitizes_xss(
        self, valid_user_data: _UserData, field: str, dirty: str, expected: str
    ) -> None:
        """User name/username/phone フィールドの XSS サニタイゼーション"""
        user = User(**{**valid_user_data, field: dirty})
        assert getattr(user, field) == expected

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
        # スキームなしURLはhttps://が補完される
        assert user.website == "https://example.com/page?a=1&b=2"  # &amp; にならないことを確認

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
            "javascript:0",
            "javascript:1+1",
            "malicious.js:xyz",
            "a.b:evil",
            "example.com:8080",
            "sub.domain.com:443/path",
            "example.com:8080/path?query=1",
            "192.168.1.1:8080",
            "10.0.0.1:3000/api",
            "/path/only",
            "java\ufe00script:alert(1)",
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
            "js_digit_after_colon",
            "js_expression_after_colon",
            "dotted_scheme_non_port",
            "dotted_scheme_alpha_after_colon",
            "domain_port_no_scheme",
            "subdomain_port_path_no_scheme",
            "domain_port_path_query_no_scheme",
            "ip_port_no_scheme",
            "ip_port_path_no_scheme",
            "path_only_no_host",
            "js_variation_selector_mn_bypass",
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
        "empty_netloc_url",
        [
            pytest.param("http://", id="http_empty_netloc"),
            pytest.param("https:///path", id="https_triple_slash"),
        ],
    )
    def test_user_website_rejects_empty_netloc(
        self, valid_user_data: _UserData, empty_netloc_url: str
    ) -> None:
        """User.website が空のnetlocを拒否すること"""
        valid_user_data["website"] = empty_netloc_url
        with pytest.raises(ValidationError, match="有効なホスト名が含まれていません"):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        ("dangerous_url", "expected_match"),
        [
            pytest.param(
                "https://example.com:abc/",
                "ポートが無効",
                id="invalid_port_string",
            ),
        ],
    )
    def test_user_website_rejects_security_bypass_patterns(
        self, valid_user_data: _UserData, dangerous_url: str, expected_match: str
    ) -> None:
        """User.website がセキュリティバイパスパターンを拒否すること"""
        valid_user_data["website"] = dangerous_url
        with pytest.raises(ValidationError, match=expected_match):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        "non_str_input",
        [
            pytest.param(123, id="int_input"),
            pytest.param(None, id="none_input"),
            pytest.param(["https://example.com"], id="list_input"),
        ],
    )
    def test_user_website_rejects_non_str_input(
        self, valid_user_data: _UserData, non_str_input: object
    ) -> None:
        """User.website が非文字列入力を拒否すること"""
        valid_user_data["website"] = non_str_input
        with pytest.raises(ValidationError):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        ("input_url", "expected_url"),
        [
            pytest.param("https://hildegard.org", "https://hildegard.org", id="https_domain"),
            pytest.param(
                "https://example.com/page?a=1&b=2",
                "https://example.com/page?a=1&b=2",
                id="https_with_query",
            ),
            pytest.param("https://valid.com", "https://valid.com", id="https"),
            pytest.param("http://valid.com", "http://valid.com", id="http"),
            pytest.param("http://example.com:8080", "http://example.com:8080", id="http_with_port"),
            # スキームなし → https:// 補完（N2設計変更）
            pytest.param("hildegard.org", "https://hildegard.org", id="schemeless_domain"),
            pytest.param("example.com/path", "https://example.com/path", id="schemeless_with_path"),
            pytest.param(
                "Example.COM/path", "https://example.com/path", id="schemeless_uppercase_host"
            ),
        ],
    )
    def test_user_website_allows_safe_url(
        self, valid_user_data: _UserData, input_url: str, expected_url: str
    ) -> None:
        """User.website が安全なURL形式を受け入れること（スキームなしはhttps://に補完）"""
        valid_user_data["website"] = input_url
        user = User(**valid_user_data)
        assert user.website == expected_url

    @pytest.mark.parametrize(
        ("input_url", "expected_url"),
        [
            pytest.param("HTTP://example.com", "http://example.com", id="uppercase_http_scheme"),
            pytest.param("HTTPS://example.com", "https://example.com", id="uppercase_https_scheme"),
            pytest.param(
                "HTTP://Example.COM", "http://example.com", id="uppercase_scheme_and_host"
            ),
            pytest.param("HtTp://Test.Com", "http://test.com", id="mixed_case_scheme_and_host"),
            pytest.param(
                "HTTP://Example.COM:8080",
                "http://example.com:8080",
                id="uppercase_scheme_and_host_with_port",
            ),
            pytest.param(
                "HTTP://Example.COM/Path?q=Value",
                "http://example.com/Path?q=Value",
                id="path_and_query_preserved",
            ),
        ],
    )
    def test_user_website_normalizes_scheme_and_host(
        self, valid_user_data: _UserData, input_url: str, expected_url: str
    ) -> None:
        """スキームとホストが小文字正規化されることを検証する（RFC 3986準拠）"""
        valid_user_data["website"] = input_url
        user = User(**valid_user_data)
        assert user.website == expected_url

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
        with pytest.raises(ValidationError, match="websiteが空になりました"):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        "userinfo_url",
        [
            "https://legit.com@evil.com",
            "http://legit.com@evil.com",
            "https://attacker@legit.com",
            "legit.com@evil.com",
            "https://:secretpassword@example.com",
        ],
        ids=[
            "https_username_bypass",
            "http_username_bypass",
            "https_attacker_username",
            "schemeless_username_bypass",
            "password_only_bypass",
        ],
    )
    def test_user_website_rejects_userinfo(
        self, valid_user_data: _UserData, userinfo_url: str
    ) -> None:
        """User.website がuserinfo付きURLを拒否すること（RFC 3986 userinfoバイパス防止）"""
        valid_user_data["website"] = userinfo_url
        with pytest.raises(ValidationError, match="URLにuserinfo"):
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

    def test_post_body_exceeds_max_length_raises_validation_error(self) -> None:
        """body>5000文字でValidationErrorが発生する（境界値テスト: max_length=5000）"""
        long_body = "a" * 5001
        with pytest.raises(ValidationError) as exc_info:
            Post(id=1, userId=1, title="Test", body=long_body)
        assert "body" in str(exc_info.value)


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
            pytest.param(field, dirty, expected, id=f"{field}-{id_}")
            for field in ("name", "body")
            for dirty, expected, id_ in _XSS_PAIRS
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

    def test_comment_email_with_ampersand_accepted_by_emailstr(self) -> None:
        """EmailStr は & を含むローカルパートを受理し、html.escape を適用しないこと。

        email-validator は RFC 5321 の dot-atom で & を許容する。
        動作変更時はこのテストが失敗するため、設計の再評価が必要。
        """
        comment = Comment(postId=1, id=1, name="Name", email="user&tag@example.com", body="Body")
        # html.escape は適用されないため & は &amp; に変換されない
        assert comment.email == "user&tag@example.com"


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


class _PhotoBaseData(TypedDict):
    """Photo モデル入力データ型."""

    albumId: int
    id: int
    title: str
    url: str
    thumbnailUrl: str


_PHOTO_BASE: Final[_PhotoBaseData] = {
    "albumId": 1,
    "id": 1,
    "title": "Test Photo",
    "url": "https://example.com/photo.jpg",
    "thumbnailUrl": "https://example.com/thumb.jpg",
}


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
        ("url", "thumbnail_url", "expected_url", "expected_thumbnail"),
        [
            pytest.param(
                "https://via.placeholder.com/600/92c952",
                "https://via.placeholder.com/150/92c952",
                "https://via.placeholder.com/600/92c952",
                "https://via.placeholder.com/150/92c952",
                id="both_https",
            ),
            pytest.param(
                "http://via.placeholder.com/600/92c952",
                "http://via.placeholder.com/150/92c952",
                "http://via.placeholder.com/600/92c952",
                "http://via.placeholder.com/150/92c952",
                id="both_http",
            ),
            pytest.param(
                "https://via.placeholder.com/600/92c952",
                "http://via.placeholder.com/150/92c952",
                "https://via.placeholder.com/600/92c952",
                "http://via.placeholder.com/150/92c952",
                id="mixed_https_http",
            ),
            pytest.param(
                "HTTPS://via.placeholder.com/600/92c952",
                "HTTP://via.placeholder.com/150/92c952",
                "https://via.placeholder.com/600/92c952",
                "http://via.placeholder.com/150/92c952",
                id="uppercase_scheme_normalized",
            ),
        ],
    )
    def test_photo_url_scheme_allows_http_https(
        self, url: str, thumbnail_url: str, expected_url: str, expected_thumbnail: str
    ) -> None:
        """Photo.validate_url_scheme が http/https URLを許可・スキームを小文字正規化すること"""
        photo = Photo(
            albumId=1,
            id=1,
            title="Test",
            url=url,
            thumbnailUrl=thumbnail_url,
        )
        assert photo.url == expected_url
        assert photo.thumbnail_url == expected_thumbnail

    @pytest.mark.parametrize(
        ("url", "thumbnail_url", "expected_url", "expected_thumbnail"),
        [
            pytest.param(
                "HTTPS://Example.COM/photo.jpg",
                "HTTP://Via.Placeholder.COM/150/92c952",
                "https://example.com/photo.jpg",
                "http://via.placeholder.com/150/92c952",
                id="uppercase_host_normalized",
            ),
            pytest.param(
                "https://EXAMPLE.COM/PHOTO.jpg",
                "https://VIA.PLACEHOLDER.COM/thumb.jpg",
                "https://example.com/PHOTO.jpg",
                "https://via.placeholder.com/thumb.jpg",
                id="uppercase_host_only_path_preserved",
            ),
            pytest.param(
                "HTTPS://Example.COM:443/photo.jpg",
                "HTTP://Via.Placeholder.COM:80/thumb.jpg",
                "https://example.com:443/photo.jpg",
                "http://via.placeholder.com:80/thumb.jpg",
                id="uppercase_host_with_port_photo",
            ),
        ],
    )
    def test_photo_validates_host_normalization(
        self,
        url: str,
        thumbnail_url: str,
        expected_url: str,
        expected_thumbnail: str,
    ) -> None:
        """Photo.validate_url_schemeがホスト部を小文字正規化すること（RFC 3986）"""
        photo = Photo(
            albumId=1,
            id=1,
            title="Test",
            url=url,
            thumbnailUrl=thumbnail_url,
        )
        assert photo.url == expected_url
        assert photo.thumbnail_url == expected_thumbnail

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

    @pytest.mark.parametrize(
        ("url", "thumbnail_url"),
        [
            pytest.param(
                "\u200b\u200c\u200d",
                "https://example.com/thumb.jpg",
                id="control_char_only_url",
            ),
            pytest.param(
                "https://via.placeholder.com/600/92c952",
                "\u200b\u200c\u200d",
                id="control_char_only_thumbnail_url",
            ),
        ],
    )
    def test_photo_rejects_control_char_only_url_fields(self, url: str, thumbnail_url: str) -> None:
        """制御文字のみのPhoto url/thumbnail_urlが空文字エラーで拒否されること"""
        with pytest.raises(ValidationError, match="URLが空になりました"):
            Photo(albumId=1, id=1, title="Test", url=url, thumbnailUrl=thumbnail_url)

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param("https:///path", id="empty-netloc-https"),
            pytest.param("http:///path", id="empty-netloc-http"),
            pytest.param("https:///", id="empty-netloc-root"),
        ],
    )
    def test_photo_url_rejects_empty_netloc(self, url: str) -> None:
        """Photo.url に netloc 空の URL が渡されたとき ValidationError を発生させること"""
        with pytest.raises(ValidationError, match="有効なホスト名が含まれていません"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url=url,
                thumbnailUrl="https://example.com/thumb.jpg",
            )

    @pytest.mark.parametrize(
        "thumbnail_url",
        [
            pytest.param("https:///thumb", id="empty-netloc-thumbnail-https"),
            pytest.param("http:///thumb", id="empty-netloc-thumbnail-http"),
        ],
    )
    def test_photo_thumbnail_url_rejects_empty_netloc(self, thumbnail_url: str) -> None:
        """Photo.thumbnail_url に netloc 空の URL が渡されたとき ValidationError を発生させること"""
        with pytest.raises(ValidationError, match="有効なホスト名が含まれていません"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnailUrl=thumbnail_url,
            )

    @pytest.mark.parametrize(
        "url",
        [
            pytest.param("https://attacker@legit.com/photo.jpg", id="https_username_bypass"),
            pytest.param("http://attacker@legit.com/photo.jpg", id="http_username_bypass"),
            pytest.param("https://legit.com@evil.com/photo.jpg", id="https_host_spoof"),
            pytest.param(
                "https://:secretpassword@example.com/photo.jpg", id="password_only_bypass"
            ),
        ],
    )
    def test_photo_url_rejects_userinfo(self, url: str) -> None:
        """Photo.url にuserinfo付きURLが渡されたとき ValidationError を発生させること"""
        with pytest.raises(ValidationError, match="URLにuserinfo"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url=url,
                thumbnailUrl="https://example.com/thumb.jpg",
            )

    @pytest.mark.parametrize(
        "thumbnail_url",
        [
            pytest.param(
                "https://attacker@example.com/photo.jpg",
                id="username_bypass",
            ),
            pytest.param(
                "https://user:pass@example.com/photo.jpg",
                id="full_credentials",
            ),
            pytest.param(
                "https://:secretpassword@example.com/photo.jpg",
                id="password_only_bypass",
            ),
        ],
    )
    def test_photo_thumbnail_url_rejects_userinfo(self, thumbnail_url: str) -> None:
        """Photo.thumbnail_urlがuserinfo付きURLを拒否すること（RFC 3986バイパス防止）"""
        with pytest.raises(ValidationError, match="URLにuserinfo"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnailUrl=thumbnail_url,
            )

    @pytest.mark.parametrize(
        ("url", "thumbnail_url"),
        [
            pytest.param(
                "https://example.com:abc/photo.jpg",
                "https://via.placeholder.com/150",
                id="invalid_port_url",
            ),
            pytest.param(
                "https://via.placeholder.com/600",
                "https://example.com:abc/thumb.jpg",
                id="invalid_port_thumbnail_url",
            ),
        ],
    )
    def test_photo_rejects_invalid_port(self, url: str, thumbnail_url: str) -> None:
        """Photo url/thumbnail_url が無効なポート文字列を拒否すること"""
        with pytest.raises(ValidationError, match="ポートが無効"):
            Photo(albumId=1, id=1, title="Test", url=url, thumbnailUrl=thumbnail_url)

    @pytest.mark.parametrize(
        "dangerous_url",
        [
            "\u200bjavascript:alert(1)",
            "java\u200bscript:alert(1)",
            "\u202ejavascript:alert(1)",
            "java\u2028script:alert(1)",
            "java\u2029script:alert(1)",
        ],
        ids=[
            "zwsp_prefix",
            "zwsp_mid_scheme",
            "bidi_override",
            "line_separator_mid",
            "paragraph_separator_mid",
        ],
    )
    def test_photo_rejects_bidi_control_char_url(self, dangerous_url: str) -> None:
        """Photo.url がBidi/制御文字を含む危険なURLスキームを拒否すること"""
        with pytest.raises(
            ValidationError, match="URLはhttp://またはhttps://で始まる必要があります"
        ):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url=dangerous_url,
                thumbnailUrl="https://example.com/thumb.jpg",
            )

    def test_photo_url_rejects_surrogate_codepoint(self) -> None:
        """孤立サロゲートを含むURLはPydanticのUnicodeバリデーションで拒否されること（E2E）

        Note:
            Pydanticはfield_validator呼び出し前にstring_unicodeエラーで拒否する。
            _strip_invisible_charsのサロゲート除去は直接文字列呼び出し時に機能する。
        """
        with pytest.raises(ValidationError, match="string_unicode"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="https://\ud800example.com/photo.jpg",
                thumbnailUrl="https://via.placeholder.com/150",
            )

    def test_photo_url_rejects_empty_string(self) -> None:
        """Photo.url に空文字列を渡すと ValidationError が発生すること。

        min_length 制約がないため、空文字列は _strip_invisible_chars → .strip() を通過後
        validate_url_scheme のガード節（if not sanitized）に到達する。
        """
        with pytest.raises(ValidationError, match="URLが空になりました"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="",
                thumbnailUrl="https://example.com/thumb.jpg",
            )

    def test_photo_thumbnail_url_strips_bidi(self) -> None:
        """Photo.thumbnail_url の Bidi 制御文字（U+202E）が除去されること"""
        bidi = "\u202e"  # RIGHT-TO-LEFT OVERRIDE (Cf カテゴリ)
        url_with_bidi = f"https://example.com/thumb{bidi}.jpg"
        photo = Photo.model_validate({**_PHOTO_BASE, "thumbnailUrl": url_with_bidi})
        assert bidi not in photo.thumbnail_url
        assert photo.thumbnail_url == "https://example.com/thumb.jpg"

    def test_photo_thumbnail_url_rejects_empty_string(self) -> None:
        """Photo.thumbnail_url に空文字列を渡すと ValidationError が発生すること。"""
        with pytest.raises(ValidationError, match="URLが空になりました"):
            Photo(
                albumId=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnailUrl="",
            )

    @pytest.mark.parametrize(
        ("input_url", "expected_url"),
        [
            pytest.param(
                "https://example.com/path with spaces/file.jpg",
                "https://example.com/path%20with%20spaces/file.jpg",
                id="path_space_encoding",
            ),
            pytest.param(
                "https://example.com/photo.jpg?name=hello world",
                "https://example.com/photo.jpg?name=hello%20world",
                id="query_space_encoding",
            ),
        ],
    )
    def test_photo_url_encodes_special_chars(self, input_url: str, expected_url: str) -> None:
        """_normalize_url の quote() によるパス・クエリのURLエンコード動作を検証する."""
        photo = Photo(
            albumId=1, id=1, title="Test", url=input_url, thumbnailUrl="https://example.com/t.jpg"
        )
        assert photo.url == expected_url


def test_strip_invisible_chars_rejects_non_str() -> None:
    """_strip_invisible_chars は非str型で ValueError を発生させること."""
    with pytest.raises(ValueError, match="文字列が必要です"):
        _strip_invisible_chars(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="文字列が必要です"):
        _strip_invisible_chars(123)  # type: ignore[arg-type]


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
