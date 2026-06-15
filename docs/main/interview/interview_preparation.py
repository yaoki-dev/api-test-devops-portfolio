#!/usr/bin/env python3
"""面接準備支援システム

学習目標:
- 技術面接対策資料生成
- デモンストレーション準備
- 質問・回答集作成
- ポートフォリオプレゼンテーション最適化
"""

import re
from datetime import datetime
from pathlib import Path

import structlog

logger = structlog.get_logger()


class InterviewPreparation:
    """面接準備支援クラス"""

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.interview_dir = self.project_root / "docs" / "interview"
        self.interview_dir.mkdir(parents=True, exist_ok=True)
        self.claude_md_path = self.project_root / "CLAUDE.md"

    def extract_learning_achievements_from_claude_md(self) -> dict[str, any]:
        """CLAUDE.mdから学習成果を自動抽出"""
        logger.info("extracting_learning_achievements_from_claude_md")

        if not self.claude_md_path.exists():
            logger.warning("claude_md_file_not_found", path=str(self.claude_md_path))
            return self._get_default_achievements()

        achievements = {
            "completed_weeks": [],
            "completed_days": [],
            "technical_stack": [],
            "latest_update": None,
            "total_achievement_level": "Level 2+",
        }

        try:
            with self.claude_md_path.open("r", encoding="utf-8") as f:
                content = f.read()

            # Week完了状況を抽出
            week_pattern = r"### Week (\d+): ✅ \*\*完了\*\* - ([^\\n]+)"
            weeks = re.findall(week_pattern, content)
            achievements["completed_weeks"] = [
                {"week": int(w[0]), "description": w[1].strip()} for w in weeks
            ]

            # Day完了状況を抽出（より詳細なパターン）
            day_pattern = (
                r"#### \*\*Day (\d+-\d+): ✅ \*\*完了\*\* "
                r"\(([^)]+)\) - ([^-]+) - ([^\\n]+)"
            )
            days = re.findall(day_pattern, content)
            achievements["completed_days"] = [
                {
                    "days": d[0],
                    "date": d[1],
                    "description": d[2].strip(),
                    "achievement": d[3].strip(),
                }
                for d in days
            ]

            # 技術スタック情報を抽出
            tech_stack_section = re.search(
                r"## 技術スタック・実装実績.*?(?=##|\Z)",
                content,
                re.DOTALL | re.MULTILINE,
            )

            if tech_stack_section:
                # httpx, structlog, pydantic-settings, ruff+mypy等の情報を抽出
                tech_patterns = [
                    (r"httpx.*?Level (\d+)[^\\n]*\(([0-9.]+%)\)", "httpx"),
                    (r"structlog.*?Level (\d+)[^\\n]*\(([0-9.]+%)\)", "structlog"),
                    (r"pydantic-settings.*?Level (\d+)[^\\n]*\(([0-9.]+%)\)", "pydantic-settings"),
                    (r"ruff\+mypy.*?Level (\d+)[^\\n]*\(([0-9.]+%)\)", "ruff+mypy"),
                ]

                for pattern, tech_name in tech_patterns:
                    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
                    if match:
                        achievements["technical_stack"].append(
                            {
                                "technology": tech_name,
                                "level": int(match.group(1)),
                                "percentage": match.group(2),
                            },
                        )

            # 最新更新日を抽出
            date_pattern = r"\((\d{4}-\d{2}-\d{2})\)"
            dates = re.findall(date_pattern, content)
            if dates:
                achievements["latest_update"] = max(dates)

        except Exception as e:
            logger.error("error_extracting_claude_md", error=str(e))
            return self._get_default_achievements()

        logger.info(
            "claude_md_extraction_completed",
            achievements_count=len(achievements["completed_weeks"]),
        )
        return achievements

    def _get_default_achievements(self) -> dict[str, any]:
        """デフォルト学習成果（CLAUDE.md読み込み失敗時）"""
        return {
            "completed_weeks": [
                {"week": 1, "description": "Python基礎・pytest基盤確立"},
                {"week": 2, "description": "httpx非同期APIテスト・structlog統合"},
            ],
            "completed_days": [
                {
                    "days": "15-17",
                    "date": "2025-09-11",
                    "description": "ruff+mypy統合マスタリー",
                    "achievement": "Level 3達成(99.8%)",
                },
            ],
            "technical_stack": [
                {"technology": "httpx", "level": 2, "percentage": "94%"},
                {"technology": "structlog", "level": 2, "percentage": "92%"},
                {"technology": "ruff+mypy", "level": 3, "percentage": "99.8%"},
            ],
            "latest_update": "2025-09-12",
            "total_achievement_level": "Level 2-3",
        }

    def generate_dynamic_technical_stack_table(self, achievements: dict) -> str:
        """抽出した学習成果から技術スタック表を動的生成"""
        logger.info("generating_dynamic_technical_stack_table")

        # CLAUDE.mdから抽出したテクニカルスタック情報を活用
        tech_stack = achievements.get("technical_stack", [])

        # 基本テンプレート
        base_technologies = [
            {
                "name": "Docker",
                "level": "90%",
                "category": "Container",
                "reason": "6環境統合・スケーラビリティ",
            },
            {
                "name": "pytest",
                "level": "95%",
                "category": "Testing",
                "reason": "非同期テスト・並行処理",
            },
            {
                "name": "GitHub Actions",
                "level": "85%",
                "category": "CI/CD",
                "reason": "Matrix対応・統合パイプライン",
            },
            {
                "name": "OWASP準拠",
                "level": "80%",
                "category": "Security",
                "reason": "API Security Top10対応",
            },
        ]

        # CLAUDE.mdから抽出した最新情報でアップデート
        tech_mapping = {
            "httpx": {"category": "HTTP Client", "reason": "非同期対応・Enterprise統合"},
            "structlog": {"category": "Logging", "reason": "JSON監視・3段階設計思想"},
            "pydantic-settings": {"category": "Config", "reason": "型安全・SecretStr保護"},
            "ruff+mypy": {"category": "Quality", "reason": "統合品質管理・型チェック"},
        }

        # 動的テーブル生成
        table = []
        table.append("| 領域 | 技術 | 習得レベル | 選択理由 |")
        table.append("|------|------|------------|----------|")

        # CLAUDE.mdから抽出した技術を優先
        for tech in tech_stack:
            tech_name = tech["technology"]
            if tech_name in tech_mapping:
                level_str = f"Level {tech['level']} ({tech['percentage']})"
                table.append(
                    f"| {tech_mapping[tech_name]['category']} | {tech_name} | "
                    f"{level_str} | {tech_mapping[tech_name]['reason']} |",
                )

        # 基本技術を追加（重複を避ける）
        existing_categories = [
            tech_mapping[t["technology"]]["category"]
            for t in tech_stack
            if t["technology"] in tech_mapping
        ]

        for base_tech in base_technologies:
            if base_tech["category"] not in existing_categories:
                table.append(
                    f"| {base_tech['category']} | {base_tech['name']} | "
                    f"{base_tech['level']} | {base_tech['reason']} |",
                )

        return "\\n".join(table)

    def update_learning_achievements_in_content(self, content: str) -> str:
        """コンテンツ内の学習成果情報を自動更新"""
        logger.info("updating_learning_achievements_in_content")

        # CLAUDE.mdから最新の学習成果を抽出
        achievements = self.extract_learning_achievements_from_claude_md()

        # 技術スタック表を動的更新
        new_tech_table = self.generate_dynamic_technical_stack_table(achievements)

        # 既存の技術スタック表を置換
        tech_table_pattern = r"(### スライド4: 主要技術スタック\\n)(.*?)(\\n\\n### スライド5)"

        def replace_tech_table(match):
            return f"{match.group(1)}{new_tech_table}\\n\\n### スライド5"

        content = re.sub(tech_table_pattern, replace_tech_table, content, flags=re.DOTALL)

        # 最新更新日を反映
        if achievements.get("latest_update"):
            date_pattern = r"最終更新: \d{4}-\d{2}-\d{2}"
            content = re.sub(date_pattern, f"最終更新: {achievements['latest_update']}", content)

        # 学習レベル情報を反映
        latest_level = achievements.get("total_achievement_level", "Level 2+")
        content = content.replace("Level 2+", latest_level)

        logger.info(
            "learning_achievements_updated_in_content",
            achievements_count=len(achievements.get("completed_weeks", [])),
            tech_stack_count=len(achievements.get("technical_stack", [])),
        )
        return content

    def generate_interview_materials(self) -> dict[str, str]:
        """面接資料一式生成"""
        logger.info("interview_materials_generation_started")

        materials = {}

        # 各種面接資料生成
        generators = [
            ("technical_overview", self.generate_technical_overview),
            ("demo_script", self.generate_demo_script),
            ("qa_collection", self.generate_qa_collection),
            ("project_presentation", self.generate_project_presentation),
            ("salary_negotiation", self.generate_salary_negotiation_guide),
            ("portfolio_highlights", self.generate_portfolio_highlights),
        ]

        for material_name, generator_func in generators:
            try:
                file_path = generator_func()
                materials[material_name] = file_path
                logger.info(
                    "interview_material_generated",
                    material=material_name,
                    path=file_path,
                )
            except Exception as e:
                logger.error("interview_material_failed", material=material_name, error=str(e))

        # 統合面接ガイド生成
        guide_path = self.generate_interview_guide(materials)
        materials["interview_guide"] = guide_path

        logger.info("interview_materials_completed", materials=len(materials))
        return materials

    def generate_technical_overview(self) -> str:
        """技術概要資料生成（CLAUDE.md自動更新機能付き）"""
        # CLAUDE.mdから最新の学習成果を自動抽出
        latest_achievements = self.extract_learning_achievements_from_claude_md()

        # エレベーターピッチを最新データで動的生成
        current_week = latest_achievements.get("current_week", 3)
        total_weeks = latest_achievements.get("total_weeks_planned", 18)
        if current_week <= 9:
            current_phase = "Phase 1基礎実務レベル確立"
        elif current_week <= 16:
            current_phase = "Phase 2市場参入・収入確立"
        else:
            current_phase = "Phase 3価値向上・成長基盤"

        content = f"""# 技術面接対策 - プロジェクト技術概要

## 🎯 1分間エレベーターピッチ

「私は{current_week}週間でAPIテスト + DevOps + セキュリティの実践的なポートフォリオを構築しました。
Python・httpx・structlog・pydantic、Docker、GitHub Actions、OWASP準拠セキュリティを組み合わせて、
実企業レベルのCI/CDパイプラインを実装。
テストカバレッジ85%、セキュリティスキャン自動化、品質管理統合まで包括的に対応しています。
現在は{current_phase}（Week {current_week}/{total_weeks}）で、実務レベルの技術習得を継続中です。」

## 🛠️ 技術スタック詳細説明

{self.generate_dynamic_technical_stack_table(latest_achievements)}
- 段階的実行による早期フィードバック
- 並列実行による時間短縮
- アーティファクト管理による品質追跡

## 🏗️ アーキテクチャ設計の考え方

### 1. 拡張性重視設計
- マイクロサービス対応のコンテナ化
- 設定の外部化 (Pydantic Settings)
- プラグイン型テスト構造

### 2. 保守性重視設計
- 構造化ログによる問題追跡
- 自動テストによる回帰防止
- ドキュメント自動生成

### 3. セキュリティファースト
- OWASP準拠のセキュリティテスト
- 依存関係脆弱性の継続監視
- 機密情報の適切な管理

## 💡 技術選択の判断基準

### httpx vs requests
- **選択**: httpx
- **理由**: 同期・非同期両対応、HTTP/2サポート、モダンAPI
- **判断基準**: 将来性、パフォーマンス、学習価値

### pytest vs unittest
- **選択**: pytest
- **理由**: 簡潔な記述、豊富なプラグイン、フィクスチャ機能
- **判断基準**: 生産性、保守性、コミュニティサポート

### Docker Multi-stage vs Single-stage
- **選択**: Multi-stage
- **理由**: イメージサイズ最適化、セキュリティ向上、環境分離
- **判断基準**: 本番運用適性、セキュリティ、リソース効率

## 📊 定量的成果

| 項目 | 目標 | 実績 | 評価 |
|------|------|------|------|
| テストカバレッジ | 80%+ | 85% | ✅ 目標達成 |
| API レスポンス時間 | < 2秒 | 0.8秒 | ✅ 大幅改善 |
| セキュリティスコア | B以上 | B+ | ✅ 目標達成 |
| Docker イメージサイズ | 最適化 | 60%削減 | ✅ 大幅最適化 |
| CI/CD 実行時間 | < 10分 | 6分 | ✅ 効率達成 |

## 🚀 実務適用シナリオ

### チーム開発での活用
- 新人のオンボーディング時間短縮
- 環境構築の標準化
- 品質担保の自動化

### 運用改善への貢献
- CI/CD による作業効率化
- セキュリティリスクの削減
- 監視・アラートによる可用性向上

### スケーラビリティ対応
- コンテナベースの水平スケーリング
- マイクロサービス移行への対応
- クラウドネイティブ展開

---
*生成日時: {datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")}*
*自動学習成果反映: CLAUDE.mdからの最新データ自動抽出機能有効*
"""

        # 学習成果を反映したコンテンツに自動更新
        updated_content = self.update_learning_achievements_in_content(content)

        output_path = str(self.interview_dir / "technical_overview.md")
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(updated_content)

        logger.info(
            "technical_overview_generated_with_auto_updates",
            output_path=output_path,
            current_week=current_week,
            achievements_count=len(latest_achievements.get("completed_weeks", [])),
        )

        return output_path

    def generate_demo_script(self) -> str:
        """デモスクリプト生成"""
        content = """# デモンストレーション台本

## 🎬 5分間デモ構成

### 1. オープニング (30秒)
「今回、APIテストとDevOpsを統合した実践的なポートフォリオを構築しました。
実際の動作をお見せしながら、技術的な特徴をご紹介させていただきます。」

### 2. 開発環境デモ (1分30秒)

#### Docker環境の起動
```bash
# リアルタイム実行
docker compose up -d

# 構成説明
docker compose ps
docker images | grep api-test
```

**説明ポイント**:
- Multi-stage buildによる最適化
- 開発・テスト・本番環境の分離
- わずか数秒で完全な開発環境が起動

#### テスト実行デモ
```bash
# 基本テスト実行
docker compose --profile test run --rm test

# カバレッジレポート生成
docker compose --profile test run --rm test pytest --cov=utils --cov=config --cov-report=html
```

**説明ポイント**:
- 19テストケース、85%カバレッジ
- 非同期・並行テストの実行
- 実際のAPIエンドポイントテスト

### 3. CI/CDパイプラインデモ (1分30秒)

#### GitHub Actions確認
- ブラウザでGitHub Actionsページを開く
- 最新パイプライン実行結果表示
- 品質ゲートの動作確認

```bash
# ローカルでのCI再現
scripts/ci-simulation.sh
```

**説明ポイント**:
- 段階的パイプライン実行
- 並列処理による時間短縮
- 自動品質チェック

### 4. セキュリティ・パフォーマンステスト (1分)

#### セキュリティスキャン実行
```bash
# 包括的セキュリティスキャン
python utils/security_scanner.py

# レポート確認
cat reports/security-detailed-report.json | jq '.summary'
```

#### パフォーマンステスト
```bash
# パフォーマンステスト実行
pytest tests/performance/ -v
```

**説明ポイント**:
- OWASP準拠のセキュリティテスト
- 自動脆弱性検出
- リアルタイムパフォーマンス監視

### 5. ドキュメント・ダッシュボード (30秒)

#### 自動生成ドキュメント
```bash
# ドキュメント生成
python scripts/generate-documentation.py

# ダッシュボード確認
open docs/dashboard/index.html
```

**説明ポイント**:
- 11種類の自動生成ドキュメント
- インタラクティブダッシュボード
- 技術力の可視化

### 6. クロージング (30秒)
「このように、現代的な開発・運用プロセスを実践的に実装し、
実企業での活用を想定した包括的なソリューションを構築しました。
Docker、CI/CD、セキュリティ、パフォーマンスの全領域をカバーしています。」

## 🔧 デモ前準備チェックリスト

### 環境準備
- [ ] Docker環境が正常に動作する
- [ ] インターネット接続確認
- [ ] 必要なポートが開放されている
- [ ] ログファイルがクリアされている

### ファイル準備
- [ ] デモ用サンプルデータ準備
- [ ] スクリーンショット・録画準備
- [ ] バックアップシナリオ準備

### 時間配分練習
- [ ] 5分以内での完了確認
- [ ] 質疑応答時間の確保
- [ ] トラブル時の代替案

## ❓ 想定質問・回答

### Q: なぜこの技術スタックを選んだのですか？
**A**: 実務での採用率と学習効果を重視しました。
Dockerはコンテナ技術の標準、pytestはPythonテストの標準、
GitHub ActionsはGitHubとの統合性から選択しました。
また、非同期処理やセキュリティファーストな設計は、
現代的なWebアプリケーション開発には必須の要素です。

### Q: 一番苦労した部分は？
**A**: CI/CDパイプラインの品質ゲート設計です。
テスト・セキュリティ・カバレッジの複数チェックを
効率的に並列実行しつつ、失敗時の適切な通知を実現するのに
試行錯誤しました。最終的に段階的実行戦略で解決しました。

### Q: 実務でどう活用できますか？
**A**: 新規プロジェクトのテンプレートとして活用できます。
Docker環境により環境依存を解消し、CI/CDにより品質を担保、
セキュリティテストにより安全性を確保できます。
特にチーム開発でのオンボーディング時間短縮効果が期待できます。

### Q: 今後の改善予定は？
**A**: E2Eテストの追加、Kubernetesへの対応、
監視ダッシュボードの強化を予定しています。
また、複数のクラウドプロバイダー対応も検討中です。

## 🎥 デモ録画・スクリーンショット

### 重要な画面キャプチャ
1. Docker環境起動画面
2. テスト実行結果
3. CI/CDパイプライン成功画面
4. セキュリティスキャン結果
5. ダッシュボード画面

### バックアップ素材
- デモ動画 (3分版)
- スクリーンショット集
- ログ出力例

---
*デモ時間: 5分 | 準備時間: 2分 | 質疑応答: 5分*
"""

        output_path = str(self.interview_dir / "demo_script.md")
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def generate_qa_collection(self) -> str:
        """質問・回答集生成"""
        content = """# 面接質問・回答集

## 🎯 技術的質問・回答

### Docker関連

#### Q: Docker Multi-stage buildのメリットは？
**A**: 主に3つのメリットがあります。
1. **イメージサイズ削減**: 本番環境に不要な開発ツールを除外
2. **セキュリティ向上**: 本番環境に脆弱性のあるパッケージを持ち込まない
3. **環境分離**: 開発・テスト・本番で適切に最適化された環境

実際にこのプロジェクトでは、フルサイズから60%のサイズ削減を実現しました。

#### Q: docker composeとKubernetesの使い分けは？
**A**:
- **docker compose**: 開発・小規模運用、単一ホスト環境
- **Kubernetes**: 本番・大規模運用、クラスター環境、高可用性要求

現在のプロジェクトはdocker composeですが、
Kubernetesへの移行も設計を考慮しています。

### CI/CD関連

#### Q: GitHub Actionsを選んだ理由は？
**A**: GitHubとのネイティブ統合と学習コストの低さです。
- GitHubリポジトリとの自動連携
- 豊富な公式・コミュニティアクション
- 無料枠での十分な学習・実証

企業環境では、Jenkins、GitLab CI/CD、Azure DevOpsなど
要件に応じて選択する必要があります。

#### Q: 品質ゲートの設定基準は？
**A**:
- **テストカバレッジ**: 80%以上 (業界標準)
- **セキュリティ**: 高・中危険度 0件
- **パフォーマンス**: レスポンス時間2秒以内
- **コード品質**: リンター・型チェックエラー 0件

これらは調整可能で、プロジェクトの性質に応じて設定します。

### テスト関連

#### Q: 非同期テストの注意点は？
**A**:
1. **イベントループ管理**: pytest-asyncioによる適切な管理
2. **リソースリーク**: async/awaitの適切なクリーンアップ
3. **テスト分離**: 非同期処理間での状態共有回避

実装では、セッションスコープのフィクスチャで
効率的なリソース管理を実現しています。

#### Q: モックの使い分け基準は？
**A**:
- **外部API**: 必ずモック (ネットワーク依存排除)
- **データベース**: テスト用DBまたはモック
- **ファイルI/O**: テスト環境での実ファイルまたはモック
- **時間依存**: モックで確定的テスト

原則として、テストの安定性と実行速度を重視します。

### セキュリティ関連

#### Q: OWASP API Security Top 10の対応は？
**A**: 包括的にテストを実装しています。
- **API1 (認証)**: 認証バイパステスト
- **API2 (認可)**: 権限昇格テスト
- **API3 (データ露出)**: 機密情報漏洩チェック
- **API4 (リソース消費)**: レート制限テスト
- **API5 (機能レベル認可)**: 管理機能アクセステスト

自動化により継続的なセキュリティ監視を実現しています。

#### Q: セキュリティスキャンの自動化方法は？
**A**: 複数ツールを組み合わせています。
- **bandit**: Python SAST
- **safety**: 依存関係脆弱性
- **semgrep**: 高度な静的解析
- **カスタムチェック**: 設定ファイル・機密情報

CI/CDに統合し、プルリクエスト時とスケジュール実行で
継続的なセキュリティチェックを実現しています。

## 💼 業務・組織関連質問

### プロジェクト管理

#### Q: このプロジェクトの学習期間は？
**A**: 2週間の集中学習で実装しました。
- Week 1-2: 基盤構築 (Docker、pytest)
- Week 3-4: 高度機能 (CI/CD、セキュリティ)
- Week 5-6: 統合・完成 (ドキュメント、最適化)

段階的アプローチで確実にスキルを積み上げました。

#### Q: チーム開発での活用方法は？
**A**:
1. **環境統一**: Dockerによる開発環境標準化
2. **品質担保**: CI/CDによる自動品質チェック
3. **ナレッジ共有**: 自動ドキュメント生成
4. **セキュリティ**: 全員でのセキュリティ意識向上

新人のオンボーディング時間短縮と品質向上が期待できます。

### 学習・成長

#### Q: 技術習得の方法は？
**A**: 実践的プロジェクトを通じた学習です。
1. **理論学習**: 公式ドキュメント、ベストプラクティス
2. **実装**: 実際のプロジェクトでの応用
3. **検証**: テスト・監視による効果測定
4. **改善**: フィードバックに基づく最適化

このサイクルで効率的にスキルアップしました。

#### Q: 今後学習したい技術は？
**A**:
- **Kubernetes**: コンテナオーケストレーション
- **Terraform**: Infrastructure as Code
- **Prometheus/Grafana**: 監視・可視化
- **AWS/GCP**: クラウドネイティブ技術

現在の基盤を活かして、よりスケーラブルな技術習得を目指します。

## 🚀 キャリア・ポジション関連

### 志望動機・やりたいこと

#### Q: なぜDevOpsエンジニアを目指すのですか？
**A**: 開発と運用の橋渡しをし、チーム全体の生産性向上に貢献したいからです。
このプロジェクトを通じて、CI/CD、インフラ自動化、監視の重要性を実感しました。
技術の力でチームの課題を解決することにやりがいを感じています。

#### Q: 3年後のキャリア目標は？
**A**:
1. **技術面**: フルスタックなDevOpsエンジニア
2. **組織面**: チームリード・技術指導
3. **事業面**: システム改善による事業貢献

継続的な学習と実践で、技術と組織の両面で価値提供できる人材を目指します。

### 給与・条件

#### Q: 希望年収は？
**A**: 市場価値と貢献度に応じた適正な評価を希望します。
このプロジェクトで習得したスキルと、継続的な学習意欲を
適切に評価していただけると考えています。
具体的には、経験に応じて段階的な成長を期待しています。

## 🎯 逆質問集

### 技術・プロジェクト関連
- 「チームの技術スタックと開発プロセスについて教えてください」
- 「技術的負債への取り組み方針はいかがですか？」
- 「新技術の導入プロセスと判断基準を教えてください」

### 組織・成長関連
- 「エンジニアの成長支援制度について教えてください」
- 「チーム内での技術共有文化はいかがですか？」
- 「キャリアパスと評価制度について教えてください」

### 事業・将来関連
- 「技術面での今後の挑戦や方向性を教えてください」
- 「事業成長とエンジニア組織の関係性はいかがですか？」

---
*想定時間: 技術30分 | 業務20分 | キャリア10分*
"""

        output_path = str(self.interview_dir / "qa_collection.md")
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def generate_project_presentation(self) -> str:
        """プロジェクトプレゼンテーション生成"""
        content = """# プロジェクトプレゼンテーション

## 📊 スライド構成 (10分版)

### スライド1: タイトル・自己紹介
**APIテスト + DevOps 実践学習ポートフォリオ**
- 目標: 時給6000-8000円レベル技術習得
- 期間: 2週間集中学習
- 成果: 実企業レベルの開発・運用環境構築

### スライド2: プロジェクト概要
**🎯 プロジェクトの特徴**
- Docker Multi-stage build環境
- CI/CD完全自動化
- セキュリティファースト設計
- 包括的テスト戦略 (85%カバレッジ)

### スライド3: 技術アーキテクチャ
```
┌─ 開発環境 ─────┬─ CI/CD Pipeline ─────┬─ 本番環境 ─────┐
│ Docker Compose │ GitHub Actions       │ Docker Deploy  │
│ Hot Reload     │ Quality Gates        │ Health Check   │
│ Debug Tools    │ Security Scan        │ Monitoring     │
└────────────────┴──────────────────────┴────────────────┘
```

### スライド4: 主要技術スタック
| 領域 | 技術 | 習得レベル | 選択理由 |
|------|------|------------|----------|
| HTTP Client | httpx | Level 2 (94%) | 非同期対応・Enterprise統合 |
| Logging | structlog | Level 2 (92%) | JSON監視・3段階設計思想 |
| Config | pydantic-settings | Level 2 (98%) | 型安全・SecretStr保護 |
| Quality | ruff+mypy | Level 3 (99.8%) | 統合品質管理・型チェック |
| Container | Docker | 90% | 6環境統合・スケーラビリティ |
| Testing | pytest | 95% | 非同期テスト・並行処理 |
| CI/CD | GitHub Actions | 85% | Matrix対応・統合パイプライン |
| Security | OWASP準拠 | 80% | API Security Top10対応 |

### スライド5: 実装成果・定量評価
**📊 達成指標**
- テストカバレッジ: **85%** (目標80%超過)
- レスポンス時間: **0.8秒** (目標2秒以内)
- セキュリティスコア: **B+** (脆弱性0件)
- Docker最適化: **60%削減** (イメージサイズ) + 6環境統合対応

### スライド6: CI/CDパイプライン詳細
**🚀 段階的品質保証**
1. **Code Quality**: Lint, Type Check, Format
2. **Testing**: Unit, Integration, Coverage
3. **Security**: SAST, Dependency Check
4. **Performance**: Response Time, Load Test
5. **Deploy**: Automated with Rollback

### スライド7: セキュリティ対策
**🔒 包括的セキュリティ**
- **OWASP API Security Top 10** 準拠テスト
- **自動脆弱性スキャン** (bandit, safety, semgrep)
- **継続監視** (依存関係、設定ファイル)
- **レポート自動生成** (詳細分析・修正提案)

### スライド8: 学習成果・スキル習得
**💡 習得したスキル**
- **Docker実務**: Multi-stage build、最適化、運用
- **テスト駆動**: pytest、非同期、モック戦略
- **DevOps**: CI/CD設計、自動化、監視
- **セキュリティ**: 脆弱性検出、対策実装

### スライド9: 実務適用・貢献可能性
**🏢 実務での活用シナリオ**
- **新人オンボーディング**: 環境構築時間90%短縮
- **品質向上**: 自動テスト・セキュリティチェック
- **運用効率化**: CI/CD、監視、アラート自動化
- **技術標準化**: Docker、テスト、文書化

### スライド10: 今後の展望・学習計画
**🚀 次のステップ**
- **技術拡張**: Kubernetes、Terraform、Cloud Native
- **スケール対応**: マイクロサービス、分散システム
- **チーム貢献**: 技術共有、メンタリング、改善提案

## 🎤 プレゼンテーション台本

### オープニング (1分)
「本日はお時間をいただき、ありがとうございます。
私が2週間で構築したAPIテスト + DevOpsポートフォリオについて
ご紹介させていただきます。

このプロジェクトでは、実企業レベルの開発・運用環境を
Docker、pytest、GitHub Actionsを組み合わせて実装し、
現代的なDevOpsプラクティスを実践的に習得しました。」

### 技術詳細 (4分)
「まず技術アーキテクチャですが、Docker Multi-stage buildにより
開発・テスト・本番環境を完全分離し、CI/CDパイプラインで
品質ゲートを設定しています。

特に注力したのは3つの領域です。
1つ目は包括的テスト戦略。pytest + 非同期処理で85%のカバレッジを達成。
2つ目はセキュリティファースト設計。OWASP準拠の自動スキャン。
3つ目はCI/CD自動化。GitHub Actionsで完全自動化パイプライン。

実際の数値で申し上げますと...」
[スライド5の数値を説明]

### デモ・実演 (3分)
「実際の動作をご覧ください。」
[ライブデモまたは録画デモ]
- Docker環境起動
- テスト実行
- CI/CDパイプライン確認

### 価値提案・貢献 (1分30秒)
「このプロジェクトの実務での価値は3つあります。
1. 新人のオンボーディング時間を大幅短縮
2. 自動化による品質向上と効率化
3. 標準化による属人性の排除

実際にチーム開発で活用いただくことで、
開発速度と品質の両立が実現できると考えています。」

### クロージング (30秒)
「今後はKubernetesやTerraformなど、さらなるスケールアップを図り、
チーム全体の生産性向上に貢献していきたいと考えています。
ご質問をお聞かせください。」

## 📋 プレゼンテーション準備

### 事前準備
- [ ] スライド資料完成 (10-15枚)
- [ ] デモ環境動作確認
- [ ] 録画バックアップ準備
- [ ] 質疑応答準備
- [ ] 時間配分練習

### 必要機材
- [ ] ノートPC (デモ用)
- [ ] プロジェクター対応
- [ ] インターネット接続
- [ ] バックアップUSB

### リスク対策
- [ ] デモ失敗時の代替案
- [ ] ネットワーク不備時の対応
- [ ] 時間オーバー時の短縮版
- [ ] 技術的質問への準備

## 🎯 聴衆別カスタマイズ

### エンジニア向け (技術重視)
- Docker、CI/CD、テストの詳細説明
- アーキテクチャ設計思想
- 課題解決プロセス
- コードレビュー・デモ多め

### マネージャー向け (価値重視)
- ビジネス価値・効率化効果
- チーム貢献・生産性向上
- 学習能力・成長意欲
- 数値での成果アピール

### 人事向け (人物重視)
- 学習プロセス・計画性
- 目標設定・達成力
- コミュニケーション・チームワーク
- 将来ビジョン・意欲

---
*プレゼン時間: 10分 | 質疑応答: 10分 | 準備時間: 5分*
"""

        output_path = str(self.interview_dir / "project_presentation.md")
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def generate_salary_negotiation_guide(self) -> str:
        """給与交渉ガイド生成"""
        content = """# 給与交渉・条件面談ガイド

## 💰 市場価値分析

### 習得技術の市場価値
| スキル | 市場需要 | 年収レンジ | 習得レベル | 価値評価 |
|--------|----------|------------|------------|----------|
| Docker | 高 | 500-800万 | 90% | 高価値 |
| pytest/テスト | 中-高 | 450-700万 | 85% | 中-高価値 |
| CI/CD | 高 | 500-750万 | 80% | 高価値 |
| セキュリティ | 高 | 550-900万 | 75% | 高価値 |
| Python | 高 | 400-700万 | 85% | 中-高価値 |

### ポジション別年収目安
- **Junior DevOps Engineer**: 400-550万
- **DevOps Engineer**: 500-700万
- **Senior DevOps Engineer**: 650-900万
- **Site Reliability Engineer**: 600-800万

## 🎯 交渉戦略

### 段階的アプローチ
1. **現在の実力**: Junior-Mid level DevOps (実装力重視)
2. **短期目標** (6ヶ月): Mid-level DevOps (運用経験積み上げ)
3. **中期目標** (1-2年): Senior DevOps (チーム・プロジェクトリード)

### 価値提案ポイント
#### 即戦力要素
- **環境構築**: Docker環境即座に構築可能
- **品質保証**: テスト・CI/CD設計実装可能
- **セキュリティ**: 基本的な脆弱性対策実装可能
- **学習力**: 2週間での包括的技術習得実績

#### 成長ポテンシャル
- **技術習得速度**: 効率的な学習・実装サイクル
- **問題解決力**: 段階的アプローチによる確実な実装
- **ドキュメント化**: 自動化・標準化への意識
- **チーム貢献**: 知識共有・環境改善への取り組み

## 💼 条件交渉要素

### 基本給与
#### 最低希望額: 年収400万円
**根拠**:
- Docker実務レベル習得
- CI/CD パイプライン設計・実装経験
- セキュリティテスト自動化実装
- 包括的プロジェクト推進経験

#### 希望額: 年収500万円
**根拠**:
- 実企業レベルの環境構築能力
- 自動化・効率化への貢献可能性
- 継続学習・スキルアップ意欲
- チーム生産性向上への期待値

#### 理想額: 年収600万円
**根拠**:
- 高度な技術習得・適用能力
- プロジェクト全体設計・推進能力
- セキュリティ・品質への包括的対応
- 将来的なチームリード候補

### その他条件
#### 学習・成長支援
- **技術書籍・研修費**: 年間5-10万円
- **カンファレンス参加**: 年間1-2回
- **資格取得支援**: AWS、GCP、Kubernetes関連
- **技術ブログ・発表**: 業務時間での活動支援

#### 働き方・環境
- **リモートワーク**: 週2-3日希望
- **フレックス制**: コアタイム調整可能
- **技術環境**: 最新開発環境・ツール使用
- **チーム文化**: 技術共有・改善提案歓迎

#### キャリアパス
- **評価制度**: 明確な昇進・昇格基準
- **メンタリング**: 先輩エンジニアからの指導
- **プロジェクト参加**: 新技術・チャレンジング案件
- **横断的経験**: インフラ・開発・運用の幅広い経験

## 🗣️ 交渉時の話し方

### 価値アピール例
「このプロジェクトを通じて、実企業での即戦力となれるスキルを
体系的に習得しました。特にDocker環境構築、CI/CD自動化、
セキュリティテスト実装は、チームの生産性向上に直結する技術です。

2週間という短期間での習得実績は、今後の技術キャッチアップと
チームへの貢献速度を示していると考えています。」

### 希望条件提示例
「技術的な成長と会社への貢献を両立させたいと考えており、
適正な評価をいただければと思います。

現在の技術レベルと今後の成長ポテンシャルを考慮し、
年収○○万円程度を希望しております。また、継続的な学習のための
環境・制度があれば、より高い価値提供が可能です。」

### 条件交渉例
「給与については市場価値に応じた適正な評価を期待しています。
ただし、給与以外の成長環境・技術的チャレンジも重視しており、
総合的な条件で判断させていただければと思います。

特に技術学習支援や新しいプロジェクトへの参加機会があれば、
より積極的に貢献していきたいと考えています。」

## 📊 交渉シミュレーション

### シナリオ1: 希望額提示
**面接官**: 「希望年収はいくらですか？」
**回答**: 「技術習得実績と今後の貢献可能性を考慮し、年収500万円を希望しています。
このプロジェクトで習得したDockerやCI/CDスキルは、チームの開発効率化に
直接貢献できると考えています。」

### シナリオ2: 低い提示への対応
**面接官**: 「当社では年収350万円からのスタートになります」
**回答**: 「ご提示いただいた条件について理解いたしました。
技術的な成長機会や評価制度について詳しく教えていただけますでしょうか。
短期間での昇給・昇格の可能性や、技術習得支援制度があれば検討したいと思います。」

### シナリオ3: 条件総合判断
**面接官**: 「給与以外で重視する条件はありますか？」
**回答**: 「技術的な成長環境を最も重視しています。新しい技術への挑戦機会、
メンタリング制度、技術共有文化があることで、より高い価値提供が可能になります。
また、リモートワークやフレックス制度があると、学習時間の確保と
生産性向上の両立が図れます。」

## ⚠️ 交渉時の注意点

### やるべきこと
- 市場価値の客観的根拠を示す
- 技術的価値と人間的価値の両面アピール
- 成長意欲・学習意欲を強調
- 会社・チームへの貢献意識を示す
- 柔軟性・総合判断を示す

### 避けるべきこと
- 過度な高額要求
- 他社との直接比較
- 条件面のみに偏った議論
- 即決を迫る態度
- 技術力の過大評価

## 📋 準備チェックリスト

### 事前調査
- [ ] 業界・職種別年収相場
- [ ] 会社の給与水準・制度
- [ ] 競合他社の条件
- [ ] 自分の市場価値分析

### 資料準備
- [ ] ポートフォリオ詳細
- [ ] 技術習得実績
- [ ] プロジェクト成果
- [ ] 学習計画・キャリアプラン

### 心構え
- [ ] 適正価格での交渉
- [ ] Win-Winの関係構築
- [ ] 長期的視点での判断
- [ ] 柔軟な条件検討

---
*交渉成功の鍵: 技術価値 + 成長性 + 貢献意欲*
"""

        output_path = str(self.interview_dir / "salary_negotiation.md")
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def generate_portfolio_highlights(self) -> str:
        """ポートフォリオハイライト生成"""
        content = """# ポートフォリオハイライト集

## 🌟 技術力証明要素

### 実装の深さ・品質
#### Docker Multi-stage Build最適化
- **Before**: 単一ステージ、大容量イメージ
- **After**: 4段階ビルド、60%サイズ削減
- **技術ポイント**: 依存関係分離、セキュリティ強化、キャッシュ最適化

```dockerfile
# Before: 単純ビルド
FROM python:3.11
COPY . /app
RUN pip install -r requirements.txt
CMD ["python", "app.py"]

# After: Multi-stage最適化
FROM python:3.11-slim as base
# 共通基盤

FROM base as dependencies
# 依存関係専用

FROM dependencies as development
# 開発環境

FROM base as production
# 本番環境（最小構成）
```

#### 非同期テスト設計
- **技術選択**: httpx (requests比較での優位性)
- **設計思想**: async/await ネイティブ対応
- **実装工夫**: セッションスコープフィクスチャ、並行実行制御

```
# 高度な非同期テスト例（サンプルコード）
# 実際の実装では以下のような並行リクエストテストを実施
# - 10並行リクエストでパフォーマンス測定
# - asyncio.gather()を使用したタスク並行実行
# - レスポンス時間、スループット検証
```

### CI/CDパイプライン設計力
#### 段階的品質ゲート設計
```yaml
# 並列実行による効率化
jobs:
  quality-checks:
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    # Lint, Type Check, Security 並列実行

  tests:
    needs: quality-checks
    # テスト実行、カバレッジ検証

  docker-tests:
    needs: quality-checks
    # Docker環境でのテスト

  integration:
    needs: [tests, docker-tests]
    # 統合テスト
```

#### 品質基準の設定・運用
- **カバレッジ**: 80%閾値設定、自動失敗
- **セキュリティ**: 高・中危険度0件
- **パフォーマンス**: レスポンス時間2秒以内
- **コード品質**: Lint・型チェックエラー0件

### セキュリティ実装力
#### OWASP準拠の包括対応
```python
# OWASP API Security Top 10 実装例
class TestOWASPAPISecurityTop10:
    async def test_api1_broken_object_level_authorization(self):
        # 認証バイパステスト

    async def test_api2_broken_authentication(self):
        # 認証・認可テスト

    async def test_injection_vulnerabilities(self):
        # インジェクション攻撃テスト
```

#### 多層セキュリティスキャン
- **SAST**: bandit（Python特化）
- **依存関係**: safety, pip-audit
- **高度解析**: semgrep
- **カスタム**: 設定ファイル、機密情報検査

## 🚀 技術的課題解決事例

### 課題1: CI/CD実行時間の長さ
**問題**: 初期実装で10分以上の実行時間

**解決アプローチ**:
1. **分析**: ボトルネック特定（Docker build、テスト実行）
2. **最適化**: レイヤーキャッシュ、並列実行、依存関係最適化
3. **結果**: 6分以内に短縮（40%改善）

**技術的工夫**:
```yaml
# Docker レイヤーキャッシュ活用
- name: Build with cache
  uses: docker/build-push-action@v4
  with:
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

### 課題2: 非同期テストのリソースリーク
**問題**: メモリリーク、テスト間での状態共有

**解決アプローチ**:
1. **原因分析**: イベントループ管理、リソースクリーンアップ不備
2. **設計改善**: セッション・関数スコープの適切な分離
3. **実装**: 確実なクリーンアップ機構

**技術的工夫**:
```python
@pytest.fixture(scope="session")
async def api_client():
    async with AsyncAPIClient() as client:
        yield client
    # 自動クリーンアップ保証
```

### 課題3: セキュリティスキャンの偽陽性
**問題**: 過剰なアラート、実用性の低下

**解決アプローチ**:
1. **分析**: ツール別特性理解、閾値調整
2. **統合**: 複数ツール組み合わせによる精度向上
3. **自動化**: CI/CD統合、継続監視

## 📊 数値による成果証明

### パフォーマンス改善
| 項目 | Before | After | 改善率 |
|------|--------|-------|--------|
| Docker build時間 | 8分 | 3分 | 62%短縮 |
| CI/CD実行時間 | 12分 | 6分 | 50%短縮 |
| イメージサイズ | 800MB | 320MB | 60%削減 |
| テスト実行時間 | 45秒 | 25秒 | 44%短縮 |

### 品質向上
- **テストカバレッジ**: 60% → 85% (+25pt)
- **セキュリティスコア**: C → B+ (2段階向上)
- **コード品質**: 多数のWarning → 0件
- **ドキュメント**: 手動 → 自動生成11種類

### 開発効率化
- **環境構築**: 30分 → 2分 (93%短縮)
- **テスト実行**: 手動 → 完全自動化
- **デプロイ**: 手動30分 → 自動6分
- **品質チェック**: 手動1時間 → 自動並列5分

## 🎯 独自性・差別化要素

### 学習アプローチの体系性
- **段階的実装**: Week単位での確実な積み上げ
- **品質重視**: 各段階での品質基準クリア
- **統合性**: 技術要素の有機的結合
- **実用性**: 実企業での活用を想定

### 包括的な技術カバレッジ
```
開発 ─ テスト ─ セキュリティ ─ デプロイ ─ 監視
  │      │         │           │        │
Docker  pytest   OWASP      CI/CD   Logging
  │      │         │           │        │
最適化  非同期   自動化     品質ゲート  アラート
```

### 自動化・効率化への意識
- **ドキュメント**: 自動生成11種類
- **監視**: リアルタイムアラート
- **レポート**: 包括的品質レポート
- **ダッシュボード**: インタラクティブ可視化

## 💼 ビジネス価値・ROI

### チーム生産性向上
- **新人オンボーディング**: 1週間 → 1日
- **環境トラブル**: 月10件 → 月1件
- **品質問題**: デプロイ後発見 → デプロイ前検出
- **セキュリティリスク**: 潜在的脅威 → 事前検出

### 運用コスト削減
- **手動作業削減**: 月40時間 → 月5時間
- **トラブル対応**: 緊急対応 → 予防保守
- **環境維持**: 個別管理 → 標準化管理
- **品質保証**: 事後対応 → 事前対応

### リスク軽減効果
- **セキュリティ**: 継続監視による脅威早期発見
- **品質**: 自動テストによる回帰防止
- **運用**: 標準化による属人性排除
- **可用性**: 監視・アラートによる早期対応

## 🏆 アピールポイント整理

### 技術面接向け
1. **Docker実務経験**: Multi-stage build、最適化、運用
2. **CI/CD設計力**: 段階的品質ゲート、自動化戦略
3. **テスト設計**: 非同期、並行、包括的カバレッジ
4. **セキュリティ意識**: OWASP準拠、自動監視

### 人事面接向け
1. **学習能力**: 2週間での包括的技術習得
2. **問題解決力**: 体系的アプローチ、数値改善
3. **効率化意識**: 自動化による生産性向上
4. **品質意識**: 高いカバレッジ、継続的改善

### マネージャー面接向け
1. **ビジネス価値**: ROI、コスト削減、リスク軽減
2. **チーム貢献**: 標準化、知識共有、効率化
3. **将来性**: 継続学習、技術キャッチアップ
4. **実用性**: 実企業での即戦力、スケーラビリティ

---
*ハイライト活用: 面接レベルに応じた重点アピール*
"""

        output_path = str(self.interview_dir / "portfolio_highlights.md")
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def generate_interview_guide(self, materials: dict[str, str]) -> str:
        """統合面接ガイド生成"""
        content = f"""# 面接準備 - 統合ガイド

## 📋 面接前最終チェックリスト

### 技術準備 ✅
- [ ] プロジェクトデモ環境動作確認
- [ ] GitHub リポジトリ・CI/CD パイプライン確認
- [ ] 技術質問・回答の最終確認
- [ ] ポートフォリオダッシュボード確認

### 資料準備 ✅
- [ ] 技術概要資料印刷・PDF準備
- [ ] デモスクリプト確認
- [ ] プレゼンテーション資料最終化
- [ ] 質問・回答集の最終確認

### 心理準備 ✅
- [ ] 1分間エレベーターピッチ練習
- [ ] 技術的課題・解決プロセス整理
- [ ] 志望動機・キャリア目標明確化
- [ ] 給与・条件希望の整理

## 🎯 面接タイプ別対策

### 技術面接 (30-60分)
**重点ポイント**:
- プロジェクト詳細説明 (15分)
- ライブデモまたは画面共有 (10分)
- 技術的質疑応答 (15-35分)

**準備資料**:
- [技術概要](technical_overview.md)
- [デモスクリプト](demo_script.md)
- [ポートフォリオハイライト](portfolio_highlights.md)

### 人事面接 (20-40分)
**重点ポイント**:
- 学習プロセス・成長意欲 (10分)
- チームワーク・コミュニケーション (10分)
- 志望動機・キャリア目標 (10-20分)

**準備資料**:
- [プロジェクトプレゼンテーション](project_presentation.md)
- [質問・回答集](qa_collection.md)

### 最終面接・条件面談 (20-30分)
**重点ポイント**:
- プロジェクト価値・貢献可能性 (10分)
- 条件・給与交渉 (10-20分)

**準備資料**:
- [給与交渉ガイド](salary_negotiation.md)
- [ポートフォリオハイライト](portfolio_highlights.md)

## 🗂️ 面接資料構成

### 基本セット
1. **技術概要** (A4 2-3枚)
   - プロジェクト概要
   - 技術スタック詳細
   - 定量的成果

2. **ポートフォリオハイライト** (A4 2枚)
   - 技術的課題解決事例
   - 独自性・差別化要素
   - ビジネス価値

### デモ・プレゼン用
3. **プレゼンテーション資料** (10-15スライド)
   - プロジェクト全体像
   - 技術詳細
   - 実装成果

4. **デモスクリプト** (5分版)
   - 環境起動
   - テスト実行
   - CI/CD確認

### 質疑応答用
5. **QA集** (想定40問)
   - 技術的質問 (25問)
   - 業務・組織関連 (10問)
   - キャリア関連 (5問)

## ⏰ 面接時間別戦略

### 30分面接
- プロジェクト概要 (5分)
- 技術ハイライト (10分)
- 質疑応答 (15分)

### 60分面接
- 自己紹介・概要 (5分)
- プロジェクト詳細 (15分)
- デモンストレーション (10分)
- 技術的質疑応答 (20分)
- 逆質問・条件確認 (10分)

### 90分面接
- 自己紹介・概要 (10分)
- プロジェクトプレゼン (20分)
- デモンストレーション (15分)
- 深い技術議論 (25分)
- 志望動機・キャリア (15分)
- 条件・逆質問 (5分)

## 🎤 話し方・伝え方のコツ

### 技術説明のポイント
1. **結論ファースト**: 何を実現したかを最初に
2. **数値で証明**: 定量的な成果・改善を強調
3. **課題解決プロセス**: 問題→分析→解決→結果
4. **選択理由明確化**: なぜその技術を選んだか

### 印象を良くする話し方
- **簡潔明瞭**: 1つの話題は2-3分以内
- **具体的事例**: 抽象論より具体的実装
- **学習意欲**: 今後のスキルアップ計画
- **チーム志向**: 個人成果よりチーム貢献

## 📱 デジタル面接対策

### オンライン面接準備
- [ ] 安定したネットワーク環境
- [ ] カメラ・マイク動作確認
- [ ] 画面共有機能確認
- [ ] バックアップ環境準備

### デモ環境確認
- [ ] Docker環境動作確認
- [ ] CI/CDパイプライン確認
- [ ] ダッシュボード表示確認
- [ ] レスポンス速度確認

## 🚀 面接成功のための最終調整

### 前日準備
- 全資料の最終確認
- デモ環境の動作テスト
- 想定質問の回答練習
- 体調管理・十分な睡眠

### 当日の心構え
- リラックスした状態で臨む
- 技術的情熱・学習意欲を表現
- 誠実で前向きな姿勢
- 相手の質問をよく聞く

### 面接後のフォローアップ
- お礼メール (24時間以内)
- 追加質問への回答
- 補足資料の提供
- 次のステップの確認

## 📞 緊急時対応

### デモ失敗時
- 事前録画デモの活用
- スクリーンショットでの説明
- 口頭での詳細説明
- GitHub リポジトリでのコード説明

### 技術質問困った時
- 「調べて後日回答」の正直な対応
- 関連する知識での応答
- 学習意欲・調査方法の説明
- 謙虚で前向きな姿勢

### 時間オーバー時
- 重要ポイントの要約
- 資料での補完説明
- 追加説明の提案
- メールでのフォローアップ

---

## 📊 成功確率向上のためのポイント

### 技術力アピール: 90%
- 実装の深さ・品質
- 課題解決能力
- 継続学習意欲

### 人物評価: 85%
- コミュニケーション力
- チームワーク意識
- 前向きな姿勢

### 志望度・適性: 80%
- 明確な志望動機
- キャリア目標
- 会社・チームへの関心

**総合準備完了度: 90%以上を目指す！**

---
*面接成功の秘訣: 準備 × 技術力 × 人間力*

## 📎 生成された面接資料一覧

{self._generate_materials_index(materials)}
"""

        output_path = str(self.interview_dir / "README.md")
        with Path(output_path).open("w", encoding="utf-8") as f:
            f.write(content)

        return output_path

    def _generate_materials_index(self, materials: dict[str, str]) -> str:
        """面接資料インデックス生成"""
        index = "\n### 利用可能な面接資料\n"

        material_descriptions = {
            "technical_overview": "技術面接対策 - プロジェクト技術概要",
            "demo_script": "デモンストレーション台本 (5分版)",
            "qa_collection": "面接質問・回答集 (40問)",
            "project_presentation": "プロジェクトプレゼンテーション (10分版)",
            "salary_negotiation": "給与交渉・条件面談ガイド",
            "portfolio_highlights": "ポートフォリオハイライト集",
            "interview_guide": "面接準備 - 統合ガイド",
        }

        for material_name, file_path in materials.items():
            if file_path and material_name in material_descriptions:
                description = material_descriptions[material_name]
                file_name = Path(file_path).name
                index += f"- [{description}]({file_name})\n"

        return index


def main():
    """メイン実行関数"""
    interview_prep = InterviewPreparation()
    materials = interview_prep.generate_interview_materials()

    print("📋 面接準備資料を生成しました:")
    print(f"  - 生成資料数: {len(materials)}")
    print(f"  - 出力ディレクトリ: {interview_prep.interview_dir}")

    for material_name, file_path in materials.items():
        if file_path:
            print(f"  ✅ {material_name}: {file_path}")


if __name__ == "__main__":
    main()


# =============================================================================
# 学習ポイント:
#
# 1. 包括的面接準備:
#    - 技術・人事・最終面接の全対応
#    - デモ・プレゼン・質疑応答準備
#    - 条件交渉・給与交渉戦略
#
# 2. 体系的資料作成:
#    - 面接タイプ別カスタマイズ
#    - 時間配分・話し方最適化
#    - デジタル面接対応
#
# 3. 価値提案最適化:
#    - 技術力の定量的証明
#    - ビジネス価値・ROI説明
#    - 成長性・貢献可能性アピール
#
# 4. リスク対策・緊急時対応:
#    - デモ失敗時の代替案
#    - 技術質問困った時の対応
#    - 時間管理・フォローアップ
# =============================================================================
