# Task Master CLI コマンド完全ガイド

*最終更新: 2025年10月30日*

このガイドは、Task Master AIを用いた開発ワークフローで使用するCLIコマンドの包括的リファレンスです。初心者から上級者まで、実用的なユースケースと具体的なコマンド例を交えて説明します。

---

## 目次

1. [はじめに](#はじめに)
2. [プロジェクト初期化](#プロジェクト初期化)
3. [日次開発ワークフロー](#日次開発ワークフロー)
4. [タスク管理](#タスク管理)
5. [分析・計画](#分析計画)
6. [依存関係管理](#依存関係管理)
7. [モデル設定](#モデル設定)
8. [フラグ・オプション一覧](#フラグオプション一覧)
9. [ユースケース別実践例](#ユースケース別実践例)
10. [トラブルシューティング](#トラブルシューティング)

---

## はじめに

### Task Master AIとは

Task Master AIは、PRD（Product Requirements Document）からタスクを自動生成し、開発ワークフローを効率化するためのAI駆動タスク管理ツールです。以下の特徴を持ちます：

- **AI支援のタスク生成**: PRDを解析し、実装可能な粒度のタスクに自動分解
- **依存関係の自動管理**: タスク間の依存関係を検証・修正
- **複雑度分析**: タスクの複雑度を評価し、サブタスクへの分割を支援
- **リサーチモード**: Perplexity AI統合により、技術調査を支援
- **CI/CD統合**: GitHub ActionsやClaudeCodeとのシームレスな統合

### 前提条件

- Node.js 18以上（推奨: 20 LTS）
- 少なくとも1つのAI APIキー（Anthropic Claude推奨）
- プロジェクトルートで実行

### インストール

Task MasterはCLIおよびMCPサーバーとして利用可能です。

```bash
# グローバルインストール（推奨）
npm install -g task-master-ai

# npx経由で実行（インストール不要）
npx task-master-ai init
```

---

## プロジェクト初期化

### 1. プロジェクトの初期化

プロジェクトルートでTask Masterを初期化します。

```bash
task-master init
```

**実行結果**:
- `.taskmaster/` ディレクトリ作成
- `tasks.json` 初期化
- `config.json` テンプレート生成

### 2. AIモデルの設定

対話形式でAIモデルを設定します（初回必須）。

```bash
task-master models --setup
```

**設定項目**:
1. **Main Model**: メインタスク処理用（推奨: `claude-3-5-sonnet-20241022`）
2. **Research Model**: リサーチ機能用（推奨: `perplexity-llama-3.1-sonar-large-128k-online`）
3. **Fallback Model**: フォールバック用（推奨: `gpt-4o-mini`）

**モデル個別設定**:

```bash
# メインモデル設定
task-master models --set-main claude-3-5-sonnet-20241022

# リサーチモデル設定
task-master models --set-research perplexity-llama-3.1-sonar-large-128k-online

# フォールバックモデル設定
task-master models --set-fallback gpt-4o-mini
```

### 3. PRD解析・タスク生成

PRDファイルを解析し、タスクを自動生成します。

```bash
# PRD解析（新規プロジェクト）
task-master parse-prd .taskmaster/docs/prd.txt

# PRD解析（既存タスクに追加）
task-master parse-prd .taskmaster/docs/new_prd.txt --append
```

**オプション**:
- `--append`: 既存タスクリストに追加（新規情報のみ）
- `--num-tasks=10`: 生成するタスク数（デフォルト: 10）

**注意**: `--append`なしで実行すると、既存のタスクが上書きされます。

---

## 日次開発ワークフロー

### 1. タスク一覧の確認

すべてのタスクを一覧表示します。

```bash
task-master list
```

**出力例**:
```
Task ID | Status      | Priority | Title
--------|-------------|----------|------
1       | pending     | high     | Week 8: Regression Testing
1.1     | pending     | high     | Regression Test Suite
1.1.1   | pending     | high     | Docker Volume Permission Tests
```

**フィルタリングオプション**:

```bash
# ステータス別
task-master list --status=pending
task-master list --status=in-progress
task-master list --status=done

# サブタスク含む
task-master list --with-subtasks
```

### 2. 次のタスクを取得

依存関係に基づき、次に実施すべきタスクを提案します。

```bash
task-master next
```

**出力例**:
```
Next available task: 1.1.1 - Docker Volume Permission Tests
Dependencies: None
Priority: high
Status: pending
```

### 3. タスク詳細の表示

特定タスクの詳細情報を表示します。

```bash
task-master show <id>

# 例
task-master show 1.1.1
```

**出力例**:
```
Task ID: 1.1.1
Title: Docker Volume Permission Regression Tests
Description: Create tests for Week 7 Docker volume mount issues
Status: pending
Priority: high
Dependencies: []

Details:
Test volume mount scenarios: read-only volumes, permission denied errors,
volume binding variations. Include both sync and async client scenarios.

Test Strategy:
Integration tests with docker-compose, mock filesystem errors,
validate error messages
```

### 4. タスクステータスの更新

タスクの状態を更新します。

```bash
task-master set-status --id=<id> --status=<status>

# 例
task-master set-status --id=1.1.1 --status=in-progress
task-master set-status --id=1.1.1 --status=done
```

**ステータス値**:
- `pending`: 作業準備完了
- `in-progress`: 現在作業中
- `done`: 完了・検証済み
- `deferred`: 延期
- `cancelled`: 不要
- `blocked`: 外部要因待機中

**複数タスク一括更新**:

```bash
# カンマ区切りで複数ID指定
task-master set-status --id=1.1,1.2,1.3 --status=done
```

**重要な挙動**:
- 親タスクを`done`にすると、すべてのサブタスクも自動的に`done`になります
- サブタスクがすべて`done`になっても、親タスクは自動的に`done`にはなりません（手動更新必要）

---

## タスク管理

### 1. タスクの追加

新規タスクをAI支援で追加します。

```bash
task-master add-task --prompt="description" --research

# 例
task-master add-task --prompt="Add Prometheus metrics endpoint" --research
```

**オプション**:
- `--research`: Perplexity AIによる技術調査を有効化
- `--priority=<high|medium|low>`: 優先度指定（デフォルト: medium）

### 2. タスクの展開（サブタスク生成）

タスクをサブタスクに分割します。

```bash
task-master expand --id=<id> --research --force

# 例
task-master expand --id=1.1 --research
```

**オプション**:
- `--research`: リサーチモードでより詳細なサブタスク生成
- `--force`: 既存サブタスクを削除して再生成
- `--all`: すべての未展開タスクを一括展開

**すべてのタスクを展開**:

```bash
task-master expand --all --research
```

**注意**: `--force`を指定すると、既存のサブタスクが削除されます。実装メモがある場合は注意してください。

### 3. タスクの更新

特定タスクをAI支援で更新します。

```bash
task-master update-task --id=<id> --prompt="changes"

# 例
task-master update-task --id=1.2 --prompt="Add HMAC-SHA512 support in addition to SHA256"
```

**複数タスクの一括更新**:

```bash
# 指定IDから後続のタスクすべてを更新
task-master update --from=<id> --prompt="changes"

# 例
task-master update --from=2 --prompt="Update all Phase 2 tasks to use new monitoring framework"
```

**用途の違い**:
- `update-task`: 単一タスクの更新（詳細変更）
- `update`: 複数タスクの一括更新（全体方針変更）

### 4. サブタスクの更新（実装メモ追加）

サブタスクに実装メモを追加します（上書きではなく追記方式）。

```bash
task-master update-subtask --id=<id> --prompt="notes"

# 例
task-master update-subtask --id=1.1.1 --prompt="Implemented volume mount tests. Found edge case: permission denied errors need special handling for Windows systems."
```

**重要な挙動**:
- `update-subtask`は**追記方式**です（既存内容は保持）
- 実装中のメモや気づきを記録する用途に最適
- 既存内容を完全に書き換える場合は`update-task`を使用

### 5. サブタスクの削除

特定タスクのサブタスクをすべて削除します。

```bash
task-master clear-subtasks --id=<id>

# 例
task-master clear-subtasks --id=1.1
```

**注意**: この操作は取り消せません。実装メモがある場合はバックアップを推奨します。

---

## 分析・計画

### 1. 複雑度分析

プロジェクト全体のタスク複雑度を分析します。

```bash
task-master analyze-complexity --research
```

**出力例**:
```
Analyzing task complexity...

Task 1.1: Complexity Score 8/10
  Recommended: Expand into 5-7 subtasks
  Reason: High technical complexity, multiple integration points

Task 1.2: Complexity Score 4/10
  Recommended: Keep as single task
  Reason: Straightforward implementation, single responsibility

Task 2.1: Complexity Score 9/10
  Recommended: Expand into 7-10 subtasks
  Reason: Critical path, requires extensive testing
```

**オプション**:
- `--research`: リサーチモードで精度向上
- `--threshold=6`: 複雑度閾値（1-10、この値以上のタスクを展開推奨）

### 2. 複雑度レポート表示

分析結果を確認します。

```bash
task-master complexity-report
```

**出力場所**: `.taskmaster/reports/task-complexity-report.json`

**レポート構造**:
```json
{
  "projectComplexity": 7.2,
  "tasksAnalyzed": 15,
  "expandRecommendations": [
    {
      "taskId": "1.1",
      "complexityScore": 8,
      "recommendedSubtasks": "5-7",
      "reason": "High technical complexity..."
    }
  ]
}
```

---

## 依存関係管理

### 1. 依存関係の追加

タスク間の依存関係を設定します。

```bash
task-master add-dependency --id=<id> --depends-on=<id>

# 例
task-master add-dependency --id=1.2 --depends-on=1.1
```

**用途**:
- タスク実施順序の制約
- 前提タスクの明示化

### 2. 依存関係の検証

依存関係の整合性をチェックします。

```bash
task-master validate-dependencies
```

**チェック項目**:
- 循環依存の検出
- 存在しないタスクIDへの依存
- 依存関係の一貫性

**出力例（問題あり）**:
```
⚠️  Dependency Issues Found:

1. Circular dependency: 1.1 → 1.2 → 1.1
2. Missing task: Task 1.5 depends on non-existent task 3.1
```

### 3. 依存関係の自動修正

依存関係の問題を自動修正します。

```bash
task-master fix-dependencies
```

**修正内容**:
- 循環依存の解消
- 存在しないタスクIDへの依存を削除
- 無効な依存関係の削除

**注意**: 自動修正後は`validate-dependencies`で再確認してください。

### 4. タスク階層の再編成

タスクを別の親タスク配下に移動します。

```bash
task-master move --from=<id> --to=<id>

# 例
task-master move --from=1.3 --to=2
```

**用途**:
- タスク構造の再編成
- Phase間の移動

---

## モデル設定

### 1. モデル設定の確認

現在のAIモデル設定を表示します。

```bash
task-master models
```

**出力例**:
```
Main Model: claude-3-5-sonnet-20241022 (Anthropic)
Research Model: perplexity-llama-3.1-sonar-large-128k-online (Perplexity)
Fallback Model: gpt-4o-mini (OpenAI)
```

### 2. 対話形式設定

対話形式でモデルを設定します（推奨）。

```bash
task-master models --setup
```

### 3. 個別モデル設定

特定のロール用モデルを設定します。

```bash
# メインモデル設定
task-master models --set-main <model-id>

# リサーチモデル設定
task-master models --set-research <model-id>

# フォールバックモデル設定
task-master models --set-fallback <model-id>
```

**主要モデルID**:

| プロバイダー | モデルID | 用途 |
|------------|---------|------|
| Anthropic | `claude-3-5-sonnet-20241022` | メイン（推奨） |
| Anthropic | `claude-3-opus-20240229` | リサーチ |
| Perplexity | `perplexity-llama-3.1-sonar-large-128k-online` | リサーチ（推奨） |
| OpenAI | `gpt-4o-mini` | フォールバック |
| Google | `gemini-1.5-pro` | 代替メイン |

---

## フラグ・オプション一覧

### グローバルオプション

| フラグ | 説明 | デフォルト値 | 例 |
|-------|------|------------|-----|
| `--research` | リサーチモード有効化（Perplexity AI） | 無効 | `--research` |
| `--force` | 強制実行（既存データ上書き） | 無効 | `--force` |
| `--id=<id>` | タスクID指定（複数指定可） | なし | `--id=1.1` または `--id=1,2,3` |
| `--status=<status>` | ステータス指定 | なし | `--status=done` |
| `--priority=<priority>` | 優先度指定 | `medium` | `--priority=high` |
| `--prompt="<text>"` | AI用プロンプト指定 | なし | `--prompt="Add tests"` |

### コマンド別オプション

| コマンド | 利用可能オプション |
|---------|------------------|
| `parse-prd` | `--append`, `--num-tasks` |
| `list` | `--status`, `--with-subtasks` |
| `expand` | `--id`, `--all`, `--research`, `--force` |
| `set-status` | `--id`, `--status` |
| `add-task` | `--prompt`, `--research`, `--priority` |
| `update-task` | `--id`, `--prompt`, `--research` |
| `update-subtask` | `--id`, `--prompt` |
| `update` | `--from`, `--prompt`, `--research` |
| `analyze-complexity` | `--research`, `--threshold` |
| `add-dependency` | `--id`, `--depends-on` |
| `move` | `--from`, `--to` |

---

## ユースケース別実践例

### ユースケース1: プロジェクト初期化フロー

**状況**: 新規プロジェクトでTask Masterを導入

```bash
# Step 1: 初期化
task-master init

# Step 2: AIモデル設定
task-master models --setup

# Step 3: PRD作成（エディタで作成）
# ファイル: .taskmaster/docs/prd.txt

# Step 4: PRD解析・タスク生成
task-master parse-prd .taskmaster/docs/prd.txt

# Step 5: 複雑度分析
task-master analyze-complexity --research

# Step 6: 複雑なタスクをサブタスクに展開
task-master expand --all --research

# Step 7: 依存関係検証
task-master validate-dependencies

# Step 8: 次のタスク確認
task-master next
```

**期待される結果**:
- タスク一覧が生成される
- 複雑度分析レポートが作成される
- サブタスクが適切に展開される
- 次のタスクが提示される

---

### ユースケース2: 日次タスク進捗確認フロー

**状況**: 毎日の開発開始時・終了時

```bash
# 朝の開始時

# Step 1: 次のタスク確認
task-master next

# Step 2: タスク詳細確認
task-master show 1.1.1

# Step 3: 作業開始
task-master set-status --id=1.1.1 --status=in-progress

# 実装中（実装メモ追加）

# Step 4: 進捗メモ追加
task-master update-subtask --id=1.1.1 --prompt="Implemented volume mount tests. Found Windows permission issue requiring investigation."

# 夕方の終了時

# Step 5: タスク完了
task-master set-status --id=1.1.1 --status=done

# Step 6: 明日のタスク確認
task-master next
```

**Tips**:
- `update-subtask`は頻繁に使用して実装メモを残す習慣をつける
- 作業途中でもメモを追加（翌日の引き継ぎがスムーズに）

---

### ユースケース3: タスク複雑度分析・展開フロー

**状況**: 複雑なタスクを適切なサブタスクに分割したい

```bash
# Step 1: 複雑度分析（リサーチモード）
task-master analyze-complexity --research

# Step 2: レポート確認
task-master complexity-report

# Step 3: 複雑度が高いタスクを確認
# レポートから複雑度8以上のタスクIDをメモ

# Step 4: 特定タスクを展開（例: タスク1.1）
task-master expand --id=1.1 --research

# Step 5: 展開結果確認
task-master show 1.1

# Step 6: サブタスク一覧確認
task-master list --with-subtasks

# Step 7: 依存関係検証
task-master validate-dependencies
```

**複雑度分析の活用**:
- 複雑度6以上: サブタスク展開推奨
- 複雑度8以上: 詳細なサブタスク（7-10個）推奨
- 複雑度4以下: 単一タスクのまま実施

---

### ユースケース4: 依存関係管理フロー

**状況**: タスクの実施順序を管理したい

```bash
# Step 1: 依存関係追加
task-master add-dependency --id=1.2 --depends-on=1.1
task-master add-dependency --id=2.1 --depends-on=1

# Step 2: 依存関係検証
task-master validate-dependencies

# Step 3: 問題が検出された場合は自動修正
task-master fix-dependencies

# Step 4: 再検証
task-master validate-dependencies

# Step 5: 次のタスク確認（依存関係を考慮）
task-master next
```

**よくある依存関係パターン**:
- **順次実装**: 1.1 → 1.2 → 1.3
- **Phase依存**: Phase 2タスクはPhase 1完了後
- **並行実施**: 依存関係なしのタスクは並行作業可能

---

### ユースケース5: 追加PRD統合フロー

**状況**: プロジェクト途中で新しい要件が追加された

```bash
# Step 1: 新PRD作成
# ファイル: .taskmaster/docs/new_requirements.txt

# Step 2: PRD解析（追加モード）
task-master parse-prd .taskmaster/docs/new_requirements.txt --append

# Step 3: 新タスク確認
task-master list

# Step 4: 新タスクの複雑度分析
task-master analyze-complexity --research

# Step 5: 新タスクのみ展開（IDを指定）
task-master expand --id=5 --research
task-master expand --id=6 --research

# Step 6: 依存関係追加（既存タスクとの関連）
task-master add-dependency --id=5.1 --depends-on=2.3

# Step 7: 依存関係検証
task-master validate-dependencies
```

**注意点**:
- `--append`を指定しないと既存タスクが上書きされる
- 新タスクと既存タスクの依存関係を明示する

---

### ユースケース6: 大規模リファクタリング計画

**状況**: 複数タスクを一括更新したい

```bash
# Step 1: 対象タスク確認
task-master list

# Step 2: 特定タスク以降を一括更新
task-master update --from=3 --prompt="Update all Phase 3 tasks to use new authentication system (JWT → OAuth2)"

# Step 3: 更新結果確認
task-master show 3
task-master show 4
task-master show 5

# Step 4: 複雑度再分析
task-master analyze-complexity --research

# Step 5: 必要に応じてサブタスク再展開
task-master expand --id=3 --research --force
```

**用途**:
- アーキテクチャ変更時の一括更新
- 技術スタック変更時の方針統一
- 要件変更時の複数タスク調整

---

## トラブルシューティング

### エラー1: AI APIキーエラー

**症状**:
```
Error: Missing API key for provider 'anthropic'
Required environment variable: ANTHROPIC_API_KEY
```

**原因**: APIキーが設定されていない

**解決方法**:

```bash
# .envファイル作成
cat > .env << EOF
ANTHROPIC_API_KEY=your_key_here
PERPLEXITY_API_KEY=your_key_here
EOF

# 環境変数確認
cat .env

# モデル設定確認
task-master models
```

**環境変数の設定場所**:
1. `.env`ファイル（プロジェクトルート）
2. `.mcp.json`（MCP統合時）
3. システム環境変数

---

### エラー2: タスクファイル同期エラー

**症状**:
```
Error: Task file out of sync
tasks.json has been modified manually
```

**原因**: `tasks.json`を手動編集した

**解決方法**:

```bash
# タスクファイル再生成
task-master generate

# 依存関係修正
task-master fix-dependencies

# 検証
task-master validate-dependencies
```

**予防策**:
- `tasks.json`を直接編集しない
- すべての変更はCLIコマンド経由で実施

---

### エラー3: 循環依存エラー

**症状**:
```
⚠️  Circular dependency detected: 1.1 → 1.2 → 1.1
```

**原因**: タスクAがタスクBに依存し、タスクBがタスクAに依存

**解決方法**:

```bash
# Step 1: 依存関係確認
task-master validate-dependencies

# Step 2: 自動修正試行
task-master fix-dependencies

# Step 3: 手動で依存関係再設定
# タスク詳細確認
task-master show 1.1
task-master show 1.2

# 不要な依存関係を削除（tasks.jsonを直接編集せず、再構築）
# 正しい依存関係を追加
task-master add-dependency --id=1.2 --depends-on=1.1

# Step 4: 再検証
task-master validate-dependencies
```

---

### エラー4: リサーチモードエラー

**症状**:
```
Error: Research mode requires PERPLEXITY_API_KEY
```

**原因**: Perplexity APIキーが未設定

**解決方法**:

```bash
# Option 1: Perplexity APIキー取得・設定
echo "PERPLEXITY_API_KEY=your_key_here" >> .env

# Option 2: リサーチモードなしで実行
task-master expand --id=1.1
task-master analyze-complexity
```

**Perplexity APIキー取得方法**:
1. https://www.perplexity.ai/ にアクセス
2. アカウント作成
3. API Keysセクションで生成

---

### エラー5: タスク展開失敗

**症状**:
```
Error: Failed to expand task 1.1
AI model request timeout
```

**原因**: AIモデルのレスポンス遅延またはネットワークエラー

**解決方法**:

```bash
# Step 1: ネットワーク確認
ping api.anthropic.com

# Step 2: 別のモデルでリトライ
task-master models --set-fallback gpt-4o-mini
task-master expand --id=1.1

# Step 3: タイムアウト後に再実行
task-master expand --id=1.1 --research
```

**予防策**:
- 安定したネットワーク環境で実行
- フォールバックモデルを設定

---

### エラー6: MCP接続エラー

**症状**:
```
Error: MCP server connection failed
Failed to connect to task-master-ai MCP server
```

**原因**: MCP設定の問題またはNode.jsバージョン不一致

**解決方法**:

```bash
# Step 1: Node.jsバージョン確認
node --version
# 期待値: v18以上

# Step 2: .mcp.json設定確認
cat .mcp.json

# Step 3: MCP再起動（Claude Codeの場合）
# Claude Codeを再起動

# Step 4: デバッグモード実行
claude --mcp-debug

# Step 5: MCPが利用できない場合はCLI使用
task-master next
task-master show 1.1
```

---

### よくある質問（FAQ）

**Q1: タスク更新とサブタスク更新の違いは？**

A: 以下の違いがあります：

| コマンド | 用途 | 更新方式 |
|---------|------|---------|
| `update-task` | タスク全体の内容変更 | 上書き |
| `update-subtask` | 実装メモの追加 | 追記 |

**Q2: --forceフラグはいつ使う？**

A: 以下のケースで使用します：
- サブタスクを完全に作り直したい
- 既存のサブタスクが不適切
- タスク構造を大幅に変更

**注意**: 実装メモが失われるため、必ずバックアップしてください。

**Q3: リサーチモードの効果は？**

A: 以下の効果があります：
- より詳細なタスク生成
- 技術的な調査結果の反映
- ベストプラクティスの提案

実行時間が長くなりますが、品質が向上します。

**Q4: 親タスク完了時のサブタスク挙動は？**

A: 親タスクを`done`にすると、すべてのサブタスクも自動的に`done`になります。逆にサブタスクがすべて完了しても、親タスクは自動的に完了しません（手動設定必要）。

**Q5: タスクファイルの手動編集は推奨される？**

A: **推奨されません**。以下の理由があります：
- 依存関係の整合性が崩れる可能性
- ファイル同期エラーの原因
- 自動生成ファイルの上書きリスク

すべての変更はCLIコマンド経由で実施してください。

---

## まとめ

### 推奨ワークフロー

**初期化フェーズ**:
1. `task-master init` - プロジェクト初期化
2. `task-master models --setup` - AIモデル設定
3. `task-master parse-prd` - PRD解析
4. `task-master analyze-complexity --research` - 複雑度分析
5. `task-master expand --all --research` - タスク展開

**日次開発フェーズ**:
1. `task-master next` - 次のタスク確認
2. `task-master show <id>` - タスク詳細確認
3. `task-master set-status --status=in-progress` - 作業開始
4. `task-master update-subtask` - 実装メモ追加
5. `task-master set-status --status=done` - タスク完了

**計画変更フェーズ**:
1. `task-master parse-prd --append` - 追加PRD統合
2. `task-master update --from=<id>` - 複数タスク一括更新
3. `task-master validate-dependencies` - 依存関係検証

### 重要な注意点

- **AI呼び出しは時間がかかる**: 最大1分程度待つことがある
- **tasks.jsonは手動編集しない**: すべてCLI経由で変更
- **リサーチモードは高品質**: 実行時間は長いが推奨
- **依存関係は定期検証**: `validate-dependencies`を定期実行
- **サブタスク更新は追記方式**: 実装メモは累積される

### さらなる学習リソース

- **公式ドキュメント**: `.taskmaster/CLAUDE.md`
- **サンプルPRD**: `.taskmaster/templates/example_prd.txt`
- **複雑度レポート**: `.taskmaster/reports/task-complexity-report.json`

---

**このガイドは、Task Master AIの実践的な使用方法を網羅しています。不明点がある場合は、まず`task-master <command> --help`で詳細情報を確認してください。**
