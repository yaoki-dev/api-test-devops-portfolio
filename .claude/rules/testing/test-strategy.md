---
paths:
  - "tests/**/*.py"
---

# テスト戦略・設計ドキュメント

*最終更新: 2026-07-30*

## エグゼクティブサマリー

**カバレッジ下限**: `pyproject.toml` の `--cov-fail-under`（CI条件: unit+integration, not external）

---

## クイックリファレンス

### 頻用コマンド

```bash
uv run pytest                          # 全テスト
uv run pytest -n auto                  # 並列実行

# カバレッジ計測（CI/CD品質ゲート用）
# IMPORTANT: unit+integrationマーカーのみで計測（externalは除外）
uv run pytest -n auto -m "(unit or integration) and not external" \
    --cov=utils --cov=config --cov=models --cov-report=term-missing
```

### 主要マーカー

| マーカー | 用途 | コマンド |
|---------|------|---------|
| `unit` | 単体テスト（モック中心） | `pytest -m unit` |
| `integration` | 統合テスト（実API） | `pytest -m integration` |
| `external` | 外部API依存（週次のみ） | `pytest -m "not external"` |
| `smoke` | スモークテスト（基本動作） | `pytest -m smoke` |
| `slow` | 低速テスト（>3秒） | `pytest -m "not slow"` |

---

## テストピラミッド

```
  Unit 70%: モック中心・高速
  Integration 30%: 実API/連携
```

| 層 | 実行時間 | 目的 |
|---|---------|------|
| Unit | <0.5s | 外部依存なし |
| Integration | 1-3s | 連携検証 |

---

## CI/CD統合

| ステージ | トリガー | テスト |
|---------|---------|--------|
| PR | pull_request | unit + integration |
| Merge | push main | + smoke |
| Weekly | schedule | + external + performance |

**品質ゲート**: `.claude/CLAUDE.md` Section「品質ゲート」→「統合コマンド」

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
