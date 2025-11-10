#!/usr/bin/env python3
"""
Week 1 Learning Plan Improvement Script

Systematically applies 7 improvement steps from workflow document using regex patterns.
Implements Option B (Strategic Layering) with cross-references, no full code duplication.

Usage:
    python scripts/week1_improvements.py
"""

import re
import sys
from pathlib import Path

# File paths
LEARNING_PLAN_PATH = Path(
    "docs/プロジェクト再編/10週ハイブリッドプラン_日次詳細学習スケジュール.md"
)
PORTFOLIO_STRATEGY_PATH = Path("docs/プロジェクト再編/ポートフォリオ戦略分析_改善版.md")
WORKFLOW_PATH = Path("docs/プロジェクト再編/Week1_improvement_workflow.md")
REPORT_PATH = Path("docs/プロジェクト再編/Week1_improvement_report.md")


class Week1Improver:
    """Week 1 learning plan improvement automation"""

    def __init__(self):
        self.learning_plan_content = ""
        self.week1_section = ""
        self.week1_start = 0
        self.week1_end = 0
        self.changes_applied = []
        self.validation_results = []

    def load_files(self) -> None:
        """Load learning plan file"""
        print("📂 Loading learning plan file...")
        with open(LEARNING_PLAN_PATH, encoding="utf-8") as f:
            self.learning_plan_content = f.read()
        print(f"✅ Loaded {len(self.learning_plan_content)} characters")

    def extract_week1_section(self) -> None:
        """Extract Week 1 section using regex (no hardcoded line numbers)"""
        print("\n🔍 Extracting Week 1 section using regex...")

        # Pattern to match Week 1 section boundary (supports both "Week 1" and "W1")
        # Matches from "### Week 1:" or "### W1:" to next "### Week 2:" or "### W2:"
        pattern = r"(### (?:Week 1|W1):.*?)(?=### (?:Week 2|W2):|$)"
        match = re.search(pattern, self.learning_plan_content, re.DOTALL)

        if not match:
            raise ValueError("Week 1 section not found!")

        self.week1_section = match.group(1)
        self.week1_start = match.start()
        self.week1_end = match.end()

        lines = self.week1_section.count("\n")
        print(f"✅ Found Week 1 section: {len(self.week1_section)} characters, {lines} lines")
        print(f"   Start position: {self.week1_start}, End position: {self.week1_end}")

    def apply_step1_format_unification(self) -> None:
        """Step 1: Format unification (Week 1 → W1, 42時間 → 45H, 15テスト → 25テスト)"""
        print("\n🔧 Step 1: Format unification...")

        original = self.week1_section

        # Replacement 1: Week 1 → W1
        self.week1_section = re.sub(r"### Week 1:", "### W1:", self.week1_section)

        # Replacement 2: 42時間 → 45H
        self.week1_section = re.sub(r"\(42時間\)", "(45H)", self.week1_section)

        # Replacement 3: 15テスト → 25テスト
        self.week1_section = re.sub(
            r"15テスト作成・実行能力", "25テスト作成・実行能力", self.week1_section
        )

        if original != self.week1_section:
            self.changes_applied.append("Step 1: Format unification completed (W1, 45H, 25テスト)")
            print("✅ Step 1 completed")
        else:
            print("⚠️  Step 1: No changes needed")

    def apply_step2_time_allocation(self) -> None:
        """Step 2: Insert time allocation breakdown after header"""
        print("\n🔧 Step 2: Time allocation breakdown insertion...")

        time_breakdown = """
**総時間**: 45H
- Phase 1（AI説明・概念理解）: 15H（6D × 2.5H）
- Phase 2（AI協働実装）: 18H（6D × 3H）
- Phase 3（理解度確認）: 3H（6D × 0.5H）
- Buffer（復習バッファ）: 9H（6D × 1.5H）
"""

        # Find header pattern
        header_pattern = r"(### W1:.*?\n)"
        match = re.search(header_pattern, self.week1_section)

        if match:
            # Check if time breakdown already exists
            if "**総時間**: 45H" not in self.week1_section:
                insert_pos = match.end()
                self.week1_section = (
                    self.week1_section[:insert_pos]
                    + time_breakdown
                    + self.week1_section[insert_pos:]
                )
                self.changes_applied.append("Step 2: Time allocation breakdown inserted")
                print("✅ Step 2 completed")
            else:
                print("⚠️  Step 2: Time breakdown already exists")
        else:
            print("❌ Step 2: Header not found")

    def apply_step3_weekly_summary(self) -> None:
        """Step 3: Insert weekly summary section"""
        print("\n🔧 Step 3: Weekly summary section insertion...")

        weekly_summary = """
**週次サマリー**: Python同期HTTP基礎（httpx） + エラーハンドリング + Pydantic型安全基盤確立
"""

        # Find position after time breakdown or after header
        if "**総時間**: 45H" in self.week1_section:
            # Insert after time breakdown
            pattern = r"(- Buffer（復習バッファ）: 9H.*?\n)"
            match = re.search(pattern, self.week1_section)
            if match:
                if "**週次サマリー**" not in self.week1_section:
                    insert_pos = match.end()
                    self.week1_section = (
                        self.week1_section[:insert_pos]
                        + weekly_summary
                        + self.week1_section[insert_pos:]
                    )
                    self.changes_applied.append("Step 3: Weekly summary section inserted")
                    print("✅ Step 3 completed")
                else:
                    print("⚠️  Step 3: Weekly summary already exists")
            else:
                print("❌ Step 3: Time breakdown end not found")
        else:
            print("⚠️  Step 3: Skipped (time breakdown not found)")

    def apply_step4_day2_error_hierarchy(self) -> None:
        """Step 4: Add Day 2 error hierarchy specification (5 exception classes)"""
        print("\n🔧 Step 4: Day 2 error hierarchy specification...")

        # Find Day 2 section
        day2_pattern = r"(#### \*\*Day 2.*?)\n(#### \*\*Day 3|\Z)"
        match = re.search(day2_pattern, self.week1_section, re.DOTALL)

        if not match:
            print("❌ Step 4: Day 2 section not found")
            return

        day2_section = match.group(1)

        # Check if error hierarchy specification exists
        if (
            "APIError/APIHTTPError/APIConnectionError/APITimeoutError/APIValidationError"
            in day2_section
        ):
            print("⚠️  Step 4: Error hierarchy specification already exists")
            return

        # Find insertion point (after implementation items, before AI prompt section)
        # Looking for the pattern: implementation items → empty line → "#### AI依頼プロンプト"
        insert_pattern = r"(\*\*Phase 2: AI協働実装.*?- バッファ \*\*\[.*?\]\*\*\n)"
        insert_match = re.search(insert_pattern, day2_section, re.DOTALL)

        if insert_match:
            error_spec = """
**エラー階層設計仕様**:
- 5例外クラス実装: APIError（基底） / APIHTTPError（4xx/5xx分離） / APIConnectionError（接続失敗） / APITimeoutError（タイムアウト） / APIValidationError（Pydantic検証失敗）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W1-Day2-エラー階層設計]

"""
            # Insert at end of insert_match
            insert_pos = match.start(1) + insert_match.end()
            self.week1_section = (
                self.week1_section[:insert_pos] + error_spec + self.week1_section[insert_pos:]
            )
            self.changes_applied.append("Step 4: Day 2 error hierarchy specification added")
            print("✅ Step 4 completed")
        else:
            print("❌ Step 4: Phase 2 implementation items not found in Day 2")

    def apply_step5_day3_pydantic_models(self) -> None:
        """Step 5: Update Day 3 Pydantic model code with specifications"""
        print("\n🔧 Step 5: Day 3 Pydantic model specification...")

        # Find Day 3 section
        day3_pattern = r"(#### \*\*Day 3.*?)\n(#### \*\*Day 4|\Z)"
        match = re.search(day3_pattern, self.week1_section, re.DOTALL)

        if not match:
            print("❌ Step 5: Day 3 section not found")
            return

        day3_section = match.group(1)

        # Check if specification exists
        if "frozen=True" in day3_section and "Field(alias=" in day3_section:
            print("⚠️  Step 5: Pydantic model specification already exists")
            return

        # Find insertion point (after implementation items with バッファ line, before AI prompt section)
        insert_pattern = r"(\*\*Phase 2: AI協働実装.*?- バッファ \*\*\[.*?\]\*\*\n)"
        insert_match = re.search(insert_pattern, day3_section, re.DOTALL)

        if insert_match:
            pydantic_spec = """
**Pydanticモデル仕様**:
- User/Post/Todo/Comment 4モデル実装
- `model_config = ConfigDict(frozen=True, populate_by_name=True)` でイミュータブル設定
- `Field(alias="userId")` でJSON ↔ Python変換（userId → user_id）
- `EmailStr` で厳密バリデーション
- 1行コードサンプル: `user_id: int = Field(alias="userId")  # JSON "userId" → Python "user_id"`
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W1-Day3-Pydanticモデル実装]

"""
            insert_pos = match.start(1) + insert_match.end()
            self.week1_section = (
                self.week1_section[:insert_pos] + pydantic_spec + self.week1_section[insert_pos:]
            )
            self.changes_applied.append("Step 5: Day 3 Pydantic model specification added")
            print("✅ Step 5 completed")
        else:
            print("❌ Step 5: Phase 2 header not found in Day 3")

    def apply_step6_day5_checklist_correction(self) -> None:
        """Step 6: Replace Day 5 incorrect checklist with error case testing checklist"""
        print("\n🔧 Step 6: Day 5 checklist correction...")

        # Find Day 5 section
        day5_pattern = r"(#### \*\*Day 5.*?)\n(#### \*\*Day 6|\Z)"
        match = re.search(day5_pattern, self.week1_section, re.DOTALL)

        if not match:
            print("❌ Step 6: Day 5 section not found")
            return

        day5_section = match.group(1)

        # Find the incorrect checklist (Pydantic Settings related)
        incorrect_pattern = (
            r"理解度チェックリスト:.*?- \[ \] Pydantic Settings.*?(?=\n\n|\*\*Phase 2)"
        )
        incorrect_match = re.search(incorrect_pattern, day5_section, re.DOTALL)

        if not incorrect_match:
            print("⚠️  Step 6: Incorrect checklist not found (may already be corrected)")
            return

        # Correct checklist for error case testing
        correct_checklist = """理解度チェックリスト:
  - [ ] HTTPステータスコード分類（4xx/5xx）とリトライ戦略（4xx即失敗、5xxリトライ）を説明できる
  - [ ] カスタム例外階層の設計パターン（基底クラス + 特化クラス）を理解している
  - [ ] コンテキストマネージャー（__enter__/__exit__）の役割とリソース管理を説明できる
  - [ ] pytest.raisesによる例外テストの実装パターンを理解している
  - [ ] モック（unittest.mock）を使ったエラーケースシミュレーションを説明できる"""

        # Replace the incorrect checklist
        start_pos = match.start(1) + incorrect_match.start()
        end_pos = match.start(1) + incorrect_match.end()

        self.week1_section = (
            self.week1_section[:start_pos] + correct_checklist + self.week1_section[end_pos:]
        )

        self.changes_applied.append(
            "Step 6: Day 5 checklist corrected (Pydantic Settings → Error Case Testing)"
        )
        print("✅ Step 6 completed")

    def apply_step7_day6_w2_preview(self) -> None:
        """Step 7: Add Day 6 next week preview section (AsyncAPIClient with Pydantic integration)"""
        print("\n🔧 Step 7: Day 6 W2 preview section...")

        # Find Day 6 section end (before weekly review or end of Week 1)
        day6_pattern = r"(#### \*\*Day 6.*?)\n(---\n\n## 週次理解度確認|\n### W2:|\Z)"
        match = re.search(day6_pattern, self.week1_section, re.DOTALL)

        if not match:
            print("❌ Step 7: Day 6 section end not found")
            return

        day6_section = match.group(1)

        # Check if W2 preview exists
        if "**W2プレビュー**" in day6_section or "次週予告" in day6_section:
            print("⚠️  Step 7: W2 preview already exists")
            return

        w2_preview = """

---

### 次週予告: W2でのAsync/Await + Pydantic統合

**AsyncAPIClient + Pydantic統合パターン**:
```python
class AsyncJSONPlaceholderClient(AsyncAPIClient):
    async def get_user(self, user_id: int) -> User:
        data = await self.get(f"/users/{user_id}")
        return self._validate_model(data, User)  # Pydantic検証

    async def get_posts(self, user_id: Optional[int] = None) -> List[Post]:
        data = await self.get(endpoint)
        return self._validate_model_list(data, Post)  # リスト検証
```

**W2で学ぶこと**:
- 非同期HTTP処理（async/await、asyncio.gather並行実行）
- AsyncAPIClientとPydanticの統合パターン
- 型安全なAPI呼び出しの実装
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W2-AsyncAPIClient-Pydantic統合]
"""

        # Insert at end of Day 6 section
        insert_pos = match.end(1)
        self.week1_section = (
            self.week1_section[:insert_pos] + w2_preview + self.week1_section[insert_pos:]
        )

        self.changes_applied.append("Step 7: Day 6 W2 preview section added")
        print("✅ Step 7 completed")

    def apply_all_improvements(self) -> None:
        """Apply all 7 improvement steps sequentially"""
        print("\n" + "=" * 60)
        print("🚀 Starting Week 1 Improvements (7 Steps)")
        print("=" * 60)

        self.apply_step1_format_unification()
        self.apply_step2_time_allocation()
        self.apply_step3_weekly_summary()
        self.apply_step4_day2_error_hierarchy()
        self.apply_step5_day3_pydantic_models()
        self.apply_step6_day5_checklist_correction()
        self.apply_step7_day6_w2_preview()

        print("\n" + "=" * 60)
        print(f"✅ All steps completed. Total changes: {len(self.changes_applied)}")
        print("=" * 60)

    def validate_improvements(self) -> None:
        """Validate improvements against quality checklist"""
        print("\n🔍 Validating improvements against quality checklist...")

        checks = [
            ("Format: W1表記", "### W1:" in self.week1_section),
            ("Format: 45H表記", "(45H)" in self.week1_section),
            ("Format: 25テスト表記", "25テスト" in self.week1_section),
            ("Time allocation present", "Phase 1（AI説明・概念理解）: 15H" in self.week1_section),
            ("Weekly summary present", "**週次サマリー**" in self.week1_section),
            (
                "Day 2 error hierarchy spec",
                "APIError/APIHTTPError/APIConnectionError" in self.week1_section,
            ),
            (
                "Day 3 Pydantic spec",
                "frozen=True" in self.week1_section and "Field(alias=" in self.week1_section,
            ),
            (
                "Day 5 checklist correct",
                "HTTPステータスコード分類" in self.week1_section
                and "Pydantic Settings"
                not in self.week1_section.split("Day 5")[1].split("Day 6")[0]
                if "Day 5" in self.week1_section and "Day 6" in self.week1_section
                else False,
            ),
            (
                "Day 6 W2 preview",
                "**W2で学ぶこと**" in self.week1_section or "次週予告" in self.week1_section,
            ),
            (
                "Cross-references present",
                "@[ポートフォリオ戦略分析_改善版.md" in self.week1_section,
            ),
        ]

        passed = 0
        for check_name, result in checks:
            status = "✅" if result else "❌"
            self.validation_results.append((check_name, result))
            print(f"  {status} {check_name}")
            if result:
                passed += 1

        print(
            f"\n📊 Validation: {passed}/{len(checks)} checks passed ({passed * 100 // len(checks)}%)"
        )

    def save_improved_content(self) -> None:
        """Save improved Week 1 section back to learning plan file"""
        print("\n💾 Saving improved content...")

        # Replace Week 1 section in full content
        improved_content = (
            self.learning_plan_content[: self.week1_start]
            + self.week1_section
            + self.learning_plan_content[self.week1_end :]
        )

        # Backup original file
        backup_path = LEARNING_PLAN_PATH.with_suffix(".md.backup")
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(self.learning_plan_content)
        print(f"✅ Backup saved: {backup_path}")

        # Save improved content
        with open(LEARNING_PLAN_PATH, "w", encoding="utf-8") as f:
            f.write(improved_content)
        print(f"✅ Improved content saved: {LEARNING_PLAN_PATH}")

    def generate_report(self) -> None:
        """Generate improvement report"""
        print("\n📄 Generating improvement report...")

        report = f"""# Week 1 Improvement Report

*Generated: {__import__("datetime").datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}*

## Changes Applied

"""
        for i, change in enumerate(self.changes_applied, 1):
            report += f"{i}. {change}\n"

        report += f"""
**Total changes**: {len(self.changes_applied)}/7 steps

## Validation Results

"""
        for check_name, result in self.validation_results:
            status = "✅ PASS" if result else "❌ FAIL"
            report += f"- {status}: {check_name}\n"

        passed = sum(1 for _, result in self.validation_results if result)
        report += f"""
**Validation score**: {passed}/{len(self.validation_results)} ({passed * 100 // len(self.validation_results)}%)

## Summary

Week 1 section successfully improved using regex-based systematic approach.
All improvements follow Option B (Strategic Layering) principles with cross-references.

**Key achievements**:
- Format unified (W1, 45H, 25テスト)
- Time allocation breakdown added
- Weekly summary added
- Technical specifications added with cross-references
- No full code duplication (Option B compliance)

**Next steps**:
- Review improved content manually
- Apply same approach to Week 2-10
- Validate cross-references work correctly
"""

        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"✅ Report generated: {REPORT_PATH}")
        print("\n" + "=" * 60)
        print("🎉 Week 1 Improvements Complete!")
        print("=" * 60)

    def run(self) -> None:
        """Run complete improvement workflow"""
        try:
            self.load_files()
            self.extract_week1_section()
            self.apply_all_improvements()
            self.validate_improvements()
            self.save_improved_content()
            self.generate_report()

            print("\n✅ SUCCESS: All operations completed")
            return 0

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback

            traceback.print_exc()
            return 1


def main():
    """Main entry point"""
    improver = Week1Improver()
    exit_code = improver.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
