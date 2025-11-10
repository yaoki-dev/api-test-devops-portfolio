#!/usr/bin/env python3
"""Generalized Week Improvement Script

Week 1-10の学習計画を体系的に改善するための一般化スクリプト。
Week番号に応じた技術仕様を自動適用。
"""

import re
from datetime import datetime
from pathlib import Path


class WeekConfig:
    """Week別設定データ"""

    # Week別総学習時間マッピング
    TOTAL_HOURS = {1: 45, 2: 45, 3: 45, 4: 45, 5: 45, 6: 45, 7: 42, 8: 42, 9: 42, 10: 42}

    # Week別目標テスト数マッピング
    TEST_COUNTS = {1: 25, 2: 35, 3: 45, 4: 55, 5: 65, 6: 75, 7: 85, 8: 95, 9: 100, 10: 100}

    # Week別主要技術マッピング
    MAIN_TECHNOLOGIES = {
        1: "Python + httpx Core",
        2: "Python + httpx Integration",
        3: "Async/Await Fundamentals",
        4: "Async/Await Advanced",
        5: "pytest + Fixtures",
        6: "pytest + Pydantic Settings",
        7: "Docker 4-stage",
        8: "CI/CD Integration",
        9: "Portfolio Optimization",
        10: "Job Application",
    }

    # Week別技術仕様挿入設定（Day番号と仕様内容）
    TECH_SPECS = {
        1: {
            2: {
                "title": "エラー階層設計仕様",
                "content": """**エラー階層設計仕様**:
- 5例外クラス実装: APIError（基底） / APIHTTPError（4xx/5xx分離） / APIConnectionError（接続失敗） / APITimeoutError（タイムアウト） / APIValidationError（Pydantic検証失敗）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W1-Day2-エラー階層設計]
""",
            },
            3: {
                "title": "Pydanticモデル仕様",
                "content": """**Pydanticモデル仕様**:
- User/Post/Todo/Comment 4モデル実装
- `model_config = ConfigDict(frozen=True, populate_by_name=True)` でイミュータブル設定
- `Field(alias="userId")` でJSON ↔ Python変換（userId → user_id）
- `EmailStr` で厳密バリデーション
- 1行コードサンプル: `user_id: int = Field(alias="userId")  # JSON "userId" → Python "user_id"`
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W1-Day3-Pydanticモデル実装]
""",
            },
        },
        2: {
            8: {
                "title": "JSONPlaceholder統合完了仕様",
                "content": """**JSONPlaceholder統合完了仕様**:
- `JSONPlaceholderClient` 4エンドポイント実装（users/posts/todos/comments）
- リトライロジック統合（4xx即失敗、5xxリトライ）
- 統合テスト実装（実API呼び出し、mock不使用）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W2-Day8-JSONPlaceholder統合]
""",
            }
        },
        3: {
            14: {
                "title": "非同期クライアント基礎仕様",
                "content": """**非同期クライアント基礎仕様**:
- `AsyncAPIClient` 実装（async/await、httpx.AsyncClient活用）
- コンテキストマネージャー実装（`__aenter__`/`__aexit__`）
- 非同期エラーハンドリング（`asyncio.TimeoutError`、`asyncio.CancelledError`）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W3-Day14-AsyncAPIClient実装]
""",
            },
            15: {
                "title": "asyncio.gather()応用仕様",
                "content": """**asyncio.gather()応用仕様**:
- `asyncio.gather()` による複数API並行呼び出し
- エラーハンドリング戦略（`return_exceptions=True`/`False` 使い分け）
- パフォーマンス測定（並行実行 vs 逐次実行の比較）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W3-Day15-asyncio.gather応用]
""",
            },
        },
        4: {
            20: {
                "title": "非同期統合完了仕様",
                "content": """**非同期統合完了仕様**:
- `AsyncJSONPlaceholderClient` 実装（4エンドポイント非同期対応）
- `get_user_data()` 並行処理実装（users + posts + todos 並行取得）
- パフォーマンステスト実装（P95応答時間 < 500ms）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W4-Day20-非同期統合完了]
""",
            }
        },
        5: {
            26: {
                "title": "pytest fixture設計仕様",
                "content": """**pytest fixture設計仕様**:
- スコープ戦略（session/module/function 使い分け）
- ファクトリーパターン（`user_data_factory`, `todo_data_factory`）
- モック/スタブ実装（`mock_httpx_client`）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W5-Day26-pytest-fixture設計]
""",
            },
            27: {
                "title": "Pydantic Settings階層仕様",
                "content": """**Pydantic Settings階層仕様**:
- 設定クラス階層（`Settings` > `APIConfig`/`LogConfig`/`TestConfig`/`SecurityConfig`）
- 環境変数自動読み込み（ネスト記法`__`区切り: `API__BASE_URL`）
- `SecretStr` 活用（`API_KEY` 保護）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W5-Day27-Pydantic-Settings階層]
""",
            },
        },
        6: {
            32: {
                "title": "カバレッジ78%達成仕様",
                "content": """**カバレッジ78%達成仕様**:
- pytest-cov統合（`--cov-fail-under=78`）
- カバレッジ不足箇所特定（`--cov-report=term-missing`）
- エッジケーステスト追加（エラーパス、境界値）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W6-Day32-カバレッジ78達成]
""",
            }
        },
        7: {
            37: {
                "title": "Multi-stage build仕様",
                "content": """**Multi-stage build仕様**:
- 4ステージ構成（base/deps/dev/prod）
- Layer caching最適化（依存関係→アプリコード順）
- イメージサイズ削減（alpine base、build artifacts削除）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W7-Day37-Multi-stage-build]
""",
            },
            38: {
                "title": "docker-compose 4環境仕様",
                "content": """**docker-compose 4環境仕様**:
- 4環境構成（dev/test/demo/prod）
- 環境別設定（`.env.dev`/`.env.test`/`.env.demo`/`.env.prod`）
- ヘルスチェック実装（`HEALTHCHECK`命令）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W7-Day38-docker-compose-4環境]
""",
            },
        },
        8: {
            43: {
                "title": "GitHub Actions workflow仕様",
                "content": """**GitHub Actions workflow仕様**:
- Stage 1: Lint + Test（ruff, mypy, pytest）
- Stage 2: Security Scan（bandit, safety, trivy）
- Stage 3: Build Docker Image（multi-platform build）
- Stage 4: Deploy to Demo（自動デプロイ、smoke test）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W8-Day43-GitHub-Actions-workflow]
""",
            },
            44: {
                "title": "品質ゲート設計仕様",
                "content": """**品質ゲート設計仕様**:
- カバレッジゲート（85%未満でfail）
- セキュリティゲート（Critical/High脆弱性でfail）
- パフォーマンスゲート（API応答時間P95 < 500ms）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W8-Day44-品質ゲート設計]
""",
            },
        },
        9: {
            49: {
                "title": "README最適化仕様",
                "content": """**README最適化仕様**:
- 技術スタック明示（Python 3.12, httpx, pytest, Docker, GitHub Actions）
- アーキテクチャ図追加（Mermaid図: 3層構造）
- デモ動画/GIF追加（docker-compose up → API呼び出し → テスト実行）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W9-Day49-README最適化]
""",
            },
            50: {
                "title": "Case Study作成仕様",
                "content": """**Case Study作成仕様**:
- 問題提起（Why）: なぜこのプロジェクトを作ったか
- 技術選定（What）: なぜこの技術スタックか
- 設計判断（How）: 主要な設計決定とトレードオフ
- 成果（Result）: カバレッジ85%、CI/CD自動化、市場価値4,500-5,500円
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W9-Day50-Case-Study作成]
""",
            },
        },
        10: {
            55: {
                "title": "応募書類最適化仕様",
                "content": """**応募書類最適化仕様**:
- 職務経歴書（技術スキル・プロジェクト成果・学習姿勢明示）
- ポートフォリオURL一覧（GitHub, README, Case Study, Demo）
- 自己PR（3つの強み: 技術力・学習速度・品質意識）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W10-Day55-応募書類最適化]
""",
            },
            56: {
                "title": "初回応募実施仕様",
                "content": """**初回応募実施仕様**:
- 応募先リスト作成（10社、時給6,000-8,000円）
- カスタマイズ応募書類作成（企業別3パターン）
- 応募追跡シート作成（応募日・企業名・結果・フィードバック）
- 詳細: @[ポートフォリオ戦略分析_改善版.md#W10-Day56-初回応募実施]
""",
            },
        },
    }


class WeekImprover:
    """Week別学習計画改善自動化クラス"""

    def __init__(self, week_num: int):
        """
        Args:
            week_num: Week番号（1-10）
        """
        if week_num < 1 or week_num > 10:
            raise ValueError(f"Week number must be between 1-10, got {week_num}")

        self.week_num = week_num
        self.learning_plan_path = (
            Path(__file__).parent.parent
            / "docs"
            / "プロジェクト再編"
            / "10週ハイブリッドプラン_日次詳細学習スケジュール.md"
        )
        self.learning_plan_content = ""
        self.week_section = ""
        self.week_start = 0
        self.week_end = 0
        self.changes_applied: list[str] = []
        self.validation_results: list[tuple[str, bool]] = []

        # Week別設定読み込み
        self.total_hours = WeekConfig.TOTAL_HOURS[week_num]
        self.test_count = WeekConfig.TEST_COUNTS[week_num]
        self.main_tech = WeekConfig.MAIN_TECHNOLOGIES[week_num]
        self.tech_specs = WeekConfig.TECH_SPECS.get(week_num, {})

    def load_learning_plan(self) -> None:
        """学習計画ファイル読み込み"""
        try:
            with open(self.learning_plan_path, encoding="utf-8") as f:
                self.learning_plan_content = f.read()
            print(f"✅ Loaded learning plan: {len(self.learning_plan_content)} characters")
        except FileNotFoundError:
            raise FileNotFoundError(f"Learning plan file not found: {self.learning_plan_path}")

    def extract_week_section(self) -> None:
        """Week Xセクション抽出（正規表現、行番号ハードコーディング不使用）"""
        # 両方の形式をサポート（"Week X" と "WX"）
        pattern = rf"(### (?:Week {self.week_num}|W{self.week_num}):.*?)(?=### (?:Week {self.week_num + 1}|W{self.week_num + 1}):|$)"
        match = re.search(pattern, self.learning_plan_content, re.DOTALL)

        if not match:
            raise ValueError(f"Week {self.week_num} section not found!")

        self.week_section = match.group(1)
        self.week_start = match.start()
        self.week_end = match.end()

        print(
            f"✅ Extracted Week {self.week_num} section: {len(self.week_section)} characters "
            f"(position {self.week_start}-{self.week_end}, {len(self.week_section.splitlines())} lines)"
        )

    def apply_step1_format_unification(self) -> None:
        """Step 1: フォーマット統一（Week X → WX, XX時間 → XXH, XXテスト → XXテスト）"""
        original = self.week_section

        # Week表記統一
        self.week_section = re.sub(
            rf"### Week {self.week_num}:", f"### W{self.week_num}:", self.week_section
        )

        # 時間表記統一（XX時間 → XXH）
        self.week_section = re.sub(r"(\d+)時間", rf"{self.total_hours}H", self.week_section)

        # テスト数表記統一
        self.week_section = re.sub(r"\d+テスト", f"{self.test_count}テスト", self.week_section)

        if self.week_section != original:
            self.changes_applied.append("Step 1: Format unification completed")
            print(
                f"✅ Step 1: Format unified (W{self.week_num}, {self.total_hours}H, {self.test_count}テスト)"
            )
        else:
            print("⚠️  Step 1: Already unified")

    def apply_step2_time_allocation(self) -> None:
        """Step 2: 時間配分詳細挿入"""
        # 挿入ポイント: Week Xヘッダー直後
        insert_pattern = rf"(### W{self.week_num}:.*?\n)"

        time_allocation = f"""
**時間配分詳細**:
- Phase 1（AI説明・概念理解）: {int(self.total_hours * 0.33)}H
- Phase 2（AI協働実装）: {int(self.total_hours * 0.40)}H
- Phase 3（理解度確認・記録）: {int(self.total_hours * 0.07)}H
- バッファ: {int(self.total_hours * 0.20)}H

"""

        # 既に挿入されているか確認
        if "**時間配分詳細**" in self.week_section:
            print("⚠️  Step 2: Time allocation already inserted")
            return

        match = re.search(insert_pattern, self.week_section, re.DOTALL)
        if match:
            self.week_section = re.sub(
                insert_pattern,
                match.group(1) + time_allocation,
                self.week_section,
                count=1,
                flags=re.DOTALL,
            )
            self.changes_applied.append("Step 2: Time allocation breakdown inserted")
            print("✅ Step 2: Time allocation inserted")
        else:
            print(f"❌ Step 2: Week {self.week_num} header not found")

    def apply_step3_weekly_summary(self) -> None:
        """Step 3: 週次サマリー挿入"""
        # 挿入ポイント: 時間配分詳細の直後
        insert_pattern = r"(- バッファ: \d+H\n)"

        weekly_summary = f"""
**週次サマリー**:
- 主要技術: {self.main_tech}
- 目標テスト数: {self.test_count}件
- カバレッジ目標: Phase 2完了時 {60 + (self.week_num - 1) * 3}%+

"""

        # 既に挿入されているか確認
        if "**週次サマリー**" in self.week_section:
            print("⚠️  Step 3: Weekly summary already inserted")
            return

        match = re.search(insert_pattern, self.week_section)
        if match:
            self.week_section = re.sub(
                insert_pattern, match.group(1) + weekly_summary, self.week_section, count=1
            )
            self.changes_applied.append("Step 3: Weekly summary inserted")
            print("✅ Step 3: Weekly summary inserted")
        else:
            print("❌ Step 3: Time allocation section not found")

    def apply_tech_spec_for_day(self, day_num: int) -> None:
        """Week別技術仕様挿入（Day指定）"""
        if day_num not in self.tech_specs:
            print(f"⏭️  No tech spec for Day {day_num}")
            return

        spec = self.tech_specs[day_num]
        spec_title = spec["title"]
        spec_content = spec["content"]

        # 既に挿入されているか確認
        if spec_title in self.week_section:
            print(f"⚠️  Day {day_num} tech spec already inserted: {spec_title}")
            return

        # Day Xセクション抽出
        day_pattern = rf"(#### \*\*Day {day_num}.*?)\n(#### \*\*Day {day_num + 1}|\Z)"
        day_match = re.search(day_pattern, self.week_section, re.DOTALL)

        if not day_match:
            print(f"❌ Day {day_num} section not found")
            return

        day_section = day_match.group(1)

        # Phase 2挿入ポイント: バッファ行の直後
        insert_pattern = r"(\*\*Phase 2: AI協働実装.*?- バッファ \*\*\[.*?\]\*\*\n)"

        match = re.search(insert_pattern, day_section, re.DOTALL)
        if match:
            updated_day_section = re.sub(
                insert_pattern,
                match.group(1) + "\n" + spec_content,
                day_section,
                count=1,
                flags=re.DOTALL,
            )

            # Week全体セクションを更新
            self.week_section = self.week_section.replace(day_section, updated_day_section)
            self.changes_applied.append(f"Day {day_num}: {spec_title} inserted")
            print(f"✅ Day {day_num}: {spec_title} inserted")
        else:
            print(f"❌ Day {day_num}: Phase 2 header not found")

    def apply_all_steps(self) -> None:
        """全7ステップ適用"""
        print(f"\n{'=' * 60}")
        print(f"Applying improvements to Week {self.week_num}")
        print(f"{'=' * 60}\n")

        self.load_learning_plan()
        self.extract_week_section()

        # Step 1-3: 共通改善
        self.apply_step1_format_unification()
        self.apply_step2_time_allocation()
        self.apply_step3_weekly_summary()

        # Step 4-6: Week別技術仕様挿入
        for day_num in sorted(self.tech_specs.keys()):
            self.apply_tech_spec_for_day(day_num)

        # Step 7: 次週プレビュー（Week 10以外）
        if self.week_num < 10:
            self.apply_step7_next_week_preview()

        # ファイル更新
        self.save_improvements()

        # 検証実行
        self.validate_improvements()
        self.generate_report()

    def apply_step7_next_week_preview(self) -> None:
        """Step 7: 次週プレビュー挿入"""
        next_week_num = self.week_num + 1
        next_week_tech = WeekConfig.MAIN_TECHNOLOGIES.get(next_week_num, "")

        # 最終日番号計算（Week 1-6: 6日、Week 7-10: 6日）
        last_day = self.week_num * 6

        preview_content = f"""
**W{next_week_num}で学ぶこと**:
- 主要技術: {next_week_tech}
- 事前準備: 今週の理解度確認問題（Day {last_day}）で80%以上達成
- 詳細: @[10週ハイブリッドプラン_日次詳細学習スケジュール.md#W{next_week_num}]
"""

        # 既に挿入されているか確認
        if f"**W{next_week_num}で学ぶこと**" in self.week_section:
            print("⚠️  Step 7: Next week preview already inserted")
            return

        # 挿入ポイント: 最終日のPhase 3直後
        insert_pattern = rf"(#### \*\*Day {last_day}.*?\*\*Phase 3: 理解度確認・記録.*?\n)"

        match = re.search(insert_pattern, self.week_section, re.DOTALL)
        if match:
            # Phase 3セクションの終わり（次のDay or セクション終了まで）を探す
            phase3_end_pattern = (
                rf"(\*\*Phase 3: 理解度確認・記録.*?\n)(#### \*\*Day {last_day + 1}|---|\Z)"
            )
            phase3_match = re.search(phase3_end_pattern, self.week_section, re.DOTALL)

            if phase3_match:
                self.week_section = re.sub(
                    phase3_end_pattern,
                    phase3_match.group(1) + preview_content + "\n" + phase3_match.group(2),
                    self.week_section,
                    count=1,
                    flags=re.DOTALL,
                )
                self.changes_applied.append(f"Step 7: W{next_week_num} preview inserted")
                print(f"✅ Step 7: W{next_week_num} preview inserted")
            else:
                print(f"❌ Step 7: Phase 3 end marker not found for Day {last_day}")
        else:
            print(f"❌ Step 7: Day {last_day} Phase 3 not found")

    def save_improvements(self) -> None:
        """改善内容をファイルに保存"""
        # Week全体セクションを元のコンテンツに置換
        updated_content = (
            self.learning_plan_content[: self.week_start]
            + self.week_section
            + self.learning_plan_content[self.week_end :]
        )

        with open(self.learning_plan_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        print(f"\n✅ Improvements saved to: {self.learning_plan_path}")

    def validate_improvements(self) -> None:
        """改善内容を10項目チェックリストで検証"""
        print(f"\n{'=' * 60}")
        print(f"Validation Results for Week {self.week_num}")
        print(f"{'=' * 60}\n")

        checks = [
            (f"Format: W{self.week_num}表記", f"### W{self.week_num}:" in self.week_section),
            (
                f"Format: {self.total_hours}H表記",
                f"({self.total_hours}H)" in self.week_section
                or f"{self.total_hours}H" in self.week_section,
            ),
            (
                f"Format: {self.test_count}テスト表記",
                f"{self.test_count}テスト" in self.week_section,
            ),
            ("Time allocation present", "Phase 1（AI説明・概念理解）" in self.week_section),
            ("Weekly summary present", "**週次サマリー**" in self.week_section),
        ]

        # Week別技術仕様チェック追加
        for day_num, spec in self.tech_specs.items():
            spec_title = spec["title"]
            checks.append((f"Day {day_num} {spec_title}", spec_title in self.week_section))

        # 次週プレビューチェック（Week 10以外）
        if self.week_num < 10:
            checks.append(
                (
                    f"W{self.week_num + 1} preview",
                    f"**W{self.week_num + 1}で学ぶこと**" in self.week_section,
                )
            )

        # クロスリファレンスチェック
        checks.append(
            ("Cross-references present", "@[ポートフォリオ戦略分析_改善版.md" in self.week_section)
        )

        passed = 0
        for check_name, result in checks:
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"- {status}: {check_name}")
            self.validation_results.append((check_name, result))
            if result:
                passed += 1

        total = len(checks)
        score = int((passed / total) * 100)
        print(f"\n**Validation score**: {passed}/{total} ({score}%)")

        if score < 80:
            print("⚠️  Warning: Validation score below 80% threshold!")

    def generate_report(self) -> None:
        """改善レポート生成"""
        report_dir = Path(__file__).parent.parent / "docs" / "プロジェクト再編"
        report_path = report_dir / f"Week{self.week_num}_improvement_report.md"

        timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")

        report = f"""# Week {self.week_num} Improvement Report

*Generated: {timestamp}*

## Changes Applied

"""

        if self.changes_applied:
            for i, change in enumerate(self.changes_applied, 1):
                report += f"{i}. {change}\n"
            report += f"\n**Total changes**: {len(self.changes_applied)} steps\n"
        else:
            report += "No changes applied (all improvements already present)\n"

        report += "\n## Validation Results\n\n"

        for check_name, result in self.validation_results:
            status = "✅ PASS" if result else "❌ FAIL"
            report += f"- {status}: {check_name}\n"

        passed = sum(1 for _, result in self.validation_results if result)
        total = len(self.validation_results)
        score = int((passed / total) * 100)

        report += f"\n**Validation score**: {passed}/{total} ({score}%)\n"

        report += f"""
## Summary

Week {self.week_num} section successfully improved using regex-based systematic approach.
All improvements follow Option B (Strategic Layering) principles with cross-references.

**Key achievements**:
- Format unified (W{self.week_num}, {self.total_hours}H, {self.test_count}テスト)
- Time allocation breakdown added
- Weekly summary added
- Technical specifications added with cross-references
- No full code duplication (Option B compliance)

**Next steps**:
- Review improved content manually
- Apply same approach to remaining weeks
- Validate cross-references work correctly

"""

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print(f"\n✅ Report generated: {report_path}")


def main():
    """Week 2改善実行（デモ）"""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python week_improver.py <week_number>")
        print("Example: python week_improver.py 2")
        sys.exit(1)

    try:
        week_num = int(sys.argv[1])
        improver = WeekImprover(week_num)
        improver.apply_all_steps()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
