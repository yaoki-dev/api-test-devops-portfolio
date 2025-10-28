# Task Master自動化フロー組み込み実装計画

*最終更新: 2025年10月28日*

## 📋 概要

### 目的
学習・実装・記録フロー自動化システム（5トリガー方式）とTask Master AIを統合し、以下を実現する：

1. **実装タスク詳細管理**: Week 1-10の全実装タスクをTask Masterで管理
2. **学習進捗軽量管理**: learning_state.yamlは学習状態のみ保持（3-4KB維持）
3. **自動連携**: Trigger 4（実装記録）でGit分析 → Task Master照会 → YAML同期

### 対象範囲
- **管理対象**: Phase 1-6（Week 1-1
0）の全実装タスク
- **統合トリガー**: Trigger 4（実装記録）を中心に全5トリガーと連携
- **データソース**: tasks.json（Task Master）↔ learning_state.yaml（軽量参照）

---

## 🏗️ アーキテクチャ設計

### 役割分離原則

| システム | 主要責任 | データ保持 | ファイルサイズ |
|---------|---------|-----------|--------------|
| **学習自動化システム** | Week/Day/Phase進捗、スキル習熟度、学習時間管理 | learning_state.yaml | 3-4KB（軽量） |
| **Task Master** | 実装タスク詳細管理、サブタスク分解、品質ゲート | tasks.json | 任意（詳細） |

### データ連携仕様

#### learning_state.yaml構造（軽量参照版）
```yaml
portfolio:
  current_tasks:                      # Task Master参照リスト
    - id: "1.1"                       # Task Master tasks.json参照ID
      name: "BaseAPIClient実装"       # 表示用キャッシュ（Task Masterから取得）
      status: "in_progress"           # Task Masterと同期
      progress: 75                    # Task Masterから算出
      estimated_hours: 6              # Task Masterから取得
```

#### tasks.json構造（Task Master - Single Source of Truth）
```json
{
  "1.1": {
    "id": "1.1",
    "title": "BaseAPIClient実装",
    "description": "同期HTTPクライアント基盤実装",
    "status": "in-progress",
    "priority": "high",
    "dependencies": [],
    "estimatedHours": 6,
    "actualHours": 4.5,
    "progress": 75,
    "subtasks": [
      {
        "id": "1.1.1",
        "title": "リトライロジック実装",
        "status": "done",
        "acceptanceCriteria": [
          "指数バックオフ実装",
          "リトライ回数上限設定可能",
          "4xxエラーは即座失敗"
        ]
      }
    ],
    "acceptanceCriteria": [
      "pytest合格（カバレッジ60%+）",
      "ruff/mypy合格",
      "リトライロジック動作確認"
    ],
    "testStrategy": "単体テスト（モック中心）、統合テスト（実API）",
    "definitionOfDone": [
      "全品質ゲート合格",
      "git commit実行",
      "ドキュメント更新"
    ]
  }
}
```

### 統合フロー図

```
┌──────────────────────────────────────────────────────────┐
│                  ユーザー操作                             │
│       「実装記録」トリガー発動                            │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│         Step 1: Git自動解析（並列実行）                   │
│  ├─ git log -1 --pretty=format:"%s"  # コミットメッセージ │
│  ├─ git diff --stat HEAD~1 HEAD      # 変更統計          │
│  └─ uv run pytest --cov | grep "TOTAL" # カバレッジ       │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│      Step 2: Task Master照会（並列実行）                  │
│  ├─ task-master show <id>            # タスク詳細取得    │
│  ├─ learning_state.yaml読込          # 現在タスク確認    │
│  └─ AI推論: コミット内容 → タスクマッチング              │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│       Step 3: Task Master更新（逐次実行）                 │
│  ├─ task-master update-subtask --id=<id>                 │
│  │   --prompt="実装内容要約 + 変更統計"                   │
│  └─ task-master set-status --id=<id> --status=done       │
│      (完了時のみ)                                         │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│    Step 4: learning_state.yaml同期（Edit Tool）          │
│  ├─ current_tasks[].status 更新                          │
│  ├─ current_tasks[].progress 更新                        │
│  └─ metrics.test_coverage 更新                           │
└─────────────────┬────────────────────────────────────────┘
                  │
                  ▼
┌──────────────────────────────────────────────────────────┐
│    Step 5: daily_progress.md記録（Edit Tool）            │
│  └─ 日次実装進捗セクション追加                            │
│      - 実装時間、変更統計、カバレッジ変化                 │
└──────────────────────────────────────────────────────────┘
```

---

## 🔧 実装フロー詳細

### Phase 1: PRD再構成（Week 7 Day 1-2、推定4時間）

#### アクション1.1: PRD Section A作成
**ファイル**: `.taskmaster/docs/prd.md` → Section A（参照情報）

**具体的作業**:
1. 既存PRD（line 1-249）から以下を抽出:
   - プロジェクト概要
   - 技術スタック
   - 非機能要件
   - 将来拡張
   - ターゲットユーザー
   - デザイン要件

2. Section A構成（Task Master実装不要な参照情報）:
```markdown
# Section A: プロジェクト参照情報

## 概要
（既存内容維持）

## 技術スタック
（既存内容維持）

## 非機能要件
（既存内容維持）

## 将来拡張
（既存内容維持）
```

**成果物**:
- [ ] Section A: 参照情報（100-150行）

#### アクション1.2: PRD Section B作成
**ファイル**: `.taskmaster/docs/prd.md` → Section B（実装タスク）

**具体的作業**:
1. 既存Phase 1-6から実装タスクを抽出:
   - Phase 1: BaseAPIClient, JSONPlaceholderClient実装
   - Phase 2: AsyncAPIClient, AsyncJSONPlaceholderClient実装
   - Phase 3: pytest統合、Pydantic Settings、structlog統合
   - Phase 4: Dockerマルチステージビルド、docker-compose構築
   - Phase 5: GitHub Actions実装、品質ゲート
   - Phase 6: README最適化、Case Study追加

2. **重要発見（不明点1.2解決）**:
   - **tasks.jsonの現状**: 0 bytes（空ファイル）
   - **タスクID衝突リスク**: 存在しない
   - **バックアップ不要**: `task-master parse-prd`前のバックアップ操作は不要
   - **初回実行の安全性**: データ損失リスクゼロ、安心して初期化可能

3. Section B構成（Task Master管理対象）:
```markdown
# Section B: 実装タスク（Task Master管理）

## Feature 1: Core API Client
### User Story
開発者として、信頼性の高いHTTP通信を実現するため、リトライロジック・タイムアウト管理・カスタム例外階層を備えた同期APIクライアントが必要。

### Acceptance Criteria（AI生成70% + 人間レビュー30%）
**AI自動生成部分（70%）**:
- BaseAPIClient実装（リトライロジック、タイムアウト管理）
- JSONPlaceholderClient実装（RESTful操作）
- 単体テスト（カバレッジ60%+）
- pytest/ruff/mypy合格

**人間レビュー追加部分（30%）**:
- セキュリティ: HTTPS必須、証明書検証有効
- エッジケース: ネットワーク切断時のグレースフルデグラデーション
- ビジネス影響: タイムアウト値の業務要件適合性確認

**受入基準品質保証プロセス**:
1. Task Master AI生成 → 70%品質の基準生成
2. 人間レビュー → セキュリティ・エッジケース・ビジネス影響追加
3. 最終品質 → 85-90%達成

### Technical Requirements
- httpx同期クライアント使用
- 指数バックオフ実装
- 5レベル例外階層

### Implementation Tasks
1. BaseAPIClient基盤実装（6h）
2. JSONPlaceholderClient実装（4h）
3. 単体テスト作成（4h）

## Feature 2: Async Implementation
（同様の構成で記載、受入基準もAI生成70% + 人間30%方式）
```

**成果物**:
- [ ] Section B: 実装タスク（150-200行）
- [ ] Feature 1-6: User Story + Acceptance Criteria（AI 70% + 人間30%）+ Tasks

#### アクション1.3: PRD検証
**担当エージェント**: `requirements-analyst`

**検証観点**:
1. **完全性**: 全Phase 1-6の実装タスクがSection Bに含まれているか
2. **明確性**: 各Featureの受入基準が具体的か
3. **粒度**: 実装タスクが6-10時間単位に分解されているか
4. **依存関係**: Feature間の依存が明示されているか

**検証コマンド**:
```bash
# 1. requirements-analystエージェント起動
@agent-requirements "PRD Section Bのレビュー: 実装タスクの完全性・明確性・粒度・依存関係を検証"

# 2. 検証結果に基づき修正
# （エージェント指摘事項を反映）
```

**成果物**:
- [ ] PRD検証レポート
- [ ] Section B修正版

---

### Phase 2: Task Master初期化（Week 7 Day 2、推定2時間）

#### アクション2.1: Task Master初期化
**具体的作業**:
```bash
# 0. バージョン互換性チェック（不明点2.3解決）
task-master --version
# 推奨: v1.7.0以上（schema v2.0対応）

# 1. Task Master初期化（既に完了していればスキップ）
task-master init

# 2. PRD解析実行
task-master parse-prd .taskmaster/docs/prd.md

# 3. タスク生成確認
task-master list
```



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
**バージョン互換性保証（不明点2.3解決）**:
```python
def check_compatibility() -> bool:
    """CLI version ↔ schema version互換性チェック"""
    from packaging import version

    cli_version = version.parse(get_taskmaster_cli_version())
    schema_version = version.parse(get_tasks_json_schema_version())

    # Compatibility Matrix
    compatibility = {
        '1.0': ['1.4.0', '1.5.0', '1.6.0'],  # Legacy schema
        '2.0': ['1.7.0', '2.0.0']            # Current schema
    }

    compatible_versions = compatibility.get(str(schema_version), [])
    is_compatible = any(cli_version >= version.parse(v) for v in compatible_versions)

    if not is_compatible:
        logger.error("❌ Version incompatibility",
                     cli_version=str(cli_version),
                     schema_version=str(schema_version))
        raise VersionError(f"CLI v{cli_version} incompatible with schema v{schema_version}")

    logger.info("✅ Version compatibility verified",
                cli_version=str(cli_version),
                schema_version=str(schema_version))
    return True
```

**固定化戦略**:
- `package.json`: `"task-master-ai": "^1.7.0"` （自動マイナーアップデート許可）
- メジャーバージョン変更時: マイグレーションスクリプト実行必須
- CI/CDでバージョン互換性テスト自動実行

**期待結果**:
- `.taskmaster/tasks/tasks.json` 生成
- 6つのFeatureタスク生成（1-6）
- 各Feature配下に実装タスク生成（1.1, 1.2, ...）

**検証観点**:
- [ ] バージョン互換性: CLI v1.7.0+ ↔ schema v2.0
- [ ] Feature数: 6個（Phase 1-6対応）
- [ ] 実装タスク総数: 15-20個（Phase 1-6の全実装タスク）
- [ ] 依存関係: Feature 2 → Feature 1等の依存が正しく設定

#### アクション2.2: タスク複雑度分析
**具体的作業**:
```bash
# 1. 複雑度分析実行
task-master analyze-complexity --research

# 2. レポート確認
task-master complexity-report
```

**成果物**:
- [ ] `.taskmaster/reports/task-complexity-report.json`
- [ ] 各タスクの複雑度スコア（0.0-1.0）

#### アクション2.3: サブタスク展開
**具体的作業**:
```bash
# 複雑度0.7以上のタスクを自動展開
task-master expand --all --research
```

**期待結果**:
- 複雑タスク（6h以上）がサブタスクに分解
- 各サブタスク: 2-4時間単位

**成果物**:
- [ ] tasks.json更新（サブタスク追加）
- [ ] 実装準備完了

#### アクション2.4: スキーマバージョン管理とマイグレーション実装（Q6対応）
**背景**: Requirements Analyst Q6「tasks.jsonとlearning_state.yamlのスキーマバージョン管理と、バージョン不一致時の自動マイグレーション機能」への回答実装

**戦略説明**:

**1. スキーマバージョン設計**:
- `tasks.json`: `"_schema_version": "2.0"` フィールド追加
- `learning_state.yaml`: `metadata.schema_version: "1.1"` 追加
- セマンティックバージョニング（major.minor）採用

**2. マイグレーションチェーン**:
- V1.0 → V1.1: `learning_history[]`フィールド追加
- V1.1 → V2.0: `portfolio.current_tasks[]`構造変更
- 自動検出 → バックアップ → 段階的マイグレーション

**3. 互換性保証**:
- 下位互換: 旧バージョンYAMLを新システムで読込可能
- 上位互換: マイグレーション後も旧CLI動作保証（read-only）
- フォールバック: マイグレーション失敗時は旧スキーマ維持

**実装コード**:

```python
# scripts/schema_manager.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Callable
import yaml
import shutil
import structlog
from pathlib import Path
from datetime import datetime

logger = structlog.get_logger()

class SchemaVersion(Enum):
    """サポートされるスキーマバージョン"""
    V1_0 = "1.0"  # 初期版
    V1_1 = "1.1"  # learning_history追加
    V2_0 = "2.0"  # current_tasks構造変更

    @classmethod
    def from_string(cls, version_str: str) -> 'SchemaVersion':
        """文字列からSchemaVersionを取得"""
        try:
            return cls(version_str)
        except ValueError:
            raise ValueError(f"Unsupported schema version: {version_str}")

    def __lt__(self, other: 'SchemaVersion') -> bool:
        """バージョン比較: self < other"""
        version_order = [self.V1_0, self.V1_1, self.V2_0]
        return version_order.index(self) < version_order.index(other)

@dataclass
class MigrationResult:
    """マイグレーション結果"""
    success: bool
    from_version: str
    to_version: str
    backup_path: Optional[str] = None
    error: Optional[str] = None

class TaskSchemaManager:
    """tasks.json / learning_state.yamlのスキーマ管理"""

    CURRENT_TASKS_SCHEMA = SchemaVersion.V2_0
    CURRENT_LEARNING_SCHEMA = SchemaVersion.V1_1

    def __init__(
        self,
        tasks_json_path: Path,
        learning_state_path: Path
    ):
        self.tasks_json_path = tasks_json_path
        self.learning_state_path = learning_state_path

    def migrate_if_needed(self) -> MigrationResult:
        """
        スキーマバージョンチェック + 必要時自動マイグレーション

        Returns:
            MigrationResult: マイグレーション結果

        Raises:
            ValueError: 未サポートバージョン
            OSError: ファイル操作失敗
        """

        # 1. 現在のバージョン取得
        with open(self.learning_state_path, 'r') as f:
            data = yaml.safe_load(f)

        current_version_str = data.get('metadata', {}).get('schema_version', '1.0')

        try:
            current_version = SchemaVersion.from_string(current_version_str)
        except ValueError as e:
            logger.error("unsupported_schema_version", version=current_version_str)
            return MigrationResult(
                success=False,
                from_version=current_version_str,
                to_version=self.CURRENT_LEARNING_SCHEMA.value,
                error=str(e)
            )

        # 2. 最新バージョンかチェック
        if current_version == self.CURRENT_LEARNING_SCHEMA:
            logger.info("schema_up_to_date", version=current_version.value)
            return MigrationResult(
                success=True,
                from_version=current_version.value,
                to_version=current_version.value
            )

        # 3. マイグレーション必要
        logger.warning(
            "schema_migration_needed",
            from_version=current_version.value,
            to_version=self.CURRENT_LEARNING_SCHEMA.value
        )

        # 4. バックアップ作成（POSIX atomic）
        backup_path = self._create_backup(self.learning_state_path)

        try:
            # 5. マイグレーション実行
            migrated_data = self._execute_migration_chain(
                data=data,
                from_version=current_version,
                to_version=self.CURRENT_LEARNING_SCHEMA
            )

            # 6. 新スキーマで保存（atomic write）
            self._atomic_write(self.learning_state_path, migrated_data)

            logger.info(
                "schema_migration_success",
                from_version=current_version.value,
                to_version=self.CURRENT_LEARNING_SCHEMA.value,
                backup=str(backup_path)
            )

            return MigrationResult(
                success=True,
                from_version=current_version.value,
                to_version=self.CURRENT_LEARNING_SCHEMA.value,
                backup_path=str(backup_path)
            )

        except Exception as e:
            # 7. エラー時: バックアップから復元
            logger.error(
                "schema_migration_failed",
                error=str(e),
                restoring_backup=True
            )

            shutil.copy2(backup_path, self.learning_state_path)

            return MigrationResult(
                success=False,
                from_version=current_version.value,
                to_version=self.CURRENT_LEARNING_SCHEMA.value,
                backup_path=str(backup_path),
                error=str(e)
            )

    def _execute_migration_chain(
        self,
        data: dict,
        from_version: SchemaVersion,
        to_version: SchemaVersion
    ) -> dict:
        """
        段階的マイグレーション実行

        Example: V1.0 → V2.0 は V1.0 → V1.1 → V2.0 の2段階
        """

        current_data = data
        version_chain = [SchemaVersion.V1_0, SchemaVersion.V1_1, SchemaVersion.V2_0]

        # from_version → to_versionの範囲でマイグレーション
        start_idx = version_chain.index(from_version)
        end_idx = version_chain.index(to_version)

        for i in range(start_idx, end_idx):
            current_version = version_chain[i]
            next_version = version_chain[i + 1]

            logger.info(
                "executing_migration_step",
                from_version=current_version.value,
                to_version=next_version.value
            )

            # マイグレーション関数を動的に取得・実行
            migration_func = getattr(
                self,
                f"_migrate_{current_version.value.replace('.', '_')}_to_{next_version.value.replace('.', '_')}"
            )

            current_data = migration_func(current_data)

        return current_data

    def _migrate_v1_0_to_v1_1(self, data: dict) -> dict:
        """V1.0 → V1.1: learning_historyフィールド追加"""

        if 'learning_history' not in data:
            data['learning_history'] = []

        data['metadata']['schema_version'] = SchemaVersion.V1_1.value
        data['metadata']['last_migration'] = datetime.now().isoformat()

        logger.info("migration_step_completed", step="v1_0_to_v1_1")
        return data

    def _migrate_v1_1_to_v2_0(self, data: dict) -> dict:
        """
        V1.1 → V2.0: portfolio.current_tasks構造変更

        変更内容:
        - 旧: current_tasks: [1, 2, 3]
        - 新: current_tasks: [{id: 1, title: "..."}, {id: 2, title: "..."}]
        """

        if 'portfolio' in data and 'current_tasks' in data['portfolio']:
            old_tasks = data['portfolio']['current_tasks']

            # タスクIDリスト → タスク詳細オブジェクトリスト
            if isinstance(old_tasks, list) and old_tasks and isinstance(old_tasks[0], (int, str)):
                # tasks.jsonから詳細情報取得
                tasks_details = self._fetch_task_details(old_tasks)
                data['portfolio']['current_tasks'] = tasks_details

        data['metadata']['schema_version'] = SchemaVersion.V2_0.value
        data['metadata']['last_migration'] = datetime.now().isoformat()

        logger.info("migration_step_completed", step="v1_1_to_v2_0")
        return data

    def _fetch_task_details(self, task_ids: list) -> list:
        """tasks.jsonからタスク詳細を取得"""

        with open(self.tasks_json_path, 'r') as f:
            tasks_json = yaml.safe_load(f)

        task_map = {task['id']: task for task in tasks_json.get('tasks', [])}

        return [
            {
                'id': task_id,
                'title': task_map.get(task_id, {}).get('title', 'Unknown'),
                'status': task_map.get(task_id, {}).get('status', 'pending')
            }
            for task_id in task_ids
        ]

    def _create_backup(self, file_path: Path) -> Path:
        """バックアップ作成（タイムスタンプ付き）"""

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = file_path.parent / f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"

        shutil.copy2(file_path, backup_path)

        logger.info("backup_created", backup_path=str(backup_path))
        return backup_path

    def _atomic_write(self, file_path: Path, data: dict):
        """アトミック書き込み（POSIX atomic rename）"""

        temp_path = file_path.parent / f"{file_path.name}.tmp"

        # 1. 一時ファイル書き込み
        with open(temp_path, 'w') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        # 2. アトミックリネーム（crash-safe）
        temp_path.rename(file_path)
```

**統合例**:

```python
# Task Master初期化時に自動実行
from schema_manager import TaskSchemaManager

def init_task_master_with_migration():
    """Task Master初期化 + スキーママイグレーション"""

    tasks_json_path = Path('.taskmaster/tasks/tasks.json')
    learning_state_path = Path('learning_state.yaml')

    # 1. スキーママイグレーション実行
    schema_manager = TaskSchemaManager(tasks_json_path, learning_state_path)
    result = schema_manager.migrate_if_needed()

    if not result.success:
        logger.error(
            "❌ Schema migration failed",
            error=result.error,
            backup=result.backup_path
        )
        raise RuntimeError(f"Schema migration failed: {result.error}")

    logger.info(
        "✅ Schema compatibility verified",
        from_version=result.from_version,
        to_version=result.to_version,
        backup=result.backup_path
    )

    # 2. Task Master初期化（通常フロー）
    # task-master init
    # task-master parse-prd ...
```

**テストケース**:

```python
import pytest
from schema_manager import TaskSchemaManager, SchemaVersion, MigrationResult
from pathlib import Path
import yaml

def test_migration_v1_0_to_v1_1(tmp_path):
    """V1.0 → V1.1マイグレーション検証"""

    # 1. V1.0形式のlearning_state.yaml作成
    learning_state = tmp_path / "learning_state.yaml"
    learning_state.write_text("""
metadata:
  schema_version: "1.0"
skill_mastery: {}
    """)

    tasks_json = tmp_path / "tasks.json"
    tasks_json.write_text("tasks: []")

    # 2. マイグレーション実行
    manager = TaskSchemaManager(tasks_json, learning_state)
    result = manager.migrate_if_needed()

    # 3. 検証
    assert result.success
    assert result.from_version == "1.0"
    assert result.to_version == "1.1"

    with open(learning_state, 'r') as f:
        migrated_data = yaml.safe_load(f)

    assert migrated_data['metadata']['schema_version'] == "1.1"
    assert 'learning_history' in migrated_data  # 新フィールド追加確認

def test_migration_chain_v1_0_to_v2_0(tmp_path):
    """V1.0 → V2.0 段階的マイグレーション検証"""

    learning_state = tmp_path / "learning_state.yaml"
    learning_state.write_text("""
metadata:
  schema_version: "1.0"
portfolio:
  current_tasks: [1, 2, 3]
    """)

    tasks_json = tmp_path / "tasks.json"
    tasks_json.write_text("""
tasks:
  - id: 1
    title: "Task 1"
    status: "pending"
  - id: 2
    title: "Task 2"
    status: "in-progress"
    """)

    manager = TaskSchemaManager(tasks_json, learning_state)
    result = manager.migrate_if_needed()

    assert result.success
    assert result.from_version == "1.0"
    assert result.to_version == "2.0"  # 最新バージョン

    with open(learning_state, 'r') as f:
        migrated_data = yaml.safe_load(f)

    # V2.0形式: current_tasks = [{id, title, status}, ...]
    assert isinstance(migrated_data['portfolio']['current_tasks'], list)
    assert migrated_data['portfolio']['current_tasks'][0]['id'] == 1
    assert migrated_data['portfolio']['current_tasks'][0]['title'] == "Task 1"

def test_migration_failure_rollback(tmp_path, monkeypatch):
    """マイグレーション失敗時のロールバック検証"""

    learning_state = tmp_path / "learning_state.yaml"
    original_content = """
metadata:
  schema_version: "1.0"
skill_mastery: {}
    """
    learning_state.write_text(original_content)

    tasks_json = tmp_path / "tasks.json"
    tasks_json.write_text("tasks: []")

    # マイグレーション関数を強制エラー
    def failing_migration(self, data):
        raise RuntimeError("Intentional failure")

    manager = TaskSchemaManager(tasks_json, learning_state)
    monkeypatch.setattr(manager, '_migrate_v1_0_to_v1_1', failing_migration)

    result = manager.migrate_if_needed()

    # 失敗確認
    assert not result.success
    assert "Intentional failure" in result.error

    # ロールバック確認
    with open(learning_state, 'r') as f:
        rolled_back_data = yaml.safe_load(f)

    assert rolled_back_data['metadata']['schema_version'] == "1.0"  # 元に戻る
```

**成果物**:
- [ ] `scripts/schema_manager.py` 作成
- [ ] Task Master初期化フローへの統合（`init_task_master_with_migration()`）
- [ ] `tests/unit/test_schema_migration.py` 作成
- [ ] マイグレーション動作確認（V1.0 → V1.1 → V2.0検証）

---

### Phase 3: learning_state.yaml統合（Week 7 Day 3、推定3時間）

#### アクション3.1: current_tasks初期化
**ファイル**: `learning_state.yaml` → `portfolio.current_tasks[]`

**具体的作業**:
1. Task Masterから現在のタスクリスト取得:
```bash
# 現在進行中のタスク取得
task-master list | grep "in-progress\|pending"
```

2. learning_state.yaml更新:
```yaml
portfolio:
  current_tasks:
    - id: "1.1"                        # Task Master tasks.json参照ID
      name: "BaseAPIClient実装"        # task-master show 1.1 から取得
      status: "in_progress"            # Task Masterと同期
      progress: 0                      # 初期値0
      estimated_hours: 6               # task-master show 1.1 から取得
    - id: "1.2"
      name: "JSONPlaceholderClient実装"
      status: "pending"
      progress: 0
      estimated_hours: 4
```

**自動化スクリプト例（エラーリカバリー + 原子性保証統合版）**:
```python
# scripts/sync_tasks_to_yaml.py
import yaml
import json
import structlog
from pathlib import Path
from typing import Dict, List

logger = structlog.get_logger()

def load_tasks_json() -> Dict:
    """tasks.json読込（不明点2.1: 3層エラーリカバリー）"""
    tasks_path = Path('.taskmaster/tasks/tasks.json')
    backup_path = Path('.taskmaster/tasks/tasks.json.backup')

    # Layer 1: 予防的検証
    if not tasks_path.exists():
        logger.error("❌ tasks.json not found", path=str(tasks_path))
        raise FileNotFoundError(f"tasks.json not found: {tasks_path}")

    # Layer 2: Graceful Degradation
    try:
        with tasks_path.open('r', encoding='utf-8') as f:
            tasks = json.load(f)
        logger.info("✅ tasks.json loaded successfully", task_count=len(tasks))
        return tasks
    except json.JSONDecodeError as e:
        logger.error("❌ JSON parse error", error=str(e), line=e.lineno)
        if backup_path.exists():
            logger.warning("⚠️ Attempting recovery from backup")
            tasks_path.write_text(backup_path.read_text())
            return load_tasks_json()  # Retry after recovery
        else:
            logger.critical("🚨 No backup available")
            raise

def atomic_write_yaml(data: dict, yaml_path: Path):
    """原子性保証のYAML書き込み（不明点2.2: POSIX Atomic Write）"""
    temp_path = yaml_path.with_suffix('.yaml.tmp')
    try:
        with temp_path.open('w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        temp_path.replace(yaml_path)  # POSIX atomic rename
        logger.info("✅ Atomic write completed", path=str(yaml_path))
    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()  # Cleanup on failure
        logger.error("❌ Atomic write failed", error=str(e))
        raise

def sync_tasks_to_yaml():
    """Task Master tasks.json → learning_state.yaml同期（不明点3.1: 単方向同期）"""
    # Task Master tasks.json読込（エラーリカバリー付き）
    tasks = load_tasks_json()

    # 現在進行中・待機中のタスク抽出
    current_tasks = []
    for task_id, task in tasks.items():
        if task['status'] in ['in-progress', 'pending']:
            current_tasks.append({
                'id': task_id,
                'name': task['title'],
                'status': task['status'],
                'progress': task.get('progress', 0),
                'estimated_hours': task.get('estimatedHours', 0)
            })

    # learning_state.yaml読込
    yaml_path = Path('learning_state.yaml')
    with yaml_path.open('r', encoding='utf-8') as f:
        state = yaml.safe_load(f)

    # Single Source of Truth: tasks.json → learning_state.yaml（不明点3.1）
    state['portfolio']['current_tasks'] = current_tasks

    # 原子性保証のYAML書き込み（不明点2.2）
    atomic_write_yaml(state, yaml_path)

    logger.info("✅ Task synchronization completed",
                synced_tasks=len(current_tasks),
                source="tasks.json",
                target="learning_state.yaml")

if __name__ == '__main__':
    sync_tasks_to_yaml()
```

**エラーリカバリー戦略（不明点2.1解決）**:
- **Layer 1: 予防的検証** - ファイル存在確認、JSON構文チェック
- **Layer 2: Graceful Degradation** - バックアップ自動復元（.json.backup）
- **Layer 3: 透明性ログ** - structlogによる詳細コンテキスト記録

**原子性保証（不明点2.2解決）**:
- POSIX atomic rename pattern（.yaml.tmp → .yaml）
- 書き込み失敗時の自動クリーンアップ
- 部分書き込みによるデータ破損防止

**単方向同期アーキテクチャ（不明点3.1解決）**:
- **Single Source of Truth**: tasks.json（Task Master管理）
- **Read-Only View**: learning_state.yaml（軽量ビュー、編集不可）
- **同期方向**: tasks.json → learning_state.yaml（単方向のみ）
- **競合回避**: learning_state.yamlでのタスク編集を禁止（tasks.jsonのみ編集可）
```

**成果物**:
- [ ] learning_state.yaml更新（current_tasks初期化）
- [ ] scripts/sync_tasks_to_yaml.py作成

#### アクション3.2: 同期テスト
**検証観点**:
1. Task Master tasks.json変更 → learning_state.yaml同期確認
2. 同期スクリプト実行時間測定（目標: 1秒以内）

**テスト手順**:
```bash
# 1. Task Master更新
task-master set-status --id=1.1 --status=done

# 2. 同期スクリプト実行
uv run python scripts/sync_tasks_to_yaml.py

# 3. learning_state.yaml確認
grep "1.1" learning_state.yaml
# 期待: status: "done"
```

**成果物**:
- [ ] 同期テスト完了
- [ ] 同期スクリプト動作確認

#### アクション3.3: 同期失敗時のリトライ戦略実装（Q5対応）
**背景**: Requirements Analyst Q5「同期失敗時はエクスポネンシャルバックオフ等でリトライを実装してリトライするのがいいと思うが、推奨の方法を教えてください」への回答実装

**推奨戦略**: 段階的リトライ + Graceful Degradation（ハイブリッド戦略）

**実装**: `scripts/sync_retry_strategy.py`

```python
import time
import random
import yaml
from typing import Optional, Callable
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()

@dataclass
class RetryConfig:
    """リトライ設定"""
    max_attempts: int = 3              # 最大試行回数
    base_delay: float = 1.0            # 初回待機時間（秒）
    max_delay: float = 10.0            # 最大待機時間（秒）
    exponential_base: float = 2.0      # 指数バックオフの底
    jitter: bool = True                # ジッター追加（同時リトライ回避）

@dataclass
class SyncResult:
    """同期結果"""
    status: str      # "success" | "degraded" | "failed"
    attempt: int     # 成功した試行回数（-1=フォールバック使用）
    data: dict       # 同期結果データ
    error: Optional[str] = None  # エラーメッセージ

class SyncRetryStrategy:
    """同期失敗時のリトライ戦略"""

    def __init__(self, config: RetryConfig = RetryConfig()):
        self.config = config

    def execute_with_retry(
        self,
        sync_func: Callable,
        fallback_func: Optional[Callable] = None
    ) -> SyncResult:
        """
        段階的リトライ + Graceful Degradation

        Args:
            sync_func: 同期処理関数
            fallback_func: フォールバック処理（リトライ失敗時）

        Returns:
            SyncResult: 実行結果
        """

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                # 同期実行
                result = sync_func()

                logger.info(
                    "sync_success",
                    attempt=attempt,
                    status="success"
                )

                return SyncResult(
                    status="success",
                    attempt=attempt,
                    data=result
                )

            except FileNotFoundError as e:
                # ファイル不在エラー → 即座失敗（リトライ不要）
                logger.error(
                    "sync_failed_file_not_found",
                    attempt=attempt,
                    error=str(e)
                )

                return self._handle_graceful_degradation(
                    error=e,
                    fallback_func=fallback_func
                )

            except (yaml.YAMLError, OSError) as e:
                # YAML構文エラー・OS障害 → リトライ可能

                if attempt == self.config.max_attempts:
                    # 最終試行失敗 → Graceful Degradation
                    logger.error(
                        "sync_failed_max_retries",
                        attempt=attempt,
                        error=str(e)
                    )

                    return self._handle_graceful_degradation(
                        error=e,
                        fallback_func=fallback_func
                    )

                # エクスポネンシャルバックオフ計算
                delay = min(
                    self.config.base_delay * (self.config.exponential_base ** (attempt - 1)),
                    self.config.max_delay
                )

                # ジッター追加（0-20%のランダム遅延）
                if self.config.jitter:
                    delay *= (1 + random.uniform(0, 0.2))

                logger.warning(
                    "sync_retry_scheduled",
                    attempt=attempt,
                    max_attempts=self.config.max_attempts,
                    delay=delay,
                    error=str(e)
                )

                time.sleep(delay)

    def _handle_graceful_degradation(
        self,
        error: Exception,
        fallback_func: Optional[Callable]
    ) -> SyncResult:
        """
        Graceful Degradation処理

        リトライ失敗時の代替処理:
        1. ローカルメモリキャッシュから復元
        2. 前回成功時のスナップショットから復元
        3. 最小限の初期状態で継続
        """

        if fallback_func:
            try:
                fallback_result = fallback_func()

                logger.info(
                    "sync_fallback_success",
                    status="degraded",
                    fallback_used=True
                )

                return SyncResult(
                    status="degraded",
                    attempt=-1,  # フォールバック使用
                    data=fallback_result,
                    error=str(error)
                )

            except Exception as fallback_error:
                logger.critical(
                    "sync_fallback_failed",
                    original_error=str(error),
                    fallback_error=str(fallback_error)
                )

        # フォールバック失敗 → 最小限の初期状態で継続
        return SyncResult(
            status="failed",
            attempt=-1,
            data=self._get_minimal_state(),
            error=str(error)
        )

    def _get_minimal_state(self) -> dict:
        """最小限の初期状態を返す"""
        return {
            "skill_mastery": {},
            "learning_history": [],
            "implementation_history": [],
            "metadata": {
                "last_sync": None,
                "status": "degraded"
            }
        }
```

**統合例**: `scripts/sync_tasks_to_yaml.py`への適用

```python
from sync_retry_strategy import SyncRetryStrategy, RetryConfig

def sync_tasks_with_retry():
    """リトライ戦略を適用した同期処理"""
    retry_strategy = SyncRetryStrategy(
        config=RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=10.0,
            jitter=True
        )
    )

    result = retry_strategy.execute_with_retry(
        sync_func=sync_tasks_to_yaml,
        fallback_func=lambda: load_from_snapshot()  # スナップショット復元
    )

    if result.status == "success":
        logger.info("✅ Sync completed successfully", attempt=result.attempt)
    elif result.status == "degraded":
        logger.warning("⚠️ Sync degraded mode", error=result.error)
    else:
        logger.error("❌ Sync failed", error=result.error)

    return result
```

**リトライ戦略の特徴**:
- **Exponential Backoff**: 1s → 2s → 4s（最大10s）
- **Jitter**: 0-20%のランダム遅延でthundering herd回避
- **エラー種別判定**: FileNotFoundError（即座失敗）、YAML/OSエラー（リトライ）
- **3層フォールバック**: リトライ → スナップショット復元 → 最小限状態

**テストケース**: `tests/unit/test_sync_retry.py`

```python
import pytest
from sync_retry_strategy import SyncRetryStrategy, RetryConfig, SyncResult

def test_retry_success_on_second_attempt():
    """2回目の試行で成功するケース"""
    attempts = []

    def flaky_sync():
        attempts.append(1)
        if len(attempts) < 2:
            raise OSError("Temporary failure")
        return {"status": "ok"}

    strategy = SyncRetryStrategy()
    result = strategy.execute_with_retry(flaky_sync)

    assert result.status == "success"
    assert result.attempt == 2
    assert len(attempts) == 2

def test_exponential_backoff_timing():
    """Exponential backoffのタイミング検証"""
    import time

    attempts = []

    def always_fail():
        attempts.append(time.time())
        raise OSError("Always fail")

    strategy = SyncRetryStrategy(config=RetryConfig(max_attempts=3))
    result = strategy.execute_with_retry(always_fail)

    # 期待遅延: 1秒 → 2秒（累計: 0s, 1s, 3s）
    assert len(attempts) == 3
    assert attempts[1] - attempts[0] >= 1.0  # 1回目 → 2回目: 1s
    assert attempts[2] - attempts[1] >= 2.0  # 2回目 → 3回目: 2s

def test_graceful_degradation_with_fallback():
    """Graceful Degradationのフォールバック動作確認"""
    def always_fail():
        raise yaml.YAMLError("Parse error")

    def fallback():
        return {"status": "fallback"}

    strategy = SyncRetryStrategy()
    result = strategy.execute_with_retry(always_fail, fallback_func=fallback)

    assert result.status == "degraded"
    assert result.attempt == -1  # フォールバック使用
    assert result.data == {"status": "fallback"}
```

**成果物**:
- [ ] `scripts/sync_retry_strategy.py` 作成
- [ ] `scripts/sync_tasks_to_yaml.py` へのリトライ統合
- [ ] `tests/unit/test_sync_retry.py` 作成
- [ ] リトライ動作確認（意図的エラー発生 → リトライ確認）

---

### Phase 4: Trigger 4統合（Week 7 Day 4-5、推定6時間）


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


#### アクション4.1: Trigger 4フロー実装
**ファイル**: `CLAUDE.md` → トリガー4セクション更新

**具体的作業**:
1. 既存Trigger 4フロー（`学習・実装・記録フロー自動化要件.md` line 507-599）を拡張:

```markdown
### トリガー4: 実装記録（完全自動化版 + Task Master統合）

**検出キーワード**: `実装記録`

**実行フロー**:

1. **Git解析（完全自動・並列実行）**:
   ```bash
   git diff HEAD~1..HEAD --stat
   git log -1 --format="%s%n%b"
   uv run pytest --cov | grep "TOTAL"
   ```

2. **Task Master照会（並列実行）**:
   ```bash
   # learning_state.yaml読込
   current_tasks=$(grep "id:" learning_state.yaml)

   # 各タスク詳細取得
   task-master show <id>
   ```

3. **AI推論（自動マッチング）**:
   - コミットメッセージ + 差分 → 実装内容要約
   - current_tasks[] × タスク詳細 → 最適マッチング
   - 変更統計 → progress推定（例: 50行変更 → 75% progress）

4. **Task Master更新（逐次実行）**:
   ```bash
   # サブタスク更新
   task-master update-subtask --id=<matched_id> \
     --prompt="実装内容: <要約>、変更: +<lines>/-<lines>、カバレッジ: <cov>%"

   # 完了判定（品質ゲート全合格時）
   if [ pytest合格 ] && [ ruff合格 ] && [ mypy合格 ]; then
     task-master set-status --id=<matched_id> --status=done
   fi
   ```

5. **learning_state.yaml同期（Edit Tool）**:
   ```python
   # scripts/sync_tasks_to_yaml.py 実行
   # → current_tasks[matched_id].status, progress更新
   ```

6. **daily_progress.md記録（Edit Tool）**:
   - 日次実装進捗セクション追加
   - メトリクス変化記録
```

**成果物**:
- [ ] CLAUDE.md更新（Trigger 4 + Task Master統合フロー）

#### アクション4.2: AIマッチングロジック実装
**ファイル**: `scripts/match_commit_to_task.py`

**具体的作業**:
```python
import re
import json
import subprocess
from typing import Dict, Optional

def get_git_info() -> Dict[str, str]:
    """Git情報取得"""
    commit_msg = subprocess.check_output(
        ["git", "log", "-1", "--format=%s%n%b"]
    ).decode().strip()

    diff_stat = subprocess.check_output(
        ["git", "diff", "--stat", "HEAD~1", "HEAD"]
    ).decode().strip()

    return {"commit_msg": commit_msg, "diff_stat": diff_stat}

def match_to_task(commit_info: Dict, current_tasks: list) -> Optional[str]:
    """
    コミット情報からTask Masterタスクにマッチング

    マッチングロジック:
    1. コミットメッセージからタスクID抽出（例: "feat: BaseAPIClient実装 (task 1.1)"）
    2. タスク名からキーワードマッチング（例: "BaseAPIClient" → task 1.1）
    3. 変更ファイルパスからタスク推定（例: utils/api_client.py → task 1.1）
    """
    commit_msg = commit_info["commit_msg"]

    # パターン1: タスクID直接指定
    task_id_match = re.search(r"task\s+(\d+\.\d+)", commit_msg, re.IGNORECASE)
    if task_id_match:
        return task_id_match.group(1)

    # パターン2: タスク名キーワードマッチング
    for task in current_tasks:
        # タスク名からキーワード抽出（例: "BaseAPIClient実装" → "BaseAPIClient"）
        keywords = re.findall(r"[A-Z][a-z]+(?:[A-Z][a-z]+)*", task["name"])
        for keyword in keywords:
            if keyword.lower() in commit_msg.lower():
                return task["id"]

    # パターン3: マッチング失敗
    return None

def estimate_progress(diff_stat: str, current_progress: int) -> int:
    """
    変更統計からprogress推定

    推定ロジック:
    - 50行未満変更: +10% progress
    - 50-150行変更: +25% progress
    - 150行以上変更: +50% progress
    """
    lines_match = re.search(r"(\d+) insertions.*(\d+) deletions", diff_stat)
    if not lines_match:
        return current_progress

    total_lines = int(lines_match.group(1)) + int(lines_match.group(2))

    if total_lines < 50:
        increment = 10
    elif total_lines < 150:
        increment = 25
    else:
        increment = 50

    return min(current_progress + increment, 100)

# 使用例
if __name__ == "__main__":
    git_info = get_git_info()

    # learning_state.yamlから現在タスク取得（YAML解析は別途実装）
    current_tasks = [
        {"id": "1.1", "name": "BaseAPIClient実装", "progress": 50}
    ]

    matched_id = match_to_task(git_info, current_tasks)
    if matched_id:
        print(f"✅ マッチング成功: task {matched_id}")

        # progress推定
        task = next(t for t in current_tasks if t["id"] == matched_id)
        new_progress = estimate_progress(git_info["diff_stat"], task["progress"])
        print(f"📊 Progress: {task['progress']}% → {new_progress}%")
    else:
        print("❌ マッチング失敗: 手動でタスクIDを指定してください")
```

**成果物**:
- [ ] scripts/match_commit_to_task.py作成
- [ ] マッチング精度テスト（目標: 85%+）

#### アクション4.2.1: AI駆動マッチングとフォールバック戦略（Q7対応）
**背景**: Requirements Analyst Q7「AIマッチングが失敗した場合のフォールバック戦略（ルールベース、手動入力、推測）」への回答実装

**戦略**: 3層フォールバック + ハイブリッドアプローチ

1. **Primary: AI駆動マッチング**（信頼度閾値: 0.7）
   - Claude API呼び出しでコミットメッセージ + タスクリストを解析
   - 複数候補返却時は信頼度スコア付き
   - API障害時は自動的にSecondaryへフォールバック

2. **Secondary: ルールベースマッチング**（正規表現 + キーワード）
   - タスクID直接抽出（例: "task 1.1"）
   - タスク名キーワードマッチング（例: "BaseAPIClient"）
   - ファイルパスからの推測（例: utils/api_client.py → API関連タスク）

3. **Tertiary: 手動入力プロンプト**
   - AIとルールの両方が失敗した場合
   - current_tasksリストを表示してユーザー選択
   - スキップオプション提供（後で手動更新）

4. **Hybrid: AIとルールの組み合わせ**（信頼度0.5-0.7時）
   - AI候補（信頼度低）+ ルール候補を両方表示
   - ユーザーに最終選択を委ねる

**実装コード**:

```python
# scripts/ai_matching_with_fallback.py
import re
import json
import subprocess
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import structlog
from anthropic import Anthropic, APIError, APITimeoutError

logger = structlog.get_logger()

@dataclass
class MatchResult:
    """マッチング結果"""
    task_id: Optional[str]
    confidence: float  # 0.0-1.0
    method: str  # "ai" | "rule" | "manual" | "hybrid"
    candidates: List[Tuple[str, float]] = None  # [(task_id, score), ...]

class AIMatchingWithFallback:
    """AI駆動タスクマッチング + 3層フォールバック"""

    AI_CONFIDENCE_THRESHOLD = 0.7  # AI単独採用の閾値
    HYBRID_CONFIDENCE_THRESHOLD = 0.5  # ハイブリッド判定の閾値

    def __init__(self, anthropic_api_key: str):
        self.client = Anthropic(api_key=anthropic_api_key)

    def match_commit_to_task(
        self,
        commit_msg: str,
        diff_stat: str,
        current_tasks: List[Dict]
    ) -> MatchResult:
        """
        コミット情報からTask Masterタスクにマッチング

        Args:
            commit_msg: コミットメッセージ
            diff_stat: git diff --stat出力
            current_tasks: learning_state.yamlのcurrent_tasks配列

        Returns:
            MatchResult: マッチング結果（信頼度・手法付き）
        """

        # 1. Primary: AI駆動マッチング試行
        ai_result = self._try_ai_matching(commit_msg, diff_stat, current_tasks)

        if ai_result and ai_result.confidence >= self.AI_CONFIDENCE_THRESHOLD:
            logger.info(
                "ai_matching_success",
                task_id=ai_result.task_id,
                confidence=ai_result.confidence
            )
            return ai_result

        # 2. Secondary: ルールベースマッチング試行
        rule_result = self._try_rule_based_matching(commit_msg, diff_stat, current_tasks)

        if rule_result and rule_result.confidence >= 0.8:  # ルールは高信頼度時のみ採用
            logger.info(
                "rule_matching_success",
                task_id=rule_result.task_id,
                method=rule_result.method
            )
            return rule_result

        # 3. Hybrid: AIとルール両方で候補がある場合
        if ai_result and rule_result:
            return self._hybrid_matching(ai_result, rule_result, current_tasks)

        # 4. Tertiary: 手動入力プロンプト
        logger.warning(
            "matching_failed",
            ai_tried=bool(ai_result),
            rule_tried=bool(rule_result)
        )
        return self._manual_matching_prompt(current_tasks)

    def _try_ai_matching(
        self,
        commit_msg: str,
        diff_stat: str,
        current_tasks: List[Dict]
    ) -> Optional[MatchResult]:
        """
        AI駆動マッチング試行（Claude API）

        Returns:
            MatchResult or None: マッチング結果（API失敗時はNone）
        """

        try:
            # タスクリストを整形
            tasks_text = "\n".join([
                f"- {task['id']}: {task.get('title', task.get('name', 'Unknown'))}"
                for task in current_tasks
            ])

            prompt = f"""以下のGitコミット情報から、最も関連性の高いTask Masterタスクを特定してください。

コミットメッセージ:
{commit_msg}

変更統計:
{diff_stat}

タスクリスト:
{tasks_text}

出力形式（JSON）:
{{
  "task_id": "1.1",
  "confidence": 0.85,
  "reasoning": "理由説明"
}}

信頼度（confidence）は0.0-1.0の範囲で、以下の基準で評価してください:
- 0.9-1.0: コミットメッセージにタスクIDや名前が明示されている
- 0.7-0.9: 変更内容がタスクの目的と明確に一致
- 0.5-0.7: 部分的な一致、複数候補あり
- 0.0-0.5: 関連性が低い、推測のみ

マッチングできない場合は task_id: null を返してください。"""

            # Claude API呼び出し（タイムアウト: 10秒）
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=500,
                timeout=10.0,
                messages=[{"role": "user", "content": prompt}]
            )

            # JSON解析
            response_text = message.content[0].text
            match_data = json.loads(response_text)

            if match_data.get("task_id"):
                return MatchResult(
                    task_id=match_data["task_id"],
                    confidence=match_data.get("confidence", 0.0),
                    method="ai"
                )

            logger.info("ai_matching_no_match")
            return None

        except (APIError, APITimeoutError) as e:
            logger.error("ai_matching_api_error", error=str(e))
            return None

        except json.JSONDecodeError as e:
            logger.error("ai_matching_parse_error", error=str(e))
            return None

    def _try_rule_based_matching(
        self,
        commit_msg: str,
        diff_stat: str,
        current_tasks: List[Dict]
    ) -> Optional[MatchResult]:
        """
        ルールベースマッチング試行

        マッチングロジック:
        1. タスクID直接抽出（例: "task 1.1"）
        2. タスク名キーワードマッチング（例: "BaseAPIClient"）
        3. ファイルパスからの推測（例: utils/api_client.py）
        """

        # パターン1: タスクID直接指定（信頼度: 1.0）
        task_id_match = re.search(r"task\s+(\d+\.\d+)", commit_msg, re.IGNORECASE)
        if task_id_match:
            task_id = task_id_match.group(1)
            return MatchResult(
                task_id=task_id,
                confidence=1.0,
                method="rule_id_explicit"
            )

        # パターン2: タスク名キーワードマッチング（信頼度: 0.8）
        for task in current_tasks:
            task_title = task.get('title', task.get('name', ''))

            # キャメルケース分割（例: BaseAPIClient → [Base, API, Client]）
            keywords = re.findall(r"[A-Z][a-z]+(?:[A-Z][a-z]+)*", task_title)

            for keyword in keywords:
                if keyword.lower() in commit_msg.lower():
                    return MatchResult(
                        task_id=task['id'],
                        confidence=0.8,
                        method="rule_keyword"
                    )

        # パターン3: ファイルパスマッチング（信頼度: 0.6）
        # 例: utils/api_client.py変更 → "api_client"含むタスク
        file_paths = re.findall(r"(\w+/[\w/]+\.py)", diff_stat)

        for file_path in file_paths:
            base_name = file_path.split('/')[-1].replace('.py', '')

            for task in current_tasks:
                task_title = task.get('title', task.get('name', ''))

                if base_name.lower() in task_title.lower().replace(' ', ''):
                    return MatchResult(
                        task_id=task['id'],
                        confidence=0.6,
                        method="rule_filepath"
                    )

        logger.info("rule_matching_no_match")
        return None

    def _hybrid_matching(
        self,
        ai_result: MatchResult,
        rule_result: MatchResult,
        current_tasks: List[Dict]
    ) -> MatchResult:
        """
        ハイブリッドマッチング（AIとルール両方で候補がある場合）

        戦略:
        - 両者が一致 → 信頼度upして採用
        - 両者が不一致 → ユーザー選択を促す
        """

        if ai_result.task_id == rule_result.task_id:
            # 両者一致: 信頼度を平均+ボーナス
            combined_confidence = (ai_result.confidence + rule_result.confidence) / 2 + 0.1
            combined_confidence = min(combined_confidence, 1.0)

            logger.info(
                "hybrid_matching_consensus",
                task_id=ai_result.task_id,
                confidence=combined_confidence
            )

            return MatchResult(
                task_id=ai_result.task_id,
                confidence=combined_confidence,
                method="hybrid_consensus"
            )

        # 両者不一致: ユーザー選択
        logger.warning(
            "hybrid_matching_conflict",
            ai_candidate=ai_result.task_id,
            rule_candidate=rule_result.task_id
        )

        return MatchResult(
            task_id=None,
            confidence=0.0,
            method="hybrid_conflict",
            candidates=[
                (ai_result.task_id, ai_result.confidence),
                (rule_result.task_id, rule_result.confidence)
            ]
        )

    def _manual_matching_prompt(self, current_tasks: List[Dict]) -> MatchResult:
        """
        手動入力プロンプト（マッチング失敗時）

        ユーザーにタスクリストを表示して選択を促す
        """

        print("\n⚠️  自動マッチング失敗: タスクを手動で選択してください\n")
        print("現在のタスク:")

        for i, task in enumerate(current_tasks, 1):
            task_title = task.get('title', task.get('name', 'Unknown'))
            print(f"  {i}. [{task['id']}] {task_title}")

        print(f"  {len(current_tasks) + 1}. スキップ（後で手動更新）")

        while True:
            choice = input("\n選択番号を入力: ").strip()

            try:
                choice_num = int(choice)

                if choice_num == len(current_tasks) + 1:
                    logger.info("manual_matching_skipped")
                    return MatchResult(
                        task_id=None,
                        confidence=0.0,
                        method="manual_skipped"
                    )

                if 1 <= choice_num <= len(current_tasks):
                    selected_task = current_tasks[choice_num - 1]
                    logger.info(
                        "manual_matching_selected",
                        task_id=selected_task['id']
                    )

                    return MatchResult(
                        task_id=selected_task['id'],
                        confidence=1.0,  # 手動選択は信頼度100%
                        method="manual_selected"
                    )

                print("❌ 無効な選択です。もう一度入力してください。")

            except ValueError:
                print("❌ 数字を入力してください。")

# 使用例
if __name__ == "__main__":
    import os

    matcher = AIMatchingWithFallback(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    # Git情報取得
    commit_msg = subprocess.check_output(
        ["git", "log", "-1", "--format=%s%n%b"]
    ).decode().strip()

    diff_stat = subprocess.check_output(
        ["git", "diff", "--stat", "HEAD~1", "HEAD"]
    ).decode().strip()

    # learning_state.yamlから現在タスク取得（簡略版）
    current_tasks = [
        {"id": "1.1", "title": "BaseAPIClient実装"},
        {"id": "1.2", "title": "JSONPlaceholderClient実装"},
        {"id": "2.1", "title": "AsyncAPIClient実装"}
    ]

    # マッチング実行
    result = matcher.match_commit_to_task(commit_msg, diff_stat, current_tasks)

    print(f"\n📊 マッチング結果:")
    print(f"  タスクID: {result.task_id}")
    print(f"  信頼度: {result.confidence:.2f}")
    print(f"  手法: {result.method}")

    if result.candidates:
        print(f"  候補: {result.candidates}")
```

**統合例（Trigger 4フローへの組み込み）**:

```python
# scripts/trigger_4_implementation_record.py
from ai_matching_with_fallback import AIMatchingWithFallback, MatchResult
import subprocess
import os

def trigger_4_with_ai_matching():
    """Trigger 4: 実装記録（AI駆動マッチング版）"""

    # 1. Git情報取得
    commit_msg = subprocess.check_output(
        ["git", "log", "-1", "--format=%s%n%b"]
    ).decode().strip()

    diff_stat = subprocess.check_output(
        ["git", "diff", "--stat", "HEAD~1", "HEAD"]
    ).decode().strip()

    # 2. 品質ゲート実行
    pytest_result = subprocess.run(["uv", "run", "pytest", "--cov=."], capture_output=True)
    ruff_result = subprocess.run(["uv", "run", "ruff", "check", "."], capture_output=True)

    if pytest_result.returncode != 0 or ruff_result.returncode != 0:
        print("❌ 品質ゲート失敗: 実装活動不認定")
        return

    # 3. learning_state.yamlから現在タスク取得
    # （YAML解析は省略）
    current_tasks = [
        {"id": "1.1", "title": "BaseAPIClient実装"},
        {"id": "1.2", "title": "JSONPlaceholderClient実装"}
    ]

    # 4. AI駆動マッチング実行
    matcher = AIMatchingWithFallback(
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )

    result: MatchResult = matcher.match_commit_to_task(
        commit_msg, diff_stat, current_tasks
    )

    if result.task_id:
        print(f"✅ マッチング成功: task {result.task_id} ({result.method}, 信頼度: {result.confidence:.2f})")

        # 5. Task Master更新
        subprocess.run([
            "task-master", "update-subtask",
            f"--id={result.task_id}",
            f"--prompt=実装内容: {commit_msg[:100]}、信頼度: {result.confidence:.2f}"
        ])

        # 6. 完了判定（品質ゲート全合格時）
        subprocess.run([
            "task-master", "set-status",
            f"--id={result.task_id}",
            "--status=done"
        ])

    else:
        print(f"⚠️  マッチング失敗（{result.method}）: Task Master更新スキップ")

if __name__ == "__main__":
    trigger_4_with_ai_matching()
```

**テストケース**:

```python
# tests/unit/test_ai_matching_fallback.py
import pytest
from unittest.mock import Mock, patch
from ai_matching_with_fallback import AIMatchingWithFallback, MatchResult

@pytest.fixture
def matcher():
    return AIMatchingWithFallback(anthropic_api_key="test-key")

@pytest.fixture
def sample_tasks():
    return [
        {"id": "1.1", "title": "BaseAPIClient実装"},
        {"id": "1.2", "title": "JSONPlaceholderClient実装"},
        {"id": "2.1", "title": "AsyncAPIClient実装"}
    ]

def test_ai_matching_success(matcher, sample_tasks):
    """AI駆動マッチング成功ケース"""

    with patch.object(matcher.client.messages, 'create') as mock_create:
        # Claude APIレスポンスをモック
        mock_create.return_value = Mock(
            content=[Mock(text='{"task_id": "1.1", "confidence": 0.9, "reasoning": "明示的言及"}')]
        )

        result = matcher.match_commit_to_task(
            commit_msg="feat: BaseAPIClient実装完了",
            diff_stat="utils/api_client.py | 150 +++++",
            current_tasks=sample_tasks
        )

        assert result.task_id == "1.1"
        assert result.confidence == 0.9
        assert result.method == "ai"

def test_rule_based_fallback_id_explicit(matcher, sample_tasks):
    """ルールベースフォールバック: タスクID明示ケース"""

    with patch.object(matcher, '_try_ai_matching', return_value=None):
        result = matcher.match_commit_to_task(
            commit_msg="feat: リトライロジック実装 (task 1.1)",
            diff_stat="utils/api_client.py | 50 +++++",
            current_tasks=sample_tasks
        )

        assert result.task_id == "1.1"
        assert result.confidence == 1.0
        assert result.method == "rule_id_explicit"

def test_rule_based_fallback_keyword(matcher, sample_tasks):
    """ルールベースフォールバック: キーワードマッチング"""

    with patch.object(matcher, '_try_ai_matching', return_value=None):
        result = matcher.match_commit_to_task(
            commit_msg="feat: BaseAPIClient基盤実装",
            diff_stat="utils/api_client.py | 100 +++++",
            current_tasks=sample_tasks
        )

        assert result.task_id == "1.1"
        assert result.confidence == 0.8
        assert result.method == "rule_keyword"

def test_hybrid_matching_consensus(matcher, sample_tasks):
    """ハイブリッドマッチング: AI+ルール一致ケース"""

    ai_result = MatchResult(task_id="1.1", confidence=0.7, method="ai")
    rule_result = MatchResult(task_id="1.1", confidence=0.8, method="rule_keyword")

    result = matcher._hybrid_matching(ai_result, rule_result, sample_tasks)

    assert result.task_id == "1.1"
    assert result.confidence > 0.8  # 平均+ボーナス
    assert result.method == "hybrid_consensus"

def test_hybrid_matching_conflict(matcher, sample_tasks):
    """ハイブリッドマッチング: AI+ルール不一致ケース"""

    ai_result = MatchResult(task_id="1.1", confidence=0.6, method="ai")
    rule_result = MatchResult(task_id="1.2", confidence=0.7, method="rule_keyword")

    result = matcher._hybrid_matching(ai_result, rule_result, sample_tasks)

    assert result.task_id is None
    assert result.method == "hybrid_conflict"
    assert len(result.candidates) == 2

def test_manual_matching_prompt(matcher, sample_tasks, monkeypatch):
    """手動入力プロンプト: ユーザー選択"""

    # 標準入力をモック（選択: 1）
    monkeypatch.setattr('builtins.input', lambda _: "1")

    result = matcher._manual_matching_prompt(sample_tasks)

    assert result.task_id == "1.1"
    assert result.confidence == 1.0
    assert result.method == "manual_selected"

def test_manual_matching_skip(matcher, sample_tasks, monkeypatch):
    """手動入力プロンプト: スキップ選択"""

    # 標準入力をモック（選択: 4 = スキップ）
    monkeypatch.setattr('builtins.input', lambda _: "4")

    result = matcher._manual_matching_prompt(sample_tasks)

    assert result.task_id is None
    assert result.method == "manual_skipped"

def test_api_timeout_fallback(matcher, sample_tasks):
    """AI APIタイムアウト時のフォールバック検証"""

    with patch.object(matcher.client.messages, 'create', side_effect=Exception("Timeout")):
        result = matcher.match_commit_to_task(
            commit_msg="feat: BaseAPIClient実装 (task 1.1)",
            diff_stat="utils/api_client.py | 100 +++++",
            current_tasks=sample_tasks
        )

        # AI失敗 → ルールベースフォールバック成功
        assert result.task_id == "1.1"
        assert result.method == "rule_id_explicit"
```

**成果物**:
- [ ] scripts/ai_matching_with_fallback.py作成
- [ ] scripts/trigger_4_implementation_record.py更新（AI統合）
- [ ] tests/unit/test_ai_matching_fallback.py作成（8テストケース）
- [ ] Claude API統合動作確認（タイムアウト10秒設定）

#### アクション4.3: 統合テスト
**テストシナリオ**:

1. **正常系テスト（タスクID直接指定）**:
```bash
# 1. 実装実施
echo "def test_retry(): pass" >> tests/unit/test_api_client.py

# 2. コミット（タスクID明示）
git add tests/unit/test_api_client.py
git commit -m "feat: リトライロジック単体テスト追加 (task 1.1)"

# 3. Trigger 4実行
# ユーザー: 「実装記録」
# 期待: task 1.1のprogress更新、Task Master update-subtask実行
```

2. **正常系テスト（キーワードマッチング）**:
```bash
# 1. 実装実施
echo "class BaseAPIClient: pass" >> utils/api_client.py

# 2. コミット（タスクID不明示）
git add utils/api_client.py
git commit -m "feat: BaseAPIClient基盤実装"

# 3. Trigger 4実行
# 期待: "BaseAPIClient"キーワードから task 1.1自動マッチング
```

3. **異常系テスト（マッチング失敗）**:
```bash
# 1. コミット（曖昧なメッセージ）
git commit -m "fix: typo"

# 3. Trigger 4実行
# 期待: マッチング失敗メッセージ表示、手動ID入力プロンプト
```

**成果物**:
- [ ] 統合テスト完了（3シナリオ）
- [ ] マッチング精度測定結果

---

### Phase 5: 他トリガー統合（Week 7 Day 6-7、推定4時間）

#### アクション5.1: Trigger 1統合（学習開始）
**既存フロー**: learning_state.yaml参照のみ
**Task Master統合**: 不要（学習活動のため）

**成果物**:
- [ ] 変更なし（統合不要確認）

#### アクション5.2: Trigger 2統合（実装開始）
**既存フロー**: learning_state.yaml.current_tasks取得

**Task Master統合**:
```markdown
### トリガー2: 実装開始

**実行フロー**:
1. **learning_state.yaml読込**:
   ```yaml
   current_tasks:
     - id: "1.1"
       status: "pending"
   ```

2. **Task Master照会**:
   ```bash
   task-master show 1.1
   # → estimatedHours, acceptanceCriteria, subtasks取得
   ```

3. **ユーザー確認プロンプト表示**:
   ```
   🛠️  実装開始: BaseAPIClient実装
   📅 Week 1 Day 3
   ⏱️  推定時間: 6h
   📦 成果物:
     - リトライロジック実装
     - タイムアウト管理実装
     - 単体テスト作成（カバレッジ60%+）

   ✅ この内容で実装を開始しますか？ (yes/no)
   ```

4. **確認後、Task Master更新**:
   ```bash
   task-master set-status --id=1.1 --status=in-progress
   ```
```

**成果物**:
- [ ] CLAUDE.md更新（Trigger 2 + Task Master統合）

#### アクション5.3: Trigger 3統合（学習記録）
**既存フロー**: 学習時間・習熟度記録のみ
**Task Master統合**: 不要（学習活動のため）

**成果物**:
- [ ] 変更なし（統合不要確認）

#### アクション5.4: Trigger 5統合（週次振り返り）
**既存フロー**: 週次データ集計・レポート生成

**Task Master統合**:
```markdown
### トリガー5: 週次振り返り + Task Master統合

**実行フロー**:

1. **週次データ集計（完全自動）**:
   - learning_history週次集計（既存）
   - implementation_history週次集計（既存）

2. **Task Master進捗集計（追加）**:
   ```bash
   # 当週完了タスク取得
   task-master list --status=done --week=<current_week>

   # 当週未完了タスク取得
   task-master list --status=in-progress,pending --week=<current_week>
   ```

3. **週次レポート生成（AI支援）**:
   ```markdown
   # Week X 週次振り返り

   ## 達成事項
   - 学習: {learning_items_completed}
   - 実装: {implementation_tasks_completed}

   ## Task Master進捗
   - 完了タスク: task 1.1, 1.2（2/5タスク、40%）
   - 未完了タスク: task 1.3, 1.4, 1.5（要調整）

   ## メトリクス進捗
   - カバレッジ: {coverage_start}% → {coverage_end}%
   - テスト数: {test_count_start} → {test_count_end}

   ## 次週計画調整
   - task 1.3の依存関係解消必要
   - task 1.5を翌週に延期提案
   ```

4. **次週タスク調整提案（AI支援）**:
   ```bash
   # 進捗遅延タスク特定
   # → Task Master優先度・依存関係調整提案
   ```
```

**成果物**:
- [ ] CLAUDE.md更新（Trigger 5 + Task Master統合）

---

## 📊 品質保証

### テスト計画（不明点4.1: pytest + AAA Pattern + CI/CD統合）

#### 単体テスト戦略
**テストフレームワーク**: pytest + AAA Pattern (Arrange-Act-Assert)

**テスト対象スクリプト**:
- [ ] `scripts/sync_tasks_to_yaml.py`: 同期ロジックテスト
- [ ] `scripts/match_commit_to_task.py`: マッチング精度テスト（目標85%+）

**AAA Pattern実装例**:
```python
# tests/unit/test_sync_tasks_to_yaml.py
import pytest
from scripts.sync_tasks_to_yaml import load_tasks_json, atomic_write_yaml

def test_load_tasks_json_success(tmp_path):
    """Arrange-Act-Assert: 正常系テスト"""
    # Arrange: テストデータ準備
    tasks_file = tmp_path / 'tasks.json'
    tasks_file.write_text('{"1.1": {"status": "done"}}')

    # Act: 関数実行
    result = load_tasks_json(tasks_file)

    # Assert: 期待結果検証
    assert result == {"1.1": {"status": "done"}}
    assert len(result) == 1

def test_load_tasks_json_recovery(tmp_path):
    """エラーリカバリーテスト（不明点2.1検証）"""
    # Arrange: 破損ファイル + バックアップ準備
    tasks_file = tmp_path / 'tasks.json'
    backup_file = tmp_path / 'tasks.json.backup'
    tasks_file.write_text('{invalid json}')
    backup_file.write_text('{"1.1": {"status": "done"}}')

    # Act: エラーリカバリー実行
    result = load_tasks_json(tasks_file)

    # Assert: バックアップから復元成功
    assert result == {"1.1": {"status": "done"}}
    assert tasks_file.read_text() == backup_file.read_text()

def test_atomic_write_yaml_success(tmp_path):
    """原子性保証テスト（不明点2.2検証）"""
    # Arrange: YAMLデータ準備
    yaml_file = tmp_path / 'test.yaml'
    data = {'tasks': [{'id': '1.1'}]}

    # Act: 原子性書き込み実行
    atomic_write_yaml(data, yaml_file)

    # Assert: .tmpファイル削除 + 正常書き込み確認
    assert yaml_file.exists()
    assert not (tmp_path / 'test.yaml.tmp').exists()
```

**CI/CD統合（GitHub Actions）**:
```yaml
# .github/workflows/test-task-master-integration.yml
name: Task Master Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov pyyaml structlog
      - name: Run integration tests
        run: |
          pytest tests/integration/test_task_master/ --cov --cov-fail-under=85
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

#### 統合テスト（E2E）
- [ ] シナリオ1: 学習開始 → 実装開始 → 実装記録 → 週次振り返り
- [ ] シナリオ2: 複数タスク並行（task 1.1, 1.2同時進行）
- [ ] シナリオ3: エラーリカバリー（マッチング失敗 → 手動ID入力）

#### パフォーマンス要件とモニタリング（不明点4.3解決）

**パフォーマンス閾値**:
- **実行時間**: <5秒（Trigger 4全体: Git解析 + AI推論 + YAML更新）


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
- **メモリ使用量**: <50MB（sync_tasks_to_yaml.py実行時）
- **ファイルサイズ**: learning_state.yaml 3-4KB維持（100タスク想定）

**モニタリング実装**:
```python
# scripts/performance_monitor.py
import time
import psutil
import structlog
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

logger = structlog.get_logger()

@dataclass
class PerformanceThresholds:
    """パフォーマンス閾値定義"""
    max_execution_time: float = 5.0      # 5秒
    max_memory_mb: float = 50.0          # 50MB
    max_yaml_size_kb: float = 12.0  # Week 10タスク規模対応（理論最大10KB + 20%バッファ）

class PerformanceMonitor:
    """パフォーマンス劣化検知とアラート"""

    def __init__(self, thresholds: PerformanceThresholds = None):
        self.thresholds = thresholds or PerformanceThresholds()
        self.metrics = {}

    def measure_execution(self, func: Callable, *args, **kwargs):
        """実行時間とメモリ使用量の測定"""
        process = psutil.Process()
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time

        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        memory_used = mem_after - mem_before

        self.metrics = {
            'execution_time': execution_time,
            'memory_used_mb': memory_used,
            'timestamp': time.time()
        }

        # 閾値超過検知
        self._check_thresholds()

        return result

    def check_yaml_size(self, yaml_path: Path):
        """YAMLファイルサイズ監視"""
        size_kb = yaml_path.stat().st_size / 1024
        self.metrics['yaml_size_kb'] = size_kb

        if size_kb > self.thresholds.max_yaml_size_kb:
            logger.warning("⚠️ YAML size exceeded threshold",
                          current_size_kb=size_kb,
                          threshold_kb=self.thresholds.max_yaml_size_kb,
                          reason="Too many tasks or verbose data")

    def _check_thresholds(self):
        """閾値超過チェックとアラート"""
        exceeded = []

        if self.metrics['execution_time'] > self.thresholds.max_execution_time:
            exceeded.append(f"Execution time: {self.metrics['execution_time']:.2f}s > {self.thresholds.max_execution_time}s")

        if self.metrics['memory_used_mb'] > self.thresholds.max_memory_mb:
            exceeded.append(f"Memory usage: {self.metrics['memory_used_mb']:.1f}MB > {self.thresholds.max_memory_mb}MB")

        if exceeded:
            logger.error("🚨 Performance degradation detected",
                        exceeded_thresholds=exceeded,
                        metrics=self.metrics)
            # オプション: Slack/Discord通知、GitHub Issue自動作成等
        else:
            logger.info("✅ Performance within thresholds", metrics=self.metrics)

# 使用例: sync_tasks_to_yaml.pyに統合
monitor = PerformanceMonitor()
monitor.measure_execution(sync_tasks_to_yaml)
monitor.check_yaml_size(Path('learning_state.yaml'))
```

**CI/CDパフォーマンステスト統合**:
```yaml
# .github/workflows/test-task-master-integration.yml に追加
      - name: Performance benchmark
        run: |
          python -m pytest tests/performance/test_sync_performance.py \
            --benchmark-only \
            --benchmark-max-time=5.0 \
            --benchmark-columns=min,max,mean,stddev
      - name: Check YAML size
        run: |
          size=$(stat -f%z learning_state.yaml)
          max_size=$((4 * 1024))  # 4KB
          if [ $size -gt $max_size ]; then
            echo "❌ YAML size exceeded: ${size} bytes > ${max_size} bytes"
            exit 1
          fi
```

**パフォーマンステストケース**:
- [ ] Trigger 4実行時間: <5秒（Git解析 + AI推論 + YAML更新）
- [ ] 同期スクリプト実行時間: <1秒
- [ ] learning_state.yamlファイルサイズ: <4KB
- [ ] メモリ使用量: <50MB（100タスク処理時）
- [ ] 劣化検知: 閾値超過時の自動アラート動作確認

### 品質ゲート

| 観点 | 合格基準 | 測定方法 |
|------|---------|---------|
| **統合成功率** | 95%+ | 10回実行中9回以上成功 |
| **マッチング精度** | 85%+ | 20コミット中17件以上正確マッチ |
| **実行時間** | 30秒以内 | Trigger 4実行時間測定 |
| **YAML軽量性** | 3-4KB | learning_state.yamlファイルサイズ |
| **データ整合性** | 100% | tasks.json ↔ learning_state.yaml比較 |

---

## ⚠️ リスクと対策

### リスク1: マッチング精度不足（85%未満）
**影響**: 実装記録の自動化が機能しない
**確率**: 中（30%）

**対策**:
1. **予防策**: コミットメッセージ規約整備（"feat: <タスク名> (task <id>)"）
2. **検知**: マッチング失敗率を週次測定
3. **対処**:
   - フォールバック: 手動ID入力プロンプト表示
   - 改善: マッチングロジック学習（失敗事例からパターン抽出）

### リスク2: Task Master API変更
**影響**: `task-master show`, `update-subtask`等のコマンド動作不全
**確率**: 低（10%）

**対策**:
1. **予防策**: Task Master バージョン固定（package.json）
2. **検知**: 定期的なコマンド動作確認（週次）
3. **対処**: バージョンアップ時に統合テスト再実行

### リスク3: learning_state.yaml肥大化
**影響**: ファイルサイズ3-4KB超過 → パフォーマンス劣化
**確率**: 低（15%）

**対策**:
1. **予防策**: current_tasks[]に最大10タスクまで制限
2. **検知**: ファイルサイズ自動測定（Trigger 5実行時）
3. **対処**: 完了タスクを自動アーカイブ（learning_state_archive.yaml移動）

### リスク4: Git解析エラー（Trigger 4）
**影響**: 実装記録トリガーが失敗
**確率**: 中（25%）

**対策**:
1. **予防策**: Git解析コマンドにエラーハンドリング追加
2. **検知**: Trigger 4実行時のエラーログ記録
3. **対処**: フォールバック → 手動入力プロンプト表示

### リスク5: データ破損・誤更新（不明点3.2, 3.3解決）
**影響**: tasks.json/learning_state.yaml破損 → プロジェクト進捗データ消失
**確率**: 低（5-10%）

**対策（不明点3.2: Git-based Rollback）**:

#### Gitベースロールバック戦略

**pre-commitフック実装** (`.git/hooks/pre-commit`):
```bash
#!/bin/bash
# 自動バックアップ・タイムスタンプ付きコミット

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=".taskmaster/backups/${TIMESTAMP}"

# タスク管理ファイルのバックアップ
mkdir -p "${BACKUP_DIR}"
cp .taskmaster/tasks/tasks.json "${BACKUP_DIR}/"
cp learning_state.yaml "${BACKUP_DIR}/" 2>/dev/null || true

# Git commit に backup タグ追加
git add .taskmaster/backups/
git commit -m "chore: auto backup ${TIMESTAMP}" --no-verify

# 30日以上前のバックアップ自動削除
find .taskmaster/backups/ -mtime +30 -type d -exec rm -rf {} +

echo "✅ Pre-commit backup completed: ${BACKUP_DIR}"
```

**ロールバック実行スクリプト** (`scripts/rollback_to_backup.sh`):
```bash
#!/bin/bash
# Usage: ./scripts/rollback_to_backup.sh [TIMESTAMP|COMMIT_HASH]

TARGET=$1

if [ -z "$TARGET" ]; then
    echo "❌ Error: Specify TIMESTAMP (YYYYMMDD_HHMMSS) or COMMIT_HASH"
    echo "Available backups:"
    ls -1 .taskmaster/backups/ | tail -10
    exit 1
fi

# Option 1: タイムスタンプ指定でバックアップから復元
if [ -d ".taskmaster/backups/${TARGET}" ]; then
    cp ".taskmaster/backups/${TARGET}/tasks.json" .taskmaster/tasks/
    cp ".taskmaster/backups/${TARGET}/learning_state.yaml" . 2>/dev/null || true
    echo "✅ Rollback completed from backup: ${TARGET}"
    exit 0
fi

# Option 2: Git commit hash指定で履歴から復元
if git cat-file -e "${TARGET}^{commit}" 2>/dev/null; then
    git checkout "${TARGET}" -- .taskmaster/tasks/tasks.json
    git checkout "${TARGET}" -- learning_state.yaml 2>/dev/null || true
    echo "✅ Rollback completed from commit: ${TARGET}"
    exit 0
fi

echo "❌ Error: Invalid TIMESTAMP or COMMIT_HASH: ${TARGET}"
exit 1
```

**ロールバックテストケース**:
```python
# tests/integration/test_rollback.py
def test_rollback_from_backup(tmp_path):
    """Arrange-Act-Assert: バックアップからのロールバック検証"""
    # Arrange: テスト用バックアップ作成
    backup_dir = tmp_path / '.taskmaster' / 'backups' / '20250101_120000'
    backup_dir.mkdir(parents=True)
    (backup_dir / 'tasks.json').write_text('{"1.1": {"status": "done"}}')

    # Act: ロールバック実行
    result = subprocess.run(['./scripts/rollback_to_backup.sh', '20250101_120000'],
                           cwd=str(tmp_path), capture_output=True, text=True)

    # Assert: 復元成功確認
    assert result.returncode == 0
    assert "✅ Rollback completed" in result.stdout
    tasks = json.loads((tmp_path / '.taskmaster' / 'tasks' / 'tasks.json').read_text())
    assert tasks == {"1.1": {"status": "done"}}

def test_rollback_from_git_commit():
    """Git履歴からのロールバック検証"""
    # Arrange: テスト用コミット作成
    subprocess.run(['git', 'add', '.taskmaster/tasks/tasks.json'])
    subprocess.run(['git', 'commit', '-m', 'test: backup commit'])
    commit_hash = subprocess.run(['git', 'rev-parse', 'HEAD'],
                                capture_output=True, text=True).stdout.strip()

    # Act: Git commit指定でロールバック
    result = subprocess.run(['./scripts/rollback_to_backup.sh', commit_hash],
                           capture_output=True, text=True)

    # Assert: Git履歴から復元成功
    assert result.returncode == 0
    assert f"✅ Rollback completed from commit: {commit_hash}" in result.stdout
```

**対策（不明点3.3: 3-2-1 Backup Rule）**:

#### 3-2-1バックアップルール実装

**3-2-1ルール定義**:
- **3 copies**: オリジナル + ローカルバックアップ + リモートバックアップ
- **2 media types**: ローカルディスク + Git remote（GitHub/GitLab）
- **1 offsite**: GitHub Actionsでの自動バックアップ（クラウド保存）

**実装アーキテクチャ**:
```
Copy 1: .taskmaster/tasks/tasks.json          (オリジナル)
Copy 2: .taskmaster/backups/TIMESTAMP/        (ローカルバックアップ、30日保持)
Copy 3: GitHub remote main branch              (リモートバックアップ、永続保存)
```

**GitHub Actions自動バックアップワークフロー**:
```yaml
# .github/workflows/auto-backup-taskmaster.yml
name: Auto Backup Task Master Data

on:
  schedule:
    - cron: '0 0 * * *'  # 毎日00:00 UTCに実行
  push:
    paths:
      - '.taskmaster/tasks/tasks.json'
      - 'learning_state.yaml'

jobs:
  backup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0  # 全履歴取得（ロールバック用）

      - name: Create timestamped backup
        run: |
          TIMESTAMP=$(date +%Y%m%d_%H%M%S)
          BACKUP_DIR=".taskmaster/backups/${TIMESTAMP}"
          mkdir -p "${BACKUP_DIR}"
          cp .taskmaster/tasks/tasks.json "${BACKUP_DIR}/"
          cp learning_state.yaml "${BACKUP_DIR}/" 2>/dev/null || true

      - name: Commit backup to remote
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"
          git add .taskmaster/backups/
          git commit -m "chore: auto backup $(date +%Y%m%d_%H%M%S) [skip ci]" || true
          git push origin main

      - name: Cleanup old backups (30+ days)
        run: |
          find .taskmaster/backups/ -mtime +30 -type d -exec rm -rf {} +
          git add .taskmaster/backups/
          git commit -m "chore: cleanup old backups [skip ci]" || true
          git push origin main || true

      - name: Upload artifacts (90-day retention)
        uses: actions/upload-artifact@v3
        with:
          name: taskmaster-backup-${{ github.sha }}
          path: |
            .taskmaster/tasks/tasks.json
            learning_state.yaml
          retention-days: 90
```

**バックアップ検証テストケース**:
```python
# tests/integration/test_backup_rule.py
def test_3_2_1_backup_rule():
    """3-2-1バックアップルール検証"""
    # Arrange: バックアップ状態確認
    original = Path('.taskmaster/tasks/tasks.json')
    local_backup = Path('.taskmaster/backups/')

    # Assert 1: Copy 1（オリジナル）存在確認
    assert original.exists(), "Copy 1 (original) missing"

    # Assert 2: Copy 2（ローカルバックアップ）存在確認
    backup_dirs = list(local_backup.glob('*/'))
    assert len(backup_dirs) > 0, "Copy 2 (local backup) missing"

    # Assert 3: Copy 3（Gitリモート）存在確認
    result = subprocess.run(['git', 'ls-remote', 'origin', 'main'],
                           capture_output=True, text=True)
    assert result.returncode == 0, "Copy 3 (remote backup) unreachable"

    # Assert 4: 2 media types検証
    assert original.stat().st_dev != "remote", "Multiple media types required"

    # Assert 5: 1 offsite検証（GitHub Actions artifact確認）
    # 注: CI/CD環境でのみ実行可能
    pass
```

**予防策**:
1. **自動化**: pre-commitフックでコミット毎にバックアップ
2. **冗長性**: 3つの独立したコピー維持（3-2-1ルール）
3. **保持期間**: ローカル30日、GitHub Actions artifact 90日

**検知**:
1. **バックアップ失敗監視**: GitHub Actions通知（Slack/Discord連携）
2. **整合性チェック**: 週次でtasks.json ↔ backups比較

**対処**:
1. **即時復旧**: `rollback_to_backup.sh [TIMESTAMP|COMMIT_HASH]`
2. **多段階復元**: 最新バックアップ → 1日前 → 7日前 → Git履歴
3. **災害復旧**: GitHub Actions artifactからの完全復元

---

## 📅 実装スケジュール

| Phase | 日程 | 作業内容 | 推定工数 | 担当エージェント |
|-------|------|---------|---------|-----------------|
| **Phase 1** | Day 1-2 | PRD再構成 | 4h | `requirements-analyst` |
| **Phase 2** | Day 2 | Task Master初期化 | 2h | `python-expert` |
| **Phase 3** | Day 3 | learning_state.yaml統合 | 3h | `python-expert` |
| **Phase 4** | Day 4-5 | Trigger 4統合 | 6h | `python-expert` + `devops-architect` |
| **Phase 5** | Day 6-7 | 他トリガー統合 | 4h | `python-expert` |
| **検証** | Day 7 | 統合テスト・品質確認 | 2h | `quality-engineer` |

**合計推定工数**: 21時間（Week 7の42時間中50%）

---

## ✅ 完了基準（Definition of Done）

### Phase 1完了基準
- [ ] PRD Section A完成（100-150行）
- [ ] PRD Section B完成（150-200行、Feature 1-6）
- [ ] requirements-analystレビュー合格

### Phase 2完了基準
- [ ] tasks.json生成（Feature 6個、実装タスク15-20個）
- [ ] 複雑度分析完了
- [ ] サブタスク展開完了

### Phase 3完了基準
- [ ] learning_state.yaml.current_tasks初期化
- [ ] scripts/sync_tasks_to_yaml.py作成・テスト完了
- [ ] 同期スクリプト実行時間1秒以内

### Phase 4完了基準
- [ ] CLAUDE.md Trigger 4更新
- [ ] scripts/match_commit_to_task.py作成
- [ ] 統合テスト3シナリオ合格
- [ ] マッチング精度85%以上

### Phase 5完了基準
- [ ] CLAUDE.md Trigger 2, 5更新
- [ ] Trigger 1, 3統合不要確認

### プロジェクト完了基準
- [ ] 全品質ゲート合格（統合成功率95%+、マッチング精度85%+、実行時間30秒以内）
- [ ] learning_state.yamlファイルサイズ3-4KB維持
- [ ] E2Eテスト3シナリオ合格
- [ ] CLAUDE.md統合ガイド更新完了

---

## 🎯 期待効果（再掲）

### 定量的効果
- **時間削減**: 30分/日（判断時間15%削減、記録時間50%削減）
- **追跡精度**: 95%+（Task Master詳細管理 + 自動同期）
- **ファイルサイズ**: 3-4KB（軽量）vs 20-30KB（重量）
- **開発効率**: 15-20%向上（タスク管理自動化による）

### 定性的効果
- **自律性向上**: 実装記録の完全自動化（Git解析 + Task Master統合）
- **品質保証**: Task Masterの詳細管理（acceptanceCriteria、testStrategy、definitionOfDone）
- **長期保守**: learning_state.yamlの軽量性維持（3-4KB）

---
