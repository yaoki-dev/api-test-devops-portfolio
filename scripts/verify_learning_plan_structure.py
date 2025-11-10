#!/usr/bin/env python3
"""
学習計画の構造検証スクリプト

テンプレート構成と各Day（D1-D60）の構造適合性を正規表現で検証します。
"""

import re
from pathlib import Path

# テンプレート必須要素（検証対象）
REQUIRED_ELEMENTS = {
    "day_header": r"^#{1,5}\s*\*?\*?D\d+",  # Day header (D1, D2, etc.) - 1-5 level headers
    "total_learning_time": r"\*\*総学習時間\*\*:\s*\d+\.?\d*H?",
    "coverage_goal": r"\*\*カバレッジ目標\*\*",
    "phase1": r"\*\*Phase 1:\s*AI説明・概念理解",
    "understanding_checklist": r"理解度チェックリスト:",
    "judgment_criteria": r"判定基準:",
    "criteria_3plus": r"3つ以上✅",  # 3+ ✅ criteria
    "phase2": r"\*\*Phase 2:\s*AI協働実装",
    "ai_request_prompt": r"AI依頼プロンプト",
    "phase3": r"\*\*Phase 3:\s*理解度確認・記録",
    "review_buffer": r"\*\*復習バッファ",
    "portfolio_deliverables": r"\*\*ポートフォリオ成果物\*\*",
}


def extract_day_sections(content: str) -> dict[int, str]:
    """
    ファイル内容から全Day（D1-D60）セクションを抽出

    対応形式:
    - 標準Day: #### **D27 (Wed.): タイトル**
    - 5-level header: ##### D31（月）: タイトル
    - 括弧なし: ##### D33: タイトル
    - Day範囲 (2日): #### **D55-56 (月-Tue.): タイトル**
    - Day範囲 (3日): ##### D34-36: タイトル

    Args:
        content: ファイル全体の内容

    Returns:
        {day_number: day_content} の辞書
        ※Day範囲（D55-56, D34-36）は最初の番号（55, 34）でキーを作成
    """
    # Enhanced pattern to match:
    # - 1-5 level headers (#{1,5})
    # - Optional bold markers (\*?\*?)
    # - Single day (D27) or day range (D55-56 or D34-36)
    # - Optional parentheses with day names (some days like D33 have no parentheses)
    pattern = r"(^#{1,5}\s*\*?\*?D(\d+)(?:-\d+)?(?:\s*[（\(][^)）]+[）\)])?:.*?)(?=^#{1,5}\s*\*?\*?D\d+|^---\s*$|\Z)"

    day_sections = {}
    for match in re.finditer(pattern, content, re.MULTILINE | re.DOTALL):
        day_content = match.group(1)
        day_number = int(match.group(2))  # 範囲の場合は最初の番号を使用
        day_sections[day_number] = day_content

    return day_sections


def verify_day_structure(day_number: int, day_content: str) -> dict[str, bool]:
    """
    1つのDayセクションの構造を検証

    Args:
        day_number: Day番号（1-60）
        day_content: Dayセクションの内容

    Returns:
        {element_name: is_present} の辞書
    """
    results = {}

    for element_name, pattern in REQUIRED_ELEMENTS.items():
        # 各必須要素が存在するか確認
        match = re.search(pattern, day_content, re.MULTILINE | re.IGNORECASE)
        results[element_name] = match is not None

    return results


def generate_report(
    day_sections: dict[int, str], verification_results: dict[int, dict[str, bool]]
) -> str:
    """
    検証結果レポートを生成

    Args:
        day_sections: 抽出されたDayセクション
        verification_results: 各Dayの検証結果

    Returns:
        レポート文字列
    """
    report_lines = [
        "# 学習計画構造検証レポート\n",
        f"*生成日時: {Path(__file__).stat().st_mtime}*\n\n",
        "## サマリー\n",
        f"- 抽出されたDay数: {len(day_sections)} / 60\n",
        f"- 検証対象要素数: {len(REQUIRED_ELEMENTS)}\n\n",
    ]

    # 全体適合率計算
    total_checks = len(verification_results) * len(REQUIRED_ELEMENTS)
    passed_checks = sum(
        sum(1 for present in day_results.values() if present)
        for day_results in verification_results.values()
    )
    overall_conformance = (passed_checks / total_checks * 100) if total_checks > 0 else 0

    report_lines.append(
        f"- **全体適合率**: {overall_conformance:.1f}% ({passed_checks}/{total_checks})\n\n"
    )

    # 不適合箇所の詳細
    report_lines.append("## 不適合箇所の詳細\n\n")

    non_conforming_days = []
    for day_num in sorted(verification_results.keys()):
        day_results = verification_results[day_num]
        missing_elements = [element for element, present in day_results.items() if not present]

        if missing_elements:
            non_conforming_days.append(day_num)
            report_lines.append(f"### D{day_num}\n\n")
            report_lines.append("**欠落要素**:\n")
            for element in missing_elements:
                report_lines.append(f"- ❌ `{element}`: {REQUIRED_ELEMENTS[element]}\n")
            report_lines.append("\n")

    if not non_conforming_days:
        report_lines.append("✅ **すべてのDayセクションがテンプレート構造に適合しています。**\n\n")
    else:
        report_lines.append(
            f"⚠️ **不適合Day数**: {len(non_conforming_days)} / {len(verification_results)}\n\n"
        )
        report_lines.append(
            f"**不適合Day一覧**: {', '.join(f'D{d}' for d in non_conforming_days)}\n\n"
        )

    # Day別適合率
    report_lines.append("## Day別適合率\n\n")
    report_lines.append("| Day | 適合率 | 欠落要素数 | ステータス |\n")
    report_lines.append("|-----|--------|------------|----------|\n")

    for day_num in sorted(verification_results.keys()):
        day_results = verification_results[day_num]
        present_count = sum(1 for present in day_results.values() if present)
        conformance = present_count / len(REQUIRED_ELEMENTS) * 100
        missing_count = len(REQUIRED_ELEMENTS) - present_count
        status = "✅" if missing_count == 0 else "⚠️"

        report_lines.append(f"| D{day_num} | {conformance:.1f}% | {missing_count} | {status} |\n")

    report_lines.append("\n")

    # 要素別検出率
    report_lines.append("## 要素別検出率\n\n")
    report_lines.append("| 要素名 | 検出率 | 検出数 / 総Day数 |\n")
    report_lines.append("|--------|--------|------------------|\n")

    element_stats = {}
    for element_name in REQUIRED_ELEMENTS.keys():
        detected_count = sum(
            1
            for day_results in verification_results.values()
            if day_results.get(element_name, False)
        )
        detection_rate = (
            (detected_count / len(verification_results) * 100) if verification_results else 0
        )
        element_stats[element_name] = (detection_rate, detected_count)

    for element_name, (rate, count) in sorted(
        element_stats.items(), key=lambda x: x[1][0], reverse=True
    ):
        status = "✅" if rate >= 95 else "⚠️" if rate >= 80 else "❌"
        report_lines.append(
            f"| {element_name} | {rate:.1f}% | {count} / {len(verification_results)} {status} |\n"
        )

    report_lines.append("\n")

    # 未抽出Dayの確認
    expected_days = set(range(1, 61))
    extracted_days = set(day_sections.keys())
    missing_days = expected_days - extracted_days

    if missing_days:
        report_lines.append("## ⚠️ 未抽出Day\n\n")
        report_lines.append("以下のDayセクションが抽出されませんでした:\n\n")
        report_lines.append(
            f"**未抽出Day**: {', '.join(f'D{d}' for d in sorted(missing_days))}\n\n"
        )

    # 推奨事項
    report_lines.append("## 推奨事項\n\n")

    if non_conforming_days or missing_days:
        report_lines.append("以下の対応を推奨します:\n\n")

        if missing_days:
            report_lines.append(
                f"1. **未抽出Day対応**: {len(missing_days)}個のDayセクションが抽出されませんでした。"
                "ファイル構造を確認してください。\n"
            )

        if non_conforming_days:
            report_lines.append(
                f"2. **不適合Day修正**: {len(non_conforming_days)}個のDayセクションに欠落要素があります。"
                "テンプレート構造に合わせて修正してください。\n"
            )
    else:
        report_lines.append(
            "✅ すべてのDayセクションが適切に抽出され、テンプレート構造に適合しています。\n\n"
        )

    return "".join(report_lines)


def main():
    """メイン処理"""
    # ファイルパス設定
    project_root = Path(__file__).parent.parent
    learning_plan_path = (
        project_root
        / "docs"
        / "プロジェクト再編"
        / "10週ハイブリッドプラン_日次詳細学習スケジュール.md"
    )

    print(f"📖 学習計画ファイル読み込み中: {learning_plan_path}")

    # ファイル読み込み
    if not learning_plan_path.exists():
        print(f"❌ エラー: ファイルが見つかりません: {learning_plan_path}")
        return

    content = learning_plan_path.read_text(encoding="utf-8")
    print(f"✅ ファイル読み込み完了: {len(content)} chars\n")

    # Day セクション抽出
    print("🔍 Dayセクション抽出中...")
    day_sections = extract_day_sections(content)
    print(f"✅ 抽出完了: {len(day_sections)} Days\n")

    # 各Day検証
    print("🔍 各Day構造検証中...")
    verification_results = {}
    for day_num, day_content in sorted(day_sections.items()):
        verification_results[day_num] = verify_day_structure(day_num, day_content)
    print("✅ 検証完了\n")

    # レポート生成
    print("📝 検証レポート生成中...")
    report = generate_report(day_sections, verification_results)

    # レポート出力
    report_path = project_root / "docs" / "プロジェクト再編" / "学習計画構造検証レポート.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"✅ レポート保存完了: {report_path}\n")

    # コンソール出力
    print(report)

    print("\n📊 検証完了")
    print(f"詳細レポート: {report_path}")


if __name__ == "__main__":
    main()
