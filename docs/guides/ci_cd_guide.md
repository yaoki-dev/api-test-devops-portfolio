# CI/CD運用ガイド
*最終更新: 2025年09月23日*

## 🚀 CI/CDパイプライン概要

### パイプライン構成
- **main-ci.yml**: メインパイプライン
- **security-scan.yml**: セキュリティ専用
- **品質ゲート**: カバレッジ80%、セキュリティチェック
- **自動デプロイ**: main ブランチ限定

## 📋 ワークフロー詳細

### Main CI Pipeline
1. **Quality Checks**: Lint, Type Check, Security Scan
2. **Tests**: Unit, Integration, Coverage
3. **Docker**: Build, Test, Push
4. **Quality Gate**: 品質基準チェック
5. **Deploy**: 本番デプロイ（条件付き）

## 🎯 品質ゲート設定

### 設定済み品質基準
- **カバレッジ**: 80%以上
- **セキュリティ**: 高・中危険度 0件
- **テスト**: 全テスト成功
- **Lint**: エラー 0件

## 🔒 セキュリティ統合

### セキュリティチェック
- **SAST**: bandit によるコード解析
- **依存関係**: safety による脆弱性チェック
- **カスタム**: 設定ファイル・機密情報検査
- **レポート**: 自動生成・アーカイブ

## 📊 監視・アラート

### 監視項目
- **パイプライン実行時間**
- **テスト成功率**
- **セキュリティスコア**
- **デプロイ頻度**

## 🔧 運用・保守

### 日常運用

#### ブランチ戦略（Git Flow）

| ブランチ | トリガー | CI実行 |
|---------|---------|--------|
| `feature/*` | PR to develop | pr-validation |
| `develop` | merge | post-merge-validation |
| `release/*` | PR to main | full-test-suite |
| `main` | merge | deployment |
| `hotfix/*` | PR to main | pr-validation + deployment |

**CI/CD対応**: `.github/workflows/ci.yml` L10-12で`main`/`develop`両方対応済み

- **PR レビュー**: 自動チェック + 手動レビュー
- **リリース**: release/*ブランチ → タグ付きリリース
- **ロールバック**: 前バージョンへの自動復旧
