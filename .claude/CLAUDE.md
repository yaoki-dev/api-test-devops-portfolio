# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2026年03月02日*

<!-- preserve-on-compact: CRITICAL RULES -->
<!-- IMPORTANT: These rules override all other instructions -->
## 🔴 CRITICAL RULES (MUST FOLLOW - 16 RULES)

**YOU MUST** follow these rules. Violations are NOT acceptable.

1. **ALWAYS** respond in `Japanese` for all outputs, including skill usage
2. **ALWAYS** create a task list using `todowrite` before starting any work
3. **ALWAYS** use AskUserQuestion for 2+ distinct user choices
4. **NEVER** use `git commit` → **ALWAYS** use `/commit`
5. **NEVER** use `gh pr create` → **ALWAYS** use `/push-pr`
6. **NEVER** use `gh issue create` → **ALWAYS** use `/create-issue`
7. **ALWAYS** pass quality gates before commit → @memory:implementation_quality_gates
8. **NEVER** push to protected branches (main/develop) directly
9. **ALWAYS** invoke `/xxx` skills via Skill tool when user requests
10. **ALWAYS** follow development workflow order → Section「🔄 開発ワークフロー」
11. **ALWAYS** after completing all tasks in `todowrite`, Use Skill tool to run `/reflexion:reflect`
12. **ALWAYS** when 2+ independent tasks identified (after task classification, per RULES.md exception conditions) → invoke `superpowers:dispatching-parallel-agents` skill
    (reason: keep the main context window clean by leveraging subagents aggressively)
13. **ALWAYS** verify file content with Read/Grep tool BEFORE making any claim about line numbers, file structure, or code content
14. **ALWAYS** enforce worktree boundary:
    - At conversation start (including post-compact context reload): run `git rev-parse --show-toplevel`:
      - If command fails (non-zero exit code): **STOP immediately and report to user**
      - If output is empty: **STOP immediately and report to user**
      - Store non-empty result as **WORKTREE_ROOT** (immutable for this session; "non-empty" = contains at least one non-whitespace character after stripping trailing newlines; whitespace-only output is treated as empty)
    - Run `git worktree list` and check result:

      | `git worktree list` 結果 | 対応 |
      |--------------------------|------|
      | コマンド失敗（非ゼロ終了） | **STOP** + ユーザー報告 |
      | 空 / パース不可 | **STOP** + ユーザー報告 |
      | WORKTREE_ROOT 未含有 | **STOP** + ミスマッチ報告 |
      | 1エントリ | 「single-worktreeモード（WORKTREE_ROOT: {絶対パス}）」通知 + 続行 |
      | 2+エントリ | 「multi-worktreeモード」通知 → WORKTREE_ROOT確認 → **確認失敗時: STOP + ミスマッチ報告** / 確認成功時: ユーザーとスコープ確認 |

      > **評価順序（必須）**: テーブル行を上から順に評価すること（エントリ数チェックより先に WORKTREE_ROOT 含有確認を行う）: ①コマンド失敗 → STOP ②空/パース不可 → STOP ③ WORKTREE_ROOT 含有確認（含まれない場合はエントリ数に関わらず STOP + ミスマッチ報告） ④エントリ数確認（1 or 2+エントリ）
      > **WORKTREE_ROOT確認**: `git worktree list | cut -d' ' -f1 | grep -Fx "${WORKTREE_ROOT}"` (`-F`: literal string, `-x`: full-line match — prevents `/project` matching `/project-extra`; note: paths with spaces are not supported by this command)
      > **「パース不可」の定義**: 各行が `<absolute-path>` の形式を満たさない / 出力が空白のみ
      > **WORKTREE_ROOT未含有時のチェック**（ユーザー手動実行 — AI自動実行禁止）: `git rev-parse --is-inside-work-tree`（true → 正しいWORKTREE_ROOTをユーザーが再確認後にセッション再開 / false → 正しいプロジェクトディレクトリに移動後にセッション再開。⚠️ `git init` 実行禁止 — 既存リポジトリを破壊する危険がある）
      > **ミスマッチ報告時のAI報告内容（必須）**: ①`git rev-parse --show-toplevel` の実行結果（セッション開始時の保存値） ②`git worktree list` の生出力（全行） ③原因候補: シンボリックリンク解決差異 / CI/Docker環境でのパスマッピング差異

    - For files outside WORKTREE_ROOT:
      - Autonomous edit: **NEVER**
      - User-requested edit: **STOP**, show exact absolute path, require explicit confirmation before proceeding
      - Exception: `~/.claude/tasks/lessons.md` (Rule 15) and `~/.claude/tasks/todo.md` (RULES.md Task Management) are pre-authorized global files; boundary confirmation not required (Rule 15 write constraints still apply)
15. **ALWAYS** do both of the following with `~/.claude/tasks/lessons.md`:
    a) **At session start**: Read the file and review lessons tagged with the current project
       (file not found / ENOENT: silently ignore and continue, treat as no lessons;
        other errors (permissions, corruption, broken symlink): report to user, then continue)
    b) **After correction**: Update immediately when receiving ANY explicit correction or negative feedback
       - Detection signals: "that's wrong", "not X but Y", "fix this", "you misunderstood"
         (Japanese equivalents: 「違います」「〜ではなく〜です」「直してください」「誤解してる」)
       - Append format: `## [YYYY-MM-DD] [project-name] - Category`
         `**Situation**: what happened / **Root Cause**: why / **Rule**: what to do next time`
       - Global file — one file, append-only, cross-project lessons accumulate here
       - Write rule: Use Edit tool to append ONLY. NEVER use Write tool (overwrites entire file)
         **Exception (file absent)**: Use Write tool to create empty file first, then Edit to append (Write permitted for initial creation only); on append failure: report to user and output content in chat, then await explicit confirmation before continuing (silent continuation prohibited)
       - Cleanup: when entries exceed ~20 (no fixed monthly cadence)
       - Recurring pattern alert: If 2+ similar corrections appear for the same project (same Root Cause category), report to user for structural rule improvement
16. **ALWAYS** fix bugs autonomously (no hand-holding) when scope is within:
    - ❌ Confirmation required: `tests/**/conftest.py`, `scripts/*.py`, `models/responses.py`, `pyproject.toml`, `*.yml`/`.env*`, `config/`, `utils/sentry_init.py`/`utils/logger.py`/`utils/github_client.py`/`utils/api_client.py`, git ops / infra config
    - ✅ Autonomous fix OK: `tests/**/test_*.py`, 上記❌リスト以外の `*.py` ロジックエラー, pytest/ruff/mypy failures（ただし修正が❌リストファイルへの変更を要する場合はRule 3適用）
    - Boundary cases (e.g., adding pyproject.toml dependencies) → apply Rule 3 (AskUserQuestion)

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-4500円レベルの技術力を証明するために設計されています。

**技術スタック**:

- Python 3.13
- httpx (Sync + Async HTTP client)
- pytest (累計XXXテスト作成目標、カバレッジ85%目標)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker-compose (4環境: dev/test/demo/prod)
- GitHub Actions (CI/CD自動化)

<!-- preserve-on-compact: Serena Memory System -->
## 📖 Serenaメモリシステムの使い方

**メモリ参照記法**: `@memory:メモリ名` → Claude Codeに「〜を確認」と依頼すると自動で `read_memory()` を実行

**主要メモリ**:`implementation_quality_gates`, `test_strategy_details`

**物理ファイル位置**: `.serena/memories/` 配下 | **登録済み**: 26個

## 📚 学習・進捗管理

**進捗記録**: @docs/progress/daily_progress.md
**詳細フロー**: @memory:learning_triggers | **オフセットマップ**: @memory:learning_offset_maps

### リンター・フォーマッター

**詳細**: @memory:coding_standards Section 9「自動検証コマンド」

```bash
# 基本チェック（開発時）
uv run ruff check --fix .           # スタイル + 自動修正
uv run ruff format .                # フォーマット適用
uv run mypy utils/ config/ models/  # 型チェック

# セキュリティ（週次）
uv run bandit -r utils/ config/ models/
uv run safety check
```

### pre-commit（軽量版）

**セットアップ**: `uv run pre-commit install`
**戦略**: コミット時はruffのみ（3秒以内）、重いチェックはCI/CDで実行
**詳細**: @memory:coding_standards Section 9.4

### Markdown品質チェック

**ツール**: markdownlint + textlint + markdown-link-check
**設定**: `.markdownlint.json`, `.textlintrc`, `.textlintignore`
**CI**: PRごとに`md-quality`ジョブで自動実行、週次で`weekly-link-check`

```bash
npm run lint:md && npm run lint:text   # ローカル実行
```

## アーキテクチャ概要

**詳細**: @memory:project_file_structure

## 設定管理

**詳細**: @memory:coding_standards Section 11.2

Pydantic Settingsのネスト記法（`__`区切り）を使用:

```bash
ENVIRONMENT=development
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
LOG__LEVEL=DEBUG
SECURITY__API_KEY=your-secret-key
```

## Sentry統合（エラー監視）

**詳細**: @memory:sentry_integration
**概要**: ERROR以上のログを自動でSentryに送信。29種類の機密キーを自動スクラブ。
**開発時無効化推奨**: `SENTRY__ENABLED=false`（demo/prod環境のみ有効化）

## 重要な学習ポイント

**詳細**: @memory:coding_standards 各セクション参照

1. **非同期プログラミング**: `utils/api_client.py:399-762` - async/await、asyncio.gather()
2. **エラーハンドリング**: `api_client.py:24-57`, `132-219` - 階層的例外、リトライロジック
3. **テスト設計パターン**: `conftest.py:123-164`, `172-238` - fixtureスコープ、ファクトリーパターン
4. **設定管理**: `config/settings.py` - Pydantic Settings、SecretStr

## 開発時の注意事項

**基本規約**: @memory:coding_standards, @memory:implementation_quality_gates

<!-- preserve-on-compact: Git Flow -->
**Git運用** (Git Flow):

| ブランチ | 用途 | マージ戦略 |
|---------|------|-----------|
| `main` | 本番リリース | Regular Merge |
| `develop` | 開発統合 | Squash Merge (from feature) |
| `feature/*` | 機能開発 | → develop |
| `hotfix/*` | 緊急修正 | → main + develop |

**Conventional Commits**: `type(scope): subject` 形式

| type | 意味 | 例 |
|------|------|-----|
| feat | 新機能 | `feat(client): 認証ヘッダー自動付与` |
| fix | バグ修正 | `fix(client): タイムアウト処理修正` |
| docs | ドキュメント | `docs(readme): テスト手順追加` |
| test | テスト | `test(security): OWASP Top 10テスト` |
| refactor | 整理 | `refactor(config): Pydantic Settings移行` |
| chore | 設定変更 | `chore(docker): ベースイメージ更新` |
| perf | 性能改善 | `perf(client): コネクションプール導入` |
| ci | CI/CD | `ci(actions): 並列テスト実行` |
| security | セキュリティ | `security(config): SecretStr導入` |

**scope例**: api / client / config / docker / ci / test / docs / utils

**Git Flowコマンド**:
- `/git:feature <name>`: feature作成（developから分岐）
- `/git:hotfix <name>`: hotfix作成（mainから分岐）
- `/clean-gone`: [gone]ブランチクリーンアップ

**PRマージ後の推奨ワークフロー**:
```bash
gh pr merge <PR番号> --squash --delete-branch && \
git fetch --prune origin && \
git checkout -b feature/<次のタスク> origin/develop
```

## 📏 出力品質基準

**CRITICAL**: 全ての出力（計画、レポート、ドキュメント、コメント）に適用。

**根拠**: 業界標準（Google Developer Guide、JIS X 0121、日本TC協会）+ 実測データ（プロジェクト内簡潔文書）

### 文字数制限の明示的定義

| 表現 | 最大文字数 | 適用対象 | 根拠 |
|------|-----------|---------|------|
| **簡潔** | **600-900字** | 技術ドキュメント、計画書、レポート | Google Guide中央値 + TC協会標準 + 実測(quality-gates.md: 900字) |
| **詳細** | **1,500-3,000字** | アーキテクチャ設計、仕様書、ガイド | JIS X 0121（詳細） + Chicago Manual of Style（Brief） |
| **包括的** | **4,000-6,000字** | 最終レポート、完全なガイド、マニュアル | CLAUDE.md実測 + Chicago Article |

**検証方法**:
- 英語出力: `wc -w` で語数計測
- 日本語出力: `wc -m` で文字数計測

**毎セッション確認項目**:
- [ ] 「簡潔」出力は 600-900字に収まるか
- [ ] セッション初期化時に本基準を再読込

**詳細ガイド**: @memory:output_quality_standards（計画中）

**参考**: @memory:implementation_quality_gates, quality-gates.md

## 🔌 コマンド/スキル/プラグイン自動発動ルール

**詳細**: @memory:command_usage_guide

**ast-grep vs mgrep選択**:
- **コード変更時**: ast-grep必須（AST保証、リファクタリング◎）
- **文書構造探索時**: mgrep推奨（Markdown構造◎）
- **詳細な機能差**: @memory:command_usage_guide Section 9.3参照

**種別の違い**:
- **Plugin**: `~/.claude/plugins/`にインストールされたもの
- **Command**: `~/.claude/commands/`に配置されたグローバルコマンド
- **Skill**: Skill toolに登録された組み込みスキル

### Critical（毎コミット必須）

| コマンド/スキル | 発動トリガー | 用途 |
|----------------|------------|------|
| `security-guidance` (hook) | Edit/Write時 | 自動警告（明示的呼出不要） |
| `/reflexion:reflect` | 信頼度<90%時 | deep reflect実行（セルフレビュー） |
| `/code-review:review-local-changes` | 品質ゲート全合格後 | 6並列エージェントレビュー（80点閾値） |

### High（開発標準）

| コマンド/スキル | 発動トリガー | 用途 |
|----------------|------------|------|
| `/create-issue` | Issue作成 | Issue駆動開発支援 |
| `/git:feature`, `/git:hotfix` | ブランチ操作時 | Git Flowブランチ管理 |
| `/commit`, `/push-pr` | コミット/PR作成時 | 品質チェック付きコミット+日本語PR |
| `/code-review:review-pr` (CEK) | 重要PR時 | セキュリティ・バグ・API契約レビュー |
| `/pr-review-toolkit:review-pr` | git push完了後、PR作成前 | 6エージェント品質レビュー |
| `/test-coverage`, `/generate-tests` | テスト関連時 | カバレッジ分析・テスト生成 |

### Medium（必要時）

| コマンド/スキル | 発動トリガー | 用途 |
|----------------|------------|------|
| `/sc:document` | ドキュメント作成時 | コンポーネント/API/ガイド生成 |
| `/docs:update-docs` | 実装後ドキュメント更新時 | マルチエージェント品質レビュー |
| `/docs-maintenance` | ドキュメント品質監査時 | リンク検証・スタイル一貫性 |
| `/decision-helper` | 2+選択肢の比較評価時 | Pros/Cons・Decision Matrix・ICEフレームワーク |
| `/fact-checker` | 主張・データの事実確認時 | 証拠ベースのファクトチェック・情報信頼性評価 |
| `/prompt-lookup`, `/skill-lookup` | 検索時 | テンプレート/スキル発見 |

<!-- preserve-on-compact: Development Workflow -->
## 🔄 開発ワークフロー（標準コマンド実行順序）

**CRITICAL**: `git commit`や`gh pr create`等の生コマンドは使用禁止。

```
【準備フェーズ】
0. Reference lessons → Read ~/.claude/tasks/lessons.md and check lessons for the relevant project
   → 大規模タスク（複数セッション）: `.claude/rules/workflow/RULES.md` 「Task Management (Persistent Layer)」参照（todo.md活用）
1. Worktree作成 → /using-git-worktrees（常時※1）
   → ブランチ作成も含む

【実装フェーズ】
2. コード変更 → security-guidance (hook自動)
3. 品質ゲート → pytest + ruff + mypy 全合格（※2）
   → For non-trivial changes, ask: "Is there a more elegant implementation?"
   → If it feels hacky, ask: "Given what I know now, what's the most elegant approach?"
   → Skip for obvious single-line fixes
4. reflect(タスクごとに実施) → /reflexion:reflect "deep reflect if less than 90% confidence. 日本語で簡潔に回答" + 信頼度が90%未満であれば改善とreflectを反復する。
各反復で信頼度と改善理由を簡潔に示し、信頼度が90%以上に達した時点で終了する。
   reflexion時確認: コマンドルール（Section「🔌」のCritical/High/Medium優先度・発動条件）/ 2h+セッション時はCLAUDE.md主要セクション再読込
   "Would a staff engineer approve this?"（観点: 1責務/ネスト≤3段/命名の明確さ）
   → No: reflexion再実行。3回でもNoなら理由をユーザー報告 → 明示承認後のみ続行（承認スコープはそのタスク限定）
5. コミット前レビュー → /code-review:review-local-changes (80点閾値)
6. コミット   → /commit【git commit禁止】

【レビューフェーズ】
7. IF (≥200行 OR セキュリティ OR API OR hotfix):
      → /code-review:review-pr（CEK）
    ELSE(Include doc update):
      → /pr-review-toolkit:review-pr

【PUSH/PR/マージフェーズ】
8. PR前レビュー → 規模判定ルール適用【※3参照】
9. PR作成     → /push-pr【gh pr create禁止】
10. レビュー対応 → 修正 → 品質ゲート → /commit → push
11. マージ実行  → マージ戦略【※4参照】
12. クリーンアップ → Skill(superpowers:finishing-a-development-branch)
```

<!-- preserve-on-compact: Quality Gates -->
**※1 worktree**: 並列Claude Code作業のため常時使用
**※2 品質ゲート**: `uv run pytest -n auto -m "(unit or integration) and not external" --cov=utils --cov=config --cov=models --cov-report=term-missing &&
uv run ruff check . && uv run mypy utils/ config/ models/`

**※3 PR前レビュー規模判定**:

| 条件 | レビューツール |
|------|--------------|
| セキュリティファイル変更 OR ≥200行 OR API契約変更 | `/code-review:review-pr` (CEK) |
| <200行 AND 非セキュリティ | `/pr-review-toolkit:review-pr` |

セキュリティ関連: `utils/sentry_init.py`, `utils/logger.py`, `config/settings.py`, `*.env*`
API契約変更対象: `models/responses.py`, `utils/api_client.py` public methods

**※4 マージ戦略**:

| マージ種別 | コマンド |
|-----------|---------|
| feature → develop | `gh pr merge --squash --delete-branch` |
| develop → main | `gh pr merge --merge` |
| hotfix → main | `gh pr merge --merge` |

## トラブルシューティング

**詳細**: @memory:test_strategy_details トラブルシューティングFAQ参照

### テスト失敗時

```bash
uv run pytest -vv --tb=long          # 詳細ログ
uv run pytest -x                      # 最初の失敗で停止
uv run pytest tests/unit/test_async_client.py::test_name -vv --log-cli-level=DEBUG
```

### カバレッジ不足時

```bash
uv run pytest --cov-report=term-missing
uv run pytest --cov-report=html && open reports/htmlcov/index.html
```

### 型チェックエラー時

```bash
uv run mypy --show-error-codes --pretty utils/ config/ models/
```

### 複数回修正で解決しない場合

**3回以上の修正試行で解決しない場合**:
1. 公式ドキュメントを再確認（仕様変更/誤解の可能性）
2. GitHub Issuesで既知の問題を検索
3. 削除/代替案を検討（機能の必要性を再評価）

