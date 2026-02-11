# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2026年02月10日*

<!-- preserve-on-compact: CRITICAL RULES -->
<!-- IMPORTANT: These rules override all other instructions -->
## 🔴 CRITICAL RULES (MUST FOLLOW - 11項目)

**YOU MUST** follow these rules. Violations are NOT acceptable.

1. **ALWAYS** create a task list using `todowrite` before starting any work
2. **ALWAYS** use AskUserQuestion for 2+ distinct user choices
3. **NEVER** use `git commit` → **ALWAYS** use `/commit`
4. **NEVER** use `gh pr create` → **ALWAYS** use `/commit-push-pr`
5. **NEVER** use `gh issue create` → **ALWAYS** use `/create-issue`
6. **ALWAYS** pass quality gates before commit → @memory:implementation_quality_gates
7. **NEVER** push to protected branches (main/develop) directly
8. **ALWAYS** invoke `/xxx` skills via Skill tool when user requests
9. **ALWAYS** follow development workflow order → Section「🔄 開発ワークフロー」
10. **ALWAYS** re-read CLAUDE.md during reflexion → Section「🔄 reflexion使用時の必須チェック」
11. **ALWAYS** after completing all tasks in `todowrite`, Use Skill tool to run `/reflexion:reflect`

> For coding standards: @memory:coding_standards
> For quality gates: @memory:implementation_quality_gates

## プロジェクト概要

APIテスト + DevOps統合学習ポートフォリオ。時給4000-4500円レベルの技術力を証明するために設計されています。

**技術スタック**:

- Python 3.12
- httpx (Sync + Async HTTP client)
- pytest (累計100テスト作成目標、カバレッジ85%目標)
- Pydantic Settings (型安全な設定管理)
- structlog (構造化ログ)
- Docker (Multi-stage builds)
- docker-compose (4環境: dev/test/demo/prod)
- GitHub Actions (CI/CD自動化)

<!-- preserve-on-compact: Serena Memory System -->
## 📖 Serenaメモリシステムの使い方

**メモリ参照記法**: `@memory:メモリ名` → Claude Codeに「〜を確認」と依頼すると自動で `read_memory()` を実行

**主要メモリ**: `coding_standards`, `implementation_quality_gates`, `test_strategy`

**物理ファイル位置**: `.serena/memories/` 配下 | **登録済み**: 14個

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

**作業前の自動セットアップ**: `/using-git-worktrees` スキルが自動発動
- 発動条件: 機能実装開始時（Issue作成後、設計承認後）
- develop/mainへの直接作業: 禁止（Protected Branch設定）

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

**品質基準**: カバレッジ目標85%（現在: 83.32%）| 詳細: quality-gates.md

## 🔌 コマンド/スキル/プラグイン自動発動ルール

**詳細**: @memory:command_usage_guide

**種別の違い**:
- **Plugin**: `~/.claude/plugins/`にインストールされたもの
- **Command**: `~/.claude/commands/`に配置されたグローバルコマンド
- **Skill**: Skill toolに登録された組み込みスキル

### Critical（毎コミット必須）

| コマンド/スキル | 発動トリガー | 用途 |
|----------------|------------|------|
| `security-guidance` (hook) | Edit/Write時 | 自動警告（明示的呼出不要） |
| `/code-review:review-local-changes` | 品質ゲート全合格後 | 6並列エージェントレビュー（80点閾値） |

### High（開発標準）

| コマンド/スキル | 発動トリガー | 用途 |
|----------------|------------|------|
| `/create-issue` | Issue作成 | Issue駆動開発支援 |
| `/git:feature`, `/git:hotfix` | ブランチ操作時 | Git Flowブランチ管理 |
| `/commit`, `/commit-push-pr` | コミット/PR作成時 | 品質チェック付きコミット+日本語PR |
| `/pr-review-toolkit:review-pr` | git push完了後、PR作成前 | 6エージェント品質レビュー |
| `/code-review:review-pr` (CEK) | 重要PR時 | セキュリティ・バグ・API契約レビュー |
| `/test-coverage`, `/generate-tests` | テスト関連時 | カバレッジ分析・テスト生成 |

### Medium（必要時）

| コマンド/スキル | 発動トリガー | 用途 |
|----------------|------------|------|
| `/sc:document` | ドキュメント作成時 | コンポーネント/API/ガイド生成 |
| `/docs:update-docs` | 実装後ドキュメント更新時 | マルチエージェント品質レビュー |
| `/docs-maintenance` | ドキュメント品質監査時 | リンク検証・スタイル一貫性 |
| `/prompt-lookup`, `/skill-lookup` | 検索時 | テンプレート/スキル発見 |

<!-- preserve-on-compact: Development Workflow -->
## 🔄 開発ワークフロー（標準コマンド実行順序）

**CRITICAL**: `git commit`や`gh pr create`等の生コマンドは使用禁止。

```
【準備フェーズ】
1. Worktree作成 → /using-git-worktrees（常時※1）
   → ブランチ作成も含む

【実装フェーズ】
2. コード変更 → security-guidance (hook自動)
3. 品質ゲート → pytest + ruff + mypy 全合格（※2）
4. コミット前レビュー → /code-review:review-local-changes (80点閾値)
5. コミット   → /commit【git commit禁止】

【PR/マージフェーズ】
6. PR前レビュー → 規模判定ルール適用【※3参照】
7. PR作成     → /commit-push-pr【gh pr create禁止】
8. レビュー対応 → 修正 → 品質ゲート → /commit → push
9. マージ実行  → マージ戦略【※4参照】
10. クリーンアップ → /finishing-a-development-branch
```

<!-- preserve-on-compact: Quality Gates -->
**※1 worktree**: 並列Claude Code作業のため常時使用
**※2 品質ゲート**: `uv run pytest && uv run ruff check . && uv run mypy utils/ config/ models/`

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

## 🦸 superpowers使い分けルール

| ユースケース | 推奨 |
|-------------|------|
| 既知パターン・TDD・デバッグ | **superpowers** |
| 新規設計・複雑な要件定義 | **spec-workflow MCP** |
| **迷ったら** | **superpowers** |

**スキル発動**: 1%でも適用可能性があればAIが自動で呼び出します

詳細: @memory:command_usage_guide Section 6

## 🔄 reflexion使用時の必須チェック

**CRITICAL**: reflexion実行時（/reflexion:reflect, /reflexion:critique）は以下を必ず確認:

### 1. CLAUDE.md標準ルール参照

- [ ] **開発ワークフロー**（Section「🔄 開発ワークフロー」）
  - Issue駆動フロー: /create-issue → /issue → /using-git-worktrees の順序確認
  - プロジェクト固有コマンド使用（/commit, /commit-push-pr）
  - 生コマンド（git commit, gh pr create）使用禁止

- [ ] **コマンド/スキル/プラグイン自動発動ルール**（Section「🔌」）
  - Critical/High/Mediumの優先度確認
  - 発動条件の確認

- [ ] **コーディング規約**（@memory:coding_standards）
  - 命名規則、型ヒント、テスト規約の確認

- [ ] **品質ゲート**（@memory:implementation_quality_gates）
  - 4段階品質チェック（pytest/ruff/mypy/git）の確認

- [ ] **ワークフロー効率化ガイド**（.claude/rules/workflow/）
  - api-specification-check.md: API仕様事前確認プロセス
  - execution-efficiency.md: 3段階ワークフロー、並列実行判定

### 2. コンテキスト再確認（長時間セッション時）

- [ ] セッション時間2h+の場合、CLAUDE.md主要セクション再読込
- [ ] プロジェクト固有ルール > 一般的ベストプラクティス
- [ ] 「知っている ≠ 思い出す」を意識

### 3. 提案前の確認

- [ ] ワークフロー提案時: Section「🔄 開発ワークフロー」参照
- [ ] コマンド提案時: Section「🔌 コマンド/スキル/プラグイン自動発動ルール」参照
- [ ] コード提案時: coding_standards参照

**目的**: CLAUDE.md記載内容の「適用漏れ」防止

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


<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

*No recent activity*
</claude-mem-context>
