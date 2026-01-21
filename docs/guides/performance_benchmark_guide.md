# パフォーマンスベンチマークガイド

*最終更新: 2025年09月23日*

## 📋 目次

1. [概要](#概要)
2. [テスト実行方法](#テスト実行方法)
3. [ベンチマーク基準値](#ベンチマーク基準値)
4. [結果の読み方](#結果の読み方)
5. [改善指針](#改善指針)
6. [詳細テスト説明](#詳細テスト説明)
7. [トラブルシューティング](#トラブルシューティング)

## 概要

このガイドでは、プロジェクトのパフォーマンステストスイートの使用方法、結果の解釈、および改善指針について説明します。5つの主要なテスト領域をカバーしています：

### テスト領域一覧

| テスト種別 | ファイル | 目的 | 重要度 |
|-----------|---------|------|-------|
| **APIパフォーマンス** | `test_api_performance.py` | レスポンス時間・スループット基準測定 | 🔴 HIGH |
| **ベンチマーク** | `test_benchmark.py` | 統計的信頼性のある性能測定・回帰検出 | 🔴 HIGH |
| **負荷テスト** | `test_load_testing.py` | 段階的負荷増加・容量限界検出 | 🟡 MEDIUM |
| **並行性テスト** | `test_concurrency.py` | 同時実行・競合状態検出 | 🟡 MEDIUM |
| **ストレステスト** | `test_stress_testing.py` | 破壊点検出・回復力評価 | 🟢 LOW |
| **リソース監視** | `test_resource_monitoring.py` | CPU・メモリ・ネットワーク監視 | 🟡 MEDIUM |

## テスト実行方法

### クイック実行コマンド

```bash
# 🚀 最重要：APIパフォーマンス基準測定
make test-performance-quick

# 📊 完全性能測定（推奨：週1回）
make test-performance-comprehensive

# 🔍 特定テスト実行
pytest tests/performance/test_api_performance.py -v
pytest tests/performance/test_benchmark.py -v
pytest tests/performance/test_load_testing.py -v
```

### 詳細実行オプション

```bash
# ベンチマークマーク付きテスト実行
pytest -m benchmark tests/performance/ -v

# 負荷テスト実行（時間がかかります）
pytest -m load_test tests/performance/ -v --tb=short

# 外部APIテスト実行
pytest -m external tests/performance/ -v

# パフォーマンスレポート生成付き実行
pytest tests/performance/ --benchmark-json=reports/benchmark.json -v
```

### 並列実行

```bash
# 効率的な並列実行（推奨）
pytest tests/performance/ -n 4 --dist worksteal -v

# リソース監視は単独実行推奨
pytest tests/performance/test_resource_monitoring.py -v
```

## ベンチマーク基準値

### 🎯 目標性能基準

| メトリクス | 基準値 | 許容範囲 | 警告閾値 |
|-----------|--------|---------|---------|
| **レスポンス時間（平均）** | 2.0秒以下 | 3.0秒以下 | 5.0秒以上 |
| **95パーセンタイル** | 3.0秒以下 | 5.0秒以下 | 10.0秒以上 |
| **スループット** | 10 req/sec以上 | 5 req/sec以上 | 1 req/sec未満 |
| **エラー率** | 5%以下 | 10%以下 | 15%以上 |
| **メモリ増加** | 50MB以下 | 100MB以下 | 200MB以上 |
| **CPU使用率（ピーク）** | 80%以下 | 90%以下 | 95%以上 |

### 🔄 運用環境別基準

#### 開発環境

- レスポンス時間：5.0秒以下
- エラー率：15%以下
- 目的：基本機能確認

#### ステージング環境

- レスポンス時間：3.0秒以下
- エラー率：10%以下
- 目的：本番環境準拠テスト

#### 本番環境

- レスポンス時間：2.0秒以下
- エラー率：5%以下
- 目的：ユーザー体験保証

### 📊 ベースライン値（JSONPlaceholder API特性対応）

```python
BASELINE_RESPONSE_TIMES = {
    "get_user": 0.5,      # ユーザー情報取得
    "get_post": 0.5,      # 投稿取得
    "get_todo": 0.5,      # TODO取得
    "get_comment": 0.5,   # コメント取得
    "get_album": 0.5,     # アルバム取得
    "batch_operation": 2.0,    # バッチ操作
    "complex_workflow": 3.0,   # 複雑ワークフロー
}

# 回帰検出閾値
REGRESSION_THRESHOLD_PERCENT = 20.0  # 20%以上の劣化で回帰と判定
```

## 結果の読み方

### 📈 基本メトリクス

#### レスポンス時間統計

```
📊 単一リクエストパフォーマンス: 0.245s
  - 平均実行時間: 1.234s
  - 最小実行時間: 0.890s
  - 最大実行時間: 2.567s
  - 標準偏差: 0.123s
  - P95: 2.100s  # 95%のリクエストがこの時間以下
  - P99: 2.400s  # 99%のリクエストがこの時間以下
```

**解釈：**

- **平均値**：一般的な性能指標
- **P95/P99**：ユーザー体験の実際の指標（重要）
- **標準偏差**：安定性の指標（小さいほど安定）

#### スループット・エラー率

```
📊 並行リクエストパフォーマンス:
  - リクエスト数: 50
  - 成功率: 96.0%
  - スループット: 8.7 req/s
  - メモリ増加: 12.3MB
```

**解釈：**

- **成功率**：95%以上が理想
- **スループット**：処理能力の指標
- **メモリ増加**：メモリリーク検出指標

### 🔍 ベンチマーク比較

```
📊 ベンチマーク結果:
  平均実行時間: 0.523s
  ベースライン比較: +12.5% ⚠️ 劣化
  回帰検出: いいえ
  測定安定性: 0.045 (安定)
```

**回帰判定基準：**

- **+20%以上**：🔴 回帰あり（改善必要）
- **+10-20%**：🟡 注意監視
- **±10%以内**：🟢 正常範囲

### 📊 負荷テスト結果

```
📊 段階的負荷増加総合分析:
  📈 スループット推移: 12.1 → 10.8 → 8.9 → 6.2 req/s
  ⏱️ 平均レスポンス時間推移: 1.2s → 1.8s → 2.4s → 3.9s
  ❌ エラー率推移: 2.0% → 4.1% → 8.3% → 15.7%
  🎯 推定安定容量: 15ユーザー
```

**容量評価：**

- **エラー率 < 10%**：安定容量
- **エラー率 10-20%**：限界容量
- **エラー率 > 20%**：不安定領域

### 🔧 リソース監視結果

```
📊 workload_medium リソース使用量分析:
  ピークCPU使用率: 67.2%
  平均CPU使用率: 45.1%
  ピークメモリ使用量: 234.5MB
  メモリ増加量: 23.7MB
  CPUスパイク数: 3
  メモリリーク検出: いいえ
```

**リソース評価基準：**

- **CPU < 80%**：正常
- **メモリ増加 < 100MB**：正常
- **メモリリーク**：要対策

## 改善指針

### 🚀 性能改善プライオリティ

#### 1. 🔴 緊急対応（即座に対応）

- **レスポンス時間 > 5秒**
- **エラー率 > 15%**
- **メモリリーク検出**
- **CPU使用率 > 95%**

```bash
# 緊急時の詳細調査
pytest tests/performance/test_api_performance.py::TestAPIPerformance::test_single_request_performance -v -s
pytest tests/performance/test_resource_monitoring.py::TestResourceMonitoring::test_memory_leak_detection -v -s
```

#### 2. 🟡 計画的改善（週内対応）

- **レスポンス時間 3-5秒**
- **エラー率 10-15%**
- **メモリ増加 100-200MB**
- **回帰検出**

#### 3. 🟢 最適化（月内対応）

- **レスポンス時間 2-3秒**
- **エラー率 5-10%**
- **スループット向上**

### 🛠️ 具体的改善手法

#### レスポンス時間改善

```python
# 並行処理の活用
async def improved_batch_operations():
    tasks = [
        api_client.get_user(1),
        api_client.get_user(2),
        api_client.get_post(1),
        api_client.get_post(2),
        api_client.get_todo(1),
    ]
    # 並行実行により単純な順次実行より2-5倍高速化
    results = await asyncio.gather(*tasks)
    return results
```

#### メモリ効率化

```python
# メモリ使用量最適化
async def memory_efficient_pattern():
    # 大量データの分割処理
    for batch in range(0, total_items, batch_size):
        batch_data = await process_batch(batch, batch_size)
        yield batch_data  # ジェネレーターでメモリ効率化
        # 明示的なクリーンアップ
        del batch_data
```

#### エラー率改善

```python
# リトライ機能付きエラーハンドリング
async def robust_api_call(endpoint, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await api_client.get(endpoint)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # 指数バックオフ
```

### 📈 段階的改善計画

```bash
# Phase 1: 基本性能確保（1週間）
1. エラー率を10%以下に削減
2. レスポンス時間を3秒以下に短縮
3. メモリリークの完全解消

# Phase 2: 安定性向上（2週間）
1. エラー率を5%以下に削減
2. レスポンス時間を2秒以下に短縮
3. 同時実行性能の向上

# Phase 3: 最適化（1ヶ月）
1. スループットの20%向上
2. リソース使用効率の改善
3. スケーラビリティの確保
```

## 詳細テスト説明

### 🔄 APIパフォーマンステスト

**ファイル：** `test_api_performance.py`

**目的：** 基本的なAPI呼び出し性能の測定とボトルネック特定

**主要テスト：**

1. **単一リクエストパフォーマンス**

   ```python
   async def test_single_request_performance(self):
       # 目的: 基本レスポンス時間測定
       # 閾値: 2.0秒以下
       # 重要度: 🔴 HIGH
   ```

2. **並行リクエストパフォーマンス**

   ```python
   async def test_concurrent_requests_performance(self):
       # 目的: 10並行での性能評価
       # 閾値: 平均2秒、P95 3秒、スループット10 req/s
       # 重要度: 🔴 HIGH
   ```

3. **負荷テストシミュレーション**

   ```python
   async def test_load_test_simulation(self):
       # 目的: 50リクエスト・5並行での持続性能
       # 閾値: 平均3秒以下
       # 重要度: 🟡 MEDIUM
   ```

### 📊 ベンチマークテスト

**ファイル：** `test_benchmark.py`

**目的：** 統計的信頼性のある性能測定と回帰検出

**主要テスト：**

1. **精密ベンチマーク測定**

   ```python
   async def test_single_user_request_benchmark(self):
       # PerformanceBenchmark による高精度測定
       # 10回測定＋2回ウォームアップ
       # 統計的信頼性確保
   ```

2. **回帰検出システム**

   ```python
   async def test_performance_regression_detection(self):
       # 過去結果との自動比較
       # 20%以上劣化で回帰判定
       # 履歴データ管理
   ```

**ベンチマーク設定：**

```python
class BenchmarkConfig:
    BENCHMARK_ITERATIONS = 10      # 測定回数
    WARMUP_ITERATIONS = 2          # ウォームアップ回数
    REGRESSION_THRESHOLD_PERCENT = 20.0  # 回帰検出閾値
    ACCEPTABLE_STDDEV_RATIO = 0.1  # 安定性基準
```

### 🚀 負荷テスト

**ファイル：** `test_load_testing.py`

**目的：** 段階的負荷増加による限界点検出と容量計画

**段階設定：**

```python
LOAD_STAGES = [5, 8, 12, 15, 20]  # ユーザー数
TEST_DURATION = 20                # 各段階の実行時間（秒）
```

**主要テスト：**

1. **段階的負荷増加**
   - 5ユーザー → 20ユーザーまで段階的増加
   - 各段階でパフォーマンス測定
   - 容量限界の自動検出

2. **持続負荷テスト**
   - 8ユーザーで60秒間持続実行
   - 性能劣化の検出
   - 安定性評価

3. **ピーク容量検出**
   - 20-50ユーザーでの限界テスト
   - エラー率30%で容量限界判定
   - 推奨運用容量算出

### ⚡ 並行性テスト

**ファイル：** `test_concurrency.py`

**目的：** 同時実行での競合状態・パフォーマンス特性の評価

**主要テスト：**

1. **並行読み取り操作**

   ```python
   async def test_concurrent_read_operations(self):
       # 10並行で各5リクエスト
       # エラー率10%未満
   ```

2. **高並行ストレス**

   ```python
   async def test_high_concurrency_stress(self):
       # 50並行で各3リクエスト
       # ストレス環境での安定性確認
   ```

3. **レースコンディション検出**

   ```python
   async def test_race_condition_detection(self):
       # 共有リソースへの並行アクセス
       # 競合状態の検出
   ```

### 💥 ストレステスト

**ファイル：** `test_stress_testing.py`

**目的：** システム破壊点検出と回復力評価

**主要テスト：**

1. **破壊点検出**

   ```python
   async def execute_breaking_point_test(self):
       # 50-2000ユーザーまで段階的増加
       # エラー率50%または応答時間30秒で破壊点判定
   ```

2. **回復力テスト**

   ```python
   async def execute_recovery_test(self):
       # ベースライン → ストレス → 回復の3段階
       # 回復時間の自動測定
   ```

3. **リソース枯渇テスト**

   ```python
   async def execute_resource_exhaustion_test(self):
       # メモリ集約的負荷でのリソース監視
       # 1GB増加で枯渇判定
   ```

### 📈 リソース監視テスト

**ファイル：** `test_resource_monitoring.py`

**目的：** CPU・メモリ・ネットワークリソースの総合監視

**監視設定：**

```python
class ResourceMonitoringConfig:
    MONITORING_INTERVAL = 0.1           # 100ms間隔監視
    CPU_WARNING_THRESHOLD = 80.0        # CPU警告閾値
    MEMORY_WARNING_THRESHOLD = 1000.0   # メモリ警告閾値
    MEMORY_GROWTH_WARNING = 100.0       # メモリ増加警告
```

**主要テスト：**

1. **ベースライン測定**
   - 最小負荷でのリソース使用量
   - 他テストとの比較基準確立

2. **ワークロード別監視**
   - light/medium/heavy 3段階
   - 負荷に応じたリソース変化

3. **メモリリーク検出**
   - 5サイクル長時間実行
   - 線形トレンド分析による自動検出

4. **CPU スパイク監視**
   - バースト負荷でのCPU使用率
   - スパイク持続時間の分析

## トラブルシューティング

### ❌ よくあるエラーと対処法

#### 1. タイムアウトエラー

```
TimeoutError: Request timed out after 30 seconds
```

**原因：** ネットワーク遅延、APIサーバー過負荷

**対処法：**

```python
# タイムアウト時間の調整
async with AsyncAPIClient(timeout=60) as client:
    response = await client.get("/posts/1")
```

#### 2. メモリエラー

```
MemoryError: Unable to allocate array
```

**原因：** メモリリーク、大量データ処理

**対処法：**

```python
# バッチサイズの削減
batch_size = 5  # 10 → 5 に削減
for batch in range(0, request_count, batch_size):
    # 処理...
```

#### 3. 接続エラー

```
ConnectionError: Failed to establish connection
```

**原因：** ネットワーク接続問題、APIサーバーダウン

**対処法：**

```python
# リトライ機能の実装
for attempt in range(3):
    try:
        response = await client.get(endpoint)
        break
    except ConnectionError:
        await asyncio.sleep(2 ** attempt)
```

### 🔧 パフォーマンス調整

#### レスポンス時間改善

```python
# 1. 並行処理の最適化
concurrent_limit = 10  # 適切な並行数に調整

# 2. キャッシュ機能の活用
@lru_cache(maxsize=100)
async def cached_api_call(endpoint):
    return await api_client.get(endpoint)

# 3. バッチサイズの最適化
optimal_batch_size = 5  # テストして最適値を決定
```

#### メモリ使用量最適化

```python
# 1. ジェネレーターの活用
def process_data_generator(data):
    for item in data:
        yield process_item(item)

# 2. 明示的なメモリ解放
del large_data_structure
gc.collect()  # ガベージコレクション実行
```

### 📊 監視・レポート機能

#### カスタムレポート生成

```python
# パフォーマンスレポート生成
def generate_custom_report(results):
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": len(results),
            "avg_response_time": calculate_average(results),
            "success_rate": calculate_success_rate(results),
        },
        "detailed_results": results
    }

    with open("custom_performance_report.json", "w") as f:
        json.dump(report, f, indent=2)
```

#### 継続的監視設定

```python
# CI/CD での自動実行
def setup_continuous_monitoring():
    # 毎日午前2時に実行
    schedule.every().day.at("02:00").do(run_performance_tests)

    # 性能劣化検出時のアラート
    if performance_degradation_detected():
        send_alert_notification()
```

### 🎯 最適化のベストプラクティス

1. **段階的改善**
   - 一度に全てを変更せず、段階的に改善
   - 各変更の効果を個別に測定

2. **ベンチマーク主導開発**
   - 変更前後で必ずベンチマーク実行
   - 回帰を防ぐための継続的測定

3. **リソース効率性**
   - メモリとCPUのバランスを考慮
   - 無駄なリソース使用の削減

4. **実用的な目標設定**
   - ユーザー体験に基づいた現実的な目標
   - 技術的制約を考慮した計画

このガイドを活用して、効果的なパフォーマンステストとシステム最適化を実現してください。

---

**参考リンク：**

- [パフォーマンス監視実装ガイド](./performance_monitor_implementation.md)
- [日常運用コマンド](./daily_commands.md)
- [Docker環境構築ガイド](./docker_guide.md)
