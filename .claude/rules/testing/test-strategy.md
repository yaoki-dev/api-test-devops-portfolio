# テスト戦略・設計ドキュメント

*最終更新: 2026年02月11日*

## エグゼクティブサマリー

**現在のカバレッジ**: 76.65%（CI条件） | **最終目標**: 85%
**テスト資産**: 300収集（CI条件: unit+integration, not external）/ 全415件
**最優先改善領域**: utils/api_client.py (49.41%)

---

## クイックリファレンス

### 頻用コマンド

```bash
uv run pytest                          # 全テスト
uv run pytest -n auto                  # 並列実行
uv run pytest --cov=utils --cov=config --cov=models --cov-report=term-missing
```

### 主要マーカー

| マーカー | 用途 | コマンド |
|---------|------|---------|
| `unit` | 単体テスト（モック中心） | `pytest -m unit` |
| `integration` | 統合テスト（実API） | `pytest -m integration` |
| `external` | 外部API依存（CI/CDのみ） | `pytest -m "not external"` |
| `smoke` | スモークテスト（基本動作） | `pytest -m smoke` |
| `slow` | 低速テスト（>3秒） | `pytest -m "not slow"` |

---

## テストピラミッド

```
  Unit 70%: モック中心・高速
  Integration 25%: 実API/連携
  E2E 5%: Playwright・ユーザージャーニー
```

| 層 | 実行時間 | 目的 |
|---|---------|------|
| Unit | <0.5s | 外部依存なし |
| Integration | 1-3s | 連携検証 |
| E2E | 10-30s | ビジネス検証 |

---

## カバレッジ戦略

| Week | 目標 | 主要実装 |
|------|------|---------|
| 1-2 | 60-65% | 単体テスト基盤 |
| 3-4 | 65-70% | Docker/CI-CD |
| 5-6 | 80-85% | 非同期/e2e |

**優先モジュール**: utils/api_client.py (49.41%) → 最優先

---

## CI/CD統合

| ステージ | トリガー | テスト |
|---------|---------|--------|
| PR | pull_request | unit + integration |
| Merge | push main | + smoke |
| Weekly | schedule | + security + performance |

**品質ゲート**: `uv run pytest --cov-fail-under=${TARGET} && uv run ruff check . && uv run mypy utils/ config/ models/`

---

## トラブルシューティング

詳細なトラブルシューティング: **@memory:test_strategy_details**

---

## 詳細ガイド

実装パターン、マーカー選択フロー、Fixture設計、CIセキュリティチェック等の詳細:
→ **@memory:test_strategy_details**

---

## 参考リソース

- [pytest](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
