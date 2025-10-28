#!/usr/bin/env python3
"""
統合分析レポートの改善提案を段階的にドキュメントに適用するスクリプト

使用方法:
    python scripts/apply_review_improvements.py
"""

import re
from pathlib import Path


class DocumentImprover:
    """ドキュメント改善適用クラス"""

    def __init__(self, doc_path: str):
        self.doc_path = Path(doc_path)
        self.content = self.doc_path.read_text(encoding="utf-8")
        self.original_content = self.content  # バックアップ用

    def backup(self) -> Path:
        """バックアップファイル作成"""
        backup_path = self.doc_path.with_suffix(".md.backup")
        backup_path.write_text(self.original_content, encoding="utf-8")
        print(f"✅ バックアップ作成: {backup_path}")
        return backup_path

    def save(self):
        """変更を保存"""
        self.doc_path.write_text(self.content, encoding="utf-8")
        print(f"✅ 変更を保存: {self.doc_path}")

    # ========================================
    # Q5: 手動マッチングUXフロー仕様追加
    # ========================================

    def apply_q5_manual_matching_ux(self):
        """Q5: 手動マッチングUXフロー仕様を追加"""
        print("\n🔴 Q5: 手動マッチングUXフロー仕様追加中...")

        # Phase 4セクションを探して、手動マッチング仕様を追加
        pattern = r"(### Phase 4: Trigger 4統合[^\n]*\n\n)(#### アクション4\.1:)"

        ux_spec = '''
#### 手動マッチングUXフロー仕様

**タイムアウト・リトライ設定**:

```python
class ManualMatchingConfig:
    """手動マッチング設定"""
    timeout_seconds: int = 30      # ユーザー入力待機時間
    max_retries: int = 3           # 無効入力時の再試行上限
    skip_on_timeout: bool = True   # タイムアウト時スキップ
```

**ユーザーフィードバックフロー**:

1. **初回プロンプト表示**:
   ```
   🤔 AIマッチング失敗。手動でタスクIDを選択してください。

   利用可能なタスク:
   1.1 - BaseAPIClient実装
   1.2 - AsyncAPIClient実装
   2.1 - pytest基本設定

   該当タスクIDを入力してください（例: 1.1）[30秒以内]:
   ```

2. **入力検証**:
   ```python
   def validate_task_id(user_input: str, valid_tasks: List[str]) -> bool:
       """タスクID検証"""
       if user_input.strip() not in valid_tasks:
           return False
       return True
   ```

3. **エラーメッセージ**:
   - 無効なID入力時:
     ```
     ❌ 無効なID「{user_input}」が入力されました。
     再度入力してください（残り{retries}回）:
     ```

   - タイムアウト時:
     ```
     ⏱️  タイムアウト（30秒経過）。このコミットをスキップします。
     次回tasks.json同期時に再度確認します。
     ```

4. **リトライ上限到達時**:
   ```
   ⚠️  3回の試行でマッチングできませんでした。
   このコミットは未割り当てとして記録します。

   コミット情報:
   - ハッシュ: {commit_hash[:7]}
   - メッセージ: {commit_msg}

   後でlearning_state.yamlから手動で割り当てできます。
   ```

**状態遷移図**:

```
[Git Commit発生]
       ↓
[AI自動マッチング試行]
       ↓
    成功? ─── YES ──→ [learning_state.yaml更新]
       ↓
      NO
       ↓
[手動マッチングプロンプト表示]
       ↓
[ユーザー入力待機（30秒）]
       ↓
  タイムアウト? ─── YES ──→ [スキップ記録] → [次回sync時再試行]
       ↓
      NO
       ↓
[入力検証]
       ↓
    有効? ─── YES ──→ [learning_state.yaml更新]
       ↓
      NO
       ↓
[リトライカウント確認]
       ↓
   < 3回? ─── YES ──→ [エラーメッセージ表示] → [再入力]
       ↓
      NO
       ↓
[未割り当て記録] → [手動割り当て手順表示]
```

'''

        replacement = r"\1" + ux_spec + r"\n\2"
        self.content = re.sub(pattern, replacement, self.content, flags=re.DOTALL)
        print("  ✅ 手動マッチングUXフロー仕様を追加しました")

    # ========================================
    # Q8: API鍵セキュア化
    # ========================================

    def apply_q8_api_key_security(self):
        """Q8: .mcp.json API鍵セキュア化仕様を追加"""
        print("\n🔴 Q8: API鍵セキュア化仕様追加中...")

        # Phase 2初期化セクションの後に追加（task-master listの直後）
        pattern = r"(task-master list\n```\n\n)"

        security_spec = r"""

**🔒 セキュリティベストプラクティス**:

1. **.gitignore設定**（必須）:
   ```bash
   # .gitignore
   .mcp.json
   .env
   ```

2. **.mcp.json.example作成**（Git管理対象）:
   ```json
   {
     "mcpServers": {
       "task-master-ai": {
         "command": "npx",
         "args": ["-y", "task-master-ai"],
         "env": {
           "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}",
           "PERPLEXITY_API_KEY": "${PERPLEXITY_API_KEY}"
         }
       }
     }
   }
   ```

3. **セットアップ手順**:
   ```bash
   # 初回セットアップ
   cp .mcp.json.example .mcp.json

   # .envファイルからAPIキーをコピーして.mcp.jsonに手動設定
   # または環境変数から自動読み込み
   ```

4. **README.mdに追記**:
   ```markdown
   ## セキュリティ設定

   ### API鍵管理

   **重要**: `.mcp.json`ファイルは絶対にGitにコミットしないでください。

   1. `.mcp.json.example`をコピー:
      ```bash
      cp .mcp.json.example .mcp.json
      ```

   2. `.env`ファイルからAPIキーを取得:
      ```bash
      cat .env | grep ANTHROPIC_API_KEY
      ```

   3. `.mcp.json`のプレースホルダーを実際のAPIキーで置換

   4. 設定確認:
      ```bash
      # .mcp.jsonが.gitignoreに含まれていることを確認
      git check-ignore .mcp.json
      # → .mcp.json (と表示されればOK)
      ```
   ```

**⚠️ 誤コミット防止チェック**:

```bash
# pre-commitフック追加（scripts/pre-commit-api-key-check.sh）
#!/bin/bash
# API鍵を含むファイルのコミット防止

if git diff --cached --name-only | grep -q ".mcp.json"; then
    echo "❌ エラー: .mcp.jsonはコミットできません（API鍵漏洩防止）"
    echo "→ .gitignoreに追加されているか確認してください"
    exit 1
fi

if git diff --cached | grep -qE "ANTHROPIC_API_KEY.*sk-ant-"; then
    echo "❌ エラー: ANTHROPIC_API_KEYが平文で含まれています"
    echo "→ 環境変数参照（\${ANTHROPIC_API_KEY}）に変更してください"
    exit 1
fi

exit 0
```
"""

        replacement = r"\1" + security_spec
        self.content = re.sub(pattern, replacement, self.content, flags=re.DOTALL)
        print("  ✅ API鍵セキュア化仕様を追加しました")

    # ========================================
    # Q11: YAMLサイズ閾値再計算
    # ========================================

    def apply_q11_yaml_threshold(self):
        """Q11: YAMLサイズ閾値を4KB→12KBに更新"""
        print("\n🔴 Q11: YAMLサイズ閾値再計算中...")

        # 現在の4KB閾値を12KBに更新
        pattern = r"max_yaml_size_kb:\s*float\s*=\s*4\.0\s*#.*"
        replacement = (
            r"max_yaml_size_kb: float = 12.0  # Week 10タスク規模対応（理論最大10KB + 20%バッファ）"
        )

        self.content = re.sub(pattern, replacement, self.content)

        # 閾値計算根拠を追加
        threshold_calc = '''

#### YAMLサイズ閾値計算根拠

**理論最大値計算**:

```python
# Week 10時点のタスク規模推定
max_tasks_week10 = 200  # Phase 1-6の全タスク累積
                        # - Week 1-2: 30タスク
                        # - Week 3-4: 40タスク
                        # - Week 5-6: 50タスク
                        # - Week 7-8: 40タスク
                        # - Week 9-10: 40タスク

# タスク1件あたりの平均サイズ
avg_task_size = 50  # bytes
# 内訳:
#   - task_id: 5 bytes（例: "1.2"）
#   - status: 10 bytes（例: "done"）
#   - timestamps: 30 bytes（2つのISO 8601形式）
#   - metadata: 5 bytes（その他）

# 理論最大値
theoretical_max = max_tasks_week10 * avg_task_size  # 10,000 bytes = 10KB

# 推奨閾値: 理論最大値 + 20%バッファ
recommended_threshold = theoretical_max * 1.2  # 12KB
```

**実装**:

```python
class PerformanceThresholds:
    """パフォーマンス閾値定義"""

    max_yaml_size_kb: float = 12.0  # 4.0 → 12.0に変更
    # 根拠: Week 10の200タスク × 50bytes = 10KB + 20%バッファ

    max_processing_time_seconds: float = 5.0
    max_memory_usage_mb: float = 50.0
```

**閾値超過時の動作**:

```python
def check_yaml_size(yaml_path: Path, threshold_kb: float = 12.0):
    """YAMLサイズチェック"""
    size_kb = yaml_path.stat().st_size / 1024

    if size_kb > threshold_kb:
        logger.warning(
            f"⚠️ learning_state.yaml肥大化検知",
            current_size=f"{size_kb:.1f}KB",
            threshold=f"{threshold_kb}KB",
            recommendation="古いタスクのアーカイブを検討してください"
        )

        # 自動アーカイブ提案
        suggest_archive_old_tasks(yaml_path)
```
'''

        # Performance Thresholdsセクションの後に追加
        pattern = r"(class PerformanceThresholds:.*?max_memory_usage_mb.*?\n)"
        replacement = r"\1" + threshold_calc
        self.content = re.sub(pattern, replacement, self.content, flags=re.DOTALL)

        print("  ✅ YAMLサイズ閾値を4KB→12KBに更新しました")

    # ========================================
    # Q6: Trigger 4パフォーマンス予算内訳
    # ========================================

    def apply_q6_performance_budget(self):
        """Q6: Trigger 4パフォーマンス予算内訳を追加"""
        print("\n🟡 Q6: パフォーマンス予算内訳追加中...")

        perf_budget = '''

#### サブプロセス別パフォーマンス予算

**全体目標: 5秒以内**

| サブプロセス | 予算 | 測定方法 | 超過時の対応 |
|------------|------|---------|------------|
| Git diff解析 | 2.0秒 | `time.perf_counter()` | Git履歴削減 |
| AI自動マッチング | 2.0秒 | `time.perf_counter()` | タイムアウト・フォールバック |
| YAML書込 | 1.0秒 | `time.perf_counter()` | YAML構造最適化 |
| **合計** | **5.0秒** | - | ユーザー警告 |

**実装**:

```python
# scripts/performance_monitor.py
import time
import structlog
from typing import Callable, TypeVar

logger = structlog.get_logger()

T = TypeVar('T')

class SubprocessThresholds:
    """サブプロセス別パフォーマンス閾値"""
    git_analysis_max: float = 2.0    # Git diff解析
    ai_matching_max: float = 2.0     # Claude API呼出
    yaml_sync_max: float = 1.0       # YAML書込

def measure_subprocess(
    name: str,
    threshold: float,
    func: Callable[[], T]
) -> T:
    """サブプロセス実行時間測定"""
    start = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - start

    # 閾値超過チェック
    if elapsed > threshold:
        logger.warning(
            f"⚠️ Subprocess '{name}' exceeded budget",
            elapsed=f"{elapsed:.2f}s",
            threshold=f"{threshold}s",
            overage=f"{elapsed - threshold:.2f}s"
        )
    else:
        logger.info(
            f"✅ Subprocess '{name}' completed",
            elapsed=f"{elapsed:.2f}s",
            budget_remaining=f"{threshold - elapsed:.2f}s"
        )

    return result

# 使用例
def trigger4_implementation():
    """Trigger 4実装（パフォーマンス測定付き）"""

    # 1. Git解析（予算: 2.0秒）
    diff_result = measure_subprocess(
        name="Git Diff Analysis",
        threshold=SubprocessThresholds.git_analysis_max,
        func=lambda: analyze_git_diff()
    )

    # 2. AIマッチング（予算: 2.0秒）
    matched_task = measure_subprocess(
        name="AI Task Matching",
        threshold=SubprocessThresholds.ai_matching_max,
        func=lambda: ai_match_commit(diff_result)
    )

    # 3. YAML更新（予算: 1.0秒）
    measure_subprocess(
        name="YAML Sync",
        threshold=SubprocessThresholds.yaml_sync_max,
        func=lambda: sync_learning_state(matched_task)
    )
```

**ボトルネック特定例**:

```
# ログ出力例
2025-10-28 14:30:15 [info     ] ✅ Subprocess 'Git Diff Analysis' completed
    elapsed=1.2s budget_remaining=0.8s

2025-10-28 14:30:17 [warning  ] ⚠️ Subprocess 'AI Task Matching' exceeded budget
    elapsed=3.5s threshold=2.0s overage=1.5s

2025-10-28 14:30:18 [info     ] ✅ Subprocess 'YAML Sync' completed
    elapsed=0.5s budget_remaining=0.5s

Total: 5.2s (⚠️ 0.2s over budget)
→ AI Matchingがボトルネック（3.5秒 vs 2.0秒予算）
```
'''

        # パフォーマンス閾値セクションの直後に追加
        pattern = (
            r"(\*\*パフォーマンス閾値\*\*:\n"
            r"- \*\*実行時間\*\*: <5秒（Trigger 4全体: Git解析 \+ AI推論 \+ YAML更新）\n)"
        )
        replacement = r"\1" + perf_budget
        self.content = re.sub(pattern, replacement, self.content, flags=re.DOTALL)

        print("  ✅ パフォーマンス予算内訳を追加しました")

    # ========================================
    # 実行メソッド
    # ========================================

    def apply_all_improvements(self):
        """全改善提案を適用"""
        print("=" * 60)
        print("📝 統合分析レポート改善提案適用開始")
        print("=" * 60)

        # バックアップ作成
        self.backup()

        # 🔴 高優先度（4-6時間）
        self.apply_q5_manual_matching_ux()
        self.apply_q8_api_key_security()
        self.apply_q11_yaml_threshold()

        # 🟡 中優先度（6-8時間）
        self.apply_q6_performance_budget()

        # 変更を保存
        self.save()

        print("\n" + "=" * 60)
        print("✅ 改善適用完了")
        print("=" * 60)
        print(f"\n📄 更新ファイル: {self.doc_path}")
        print(f"💾 バックアップ: {self.doc_path.with_suffix('.md.backup')}")
        print("\n次のステップ:")
        print("1. git diff でレビュー")
        print("2. 問題なければ git commit")
        print("3. 残りの中・低優先度項目は別タスクで実装")


def main():
    """メイン実行"""
    doc_path = "docs/task master 自動化フロー組み込み計画.md"

    improver = DocumentImprover(doc_path)
    improver.apply_all_improvements()


if __name__ == "__main__":
    main()
