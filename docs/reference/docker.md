# Docker

*最終更新: 2026-07-06*

## Docker環境概要

### 環境構成

- **Base Image**: python:3.14-slim
- **Multi-stage**: base, dependencies, runtime, test
- **最適化**: レイヤーキャッシュ、サイズ削減
- **セキュリティ**: 非rootユーザー、脆弱性対策

## Multi-stage Build設計

### Build Stages

1. **base**: 共通基盤
2. **dependencies**: 依存関係インストール
3. **runtime**: 開発/ステージング/本番 環境
4. **test**: テスト環境

## docker compose設定

### 利用可能な設定

- `docker-compose.yml`: 単一ファイルの設計

**Note**:
本プロジェクトでは、単一の runtime image を development / staging / production で共用し、
ENVIRONMENT と環境別 env ファイルで設定と検証ポリシーを環境別に切り替える。
テスト実行は専用 test image に分離し、本番 runtime image にテスト依存を含めない。

## イメージ最適化

### イメージサイズ（実測 2026-07-04）

| イメージ | local image size | compressed pull size |
|---|---:|---:|
| runtime（GHCR公開） | 202 MB（GHCR pull 後） | 48.4 MB |
| test（CI内部） | 577 MB | 非公開 |

- `local image size` は docker images の DISK USAGE / SIZE を採用。
- `compressed pull size` は GHCR の manifest layer size 合計を採用。
- `runtime image` は公開・pull対象のため compressed size を主指標として併記。
- `test image` はローカルテストおよび CI で利用する検証用イメージであり、GHCR へ公開していないため compressed pull size は掲載していません。

### 実装済み最適化

- **python:3.14-slim** ベースを `@sha256` digest で固定（サプライチェーン対策）
- **Multi-stage build**（base / dependencies / runtime / test）で本番 runtime へ dev 依存・テストコードを持ち込まない
- **.dockerignore** で build context から不要物を除外（`**/__pycache__/`・`**/.mypy_cache/` など nested キャッシュを含む。`**/` を付けないと nested ディレクトリを除外できない点に注意）
- **レイヤーキャッシュ + uv sync キャッシュ**でコードのみ変更時のビルドを高速化
- **非 root（appuser）実行**と **HEALTHCHECK**（起動時に config ロードを検証）
- **Trivy** の CVE スキャン統合（CRITICAL/HIGH グリーン時のみ GHCR publish）
- **マルチアーキ publish**（linux/amd64 + linux/arm64）で GHCR runtime を manifest list として公開し、Apple Silicon 等 arm64 ホストでもエミュレーションなしにネイティブ pull/run できる。publish 後に両 arch の manifest 存在と arm64 実行を CI で検証する

## 実行方法

本プロジェクトは「**Build Once, Run Anywhere**」の原則に基づき、コードを内包した1つの不変な共通ランタイム（`runtime` ステージ）を、環境変数（`ENVIRONMENT`）で制御する設計を採用しています。

```bash

# テスト実行
docker compose --profile test run --build --rm test

# 共通runtimeコンテナ起動
docker compose up -d

# 共通runtimeコンテナ起動（Dockerfile・依存関係を変更した場合）
docker compose up -d --build

# ステージング環境で起動
ENVIRONMENT=staging docker compose up -d --build

# 本番環境で起動
ENVIRONMENT=production docker compose up -d --build

```

## 起動確認

```bash
# State=running / Health=healthy を確認
docker compose ps

# appコンテナの起動ログを確認し、指定した環境の設定で起動していることを確認
docker compose logs app
```

## トラブルシューティング

### 一般的な問題と解決法

- **ビルド失敗**: キャッシュクリア、依存関係確認
- **起動エラー**: ログ確認、ポート競合チェック
- **パフォーマンス**: リソース制限、ボリューム設定

## Demo

本番用イメージである ⁠target: runtime⁠ をビルドした上で、環境変数を切り替えて ⁠staging⁠ 環境として起動したデモをお見せします。
コンテナ自体は本番環境と同一ですが、デモ中のAPIキー漏洩や本番データへの影響を防ぐため、外部注入する設定のみをステージング用の安全なものに切り替えています。

同一runtimeイメージをENVIRONMENT切替でstaging起動。stagingは本番同等にsecret+HTTPSを強制し、欠落時はfail-loudで再起動。設定をイメージに焼かないCD原則を実演します
