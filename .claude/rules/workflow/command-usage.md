# コマンド使用ガイド

*最終更新: 2026年01月28日*
*用途: ccplugins/SuperClaude/Claude Templatesコマンドの最適選択 + Plugin自動発動ルール*
*アクセス頻度: 中（開発タスク開始時、コマンド選択迷い時）*

## 📚 目次

1. コマンド選択マトリクス
2. フレームワーク特性
3. 重複排除の根拠と証拠ベース分析
4. Plugin自動発動ルール
5. コマンド削除時チェックリスト
6. superpowers使い分けガイド 🆕

---

## 1. コマンド選択マトリクス

**目的**: 複数のコマンドフレームワーク（ccplugins、SuperClaude、Claude Templates）から最適なコマンドを選択するための早見表

### テスト・品質保証

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| コンテキスト検出テスト | `/test` | ccplugins | Cold Start検出、自動修正 | `/test`, `/test tests/unit/`, `/test --coverage` |
| E2Eブラウザテスト | `/sc:test` | SuperClaude | Playwright MCP統合 | `/sc:test` |
| Docker環境テスト | `/test` | ccplugins | docker-compose統合 | `/test "docker-compose up dev"` |

### 実装・開発

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| リポジトリ移植実装 | `/implement` | ccplugins | Deep Validation + auto-fix | `/implement "GitHub Actions test workflow実装"` |
| マルチPersona協働実装 | `/sc:implement` | SuperClaude | 5種類のPersona協働 | `/sc:implement "feature"` |
| チェックリストベース実装 | `/implement` | ccplugins | セッション継続、進捗追跡 | `/implement docs/プロジェクト再編/Week7_Docker実装完了チェックリスト.md` |
| 仕様書ベース実装 | `/implement` | ccplugins | 自動計画生成（implement/plan.md） | `/implement docs/プロジェクト再編/Week8_Day44_CICD最適化強化仕様.md` |

### セキュリティ

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| 脆弱性検出・自動修正 | `/security-scan` | ccplugins | セッション継続型修正フロー | `/security-scan Dockerfile docker-compose.yml` |
| Python依存関係スキャン | `/security-scan` | ccplugins | safety統合、自動修正 | `/security-scan requirements.txt` |
| 全体セキュリティスキャン | `/security-scan` | ccplugins | Critical/High/Medium分類 | `/security-scan` |

### ドキュメント

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| 新規ドキュメント生成 | `/sc:document` | SuperClaude | コンポーネント/API/ガイド生成（inline/api/guide） | `/sc:document src/api --type api` |
| 実装後ドキュメント更新 | `/docs:update-docs` | CEK Plugin | Git連携+マルチエージェント品質レビュー | `/docs:update-docs` |
| ドキュメント品質監査 | `/docs-maintenance` | ccplugins | リンク検証・スタイル一貫性・自動同期 | `/docs-maintenance --audit` |
| プロジェクト全体ドキュメント | `/docs` | ccplugins | 全ドキュメント一括更新 | `/docs update` |

### 設計・計画

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| 要件発見（ブレスト） | `/sc:brainstorm` | SuperClaude | 7種類のPersona協働、6種類のMCP統合 | `/sc:brainstorm` |
| ワークフロー生成 | `/sc:workflow` | SuperClaude | PRD → 実装計画変換、7種類のPersona協働 | `/sc:workflow` |

### セッション管理

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| セッション復元 | `/sc:load` | SuperClaude | Serena MCP統合（cross-session persistence） | `/sc:load` |
| セッション保存 | `/sc:save` | SuperClaude | Serena MCP統合（checkpoint creation） | `/sc:save` |

---

## 2. フレームワーク特性

### ccplugins（Smart系）

**特徴**:
- セッションインテリジェンス: コンテキスト検出、Cold Start検出
- 自動修正: テスト失敗時の自動リトライ・修正フロー
- 継続的改善: 進捗追跡、セッション継続型ワークフロー

**適用場面**:
- 単一リポジトリ内の開発タスク
- 継続的改善・品質保証
- チェックリスト・仕様書ベースの実装

**主要コマンド**:
- `/test`: コンテキスト検出テスト、Docker環境テスト
- `/implement`: リポジトリ移植、チェックリスト/仕様書ベース実装
- `/review`: コードレビュー
- `/docs`: ドキュメント一括更新、`/sc:document`（生成）、`/docs:update-docs`（更新）
- `/refactor`: リファクタリング
- `/scaffold`: プロジェクト雛形作成
- `/security-scan`: セキュリティ脆弱性検出・自動修正

---

### SuperClaude

**特徴**:
- MCP統合: Serena（記憶管理）、Playwright（E2Eテスト）、Sequential（複雑分析）
- マルチPersona協働: 7種類のPersona（architect, developer, tester等）が協働
- 複雑なワークフロー: 要件発見→設計→実装の全工程サポート

**適用場面**:
- 要件発見・ブレインストーミング
- アーキテクチャ設計・ワークフロー生成
- セッション管理（復元・保存）
- E2Eブラウザテスト

**主要コマンド**:
- `/sc:brainstorm`: 要件発見（7種類のPersona協働、6種類のMCP統合）
- `/sc:workflow`: PRD → 実装計画変換
- `/sc:implement`: マルチPersona協働実装（5種類のPersona）
- `/sc:test`: E2Eブラウザテスト（Playwright MCP統合）
- `/sc:load`: セッション復元（Serena MCP統合）
- `/sc:save`: セッション保存（Serena MCP統合）

---

## 3. 重複排除の根拠と証拠ベース分析

### コマンド重複の判定基準

以下の基準で、機能的重複を排除し、各コマンドの固有価値を明示：

### 重複コマンドの保持判定

#### 1. `/sc:implement` vs `/implement`: **両者保持**

**判定理由**:
- `/sc:implement`: マルチPersona協働（architect / developer / tester / security / performanceの5種類）
- `/implement`: Deep Validation（品質ゲート自動実行） + auto-fix（エラー自動修正）

**使い分け**:
- 複雑な機能実装（アーキテクチャ設計必要）: `/sc:implement`
- 仕様書・チェックリストベース実装: `/implement`

---

#### 2. `/sc:test` vs `/test`: **両者保持**

**判定理由**:
- `/sc:test`: E2Eブラウザテスト（Playwright MCP統合、UI自動操作）
- `/test`: コンテキスト検出テスト（Cold Start検出、自動修正、docker-compose統合）

**使い分け**:
- ブラウザUI操作テスト: `/sc:test`
- 単体・統合テスト、Docker環境テスト: `/test`

---

#### 3. `/docs`: **ccplugins独自**

**特徴**:
- `/docs`: 全ドキュメント一括更新（README、API docs、Architecture docs）、バッジ自動生成（shields.io）

**推奨**:
- 新規ドキュメント生成: `/sc:document` （SuperClaude）
- 実装後の更新: `/docs:update-docs` （CEK Plugin）
- 品質監査: `/docs-maintenance` （ccplugins）
- プロジェクト全体一括更新: `/docs` （ccplugins）

> **Note**: ドキュメントスキルは目的別に分離（生成→更新→監査のライフサイクル）

---

### 証拠ベース分析

**証拠**: 実ファイル内容（YAML headers、MCP統合宣言）から抽出した特徴量に基づく比較分析

#### ccpluginsコマンド実装特徴量（YAML headers分析）
```yaml
# /test コマンド例
features:
  - context_detection: Cold Start検出
  - auto_fix: テスト失敗時の自動修正
  - docker_integration: docker-compose統合

# /implement コマンド例
features:
  - deep_validation: 品質ゲート自動実行（pytest, ruff, mypy）
  - session_continuity: セッション継続型進捗追跡
  - auto_planning: implement/plan.md自動生成
```

#### SuperClaudeコマンド実装特徴量（MCP統合宣言）
```yaml
# /sc:test コマンド例
mcp_integrations:
  - playwright: E2Eブラウザテスト自動化

# /sc:implement コマンド例
personas:
  - architect: アーキテクチャ設計
  - developer: 実装
  - tester: テスト設計
  - security: セキュリティ検証
  - performance: パフォーマンス最適化
```

---

## 4. Plugin自動発動ルール

**目的**: AIが明示的指示なしで適切なPluginを自動発動するためのルール定義

### 優先度別発動ルール

#### Critical（毎コミット必須）

| Plugin | パッケージ | 発動トリガー | 用途 |
|--------|----------|------------|------|
| `security-guidance` | @claude-code-plugins | Edit/Write/MultiEdit時 | 自動セキュリティ警告（9パターン検出） |
| `/code-review:code-review` | @claude-code-plugins | 品質ゲート全合格後（※1） | 4並列エージェントレビュー（80点閾値） |

#### High（開発標準）

| Plugin | パッケージ | 発動トリガー | 用途 |
|--------|----------|------------|------|
| `/feature` | @claude-code-templates | 新機能開発開始時 | developからfeatureブランチ作成 |
<!-- | `/release` | @claude-code-templates | リリース準備時 | releaseブランチ作成+バージョン管理 | -->
| `/hotfix` | @claude-code-templates | 緊急修正時 | mainからhotfixブランチ作成 |
| `/commit` | @claude-code-plugins | コミット作成時 | ステージング+コミット |
| `/commit-push-pr` | @claude-code-plugins | PR作成時 | コミット→プッシュ→PR一括 |
| `/pr-review-toolkit:review-pr` | @claude-code-plugins | git push完了後、PR作成前 | 6エージェント包括レビュー |
| `/test-coverage`, `/generate-tests` | グローバルコマンド | テスト関連時 | カバレッジ分析・テスト生成 |

#### Medium（必要時）

| Plugin | パッケージ | 発動トリガー | 用途 |
|--------|----------|------------|------|
| `/docs-maintenance` | プロジェクト固有 | ドキュメント保守時 | 品質保証・バリデーション・自動更新 |
| `/troubleshooting-guide` | プロジェクト固有 | トラブルシューティング時 | 診断手順・共通問題・自動解決 |
| `/prompt-lookup` | グローバルスキル | プロンプト検索時 | プロンプトテンプレート発見・改善 |
| `/skill-lookup` | グローバルスキル | スキル検索時 | 再利用可能なAI機能発見・インストール |


### ユースケース別推奨フロー

#### 技術学習フェーズ
```
1. 学習開始 → (コード作成)
2. テスト作成後 → `/test-coverage`
3. 実装完了後 → `/code-review:code-review`
4. コミット時 → security-guidance自動警告 + `/commit`
```

#### ポートフォリオ実装フェーズ
```
1. 機能開発開始 → `/feature <name>`
2. 実装中の変更保存 → `/commit`
3. 実装完了・PR作成前 → `/pr-review-toolkit:review-pr`
4. PR作成 → `/commit-push-pr`
5. マージ後 → `/clean_gone`
<!-- 6. リリース準備 → `/release <version>` -->
7. リリース完了 → `/clean-gone`
```

#### 実案件対応フェーズ
```
1. 品質ゲート全合格後 → `/code-review:code-review` (Critical必須)
2. PR作成時 → `/pr-review-toolkit:review-pr` (High標準)
3. ドキュメント保守時 → `/docs-maintenance` (Medium必要時)
```

**※1 品質ゲート**: `uv run pytest && uv run ruff check . && uv run mypy utils/ config/ models/`

---

**参照元**:
- グローバルCLAUDE.md 行167-218（2025年11月14日抽出）
- docs/guides/claude-code-plugins-usage-guide.md（2026年1月28日更新）

---

## 5. コマンド削除時チェックリスト

**目的**: Slashコマンド削除後の参照整合性を確保するための即時チェック手順

### チェック対象

| スコープ | 対象パス | 影響範囲 |
|---------|---------|---------|
| プロジェクトローカル | `docs/`, `.serena/memories/` | 当該プロジェクトのみ |
| グローバル設定 | `~/.claude/` | **全プロジェクト** |

### 実行手順

#### Step 1: 削除コマンド名を変数化
```bash
# 例: /sc:document を削除した場合
DELETED_CMD="/sc:document"
```

#### Step 2: プロジェクトローカルチェック
```bash
grep -rn "$DELETED_CMD" docs/ .serena/memories/
```

#### Step 3: グローバル設定チェック（重要）
```bash
# debug/ディレクトリはログファイルのため除外
grep -rn "$DELETED_CMD" ~/.claude --include="*.md" | grep -v "/debug/"
```

**教訓**: プロジェクトローカルのみクリーンアップし、グローバル設定を見落としやすい。Step 3のグローバルチェックを忘れずに実行すること。

---

## 6. superpowers使い分けガイド

**導入日**: 2025-12-28 | **バージョン**: 4.0.3
**更新日**: 2025-12-31（spec-workflow MCP版移行対応）

**目的**: superpowersとspec-workflow MCPの使い分け判断基準を提供

> **※本ルールはプロジェクト固有の判断基準であり、公式推奨ではありません。実運用で調整してください。**

### superpowers vs spec-workflow MCP 使い分け

| ユースケース | 推奨ツール | 理由 |
|-------------|-----------|------|
| 既知パターンの高速実装 | **superpowers** | 自律実行で効率化 |
| TDD強制が必要 | **superpowers** | `test-driven-development`スキル |
| 体系的デバッグ | **superpowers** | `systematic-debugging`スキル |
| 新規機能の詳細設計 | **spec-workflow MCP** | 各ステップ承認で慎重に |
| 複雑な要件定義 | **spec-workflow MCP** | 自然言語で仕様作成依頼 |
| **迷ったら** | **superpowers** | デフォルトはsuperpowersで開始 |

### superpowersコマンド

| コマンド | 用途 | 例 |
|---------|------|-----|
| `/superpowers:brainstorm` | アイデア発想・要件整理 | 新機能検討時 |
| `/superpowers:write-plan` | 実装計画作成 | 設計完了後 |
| `/superpowers:execute-plan` | 計画の自律実行 | Plan承認後 |

### superpowersスキル（主要）

| スキル | 用途 | 発動方法 |
|--------|------|----------|
| `test-driven-development` | TDD強制 | AIが自動判断して呼び出し |
| `systematic-debugging` | 体系的デバッグ | AIが自動判断して呼び出し |
| `verification-before-completion` | 完了前検証 | AIが自動判断して呼び出し |
| `dispatching-parallel-agents` | 並列エージェント | AIが自動判断して呼び出し |

**スキル発動ルール**: 1%でも適用可能性があればAIが自動で呼び出します

### spec-workflow MCP（自然言語インターフェース）

> **Note**: CLI版（`/spec-create`等のSlashコマンド）は廃止済み。MCP版は自然言語で依頼します。

| 依頼例 | 用途 |
|--------|------|
| 「新しい仕様を作成して」 | 仕様作成（Requirements → Design → Tasks） |
| 「仕様の実行を開始して」 | タスク実行 |
| 「仕様のステータスを確認して」 | 進捗確認 |
| 「バグレポートを作成して」 | バグ追跡 |

### 使用例

- 「バグ修正」→ AIが`test-driven-development`スキルを自動発動（superpowers）
- 「新機能設計」→ 「新しい仕様を作成して」と自然言語で依頼（spec-workflow MCP）
- 「既存機能の改善」→ `/superpowers:brainstorm`で開始

---

**移行元**: CLAUDE.md 行969-1009（2025-12-29移行）
**更新履歴**: 2025-12-31 CLI版→MCP版移行（26ファイル削除、自然言語インターフェース追加）
