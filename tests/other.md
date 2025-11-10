 ---
  ⚡ Stage 2: Memory File最適化（-20k tokens、1時間）

  User CLAUDE.md最適化:

  # 削減対象セクション:
  1. Agent Selection Strategy Mapping（3k tokens）
     → 外部ファイル化: docs/ai_collaboration/agent_mapping.md

  2. Complex Workflow Playbooks（5k tokens）
     → 外部ファイル化: docs/ai_collaboration/workflows.md

  3. Command Usage Guidelines（2k tokens）
     → ccplugins使用時のみ動的読み込み

  Project CLAUDE.md最適化:

  # 削減対象:
  1. LEARNING_PLAN_WEEK_MAP（2k tokens）
     → 使用時のみ動的参照（既存のRead offset/limit活用）

  2. PORTFOLIO_STRATEGY_WEEK_MAP（2k tokens）
     → 同上

  3. AI協働学習フロー仕組み（4k tokens）
     → 外部ファイル化: docs/learning/ai_collaboration_flow.md

  削減効果: 250k → 230k tokens（15%余裕）

  ---
  🎯 Stage 3: Agent定義整理（-1k tokens、30分）

  削除対象エージェント（使用頻度<5%）:

  削除リスト:
  - penetration-tester
  - compliance-specialist
  - incident-responder
  - docusaurus-expert
  - load-testing-specialist
  - frontend-architect (プロジェクトで未使用)
  - socratic-mentor (学習フェーズ完了後不要)