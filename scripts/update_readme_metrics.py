#!/usr/bin/env python3
"""README.md メトリクス自動更新スクリプト

coverage.json から最新のカバレッジ数値を抽出し、
README.md 内のバッジを自動更新します。

使用方法:
    uv run python scripts/update_readme_metrics.py

更新対象:
    - Coverage バッジ (カバレッジ率)
    - テスト数バッジ (pytest --collect-only から取得可能)

最終更新: 2025年11月28日
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def get_coverage_from_json(coverage_file: Path) -> float | None:
    """coverage.json からカバレッジ率を抽出する。

    Args:
        coverage_file: coverage.json のパス

    Returns:
        カバレッジ率 (0-100)、取得失敗時は None

    """
    if not coverage_file.exists():
        print(f"警告: {coverage_file} が見つかりません")
        return None

    try:
        with coverage_file.open(encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        # totals.percent_covered を取得
        percent_covered = data.get("totals", {}).get("percent_covered", 0.0)
        return float(percent_covered)
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        print(f"エラー: coverage.json の解析に失敗: {e}")
        return None


def get_test_count() -> int | None:
    """Pytest --collect-only でテスト数を取得する。

    Returns:
        テスト数、取得失敗時は None

    """
    try:
        result = subprocess.run(
            ["uv", "run", "pytest", "--collect-only", "-q"],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        # 出力の最終行から "X tests" を抽出
        # 例: "192 tests collected"
        output = result.stdout.strip()
        lines = output.split("\n")

        for line in reversed(lines):
            match = re.search(r"(\d+)\s+test", line)
            if match:
                return int(match.group(1))

        return None
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"警告: テスト数の取得に失敗: {e}")
        return None


def get_badge_color(percent: float) -> str:
    """カバレッジ率に応じたバッジ色を返す。

    Args:
        percent: カバレッジ率 (0-100)

    Returns:
        shields.io 用の色名

    """
    if percent >= 80:
        return "brightgreen"
    if percent >= 60:
        return "green"
    if percent >= 40:
        return "yellow"
    if percent >= 20:
        return "orange"
    return "red"


def update_readme_badges(readme_file: Path, coverage: float, test_count: int | None) -> bool:
    """README.md のバッジを更新する。

    Args:
        readme_file: README.md のパス
        coverage: カバレッジ率
        test_count: テスト数 (None の場合は更新しない)

    Returns:
        更新成功時 True

    """
    if not readme_file.exists():
        print(f"エラー: {readme_file} が見つかりません")
        return False

    content = readme_file.read_text(encoding="utf-8")
    original_content = content

    # カバレッジバッジの更新
    # パターン: [![Coverage](https://img.shields.io/badge/coverage-XX%25-COLOR)]
    coverage_pattern = r"\[!\[Coverage\]\(https://img\.shields\.io/badge/coverage-\d+%25-\w+\)\]"
    coverage_display = f"{coverage:.0f}"
    color = get_badge_color(coverage)
    new_coverage_badge = (
        f"[![Coverage](https://img.shields.io/badge/coverage-{coverage_display}%25-{color})]"
    )

    if re.search(coverage_pattern, content):
        content = re.sub(coverage_pattern, new_coverage_badge, content)
        print(f"✅ カバレッジバッジを更新: {coverage_display}% ({color})")
    else:
        print("⚠️ カバレッジバッジのパターンが見つかりません")

    # テスト数バッジの更新 (オプション)
    if test_count is not None:
        tests_pattern = r"\[!\[Tests\]\(https://img\.shields\.io/badge/tests-\d+%2B?-\w+\)\]"
        new_tests_badge = (
            f"[![Tests](https://img.shields.io/badge/tests-{test_count}%2B-brightgreen)]"
        )

        if re.search(tests_pattern, content):
            content = re.sub(tests_pattern, new_tests_badge, content)
            print(f"✅ テスト数バッジを更新: {test_count}+")

    # 変更があれば書き込み
    if content != original_content:
        readme_file.write_text(content, encoding="utf-8")
        print(f"✅ {readme_file} を更新しました")
        return True
    print("ℹ️ 変更はありません")
    return True


def main() -> int:
    """メインエントリポイント。

    Returns:
        終了コード (0: 成功, 1: 失敗)

    """
    # プロジェクトルートを検出
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    coverage_file = project_root / "coverage.json"
    readme_file = project_root / "README.md"

    print("=" * 50)
    print("README.md メトリクス自動更新")
    print("=" * 50)

    # カバレッジ取得
    coverage = get_coverage_from_json(coverage_file)
    if coverage is None:
        print("エラー: カバレッジの取得に失敗しました")
        return 1

    print(f"📊 現在のカバレッジ: {coverage:.2f}%")

    # テスト数取得 (オプション、時間がかかるためスキップ可能)
    test_count = None
    if "--with-test-count" in sys.argv:
        print("📝 テスト数を取得中...")
        test_count = get_test_count()
        if test_count:
            print(f"📝 テスト数: {test_count}")

    # README更新
    success = update_readme_badges(readme_file, coverage, test_count)

    print("=" * 50)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
