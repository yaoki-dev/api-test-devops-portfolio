# Claude Squad 日常ワークフローガイド

*最終更新: 2025年09月24日*

## 📋 概要

このガイドでは、api-test-devops-portfolioプロジェクトでのClaude Squad日常運用パターンを実践的に説明します。913テスト環境での効率的な並列開発ワークフローを提供します。

## 🌅 朝の開発開始パターン

### ステップ1: 環境状態確認
```bash
# プロジェクトルートに移動
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# 前日の作業状態確認
cs list --all
git status
git log --oneline -10

# ワークツリー状態確認
git worktree list
make squad-status
```

### ステップ2: 本日の作業計画立案
```bash
# セッション計画表示
echo "=== 本日のClaude Squad作業計画 ==="
echo "セッション A（コア開発）: API機能強化"
echo "セッション B（テスト）: カバレッジ85%維持"
echo "セッション C（セキュリティ）: OWASP準拠確認"
echo "セッション D（パフォーマンス）: 性能最適化"
echo "セッション E（ドキュメント）: 技術文書更新"
```

### ステップ3: セッション起動
```bash
# メイン開発セッション起動
cs spawn --agent=claude-code --task="API機能強化開発" --workspace=../claude-squad-workspaces/squad-core-dev

# テスト強化セッション起動
cs spawn --agent=claude-code --task="テストカバレッジ強化" --workspace=../claude-squad-workspaces/squad-testing

# セキュリティチェックセッション起動（必要時）
cs spawn --agent=claude-code --task="セキュリティ検証" --workspace=../claude-squad-workspaces/squad-security

# セッション確認
cs list
```

## 🔄 日中の並列開発パターン

### パターン1: 機能追加開発（高頻度）
```bash
# API機能開発（セッション A）
cs switch core-dev-001
# → utils/api_client.py の機能拡張
# → config/settings.py の設定追加
# → 非同期HTTP処理の最適化

# 対応テスト作成（セッション B）
cs switch testing-002
# → tests/unit/test_api_client.py の拡張
# → tests/integration/ の追加テスト
# → カバレッジ確認・85%維持

# セキュリティ検証（セッション C）
cs switch security-003
# → 新機能のセキュリティテスト追加
# → OWASP準拠確認
```

### パターン2: バグ修正・品質改善（中頻度）
```bash
# 問題調査・修正（セッション A + D）
cs spawn --agent=claude-code --task="性能問題調査修正" --workspace=../claude-squad-workspaces/squad-performance
cs spawn --agent=claude-code --task="コア機能バグ修正" --workspace=../claude-squad-workspaces/squad-core-dev

# 回帰テスト強化（セッション B）
cs switch testing-002
# → 既存テストの検証・強化
# → 回帰テスト追加

# 進捗確認
cs status performance-004
cs status core-dev-001
cs status testing-002
```

### パターン3: 大規模リファクタリング（低頻度）
```bash
# 全セッション並列リファクタリング
cs spawn --agent=claude-code --task="アーキテクチャ改善" --workspace=../claude-squad-workspaces/squad-core-dev
cs spawn --agent=aider --task="テストコード改善" --workspace=../claude-squad-workspaces/squad-testing
cs spawn --agent=claude-code --task="セキュリティ強化" --workspace=../claude-squad-workspaces/squad-security
cs spawn --agent=claude-code --task="パフォーマンス最適化" --workspace=../claude-squad-workspaces/squad-performance
cs spawn --agent=claude-code --task="ドキュメント更新" --workspace=../claude-squad-workspaces/squad-docs

# 全セッション進捗監視
watch -n 10 'cs list'
```

## 🔍 品質チェック統合ワークフロー

### リアルタイム品質確認
```bash
# 開発中の継続的品質チェック
# セッション A作業後
cs switch core-dev-001
make test-unit type-check

# セッション B作業後
cs switch testing-002
make coverage test-integration

# セッション C作業後
cs switch security-003
make security-quick

# セッション D作業後
cs switch performance-004
make performance-quick
```

### 日次品質ゲートチェック
```bash
# 1日の終わりの包括品質チェック
make squad-quality

# 結果確認・問題対応
if [ $? -ne 0 ]; then
    echo "⚠️  品質問題検出 - 各セッションで問題解決必要"
    cs list
    make squad-status
else
    echo "✅ 全品質チェック合格"
fi
```

## 🌆 夕方の統合・マージパターン

### ステップ1: セッション作業完了確認
```bash
# 各セッション作業状況確認
cs review core-dev-001      # コア開発変更確認
cs review testing-002       # テスト変更確認
cs review security-003      # セキュリティ変更確認（該当時）
cs review performance-004   # パフォーマンス変更確認（該当時）

# 各セッション品質ゲート確認
make squad-quality
```

### ステップ2: セッション統合準備
```bash
# 統合前のコミット・プッシュ
cs switch core-dev-001
git add . && git commit -m "feat: API機能強化 - 非同期HTTP処理最適化"
git push origin feature/core-development

cs switch testing-002
git add . && git commit -m "test: API機能テスト追加 - カバレッジ85%維持"
git push origin feature/testing-qa

# 他のセッションも同様にコミット・プッシュ
```

### ステップ3: 統合実行
```bash
# セッション統合実行
make squad-integrate

# 統合後の完全検証
make ci-comprehensive

# 統合成功確認
git log --oneline integration/squad-merge -10
```

## 🌙 夜間・バンコク時間最適化パターン

### 深夜作業設定（JST 22:00-02:00 / BKK 20:00-24:00）
```bash
# 夜間長時間作業セッション設定
cs spawn --agent=optimizer --task="夜間パフォーマンス最適化" --schedule=later --workspace=../claude-squad-workspaces/squad-performance

# 停電対策設定
cs config --auto-save=true --interval=30s
cs config --backup-frequency=1h

# セッション永続化
cs switch performance-night-001
# Ctrl+B, D でデタッチ（バックグラウンド継続）
```

### 朝の夜間作業確認（JST 07:00 / BKK 05:00）
```bash
# 夜間セッション結果確認
cs list --all
cs review performance-night-001

# 夜間作業の統合
if cs status performance-night-001 | grep "completed"; then
    cs merge performance-night-001 --to=integration/squad-merge
    echo "✅ 夜間作業統合完了"
else
    echo "⏳ 夜間作業継続中"
fi
```

## 🚨 緊急対応パターン

### 本番障害対応
```bash
# 緊急調査・修正セッション並列起動
cs spawn --agent=debugger --task="本番障害原因調査" --priority=critical --workspace=../claude-squad-workspaces/squad-core-dev
cs spawn --agent=claude-code --task="ホットフィックス作成" --priority=critical --workspace=../claude-squad-workspaces/squad-security

# 緊急テスト実行
cs spawn --agent=tester --task="緊急回帰テスト" --priority=critical --workspace=../claude-squad-workspaces/squad-testing

# 進捗リアルタイム監視
watch -n 5 'cs list | grep critical'
```

### セキュリティ脆弱性対応
```bash
# セキュリティ専用緊急セッション
cs spawn --agent=security --task="脆弱性対応緊急修正" --priority=critical --workspace=../claude-squad-workspaces/squad-security

# 包括セキュリティチェック
make security-comprehensive

# OWASP準拠確認
uv run pytest tests/security/ -v --tb=short
```

## 📊 効率化・生産性向上パターン

### 定期メンテナンス（週1回）
```bash
# 週次Claude Squadメンテナンス
cs cleanup --days=7                    # 古いセッション削除
cs config --optimize                   # 設定最適化
make squad-status                      # 全体状況確認

# ワークツリー最適化
git worktree prune                     # 不要ワークツリー削除
git gc --aggressive                    # Gitリポジトリ最適化
```

### 月次効果測定
```bash
# 月次Claude Squad効果測定
echo "=== 月次Claude Squad効果レポート ==="
echo "セッション数: $(cs list --all | wc -l)"
echo "品質ゲート合格率: $(make squad-quality && echo 100% || echo 要改善)"
echo "テストカバレッジ: $(uv run pytest --cov=utils --cov=config --cov-report=term | grep TOTAL | awk '{print $4}')"

# パフォーマンス測定
python scripts/run_effectiveness_measurement.py demo
```

## 🎯 コマンド実行例集

### よく使用するコマンドパターン
```bash
# 基本セッション管理
cs list                               # アクティブセッション確認
cs spawn --agent=claude-code --task="開発タスク"  # 新規セッション
cs switch session-id                  # セッション切り替え
cs kill session-id                    # セッション終了

# 作業確認・統合
cs status session-id                  # セッション詳細確認
cs review session-id                  # 変更内容確認
cs merge session-id --to=branch       # ブランチ統合

# 品質・効率管理
make squad-status                     # 全体状況確認
make squad-quality                    # 品質チェック
make squad-integrate                  # 統合実行
make squad-cleanup                    # クリーンアップ
```

### デバッグ・トラブルシューティング
```bash
# セッション問題対応
cs logs session-id                    # セッションログ確認
cs restart session-id                 # セッション再起動
cs recover session-id                 # セッション復旧

# 詳細診断
cs config --debug=true               # デバッグモード有効
cs spawn --verbose --task="テスト"    # 詳細ログ付きセッション
```

## 📈 期待される日常効果

### 定量的効果指標
- **開発速度**: 280-440%向上（並列セッション効果）
- **品質保証**: 85%テストカバレッジ継続維持
- **セキュリティ**: OWASP API Security Top 10準拠継続
- **CI/CD効率**: 10ワークフロー最適化活用
- **時間効率**: 24時間開発パターンでバンコク時差活用

### 定性的効果
- 専門領域集中による開発品質向上
- 並列処理による作業効率大幅改善
- セッション分離による干渉・競合回避
- git worktree活用による安全な実験・開発

## 💡 運用ベストプラクティス

1. **朝の状態確認**: 必ず`cs list --all`と`make squad-status`実行
2. **セッション命名**: 一貫した命名規則維持（機能-用途-番号）
3. **定期統合**: 機能完了毎の`make squad-integrate`実行
4. **品質ゲート**: 作業終了時の品質チェック必須実行
5. **バックアップ**: 重要作業前の状態保存励行

---

この日常ワークフローガイドにより、api-test-devops-portfolioプロジェクトでClaude Squadを最大限活用した効率的な開発が実現できます。