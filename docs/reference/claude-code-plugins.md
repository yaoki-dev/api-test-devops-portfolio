# Claude Code Plugins

*最終更新: 2026年01月28日*

このガイドでは、本プロジェクトで活用しているClaude Code Pluginsの設定と使用方法を説明します。

---

## 目次

1. [概要](#概要)
2. [プラグイン分類](#プラグイン分類)
3. [Critical優先度プラグイン](#critical優先度プラグイン)
4. [High優先度プラグイン](#high優先度プラグイン)
5. [グローバルコマンド活用ガイド](#グローバルコマンド活用ガイド)
6. [優先度別推奨順位表](#優先度別推奨順位表)
7. [トラブルシューティング](#トラブルシューティング)

---

## 概要

Claude Code Pluginsは、開発ワークフローを効率化するための拡張機能です。

### インストール済みプラグイン一覧（3件）

| プラグイン | バージョン | 優先度 | 提供機能 |
|-----------|-----------|--------|----------|
| security-guidance | 1.0.0 | Critical | セキュリティフック |
| code-review | 1.0.0 | Critical | 4並列コードレビュー |
| pr-review-toolkit | 1.0.0 | High | 6エージェントPRレビュー |

### グローバルコマンドに移行済み

以下のプラグインは削除され、グローバルコマンドとして提供されています：

| 旧プラグイン | 移行先グローバルコマンド |
|-------------|------------------------|
| git-workflow | `/git:feature`, `/git:hotfix`, `/release`, `/flow-status`, `/clean-gone` |
| testing-suite | `/test-coverage`, `/generate-tests` |

> **Note**: documentation-generator, performance-optimizer, security-proは削除済み（代替なし）

---

## プラグイン分類

### 優先度定義

| 優先度 | 定義 | 使用頻度 |
|--------|------|----------|
| **Critical** | 毎コミット・毎PR必須 | 毎日複数回 |
| **High** | 開発フロー標準 | 毎日 |

---

## Critical優先度プラグイン

### 1. security-guidance（セキュリティガイダンス）

**バージョン**: 1.0.0
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

---

### 2. code-review（コードレビュー）

**バージョン**: 1.0.0
**リポジトリ**: [anthropics/claude-code-plugins](https://github.com/anthropics/claude-code-plugins)

#### 概要

4つの専門エージェントが並列でコードレビューし、信頼度スコアに基づいて結果を統合する。

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

---

## High優先度プラグイン

### 3. pr-review-toolkit（PRレビューツールキット）

**バージョン**: 1.0.0
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

## グローバルコマンド活用ガイド

### Git Flow コマンド（旧git-workflowプラグイン）

Git Flowワークフローを完全サポート。ブランチ作成からマージまでを自動化。

#### 提供コマンド

| コマンド | 機能 |
|----------|------|
| `/git:feature <name>` | featureブランチ作成 |
| `/release <version>` | releaseブランチ作成 |
| `/git:hotfix <name>` | hotfixブランチ作成 |
| `/flow-status` | Git Flow状態確認 |
| `/clean-gone` | [gone]ブランチクリーンアップ |

> **Note**: ブランチ完了には `/finishing-a-development-branch` を使用

#### 使用例

```bash
# 新機能開発開始
/git:feature add-auth

# リリース準備
/release v1.2.0

# 緊急修正
/git:hotfix fix-critical-bug

# 状態確認
/flow-status
```

### テスト関連コマンド（旧testing-suiteプラグイン）

| コマンド | 機能 |
|----------|------|
| `/test-coverage` | カバレッジ分析・改善提案 |
| `/generate-tests` | テスト自動生成 |

### 開発フロー例

```
【開発フロー例】

1. 機能開発開始
   → /git:feature add-user-auth
   （featureブランチ作成）

2. 実装中の変更保存
   → /commit
   （変更をコミット）

3. 実装完了・PR作成
   → /commit-push-pr
   （コミット→プッシュ→PR作成）

4. マージ後のクリーンアップ
   → /clean-gone
   （マージ済みブランチ削除）

5. リリース準備
   → /release v1.2.0
   （releaseブランチ作成）

6. リリース完了
   → /finishing-a-development-branch
   （マージ戦略選択・クリーンアップ）
```

### 推奨コマンド一覧

| 場面 | 推奨コマンド |
|------|-------------|
| ブランチ作成 | `/git:feature`, `/release`, `/git:hotfix` |
| 日常コミット | `/commit` |
| PR作成 | `/commit-push-pr` |
| ブランチ完了 | `/finishing-a-development-branch` |
| ブランチ削除 | `/clean-gone` |
| 状態確認 | `/flow-status` |
| テストカバレッジ | `/test-coverage` |
| テスト生成 | `/generate-tests` |

---

## 優先度別推奨順位表

### Critical（毎日必須）

| 順位 | プラグイン | 理由 |
|------|-----------|------|
| 1 | security-guidance | セキュリティ自動チェック |
| 2 | code-review | 品質担保 |

### High（開発標準）

| 順位 | プラグイン/コマンド | 理由 |
|------|-------------------|------|
| 1 | pr-review-toolkit | PR品質向上 |
| 2 | `/git:feature`, `/git:hotfix` | ブランチ管理（グローバルコマンド） |
| 3 | `/test-coverage` | カバレッジ分析（グローバルコマンド） |

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
- [Claude Code 公式ドキュメント](https://docs.anthropic.com/en/docs/claude-code)
