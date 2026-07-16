"""レスポンスモデルテスト共有 XSS ベクター"""

from typing import Final

import pytest

# XSS テストベクター（OWASP Cheat Sheetベース・プロジェクト独自分類）
# Reference: https://cheatsheetseries.owasp.org/cheatsheets/XSS_Filter_Evasion_Cheat_Sheet.html

type XSSVector = tuple[str, str]  # XSS_TEST_VECTORS 用

# XSSテストベクター定数
XSS_TEST_VECTORS: Final[list[XSSVector]] = [
    # Basic Script Tags
    (
        "<script>alert('XSS')</script>",
        "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;",
    ),
    (
        "<SCRIPT>alert(1)</SCRIPT>",
        "&lt;SCRIPT&gt;alert(1)&lt;/SCRIPT&gt;",
    ),
    # Event Handlers (CRITICAL - most common bypass)
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
    # URI Schemes (CRITICAL)
    (
        '<a href="javascript:alert(1)">',
        "&lt;a href=&quot;javascript:alert(1)&quot;&gt;",
    ),
    (
        '<iframe src="javascript:alert(1)">',
        "&lt;iframe src=&quot;javascript:alert(1)&quot;&gt;",
    ),
    # Attribute Injection
    (
        '" onclick="alert(1)"',
        "&quot; onclick=&quot;alert(1)&quot;",
    ),
    (
        "' onfocus='alert(1)'",
        "&#x27; onfocus=&#x27;alert(1)&#x27;",
    ),
    # Edge Cases
    ("", ""),  # Empty string
    ("Normal text", "Normal text"),  # Passthrough (no XSS)
    (
        "Hello <b>World</b>",
        "Hello &lt;b&gt;World&lt;/b&gt;",
    ),  # Safe HTML
    # Special Characters
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
