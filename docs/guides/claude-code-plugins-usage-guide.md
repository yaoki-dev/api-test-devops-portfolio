# Claude Code Plugins 活用ガイド

*最終更新: 2025年12月06日*

このガイドでは、本プロジェクトで活用しているClaude Code Pluginsの設定と使用方法を説明します。

---

## 目次

1. [概要](#概要)
2. [プラグイン分類](#プラグイン分類)
3. [Critical優先度プラグイン](#critical優先度プラグイン)
4. [High優先度プラグイン](#high優先度プラグイン)
5. [Medium優先度プラグイン](#medium優先度プラグイン)
6. [Low優先度プラグイン](#low優先度プラグイン)
7. [git-workflowとcommit-commandsの使い分け](#git-workflowとcommit-commandsの使い分け)
8. [優先度別推奨順位表](#優先度別推奨順位表)
9. [トラブルシューティング](#トラブルシューティング)

---

## 概要

Claude Code Pluginsは、開発ワークフローを効率化するための拡張機能です。

### プラグインの種類

| 種類 | パッケージ名 | 特徴 |
|------|-------------|------|
| **Plugins** | `@claude-code-plugins` | コマンド・フック・エージェント中心 |
| **Templates** | `@claude-code-templates` | ワークフローテンプレート中心 |

### インストール済みプラグイン一覧（10件）

| プラグイン | バージョン | 優先度 | 提供機能 |
|-----------|-----------|--------|----------|
| security-guidance | 1.0.0 | Critical | セキュリティフック |
| code-review | 1.0.0 | Critical | 4並列コードレビュー |
| pr-review-toolkit | 1.0.0 | High | 6エージェントPRレビュー |
| commit-commands | 1.0.0 | High | Git操作コマンド |
| git-workflow | 1.0.1 | High | Git Flow管理 |
| testing-suite | 1.0.1 | High | テスト自動化 |
| documentation-generator | 1.0.1 | Medium | ドキュメント生成 |
| performance-optimizer | 1.0.1 | Medium | パフォーマンス最適化 |
| security-pro | 1.0.1 | Medium | セキュリティ監査 |
| ai-ml-toolkit | 1.0.1 | Low | AI/ML開発支援 |

---

## プラグイン分類

### 優先度定義

| 優先度 | 定義 | 使用頻度 |
|--------|------|----------|
| **Critical** | 毎コミット・毎PR必須 | 毎日複数回 |
| **High** | 開発フロー標準 | 毎日 |
| **Medium** | 必要時使用 | 週数回 |
| **Low** | 特定場面のみ | 月数回 |

---

## Critical優先度プラグイン

### 1. security-guidance（セキュリティガイダンス）

**バージョン**: 1.0.0
**作者**: David Dworken (Anthropic)
**リポジトリ**: [anthropics/claude-code-plugins](https://github.com/anthropics/claude-code-plugins)

#### 概要

PreToolUseフックによるリアルタイムセキュリティ警告システム。コード編集時に危険なパターンを検出し、開発者に警告を表示します。

#### 検出パターン（9種類）

| パターン | 対象言語 | リスク |
|----------|----------|--------|
| GitHub Actions workflow | YAML | ワークフローインジェクション |
| Node.js subprocess execution | JavaScript | コマンドインジェクション |
| Dynamic function creation | JavaScript | コードインジェクション |
| Code evaluation | JavaScript | コードインジェクション |
| React dangerous HTML | JSX/TSX | XSS攻撃 |
| DOM direct output | JavaScript | XSS攻撃 |
| innerHTML assignment | JavaScript | XSS攻撃 |
| Object deserialization | Python | 任意コード実行 |
| OS command execution | Python | コマンドインジェクション |

#### 動作仕様

- **トリガー**: `Edit`, `Write`, `MultiEdit` ツール使用時
- **警告方式**: セッション内で同一パターンは1回のみ警告
- **影響範囲**: 警告表示のみ（処理はブロックしない）

#### 使用方法

```bash
# 自動有効化（インストール後、設定不要）
# コード編集時に自動でセキュリティチェック実行
```

#### 警告表示例

```
⚠️ Security Warning: Using subprocess execution with user input can
lead to command injection. Consider using explicit arguments instead.
```

---

### 2. code-review（コードレビュー）

**バージョン**: 1.0.0
**作者**: Boris Cherny (Anthropic)
**リポジトリ**: [anthropics/claude-code-plugins](https://github.com/anthropics/claude-code-plugins)

#### 概要

4つの専門エージェントが並列でコードレビューを実行し、信頼度スコアに基づいて結果を統合します。

#### エージェント構成

| エージェント | 役割 | 重点領域 |
|-------------|------|----------|
| Agent 1 | ベストプラクティス | コーディング規約、設計パターン |
| Agent 2 | セキュリティ | 脆弱性、認証、データ保護 |
| Agent 3 | パフォーマンス | 効率性、リソース使用 |
| Agent 4 | 保守性 | 可読性、テスト容易性 |

#### 信頼度スコアリング

- **閾値**: 80点（デフォルト）
- **計算**: 4エージェントの評価を重み付け集計
- **出力**: 総合スコア + 各エージェントの詳細フィードバック

#### 使用方法

```bash
# PRレビュー実行
/code-review:code-review
```

#### 出力例

```
## Code Review Results

**Overall Confidence Score: 85/100** ✅

### Best Practices (Agent 1): 88/100
- ✅ Follows project conventions
- ⚠️ Consider extracting common logic to utils

### Security (Agent 2): 82/100
- ✅ Input validation present
- ⚠️ Add rate limiting to API endpoint

### Performance (Agent 3): 85/100
- ✅ Efficient database queries
- ✅ Proper caching implementation

### Maintainability (Agent 4): 84/100
- ✅ Clear function naming
- ⚠️ Add docstrings to public methods
```

---

## High優先度プラグイン

### 3. pr-review-toolkit（PRレビューツールキット）

**バージョン**: 1.0.0
**作者**: Daisy (Anthropic)
**リポジトリ**: [anthropics/claude-code-plugins](https://github.com/anthropics/claude-code-plugins)

#### 概要

6種類の専門エージェントによる包括的なPRレビューシステム。

#### エージェント一覧

| エージェント | 役割 | 使用場面 |
|-------------|------|----------|
| `comment-analyzer` | コメント正確性分析 | ドキュメント追加後 |
| `code-reviewer` | コード品質レビュー | 実装完了後 |
| `code-simplifier` | コード簡素化 | リファクタリング時 |
| `pr-test-analyzer` | テストカバレッジ分析 | PR作成前 |
| `silent-failure-hunter` | サイレント失敗検出 | エラーハンドリング確認 |
| `type-design-analyzer` | 型設計分析 | 新型定義時 |

#### 使用方法

```bash
# 包括的PRレビュー
/pr-review-toolkit:review-pr

# 個別エージェント呼び出し
# comment-analyzer: コメントの正確性検証
# code-reviewer: コード品質チェック
# pr-test-analyzer: テストカバレッジ確認
```

---

### 4. commit-commands（コミットコマンド）

**バージョン**: 1.0.0
**作者**: Anthropic
**リポジトリ**: [anthropics/claude-code-plugins](https://github.com/anthropics/claude-code-plugins)

#### 概要

Git操作を効率化するコマンドセット。

#### 提供コマンド

| コマンド | 機能 | 説明 |
|----------|------|------|
| `/commit` | コミット作成 | 変更をステージング＋コミット |
| `/commit-push-pr` | PR作成ワンストップ | コミット→プッシュ→PR作成 |
| `/clean_gone` | ブランチクリーンアップ | リモート削除済みブランチを削除 |

#### 使用方法

```bash
# 変更をコミット
/commit

# PR作成まで一括実行
/commit-push-pr

# 不要ブランチ削除
/clean_gone
```

---

### 5. git-workflow（Git Flow管理）

**バージョン**: 1.0.1
**パッケージ**: `@claude-code-templates`

#### 概要

Git Flowワークフローを完全サポート。ブランチ作成からマージまでを自動化。

#### 提供コマンド

| コマンド | 機能 |
|----------|------|
| `/git-workflow:feature <name>` | featureブランチ作成 |
| `/git-workflow:release <version>` | releaseブランチ作成 |
| `/git-workflow:hotfix <name>` | hotfixブランチ作成 |
| `/git-workflow:finish` | ブランチ完了・マージ |
| `/git-workflow:flow-status` | Git Flow状態確認 |

#### 使用方法

```bash
# 新機能開発開始
/git-workflow:feature add-auth

# リリース準備
/git-workflow:release v1.2.0

# 緊急修正
/git-workflow:hotfix fix-critical-bug

# ブランチ完了
/git-workflow:finish

# 状態確認
/git-workflow:flow-status
```

---

### 6. testing-suite（テストスイート）

**バージョン**: 1.0.1
**パッケージ**: `@claude-code-templates`

#### 概要

テスト自動化とカバレッジ管理のための包括的ツールキット。

#### 提供コマンド

| コマンド | 機能 |
|----------|------|
| `/testing-suite:generate-tests` | テスト自動生成 |
| `/testing-suite:e2e-setup` | E2Eテスト環境構築 |
| `/testing-suite:test-coverage` | カバレッジ分析 |
| `/testing-suite:setup-visual-testing` | ビジュアルテスト設定 |
| `/testing-suite:setup-load-testing` | 負荷テスト設定 |
| `/testing-suite:test-automation-orchestrator` | テスト自動化オーケストレーション |
| `/testing-suite:test-quality-analyzer` | テスト品質分析 |

---

## Medium優先度プラグイン

### 7. documentation-generator（ドキュメント生成）

**バージョン**: 1.0.1
**パッケージ**: `@claude-code-templates`

#### 概要

技術ドキュメントの自動生成と更新。

#### 提供コマンド

```bash
# ドキュメント更新
/documentation-generator:update-docs

# オプション
--implementation  # 実装ステータス更新
--api            # API文書更新
--architecture   # アーキテクチャ文書更新
--sync           # 全文書同期
--validate       # 文書検証
```

---

### 8. performance-optimizer（パフォーマンス最適化）

**バージョン**: 1.0.1
**パッケージ**: `@claude-code-templates`

#### 概要

アプリケーションパフォーマンスの分析と最適化。

#### 提供コマンド

```bash
# パフォーマンス監査
/performance-optimizer:performance-audit

# オプション
--frontend  # フロントエンド分析
--backend   # バックエンド分析
--full      # 完全監査
```

---

### 9. security-pro（セキュリティプロ）

**バージョン**: 1.0.1
**パッケージ**: `@claude-code-templates`

#### 概要

包括的なセキュリティ監査と脆弱性分析。

#### 提供コマンド

```bash
# セキュリティ監査
/security-pro:security-audit

# 依存関係監査
/security-pro:dependency-audit

# オプション
--full       # 完全監査
--security   # セキュリティのみ
--licenses   # ライセンス確認
--updates    # 更新確認
--all        # 全項目
```

---

## Low優先度プラグイン

### 10. ai-ml-toolkit（AI/MLツールキット）

**バージョン**: 1.0.1
**パッケージ**: `@claude-code-templates`

#### 概要

AI/ML開発支援ツール。LLMアプリケーション、RAGシステム、MLパイプライン構築をサポート。

#### 提供エージェント

| エージェント | 役割 |
|-------------|------|
| `ai-engineer` | LLMアプリ・RAGシステム |
| `ml-engineer` | MLパイプライン・モデルデプロイ |
| `nlp-engineer` | NLP・テキスト分析 |
| `computer-vision-engineer` | 画像処理・物体検出 |
| `mlops-engineer` | MLOps・実験管理 |

---

## git-workflowとcommit-commandsの使い分け

### 比較表

| 観点 | git-workflow | commit-commands |
|------|--------------|-----------------|
| **パッケージ** | @claude-code-templates | @claude-code-plugins |
| **主目的** | Git Flowブランチ管理 | 日常Git操作効率化 |
| **対象操作** | ブランチ作成・マージ | コミット・PR作成 |
| **使用頻度** | 機能単位（週数回） | 毎日複数回 |

### 使用場面ガイド

```
【開発フロー例】

1. 機能開発開始
   → /git-workflow:feature add-user-auth
   （featureブランチ作成）

2. 実装中の変更保存
   → /commit
   （変更をコミット）

3. 実装完了・PR作成
   → /commit-push-pr
   （コミット→プッシュ→PR作成）

4. マージ後のクリーンアップ
   → /clean_gone
   （マージ済みブランチ削除）

5. リリース準備
   → /git-workflow:release v1.2.0
   （releaseブランチ作成）

6. リリース完了
   → /git-workflow:finish
   （main + developへマージ）
```

### 推奨使い分け

| 場面 | 推奨コマンド |
|------|-------------|
| ブランチ作成 | `/git-workflow:feature|release|hotfix` |
| 日常コミット | `/commit` |
| PR作成 | `/commit-push-pr` |
| ブランチマージ | `/git-workflow:finish` |
| ブランチ削除 | `/clean_gone` |
| 状態確認 | `/git-workflow:flow-status` |

---

## 優先度別推奨順位表

### Critical（毎日必須）

| 順位 | プラグイン | 理由 |
|------|-----------|------|
| 1 | security-guidance | セキュリティ自動チェック |
| 2 | code-review | 品質担保 |

### High（開発標準）

| 順位 | プラグイン | 理由 |
|------|-----------|------|
| 1 | commit-commands | 日常Git操作 |
| 2 | git-workflow | ブランチ管理 |
| 3 | pr-review-toolkit | PR品質向上 |
| 4 | testing-suite | テスト自動化 |

### Medium（必要時）

| 順位 | プラグイン | 理由 |
|------|-----------|------|
| 1 | documentation-generator | ドキュメント整備 |
| 2 | security-pro | 定期セキュリティ監査 |
| 3 | performance-optimizer | パフォーマンス改善 |

### Low（特定場面）

| 順位 | プラグイン | 理由 |
|------|-----------|------|
| 1 | ai-ml-toolkit | AI/ML機能実装時のみ |

---

## トラブルシューティング

### プラグインが動作しない場合

```bash
# プラグイン一覧確認
claude /plugins

# プラグイン再インストール
claude /install-plugin <plugin-name>
```

### セキュリティフックが誤検出する場合

security-guidanceは以下のカテゴリのパターンを検出します：
- サブプロセス実行系（Node.js）
- 動的コード実行系（JavaScript）
- XSS関連（React/DOM操作）
- シリアライズ関連（Python）
- OSコマンド実行（Python）

正当な使用の場合は、警告を確認した上で続行してください。

### コマンドが見つからない場合

```bash
# 利用可能なコマンド確認
/help

# 特定プラグインのコマンド確認
/<plugin-name>:
```

---

## 参考リンク

- [Claude Code Plugins 公式リポジトリ](https://github.com/anthropics/claude-code-plugins)
- [Claude Code Templates 公式リポジトリ](https://github.com/anthropics/claude-code-templates)
- [Claude Code 公式ドキュメント](https://docs.anthropic.com/en/docs/claude-code)
