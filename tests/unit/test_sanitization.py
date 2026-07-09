"""Pydantic サニタイズ テスト"""

import html
import re

import pytest

from models.sanitization import sanitize_user_content, strip_invisible_chars
from tests.unit._response_test_vectors import XSS_TEST_VECTORS

pytestmark = pytest.mark.unit


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
        with pytest.raises(ValueError, match=re.escape("String required")):
            sanitize_user_content(None)  # type: ignore[arg-type]


def test_strip_invisible_chars_preserves_ascii_space() -> None:
    """_strip_invisible_chars がASCIIスペース(U+0020)を保持することを検証。

    U+0020はZsカテゴリだが、URLクエリパラメータ等に含まれる正常な文字として保持される。
    NBSP (U+00A0) 等の他のZs文字は除去される。
    """
    # ASCII スペースは保持される
    assert (
        strip_invisible_chars("https://example.com/path?a=1 b=2")
        == "https://example.com/path?a=1 b=2"
    )
    # NBSP (U+00A0: Zs) はNFKC前に除去される（NFKC変換前にZsフィルタが適用されるため）
    assert strip_invisible_chars("https://\u00a0example.com") == "https://example.com"
    # 全角スペース (U+3000: Zs) はNFKC前に除去される
    assert strip_invisible_chars("https://\u3000example.com") == "https://example.com"
    # Variation Selector-1 (U+FE00) は除去される
    assert strip_invisible_chars("java\ufe00script:alert(1)") == "javascript:alert(1)"
    # Variation Selector Supplement (U+E0100) も除去される
    assert strip_invisible_chars("java\U000e0100script:alert(1)") == "javascript:alert(1)"
    # Line Separator (U+2028: Zl) は除去される
    assert strip_invisible_chars("java\u2028script:alert(1)") == "javascript:alert(1)"
    # Paragraph Separator (U+2029: Zp) は除去される
    assert strip_invisible_chars("java\u2029script:alert(1)") == "javascript:alert(1)"


def test_strip_invisible_chars_removes_surrogate_codepoint() -> None:
    """_strip_invisible_chars が孤立サロゲート(Cs)をnormalize前に除去することを検証。

    孤立サロゲート(U+D800-U+DFFF)は unicodedata.normalize() で ValueError を
    送出するため、事前除去が必要。
    """
    # 孤立サロゲートが除去され、残りの文字列が返される
    assert strip_invisible_chars("https://\ud800example.com") == "https://example.com"
    # サロゲートのみの入力は空文字列になる
    assert strip_invisible_chars("\ud800\udbff\udfff") == ""
    # サロゲートが混在しても正常な文字は保持される
    assert strip_invisible_chars("abc\ud800def") == "abcdef"


def test_strip_invisible_chars_returns_empty_for_empty_input() -> None:
    """_strip_invisible_chars に空文字列を渡すと空文字列が返ること。"""
    assert strip_invisible_chars("") == ""


def test_strip_invisible_chars_strips_zero_width_space() -> None:
    """ゼロ幅スペース(U+200B, Cf)を除去すること"""
    result = strip_invisible_chars("exam\u200bple.com")
    assert result == "example.com"


def test_strip_invisible_chars_strips_bidi_override() -> None:
    """Bidi制御文字(U+202E, Cf)を除去すること"""
    result = strip_invisible_chars("exam\u202eple.com")
    assert result == "example.com"


def test_strip_invisible_chars_preserves_regular_space() -> None:
    """通常スペース(U+0020)は保持すること"""
    result = strip_invisible_chars("hello world")
    assert result == "hello world"


def test_strip_invisible_chars_preserves_combining_mark() -> None:
    """結合文字は保持され、NFD由来のホスト名をサイレントに改変しないこと。"""
    result = strip_invisible_chars("cafe\u0301.com")
    assert result == "café.com"
