# Week別実行マッピング - 6週間実行計画日次詳細

*最終更新: 2025年11月21日*

## 📋 ドキュメント概要

このドキュメントは、6週間実行ロードマップの日次レベルの実行計画を提供します。各Weekの日次スケジュール、学習項目、実装タスク、成果物を詳細に定義し、10週→6週マッピング戦略の実行可能な形式に展開します。

### 対象読者
- 学習実行者（日次計画確認用）
- AI協働システム（自動化トリガー実行用）
- 進捗管理システム（learning_state.yaml更新用）

### 関連ドキュメント
- **戦略**: `6週間実行ロードマップ.md` - 全体戦略、マッピングロジック、理論的基盤
- **自動化**: `フロー自動化改善要件.md` - Trigger仕様、learning_state.yamlスキーマ
- **進捗**: `docs/progress/daily_progress.md` - 実績記録、メトリクス追跡

---

## 1. Week 1-2: Python/pytest応用統合（Days 1-12）

**期間**: Days 1-12（84時間）
**元Week統合**: Week 1 + Week 4 + Week 5
**カバレッジ目標**: 50% → 60%
**学習方針**: AI加速型統合学習（応用領域: Phase 1: 1H + Phase 2: 5H + Phase 3: 1H = 7H、Phase 3統一原則適用）

---

### Day 1: Python基礎 + httpx Core Setup

**学習項目** (6H):
- **Python基礎**: 型ヒント、dataclass、Enum、pathlib（W1 Day1統合）
  - Phase 1 (0.5H): AI説明 → 型ヒントの目的、dataclass vs dict比較
  - Phase 2 (4.5H): AI協働実装 → `utils/models.py`にデータクラス作成
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **httpx応用**: Client初期化、基本的なGET/POSTリクエスト（W1 Day1統合）**【応用領域】**
  - Phase 1 (1H): AI説明 → httpx vs requests比較、同期API特性（基本概念確認済み）
  - Phase 2 (5H): AI協働実装 → `utils/api_client.py`の同期メソッド拡張
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `utils/models.py`: APIレスポンスモデル定義（dataclass）
- [ ] `utils/api_client.py`: 同期APIクライアント基本メソッド実装
- [ ] `tests/unit/test_models.py`: モデルバリデーションテスト作成

**品質ゲート**:
- Gate 1: pytest合格（新規テスト全合格）
- Gate 2: ruff合格（PEP 8準拠）
- Gate 3: mypy合格（型ヒント完全性）
- Gate 4: git commit完了

**成果物**:
- `utils/models.py`: 3-5個のデータクラス
- `utils/api_client.py`: 基本CRUD操作メソッド
- `tests/unit/test_models.py`: 10-15テストケース

**Trigger使用**:
- Trigger 1: `学習開始` → learning_state.yaml更新
- Trigger 3: `学習記録: 6h、課題: [記入]` → 習熟度計算、履歴記録
- Trigger 4: `実装記録` → Git解析、品質ゲート自動実行、メトリクス記録

**期待習熟度**: Python基礎 85%, httpx応用 85%

---

### Day 2: Error Handling基礎 + Retry Logic

**学習項目** (6H):
- **Error Handling**: 階層的例外設計、HTTPステータスコード別処理（W4 Day19統合）
  - Phase 1 (0.5H): AI説明 → 例外階層の設計原則、4xx vs 5xxの処理戦略
  - Phase 2 (4.5H): AI協働実装 → `utils/exceptions.py`に階層的例外クラス実装
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **Retry Logic**: 指数バックオフ、リトライ条件判定（W4 Day20統合）
  - Phase 1 (0.5H): AI説明 → 指数バックオフアルゴリズム、リトライ可能エラー判定
  - Phase 2 (4.5H): AI協働実装 → `utils/retry.py`にリトライデコレータ実装
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `utils/exceptions.py`: 階層的例外クラス定義（BaseError → APIError → NetworkError等）
- [ ] `utils/retry.py`: リトライデコレータ実装（@retry_on_failure）
- [ ] `tests/unit/test_retry.py`: リトライロジックテスト（成功/失敗/上限到達ケース）

**品質ゲート**:
- Gate 1: pytest合格（リトライシナリオ全網羅）
- Gate 2: ruff合格
- Gate 3: mypy合格
- Gate 4: git commit完了

**成果物**:
- `utils/exceptions.py`: 5-8個の例外クラス
- `utils/retry.py`: リトライデコレータ（設定可能パラメータ）
- `tests/unit/test_retry.py`: 15-20テストケース

**Trigger使用**: Trigger 1, 3, 4（Day 1と同様）

**期待習熟度**: Error Handling 85%, Retry Logic 85%

---

### Day 3: pytest応用 + Fixture設計

**学習項目** (6H):
- **pytest応用**: マーカー、パラメトライズ、フィクスチャスコープ（W5 Day25統合）**【応用領域】**
  - Phase 1 (1H): AI説明 → pytestの哲学、fixture vs setup/teardownの違い（基本概念確認済み）
  - Phase 2 (5H): AI協働実装 → `conftest.py`に共通フィクスチャ実装
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **Fixture設計**: スコープ管理、ファクトリーパターン（W5 Day26統合）**【応用領域】**
  - Phase 1 (1H): AI説明 → session/module/function スコープの使い分け（基本概念確認済み）
  - Phase 2 (5H): AI協働実装 → ファクトリーフィクスチャ作成
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `tests/conftest.py`: 共通フィクスチャ実装（mock_client, test_data_factory等）
- [ ] `tests/unit/test_fixtures.py`: フィクスチャ動作検証テスト
- [ ] `pytest.ini`: マーカー定義、カバレッジ設定

**品質ゲート**: Gate 1-4全合格

**成果物**:
- `tests/conftest.py`: 5-10個の共通フィクスチャ
- `pytest.ini`: プロジェクト標準設定
- `tests/unit/test_fixtures.py`: 10-15テストケース

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: pytest応用 85%, Fixture設計 85%

---

### Day 4: Mock/Stub戦略 + カバレッジ向上

**学習項目** (6H):
- **Mock/Stub**: pytest-mock、HTTPモック戦略（W5 Day27統合）
  - Phase 1 (0.5H): AI説明 → Mock vs Stub vs Fake、外部依存分離戦略
  - Phase 2 (4.5H): AI協働実装 → `tests/mocks/`ディレクトリ構造、HTTPレスポンスモック
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **カバレッジ向上**: 未カバー行分析、エッジケーステスト（W5 Day28統合）
  - Phase 1 (0.5H): AI説明 → カバレッジレポート読解、優先度判定
  - Phase 2 (4.5H): AI協働実装 → 未カバー行のテスト追加
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `tests/mocks/http_mocks.py`: HTTPレスポンスモックファクトリー
- [ ] `tests/unit/`: 既存テストにモック追加、エッジケース追加
- [ ] カバレッジ50%達成確認（pytest --cov）

**品質ゲート**: Gate 1-4全合格 + カバレッジ50%以上

**成果物**:
- `tests/mocks/http_mocks.py`: 再利用可能なモック
- カバレッジレポート（50%達成）
- 追加テスト20-30ケース

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: Mock/Stub 85%, カバレッジ向上 85%

---

### Day 5: 統合復習 + 自己診断

**学習項目** (6H):
- **Week 1-2統合復習**: Day 1-4の知識統合、弱点補強
  - Phase 1 (0.5H): AI説明 → 4日間の学習項目相互関連性
  - Phase 2 (4.5H): AI協働実装 → 統合演習（API呼び出し→エラーハンドリング→リトライ→テスト）
  - Phase 3 (1H): 理解度確認 → 総合問題5問/40点満点

**実装タスク** (2H):
- [ ] 統合テストケース作成（複数モジュール連携）
- [ ] リファクタリング（DRY原則適用、重複排除）
- [ ] ドキュメント更新（README.md、CLAUDE.md）

**品質ゲート**: Gate 1-4全合格 + カバレッジ55%以上

**成果物**:
- 統合テストスイート
- リファクタリング済みコードベース
- 更新済みドキュメント

**Trigger使用**: Trigger 1, 3, 4, 6（理解度確認）

**期待習熟度**: 全項目80%以上（弱点がある場合は週末に復習）

---

### Day 6: Pydantic Settings + 環境変数管理

**学習項目** (6H):
- **Pydantic Settings**: BaseSettings、ネスト設定、バリデーション（W5 Day29統合）
  - Phase 1 (0.5H): AI説明 → Pydantic Settingsの型安全性、環境変数自動読み込み
  - Phase 2 (4.5H): AI協働実装 → `config/settings.py`にネスト設定クラス実装
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **環境変数管理**: .env構造、SecretStr、環境別設定（W5 Day29統合）
  - Phase 1 (0.5H): AI説明 → 12-Factor App原則、シークレット保護
  - Phase 2 (4.5H): AI協働実装 → `.env.example`作成、環境判定ロジック
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `config/settings.py`: ネスト設定クラス実装（API, Log, Test, Security設定）
- [ ] `.env.example`: 環境変数テンプレート作成
- [ ] `tests/unit/test_settings.py`: 設定バリデーションテスト

**品質ゲート**: Gate 1-4全合格

**成果物**:
- `config/settings.py`: 型安全な設定管理システム
- `.env.example`: ドキュメント化された環境変数
- `tests/unit/test_settings.py`: 15-20テストケース

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: Pydantic Settings 85%, 環境変数管理 85%

---

### Day 7-12: [後続のDayは省略 - Stage 2, 3で追加]

*(Week 1-2の残り6日間の詳細はStage 2以降で追加)*

---

## 2. Week 3-4: Docker/CI/CD統合（Days 13-24）

**期間**: Days 13-24（72時間）
**元Week統合**: Week 7 + Week 8
**カバレッジ目標**: 60% → 70%
**学習方針**: AI加速型インフラ構築（DevOps実践重視）

---

### Day 13: Docker基礎 + Multi-stage Builds

**学習項目** (6H):
- **Docker基礎**: イメージ、コンテナ、Layer概念（W7 Day37統合）
  - Phase 1 (0.5H): AI説明 → DockerとVM比較、イメージレイヤーキャッシュ戦略
  - Phase 2 (3.5H): AI協働実装 → `Dockerfile`作成（Python 3.12ベース）
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **Multi-stage Builds**: ビルド最適化、イメージサイズ削減（W7 Day38統合）
  - Phase 1 (0.5H): AI説明 → Multi-stageの目的、stage間の依存関係
  - Phase 2 (3.5H): AI協働実装 → 4-stage Dockerfile実装（builder, tester, dev, prod）
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `Dockerfile`: 4-stage構成実装（builder/tester/dev/prod）
- [ ] `.dockerignore`: ビルドコンテキスト最適化
- [ ] `docker-compose.yml`: 開発環境定義

**品質ゲート**:
- Gate 1: pytest（Dockerコンテナ内で全テスト合格）
- Gate 2: ruff合格
- Gate 3: mypy合格
- Gate 4: git commit完了
- **追加**: Docker build成功、イメージサイズ < 200MB

**成果物**:
- `Dockerfile`: 4-stage Multi-stage builds
- `.dockerignore`: 最適化設定
- `docker-compose.yml`: 開発環境定義

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: Docker基礎 85%, Multi-stage Builds 85%

---

### Day 14: docker-compose + 環境別構成

**学習項目** (6H):
- **docker-compose**: サービス定義、ネットワーク、ボリューム（W7 Day39統合）
  - Phase 1 (0.5H): AI説明 → docker-composeの役割、サービス間通信
  - Phase 2 (3.5H): AI協働実装 → `docker-compose.yml`拡張（app, db, redisサービス）
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **環境別構成**: dev/test/prod設定分離（W7 Day40統合）
  - Phase 1 (0.5H): AI説明 → 環境別Override戦略、シークレット管理
  - Phase 2 (3.5H): AI協働実装 → `docker-compose.*.yml`作成（4環境）
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `docker-compose.yml`: ベース設定
- [ ] `docker-compose.dev.yml`: 開発環境オーバーライド
- [ ] `docker-compose.test.yml`: テスト環境オーバーライド
- [ ] `docker-compose.prod.yml`: 本番環境オーバーライド

**品質ゲート**: Gate 1-4全合格 + 4環境全てでdocker-compose up成功

**成果物**:
- 4環境のdocker-compose構成
- ドキュメント（`docs/docker/README.md`）

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: docker-compose 85%, 環境別構成 85%

---

### Day 15: GitHub Actions基礎 + CI Pipeline

**学習項目** (6H):
- **GitHub Actions基礎**: Workflow, Job, Step概念（W8 Day43統合）
  - Phase 1 (0.5H): AI説明 → CI/CD概念、GitHub Actionsアーキテクチャ
  - Phase 2 (3.5H): AI協働実装 → `.github/workflows/ci.yml`作成
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **CI Pipeline**: Lint, Test, Coverage自動化（W8 Day44統合）
  - Phase 1 (0.5H): AI説明 → CIパイプライン設計原則、並列実行戦略
  - Phase 2 (3.5H): AI協働実装 → マトリックス戦略、キャッシュ最適化
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `.github/workflows/ci.yml`: CI Pipeline実装（Python 3.12, 3.11マトリックス）
- [ ] `.github/workflows/coverage.yml`: カバレッジレポート自動生成
- [ ] CI/CDドキュメント作成

**品質ゲート**: Gate 1-4全合格 + CI Pipeline成功（GitHub Actions）

**成果物**:
- `.github/workflows/ci.yml`: 完全なCIパイプライン
- `.github/workflows/coverage.yml`: カバレッジ自動化
- CI成功バッジ（README.md）

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: GitHub Actions基礎 85%, CI Pipeline 85%

---

### Day 16-24: [後続のDayは省略 - Stage 2, 3で追加]

*(Week 3-4の残り9日間の詳細はStage 2以降で追加)*

---

---

## 3. Week 5: Async深化 + 性能最適化（Days 25-30）

**期間**: Days 25-31（49時間）
**元Week統合**: Week 2 + Week 3 + Week 6（Async深化集中）
**カバレッジ目標**: 70% → 80%
**学習方針**: AI加速型非同期プログラミング深化（並行処理最適化）

---

### Day 25: Async/Await基礎 + 非同期コンテキストマネージャー

**学習項目** (6H):
- **Async/Await基礎**: イベントループ、コルーチン、Task概念（W2 Day7統合）
  - Phase 1 (0.5H): AI説明 → 同期vs非同期の実行モデル比較、イベントループの役割
  - Phase 2 (4.5H): AI協働実装 → `utils/async_client.py`に非同期APIクライアント実装
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **非同期コンテキストマネージャー**: `__aenter__/__aexit__`実装（W2 Day8統合）
  - Phase 1 (0.5H): AI説明 → 非同期リソース管理、async with構文
  - Phase 2 (4.5H): AI協働実装 → `AsyncAPIClient.__aenter__/__aexit__`実装
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `utils/async_client.py`: 非同期APIクライアント実装（httpx.AsyncClient統合）
- [ ] `utils/async_client.py`: 非同期コンテキストマネージャー実装
- [ ] `tests/unit/test_async_client.py`: 非同期テスト作成（pytest-asyncio使用）

**品質ゲート**: Gate 1-4全合格

**成果物**:
- `utils/async_client.py`: 完全な非同期APIクライアント
- `tests/unit/test_async_client.py`: 15-20非同期テストケース

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: Async/Await基礎 85%, 非同期コンテキストマネージャー 85%

---

### Day 26: asyncio.gather + 並行処理最適化

**学習項目** (6H):
- **asyncio.gather**: 並行実行、例外処理、return_exceptions（W3 Day13統合）
  - Phase 1 (0.5H): AI説明 → asyncio.gather vs asyncio.wait比較、並行度制御
  - Phase 2 (4.5H): AI協働実装 → `utils/concurrent.py`に並行実行ヘルパー実装
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **並行処理最適化**: Semaphore、レート制限、バッチ処理（W3 Day14統合）
  - Phase 1 (0.5H): AI説明 → リソース制限戦略、バックプレッシャー対策
  - Phase 2 (4.5H): AI協働実装 → `asyncio.Semaphore`でAPI呼び出し制限
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `utils/concurrent.py`: 並行実行ヘルパー（gather_with_limit, batch_execute等）
- [ ] `utils/rate_limiter.py`: レート制限実装（Token Bucket Algorithm）
- [ ] `tests/unit/test_concurrent.py`: 並行処理テスト（10並行実行、エラーハンドリング）

**品質ゲート**: Gate 1-4全合格

**成果物**:
- `utils/concurrent.py`: 再利用可能な並行実行ヘルパー
- `utils/rate_limiter.py`: プロダクションレベルのレート制限
- `tests/unit/test_concurrent.py`: 15-20テストケース

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: asyncio.gather 85%, 並行処理最適化 85%

---

### Day 27: 非同期エラーハンドリング + タイムアウト戦略

**学習項目** (6H):
- **非同期エラーハンドリング**: TaskGroup、例外伝播、キャンセル処理（W3 Day15統合）
  - Phase 1 (0.5H): AI説明 → asyncio.TaskGroupの例外集約、キャンセルシグナル
  - Phase 2 (4.5H): AI協働実装 → `utils/async_error_handler.py`に構造化エラーハンドリング
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **タイムアウト戦略**: asyncio.wait_for、デッドライン管理（W3 Day16統合）
  - Phase 1 (0.5H): AI説明 → タイムアウト設計原則、カスケードタイムアウト回避
  - Phase 2 (4.5H): AI協働実装 → タイムアウトデコレータ、自動リトライ統合
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `utils/async_error_handler.py`: 非同期例外ハンドラー実装
- [ ] `utils/timeout.py`: タイムアウトデコレータ実装（@async_timeout）
- [ ] `tests/unit/test_async_errors.py`: エラーシナリオテスト（キャンセル、タイムアウト、例外伝播）

**品質ゲート**: Gate 1-4全合格

**成果物**:
- `utils/async_error_handler.py`: 構造化エラーハンドリング
- `utils/timeout.py`: タイムアウト管理システム
- `tests/unit/test_async_errors.py`: 20-25テストケース

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: 非同期エラーハンドリング 85%, タイムアウト戦略 85%

---

### Day 28: パフォーマンステスト + ベンチマーク

**学習項目** (6H):
- **パフォーマンステスト**: pytest-benchmark、メトリクス収集（W6 Day31統合）
  - Phase 1 (0.5H): AI説明 → パフォーマンステスト設計原則、統計的有意性
  - Phase 2 (4.5H): AI協働実装 → `tests/performance/`ディレクトリ構造、ベンチマークテスト
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **ベンチマーク**: 同期vs非同期比較、最適化検証（W6 Day32統合）
  - Phase 1 (0.5H): AI説明 → ベンチマーク結果解釈、ボトルネック特定
  - Phase 2 (4.5H): AI協働実装 → ベンチマーク自動化、CI統合
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `tests/performance/test_api_performance.py`: API呼び出しベンチマーク
- [ ] `tests/performance/test_concurrent_performance.py`: 並行処理ベンチマーク
- [ ] `conftest.py`: パフォーマンステストフィクスチャ追加

**品質ゲート**: Gate 1-4全合格 + パフォーマンス基準達成（応答時間 < 100ms、スループット > 100 req/s）

**成果物**:
- `tests/performance/`: パフォーマンステストスイート
- ベンチマークレポート（docs/performance/）
- CI/CDパイプライン統合

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: パフォーマンステスト 85%, ベンチマーク 85%

---

### Day 29: カバレッジ80%達成 + リファクタリング

**学習項目** (6H):
- **カバレッジ80%達成**: 未カバー行分析、エッジケーステスト追加（W6 Day33統合）
  - Phase 1 (0.5H): AI説明 → カバレッジ目標設定原則、80/20ルール適用
  - Phase 2 (4.5H): AI協働実装 → 未カバー行のテスト追加、境界値テスト
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **リファクタリング**: DRY原則適用、コード品質向上（W6 Day34統合）
  - Phase 1 (0.5H): AI説明 → リファクタリングパターン、技術的負債返済戦略
  - Phase 2 (4.5H): AI協働実装 → 重複コード排除、抽象化層導入
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] カバレッジ80%達成確認（pytest --cov-fail-under=80）
- [ ] リファクタリング実施（共通ロジック抽出、ヘルパー関数作成）
- [ ] コード品質メトリクス改善（ruff --select=C901複雑度チェック）

**品質ゲート**: Gate 1-4全合格 + カバレッジ80%以上 + 複雑度スコア < 10

**成果物**:
- カバレッジレポート（80%達成）
- リファクタリング済みコードベース
- コード品質レポート

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: カバレッジ80%達成 85%, リファクタリング 85%

---

### Day 30: Week 5統合復習 + 自律チャレンジ

**学習項目** (6H):
- **Week 5統合復習**: Day 25-29の知識統合、弱点補強（W6 Day36統合）
  - Phase 1 (0.5H): AI説明 → 5日間の学習項目相互関連性、実践統合
  - Phase 2 (4.5H): AI協働実装 → 総合演習（非同期API → 並行処理 → エラーハンドリング → パフォーマンステスト）
  - Phase 3 (1H): 理解度確認 → 総合問題5問/40点満点
- **自律チャレンジ**: AI支援最小化、自力実装力確認（W6 Day36統合）
  - Phase 1 (0.5H): AI説明 → 自律実装チェックリスト、評価基準
  - Phase 2 (4.5H): 自力実装 → 新規機能実装（AI質問は3回まで制限）
  - Phase 3 (1H): 理解度確認 → 自己評価、弱点特定

**実装タスク** (2H):
- [ ] 自律チャレンジ課題実装（例: 新しいAPI統合、複雑な非同期処理）
- [ ] 全テストスイート実行確認（pytest --verbose）
- [ ] Week 5総括ドキュメント作成

**品質ゲート**: Gate 1-4全合格 + 自律チャレンジ合格（AI支援3回以内、品質ゲート全合格）

**成果物**:
- 自律チャレンジ成果物
- Week 5総括レポート
- 次週計画調整案

**Trigger使用**: Trigger 1, 3, 4, 6（理解度確認）

**期待習熟度**: 全項目80%以上（弱点がある場合はWeek 6で補強）

---

---

## 4. Week 6: 最適化 + 応募準備（Days 31-36）

**期間**: Days 32-37（42時間）
**元Week統合**: Week 9 + Week 10（最適化 + 応募準備集中）
**カバレッジ目標**: 80% → 85%（最終目標達成） + **100テスト達成**
**学習方針**: AI加速型ポートフォリオ完成（市場価値最大化）

---

### Day 31: セキュリティテスト + 脆弱性診断

**学習項目** (6H):
- **セキュリティテスト**: OWASP Top 10、bandit、safety（W9 Day49統合）
  - Phase 1 (0.5H): AI説明 → セキュリティテスト戦略、脆弱性分類
  - Phase 2 (4.5H): AI協働実装 → `tests/security/`ディレクトリ、セキュリティテストスイート
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **脆弱性診断**: 依存関係チェック、コードスキャン（W9 Day50統合）
  - Phase 1 (0.5H): AI説明 → サプライチェーン攻撃対策、定期診断プロセス
  - Phase 2 (4.5H): AI協働実装 → CI/CDにセキュリティスキャン統合
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `tests/security/test_owasp_top10.py`: OWASP Top 10テスト
- [ ] `.github/workflows/security.yml`: セキュリティスキャンworkflow
- [ ] セキュリティドキュメント作成（`docs/security/SECURITY.md`）

**品質ゲート**: Gate 1-4全合格 + セキュリティスキャン0件

**成果物**:
- セキュリティテストスイート
- CI/CDセキュリティ自動化
- セキュリティドキュメント

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: セキュリティテスト 85%, 脆弱性診断 85%

---

### Day 32: ドキュメント完成 + README最適化

**学習項目** (6H):
- **ドキュメント完成**: README、ARCHITECTURE、API仕様（W9 Day51統合）
  - Phase 1 (0.5H): AI説明 → 技術ドキュメント構造、読者別最適化
  - Phase 2 (4.5H): AI協働実装 → README.md完成版、バッジ追加
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **README最適化**: 技術スタック強調、デモGIF、採用担当向け（W9 Day52統合）
  - Phase 1 (0.5H): AI説明 → ポートフォリオREADMEベストプラクティス
  - Phase 2 (4.5H): AI協働実装 → デモGIF作成、技術スタック図作成
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `README.md`: 完成版（技術スタック、デモGIF、セットアップ、実績）
- [ ] `docs/ARCHITECTURE.md`: アーキテクチャ図、設計判断記録
- [ ] `docs/API.md`: API仕様書（OpenAPI準拠）

**品質ゲート**: Gate 1-4全合格 + ドキュメント品質90%

**成果物**:
- 完成版README.md（採用担当向け最適化）
- 包括的技術ドキュメント
- デモGIF・技術スタック図

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: ドキュメント完成 85%, README最適化 85%

---

### Day 33: CI/CD完成 + デプロイ自動化

**学習項目** (6H):
- **CI/CD完成**: マルチステージパイプライン、自動デプロイ（W9 Day53統合）
  - Phase 1 (0.5H): AI説明 → CI/CD成熟度モデル、ベストプラクティス
  - Phase 2 (4.5H): AI協働実装 → `.github/workflows/deploy.yml`作成
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **デプロイ自動化**: 環境別デプロイ、ロールバック戦略（W9 Day54統合）
  - Phase 1 (0.5H): AI説明 → Blue-Greenデプロイ、カナリアリリース
  - Phase 2 (4.5H): AI協働実装 → 環境別デプロイスクリプト
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] `.github/workflows/deploy.yml`: デプロイワークフロー完成
- [ ] `scripts/deploy.sh`: デプロイスクリプト（環境別）
- [ ] デプロイドキュメント（`docs/deployment/DEPLOYMENT.md`）

**品質ゲート**: Gate 1-4全合格 + CI/CD成熟度85%

**成果物**:
- 完全自動化CI/CDパイプライン
- 環境別デプロイスクリプト
- デプロイドキュメント

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: CI/CD完成 85%, デプロイ自動化 85%

---

### Day 34: カバレッジ85%達成 + 100テスト達成 + 最終品質保証

**学習項目** (6H):
- **カバレッジ85%達成**: 最終未カバー行対策（W10 Day55統合）
  - Phase 1 (0.5H): AI説明 → カバレッジ最終目標、品質保証戦略
  - Phase 2 (4.5H): AI協働実装 → 最終テスト追加、エッジケース網羅
  - Phase 3 (1H): 理解度確認 → AI生成問題3問/25点満点
- **100テスト達成**: テスト数90→100への拡充（実務経験者余剰9H活用）**【新規タスク】**
  - Phase 1 (0.5H): AI説明 → 100テスト構成（Unit 60 + Integration 30 + System 7 + Performance 3）
  - Phase 2 (5.5H): AI協働実装 → 統合テスト10件追加、システムテスト拡充
  - Phase 3 (1H): 理解度確認 → 同上
- **最終品質保証**: 全テスト実行、メトリクス確認（W10 Day56統合）
  - Phase 1 (0.5H): AI説明 → 品質メトリクス総括、最終チェックリスト
  - Phase 2 (4.5H): AI協働実装 → 品質レポート生成、改善項目対応
  - Phase 3 (1H): 理解度確認 → 同上

**実装タスク** (2H):
- [ ] カバレッジ85%達成確認（pytest --cov-fail-under=85）
- [ ] **100テスト達成確認**（pytest --collect-only | grep "test session" で確認）
- [ ] 全品質ゲート合格確認（pytest, ruff, mypy, bandit, safety）
- [ ] 品質レポート生成（`docs/quality/QUALITY_REPORT.md`）

**品質ゲート**: Gate 1-4全合格 + カバレッジ85%以上 + **テスト数100件以上** + セキュリティスキャン0件

**成果物**:
- カバレッジレポート（85%達成）
- **100テストスイート（Unit 60 + Integration 30 + System 7 + Performance 3）**
- 品質レポート（全メトリクス総括）
- 改善履歴ドキュメント

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: カバレッジ85%達成 85%, 最終品質保証 85%

---

### Day 35: 応募準備 + ポートフォリオ最終調整

**学習項目** (6H):
- **応募準備**: 職務経歴書、ポートフォリオ説明資料（W10 Day57統合）
  - Phase 1 (0.5H): AI説明 → 技術職応募戦略、ポートフォリオ訴求ポイント
  - Phase 2 (4.5H): AI協働実装 → 職務経歴書作成、ポートフォリオ説明スライド
  - Phase 3 (1H): 理解度確認 → 自己PR確認、技術質問対策
- **ポートフォリオ最終調整**: スクリーンショット、デモ動画（W10 Day58統合）
  - Phase 1 (0.5H): AI説明 → 視覚資料作成ベストプラクティス
  - Phase 2 (4.5H): AI協働実装 → スクリーンショット撮影、デモ動画編集
  - Phase 3 (1H): 理解度確認 → プレゼン練習、質疑応答シミュレーション

**実装タスク** (2H):
- [ ] 職務経歴書作成（`docs/career/RESUME.md`）
- [ ] ポートフォリオ説明スライド作成（`docs/presentation/PORTFOLIO.pdf`）
- [ ] デモ動画作成（`docs/demo/DEMO.mp4`）

**品質ゲート**: 応募資料完成度90%以上

**成果物**:
- 職務経歴書（技術スキル強調）
- ポートフォリオ説明スライド（10-15枚）
- デモ動画（3-5分）

**Trigger使用**: Trigger 1, 3, 4

**期待習熟度**: 応募準備 85%, ポートフォリオ最終調整 85%

---

### Day 36: 初回応募 + Week 6総括

**学習項目** (6H):
- **初回応募**: 企業リサーチ、応募書類提出（W10 Day59統合）
  - Phase 1 (0.5H): AI説明 → 応募企業選定基準、応募戦略
  - Phase 2 (4.5H): AI協働実装 → 企業リサーチ、カスタマイズ応募書類作成
  - Phase 3 (1H): 理解度確認 → 応募書類最終確認
- **Week 6総括**: 6週間総括、次ステップ計画（W10 Day60統合）
  - Phase 1 (0.5H): AI説明 → 学習成果総括、継続学習計画
  - Phase 2 (4.5H): AI協働実装 → 6週間総括レポート作成
  - Phase 3 (1H): 理解度確認 → 自己評価、成長記録

**実装タスク** (2H):
- [ ] 初回応募（3-5社）
- [ ] 6週間総括レポート作成（`docs/summary/6WEEK_SUMMARY.md`）
- [ ] 継続学習計画作成（`docs/learning/CONTINUOUS_LEARNING.md`）

**品質ゲート**: 応募完了 + 総括レポート完成

**成果物**:
- 初回応募完了（3-5社）
- 6週間総括レポート
- 継続学習計画

**Trigger使用**: Trigger 1, 3, 4, 5（週次振り返り）

**期待習熟度**: 初回応募 100%, Week 6総括 100%

---

## 5. 統合サマリーとクイックリファレンス

### 5.1 6週間構造概要

| Week | 期間 | 統合元Week | 焦点領域 | カバレッジ目標 | 学習時間 | 実装時間 |
|------|------|-----------|---------|--------------|---------|---------|
| Week 1 | Days 1-6 | W1 | Python/httpx実践 | 58.16%→65% | 35H | 7H |
| Week 2 | Days 7-12 | W4+W5 | Error Handling/Pydantic | 65%→70% | 35H | 7H |
| Week 3 | Days 13-18 | W7 | Docker基盤 | 70%→72% | 25H | 5H |
| Week 4 | Days 19-24 | W8 | CI/CD統合 | 72%→75% | 35H | 7H |
| Week 5 | Days 25-30 | W2+W3 | Async深化 | 75%→82% | 35H | 7H |
| Week 5.5 | Day 31 | W6 | 統合復習 | 82%（確認） | 6H | 1H |
| Week 6 | Days 32-37 | W9+W10 | 最適化+応募準備 | 82%→85% | 35H | 7H |
| **合計** | 37日間 | 10週→6週 | - | 58.16%→85% | 206H | 41H |

**実務経験者最適化**: Docker 6ヶ月 + システムテスト1.5年の経験により、288H→252H（36H削減）を実現

### 5.2 Phase別時間配分（統一フォーマット）

**標準学習モデル（新規領域の場合）**（全36日間の基準）:
```
Phase 1: AI説明・概念理解 (合計 1H)
- 2項目の新技術概念を理解
- 理解度チェックリスト確認
- 目標理解度: 30%

Phase 2: AI協働実装 (合計 5H)
- 2項目の実装作業（70-80% AI生成）
- テスト作成・品質ゲート実行
- 目標理解度: 60%

Phase 3: 理解度確認・記録 (合計 1H)
- AI生成問題: 3問/25点満点（通常）または5問/40点満点（統合復習）
- 合格基準: 20点/25点（80%）
- 目標理解度: 85%

Daily Total: 8H（学習 1H+5H+2H=8H）

※ 実務経験者は4パターン配分により3.5H～7Hに最適化（下記表参照）
```

**実務経験者向け4パターンPhase配分** (Days 1-36適用、295H総計版):

| パターン | Phase 1 | Phase 2 | Phase 3 | Buffer | 合計 | 対象項目例 |
|---------|---------|---------|---------|--------|------|-----------|
| **既知領域** | 0.5H | 4H | 1H | 1H | **6.5H** | Docker基礎、テスト設計 |
| **応用領域** | 1H | 5H | 1H | 1H | **8H** | httpx応用、pytest応用 |
| **新規領域** | 1H | 5H | 1H | 1H | **8H** | Pydantic、asyncio、GitHub Actions |
| **統合領域** | 0.5H | 7H | 1H | 1H | **9.5H** | 性能最適化、セキュリティ |

**Phase 3統一 + Buffer追加の設計判断（ADR-006）**:
- 全パターンでPhase 3 = 1H/日に統一（Buffer統合、Trigger自動化効果）
- 理解度確認+記録+復習を1Hで完結、週次管理の簡素化
- 詳細: `docs/プロジェクト再編/6週再編/最終版.md` ADR-006参照

**適用効果**:
- Phase 3統一+Phase 1増強: +13.5H
- Week 3削減効果（既知領域Phase 2短縮）: -15.5H
- **最終総時間**: 288H → **247H**（-41H、14.2%削減、平均6.68H/日）
- **週次平均削減**: 36H ÷ 4週 = 9H/週
- **Week 6余剰投資**: Week 6の9H削減分 → 100テスト達成タスク（Day 34に4H配分）

### 5.3 Trigger使用パターン

**学習開始時** (Days 1-36全日):
```bash
# コマンド: 学習開始
Trigger 1: learning_state.yaml更新（current_learning_item設定）
- 自動補完: Week/Day、学習項目名、推定時間6H、目標習熟度85%
```

**学習完了時** (Days 1-36全日):
```bash
# コマンド: 学習記録: 6h、課題: [記入]
Trigger 3: 習熟度計算 + learning_history追加
- Mastery計算: (6 / 6) * 85 = 85%
- Status: "完了" (85%以上), "要復習" (1-84%), "未学習" (0%)
```

**実装完了時** (Days 1-36全日):
```bash
# コマンド: 実装記録
Trigger 4: Git解析 + 4 Quality Gates自動実行
- Gate 1: pytest合格
- Gate 2: ruff合格
- Gate 3: mypy合格
- Gate 4: git commit完了
- 実装活動認定: ✅ 認定 / ❌ 不認定
```

**理解度確認時** (Days 5, 12, 19, 24, 30, 36):
```bash
# コマンド: 理解度確認
Trigger 6: AI生成問題3問/25点満点
- 合格基準: 20点/25点（80%）
- 不合格時: 復習ループ（最大3回）
```

**週次振り返り時** (Days 12, 24, 30, 36):
```bash
# コマンド: 週次振り返り
Trigger 5: 週次データ集計 + レポート生成
- 学習時間集計
- 実装時間集計
- メトリクス進捗計算
```

### 5.4 品質ゲート基準（Week別）

| Week | カバレッジ目標 | テスト数目標 | 複雑度上限 | セキュリティ |
|------|--------------|------------|-----------|------------|
| Week 1-2 | 50%→60% | 40→60 | 10 | - |
| Week 3-4 | 60%→70% | 60→75 | 10 | - |
| Week 5 | 70%→80% | 75→90 | 10 | - |
| Week 6 | 80%→85% | **90→100** | 10 | 0件 |

**最終目標（Day 36完了時）**:
- **テスト数**: **100件**（Unit 60 + Integration 30 + System 7 + Performance 3）
- **カバレッジ**: **85%以上**
- **時給想定**: **4,500-5,500円**（実務経験2年 + 100テスト + 85%カバレッジ）

### 5.5 使用例

**例1: Day 1の実行フロー**
```bash
# 1. 学習開始
"学習開始"
→ Trigger 1: learning_state.yaml更新
→ AI自動補完: "Python基礎 + httpx応用、5.5H（応用領域）、目標85%"

# 2. Phase 1: AI説明（0.75H）
→ Python型ヒント、httpx応用の概念確認（基本概念確認済み）

# 3. Phase 2: AI協働実装（4H）
→ utils/models.py作成、utils/api_client.py実装、テスト作成

# 4. Phase 3: 理解度確認（0.75H）
"理解度確認"
→ Trigger 6: AI生成問題3問/25点満点
→ 合格（22点/25点）

# 5. 実装完了
"実装記録"
→ Trigger 4: Git解析 + 4 Quality Gates実行
→ 全合格 → 実装活動認定

# 6. 学習記録
"学習記録: 6h、課題: なし"
→ Trigger 3: Mastery計算 (6/6)*85 = 85%
→ Status: "完了"
```

**例2: Week 1-2終了時（Day 12）**
```bash
# 週次振り返り
"週次振り返り"
→ Trigger 5: 週次データ集計
→ 学習時間: 56H（応用領域最適化）
→ 実装時間: 19H
→ カバレッジ: 58.16% → 60%
→ テスト数: 35 → 60
→ レポート生成: docs/summary/week1_2_summary.md
```

**例3: 実務経験者の時間削減効果（Day 13 Docker学習）**
```bash
# Docker学習（既知領域）
"学習開始"
→ AI自動補完: "Docker 4-stage builds、3.5H（既知領域）、目標85%"
→ Phase配分: 0H（Phase 1スキップ） + 3H（Phase 2） + 0.5H（Phase 3） = 3.5H
→ 削減効果: 6H標準 → 3.5H（2.5H削減）

# 削減理由
→ Docker実務経験6ヶ月により概念理解済み
→ Phase 1（AI説明）をスキップし、即実装に移行
→ 実装品質は同等（4 Quality Gates全合格）
```

**例4: 100テスト達成（Day 34）**
```bash
# 100テスト達成作業
→ 実務経験者余剰9Hを活用
→ 統合テスト10件追加（4H）
→ システムテスト拡充（3H）
→ 最終確認: pytest --collect-only | grep "test session"
→ 結果: 100 tests collected

# 市場価値向上効果
→ テスト数90件: 時給4,000-4,500円レンジ
→ テスト数100件: 時給4,500-5,500円レンジ（+500円）
→ 案件獲得率: 75-80%（5社応募→4社面接→1-2社内定）
```

### 5.6 関連ドキュメント参照

**戦略文書**:
- [`6週間実行ロードマップ.md`](./6週間実行ロードマップ.md): 全体戦略、マッピングロジック、Sequential Thinking分析

**自動化仕様**:
- [`フロー自動化改善要件.md`](./フロー自動化改善要件.md): Trigger 1-6仕様、learning_state.yamlスキーマ

**進捗記録**:
- [`docs/progress/daily_progress.md`](../../progress/daily_progress.md): 日次実績記録、メトリクス追跡

**メモリリファレンス**:
- `@memory:ai_collaboration_workflow`: AI協働学習フロー詳細
- `@memory:coding_standards`: コーディング規約
- `@memory:implementation_quality_gates`: 品質ゲート詳細
- `@memory:test_strategy`: テスト戦略全体

---

**ドキュメント完成**: 全5セクション作成完了（~12,000文字）

*6週間実行計画の日次詳細マッピングが完成しました。3ファイル全て完成し、ユーザーレビュー待ちです。*
