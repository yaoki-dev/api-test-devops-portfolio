# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

*最終更新: 2026年01月28日*

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

## 📖 Serenaメモリシステムの使い方

このプロジェクトではSerena MCPのメモリ機能を活用し、プロジェクト知識を効率的に管理しています。

**メモリ参照記法**: `@memory:メモリ名`

- 例: `@memory:coding_standards` → コーディング規約を参照
- Claude Codeに「〜を確認」と依頼すると、自動で `read_memory()` を実行

**登録済みメモリ**: `list_memories()` で確認（現在14個）

**主要メモリ**: `coding_standards`, `implementation_quality_gates`, `test_strategy`

**物理ファイル位置**: `.serena/memories/` 配下

## 📚 学習・進捗管理

**進捗記録**: @docs/progress/daily_progress.md

**詳細フロー**: @memory:learning_triggers
**オフセットマップ**: @memory:learning_offset_maps

## 🚀 学習・実装記録自動化トリガー

**検出キーワード**: `学習開始`, `実装開始`, `学習記録`, `実装記録`, `週次振り返り`, `理解度確認`, `エラー記録`

**詳細フロー**: @memory:learning_triggers
**オフセットマップ**: @memory:learning_offset_maps

### 🤖 AI協働学習フロー仕組み

**詳細**: @memory:ai_collaboration_workflow

**概要**: 新技術習得のための3フェーズ学習方法論

- **Phase 1**: AI説明・概念理解（目標理解度80%）
- **Phase 2**: AI協働実装（目標理解度60%）
- **Phase 3**: 理解度確認・記録（目標理解度80%+）

**関連**: 実装品質ゲート、AI協働12原則（原則1・2・4）との整合性、トリガー6との連携

### リンター・フォーマッター

**詳細**: @memory:coding_standards Section 9「自動検証コマンド」

**クイックリファレンス**:

```bash
# 基本チェック（開発時）
uv run ruff check --fix .      # スタイル + 自動修正
uv run ruff format .            # フォーマット適用
uv run mypy utils/ config/ models/  # 型チェック

# セキュリティ（週次）
uv run bandit -r utils/ config/ models/ # 脆弱性スキャン
uv run safety check             # 依存関係チェック
```

### pre-commit（軽量版）

**詳細**: @memory:coding_standards Section 9.4、@memory:implementation_quality_gates

**セットアップ**: `uv run pre-commit install` （初回のみ）

**戦略**: コミット時はruffのみ（3秒以内）、重いチェック（mypy, bandit, pytest）はCI/CDで実行

**理由**: 開発体験優先（個人開発最適化）。詳細なトレードオフ分析は@memory参照

### Markdown品質チェック

**ツール**: markdownlint + textlint（日本語対応）+ markdown-link-check（週次）

**設定ファイル**:

- `.markdownlint.json`: 23ルール無効化+1ルール部分許可（既存ドキュメント互換）
- `.textlintrc`: preset-ja-technical-writing設定
- `.textlintignore`: archive/, obsidian-vault等除外
- `.markdown-link-check.json`: Rate limit対応、@memory:パターン除外

**ルール無効化の理由**:

| カテゴリ | 無効化ルール | 理由 |
|---------|-------------|------|
| **日本語互換** | MD013（行長） | 日本語は文字密度が高く80文字制限が厳しすぎる |
| **プロジェクト慣習** | MD024（重複見出し）, MD025（複数H1） | 進捗ログで同名セクションを許容 |
| **コード例** | MD040（言語指定なしコードブロック） | 出力例・ログで言語不要なケースあり |
| **HTML許容** | MD033（インラインHTML） | details/summary/kbd等を許容 |
| **textlint** | no-unmatched-pair, no-exclamation-question-mark, ja-no-weak-phrase, ja-no-mixed-period, ja-unnatural-alphabet | コード例との競合、学習教材での表現許容のため |

**ローカル実行**:

```bash
# 依存インストール（初回のみ）
npm ci

# npm scripts使用（推奨）
npm run lint:md       # Markdownリント
npm run lint:md:fix   # 自動修正
npm run lint:text     # textlint
npm run lint:text:fix # textlint自動修正
npm run lint:links    # リンクチェック（README.md）
npm run lint:all      # md + text 一括実行

# npx直接実行（従来方式）
npx markdownlint '**/*.md' --ignore node_modules --ignore .venv --ignore .worktrees
npx textlint '**/*.md' --ignore-path .textlintignore
```

**CI**: PRごとに`md-quality`ジョブで自動実行（5分以内）、週次で`weekly-link-check`実行

**DRY同期確認**: CI除外パスと.textlintignoreの同期確認コマンド
```bash
# .textlintignoreのパターン数（コメント・空行除外）
grep -v '^#' .textlintignore | grep -c '.'  # 期待: 14-15パターン

# ci.ymlの各findセクションの除外パターン数（2箇所あるため個別確認）
grep -A 20 "Find Markdown files" .github/workflows/ci.yml | grep -c "\-not -path"  # 期待: 14
grep -A 35 "Run markdown-link-check" .github/workflows/ci.yml | grep -c "\-not -path"  # 期待: 14
```

## アーキテクチャ概要

**詳細**: @memory:project_file_structure

## 設定管理

### 環境変数設定（`.env`）

Pydantic Settingsのネスト記法（`__`区切り）を使用:

```bash
# 環境設定
ENVIRONMENT=development      # development|testing|staging|production
DEBUG=true

# API設定
API__BASE_URL=https://jsonplaceholder.typicode.com
API__TIMEOUT=30
API__RETRY_COUNT=3
API__RETRY_DELAY=1.0
API__MAX_CONNECTIONS=10

# ログ設定
LOG__LEVEL=DEBUG            # DEBUG|INFO|WARNING|ERROR|CRITICAL
LOG__FORMAT=console         # console|json
LOG__FILE=/var/log/app/api-test.log

# テスト設定
TEST__EXTERNAL_API_ENABLED=true
TEST__PERFORMANCE_TEST_ENABLED=false

# セキュリティ設定
SECURITY__API_KEY=your-secret-key
SECURITY__RATE_LIMIT_REQUESTS=100
```

## Sentry統合（エラー監視）

**詳細**: @memory:sentry_integration

**概要**: Sentry SDKを統合し、ERROR以上のログを自動でSentryに送信。29種類の機密キーを自動スクラブ。

**コアモジュール**: `utils/sentry_init.py`, `utils/logger.py`, `config/settings.py`

**開発時無効化推奨**: 学習・開発段階では`SENTRY__ENABLED=false`（demo/prod環境のみ有効化）

## 重要な学習ポイント

### 1. 非同期プログラミング

- `async/await`パターンの実装（`utils/api_client.py:399-762`）
- `asyncio.gather()`による並行処理（`api_client.py:741-761`）
- 非同期コンテキストマネージャー（`__aenter__/__aexit__`）

### 2. エラーハンドリング戦略

- 階層的な例外設計（`api_client.py:24-57`）
- HTTPステータスコード別処理（4xx即失敗、5xxリトライ）
- リトライロジック実装（`api_client.py:132-219`）

### 3. テスト設計パターン

- pytest fixtureスコープの使い分け（session/module/function）
- ファクトリーパターンによるテストデータ生成（`conftest.py:172-238`）
- モック・スタブの活用（`conftest.py:123-164`）
- パフォーマンステスト（`conftest.py:246-274`）

### 4. 設定管理ベストプラクティス

- Pydantic Settingsによる型安全な設定（`config/settings.py`）
- 環境変数の自動読み込み・バリデーション
- `SecretStr`によるシークレット保護（`settings.py:142-155`）

## 開発時の注意事項

**基本規約**: @memory:coding_standards, @memory:implementation_quality_gates

**作業前の自動セットアップ**: `/superpowers:using-git-worktrees` スキルが自動発動

- 発動条件: 機能実装開始時（Issue作成後、設計承認後、実装フェーズ移行時）
- 自動処理: `origin/develop`から新ブランチ作成　+ worktree設定（.worktrees/）
- develop/mainへの直接作業: 禁止（Protected Branch設定）
- ユーザー操作: 不要（自動実行）

**Git運用** (Git Flow):

- `main`: 本番リリース用（タグ付きリリースのみ）
- `develop`: 開発統合ブランチ（次期リリース準備）main へマージ
  - 理由: Protected branchには直接pushできないため、ローカル更新は不要
  - `git fetch` + 新ブランチ作成により、常に最新のリモート状態から作業開始
- `feature/*`: 機能開発 → develop へPR・Squash Merge
- `hotfix/*`: 緊急修正 → main + develop へマージ
- **コミットメッセージ** (Conventional Commits準拠):

| プレフィクス | 意味（実務での使われ方） | プロジェクト実例 |
|-------------|------------------------|----------------|
| **feat:** | 新機能追加 | `feat(client): GitHub API認証ヘッダー自動付与機能追加` |
| **fix:** | バグ修正 | `fix(client): リトライロジックのタイムアウト処理修正` |
| **docs:** | ドキュメント変更 | `docs(readme): テスト実行手順を追加` |
| **test:** | テスト追加・変更 | `test(security): OWASP API Security Top 10テスト追加` |
| **refactor:** | 挙動を変えないコード整理 | `refactor(config): 環境変数管理をPydantic Settingsに移行` |
| **chore:** | 依存更新、設定変更 | `chore(docker): Multi-stage buildsのベースイメージ更新` |
| **perf:** | パフォーマンス改善 | `perf(client): コネクションプール導入で応答時間30%短縮` |
| **ci:** | CI/CD設定変更 | `ci(actions): 並列テスト実行でCI時間50%短縮` |
| **security:** | セキュリティ修正 | `security(config): SecretStrによるAPI_KEY平文出力防止` |

  **推奨形式**: `type(scope): subject`（例: `feat(auth): JWT認証実装`）

  **スコープ例**: api / client / config / docker / ci / test / docs / utils

  **破壊的変更**: `feat(api)!: レスポンス形式変更` + Footer: `BREAKING CHANGE: 詳細`

  **Issue参照**: Footer: `Closes #123` / `Refs #456`

**Git Flowコマンド（Serena MCP統合版）**:

- `/feature <name>`: feature作成（developから分岐）
- `/hotfix <name>`: hotfix作成（mainから分岐）
- `/flow-status`: 状態確認
- `/clean-gone`: [gone]ブランチクリーンアップ（worktree対応）

**Serena MCP統合の利点**:

- リアルタイムガイダンス: 14個のメモリ（coding_standards、test_strategy等）に即アクセス
- 品質保証: implementation_quality_gatesを参照しながらcommit実行
- 効率性: 必要なメモリのみ読込（CLAUDE.md全体読込より効率的）

**Git削除の伝播（重要な学び）**:

- ⚠️ `git rm`による削除は**削除diff**として扱われる
- develop→mainマージ時、削除diffは自動適用される
- 両ブランチに存在するファイルの場合、developでの削除がmainにも反映される
- 例外: mainにしか存在しないファイル（developの履歴にない）は手動削除が必要

**ブランチ衛生管理**:

- バックアップディレクトリの代わりにGit履歴を使用
- 廃止ファイルはdevelopでクリーンアップ → mainへ自動伝播
- プロジェクトワークフロー: develop→main直接マージ（releaseブランチ不使用）

> **発見日**: 2025-12-09（58ファイルクリーンアップ実施時）

**Git Flow + Protected Branch での Squash Merge 注意点**:

- ⚠️ **同期 PR に Squash Merge を使用してはいけない**
  - 履歴が分断され、次回の逆方向 PR でコンフリクトが発生する
- ✅ **同期 PR は必ず Regular Merge を使用**
  - 履歴統合が維持され、双方向の PR が円滑に実行できる

| シナリオ | 推奨マージ方式 |
|---------|--------------|
| feature → develop | Squash Merge ✅ |
| develop → main (リリース) | Regular Merge ✅ |
| hotfix → main | Regular Merge ✅ |
| hotfix → develop | Regular Merge ✅ |

**単方向フロー（2026-01-19 変更）**:

- main→develop の自動同期は廃止（ping-pong 問題回避のため）
- hotfix 適用後は手動で develop への cherry-pick を検討

**PR Validation テスト戦略**:

- develop PR: unit + integration（カバレッジ計測）→ smoke（カバレッジなし）
- main PR: unit + integration（カバレッジ計測）→ smoke（カバレッジなし）

**PRマージ後の推奨ワークフロー**:

```bash
# ✅ 推奨（3ステップ・コンフリクトゼロ）
gh pr merge <PR番号> --squash --delete-branch && \
git fetch --prune origin && \
git checkout -b feature/<次のタスク> origin/develop
```

```bash
# ❌ 非推奨（コンフリクトリスク）
git checkout develop
git pull origin develop  # ← Protected Branchで不要
```

**理由**: ローカルdevelopへのpushは禁止（上記参照）。`origin/develop`から直接分岐が効率的。

> **発見日**: 2026-01-11（PR #57 マージ作業時）

**品質基準**:

- カバレッジ目標: Week 7-10でPhase別に設定（最終目標85%）

## 🔌 コマンド/スキル/プラグイン自動発動ルール

AIが自動的に適切なコマンド・スキル・プラグインを発動するためのルール。詳細（パッケージ情報・完全な発動トリガー一覧）は`@memory:command_usage_guide`を参照。

**種別の違い**:
- **Plugin**: `~/.claude/plugins/`にインストールされたもの（例: `pr-review-toolkit@claude-code-plugins`）
- **Command**: `~/.claude/commands/`に配置されたグローバルコマンド（`.md`ファイル）
- **Skill**: Skill toolに登録された組み込みスキル

### Critical（毎コミット必須）

| コマンド/スキル | 種別 | 発動トリガー | 用途 |
|----------------|------|------------|------|
| `security-guidance` (hook) | Plugin | Edit/Write/MultiEdit時 | 自動警告（明示的呼出不要） |
| `/code-review:code-review` | Plugin | 品質ゲート全合格後（※1） | 4並列エージェントレビュー（80点閾値） |

### High（開発標準）

| コマンド/スキル | 種別 | 発動トリガー | 用途 |
|----------------|------|------------|------|
| `/create-issue`, `/issue` | Command | Issue作成/参照時 | Issue駆動開発支援 |
| `/feature`, `/hotfix` | Command | ブランチ操作時 | Git Flowブランチ管理 |
| `/commit`, `/commit-push-pr` | Command | コミット/PR作成時 | 品質チェック付きコミット+日本語PR |
| `/pr-review-toolkit:review-pr` | Plugin | git push完了後、PR作成前 | 6エージェント品質レビュー |
| `/code-review:review-pr` (CEK) | Plugin | 重要PR時 | 6エージェント防御レビュー（セキュリティ・バグ・API契約） |
| `/comprehensive-pr-review` | Command | リリース前PR | 10エージェント統合レビュー |
| `/test-coverage`, `/generate-tests` | Command | テスト関連時 | カバレッジ分析・テスト生成 |

### Medium（必要時）

| コマンド/スキル | 種別 | 発動トリガー | 用途 |
|----------------|------|------------|------|
| `/sc:document` | Command | 新規ドキュメント作成時 | コンポーネント/API/ガイド生成 |
| `/docs:update-docs` | Plugin | 実装後ドキュメント更新時 | Git連携+マルチエージェント品質レビュー |
| `/docs-maintenance` | Command | ドキュメント品質監査時 | リンク検証・スタイル一貫性・自動同期 |
| `/troubleshooting-guide` | Command | トラブルシューティング時 | 診断手順・共通問題・自動解決 |
| `/prompt-lookup` | Skill | プロンプト検索時 | プロンプトテンプレート発見・改善 |
| `/skill-lookup` | Skill | スキル検索時 | 再利用可能なAI機能発見・インストール |
| `/senior-devops` | Skill | DevOps包括作業時 | CI/CD、IaC、コンテナ、クラウド統合 |
| `/make-it-pretty` | Command | 週次/スプリント境界 | 全体リファクタリング |

**※6 Issue-PR自動紐付け（2026-01-25 追加）:**

`/commit-push-pr` スキルは以下を自動実行:
1. ブランチ名からIssue番号を抽出（`feature/issue-XXX-...` パターン）
2. PRテンプレートに `Closes #XXX` を自動挿入
3. PR作成後、該当IssueにPR参照コメントを自動追加

**エラーハンドリング**: 詳細は `~/.claude/commands/commit-push-pr.md` 270-464行参照

`/feature` スキルのブランチ命名規則:
- Issue対応時: `issue-<番号>-<説明>` 形式を**強制**（バリデーション失敗 → エラー表示 → 作成中断）
- Issue対応以外: 従来通り自由形式（kebab-case推奨）

## 🔄 開発ワークフロー（標準コマンド実行順序）

**CRITICAL**: 以下のコマンドを**この順序で**実行すること。`git commit`や`gh pr create`等の生コマンドは使用禁止。

```
【Issue駆動フェーズ】
0. Issue作成   → /create-issue【新規タスク時】
1. Issue参照   → /issue <番号>（要件整理・実装戦略）
2. Worktree作成 → /superpowers:using-git-worktrees（常時※3）
   → ブランチ作成も含む

【実装フェーズ】
3. コード変更 → security-guidance (hook自動)
4. 品質ゲート → pytest + ruff + mypy 全合格（※1）
5. 自己改善  → /reflexion:reflect
6. コード簡素化 → /pr-review-toolkit:review-pr simplify【条件付き※2】
7. レビュー実行 → 規模判定ルール適用【※4参照】

【PR/マージフェーズ】
8. コミット   → /commit (90点閾値、日本語)【git commit禁止】
9. PR作成         → /commit-push-pr【gh pr create禁止】
10. レビュー対応   → 【ループ: 修正要求あれば】
    - 修正 → 品質ゲート → /commit → push
11. マージ実行     → マージ戦略【※5参照】
12. マージ完了
13. クリーンアップ → /superpowers:finishing-a-development-branch
```

**※1 品質ゲート**: `uv run pytest && uv run ruff check . && uv run mypy utils/ config/ models/`
**※2 simplify条件**: 長時間セッション(2h+)または複雑ロジック実装時のみ
**※3 worktree**: 並列Claude Code作業のため常時使用（worktreeディレクトリ作成→新ブランチチェックアウト→cd移動。元リポジトリのHEADは不変）
**※4 レビュー規模判定ルール（導入日: 2026-01-15）:**

**判定順序（優先度順）:**

1. **セキュリティ優先チェック（行数無視）**
   セキュリティ関連ファイル変更あり → `/reflexion:critique` 必須

   セキュリティ関連: `utils/sentry_init.py`, `utils/logger.py`, `config/settings.py`, `*.env*`

2. **行数ベース判定（非セキュリティ）**

   ```bash
   DIFF_STAT=$(git diff --stat)
   LINES=$(echo "$DIFF_STAT" | tail -1 | awk '{gsub(/[^0-9]/, " "); print $2+$3}')
   ```

   | 変更行数 | レビュースキル |
   |---------|--------------|
   | <100行 | `/superpowers:requesting-code-review` |
   | 100-200行 | `/code-review:code-review (80点閾値)` |
   | ≥200行 | `/code-review:code-review (80点閾値)` → `/reflexion:critique` |

3. **ファイル数チェック**
   ファイル変更≥3 → `/reflexion:critique` 追加

   **組み合わせ例**:

   | 行数 | 1-2ファイル | ≥3ファイル |
   |------|------------|-----------|
   | <100行 | `/superpowers:requesting-code-review` | `/superpowers:requesting-code-review`+ `/reflexion:critique` |
   | 100-200行 | `code-review:code-review` | `code-review:code-review` + `/reflexion:critique` |
   | ≥200行 | `/code-review:code-review` + `/reflexion:critique` | `/code-review:code-review` + `/reflexion:critique` |

**※5 マージ戦略（Protected Branch対応）:**

| マージ種別 | コマンド |
|-----------|---------|
| feature → develop | `gh pr merge --squash --delete-branch` |
| develop → main | `gh pr merge --merge` |
| hotfix → main | `gh pr merge --merge` |

## 🦸 superpowers使い分けルール

**導入日**: 2025-12-28 | **バージョン**: 4.0.3

| ユースケース | 推奨 |
|-------------|------|
| 既知パターン・TDD・デバッグ | **superpowers** |
| 新規設計・複雑な要件定義 | **spec-workflow MCP** |
| **迷ったら** | **superpowers** |

**スキル発動**: 1%でも適用可能性があればAIが自動で呼び出します

詳細（コマンド・スキル一覧）: @memory:command_usage_guide Section 6

## 🔄 reflexion使用時の必須チェック

**CRITICAL**: reflexion実行時（/reflexion:reflect, /reflexion:critique）は以下を必ず確認:

### 1. CLAUDE.md標準ルール参照

- [ ] **開発ワークフロー**（Section「🔄 開発ワークフロー」）
  - Issue駆動フロー: /create-issue → /issue →  /superpowers:using-git-worktrees の順序確認
  - プロジェクト固有コマンド使用（/commit, /commit-push-pr）
  - 生コマンド（git commit, gh pr create）使用禁止

- [ ] **コマンド/スキル/プラグイン自動発動ルール**（Section「🔌 コマンド/スキル/プラグイン自動発動ルール」）
  - Critical/High/Mediumの優先度確認
  - 発動条件の確認

- [ ] **コーディング規約**（@memory:coding_standards）
  - 命名規則、型ヒント、テスト規約の確認

- [ ] **品質ゲート**（@memory:implementation_quality_gates）
  - 4段階品質チェック（pytest/ruff/mypy/git）の確認

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

**このセクションの範囲**: 高頻度で参照する基本コマンドのみ
**詳細な原因分析・解決策**: @memory:test_strategy_details トラブルシューティングFAQ参照

### テスト失敗時

```bash
# 詳細ログ出力
uv run pytest -vv --tb=long

# 最初の失敗で停止
uv run pytest -x

# 特定テストのみデバッグ実行
uv run pytest tests/unit/test_async_client.py::test_name -vv --log-cli-level=DEBUG
```

### カバレッジ不足時

```bash
# カバレッジレポート確認
uv run pytest --cov-report=term-missing

# HTMLレポート生成
uv run pytest --cov-report=html
open reports/htmlcov/index.html
```

### 型チェックエラー時

```bash
# mypy詳細出力
uv run mypy --show-error-codes --pretty utils/ config/ models/
```
