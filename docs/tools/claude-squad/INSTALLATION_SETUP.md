# Claude Squad インストール・セットアップガイド

*最終更新: 2025年09月24日*

## 📋 インストール概要

このガイドでは、api-test-devops-portfolioプロジェクト用にClaude Squadを実際にインストール・設定する手順を詳しく説明します。

## 🔧 前提条件の確認

### 必須ツールの検証
```bash
# tmux バージョン確認（必須）
tmux --version
# 期待値: tmux 3.0以上

# GitHub CLI バージョン確認（必須）
gh --version
# 期待値: gh version 2.0以上

# Git バージョン確認（worktree機能用）
git --version
# 期待値: git version 2.7.0以上

# Python環境確認
python --version
# 期待値: Python 3.12.11（プロジェクト最適化バージョン）

# uv パッケージマネージャー確認
uv --version
# 期待値: uv 0.4以上
```

### 不足ツールのインストール
```bash
# tmux インストール（Mac）
brew install tmux

# GitHub CLI インストール（Mac）
brew install gh

# GitHub CLI認証設定
gh auth login
```

## 📦 Claude Squad インストール

### 方法1: Homebrew インストール（推奨）
```bash
# Claude Squad インストール
brew install claude-squad

# インストール確認
claude-squad --version

# シンボリックリンク作成（csコマンド短縮用）
ln -s "$(brew --prefix)/bin/claude-squad" "$(brew --prefix)/bin/cs"

# 短縮コマンド確認
cs --version
```

### 方法2: 手動インストール（バックアップ）
```bash
# インストールスクリプト実行
curl -fsSL https://raw.githubusercontent.com/smtg-ai/claude-squad/main/install.sh | bash

# PATH設定確認
echo $PATH | grep claude-squad

# 必要に応じてPATH追加
export PATH="$HOME/.claude-squad/bin:$PATH"
echo 'export PATH="$HOME/.claude-squad/bin:$PATH"' >> ~/.zshrc
```

## 🏗️ プロジェクト初期設定

### Claude Squad プロジェクト初期化
```bash
# プロジェクトルートディレクトリに移動
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# Claude Squad プロジェクト初期化
cs init

# 設定ファイル確認
ls -la .claude-squad/
cat .claude-squad/config.yaml
```

### プロジェクト設定カスタマイズ
```bash
# 設定一覧表示
cs config --list

# プロジェクト固有設定
cs config --set max-sessions=5
cs config --set default-agent=claude-code
cs config --set auto-save=true
cs config --set save-interval=30s

# バンコク時間帯最適化
cs config --set timezone=Asia/Bangkok
cs config --set work-hours=05:00-22:00
```

## 🌳 ワークツリー環境構築

### ブランチ・ワークツリー構造作成
```bash
# 現在のブランチ確認
git branch
git status

# 5つのフィーチャーブランチ作成
git checkout -b feature/core-development
git checkout -b feature/testing-qa
git checkout -b feature/security-compliance
git checkout -b feature/performance-devops
git checkout -b feature/docs-learning

# 統合ブランチ作成
git checkout -b integration/squad-merge

# メインブランチに戻る
git checkout main
```

### ワークツリー作成
```bash
# プロジェクトルートから実行
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# 5セッション用ワークツリー作成
mkdir -p ../claude-squad-workspaces

# セッション A: コア開発
git worktree add ../claude-squad-workspaces/squad-core-dev feature/core-development

# セッション B: テスト・品質保証
git worktree add ../claude-squad-workspaces/squad-testing feature/testing-qa

# セッション C: セキュリティ・コンプライアンス
git worktree add ../claude-squad-workspaces/squad-security feature/security-compliance

# セッション D: パフォーマンス・DevOps
git worktree add ../claude-squad-workspaces/squad-performance feature/performance-devops

# セッション E: ドキュメント・学習システム
git worktree add ../claude-squad-workspaces/squad-docs feature/docs-learning

# ワークツリー確認
git worktree list
```

### 各ワークツリーの環境設定
```bash
# セッション A環境設定
cd ../claude-squad-workspaces/squad-core-dev
uv sync --dev
cp ../../api-test-devops-portfolio/.env.example .env

# セッション B環境設定
cd ../squad-testing
uv sync --dev
cp ../../api-test-devops-portfolio/.env.example .env

# セッション C環境設定
cd ../squad-security
uv sync --dev
cp ../../api-test-devops-portfolio/.env.example .env

# セッション D環境設定
cd ../squad-performance
uv sync --dev
cp ../../api-test-devops-portfolio/.env.example .env

# セッション E環境設定
cd ../squad-docs
uv sync --dev
cp ../../api-test-devops-portfolio/.env.example .env

# 元ディレクトリに戻る
cd /Users/yuta/Yuta/python/api-test-devops-portfolio
```

## ⚙️ セッションテンプレート設定

### セッション設定ファイル作成
```bash
# Claude Squad設定ディレクトリ作成
mkdir -p .claude-squad/sessions

# セッション A設定
cat > .claude-squad/sessions/core-development.yaml << 'EOF'
# セッション A: コア開発・アーキテクチャ
name: core-development
description: "コア開発、APIクライアント、設定管理"
workspace: ../claude-squad-workspaces/squad-core-dev
agent: claude-code
focus_areas:
  - "utils/api_client.py"
  - "utils/performance_monitor.py"
  - "config/settings.py"
quality_gates:
  - "make test-unit"
  - "make type-check"
EOF

# セッション B設定
cat > .claude-squad/sessions/testing-qa.yaml << 'EOF'
# セッション B: テスト・品質保証
name: testing-qa
description: "テスト自動化、カバレッジ分析、品質保証"
workspace: ../claude-squad-workspaces/squad-testing
agent: claude-code
focus_areas:
  - "tests/"
  - "tests/conftest.py"
quality_gates:
  - "make coverage"
  - "make test-integration"
EOF

# セッション C設定
cat > .claude-squad/sessions/security-compliance.yaml << 'EOF'
# セッション C: セキュリティ・コンプライアンス
name: security-compliance
description: "セキュリティテスト、OWASP準拠、脆弱性対応"
workspace: ../claude-squad-workspaces/squad-security
agent: claude-code
focus_areas:
  - "tests/security/"
  - "utils/security_helpers.py"
quality_gates:
  - "make security-comprehensive"
EOF

# セッション D設定
cat > .claude-squad/sessions/performance-devops.yaml << 'EOF'
# セッション D: パフォーマンス・DevOps
name: performance-devops
description: "パフォーマンス最適化、CI/CD、Docker管理"
workspace: ../claude-squad-workspaces/squad-performance
agent: claude-code
focus_areas:
  - "tests/performance/"
  - ".github/workflows/"
  - "Dockerfile"
  - "Makefile"
quality_gates:
  - "make performance-quick"
EOF

# セッション E設定
cat > .claude-squad/sessions/docs-learning.yaml << 'EOF'
# セッション E: ドキュメント・学習システム
name: docs-learning
description: "技術文書、学習管理、監視システム"
workspace: ../claude-squad-workspaces/squad-docs
agent: claude-code
focus_areas:
  - "docs/"
  - "monitoring/"
quality_gates:
  - "make lint"
  - "make format"
EOF
```

## 🔄 Makefile統合

### Claude Squad用Makefileターゲット追加
```bash
# Makefileに追加するターゲット作成
cat >> Makefile << 'EOF'

# ================================================================
# Claude Squad 統合ターゲット
# ================================================================

.PHONY: squad-init squad-status squad-quality squad-integrate squad-cleanup

# Claude Squad初期設定
squad-init:
	@echo "🚀 Claude Squad初期設定開始"
	cs init
	@echo "✅ Claude Squad初期設定完了"

# 全セッション状態確認
squad-status:
	@echo "📊 Claude Squad セッション状態確認"
	cs list --all
	@echo "📈 各セッション詳細状態:"
	-cs status core-development
	-cs status testing-qa
	-cs status security-compliance
	-cs status performance-devops
	-cs status docs-learning

# 全セッション品質チェック
squad-quality:
	@echo "🔍 Claude Squad品質チェック開始"
	@echo "セッション A（コア開発）品質チェック:"
	make test-unit type-check
	@echo "セッション B（テスト）品質チェック:"
	make coverage test-integration
	@echo "セッション C（セキュリティ）品質チェック:"
	make security-comprehensive
	@echo "セッション D（パフォーマンス）品質チェック:"
	make performance-quick
	@echo "セッション E（ドキュメント）品質チェック:"
	make lint format
	@echo "✅ 全セッション品質チェック完了"

# セッション統合
squad-integrate:
	@echo "🔄 Claude Squad セッション統合開始"
	git checkout integration/squad-merge
	cs merge core-development --to=integration/squad-merge
	cs merge testing-qa --to=integration/squad-merge
	cs merge security-compliance --to=integration/squad-merge
	cs merge performance-devops --to=integration/squad-merge
	cs merge docs-learning --to=integration/squad-merge
	@echo "🔍 統合後品質チェック実行"
	make ci-comprehensive
	@echo "✅ Claude Squad統合完了"

# Claude Squad環境クリーンアップ
squad-cleanup:
	@echo "🧹 Claude Squad クリーンアップ開始"
	cs kill --all
	cs cleanup --days=3
	@echo "✅ Claude Squadクリーンアップ完了"
EOF
```

## 🧪 インストール確認テスト

### 基本機能テスト
```bash
# インストール確認
cs --version
cs config --list

# テストセッション作成
cs spawn --agent=claude-code --task="インストール確認テスト" --workspace=test

# セッション確認
cs list

# テストセッション終了
cs kill test-001
```

### ワークツリー動作確認
```bash
# ワークツリー一覧確認
git worktree list

# 各ワークツリーでのgit状態確認
cd ../claude-squad-workspaces/squad-core-dev
git status
git branch

cd ../squad-testing
git status
git branch

# 元ディレクトリに戻る
cd /Users/yuta/Yuta/python/api-test-devops-portfolio
```

### 品質チェック統合確認
```bash
# Makefileターゲット実行確認
make squad-status
make squad-quality

# CI/CD統合確認
make test-unit
make coverage
make security-quick
```

## 📊 セットアップ完了確認

### チェックリスト
- [ ] Claude Squad インストール完了
- [ ] 短縮コマンド(cs)設定完了
- [ ] プロジェクト初期化完了
- [ ] 5つのワークツリー作成完了
- [ ] セッション設定ファイル作成完了
- [ ] Makefile統合完了
- [ ] 基本機能テスト成功
- [ ] 品質チェック統合確認

### 設定状態確認コマンド
```bash
# 最終確認コマンド実行
echo "=== Claude Squad設定確認 ==="
cs --version
cs config --list

echo "=== ワークツリー確認 ==="
git worktree list

echo "=== セッション設定確認 ==="
ls -la .claude-squad/sessions/

echo "=== Makefile統合確認 ==="
make squad-status

echo "✅ Claude Squadセットアップ完了！"
```

## 🎯 次のステップ

セットアップ完了後:
1. [プロジェクト統合ガイド](./PROJECT_INTEGRATION_GUIDE.md)を参照
2. [日常ワークフローガイド](./DAILY_WORKFLOWS.md)で実践方法を学習
3. [トラブルシューティングガイド](./TROUBLESHOOTING.md)を確認

---

このセットアップガイドにより、api-test-devops-portfolioプロジェクトでClaude Squadを効果的に活用する基盤が整います。