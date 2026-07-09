"""Pydantic URL検証 テスト"""

import re
from typing import Final, TypedDict
from urllib.parse import urlparse

import pytest
from pydantic import ValidationError

from models.responses import Photo
from models.sanitization import normalize_url, validate_scheme_less_url
from tests.unit._response_test_vectors import _XSS_MODEL_PARAMS

pytestmark = pytest.mark.unit


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
            album_id=1,
            id=1,
            title="Test Photo",
            url="https://via.placeholder.com/600/92c952",
            thumbnail_url="https://via.placeholder.com/150/92c952",
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
            album_id=1,
            id=1,
            title="Test",
            url=url,
            thumbnail_url=thumbnail_url,
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
            album_id=1,
            id=1,
            title="Test",
            url=url,
            thumbnail_url=thumbnail_url,
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
            album_id=1,
            id=1,
            title=dirty,
            url="https://example.com/photo.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
        )
        assert photo.title == expected

    def test_photo_rejects_javascript_url(self) -> None:
        """Photo モデルが javascript: スキームを拒否することを確認"""
        with pytest.raises(ValidationError) as exc_info:
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="javascript:alert('XSS')",
                thumbnail_url="https://example.com/thumb.jpg",
            )

        assert "URL must start with http:// or https://" in str(exc_info.value)

    def test_photo_rejects_data_url(self) -> None:
        """Photo モデルが data: スキームを拒否することを確認"""
        with pytest.raises(ValidationError) as exc_info:
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnail_url="data:image/png;base64,iVBORw0KGgo=",
            )

        assert "URL must start with http:// or https://" in str(exc_info.value)

    def test_photo_rejects_schemeless_url(self) -> None:
        """Photo.url がスキームなしURLを拒否すること"""
        with pytest.raises(
            ValidationError, match=re.escape("URL must start with http:// or https://")
        ):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="example.com/photo.jpg",
                thumbnail_url="https://example.com/thumb.jpg",
            )

    def test_photo_rejects_schemeless_thumbnail_url(self) -> None:
        """Photo.thumbnail_url がスキームなしURLを拒否すること"""
        with pytest.raises(
            ValidationError, match=re.escape("URL must start with http:// or https://")
        ):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnail_url="example.com/thumb.jpg",
            )

    @pytest.mark.parametrize(
        ("url", "thumbnail_url", "expected_match"),
        [
            pytest.param(
                "https://evil.com%0d%0aInjected",
                "https://example.com/thumb.jpg",
                "percent-encoded control characters",
                id="crlf_in_url",
            ),
            pytest.param(
                "https://example.com/photo.jpg",
                "https://evil.com%0aInjected",
                "percent-encoded control characters",
                id="lf_in_thumbnail",
            ),
            pytest.param(
                "https://example.com%0D%0A/photo.jpg",
                "https://example.com/thumb.jpg",
                "percent-encoded control characters",
                id="uppercase_crlf_in_url",
            ),
        ],
    )
    def test_photo_rejects_percent_encoded_crlf(
        self, url: str, thumbnail_url: str, expected_match: str
    ) -> None:
        """Photo.validate_url_scheme がパーセントエンコードされたCRLFを拒否すること"""
        with pytest.raises(ValidationError, match=expected_match):
            Photo(album_id=1, id=1, title="Test", url=url, thumbnail_url=thumbnail_url)

    @pytest.mark.parametrize(
        ("field_key", "bad_url"),
        [
            pytest.param("url", "https://example.com/%GG/path.jpg", id="url_incomplete_pct_gg"),
            pytest.param("url", "https://example.com/path%", id="url_incomplete_pct_bare"),
            pytest.param(
                "thumbnailUrl",
                "https://example.com/thumb%GG.jpg",
                id="thumbnail_incomplete_pct_gg",
            ),
        ],
    )
    def test_photo_rejects_incomplete_percent_encoding(self, field_key: str, bad_url: str) -> None:
        """Photo url/thumbnail_url が不完全なパーセントエンコードを拒否すること."""
        with pytest.raises(ValidationError, match=re.escape("incomplete percent-encoding")):
            Photo.model_validate({**_PHOTO_BASE, field_key: bad_url})

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
        with pytest.raises(ValidationError, match=re.escape("URL became empty")):
            Photo(album_id=1, id=1, title="Test", url=url, thumbnail_url=thumbnail_url)

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
        with pytest.raises(ValidationError, match=re.escape("Valid hostname not found")):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url=url,
                thumbnail_url="https://example.com/thumb.jpg",
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
        with pytest.raises(ValidationError, match=re.escape("Valid hostname not found")):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnail_url=thumbnail_url,
            )

    @pytest.mark.parametrize("field_name", ["url", "thumbnail_url"], ids=["url", "thumbnail"])
    def test_photo_rejects_ascii_whitespace_in_host(self, field_name: str) -> None:
        """Photo の URL フィールドがホスト部のASCII空白を拒否すること."""
        key = "url" if field_name == "url" else "thumbnailUrl"
        with pytest.raises(ValidationError, match=re.escape("Hostname contains whitespace")):
            Photo.model_validate({**_PHOTO_BASE, key: "https://example .com/photo.jpg"})

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
        with pytest.raises(ValidationError, match=re.escape("URL cannot contain userinfo")):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url=url,
                thumbnail_url="https://example.com/thumb.jpg",
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
        with pytest.raises(ValidationError, match=re.escape("URL cannot contain userinfo")):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnail_url=thumbnail_url,
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
        with pytest.raises(ValidationError, match=re.escape("Invalid port")):
            Photo(album_id=1, id=1, title="Test", url=url, thumbnail_url=thumbnail_url)

    # Photo URL危険ペイロード共通定数（両フィールド同一バリデータ共有のため再利用）
    _PHOTO_DANGEROUS_URLS: Final = [
        pytest.param("\u200bjavascript:alert(1)", id="zwsp_prefix"),
        pytest.param("java\u200bscript:alert(1)", id="zwsp_mid_scheme"),
        pytest.param("\u202ejavascript:alert(1)", id="bidi_override"),
        pytest.param("java\u2028script:alert(1)", id="line_separator_mid"),
        pytest.param("java\u2029script:alert(1)", id="paragraph_separator_mid"),
        pytest.param("java\ufe00script:alert(1)", id="variation_selector_vs1"),
        pytest.param("java\ufe0fscript:alert(1)", id="variation_selector_vs16"),
        pytest.param(
            "java\U000e0100script:alert(1)",
            id="variation_selector_supplement_min",
        ),
        pytest.param(
            "java\U000e01efscript:alert(1)",
            id="variation_selector_supplement_max",
        ),
    ]

    @pytest.mark.parametrize(
        "dangerous",
        _PHOTO_DANGEROUS_URLS,
    )
    def test_photo_url_rejects_invisible_char_dangerous_scheme(self, dangerous: str) -> None:
        """Photo.url が不可視文字で難読化された危険スキームを拒否すること。

        url と thumbnail_url は同一の validate_url_scheme バリデータを共有するため、
        url フィールドでの全件検証でバリデータロジックを網羅。
        thumbnail_url 側は alias バインド確認のみ別テストで実施（保守性・二重メンテ防止）。
        """
        with pytest.raises(
            ValidationError, match=re.escape("URL must start with http:// or https://")
        ):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url=dangerous,
                thumbnail_url="https://example.com/photo.jpg",
            )

    @pytest.mark.parametrize(
        "dangerous",
        [
            pytest.param("\u200bjavascript:alert(1)", id="zwsp_prefix_alias"),
            pytest.param("java\ufe0fscript:alert(1)", id="variation_selector_vs16_alias"),
        ],
    )
    def test_photo_thumbnail_url_alias_rejects_invisible_char_dangerous_scheme(
        self, dangerous: str
    ) -> None:
        """Photo.thumbnailUrl(alias) が同一バリデータで危険スキームを拒否すること。

        alias 入力経路（thumbnailUrl=）でのバインド検証のみ実施。
        バリデータロジック検証は test_photo_url_rejects_invisible_char_dangerous_scheme に委譲。
        """
        with pytest.raises(
            ValidationError, match=re.escape("URL must start with http:// or https://")
        ):
            # model_validate で外部入力（alias 名を含む辞書）をシミュレート
            Photo.model_validate(
                {
                    "album_id": 1,
                    "id": 1,
                    "title": "Test",
                    "url": "https://example.com/photo.jpg",
                    "thumbnailUrl": dangerous,  # alias 名を含む辞書で検証
                }
            )

    # 不可視文字を1クラス1文字で列挙（escape表記で可視化）。各クラスの除去感度検証に使用。
    _PHOTO_INVISIBLE_CHARS: Final = [
        pytest.param("\u200b", id="zwsp"),
        pytest.param("\u202e", id="bidi_override"),
        pytest.param("\u2028", id="line_separator"),
        pytest.param("\u2029", id="paragraph_separator"),
        pytest.param("\x01", id="c0_control"),
        pytest.param("\ufe00", id="variation_selector_vs1"),
        pytest.param("\ufe0f", id="variation_selector_vs16"),
        pytest.param("\U000e0100", id="variation_selector_supplement_min"),
        pytest.param("\U000e01ef", id="variation_selector_supplement_max"),
    ]

    @pytest.mark.parametrize("invisible", _PHOTO_INVISIBLE_CHARS)
    def test_photo_url_strips_invisible_chars(self, invisible: str) -> None:
        """url に埋め込まれた各クラスの不可視文字が除去され正規URLになること（除去感度検証）。

        難読化スキーム拒否テストは「http以外」の catch-all で弾くため、不可視文字が実際に
        除去されたかを判別できない（除去が壊れても非httpとして拒否され緑のまま）。本テストは
        正規httpURLに不可視文字を埋め込み、除去後に等価な正規URLへ正規化されることを表明し、
        strip_invisible_chars の各カテゴリ除去ロジックの回帰を直接検出する。
        """
        photo = Photo(
            album_id=1,
            id=1,
            title="Test",
            url=f"https://example.com/pho{invisible}to.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
        )
        assert photo.url == "https://example.com/photo.jpg"

    def test_photo_url_rejects_surrogate_codepoint(self) -> None:
        """孤立サロゲートを含むURLはPydanticのUnicodeバリデーションで拒否されること（E2E）

        Note:
            Pydanticはfield_validator呼び出し前にstring_unicodeエラーで拒否する。
            strip_invisible_charsのサロゲート除去は直接文字列呼び出し時に機能する。
        """
        with pytest.raises(ValidationError, match=re.escape("string_unicode")):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="https://\ud800example.com/photo.jpg",
                thumbnail_url="https://via.placeholder.com/150",
            )

    def test_photo_url_rejects_empty_string(self) -> None:
        """Photo.url に空文字列を渡すと ValidationError が発生すること。

        min_length 制約がないため、空文字列は strip_invisible_chars → .strip() を通過後
        validate_url_scheme のガード節（if not sanitized）に到達する。
        """
        with pytest.raises(ValidationError, match=re.escape("URL became empty")):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="",
                thumbnail_url="https://example.com/thumb.jpg",
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
        with pytest.raises(ValidationError, match=re.escape("URL became empty")):
            Photo(
                album_id=1,
                id=1,
                title="Test",
                url="https://example.com/photo.jpg",
                thumbnail_url="",
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
            pytest.param(
                "https://example.com/page#sec<xss>",
                "https://example.com/page#sec%3Cxss%3E",
                id="fragment_xss_encoding",
            ),
            pytest.param(
                "https://example.com/page#already%20encoded",
                "https://example.com/page#already%20encoded",
                id="fragment_no_double_encoding",
            ),
        ],
    )
    def test_photo_url_encodes_special_chars(self, input_url: str, expected_url: str) -> None:
        """_normalize_url の quote() によるパス・クエリのURLエンコード動作を検証する."""
        photo = Photo(
            album_id=1, id=1, title="Test", url=input_url, thumbnail_url="https://example.com/t.jpg"
        )
        assert photo.url == expected_url

    @pytest.mark.parametrize("field_name", ["url", "thumbnail_url"], ids=["url", "thumbnail"])
    def test_photo_rejects_normalized_length_overflow(self, field_name: str) -> None:
        """Photo のURLは正規化後も 2048 文字以内である必要があることを検証する。"""
        long_path = "あ" * 250
        key = "url" if field_name == "url" else "thumbnailUrl"
        photo_data = {
            **_PHOTO_BASE,
            key: f"https://example.com/{long_path}",
        }
        with pytest.raises(
            ValidationError,
            match=r"URL length after normalization exceeds limit",
        ):
            Photo.model_validate(photo_data)

    def test_photo_url_rejects_percent_encoded_at_with_literal_at(self) -> None:
        """%40エンコード済み@と@リテラル混在のuserinfoバイパスを拒否すること.

        urlparse は "user%40evil.com@host.example.com" をuserinfoとして解析するため、
        URLにuserinfoが含まれると判定しValidationErrorを発生させる。
        """
        with pytest.raises(ValidationError, match=re.escape("URL cannot contain userinfo")):
            Photo(**{**_PHOTO_BASE, "url": "https://user%40evil.com@host.example.com/path.jpg"})

    def test_photo_url_rejects_percent_encoded_at_in_host(self) -> None:
        """%40（エンコード済み@）を含むURLはuserinfoバイパスとして拒否すること.

        urlparse は "user%40evil.com" をhostname全体として解析するが、
        unquote後に@が検出されるためセキュリティ上拒否する。
        """
        with pytest.raises(ValidationError, match=re.escape("userinfo")):
            Photo(**{**_PHOTO_BASE, "url": "https://user%40evil.com/path.jpg"})

    def test_photo_url_rejects_invalid_percent_encoding(self) -> None:
        """不正なパーセントエンコード（UTF-8として無効）をネットロック部に含むURLを拒否すること"""
        with pytest.raises(ValidationError, match=re.escape("percent-encod")):
            Photo(**{**_PHOTO_BASE, "url": "https://exam%80ple.com/path.jpg"})


class TestNormalizeUrl:
    """_normalize_url の直接ユニットテスト"""

    pytestmark = pytest.mark.unit

    def test_basic_normalization(self) -> None:
        """スキームとホストの小文字正規化"""
        result = normalize_url(urlparse("HTTPS://EXAMPLE.COM/Path"))
        assert result == "https://example.com/Path"

    def test_ipv6_bracket_preservation(self) -> None:
        """IPv6アドレスのブラケット復元"""
        result = normalize_url(urlparse("https://[::1]:8080/path"))
        assert result == "https://[::1]:8080/path"

    def test_safe_params_encoding(self) -> None:
        """RFC 3986 §3.3 パラメータ部のエンコード"""
        result = normalize_url(urlparse("https://example.com/path;type=pdf"))
        assert ";type=pdf" in result

    def test_fragment_preserves_unreserved(self) -> None:
        """フラグメントのunreserved文字（._~）が過剰エンコードされないこと"""
        result = normalize_url(urlparse("https://example.com/page#section_1.2~draft"))
        assert result.endswith("#section_1.2~draft")

    def test_existing_percent_encoding_preserved(self) -> None:
        """既存の%エンコードが二重エンコードされないこと"""
        result = normalize_url(urlparse("https://example.com/path%20name"))
        assert "%20" in result
        assert "%2520" not in result  # 二重エンコード防止

    def test_single_quote_encoded_to_percent27(self) -> None:
        """シングルクォートがXSS防止のため%27にエンコードされること（RFC 3986 safe除外）"""
        result = normalize_url(urlparse("https://example.com/path/file'.jpg"))
        assert "%27" in result
        assert "'" not in result.split("//", 1)[1]  # ホスト以降にシングルクォートなし

    def test_hostname_none_raises_error(self) -> None:
        """hostname=None（netloc=':8080'）で ValueError が発生すること"""
        parsed = urlparse("https://:8080/path")
        assert parsed.hostname is None, "前提条件: hostname が None であること"
        with pytest.raises(ValueError, match=re.escape("Failed to resolve hostname")):
            normalize_url(parsed)


class TestValidateSchemeLessUrl:
    """_validate_scheme_less_url の直接ユニットテスト"""

    pytestmark = pytest.mark.unit

    def test_rejects_incomplete_percent_encoding(self) -> None:
        """不完全なパーセントエンコード（%GG等）を拒否すること"""
        with pytest.raises(ValueError, match=re.escape("incomplete percent-encoding")):
            validate_scheme_less_url("example%GG.com")

    def test_rejects_path_separator(self) -> None:
        """パス区切り（/）を含むURLを拒否すること"""
        with pytest.raises(ValueError, match=re.escape("cannot contain a path")):
            validate_scheme_less_url("example.com/path")

    def test_rejects_fragment(self) -> None:
        """フラグメント（#）を含むURLを拒否すること"""
        with pytest.raises(ValueError, match=re.escape("cannot contain a fragment")):
            validate_scheme_less_url("example.com#section")

    def test_rejects_query(self) -> None:
        """クエリ（?）を含むURLを拒否すること"""
        with pytest.raises(ValueError, match=re.escape("cannot contain a query")):
            validate_scheme_less_url("example.com?key=val")

    def test_accepts_valid_domain(self) -> None:
        """有効なドメイン名はエラーなしで通過すること"""
        validate_scheme_less_url("example.com")  # 例外なし = 成功
