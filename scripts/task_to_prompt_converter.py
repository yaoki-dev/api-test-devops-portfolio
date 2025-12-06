#!/usr/bin/env python3
"""
ポートフォリオ戦略の日次タスクを実装プロンプトテンプレートに自動変換するスクリプト

使用方法:
    python scripts/task_to_prompt_converter.py --week 1 --day 1
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Any


class TaskToPromptConverter:
    """タスク情報を実装プロンプトに変換するコンバーター"""

    def __init__(self):
        self.portfolio_path = Path("docs/プロジェクト再編/ポートフォリオ戦略.md")
        self.template_path = Path("docs/templates/ai_implementation_prompt_template_compact.md")
        self.output_dir = Path("docs/work/prompts")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_task_info(self, week: int, day: int) -> dict[str, Any]:
        """ポートフォリオ戦略から指定された週・日のタスク情報を抽出"""

        with self.portfolio_path.open(encoding="utf-8") as f:
            content = f.read()

        # タスク情報の抽出パターン
        task_pattern = rf"D{day}.*?Task {week}\.{day}:\s*(.*?)$"
        requirements_pattern = (
            rf"#### Task {week}\.{day}:.*?\*\*要件\*\*:(.*?)(?=\*\*テスト要件\*\*)"
        )
        test_pattern = (
            rf"#### Task {week}\.{day}:.*?\*\*テスト要件\*\*.*?"
            rf"\((.*?)件\)(.*?)(?=\*\*セキュリティ要件\*\*)"
        )
        security_pattern = (
            rf"#### Task {week}\.{day}:.*?\*\*セキュリティ要件\*\*:"
            rf"(.*?)(?=\*\*AI依頼プロンプト\*\*)"
        )
        skeleton_pattern = rf"#### Task {week}\.{day}:.*?\*\*実装スケルトン\*\*.*?```python(.*?)```"

        # 情報抽出
        task_info = {
            "week": week,
            "day": day,
            "task_name": "",
            "requirements": "",
            "test_count": 0,
            "test_cases": [],
            "security_requirements": "",
            "skeleton": "",
            "file_paths": [],
        }

        # タスク名の抽出
        task_match = re.search(task_pattern, content, re.MULTILINE)
        if task_match:
            task_info["task_name"] = task_match.group(1).strip()

        # 要件の抽出
        req_match = re.search(requirements_pattern, content, re.DOTALL)
        if req_match:
            task_info["requirements"] = req_match.group(1).strip()
            # ファイルパスの抽出
            file_paths = re.findall(r"\[(.*?\.py)\]", task_info["requirements"])
            task_info["file_paths"] = list(set(file_paths))

        # テスト要件の抽出
        test_match = re.search(test_pattern, content, re.DOTALL)
        if test_match:
            task_info["test_count"] = int(test_match.group(1))
            test_details = test_match.group(2).strip()
            # テストケースのリスト化
            test_cases = re.findall(
                r"\d+\.\s*`(test_.*?)`:\s*(.*?)(?=\n\d+\.|$)", test_details, re.DOTALL
            )
            task_info["test_cases"] = [
                {"name": tc[0], "description": tc[1].strip()} for tc in test_cases
            ]

        # セキュリティ要件の抽出
        sec_match = re.search(security_pattern, content, re.DOTALL)
        if sec_match:
            task_info["security_requirements"] = sec_match.group(1).strip()

        # 実装スケルトンの抽出
        skeleton_match = re.search(skeleton_pattern, content, re.DOTALL)
        if skeleton_match:
            task_info["skeleton"] = skeleton_match.group(1).strip()

        return task_info

    def create_compact_prompt(self, task_info: dict[str, Any]) -> str:
        """タスク情報からCompact版プロンプトを生成"""

        # メソッドシグネチャの推測（スケルトンから抽出）
        method_signatures = self._extract_method_signatures(task_info["skeleton"])

        # ファイルパスの決定
        target_file = (
            task_info["file_paths"][0] if task_info["file_paths"] else "utils/api_client.py"
        )

        # 処理ロジックの構築
        processing_logic = self._build_processing_logic(task_info["requirements"])

        # テストケースの構築
        test_cases_str = self._format_test_cases(task_info["test_cases"])

        prompt = f"""## AI実装依頼: {task_info["task_name"]}

### 1. 実装スコープ
**ファイルパス**: `{target_file}`
**対象コンポーネント**: {self._extract_component_name(task_info["task_name"])}
**操作種別**: 機能追加
**複雑度**: {"Simple" if task_info["day"] <= 3 else "Medium"}

**メソッドシグネチャ**:
{method_signatures}

### 2. 技術仕様
**技術スタック**: Python 3.12, httpx, pytest
**品質基準**: @memory:implementation_quality_gates
**カバレッジ目標**: Week {task_info["week"]}: 39.5%

### 3. 機能要件
**入力**: {self._extract_input(task_info["requirements"])}
**処理ロジック**:
{processing_logic}

**出力**: {self._extract_output(task_info["requirements"])}
**エラーハンドリング**: @memory:project_architecture

{self._add_security_if_needed(task_info["security_requirements"])}

### 4. テスト要件
**テストケース数**: 最低{task_info["test_count"]}件
{test_cases_str}

**テストマーカー**: @pytest.mark.regression, @pytest.mark.asyncio

### 5. 成功基準
**タスク固有の検証**:
{self._generate_validation_checklist(task_info["requirements"])}

**品質ゲート**: @memory:implementation_quality_gates
"""

        return prompt

    def _extract_method_signatures(self, skeleton: str) -> str:
        """スケルトンからメソッドシグネチャを抽出"""
        signatures = []
        # def文を抽出
        def_patterns = re.findall(r"def\s+(\w+)\([^)]*\).*?(?=\n|$)", skeleton)
        for method in def_patterns:
            signatures.append(f"def {method}(...) -> ...:  # 詳細は実装スケルトン参照")
        return "\n".join(signatures) if signatures else "# スケルトンから抽出"

    def _extract_component_name(self, task_name: str) -> str:
        """タスク名からコンポーネント名を抽出"""
        if "BaseAPIClient" in task_name:
            return "BaseAPIClient"
        elif "JSONPlaceholder" in task_name:
            return "JSONPlaceholderClient"
        else:
            return "対象コンポーネント"

    def _build_processing_logic(self, requirements: str) -> str:
        """要件から処理ロジックを構築"""
        logic_items = []
        # 箇条書き項目を抽出
        items = re.findall(r"[-•]\s+(.*?)(?=\n[-•]|\n\n|$)", requirements, re.DOTALL)
        for i, item in enumerate(items[:5], 1):  # 最大5項目
            logic_items.append(f"{i}. {item.strip()}")
        return "\n".join(logic_items)

    def _extract_input(self, requirements: str) -> str:
        """要件から入力パラメータを推測"""
        if "timeout" in requirements.lower():
            return "base_url: str, timeout: float = 30.0"
        return "適切なパラメータ"

    def _extract_output(self, requirements: str) -> str:
        """要件から出力型を推測"""
        if "dict" in requirements:
            return "dict[str, Any]"
        elif "Client" in requirements:
            return "BaseAPIClient instance"
        return "適切な戻り値"

    def _format_test_cases(self, test_cases: list) -> str:
        """テストケースをフォーマット"""
        formatted = []
        for i, tc in enumerate(test_cases, 1):
            formatted.append(f"{i}. {tc['name']}: {tc['description']}")
        return "\n".join(formatted)

    def _add_security_if_needed(self, security_requirements: str) -> str:
        """セキュリティ要件があれば追加"""
        if security_requirements:
            return f"\n**セキュリティ要件**:\n{security_requirements}"
        return ""

    def _generate_validation_checklist(self, requirements: str) -> str:
        """要件から検証チェックリストを生成"""
        checklist = []
        if "Context Manager" in requirements:
            checklist.append("- [ ] Context Manager が正しく動作する")
        if "timeout" in requirements.lower():
            checklist.append("- [ ] timeout検証が機能する")
        if "型ヒント" in requirements:
            checklist.append("- [ ] 型ヒントが完備されている")
        if "テスト" in requirements:
            checklist.append("- [ ] テストが全て合格する")

        return "\n".join(checklist) if checklist else "- [ ] 要件を満たしている"

    def save_prompt(self, prompt: str, week: int, day: int):
        """生成したプロンプトを保存"""
        filename = f"week{week}_day{day}_prompt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        output_path = self.output_dir / filename

        with output_path.open("w", encoding="utf-8") as f:
            f.write(prompt)

        print(f"✅ プロンプトを保存しました: {output_path}")
        return output_path

    def execute(self, week: int, day: int) -> Path:
        """変換を実行"""
        print(f"📚 Week {week} Day {day} のタスク情報を抽出中...")
        task_info = self.extract_task_info(week, day)

        print("🔄 Compact版プロンプトに変換中...")
        prompt = self.create_compact_prompt(task_info)

        print("💾 プロンプトを保存中...")
        output_path = self.save_prompt(prompt, week, day)

        print("\n✨ 変換完了！")
        print(f"📋 タスク名: {task_info['task_name']}")
        print(f"🧪 テスト数: {task_info['test_count']}件")
        print(f"📁 対象ファイル: {', '.join(task_info['file_paths'])}")

        return output_path


def main():
    parser = argparse.ArgumentParser(description="日次タスクを実装プロンプトに変換")
    parser.add_argument("--week", type=int, required=True, help="週番号 (1-10)")
    parser.add_argument("--day", type=int, required=True, help="日番号 (1-6)")
    parser.add_argument("--execute", action="store_true", help="AIに即座に実行させる")

    args = parser.parse_args()

    converter = TaskToPromptConverter()
    output_path = converter.execute(args.week, args.day)

    if args.execute:
        print("\n🚀 AIに実装を依頼します...")
        print("以下のコマンドをClaude Codeに実行してください:")
        print(f"\n@{output_path} の内容に従って実装してください。")
        print("実装後は品質ゲートを実行してください。")


if __name__ == "__main__":
    main()
