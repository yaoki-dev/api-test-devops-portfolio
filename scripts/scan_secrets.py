#!/usr/bin/env python3
"""秘密情報検出（キーワードベース・簡略版）"""

import sys
from pathlib import Path

SECRET_KEYWORDS = [
    "api_key",
    "api-key",
    "apikey",
    "secret",
    "password",
    "token",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "PERPLEXITY_API_KEY",
]


def scan_file(file_path: Path) -> bool:
    """キーワード検出（誤検知許容）"""
    content = file_path.read_text().lower()
    for keyword in SECRET_KEYWORDS:
        if keyword.lower() in content:
            print(f"⚠️ Warning: '{keyword}' detected in {file_path}")
            print("   → Manual review required before commit")
            return True
    return False


if __name__ == "__main__":
    tasks_json = Path(".taskmaster/tasks/tasks.json")
    if scan_file(tasks_json):
        sys.exit(1)  # ブロック
    print("✅ No secrets detected")
    sys.exit(0)
