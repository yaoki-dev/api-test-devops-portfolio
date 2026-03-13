# コマンド・Plugin・スキル使い分けガイド

*最終更新: 2026年02月18日*
*用途: ワークフロー駆動型の最適ツール選択ガイド - コマンド/Plugin/スキル/エージェントの使い分け*
*対象: 仕様駆動開発、Claude Flow エージェントオーケストレーション活用プロジェクト*
*アクセス頻度: 高（開発タスク開始時、ワークフロー設計時、ツール選択時）*

## 📚 目次

**このガイドの役割**: 3つのカタログ（AGENTS/COMMANDS/SKILLS）の「辞書的参照」に対し、本ガイドは「ワークフロー駆動の使い分け」を提供します。

1. [ワークフロー別推奨ツール](#1-ワークフロー別推奨ツール) 🆕
2. [コマンド選択マトリクス](#2-コマンド選択マトリクス)
3. [フレームワーク特性](#3-フレームワーク特性)
4. [重複排除の根拠](#4-重複排除の根拠と証拠ベース分析)
5. [自動発動ルール](#5-自動発動ルールpluginhookskill)
6. [コマンド削除時チェックリスト](#6-コマンド削除時チェックリスト)
7. [仕様駆動開発プラグイン使い分けガイド](#7-仕様駆動開発プラグイン使い分けガイド)
8. [関連ドキュメント](#8-関連ドキュメント)
9. [ast-grep / mgrep 使用ガイド](#9-ast-grep--mgrep-使用ガイド) 🆕

---

## 1. ワークフロー別推奨ツール

**目的**: 開発フェーズ・ワークフロー別に最適なツール組み合わせを提示

**💡 Note**: sdd/superpowers/spec-workflow MCPの3プラグイン詳細比較は [Section 7](#7-仕様駆動開発プラグイン使い分けガイド) を参照

### 仕様駆動開発ワークフロー

```mermaid
graph LR
    A[要件定義] --> B[仕様作成]
    B --> C[設計]
    C --> D[実装]
    D --> E[テスト]
    E --> F[レビュー]
    F --> G[デプロイ]
```

| フェーズ | 推奨ツール | 役割 | エージェント協働 |
|---------|----------|------|----------------|
| **要件定義** | `sdd:brainstorm` | 対話型アイデア発想 | - |
| | `sdd:create-ideas` | 単発アイデア生成（確率分布） | - |
| | `/brainstorm` | アイデア発想・要件整理 | - |
| | `/sc:brainstorm` | 7種類Persona協働 | architect, product-manager |
| | `spec-workflow MCP` | 仕様書作成（自然言語） | - |
| **仕様作成** | `sdd:01-specify` | 機能仕様書作成（spec-checklist検証） | business-analyst |
| | `/write-plan` | 実装計画作成（TDD Iron Law） | - |
| | `/sc:workflow` | PRD → 実装計画変換 | tech-lead, architect |
| **設計** | `sdd:02-plan` | アーキテクチャ設計（3案比較） | software-architect, researcher |
| | `/sc:implement` | マルチPersona協働実装 | architect, developer |
| | `@tech-lead (agent)` | タスク分解・依存関係整理 | - |
| **実装** | `sdd:04-implement` | Phase単位実装 | developer（Phase実行） |
| | `/implement` | 仕様書ベース実装 | developer |
| | `/execute-plan` | 計画自律実行（バッチ） | - |
| | `/subagent-driven-development` | タスク実行（2段階レビュー） | - |
| | `@developer (agent)` | コード生成 | - |
| **ドキュメント** | `sdd:05-document` | 実装ドキュメント自動生成 | tech-writer |
| **テスト** | `/test` | コンテキスト検出テスト | - |
| | `/generate-tests` | テスト自動生成 | - |
| | `@qa-expert (agent)` | テスト戦略設計 | - |
| **レビュー** | `/code-review:review-local-changes` | 6並列エージェント（80点閾値） | code-reviewer |
| | `/pr-review-toolkit:review-pr` | 6エージェント包括レビュー | silent-failure-hunter, security-code-reviewer |
| | `/superpowers:verification-before-completion` | 作業完了証拠確認（reflect前） | - |
| | `/reflexion:reflect` | 自己改善フィードバック | - |
| **デプロイ** | `/push-pr` | PR作成 | - |
| | `/docs:update-docs` | ドキュメント自動更新 | tech-writer |

### Claude Flow エージェントオーケストレーション

**マルチエージェント並列処理パターン**（概念図）:

> **注**: 以下のYAML/Pythonコードは並列処理の概念を示す疑似コードです。実際の実装は複数のTask tool呼び出しを1メッセージ内で並列記述します。

```yaml
# 例: 包括的コードレビュー（概念図）
workflow:
  phase: review
  parallel_agents:
    - silent-failure-hunter      # エラーハンドリング検証
    - security-code-reviewer      # セキュリティ脆弱性検出
    - performance-reviewer        # パフォーマンス分析
    - code-quality-reviewer       # コード品質評価
    - test-coverage-reviewer      # テストカバレッジ分析
    - documentation-accuracy-reviewer  # ドキュメント整合性

  sequential_flow:
    1. 全エージェント並列実行 (Task tool)
    2. 結果集約・優先度付け
    3. 修正提案生成
```

**実際の実装方法**:
1メッセージ内で複数のTask tool呼び出しを記述することで並列実行を実現します。

```markdown
# 6エージェント並列レビューの実際の実装例
<function_calls>
<invoke name="Task">
  <parameter name="subagent_type">silent-failure-hunter</parameter>
  <parameter name="description">エラーハンドリング検証</parameter>
  <parameter name="prompt">unstaged changesのエラーハンドリングを検証</parameter>
</invoke>
<invoke name="Task">
  <parameter name="subagent_type">security-code-reviewer</parameter>
  <parameter name="description">セキュリティ脆弱性検出</parameter>
  <parameter name="prompt">認証ロジックの脆弱性をチェック</parameter>
</invoke>
<!-- 残り4エージェント（Line 81-85参照）も同様に記述 -->
</function_calls>
```

### Git Flow + Plugin統合ワークフロー

| Git操作 | 推奨Plugin | 発動タイミング |
|---------|-----------|--------------|
| Feature開始 | `/git:feature <name>` | Issue作成後 |
| コミット | `/commit` | 品質ゲート全合格後 |
| PR作成 | `/push-pr` | `/pr-review-toolkit:review-pr` 完了後 |
| マージ | `gh pr merge --squash` | レビュー承認後 |
| ブランチ削除 | `/finishing-a-development-branch` | マージ完了後 |

---

## 2. コマンド選択マトリクス

**目的**: 複数のコマンドフレームワーク（ccplugins、SuperClaude、Claude Templates）から最適なコマンドを選択するための早見表

### テスト・品質保証

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| コンテキスト検出テスト | `/test` | ccplugins | Cold Start検出、自動修正 | `/test`, `/test tests/unit/`, `/test --coverage` |
| E2Eブラウザテスト | `/sc:test` | SuperClaude | Playwright MCP統合 | `/sc:test` |
| Docker環境テスト | `/test` | ccplugins | docker-compose統合 | `/test "docker-compose up dev"` |
| テストカバレッジ分析 | `/test-coverage` | 個別インストール | 4種類のカバレッジタイプ（line/branch/function/statement）分析 | `/test-coverage --line` |
| テスト自動生成 | `/generate-tests` | 個別インストール | AIベースのunit/integration/edge caseテスト生成 | `/generate-tests src/auth.ts` |

### 実装・開発

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| リポジトリ移植実装 | `/implement` | ccplugins | Deep Validation + auto-fix | `/implement "GitHub Actions test workflow実装"` |
| マルチPersona協働実装 | `/sc:implement` | SuperClaude | 5種類のPersona協働 | `/sc:implement "feature"` |
| チェックリストベース実装 | `/implement` | ccplugins | セッション継続、進捗追跡 | `/implement docs/プロジェクト再編/Week7_Docker実装完了チェックリスト.md` |
| 仕様書ベース実装 | `/implement` | ccplugins | 自動計画生成（implement/plan.md） | `/implement docs/プロジェクト再編/Week8_Day44_CICD最適化強化仕様.md` |
| プロジェクト雛形作成 | `/scaffold` | ccplugins | パターン検出型スキャフォールディング | `/scaffold UserProfile` |

### セキュリティ

| 目的 | 推奨コマンド | フレームワーク | 固有価値 | 具体例 |
|-----|------------|-------------|---------|--------|
| 脆弱性検出・自動修正 | `/security-scan` | ccplugins | セッション継続型修正フロー | `/security-scan Dockerfile docker-compose.yml` |
| Python依存関係スキャン | `/security-scan` | ccplugins | safety統合、自動修正 | `/security-scan requirements.txt` |
| 全体セキュリティスキャン | `/security-scan` | ccplugins | Critical/High/Medium分類 | `/security-scan` |

### ドキュメント

| 目的 | 推奨コマンド | 規模・条件 | 設計特性 | 固有価値 | 具体例 |
|-----|------------|----------|---------|---------|--------|
| 新規コンポーネント作成 | `/sc:document` | コンポーネント/API | 作成特化（4形式対応） | inline/external/API ref/guides生成 | `/sc:document utils/auth.py --style detailed` |
| 小規模・迅速更新 | `/docs` | 1-2ファイル | 単一AI自律型 | 高速（agent起動なし）、4モード | `/docs update` |
| 大規模・品質重視更新 | `/docs:update-docs` | 3+ファイルOR API変更 | マルチagent+review | 並列処理、専用品質保証、index管理 | `/docs:update-docs` |
| ドキュメント品質監査 | `/docs-maintenance` | 全体監査 | 監査特化 | リンク検証・スタイル一貫性・自動同期 | `/docs-maintenance --audit` |

**使い分けルール**:
- **作成フェーズ**: `/sc:document`（コンポーネント詳細） → `/docs`（プロジェクト統合）
- **更新フェーズ**: 小規模（1-2ファイル）→ `/docs` | 大規模（3+ファイル）→ `/docs:update-docs`
- **品質重視**: `/docs:update-docs`（review agent）| 速度重視: `/docs`（単一AI）

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

## 3. フレームワーク特性

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

## 4. 重複排除の根拠と証拠ベース分析

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

### 証拠ベース分析: 実装特徴量の機械可読化

#### ccpluginsコマンド実装特徴量

| ツール | 実装特徴 | 検証方法 |
|--------|---------|---------|
| `/test` | context_detection（Cold Start検出）<br>auto_fix（テスト失敗時の自動修正）<br>docker_integration（docker-compose統合） | `grep -E 'context_detection\|Cold Start' ~/.claude/commands/test.md` |
| `/implement` | deep_validation（品質ゲート自動実行: pytest, ruff, mypy）<br>session_continuity（セッション継続型進捗追跡）<br>auto_planning（implement/plan.md自動生成） | `grep -E 'deep_validation\|quality gate' ~/.claude/commands/implement.md` |

#### SuperClaudeコマンド実装特徴量

| ツール | 実装特徴 | 検証方法 |
|--------|---------|---------|
| `/sc:test` | playwright（E2Eブラウザテスト自動化） | MCP接続確認: `grep 'playwright' ~/.claude/settings.json` |
| `/sc:implement` | personas: architect（アーキテクチャ設計）<br>developer（実装）<br>tester（テスト設計）<br>security（セキュリティ検証）<br>performance（パフォーマンス最適化） | `grep -E 'personas\|architect' ~/.claude/commands/sc-implement.md` |

---

## 5. 自動発動ルール（Plugin/Command/Hook/Skill）

**目的**: AIが明示的指示なしで適切なツールを自動発動するためのルール定義

**💡 関連**: 全スキル自動発動ルール（簡潔版）は `~/.claude/docs/SKILLS_CATALOG.md` Section「スキル自動発動ルール」を参照

**注記**: CCPluginsコマンド（`/implement`, `/test`, `/scaffold`, `/security-scan`）はユーザー明示実行を前提とするため、このセクションには記載していません。これらのコマンドは Section 2「コマンド選択マトリクス」で使い分けを参照してください。

### 優先度別発動ルール

#### Critical（毎コミット必須）

| ツール | 種別 | 発動トリガー | 用途 |
|--------|------|------------|------|
| `security-guidance` | Hook | Edit/Write/MultiEdit時 | 自動セキュリティ警告（9パターン検出） |
| `/superpowers:verification-before-completion` | Skill | タスク完了時（reflect前） | 作業完了証拠確認|
| `/reflexion:reflect` | Skill | タスク完了時 | deep reflect実行（セルフレビュー） |
| `/code-review:review-local-changes` | Skill | 品質ゲート全合格後（※1） | 6並列エージェントレビュー（80点閾値） |

#### High（開発標準）

| ツール | 種別 | 発動トリガー | 用途 |
|--------|------|------------|------|
| `/create-issue` | SKill |Issue作成 | Issue駆動開発支援 |
| `/commit` | Skill | コミット作成時 | ステージング+コミット |
| `/push-pr` | Skill | PR作成時 | プッシュ→PR作成 |
| `/pr-review-toolkit:review-pr` | Skill | git push完了後、PR作成前 | 6エージェント包括レビュー |
| `/code-review:review-pr (CEK)` | Skill | 重要PR時 | 6エージェント防御レビュー（セキュリティ・バグ・API契約） |
| `/test-coverage` | Command | テスト関連時 | カバレッジ分析 |
| `/generate-tests` | Command | テスト関連時 | テスト生成 |

#### Medium（必要時）

| ツール | 種別 | 発動トリガー | 用途 |
|--------|------|------------|------|
| `/sc:document` | Command | 新規ドキュメント作成時 | コンポーネント/API/ガイド生成 |
| `/docs:update-docs` | Skill | 実装後ドキュメント更新時 | Git連携+マルチエージェント品質レビュー |
| `/docs-maintenance` | Command | ドキュメント品質監査時 | リンク検証・スタイル一貫性・自動同期 |
| `/troubleshooting-guide` | Command | トラブルシューティング時 | 診断手順・共通問題・自動解決 |
| `/decision-helper` | Skill | 2+選択肢の比較評価時 | 構造化意思決定フレームワーク（Pros/Cons, Decision Matrix, ICE） |
| `/fact-checker` | Skill | 主張・データの事実確認時 | 証拠ベースの事実検証・情報信頼性評価（6段階Verdictスケール） |
| `/prompt-lookup` | Skill | プロンプト検索時 | プロンプトテンプレート発見・改善 |
| `/skill-lookup` | Skill | スキル検索時 | 再利用可能なAI機能発見・インストール |


### ユースケース別推奨フロー

#### 技術学習フェーズ
```
1. 学習開始 → (コード作成)
2. テスト作成後 → `/test-coverage`
3. 実装完了後 → `/code-review:review-local-changes`
4. コミット時 → security-guidance自動警告 + `/commit`
```

#### ポートフォリオ実装フェーズ
```
1. 機能開発開始 → `/git:feature <name>`
2. 実装中の変更保存 → `/commit`
3. 実装完了・PR作成前 → `/pr-review-toolkit:review-pr`
4. PR作成 → `/push-pr`
5. マージ後 → `/clean_gone`
<!-- 6. リリース準備 → `/release <version>` -->
7. リリース完了 → `/clean-gone`
```

#### 実案件対応フェーズ
```
1. 品質ゲート全合格後 → `/code-review:review-local-changes` (Critical必須)
2. PR作成時 → `/pr-review-toolkit:review-pr` (High標準)
3. ドキュメント保守時 → `/docs-maintenance` (Medium必要時)
```

**※1 品質ゲート**: `uv run pytest && uv run ruff check . && uv run mypy utils/ config/ models/`

---

**参照元**:
- グローバルCLAUDE.md 行167-218（2025年11月14日抽出）
- docs/guides/claude-code-plugins-usage-guide.md（2026年1月28日更新）

---

## 6. コマンド削除時チェックリスト

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

## 7. 仕様駆動開発プラグイン使い分けガイド

**導入日**: 2025-12-28 | **バージョン**: superpowers 4.2.0, sdd 1.1.5, spec-workflow MCP
**更新日**: 2026-02-06（sdd vs superpowers vs spec-workflow MCP 3者比較追加）

**目的**: 3つの仕様駆動開発プラグイン（sdd, superpowers, spec-workflow MCP）の使い分け判断基準を提供

**💡 Note**: ワークフロー統合の全体像は [Section 1](#1-ワークフロー別推奨ツール) を参照

> **※本ルールはプロジェクト固有の判断基準であり、公式推奨ではありません。実運用で調整してください。**

### 3プラグイン比較マトリクス

| フェーズ | sdd | superpowers | spec-workflow MCP | 推奨選択基準 |
|---------|-----|-------------|-------------------|------------|
| **要件発見** | `brainstorm`（対話型） | `brainstorming`（段階的質問） | 自然言語仕様作成 | 対話重視→sdd/superpowers、仕様文書化→spec-workflow |
| **仕様作成** | `01-specify`（spec-checklist.md） | `writing-plans`（TDD Iron Law） | Requirements → Design → Tasks | 品質保証重視→sdd、TDD強制→superpowers、段階承認→spec-workflow |
| **設計** | `02-plan`（アーキテクチャ比較） | （執行プラン統合） | Design仕様 | 複数設計案比較→sdd、単一最適解→superpowers、自然言語指示→spec-workflow |
| **タスク分解** | `03-tasks`（依存関係分析） | `writing-plans`（bite-sized） | Tasks仕様 | Phase依存管理→sdd、TDD細分化→superpowers |
| **実装** | `04-implement`（Phase実行） | `subagent-driven-development`（タスク実行） | 自然言語実行指示 | Phase管理→sdd、品質保証→superpowers、段階承認→spec-workflow |
| **ドキュメント** | `05-document`（自動生成） | `finishing-a-development-branch` | （手動） | 自動文書化→sdd、PR統合→superpowers |

### sdd vs superpowers vs spec-workflow MCP 使い分け

| ユースケース | 推奨ツール | 理由 |
|-------------|-----------|------|
| **複数設計案の比較検討が必要** | **sdd** | `02-plan`で3つのアーキテクチャ案を生成・比較 |
| **仕様品質保証が重要** | **sdd** | spec-checklist.mdで15項目検証 |
| **研究・技術調査が必要** | **sdd** | researcher/code-explorerエージェント並列実行 |
| **既知パターンの高速実装** | **superpowers** | 自律実行で効率化 |
| **TDD強制が必要** | **superpowers** | `test-driven-development`スキル（Iron Law） |
| **タスク粒度の最適化** | **superpowers** | bite-sized tasks（2-5分/タスク） |
| **実装品質の早期検出** | **superpowers** | タスクごとの2段階レビュー（仕様遵守→品質） |
| **体系的デバッグ** | **superpowers** | `systematic-debugging`スキル |
| **新規機能の段階的承認** | **spec-workflow MCP** | Requirements→Design→Tasks各ステップで承認 |
| **複雑な要件定義** | **spec-workflow MCP** | 自然言語で仕様作成依頼 |
| **迷ったら** | **superpowers** | デフォルトはsuperpowersで開始 |

### sddコマンド（仕様駆動開発ワークフロー）

| コマンド | フェーズ | 用途 | 主要機能 |
|---------|---------|------|---------|
| `sdd:00-setup` | 準備 | プロジェクト憲法作成 | constitution.md生成、ガバナンス定義 |
| `sdd:brainstorm` | 要件発見 | 対話型アイデア発想 | 6アプローチ生成、段階的検証 |
| `sdd:create-ideas` | 要件発見 | 単発アイデア生成 | 確率分布サンプリング（6案） |
| `sdd:01-specify` | 仕様作成 | 機能仕様書作成 | spec-checklist.md検証、business-analyst |
| `sdd:02-plan` | 設計 | アーキテクチャ設計 | 3つの設計案比較、software-architect |
| `sdd:03-tasks` | タスク分解 | 実行可能タスク生成 | 依存関係分析、tech-lead |
| `sdd:04-implement` | 実装 | Phase単位実装 | developer（Phase実行）、品質レビュー |
| `sdd:05-document` | 文書化 | 実装ドキュメント生成 | tech-writer、完了検証 |

### superpowersコマンド（自律実行ワークフロー）

| コマンド | 用途 | 主要機能 | 例 |
|---------|------|---------|-----|
| `/brainstorm` | アイデア発想・要件整理 | 段階的質問、対話型検証 | 新機能検討時 |
| `/write-plan` | 実装計画作成 | bite-sized tasks、TDD Iron Law | 設計完了後 |
| `/execute-plan` | 計画の自律実行 | バッチ実行、チェックポイント付き | Plan承認後 |

### superpowersスキル（主要）

| スキル | 用途 | 発動方法 |
|--------|------|----------|
| `test-driven-development` | TDD強制 | AIが自動判断して呼び出し |
| `systematic-debugging` | 体系的デバッグ | AIが自動判断して呼び出し |
| `verification-before-completion` | 完了前検証 | AIが自動判断して呼び出し |
| `dispatching-parallel-agents` | 並列エージェント | AIが自動判断して呼び出し |
| `requesting-code-review` | コードレビュー依頼 | 手動呼び出し（※レビュースキル不足注意） |

**スキル発動ルール**: 1%でも適用可能性があればAIが自動で呼び出します

**参照**:
- GitHub公式リポジトリ: https://github.com/obra/superpowers
- 連携エージェント: なし（自律実行型）

### sdd（仕様駆動開発フレームワーク）

**バージョン**: 1.1.5
**パッケージ**: `sdd@context-engineering-kit`

**特徴**:
- Phase駆動ワークフロー（00-setup → 01-specify → 02-plan → 03-tasks → 04-implement → 05-document）
- 仕様品質保証（spec-checklist.md 15項目検証）
- マルチエージェント協働（business-analyst, researcher, code-explorer, software-architect, tech-lead, developer, tech-writer）
- 複数設計案比較（02-planで3つのアーキテクチャ案生成）

**参照**:
- GitHub公式リポジトリ: https://github.com/NeoLabHQ/context-engineering-kit
- ディレクトリ: `~/.claude/plugins/cache/context-engineering-kit/sdd/1.1.5/commands/`

**連携エージェント**:
- business-analyst（要件分析）
- researcher（技術調査）
- code-explorer（コードベース分析）
- software-architect（アーキテクチャ設計）
- tech-lead（タスク分解）
- developer（実装）
- tech-writer（ドキュメント生成）

### spec-workflow MCP（自然言語インターフェース）

> **Note**: CLI版（`/spec-create`等のSlashコマンド）は廃止済み。MCP版は自然言語で依頼します。

**参照**:
- GitHub公式リポジトリ: https://github.com/Pimzino/spec-workflow-mcp
- ユーザーガイド: https://github.com/Pimzino/spec-workflow-mcp/blob/main/docs/USER-GUIDE.md

**連携エージェント**: researcher, tech-writer, analyst, requirements-analyst, refactoring-expert

| 依頼例 | 用途 |
|--------|------|
| 「新しい仕様を作成して」 | 仕様作成（Requirements → Design → Tasks） |
| 「仕様の実行を開始して」 | タスク実行 |
| 「仕様のステータスを確認して」 | 進捗確認 |
| 「バグレポートを作成して」 | バグ追跡 |

### 使用例

**sddが最適なケース**:
- 「複数のアーキテクチャ案を比較したい」→ `sdd:02-plan`で3つの設計案を自動生成・比較
- 「仕様書の品質を保証したい」→ `sdd:01-specify`でspec-checklist.md 15項目検証
- 「未知技術を調査しながら設計」→ `sdd:02-plan`でresearcher/code-explorer並列実行

**superpowersが最適なケース**:
- 「バグ修正」→ AIが`test-driven-development`スキルを自動発動（superpowers）
- 「既知パターンの高速実装」→ `/execute-plan`で自律実行
- 「TDD厳守が必要」→ `writing-plans`でIron Law強制
- 「タスクごとの品質保証」→ `subagent-driven-development`で2段階レビュー

**spec-workflow MCPが最適なケース**:
- 「新機能を段階的に承認しながら進めたい」→ 「新しい仕様を作成して」と自然言語で依頼（spec-workflow MCP）
- 「複雑な要件を自然言語で定義」→ Requirements → Design → Tasks段階的承認

**ハイブリッド使用パターン**:
- Phase 1（要件～設計）: `sdd:brainstorm` → `sdd:01-specify` → `sdd:02-plan`
- Phase 2（実装）: `write-plan` → `subagent-driven-development`
- Phase 3（文書化）: `sdd:05-document`

---

**移行元**: CLAUDE.md 行969-1009（2025-12-29移行）
**更新履歴**:
- 2025-12-31: CLI版→MCP版移行（26ファイル削除、自然言語インターフェース追加）
- 2026-02-06: ワークフロー駆動型ガイドに改編、Phase 1-2実装完了、参照URL・連携エージェント追記
- 2026-02-06: sdd vs superpowers vs spec-workflow MCP 3者比較マトリクス追加、フェーズ別推奨選択基準、ハイブリッド使用パターン追加

---

## 8. 関連ドキュメント

### 3大カタログ（辞書的参照）

本ガイドと3大カタログの役割分担:

| ドキュメント | 役割 | 更新頻度 | 主な用途 |
|------------|------|---------|---------|
| **本ガイド (command-usage.md)** | **ワークフロー駆動の使い分け** | 中（機能追加時） | 開発フェーズ別の最適ツール選択 |
| **AGENTS_CATALOG.md** | エージェント全項目辞書 | 低（エージェント追加時） | エージェント仕様の詳細確認 |
| **COMMANDS_CATALOG.md** | コマンド全項目辞書 | 低（コマンド追加時） | コマンドオプション・引数の確認 |
| **SKILLS_CATALOG.md** | スキル全項目辞書（693件） | 低（スキル追加時） | スキル発動条件・機能の確認 |

### アクセスパス

```bash
# グローバル設定
~/.claude/docs/AGENTS_CATALOG.md    # 69エージェント（44ローカル + 19プラグイン + 6プロジェクト）
~/.claude/docs/COMMANDS_CATALOG.md  # 80コマンド（SuperClaude Framework）
~/.claude/docs/SKILLS_CATALOG.md    # 695スキル（32ユーザー + 663プラグイン）

# プロジェクト固有
.claude/rules/workflow/command-usage.md  # 本ガイド（ワークフロー駆動）
.claude/rules/workflow/RULES.md          # 行動ルール
.claude/rules/principles/PRINCIPLES.md   # 基本原則
```

### 推奨参照フロー

```
【開発開始時】
1. command-usage.md Section 1「ワークフロー別推奨ツール」で全体像把握
2. 具体的なツールが決定したら、各カタログで詳細確認
   - エージェント → AGENTS_CATALOG.md
   - コマンド → COMMANDS_CATALOG.md
   - スキル → SKILLS_CATALOG.md

【ツール詳細確認時】
1. カタログで発動条件・機能を確認
2. command-usage.md Section 2-5で使い分け・組み合わせを確認
```

### Claude Flow統合リファレンス

**マルチエージェントオーケストレーション**:
- 並列実行パターン: Section 1「Claude Flow エージェントオーケストレーション」参照
- エージェント一覧: `~/.claude/docs/AGENTS_CATALOG.md`
- タスク管理: Task tool（TaskCreate/TaskUpdate/TaskList）

**仕様駆動開発統合**:
- spec-workflow MCP: Section 7「spec-workflow MCP（自然言語インターフェース）」参照
- superpowers統合: Section 7「superpowers vs spec-workflow MCP 使い分け」参照

---

## 更新履歴

| 日付 | 変更内容 | Phase |
|------|---------|-------|
| 2026-01-28 | 初版作成（コマンド使用ガイド） | - |
| 2025-12-29 | CLAUDE.md から superpowers セクション移行 | - |
| 2025-12-31 | CLI版→MCP版移行（26ファイル削除） | - |
| 2026-02-06 | ワークフロー駆動型ガイドに改編 | Phase 1-2 |
| 2026-02-06 | 見出し修正・3大カタログ相互参照追加 | Phase 1-2 |
| 2026-02-06 | 優先度1-2修正完了（用語分類修正、証拠ベース分析表形式化、/git:feature, /git:hotfix削除） | Phase 1-2 |
| 2026-02-06 | Section番号重複修正（4→5繰り下げ）、Section 2マトリクスに/scaffold, /test-coverage, /generate-tests追加、Section 5にCCPlugins説明追記 | Phase 2完了 |
| 2026-02-06 | 目次-本文Section番号整合性修正（7→6, 8→7, 9→8）、目次リンクタイトル更新 | 最終検証 |
## 9. ast-grep / mgrep 使用ガイド

**目的**: AST解析ベース構造的コード検索・リファクタリング

### 9.1 ツール選択基準（Self-consistency check必須）

| ツール | 用途 | 成功条件 | 禁止条件 |
|--------|------|---------|---------|
| **ast-grep** | 言語構造的検索（関数定義、クラス継承、型ヒント） | 構文木パターン明確 + AST理解 | 文字列リテラル検索、正規表現で解決可能 |
| **mgrep** | コンテキスト統合検索（複数ファイル横断リファクタ） | 統一的命名変更 + AI支援リファクタ | 単純grep代替 |
| **Grep（標準）** | 文字列パターン検索 | **常に最優先検討** | - |

**基本原則**: **疑義時は常にGrep**（False Positive最小化）

### 9.2 使用禁止条件（False Positive防止）

**NEVER use ast-grep/mgrep if**:
- 標準Grepで十分（例: `import httpx`検索）
- 文字列リテラル内の検索（例: エラーメッセージ文言 `"Invalid JSON"`）
- 正規表現で解決可能な検索（例: `"test_.*_async"`）
- AST構造理解が曖昧な場合（→ Grepで代替）
- テスト実行中・未コミット変更あり（破壊的変更リスク）

### 9.3 用途別の詳細判断（機能差）

**ast-grep vs mgrep の本質的な違い:**

| 用途 | ast-grep | mgrep | 選択基準 |
|------|---------|-------|---------|
| リファクタリング | ◎ | × | コード変更時はast-grep必須（AST保証） |
| 安全な書き換え | ◎ | △ | 構文理解が必要 → ast-grep推奨 |
| Markdown構造探索 | ○ | ◎ | 文書構造 → mgrep推奨 |
| CI統合 | ◎ | ○ | 自動化・信頼性 → ast-grep推奨 |

**記号:** ◎=非常に優れている ○=優れている △=制限あり ×=非推奨

### 9.4 典型的成功例

**Use Case 1: Python型ヒント統一変換**
```bash
# ✅ ast-grep: Python 3.10 Union → 3.14 | 型変換
ast-grep --pattern 'Union[$A, $B]' --lang python utils/ config/ models/

# ❌ Grep: 不正確（コメント・文字列リテラル内も誤検出）
grep -r "Union\[" --include="*.py"
```

**Use Case 2: 非同期関数定義の全検索**
```bash
# ✅ ast-grep: 構文木ベース正確検索
ast-grep --pattern 'async def $FUNC($$$): $$$' --lang python

# ❌ Grep: Docstring内 "async def" も誤検出
grep -r "async def" .
```

**Use Case 3: 特定クラス継承の追跡**
```bash
# ✅ ast-grep: 継承関係解析
ast-grep --pattern 'class $CLASS(APIClientError): $$$' --lang python

# ❌ Grep: クラス名文字列も拾う
```

### 9.5 典型的失敗例（Grepで代替すべき）

**Anti-pattern 1: import文検索**
```bash
# ❌ 過剰: ast-grep
ast-grep --pattern 'import $MODULE' --lang python

# ✅ 適切: Grep（単純パターン検索）
grep -r "^import httpx" --include="*.py"
```

**Anti-pattern 2: 文字列リテラル検索**
```bash
# ❌ 不適切: ast-grep（文字列内容はAST構造に含まれない）
ast-grep --pattern '"Invalid JSON"' --lang python

# ✅ 適切: Grep
grep -r "Invalid JSON" --include="*.py"
```

**Anti-pattern 3: 正規表現パターン**
```bash
# ❌ 過剰: ast-grep
ast-grep --pattern 'test_$NAME' --lang python

# ✅ 適切: Grep
grep -rE "^def test_" tests/ --include="*.py"
```

### 9.6 mgrep（morph-mcp）統合検索

**用途**: コンテキスト保持型の統一リファクタリング

**成功条件**:
- 複数ファイル横断の命名変更（変数名・関数名の一括変更）
- 構造的に関連するコード群の一括検索（API呼び出しパターン等）
- AI支援が必要な複雑なリファクタリング

**制約**:
- MCPサーバー `morph-mcp` 必須（インストール確認: `ls ~/.claude/servers/morph-mcp/`）
- 単純な文字列置換は標準Grepで代替

**実行例**:
```bash
# Markdown見出し構造抽出（CLAUDE.md最適化時）
# → morph-mcp経由で実行（MCP tool使用）
```

### 9.7 信頼度と制約

| 要素 | 値 | 備考 |
|------|-----|------|
| AST解析精度 | 0.92 | 構文エラー時は動作せず |
| False Positive許容率 | <5% | Phase 2昇格条件（CLAUDE.md記載検討） |
| 標準Grep優先原則 | 必須 | 疑義時は常にGrep |
| 適用対象 | Python 3.14互換 | プロジェクト技術スタック準拠 |

### 9.8 実装推奨トリガー（参考）

**以下のケースで使用検討**（強制ではない）:

| ケース | トリガー条件 | ツール |
|--------|------------|--------|
| Python構文変換 | 3.10→3.14型ヒント統一 | ast-grep |
| pytestマーカー監査 | 品質ゲート失敗時（CRITICAL RULE 7） | ast-grep |
| API契約変更検証 | models/responses.py変更時 | ast-grep |
| CLAUDE.md構造分析 | 最適化・圧縮作業時 | mgrep |
| メモリファイル構成確認 | `.serena/memories/` 構造把握時 | mgrep |

**重要**: 上記はあくまで「検討」であり、**標準Grepで解決可能なら常にGrepを優先**

### 9.9 学習フェーズ運用（観察期間）

**期間**: 2026年02月13日 ～ 2026年02月20日（7日間）

**評価基準**:
- AI自発的メモリ参照: ≥3回
- 実際のast-grep/mgrep使用: ≥1回
- False Positive発生: 0件

**Phase 2移行条件**: 上記達成 **AND** ユーザー明示的要望ある場合のみ
- Phase 2: CLAUDE.md Mediumカテゴリに +1行追加検討
- Phase 3: High優先度昇格検討（使用頻度≥週2回 AND FP<5%）

**失敗時の撤退基準**（1週間後評価）:
- AI自発参照0回 OR 実使用0回 OR FP≥2件 → 本セクション削除

---
| 2026-02-13 | Section 9「ast-grep / mgrep 使用ガイド」追加（Phase 1実装、CLAUDE.md変更0行、自然淘汰観察戦略） | Phase 1 |
| 2026-02-13 | Section 9.3「用途別の詳細判断（機能差）」追加、Section番号繰り下げ（9.4→9.5～9.9）（Option G'実装） | Phase 1強化 |
| 2026-02-18 | Section 5 Medium に /decision-helper, /fact-checker を追加 | - |
