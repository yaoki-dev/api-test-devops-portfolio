# Docker活用ガイド

*最終更新: 2025年09月23日*

## 🐳 Docker環境概要

### 環境構成

- **Base Image**: python:3.11-slim
- **Multi-stage**: development, test, production
- **最適化**: レイヤーキャッシュ、サイズ削減
- **セキュリティ**: 非rootユーザー、脆弱性対策

## 🏗️ Multi-stage Build設計

### Build Stages

1. **base**: 共通基盤
2. **dependencies**: 依存関係インストール
3. **development**: 開発環境
4. **test**: テスト環境
5. **production**: 本番環境（最小構成）

## 🔧 docker-compose設定

### 利用可能な設定

- `docker-compose.yml`: 基本開発環境
- `docker-compose.dev.yml`: 開発特化
- `docker-compose.test.yml`: テスト環境
- `docker-compose.ci.yml`: CI専用

## 📦 イメージ最適化

### 実装済み最適化

- Multi-stage build によるサイズ削減
- .dockerignore による不要ファイル除外
- レイヤーキャッシュ最適化
- セキュリティスキャン統合

## 🚀 実行方法

```bash
# 開発環境起動
docker-compose up -d

# テスト実行
docker-compose -f docker-compose.test.yml run tests

# 本番ビルド
docker build --target production -t app:prod .
```

## 🔍 トラブルシューティング

### 一般的な問題と解決法

- **ビルド失敗**: キャッシュクリア、依存関係確認
- **起動エラー**: ログ確認、ポート競合チェック
- **パフォーマンス**: リソース制限、ボリューム設定
