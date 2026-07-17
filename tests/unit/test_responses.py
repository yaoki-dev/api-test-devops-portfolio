"""Pydanticレスポンスモデルの契約テスト。"""

import re
from typing import Any, Final, TypedDict

import pytest
from pydantic import BaseModel, ValidationError

from models.responses import Address, Album, Comment, Company, Geo, Photo, Post, Todo, User
from models.sanitization import WEBSITE_NORMALIZED_MAX_LENGTH
from tests.types import _UserData  # noqa: PLC2701 - test-internal helper naming preserved
from tests.unit._response_test_vectors import _XSS_MODEL_PARAMS, _XSS_PAIRS

pytestmark = pytest.mark.unit


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


class TestGeoModel:
    """Geo.lat/lngのhtml.escape()サニタイズをOWASP Cheat Sheetベースの独自分類で検証する。"""

    def test_geo_basic_creation(self) -> None:
        geo = Geo(lat="-37.3159", lng="81.1496")

        assert geo.lat == "-37.3159"
        assert geo.lng == "81.1496"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_geo_sanitizes_xss(self, dirty: str, expected: str) -> None:
        geo = Geo(lat=dirty, lng="normal")
        assert geo.lat == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_geo_lng_sanitizes_xss(self, dirty: str, expected: str) -> None:
        geo = Geo(lat="0", lng=dirty)
        assert geo.lng == expected

    def test_geo_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Geo(lat="0", lng="0", extra="not allowed")  # type: ignore[call-arg]

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    @pytest.mark.parametrize(
        ("lat", "lng"),
        [
            pytest.param("0", "0", id="zero_zero"),
            pytest.param("a" * 50, "b" * 50, id="max_length_50"),
            pytest.param("-90.0000", "180.0000", id="typical_coordinate_values"),
        ],
    )
    def test_geo_lat_lng_boundary_values(self, lat: str, lng: str) -> None:
        geo = Geo(lat=lat, lng=lng)
        assert geo.lat == lat
        assert geo.lng == lng

    @pytest.mark.parametrize(
        "field",
        [
            pytest.param("lat", id="lat_too_long"),
            pytest.param("lng", id="lng_too_long"),
        ],
    )
    def test_geo_lat_lng_exceeds_max_length(self, field: str) -> None:
        kwargs = {"lat": "0", "lng": "0"}
        kwargs[field] = "x" * 51
        with pytest.raises(ValidationError, match=field):
            Geo(**kwargs)


class TestAddressModel:
    """Address.streetのhtml.escape()サニタイズをOWASP Cheat Sheetベースの独自分類で検証する。"""

    @pytest.fixture
    def valid_geo(self) -> Geo:
        """XSS サニタイゼーションテスト専用の Address.geo ダミーインスタンス"""
        return Geo(lat="0", lng="0")

    def test_address_basic_creation(self) -> None:
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
        address = Address(street=dirty, suite="Test", city="City", zipcode="12345", geo=valid_geo)
        assert address.street == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    @pytest.mark.parametrize("field", ["suite", "city"])
    def test_address_sanitizes_xss_all_fields(
        self, valid_geo: Geo, dirty: str, expected: str, field: str
    ) -> None:
        kwargs: dict[str, Any] = {
            "street": "Normal",
            "suite": "Normal",
            "city": "Normal",
            "zipcode": "12345",
            "geo": valid_geo,
        }
        kwargs[field] = dirty
        address = Address(**kwargs)
        assert getattr(address, field) == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        [
            pytest.param(
                '" onclick="a"',
                "&quot; onclick=&quot;a&quot;",
                id="attr_injection",
            ),
            pytest.param("Test & Test", "Test &amp; Test", id="special_chars_amp"),
        ],
    )
    def test_address_zipcode_sanitizes_xss(self, valid_geo: Geo, dirty: str, expected: str) -> None:
        """Address.zipcodeのXSSサニタイズを、max_length=20制約に収まるpayloadのみで検証する。"""
        address = Address(
            street="Normal", suite="Normal", city="Normal", zipcode=dirty, geo=valid_geo
        )
        assert address.zipcode == expected

    def test_address_boundary_values(self, valid_geo: Geo) -> None:
        address = Address(
            street="a" * 200,
            suite="b" * 100,
            city="c" * 100,
            zipcode="d" * 20,
            geo=valid_geo,
        )
        assert len(address.street) == 200
        assert len(address.suite) == 100
        assert len(address.city) == 100
        assert len(address.zipcode) == 20

    @pytest.mark.parametrize(
        ("field", "max_len"),
        [
            pytest.param("street", 200, id="street_too_long"),
            pytest.param("suite", 100, id="suite_too_long"),
            pytest.param("city", 100, id="city_too_long"),
            pytest.param("zipcode", 20, id="zipcode_too_long"),
        ],
    )
    def test_address_exceeds_max_length(self, valid_geo: Geo, field: str, max_len: int) -> None:
        kwargs: dict[str, str | Geo] = {
            "street": "Normal",
            "suite": "Normal",
            "city": "Normal",
            "zipcode": "12345",
            "geo": valid_geo,
        }
        kwargs[field] = "x" * (max_len + 1)
        with pytest.raises(ValidationError, match=field):
            Address(**kwargs)


class TestCompanyModel:
    """Company.nameのhtml.escape()サニタイズをOWASP Cheat Sheetベースの独自分類で検証する。"""

    def test_company_basic_creation(self) -> None:
        company = Company(
            name="Romaguera-Crona",
            catch_phrase="Multi-layered client-server neural-net",
            bs="harness real-time e-markets",
        )

        assert company.name == "Romaguera-Crona"
        assert company.catch_phrase == "Multi-layered client-server neural-net"

    def test_company_alias_working(self) -> None:
        # mypy: pydantic.mypy plugin は alias kwarg を field として認識しないため抑制
        # validate_by_name=True により runtime は正常 (alias 動作の意図的検証)
        company = Company(
            name="Test",
            catchPhrase="Test Phrase",  # type: ignore[call-arg]
            bs="test",
        )

        assert company.catch_phrase == "Test Phrase"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_company_sanitizes_xss(self, dirty: str, expected: str) -> None:
        company = Company(name=dirty, catch_phrase="Normal", bs="Normal")
        assert company.name == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    @pytest.mark.parametrize("field", ["catch_phrase", "bs"])
    def test_company_sanitizes_xss_all_fields(self, dirty: str, expected: str, field: str) -> None:
        alias_map = {"catch_phrase": "catchPhrase", "bs": "bs"}
        kwargs: dict[str, Any] = {
            "name": "Normal",
            "catchPhrase": "Normal",
            "bs": "Normal",
        }
        kwargs[alias_map[field]] = dirty
        company = Company(**kwargs)
        assert getattr(company, field) == expected


class TestUserModel:
    """User.name/username/phoneのhtml.escape()サニタイズと、websiteの危険スキーム
    （javascript:/data:/vbscript:）バリデーションをOWASP Cheat Sheetベースの独自分類で検証する。"""

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
        user = User(**valid_user_data)

        assert user.id == 1
        assert user.name == "Leanne Graham"
        assert user.address.city == "Gwenborough"
        assert user.company.name == "Romaguera-Crona"

    def test_user_nested_models(self, valid_user_data: _UserData) -> None:
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
        user = User(**{**valid_user_data, field: dirty})
        assert getattr(user, field) == expected

    def test_user_validate_by_name(self, valid_user_data: _UserData) -> None:
        # User モデルは validate_by_name=True なので、alias で値を設定可能
        user = User(**valid_user_data)
        assert user.company.catch_phrase == "Multi-layered client-server neural-net"

    def test_user_extra_fields_forbidden(self, valid_user_data: _UserData) -> None:
        valid_user_data["extra_field"] = "not allowed"  # type: ignore[typeddict-unknown-key]

        with pytest.raises(ValidationError) as exc_info:
            User(**valid_user_data)

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"

    def test_user_email_must_be_valid_format(self, valid_user_data: _UserData) -> None:
        valid_user_data["email"] = "not-an-email"
        with pytest.raises(ValidationError, match=r"email"):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        "invalid_email",
        [
            pytest.param("user@", id="missing_domain"),
            pytest.param("@domain.com", id="missing_local_part"),
            pytest.param(".start@example.com", id="leading_dot_local"),
            pytest.param("user..double@example.com", id="consecutive_dots"),
            pytest.param("user@.domain.com", id="leading_dot_domain"),
            pytest.param("", id="empty_string"),
        ],
    )
    def test_user_email_rejects_rfc_noncompliant(
        self, valid_user_data: _UserData, invalid_email: str
    ) -> None:
        valid_user_data["email"] = invalid_email
        with pytest.raises(ValidationError, match=r"email"):
            User(**valid_user_data)

    def test_user_email_max_length_valid(self, valid_user_data: _UserData) -> None:
        # 52 + "@"(1) + 35 + ".example.com"(12) = 100文字（local≤64: RFC5321準拠）
        valid_user_data["email"] = "a" * 52 + "@" + "b" * 35 + ".example.com"
        user = User(**valid_user_data)
        assert len(user.email) == 100

    def test_user_email_max_length_invalid(self, valid_user_data: _UserData) -> None:
        # 52 + "@"(1) + 36 + ".example.com"(12) = 101文字（local≤64: RFC5321準拠）
        # emailフィールドのloc確認で検証（email-validatorバージョン依存のmatch文字列を回避）
        valid_user_data["email"] = "a" * 52 + "@" + "b" * 36 + ".example.com"
        with pytest.raises(ValidationError) as exc_info:
            User(**valid_user_data)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("email",) for e in errors), (
            f"emailフィールドのバリデーションエラーが期待されたが: {errors}"
        )

    def test_user_website_max_length_boundary(self, valid_user_data: _UserData) -> None:
        max_len = WEBSITE_NORMALIZED_MAX_LENGTH  # 2048
        base = "https://example.com/"
        # ちょうど max_len 文字: 正常
        path = "a" * (max_len - len(base))
        valid_user_data["website"] = base + path
        user = User(**valid_user_data)
        assert len(user.website) == max_len

        # スキームなし → https:// 補完後に max_len 超過
        domain_suffix = ".example.com"
        pad = max_len - len("https://") - len(domain_suffix) + 1
        schemeless = "a" * pad + domain_suffix
        valid_user_data["website"] = schemeless
        with pytest.raises(
            ValidationError,
            match=r"URL length after normalization exceeds limit",
        ):
            User(**valid_user_data)

        # max_len + 1 文字: ValidationError
        valid_user_data["website"] = base + "a" * (max_len + 1 - len(base))
        with pytest.raises(ValidationError, match=r"URL length after normalization exceeds limit"):
            User(**valid_user_data)

    def test_user_website_is_not_html_escaped(self, valid_user_data: _UserData) -> None:
        value = "https://example.com/page?a=1&b=2"
        valid_user_data["website"] = value
        user = User(**valid_user_data)
        assert user.website == "https://example.com/page?a=1&b=2"  # &amp; にならないことを確認

    @pytest.mark.parametrize(
        ("dangerous_url", "expected_match"),
        [
            pytest.param("javascript:alert(1)", "Dangerous URL scheme detected", id="js_basic"),
            pytest.param("JAVASCRIPT:alert(1)", "Dangerous URL scheme detected", id="js_uppercase"),
            pytest.param("javascript:void(0)", "Dangerous URL scheme detected", id="js_void"),
            pytest.param(
                "data:text/html,<script>alert(1)</script>",
                "Dangerous URL scheme detected",
                id="data_html",
            ),
            pytest.param(
                "Data:image/png;base64,abc", "Dangerous URL scheme detected", id="data_image"
            ),
            pytest.param("vbscript:msgbox(1)", "Dangerous URL scheme detected", id="vbscript"),
            pytest.param(
                " javascript:alert(1)", "Dangerous URL scheme detected", id="js_leading_space"
            ),
            pytest.param(
                "\tjavascript:void(0)", "Dangerous URL scheme detected", id="js_leading_tab"
            ),
            pytest.param(
                "\u200bjavascript:alert(1)",
                "Dangerous URL scheme detected",
                id="js_zwsp_prefix",
            ),
            pytest.param(
                "java\u200bscript:alert(1)",
                "Dangerous URL scheme detected",
                id="js_zwsp_mid_scheme",
            ),
            pytest.param(
                "\u202ejavascript:alert(1)",
                "Dangerous URL scheme detected",
                id="js_bidi_override",
            ),
            pytest.param(
                "j\u00a0avascript:alert(1)",
                "Dangerous URL scheme detected",
                id="js_nbsp_mid_scheme",
            ),
            pytest.param(
                "\u2060javascript:alert(1)",
                "Dangerous URL scheme detected",
                id="js_word_joiner_prefix",
            ),
            pytest.param(
                "\u2066javascript:alert(1)", "Dangerous URL scheme detected", id="js_lri_prefix"
            ),
            pytest.param(
                "\u2069javascript:alert(1)", "Dangerous URL scheme detected", id="js_pdi_prefix"
            ),
            pytest.param(
                "vbs\u200bcript:msgbox(1)",
                "Dangerous URL scheme detected",
                id="vbscript_zwsp_mid",
            ),
            pytest.param(
                "da\u200bta:text/html,x", "Dangerous URL scheme detected", id="data_zwsp_mid"
            ),
            pytest.param(
                "vbscript\u202e:msgbox(1)",
                "Dangerous URL scheme detected",
                id="vbscript_bidi_override",
            ),
            pytest.param(
                "da\u200bta:image/png;base64,abc",
                "Dangerous URL scheme detected",
                id="data_zwsp_mid_image",
            ),
            pytest.param(
                "java\u2028script:alert(1)",
                "Dangerous URL scheme detected",
                id="js_line_separator_mid",
            ),
            pytest.param(
                "java\u2029script:alert(1)",
                "Dangerous URL scheme detected",
                id="js_paragraph_separator_mid",
            ),
            pytest.param("ftp://evil.com", "Dangerous URL scheme detected", id="ftp_scheme"),
            pytest.param("file:///etc/passwd", "Dangerous URL scheme detected", id="file_scheme"),
            pytest.param(
                "blob:https://evil.com/uuid", "Dangerous URL scheme detected", id="blob_scheme"
            ),
            pytest.param(
                "javascript:0", "Dangerous URL scheme detected", id="js_digit_after_colon"
            ),
            pytest.param(
                "javascript:1+1",
                "Dangerous URL scheme detected",
                id="js_expression_after_colon",
            ),
            pytest.param(
                "malicious.js:xyz", "Dangerous URL scheme detected", id="dotted_scheme_non_port"
            ),
            pytest.param(
                "a.b:evil",
                "Dangerous URL scheme detected",
                id="dotted_scheme_alpha_after_colon",
            ),
            # domain:portはRFC 3986スキーム正規表現(_SCHEME_RE)にマッチするため
            # 「危険なスキーム」パスに到達する（IPアドレスの場合はマッチしない）
            pytest.param(
                "example.com:8080", "Dangerous URL scheme detected", id="domain_port_no_scheme"
            ),
            pytest.param(
                "sub.domain.com:443/path",
                "Dangerous URL scheme detected",
                id="subdomain_port_path_no_scheme",
            ),
            pytest.param(
                "example.com:8080/path?query=1",
                "Dangerous URL scheme detected",
                id="domain_port_path_query_no_scheme",
            ),
            pytest.param(
                "192.168.1.1:8080",
                "Scheme-less URL cannot contain a port",
                id="ip_port_no_scheme",
            ),
            pytest.param(
                "10.0.0.1:3000/api",
                "Scheme-less URL cannot contain a path",
                id="ip_port_path_no_scheme",
            ),
            pytest.param(
                "/path/only",
                "Scheme-less URL cannot contain a path",
                id="path_only_no_host",
            ),
            pytest.param(
                "java\ufe00script:alert(1)",
                "Dangerous URL scheme detected",
                id="js_variation_selector_mn_bypass",
            ),
            pytest.param(
                "java\U000e0100script:alert(1)",
                "Dangerous URL scheme detected",
                id="js_variation_selector_supplement_mn_bypass",
            ),
        ],
    )
    def test_user_website_rejects_dangerous_scheme(
        self, valid_user_data: _UserData, dangerous_url: str, expected_match: str
    ) -> None:
        valid_user_data["website"] = dangerous_url
        with pytest.raises(ValidationError, match=expected_match):
            User(**valid_user_data)

    def test_user_website_rejects_protocol_relative_url(self, valid_user_data: _UserData) -> None:
        valid_user_data["website"] = "//cdn.example.com/image.jpg"
        with pytest.raises(
            ValidationError, match=re.escape("Protocol-relative URLs are not allowed")
        ):
            User(**valid_user_data)

    def test_user_website_rejects_fullwidth_javascript_scheme(
        self, valid_user_data: _UserData
    ) -> None:
        """全角文字によるスキームバイパスをNFKC正規化で検出し拒否することを検証する。"""
        valid_user_data["website"] = "ｊａｖａｓｃｒｉｐｔ:alert(1)"
        with pytest.raises(ValidationError, match=re.escape("Dangerous URL scheme detected")):
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
        valid_user_data["website"] = empty_netloc_url
        with pytest.raises(ValidationError, match=re.escape("Valid hostname not found")):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        "invalid_host_url",
        [
            pytest.param("https://example .com", id="schemeful_host_space"),
            pytest.param("example .com", id="schemeless_host_space"),
        ],
    )
    def test_user_website_rejects_ascii_whitespace_in_host(
        self, valid_user_data: _UserData, invalid_host_url: str
    ) -> None:
        valid_user_data["website"] = invalid_host_url
        with pytest.raises(ValidationError, match=re.escape("Hostname contains whitespace")):
            User(**valid_user_data)

    def test_user_website_wraps_overflowerror_in_validationerror(
        self, valid_user_data: _UserData, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _OverflowingParseResult:
            scheme = "https"
            netloc = "example.com"
            path = ""
            params = ""
            query = ""
            fragment = ""

            @property
            def port(self) -> None:
                return None

            @property
            def username(self) -> None:
                return None

            @property
            def password(self) -> str:
                raise OverflowError("simulated overflow during password access")

            @property
            def hostname(self) -> str:
                return "example.com"

        def fake_urlparse(_: str) -> _OverflowingParseResult:
            return _OverflowingParseResult()

        # URL 検証は models.sanitization に委譲済みのため、urlparse はそちらを patch する
        monkeypatch.setattr("models.sanitization.urlparse", fake_urlparse)
        valid_user_data["website"] = "https://example.com"

        with pytest.raises(ValidationError, match=re.escape("Failed to parse userinfo from URL")):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        ("dangerous_url", "expected_match"),
        [
            pytest.param(
                "https://example.com:abc/",
                "Invalid port",
                id="invalid_port_string",
            ),
            pytest.param(
                "%0d%0aevil.com",
                "percent-encoded control characters",
                id="percent_encoded_crlf_injection",
            ),
            pytest.param(
                "%0d%0a//evil.com",
                "percent-encoded control characters",
                id="percent_encoded_crlf_slash_bypass",
            ),
            pytest.param(
                "%7f",
                "percent-encoded control characters",
                id="percent_encoded_del_character",
            ),
            pytest.param(
                "%2f%2fevil.com",
                "Scheme-less URL cannot contain a path",
                id="percent_encoded_slash_bypass",
            ),
            pytest.param(
                "example.com/path",
                "Scheme-less URL cannot contain a path",
                id="schemeless_with_path",
            ),
            pytest.param(
                "example.com%2Fpath",
                "Scheme-less URL cannot contain a path",
                id="schemeless_with_encoded_path",
            ),
            pytest.param(
                "https://evil<script>xss</script>.example.com/path",
                "Hostname contains invalid characters",
                id="xss_metachar_in_netloc",
            ),
            pytest.param(
                "Example.COM/path",
                "Scheme-less URL cannot contain a path",
                id="schemeless_uppercase_host_with_path",
            ),
            pytest.param(
                "https://example.com%80",
                "invalid percent-encoding",
                id="invalid_utf8_percent_encoding_https",
            ),
            pytest.param(
                "example.com%80",
                "invalid percent-encoding",
                id="invalid_utf8_percent_encoding",
            ),
        ],
    )
    def test_user_website_rejects_security_bypass_patterns(
        self, valid_user_data: _UserData, dangerous_url: str, expected_match: str
    ) -> None:
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
        valid_user_data["website"] = non_str_input  # type: ignore[typeddict-item]
        with pytest.raises(ValidationError, match=re.escape("String required")):
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
        ],
    )
    def test_user_website_allows_safe_url(
        self, valid_user_data: _UserData, input_url: str, expected_url: str
    ) -> None:
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
        """制御文字のみのwebsiteはサニタイズ後に空文字列となるため、ValidationErrorになることを検証する。"""
        valid_user_data["website"] = control_only
        with pytest.raises(ValidationError, match=re.escape("Website became empty")):
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
        with pytest.raises(ValidationError, match=re.escape("URL cannot contain userinfo")):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        ("input_url", "expected_url"),
        [
            pytest.param(
                "https://example.com/my page",
                "https://example.com/my%20page",
                id="path_space_encoding",
            ),
            pytest.param(
                "https://example.com/page#<xss>",
                "https://example.com/page#%3Cxss%3E",
                id="fragment_xss_encoding",
            ),
            pytest.param(
                "https://example.com/page#already%20encoded",
                "https://example.com/page#already%20encoded",
                id="fragment_no_double_encoding",
            ),
            pytest.param(
                "https://example.com/search?nested?key=val",
                "https://example.com/search?nested?key=val",
                id="query_literal_question_mark_preserved",
            ),
            pytest.param(
                "https://example.com/search?q=<script>",
                "https://example.com/search?q=%3Cscript%3E",
                id="query_lt_gt_xss_encoding",
            ),
            pytest.param(
                "https://example.com/search?q=alert('xss')",
                "https://example.com/search?q=alert(%27xss%27)",
                id="query_single_quote_encoding",
            ),
            pytest.param(
                "https://example.com/search?q=<script>alert('xss')</script>",
                "https://example.com/search?q=%3Cscript%3Ealert(%27xss%27)%3C/script%3E",
                id="query_combined_xss_payload_encoding",
            ),
        ],
    )
    def test_user_website_encodes_special_chars(
        self, valid_user_data: _UserData, input_url: str, expected_url: str
    ) -> None:
        valid_user_data["website"] = input_url
        user = User(**valid_user_data)
        assert user.website == expected_url

    def test_user_website_rejects_percent_encoded_at_with_literal_at(
        self, valid_user_data: _UserData
    ) -> None:
        """urlparseが%40エンコード済み@と@リテラル混在をuserinfoと解釈しバイパスされることを防ぐ契約を検証する。"""
        valid_user_data["website"] = "https://user%40evil.com@host.example.com"
        with pytest.raises(ValidationError, match=re.escape("URL cannot contain userinfo")):
            User(**valid_user_data)

    @pytest.mark.parametrize(
        "bad_url",
        [
            pytest.param("http://example.com/%GG", id="incomplete_pct_gg"),
            pytest.param("http://example.com/path%", id="incomplete_pct_bare"),
        ],
    )
    def test_user_website_rejects_incomplete_percent_encoding(
        self, valid_user_data: _UserData, bad_url: str
    ) -> None:
        """%GGや末尾%は_PERCENT_CTRL_REでなく_INCOMPLETE_PCT_REにマッチしてValidationErrorになる契約を検証する。"""
        valid_user_data["website"] = bad_url
        with pytest.raises(ValidationError, match=re.escape("incomplete percent-encoding")):
            User(**valid_user_data)


class TestPostModel:
    def test_post_basic_creation(self) -> None:
        post = Post(user_id=1, id=1, title="Test Title", body="Test Body")

        assert post.user_id == 1
        assert post.title == "Test Title"

    def test_post_alias_working(self) -> None:
        # mypy: pydantic.mypy plugin は alias kwarg を field として認識しないため抑制
        # validate_by_name=True により runtime は正常 (alias 動作の意図的検証)
        post = Post(userId=5, id=1, title="Test", body="Test")  # type: ignore[call-arg]

        assert post.user_id == 5

    def test_post_alias_compatibility(self) -> None:
        """Pydantic移行時のalias⇄属性ラウンドトリップ退行を防ぐため、userId⇄user_idの往復変換を検証する。"""
        data = {"userId": 1, "id": 1, "title": "title", "body": "body"}
        post = Post.model_validate(data)

        assert post.user_id == data["userId"]
        assert post.model_dump(by_alias=True)["userId"] == data["userId"]

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_post_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        post = Post(user_id=1, id=1, title=dirty, body="Normal body")
        assert post.title == expected

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_post_body_sanitizes_xss(self, dirty: str, expected: str) -> None:
        post = Post(user_id=1, id=1, title="Normal title", body=dirty)
        assert post.body == expected

    @pytest.mark.parametrize(
        "invalid_id",
        [
            pytest.param(0, id="zero"),
            pytest.param(-1, id="negative"),
        ],
    )
    def test_post_invalid_id_raises_validation_error(self, invalid_id: int) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Post(id=invalid_id, user_id=1, title="Test", body="Body")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("id",) and e["type"] == "greater_than_equal" for e in errors)

    def test_post_title_max_length_valid(self) -> None:
        post = Post(id=1, user_id=1, title="a" * 200, body="Body")
        assert len(post.title) == 200

    def test_post_title_max_length_invalid(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Post(id=1, user_id=1, title="a" * 201, body="Body")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("title",) and e["type"] == "string_too_long" for e in errors)

    def test_post_body_exceeds_max_length_raises_validation_error(self) -> None:
        long_body = "a" * 5001
        with pytest.raises(ValidationError) as exc_info:
            Post(id=1, user_id=1, title="Test", body=long_body)
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("body",) and e["type"] == "string_too_long" for e in errors)

    def test_post_body_max_length_valid(self) -> None:
        post = Post(title="T", body="a" * 5000, user_id=1, id=1)
        assert len(post.body) == 5000


class TestCommentModel:
    """Comment.name/bodyのhtml.escape()サニタイズをOWASP Cheat Sheetベースの独自分類で検証する。"""

    def test_comment_basic_creation(self) -> None:
        comment = Comment(
            post_id=1,
            id=1,
            name="Test Name",
            email="test@example.com",
            body="Test Comment",
        )

        assert comment.post_id == 1
        assert comment.email == "test@example.com"

    def test_comment_alias_compatibility(self) -> None:
        """Pydantic移行時のalias⇄属性ラウンドトリップ退行を防ぐため、postId⇄post_idの往復変換を検証する。"""
        data = {
            "postId": 1,
            "id": 1,
            "name": "name",
            "email": "test@example.com",
            "body": "body",
        }
        comment = Comment.model_validate(data)

        assert comment.post_id == data["postId"]
        assert comment.model_dump(by_alias=True)["postId"] == data["postId"]

    @pytest.mark.parametrize(
        ("field", "dirty", "expected"),
        [
            pytest.param(field, dirty, expected, id=f"{field}-{id_}")
            for field in ("name", "body")
            for dirty, expected, id_ in _XSS_PAIRS
        ],
    )
    def test_comment_sanitizes_xss(self, field: str, dirty: str, expected: str) -> None:
        data: dict[str, str | int] = {**_COMMENT_BASE, field: dirty}  # type: ignore[dict-item]
        comment = Comment.model_validate(data)
        assert getattr(comment, field) == expected

    def test_comment_email_must_be_valid_format(self) -> None:
        with pytest.raises(ValidationError, match=r"email"):
            Comment(post_id=1, id=1, name="Name", email="not-an-email", body="Body")

    def test_comment_email_max_length_valid(self) -> None:
        # 52 + "@"(1) + 35 + ".example.com"(12) = 100文字（local≤64: RFC5321準拠）
        long_email = "a" * 52 + "@" + "b" * 35 + ".example.com"
        comment = Comment(post_id=1, id=1, name="Name", email=long_email, body="Body")
        assert len(comment.email) == 100

    def test_comment_email_max_length_invalid(self) -> None:
        # 52 + "@"(1) + 36 + ".example.com"(12) = 101文字（local≤64: RFC5321準拠）
        # emailフィールドのloc確認で検証（email-validatorバージョン依存のmatch文字列を回避）
        long_email = "a" * 52 + "@" + "b" * 36 + ".example.com"
        with pytest.raises(ValidationError) as exc_info:
            Comment(post_id=1, id=1, name="Name", email=long_email, body="Body")
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("email",) for e in errors), (
            f"emailフィールドのバリデーションエラーが期待されたが: {errors}"
        )

    def test_comment_email_with_ampersand_accepted_by_emailstr(self) -> None:
        """email-validatorがRFC 5321 dot-atomで&を許容しhtml.escapeが非適用となる仕様を保護する。"""
        comment = Comment(post_id=1, id=1, name="Name", email="user&tag@example.com", body="Body")
        # html.escape は適用されないため & は &amp; に変換されない
        assert comment.email == "user&tag@example.com"

    def test_comment_email_rejects_html_meta_chars(self) -> None:
        """EmailStrが<>を含むアドレスを拒否するため、html.escapeを適用しなくても安全である根拠を検証する。"""
        with pytest.raises(ValidationError):
            Comment(post_id=1, id=1, name="Name", email="<xss>@evil.com", body="Body")
        with pytest.raises(ValidationError):
            Comment(post_id=1, id=1, name="Name", email="user&amp;@evil.com", body="Body")


class TestTodoModel:
    def test_todo_basic_creation(self) -> None:
        todo = Todo(user_id=1, id=1, title="Test TODO", completed=False)

        assert todo.user_id == 1
        assert todo.title == "Test TODO"
        assert todo.completed is False

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_todo_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        todo = Todo(user_id=1, id=1, title=dirty, completed=False)
        assert todo.title == expected


class TestAlbumModel:
    def test_album_basic_creation(self) -> None:
        album = Album(user_id=1, id=1, title="Test Album")

        assert album.user_id == 1
        assert album.title == "Test Album"

    @pytest.mark.parametrize(
        ("dirty", "expected"),
        _XSS_MODEL_PARAMS,
    )
    def test_album_title_sanitizes_xss(self, dirty: str, expected: str) -> None:
        album = Album(user_id=1, id=1, title=dirty)
        assert album.title == expected


class TestExtraFieldsForbidden:
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
        model_class: type[BaseModel],
        valid_data: dict[str, Any],
        extra_field: dict[str, Any],
    ) -> None:
        invalid_data = {**valid_data, **extra_field}

        with pytest.raises(ValidationError) as exc_info:
            model_class(**invalid_data)

        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"
