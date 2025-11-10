# Task Master AI - Agent Integration Guide

## Essential Commands

### Core Workflow Commands

```bash
## プロジェクト初期化

# 現在のプロジェクトで Task Master を初期化
task-master init
# PRD ドキュメントからタスクを生成
task-master parse-prd .taskmaster/docs/prd.txt
# AI モデルを対話形式で設定
task-master models --setup

## 日次開発ワークフロー

# 全タスクのステータスを表示
task-master list
# 次の利用可能なタスクを取得
task-master next
# タスクの詳細情報を表示（例：task-master show 1.2）
task-master show <id>
# タスクを完了状態に設定
task-master set-status --id=<id> --status=done

## タスク管理

# AI 支援でタスクを追加
task-master add-task --prompt="description" --research
# タスクをサブタスクに分割
task-master expand --id=<id> --research --force
# 特定のタスクを更新
task-master update-task --id=<id> --prompt="changes"
# 指定 ID から複数タスクを更新
task-master update --from=<id> --prompt="changes"
# サブタスクに実装メモを追加
task-master update-subtask --id=<id> --prompt="notes"

## 分析・計画

# タスクの複雑さを分析
task-master analyze-complexity --research
# 複雑さ分析結果を表示
task-master complexity-report
# 対象外のタスクをすべて展開
task-master expand --all --research

## 依存関係と整理

# タスク依存関係を追加
task-master add-dependency --id=<id> --depends-on=<id>
# タスク階層を再編成
task-master move --from=<id> --to=<id>
# 依存関係の問題をチェック
task-master validate-dependencies
# タスク Markdown ファイルを更新（通常は自動実行）
task-master generate
```

## Key Files & Project Structure

### Core Files

- `.taskmaster/tasks/tasks.json` - メインのタスクデータファイル（自動管理）
- `.taskmaster/config.json` - AI モデル設定（`task-master models` で変更）
- `.taskmaster/docs/prd.txt` - PRD（Product Requirements Document）ドキュメント
- `.taskmaster/tasks/*.txt` - 個別タスクファイル（tasks.json から自動生成）
- `.env` - CLI 用 API キー

### Claude Code Integration Files

- `CLAUDE.md` - Claude Code 用自動読み込みコンテキスト（本ファイル）
- `.claude/settings.json` - Claude Code ツール許可リストと設定
- `.claude/commands/` - 繰り返しワークフロー用カスタムスラッシュコマンド
- `.mcp.json` - MCP サーバー設定（プロジェクト固有）

### Directory Structure

```
project/
├── .taskmaster/
│   ├── tasks/              # タスクファイルディレクトリ
│   │   ├── tasks.json      # メインタスクデータベース
│   │   ├── task-1.md      # 個別タスクファイル
│   │   └── task-2.md
│   ├── docs/              # ドキュメントディレクトリ
│   │   ├── prd.txt        # 要件定義書
│   ├── reports/           # 分析レポートディレクトリ
│   │   └── task-complexity-report.json
│   ├── templates/         # テンプレートファイル
│   │   └── example_prd.txt  # PRD サンプルテンプレート
│   └── config.json        # AI モデルと設定
├── .claude/
│   ├── settings.json      # Claude Code 設定
│   └── commands/         # カスタムスラッシュコマンド
├── .env                  # API キー
├── .mcp.json            # MCP 設定
└── CLAUDE.md            # 本ファイル - Claude Code で自動読み込み
```

## MCP Integration

Task Master は Claude Code が接続できる MCP サーバーを提供します。`.mcp.json` で設定してください：

```json
{
  "mcpServers": {
    "task-master-ai": {
      "command": "npx",
      "args": ["-y", "task-master-ai"],
      "env": {
        "ANTHROPIC_API_KEY": "your_key_here",
        "PERPLEXITY_API_KEY": "your_key_here",
        "OPENAI_API_KEY": "OPENAI_API_KEY_HERE",
        "GOOGLE_API_KEY": "GOOGLE_API_KEY_HERE",
        "XAI_API_KEY": "XAI_API_KEY_HERE",
        "OPENROUTER_API_KEY": "OPENROUTER_API_KEY_HERE",
        "MISTRAL_API_KEY": "MISTRAL_API_KEY_HERE",
        "AZURE_OPENAI_API_KEY": "AZURE_OPENAI_API_KEY_HERE",
        "OLLAMA_API_KEY": "OLLAMA_API_KEY_HERE"
      }
    }
  }
}
```

### Essential MCP Tools

```javascript
// 利用可能な Task Master コマンドを表示
help;

// プロジェクト初期化

// Task Master を初期化
initialize_project; // = task-master init
// PRD から解析
parse_prd; // = task-master parse-prd

// 日次ワークフロー

// タスク一覧取得
get_tasks; // = task-master list
// 次のタスク取得
next_task; // = task-master next
// タスク詳細表示
get_task; // = task-master show <id>
// ステータス設定
set_task_status; // = task-master set-status

// タスク管理

// タスク追加
add_task; // = task-master add-task
// タスク展開
expand_task; // = task-master expand
// タスク更新
update_task; // = task-master update-task
// サブタスク更新
update_subtask; // = task-master update-subtask
// 複数タスク更新
update; // = task-master update

// 分析

// プロジェクト複雑さ分析
analyze_project_complexity; // = task-master analyze-complexity
// 複雑さレポート表示
complexity_report; // = task-master complexity-report
```

## Claude Code Workflow Integration

### Standard Development Workflow

#### 1. Project Initialization

```bash
# Task Master を初期化
task-master init

# PRD を作成または取得してから解析
task-master parse-prd .taskmaster/docs/prd.txt

# 複雑さを分析してタスクを展開
task-master analyze-complexity --research
task-master expand --all --research
```

タスクがすでに存在する場合、別の PRD を解析できます（新規情報のみ！）。parse-prd に --append フラグを使用してください。これにより、生成されたタスクが既存のタスク一覧に追加されます。

#### 2. Daily Development Loop

```bash
# 各セッションを開始

# 次の利用可能なタスクを検索
task-master next
# タスク詳細を確認
task-master show <id>

# 実装中、コードコンテキストをタスクとサブタスクにチェックイン
task-master update-subtask --id=<id> --prompt="implementation notes..."

# タスクを完了
task-master set-status --id=<id> --status=done
```

#### 3. Multi-Claude Workflows

複雑なプロジェクトの場合は、複数の Claude Code セッションを使用してください：

```bash
# Terminal 1: メイン実装
cd project && claude

# Terminal 2: テストと検証
cd project-test-worktree && claude

# Terminal 3: ドキュメント更新
cd project-docs-worktree && claude
```

### Custom Slash Commands

`.claude/commands/taskmaster-next.md` を作成：

```markdown
次の利用可能な Task Master タスクを検索して、その詳細を表示します。

ステップ：

1. `task-master next` を実行して次のタスクを取得
2. タスクが利用可能な場合、`task-master show <id>` で完全な詳細を取得
3. 実装する必要があることの概要を提供
4. 最初の実装ステップを提案
```

`.claude/commands/taskmaster-complete.md` を作成：

```markdown
Task Master タスクを完了: $ARGUMENTS

ステップ：

1. `task-master show $ARGUMENTS` で現在のタスクをレビュー
2. すべての実装が完了していることを確認
3. このタスクに関連するテストを実行
4. 完了に設定: `task-master set-status --id=$ARGUMENTS --status=done`
5. `task-master next` で次の利用可能なタスクを表示
```

## Tool Allowlist Recommendations

`.claude/settings.json` に追加：

```json
{
  "allowedTools": [
    "Edit",
    "Bash(task-master *)",
    "Bash(git commit:*)",
    "Bash(git add:*)",
    "Bash(npm run *)",
    // Task Master MCP ツール許可
    "mcp__task_master_ai__*"
  ]
}
```

## Configuration & Setup

### API Keys Required

少なくとも **1 つ**の API キーを設定する必要があります：

- `ANTHROPIC_API_KEY` (Claude models) - **推奨**
- `PERPLEXITY_API_KEY` (Research features) - **強く推奨**
- `OPENAI_API_KEY` (GPT models)
- `GOOGLE_API_KEY` (Gemini models)
- `MISTRAL_API_KEY` (Mistral models)
- `OPENROUTER_API_KEY` (複数モデル)
- `XAI_API_KEY` (Grok models)

`models` コマンドで定義された3つのロールのいずれかで使用されるプロバイダーの API キーが必要です。

### Model Configuration

```bash
# 対話形式でセットアップ（推奨）
task-master models --setup

# 特定のモデルを設定

# メインモデルを設定
task-master models --set-main claude-3-5-sonnet-20241022
# リサーチモデルを設定
task-master models --set-research perplexity-llama-3.1-sonar-large-128k-online
# フォールバックモデルを設定
task-master models --set-fallback gpt-4o-mini
```

## Task Structure & IDs

### Task ID Format

- メインタスク: `1`, `2`, `3`, など
- サブタスク: `1.1`, `1.2`, `2.1`, など
- サブサブタスク: `1.1.1`, `1.1.2`, など

### Task Status Values

- `pending` - 作業準備完了
- `in-progress` - 現在作業中
- `done` - 完了・検証済み
- `deferred` - 延期
- `cancelled` - 不要
- `blocked` - 外部要因待機中

### Task Fields

```json
{
  "id": "1.2",
  "title": "ユーザー認証の実装",
  "description": "JWT ベースの認証システムをセットアップ",
  "status": "pending",
  "priority": "high",
  "dependencies": ["1.1"],
  "details": "ハッシング に bcrypt を使用、トークンに JWT を使用...",
  "testStrategy": "認証関数の単体テスト、ログインフローの統合テスト",
  "subtasks": []
}
```

## Claude Code Best Practices with Task Master

### Context Management

- フォーカスを保つため、異なるタスク間では `/clear` を使用
- 本 CLAUDE.md ファイルはコンテキストに自動読み込み
- 必要に応じて `task-master show <id>` で特定のタスクコンテキストを取得

### Iterative Implementation

1. `task-master show <subtask-id>` - 要件を理解
2. コードベースを探索して実装を計画
3. `task-master update-subtask --id=<id> --prompt="detailed plan"` - 計画をログ
4. `task-master set-status --id=<id> --status=in-progress` - 作業開始
5. ログに記録されている計画に従ってコードを実装
6. `task-master update-subtask --id=<id> --prompt="what worked/didn't work"` - 進捗をログ
7. `task-master set-status --id=<id> --status=done` - タスク完了

### Complex Workflows with Checklists

大規模な移行や複数ステップのプロセスの場合：

1. 新しい変更を説明する Markdown PRD ファイルを作成: `touch task-migration-checklist.md` (PRD は .txt または .md)
2. `task-master parse-prd --append` で新しい PRD を解析（MCP でも利用可能）
3. Taskmaster を使用して新しく生成されたタスクをサブタスクに展開。`analyze-complexity` で正しい --to と --from ID（新しい ID）を使用して、各タスクの理想的なサブタスク数を特定。その後展開します。
4. 項目を体系的に進め、完了したものをチェックオフ
5. 行き詰まった場合は、実装前/実装中に `task-master update-subtask` を使用して各タスク/サブタスクの進捗をログしたり、更新/調査したりします。

### Git Integration

Task Master は `gh` CLI で効果的に機能します：

```bash
# 完了したタスクの PR を作成
gh pr create --title "Complete task 1.2: User authentication" --body "Implements JWT auth system as specified in task 1.2"

# コミットでタスクを参照
git commit -m "feat: implement JWT auth (task 1.2)"
```

### Parallel Development with Git Worktrees

```bash
# 並列タスク開発用の worktree を作成
git worktree add ../project-auth feature/auth-system
git worktree add ../project-api feature/api-refactor

# 各 worktree で Claude Code を実行

# Terminal 1: 認証作業
cd ../project-auth && claude
# Terminal 2: API 作業
cd ../project-api && claude
```

## Troubleshooting

### AI Commands Failing

```bash
# API キーが設定されているか確認
# CLI 使用用
cat .env

# モデル設定を確認
task-master models

# 別のモデルでテスト
task-master models --set-fallback gpt-4o-mini
```

### MCP Connection Issues

- `.mcp.json` 設定を確認
- Node.js がインストールされていることを確認
- Claude Code 起動時に `--mcp-debug` フラグを使用
- MCP が利用できない場合は CLI をフォールバックとして使用

### Task File Sync Issues

```bash
# tasks.json からタスクファイルを再生成
task-master generate

# 依存関係の問題を修正
task-master fix-dependencies
```

再初期化しないでください。同じ Taskmaster コアファイルを再追加するだけで、それ以上のことはしません。

## Important Notes

### AI-Powered Operations

以下のコマンドは AI 呼び出しを実行し、最大 1 分かかることがあります：

- `parse_prd` / `task-master parse-prd`
- `analyze_project_complexity` / `task-master analyze-complexity`
- `expand_task` / `task-master expand`
- `expand_all` / `task-master expand --all`
- `add_task` / `task-master add-task`
- `update` / `task-master update`
- `update_task` / `task-master update-task`
- `update_subtask` / `task-master update-subtask`

### File Management

- `tasks.json` を手動で編集しないこと - コマンドを使用
- `.taskmaster/config.json` を手動で編集しないこと - `task-master models` を使用
- `tasks/` 内のタスク Markdown ファイルは自動生成
- tasks.json への手動変更後に `task-master generate` を実行

### Claude Code Session Management

- フォーカスを保つため、頻繁に `/clear` を使用
- 繰り返されるタスク Task Master ワークフロー用のカスタムスラッシュコマンドを作成
- ツール許可リストを設定してパーミッションを合理化
- オートメーション用のヘッドレスモード: `claude -p "task-master next"`

### Multi-Task Updates

- `update --from=<id>` を使用して複数の将来タスクを更新
- `update-task --id=<id>` を使用して単一タスク更新
- `update-subtask --id=<id>` を使用して実装ログ

### Research Mode

- リサーチベースの AI 強化のため `--research` フラグを追加
- 環境内に Perplexity (`PERPLEXITY_API_KEY`) のようなリサーチモデル API キーが必要
- より詳細なタスク作成と更新を提供
- 複雑な技術タスクに推奨

---

本ガイドにより、Claude Code は Task Master の必須機能にエージェント開発ワークフロー向けの即座にアクセスできることが保証されます。
