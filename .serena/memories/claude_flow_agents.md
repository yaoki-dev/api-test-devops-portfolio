# Claude-Flow エージェント構成

*作成日: 2026年02月05日*

## 目的

品質ゲート4段階（pytest/ruff/mypy/git）の自動化支援

## エージェント一覧

### 1. tester-1
- **Type**: tester
- **Capabilities**: pytest, coverage-analysis, test-markers, unittest-integration
- **役割**: pytest実行、カバレッジ分析、テストマーカー管理

### 2. reviewer-1
- **Type**: reviewer
- **Capabilities**: ruff-check, mypy-typecheck, code-review, document-review
- **役割**: コードスタイル検証、型チェック、品質レビュー

### 3. qa-expert-1
- **Type**: tester
- **Capabilities**: quality-gate-validation, coverage-multidim, test-pyramid-check, implementation-certification
- **役割**: 品質ゲート4段階統合検証、実装活動認定

### 4. optimizer-1
- **Type**: perf-analyzer
- **Capabilities**: performance-benchmark, bottleneck-analysis, refactoring-suggest, test-parallelization
- **役割**: パフォーマンス分析、ボトルネック検出、並列化最適化

### 5. analyst-1
- **Type**: code-analyzer
- **Capabilities**: coverage-trend-analysis, test-count-tracking, daily-progress-update, weekly-retrospective
- **役割**: カバレッジ推移分析、テスト数追跡、進捗記録

## 再作成コマンド

```bash
# tester-1
mcp__claude-flow-lite__agent_spawn(
  type="tester",
  name="tester-1",
  swarmId="api-test-devops-portfolio",
  capabilities=["pytest", "coverage-analysis", "test-markers", "unittest-integration"]
)

# reviewer-1
mcp__claude-flow-lite__agent_spawn(
  type="reviewer",
  name="reviewer-1",
  swarmId="api-test-devops-portfolio",
  capabilities=["ruff-check", "mypy-typecheck", "code-review", "document-review"]
)

# qa-expert-1
mcp__claude-flow-lite__agent_spawn(
  type="tester",
  name="qa-expert-1",
  swarmId="api-test-devops-portfolio",
  capabilities=["quality-gate-validation", "coverage-multidim", "test-pyramid-check", "implementation-certification"]
)

# optimizer-1
mcp__claude-flow-lite__agent_spawn(
  type="perf-analyzer",
  name="optimizer-1",
  swarmId="api-test-devops-portfolio",
  capabilities=["performance-benchmark", "bottleneck-analysis", "refactoring-suggest", "test-parallelization"]
)

# analyst-1
mcp__claude-flow-lite__agent_spawn(
  type="code-analyzer",
  name="analyst-1",
  swarmId="api-test-devops-portfolio",
  capabilities=["coverage-trend-analysis", "test-count-tracking", "daily-progress-update", "weekly-retrospective"]
)
```

## 実測パフォーマンス

### 品質ゲート実行時間（2026-02-05測定）
- pytest: 16.85秒（401テスト、10並列）
- ruff: 0.08秒
- mypy: 0.59秒
- git status: 0.02秒
- **総実行時間: 18秒**

### 効率化の本質的価値
実行時間短縮ではなく、**品質保証の一貫性確保**が主要価値。

## トークンコスト分析

| 方式 | 初回コスト | 実行コスト |
|------|----------|----------|
| Bash直接 | 0 tokens | ~50 tokens/回 |
| エージェント（メモリ復元） | ~2,500 tokens | ~200 tokens/回 |

**Break-even**: 5回実行で経済的

## セッション復元手順

1. Serenaメモリ読込: `read_memory("claude_flow_agents")`
2. エージェント再作成: 上記コマンド5つ実行
3. 品質ゲート検証: `qa-expert-1`による4段階チェック
