# Agent導入計画

*最終更新: 2025年10月27日*

## 🎯 導入推奨Agent一覧（優先度順）

### Tier 1: 必須導入（Week 7開始時）⭐⭐⭐⭐⭐

#### 1. Context Manager

- **機能**: プロジェクト全体の文脈管理、マイルストーン管理、依存関係可視化
- **導入理由**: タスク管理の盲点解消、実務基盤構築
- **期待効果**: タスク分解精度 50% → 90%
- **ROI**: 7.65倍（年間+1,560,000円収入）
- **導入タイミング**: Week 7 Day 1（Docker学習開始前）

**初回使用コマンド**:

```bash
@context-manager "Week 7のDocker学習（42h）をマイルストーンに分解してください。
各フェーズの成果物、依存関係、クリティカルパスを明示すること"
```

---

#### 2. Task Decomposition Expert

- **機能**: 技術タスクの最適粒度分解（1-2h単位）、成功基準設定
- **導入理由**: 学習効率化、実装品質向上
- **期待効果**: 学習効率 1.5倍、AI依頼品質 Level 2 → Level 4
- **ROI**: タスク分解時間 10分 → 1分（90%削減）
- **導入タイミング**: Week 7 Day 1（Context Managerと同時）

**初回使用コマンド**:

```bash
@task-decomposition "Docker Multi-stage builds学習（8h）を、
1-2時間で完了できる粒度にタスク分解してください。
各タスクの成功基準（理解度30%、テスト合格等）を含めること"
```

---

#### 3. Prompt Engineer

- **機能**: AI依頼品質の最適化、プロンプトテンプレート作成
- **導入理由**: AI協働実務の効率化、収入直結
- **期待効果**: AI依頼品質 Level 2 → Level 4、時給+500-1000円
- **ROI**: 月次プロンプトレビューで継続的改善
- **導入タイミング**: Week 7 Day 2（基本操作習得後）

**初回使用コマンド**:

```bash
@prompt-engineer "docker-devopsへの依頼を最適化してください。
依頼内容: 'Docker 4-stage実装を教えてください'
目標: AI依頼品質をLevel 4（技術的依頼）に向上"
```

---

### Tier 2: 高優先導入（Week 8-9）⭐⭐⭐⭐

#### 4. Code Reviewer

- **機能**: Enterprise品質基準でのコードレビュー、CVE参照付き指摘
- **導入理由**: 専門レビュー強化、実装品質向上
- **期待効果**: レビュー深度 60% → 95%、改善実装率 40% → 85%
- **ROI**: バグ修正時間50%削減
- **導入タイミング**: Week 8 Day 1（CI/CD統合開始時）

**初回使用コマンド**:

```bash
@code-reviewer "実装したDockerfile（200行）をEnterprise品質基準でレビュー。
セキュリティ・パフォーマンス・保守性の3観点で詳細分析し、
CVE参照・具体的改善コード例を含めてください"
```

---

#### 5. MCP Expert

- **機能**: MCP（Model Context Protocol）統合専門、LLM統合設計
- **導入理由**: 新領域対応、市場価値向上
- **期待効果**: 時給+500-1000円、LLM統合案件対応可能
- **ROI**: 新技術習得による案件獲得率向上
- **導入タイミング**: Week 9 Day 1（ポートフォリオ最適化時）

**初回使用コマンド**:

```bash
@mcp-expert "本プロジェクトへのMCP統合可能性を評価してください。
Week 10以降の発展学習として、APIテスト結果のLLM自動分析を追加する設計案を提案"
```

---

### Tier 3: オプション導入（Week 10+）⭐⭐⭐

#### 6. Architect Review

- **機能**: アーキテクチャレビュー特化、設計判断の妥当性検証
- **導入条件**: 複雑なアーキテクチャ決定が必要な実務案件
- **導入タイミング**: 案件獲得後、設計フェーズ

---

#### 7. Search Specialist

- **機能**: 意味的なコードベース検索、パターン分析
- **導入条件**: 10,000行以上のレガシーコード調査
- **導入タイミング**: レガシーシステムリファクタリング案件

---

#### 8. API Documenter

- **機能**: OpenAPI/Swagger仕様書自動生成
- **導入条件**: 顧客向けAPI仕様書が必要な案件
- **導入タイミング**: API開発案件のドキュメント作成フェーズ

---

### 導入不要Agent（既存で完全カバー）❌

- **Python Pro**: 既存python-expert (3.1k)で十分
- **Test Engineer**: 既存api-testing (13k) + quality-engineer (2.8k)で完全カバー
- **Error Detective**: 既存root-cause-analyst (3.0k)で十分
- **DevOps Engineer**: 既存docker-devops (7.9k) + ci-cd-pipeline (22k)で完全カバー

---

## 📅 導入スケジュール

### Week 7 Day 1（10/27 想定）

**午前（2h）: 必須Agent 3つ導入**

```bash
# 1. Agentファイル配置
mkdir -p /Users/yuta/.claude/agents/
# https://www.aitmpl.com/agents から以下をダウンロード:
# - context-manager.md
# - task-decomposition-expert.md
# - prompt-engineer.md

# 2. 動作確認
@context-manager "テスト: Week 7のDocker学習をマイルストーン分解"
@task-decomposition "テスト: Docker基礎学習（8h）をタスク分解"
@prompt-engineer "テスト: docker-devopsへの依頼最適化"
```

**午後（2h）: Agent活用実践**

```bash
# 1. Week 7学習計画をAgent支援で再構築
@context-manager "Week 7のDocker学習（42h）を最適化されたマイルストーンに分解"
@task-decomposition "Phase 1: 基礎学習（8h）を1-2h粒度にタスク分解"

# 2. 最適化された学習計画でDocker学習開始
「学習開始」トリガー実行
```

---

### Week 8 Day 1（11/4 想定）

**午前（1h）: Code Reviewer導入**

```bash
# 1. Agentファイル配置
# https://www.aitmpl.com/agents から code-reviewer.md をダウンロード

# 2. Week 7実装のレビュー実施
@code-reviewer "Week 7で実装したDockerfile全体をEnterprise品質基準でレビュー"
```

---

### Week 9 Day 1（11/11 想定）

**午前（1h）: MCP Expert導入**

```bash
# 1. Agentファイル配置
# https://www.aitmpl.com/agents から mcp-expert.md をダウンロード

# 2. MCP統合可能性評価
@mcp-expert "本プロジェクトへのMCP統合設計案を提案"
```

---

## 🎓 Agent習得カリキュラム

### Phase 1: 基本操作習得（Week 7 Day 1-3）

**Day 1: Context Manager**

- [ ] マイルストーン分解の実践
- [ ] 依存関係グラフの読み方
- [ ] クリティカルパスの特定

**Day 2: Task Decomposition**

- [ ] 最適粒度（1-2h）の理解
- [ ] 成功基準の設定方法
- [ ] タスク優先順位付け

**Day 3: Prompt Engineer**

- [ ] AI依頼品質の評価基準
- [ ] Level 2 → Level 3への改善
- [ ] プロンプトテンプレート作成

---

### Phase 2: Agent連携習得（Week 7 Day 4-7）

**連携パターン1: 学習サイクル**

```yaml
Day 4-5:
  1. task-decomposition（タスク分解）
  2. docker-devops（AI説明・概念理解）
  3. python-expert + docker-devops（AI協働実装）
  4. 理解度確認（トリガー6）

評価基準:
  - タスク完了率: 90%以上
  - 理解度スコア: 80%以上
  - AI依頼品質: Level 3達成
```

**連携パターン2: 実装→レビューサイクル**

```yaml
Day 6-7:
  1. task-decomposition（実装タスク分解）
  2. docker-devops（Docker 4-stage実装）
  3. code-reviewer（レビュー） ※Week 8で実践
  4. 改善実装

評価基準:
  - 品質ゲート合格率: 95%以上
  - レビュー指摘対応率: 100%
```

---

### Phase 3: Agent活用最適化（Week 8-9）

**Week 8: 専門レビュー強化**

- [ ] Code ReviewerによるEnterprise品質レビュー
- [ ] セキュリティ・パフォーマンス・保守性の3観点分析
- [ ] CVE参照付き改善実装

**Week 9: 新技術統合**

- [ ] MCP Expert活用開始
- [ ] LLM統合可能性評価
- [ ] 発展学習計画策定

---

## 📊 Agent導入効果測定（KPI）

### Week 7-8（学習フェーズ）

| KPI | 目標値 | 測定方法 | 現状 |
|-----|--------|----------|------|
| タスク分解精度 | 90% | Context Manager出力の実行可能性 | 50% |
| AI依頼品質 | Level 3 | Prompt Engineer評価 | Level 2 |
| 学習効率 | 1.5倍 | 推定時間 vs 実績時間 | 1.0倍 |
| 理解度スコア | 80%以上 | 週次理解度テスト | 60% |
| 品質ゲート合格率 | 95%以上 | pytest/ruff/mypy合格率 | 85% |

---

### Week 9-10（実務準備フェーズ）

| KPI | 目標値 | 測定方法 | 現状 |
|-----|--------|----------|------|
| コードレビュー指摘率 | 30%以下 | Code Reviewer指摘数 / コード行数 | 60% |
| レビュー深度 | 95% | Enterprise品質基準カバー率 | 60% |
| 時給向上 | +500-1000円 | Agent活用効果シミュレーション | - |
| ポートフォリオ品質 | 90% | 市場価値評価（時給6000-8000円証明） | 40% |

---

## 🚨 導入時の注意点

### 1. Agent依存症の防止

**リスク**:

- AI生成コードを理解せずにコピー
- 基礎知識の欠如
- 自力実装能力の低下

**対策**:

```yaml
実装品質判定（必須）:
  - pytest合格
  - ruff合格
  - mypy合格
  - 理解度確認（週1回）

AI活用率の監視:
  - AI使用時間: 50%以下推奨
  - 自力実装時間: 50%以上維持
  - エラー修正回数: 週3回以内
```

---

### 2. Agent選択ミスの防止

**リスク**:

- タスクに不適切なAgent使用
- 期待する出力が得られない

**対策**:

```yaml
Agent選択チェックリスト:
  - [ ] タスクの目的明確化
  - [ ] Agent専門領域との一致確認
  - [ ] 既存Agent活用歴の参照
  - [ ] 連携Agentの事前計画
```

---

### 3. プロンプト品質の停滞防止

**リスク**:

- Level 2依頼から成長しない
- 時給が頭打ち

**対策**:

```yaml
月次プロンプトレビュー（Prompt Engineer活用）:
  - 過去1ヶ月のAI依頼を分析
  - Level 3→4への改善点特定
  - 成功パターンのテンプレート化
```

---

## 📚 参考資料

### Agent活用ベストプラクティス

1. **タスク分解パターン集**:
   - `/Users/yuta/Yuta/python/api-test-devops-portfolio/docs/ai_collaboration/task_decomposition_patterns.md`

2. **プロンプトテンプレート集**:
   - `/Users/yuta/Yuta/python/api-test-devops-portfolio/docs/ai_collaboration/prompt_templates.md`

3. **Agent連携パターン集**:
   - `/Users/yuta/Yuta/python/api-test-devops-portfolio/docs/ai_collaboration/agent_collaboration_patterns.md`

4. **実務Agent活用戦略**:
   - `/Users/yuta/Yuta/python/api-test-devops-portfolio/docs/ai_collaboration/agent_strategy_production.md`

---

**次のステップ**: Week 7 Day 1（10/27）に必須Agent 3つを導入し、Docker学習で実践検証を開始してください。
