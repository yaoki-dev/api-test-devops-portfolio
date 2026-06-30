# Docker

*最終更新: 2026年06月11日*

## 🐳 Docker環境概要

### 環境構成

- **Base Image**: python:3.14-slim
- **Multi-stage**: base, dependencies, runtime, test
- **最適化**: レイヤーキャッシュ、サイズ削減
- **セキュリティ**: 非rootユーザー、脆弱性対策

## 🏗️ Multi-stage Build設計

### Build Stages

1. **base**: 共通基盤
2. **dependencies**: 依存関係インストール
3. **runtime**: 開発/ステージング/本番 環境
4. **test**: テスト環境

## 🔧 docker compose設定

### 利用可能な設定

- `docker-compose.yml`: 単一ファイルの設計

**Note**:
本プロジェクトでは、単一の runtime image を development / staging / production で共用し、
ENVIRONMENT と環境別 env ファイルで設定と検証ポリシーを環境別に切り替える。
テスト実行は専用 test image に分離し、本番 runtime image にテスト依存を含めない。

## 📦 イメージ最適化

### 実装済み最適化

- Multi-stage build によるサイズ削減
- .dockerignore による不要ファイル除外
- レイヤーキャッシュ最適化
- セキュリティスキャン統合
- SHA256固定
- HEALTHCHECK
- uv syncキャッシュ利用

## 🚀 実行方法

```bash
# 開発環境起動
docker compose up -d

# テスト実行
docker compose --profile test run --rm test

# ステージング実行
ENVIRONMENT=staging docker compose up -d

# 本番ビルド
docker build --target runtime -t app:prod .

# 本番実行
ENVIRONMENT=production docker compose up -d

```

## 起動確認

```bash
# State=running / Health=healthy を確認
docker compose ps

# appコンテナの起動ログを確認し、指定した環境の設定で起動していることを確認
docker compose logs app
```

## 🔍 トラブルシューティング

### 一般的な問題と解決法

- **ビルド失敗**: キャッシュクリア、依存関係確認
- **起動エラー**: ログ確認、ポート競合チェック
- **パフォーマンス**: リソース制限、ボリューム設定

## Demo

本番用イメージである ⁠target: runtime⁠ をビルドした上で、環境変数を切り替えて ⁠staging⁠ 環境として起動したデモをお見せします。
コンテナ自体は本番環境と同一ですが、デモ中のAPIキー漏洩や本番データへの影響を防ぐため、外部注入する設定のみをステージング用の安全なものに切り替えています。

同一runtimeイメージをENVIRONMENT切替でstaging起動。stagingは本番同等にsecret+HTTPSを強制し、欠落時はfail-loudで再起動。設定をイメージに焼かないCD原則を実演します
