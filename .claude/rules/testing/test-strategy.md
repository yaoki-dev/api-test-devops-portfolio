# テスト戦略・設計ドキュメント

*最終更新: 2025年12月26日*

## エグゼクティブサマリー

**プロジェクト目標**: 時給4,000-4,500円レベルの技術力証明
**現在のカバレッジ**: ~65-70% (目標: 85%)
**テスト資産**: 69関数 / 324収集 (parametrize展開後)、~7,500行、20+フィクスチャ
**最優先改善領域**: utils/api_client.py、models/responses.py

---

## クイックリファレンス

### 頻用コマンド

```bash
# 基本実行
uv run pytest                          # 全テスト
uv run pytest -v                       # 詳細出力
uv run pytest -x                       # 最初の失敗で停止

# 並列実行
uv run pytest -n auto                  # CPU数に応じた並列
uv run pytest -n auto -m "not external and not manual"

# カバレッジ
uv run pytest --cov=utils --cov=config --cov=models --cov-report=term-missing
uv run pytest --cov-report=html        # → reports/htmlcov/
uv run pytest --cov-fail-under=85
```

### マーカー索引 (2025-12-26実測)

| マーカー | 使用数 | 用途 | コマンド |
|---------|--------|------|---------|
| `unit` | 52 | 単体テスト | `pytest -m unit` |
| `integration` | 12 | 統合テスト | `pytest -m integration` |
| `external` | 6 | 外部API依存 | `pytest -m "not external"` |
| `smoke` | 3 | スモークテスト | `pytest -m smoke` |
| `performance` | 2 | パフォーマンス | `pytest -m performance` |

### 検証コマンド

```bash
# テスト関数総数
grep -r "^def test_\|^async def test_" tests/ | wc -l

# pytest収集数（parametrize展開後）
uv run pytest --collect-only 2>/dev/null | grep "collected"

# マーカー別使用数
grep -r "@pytest.mark\." tests/ | grep -oE "@pytest\.mark\.[a-z_]+" | sort | uniq -c
```

### 主要Fixture

| フィクスチャ | 用途 | スコープ |
|------------|------|---------|
| `async_client` | 非同期HTTPクライアント | function |
| `mock_httpx_client` | モックHTTPX | function |
| `todo_data_factory` | TODOデータ生成 | function |
| `performance_timer` | パフォーマンス計測 | function |
| `test_config` | テスト設定 | session |

---

## 1. テストピラミッド

```
           E2E (5%)          ← Playwright、ユーザージャーニー
          /        \
   Integration (25%)         ← 実API、コンポーネント連携
        /            \
     Unit (70%)              ← モック中心、高速実行
```

| 層 | 定義 | 実行時間 | 目的 |
|---|------|---------|------|
| Unit | 外部依存なし | <0.5s | モック中心 |
| Integration | 実API | 1-3s | 連携検証 |
| E2E | ユーザーシナリオ | 10-30s | ビジネス検証 |

---

## 2. カバレッジ戦略

### 2.1 6週プラン目標

| Week | 目標 | 増加 | 主要実装 |
|------|------|------|---------|
| 1 | 40% | +25件 | 単体テスト基盤 |
| 2 | 60% | +20件 | エラーハンドリング |
| 3-4 | 60% | 維持 | Docker/CI-CD |
| 5 | 80% | +30件 | 非同期テスト |
| 6 | 85% | +25件 | e2e |

### 2.2 優先モジュール

1. **utils/api_client.py** (~970行) - リトライ、エラー処理
2. **models/responses.py** (~350行) - サニタイゼーション
3. **config/settings.py** (~450行) - ✅ 96%達成

---

## 3. CI/CD統合

### 3.1 ステージ構成

| ステージ | トリガー | テスト |
|---------|---------|--------|
| PR | pull_request | unit + integration |
| Merge | push main | + smoke |
| Weekly | schedule | + security + performance |

### 3.2 品質ゲート

```bash
uv run pytest --cov-fail-under=${TARGET} \
  && uv run ruff check . \
  && uv run mypy utils/ config/ models/ \
  && git status
```

---

## 4. トラブルシューティング

| 問題 | 解決策 |
|------|--------|
| カバレッジが上がらない | `--cov-report=term-missing` |
| 非同期テスト失敗 | `asyncio_mode = "auto"` 確認 |
| 並列実行で失敗 | reset_settings autouse確認 |
| モック動作しない | `Mock(spec=Class)` 使用 |

### デバッグコマンド

```bash
uv run pytest -vv --tb=long           # 詳細トレース
uv run pytest --collect-only          # テスト一覧
uv run pytest --log-cli-level=DEBUG   # ログ出力
```

---

## 5. 詳細ガイド

実装パターン、CIセキュリティチェック、パフォーマンステスト等の詳細:
→ **@memory:test_strategy_details**

---

## 参考リソース

- [pytest](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [pytest-xdist](https://pytest-xdist.readthedocs.io/)
