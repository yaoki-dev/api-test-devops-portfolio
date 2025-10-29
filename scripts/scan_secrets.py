#!/usr/bin/env python3
"""秘密情報検出（正規表現パターンマッチング版）

Task Master AI統合 - 総合分析レポート P0優先度実装
- 正規表現ベースのパターンマッチング
- 全ファイルスキャン対応
- 値部分の検証
"""

import re
import sys
from pathlib import Path

# 正規表現パターン（Task Master AIレポート仕様準拠）
SECRET_PATTERNS = [
    # API Key patterns (20文字以上)
    (r'api[_-]?key.*=.*["\'][\w-]{20,}["\']', "API Key detected"),
    # Password patterns (8文字以上)
    (r'password.*=.*["\'][\w-]{8,}["\']', "Password detected"),
    # Specific API Key patterns
    (
        r'(ANTHROPIC|OPENAI|PERPLEXITY|GOOGLE|XAI|MISTRAL)_API_KEY\s*=\s*["\'][\w-]+["\']',
        "Provider API Key detected",
    ),
    # Token patterns
    (r'token\s*=\s*["\'][\w.-]{20,}["\']', "Token detected"),
    # AWS patterns
    (r'aws[_-]?access[_-]?key[_-]?id.*["\'][A-Z0-9]{20}["\']', "AWS Access Key detected"),
    (r'aws[_-]?secret[_-]?access[_-]?key.*["\'][\w/+=]{40}["\']', "AWS Secret Key detected"),
    # GitHub Token patterns
    (r"gh[ps]_[a-zA-Z0-9]{36,}", "GitHub Token detected"),
    # Private Key patterns
    (r"-----BEGIN.*PRIVATE KEY-----", "Private Key detected"),
]


def scan_for_secrets(file_path: Path) -> list[tuple[str, str, int]]:
    """
    秘密情報検出（正規表現パターンマッチング）

    Args:
        file_path: スキャン対象ファイルパス

    Returns:
        検出結果リスト [(パターン説明, マッチ文字列, 行番号), ...]
    """
    try:
        with file_path.open("r", encoding="utf-8") as f:
            content = f.read()
    except (UnicodeDecodeError, PermissionError):
        # バイナリファイル・権限エラーはスキップ
        return []

    detections = []
    lines = content.split("\n")

    for pattern, description in SECRET_PATTERNS:
        for line_num, line in enumerate(lines, start=1):
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                detections.append((description, match.group(0), line_num))

    return detections


def scan_directory(directory: Path = Path()) -> bool:
    """
    ディレクトリ全体をスキャン

    Args:
        directory: スキャン対象ディレクトリ

    Returns:
        秘密情報検出時True
    """
    # スキャン除外パターン
    exclude_patterns = {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "htmlcov",
        "reports",
        ".env.example",
    }

    found_secrets = False

    for file_path in directory.rglob("*"):
        # 除外パターンチェック
        if any(excluded in file_path.parts for excluded in exclude_patterns):
            continue

        # ファイルのみ処理
        if not file_path.is_file():
            continue

        # スキャン実行
        detections = scan_for_secrets(file_path)

        if detections:
            found_secrets = True
            print(f"🚨 CRITICAL: Secrets detected in {file_path}")
            for description, matched_text, line_num in detections:
                # 実際の値を隠して表示
                masked_text = matched_text[:10] + "***" if len(matched_text) > 10 else "***"
                print(f"   Line {line_num}: {description}")
                print(f"   Pattern: {masked_text}")
            print()

    return found_secrets


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="秘密情報検出スクリプト")
    parser.add_argument(
        "--path",
        type=Path,
        default=Path(),
        help="スキャン対象パス（デフォルト: カレントディレクトリ）",
    )
    args = parser.parse_args()

    print("🔍 Starting secret scan...")
    print(f"📂 Target: {args.path.absolute()}")
    print()

    if scan_directory(args.path):
        print("❌ Secret scan FAILED")
        print("   → Manual review and removal required before commit")
        sys.exit(1)

    print("✅ Secret scan PASSED")
    print("   No secrets detected")
    sys.exit(0)
