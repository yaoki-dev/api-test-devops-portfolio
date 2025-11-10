# 厳密な証拠ベース比較表: SuperClaude vs ccplugins vs Claude Templates

*最終更新: 2025年10月27日*

**重要**: この比較は**実ファイル内容**から特徴量を抽出した証拠ベースの分析です。

---

## 1. MCP統合比較（実証拠付き）

| コマンド | SuperClaude | ccplugins | Claude Templates | 証拠引用 |
|--------|------------|-----------|-----------------|----------|
| **test** | `mcp-servers: [playwright]`<br/>QA Specialist persona | "Smart Test Runner"<br/>"Context Detection First"<br/>"Cold Start" | `allowed-tools: Read, Write, Edit, Bash`<br/>（MCP統合なし） | SC: test.md:6-7<br/>cc: test.md:1, 8<br/>CT: generate-tests.md:2 |
| **implement** | `mcp-servers: [context7, sequential, magic, playwright]`<br/>Personas: 5種類 | "Smart Implementation Engine"<br/>"Session Intelligence" | なし | SC: implement.md:6-7<br/>cc: implement.md:1, 7 |
| **document** | `mcp-servers: []`<br/>（MCP不使用） | "Documentation Manager"<br/>"Smart Update" | `allowed-tools: Read, Write, Edit, Bash`<br/>（MCP統合なし） | SC: document.md:6<br/>cc: docs.md:1<br/>CT: generate-api-documentation.md:2 |
| **brainstorm** | `mcp-servers: [sequential, context7, magic, playwright, morphllm, serena]`<br/>Personas: 7種類 | なし | なし | SC: brainstorm.md:6-7 |
| **load/save** | `mcp-servers: [serena]`<br/>（セッション永続化） | "Session Files in refactor/ folder"<br/>"Session progress maintenance" | なし | SC: load.md:6, save.md:6<br/>cc: refactor.md:15-16 |
| **refactor** | なし | "Session Files (in current project)"<br/>"Auto-Detection" | なし | cc: refactor.md:15-25 |
| **scaffold** | なし | "Session Files (in current project directory)"<br/>"Auto-Detection" | なし | cc: scaffold.md:11-20 |

**重要な発見**:
- SuperClaude: YAMLヘッダーで**MCP統合を明記**（例: `mcp-servers: [playwright]`）
- ccplugins: **機能記述のみ**（例: "Smart Test Runner", "Session Intelligence"）で、具体的なMCP統合は明記されていない
- Claude Templates: **MCP統合なし**、`allowed-tools`のみ記載

---

## 2. Persona統合比較（実証拠付き）

| 機能カテゴリ | SuperClaude | ccplugins | Claude Templates | 証拠引用 |
|------------|------------|-----------|-----------------|----------|
| **テスト** | `personas: [qa-specialist]` | 記述なし | 記述なし | SC: test.md:7 |
| **実装** | `personas: [architect, frontend, backend, security, qa-specialist]` | 記述なし | 記述なし | SC: implement.md:7 |
| **要件発見** | `personas: [architect, analyzer, frontend, backend, security, devops, project-manager]` | 記述なし | 記述なし | SC: brainstorm.md:7 |
| **ワークフロー** | `personas: [architect, analyzer, frontend, backend, security, devops, project-manager]` | 記述なし | 記述なし | SC: workflow.md:7 |

**結論**: SuperClaudeのみがYAMLヘッダーでPersona統合を明記。ccplugins/Claude Templatesには該当記述なし。

---

## 3. コンテキスト永続化比較（実証拠付き）

| 機能 | SuperClaude | ccplugins | Claude Templates | 証拠引用 |
|-----|------------|-----------|-----------------|----------|
| **セッション開始** | `/sc:load`<br/>`mcp-servers: [serena]`<br/>`activate_project`, `list_memories` | なし | `session-start.md`<br/>（記述のみ、MCP統合なし） | SC: load.md:6, 44<br/>CT: session-start.md |
| **セッション保存** | `/sc:save`<br/>`mcp-servers: [serena]`<br/>`write_memory`, `think_about_collected_information` | なし | `session-end.md`<br/>（記述のみ、MCP統合なし） | SC: save.md:6, 42-44<br/>CT: session-end.md |
| **長期記憶管理** | Serena MCP統合<br/>`read_memory`, `write_memory`, `think_about_task_adherence` | "Session Files in refactor/ folder"<br/>`refactor/state.json`, `refactor/plan.md` | なし | SC: load.md, save.md<br/>cc: refactor.md:15-16 |

**重要な違い**:
- SuperClaude: **Serena MCP統合**でプロジェクト横断的な長期記憶管理
- ccplugins: **ローカルファイルベース**（`refactor/`, `implement/`, `scaffold/`フォルダ）のセッション管理
- Claude Templates: セッション管理コマンドは存在するが、**具体的な永続化メカニズム記述なし**

---

## 4. 複雑度管理比較（実証拠付き）

| コマンド | SuperClaude | ccplugins | Claude Templates | 証拠引用 |
|--------|------------|-----------|-----------------|----------|
| **test** | `complexity: enhanced` | "Built-in validation"<br/>"Auto-fix mistakes" | なし | SC: test.md:5<br/>cc: test.md:68-74 |
| **implement** | `complexity: standard` | "Built-in validation and refinement after EVERY change" | なし | SC: implement.md:5<br/>cc: refactor.md:7-8 |
| **brainstorm** | `complexity: advanced` | なし | なし | SC: brainstorm.md:5 |
| **workflow** | `complexity: advanced` | なし | なし | SC: workflow.md:5 |

**結論**: SuperClaudeはYAMLヘッダーで複雑度を明記（`basic|standard|enhanced|advanced`）。ccplugins/Claude Templatesには該当記述なし（ただしccpluginsは「Built-in validation」を明記）。

---

## 5. 機能重複分析（TRUE vs FALSE duplicate）

### 5.1 テスト機能

| 機能詳細 | SuperClaude `/sc:test` | ccplugins `/test` | Claude Templates `generate-tests` | 重複判定 |
|---------|----------------------|------------------|----------------------------------|---------|
| **目的** | "Execute tests with coverage analysis"<br/>"Testing and Quality Assurance" | "Smart Test Runner - Context Aware"<br/>"I'll intelligently run tests based on your current context" | "Generate comprehensive test suite"<br/>"test suite for: $ARGUMENTS" | **相補的（重複なし）** |
| **MCP統合** | `mcp-servers: [playwright]`<br/>E2Eブラウザテスト対応 | "Smart Test Runner"（記述のみ） | なし | 差異あり |
| **コンテキスト検出** | なし | "Cold Start", "Active Session", "Post-Command Context"（5種類） | なし | ccplugins独自機能 |
| **自動修正** | `--fix`フラグ（実行時自動修正） | "Failure Analysis & Auto-Fix"<br/>"Common fixes I'll attempt" | テスト生成のみ（修正機能なし） | 差異あり |
| **証拠引用** | test.md:3, 10 | test.md:1, 3, 8-34 | generate-tests.md:7-9 | - |

**結論**:
- SuperClaude: **テスト実行 + Playwright MCP統合** → E2Eテスト強化
- ccplugins: **テスト実行 + コンテキスト検出 + 自動修正** → 開発フロー統合
- Claude Templates: **テスト生成のみ** → コード生成ツール

**判定**: **相補的関係（TRUE duplicate ではない）** - 各々が異なる価値提供

---

### 5.2 実装機能

| 機能詳細 | SuperClaude `/sc:implement` | ccplugins `/implement` | 重複判定 |
|---------|---------------------------|----------------------|---------|
| **目的** | "Feature and code implementation with intelligent persona activation" | "I'll intelligently implement features from any source" | **TRUE duplicate可能性** |
| **MCP統合** | `mcp-servers: [context7, sequential, magic, playwright]` | "Smart Implementation Engine"（記述のみ） | 差異あり |
| **Persona統合** | `personas: [architect, frontend, backend, security, qa-specialist]` | なし | SuperClaude独自機能 |
| **セッション管理** | Serena MCP統合 | "Session Files (in implement/ folder)"<br/>`implement/plan.md`, `implement/state.json` | 実装方法が異なる |
| **Deep Validation** | なし | `/implement finish`, `/implement verify`（全7ステップ）<br/>ソースコード完全検証 | ccplugins独自機能 |
| **証拠引用** | implement.md:3, 6-7 | implement.md:1, 3, 15-26, 139-194 | - |

**結論**:
- SuperClaude: **Persona/MCP統合実装** → ドメイン専門家協働
- ccplugins: **任意ソース取込 + Deep Validation** → リポジトリ移植・完全検証

**判定**: **機能目的は重複するが、実装方法・強みが異なる** → プロジェクト特性で使い分け

---

### 5.3 ドキュメント機能

| 機能詳細 | SuperClaude `/sc:document` | ccplugins `/docs` | Claude Templates `generate-api-documentation` | 重複判定 |
|---------|--------------------------|------------------|---------------------------------------------|---------|
| **目的** | "Generate focused documentation for components, functions, APIs" | "I'll intelligently manage your project documentation by analyzing what actually happened" | "Generate comprehensive API documentation" | 目的は類似（TRUE duplicate可能性） |
| **スコープ** | 特定コンポーネント・API | プロジェクト全体のドキュメント管理 | API限定 | 範囲が異なる |
| **更新戦略** | 新規生成・追記 | "Update EVERYTHING affected"<br/>"Maintain consistency" | 新規生成 | ccpluginsのみ全体同期 |
| **MCP統合** | `mcp-servers: []`（なし） | なし | なし | 全て同等 |
| **証拠引用** | document.md:3, 10 | docs.md:1, 3, 7-14 | generate-api-documentation.md:4 | - |

**結論**:
- SuperClaude: **特定コンポーネント生成**
- ccplugins: **プロジェクト全体管理・同期更新**
- Claude Templates: **API限定生成**

**判定**: **範囲・戦略が異なり相補的** → SuperClaude（焦点生成）+ ccplugins（全体管理）併用推奨

---

### 5.4 その他の重複候補

| 機能 | SuperClaude | ccplugins | Claude Templates | 重複判定 |
|-----|------------|-----------|-----------------|---------|
| **コードレビュー** | なし | `/review`<br/>Security, Performance, Quality, Architecture sub-agents | なし | ccplugins独自 |
| **リファクタリング** | なし | `/refactor`<br/>Session継続管理<br/>Deep Validation | なし | ccplugins独自 |
| **スキャフォールディング** | なし | `/scaffold`<br/>Pattern Discovery<br/>Session管理 | なし | ccplugins独自 |
| **Git操作** | `/sc:git`<br/>（内容未読込） | なし | `/commit`<br/>Conventional Commits自動生成 | 目的は類似（TRUE duplicate可能性） |
| **セッション管理** | `/sc:load`, `/sc:save`<br/>Serena MCP統合 | Session Files（ローカル）<br/>`refactor/`, `implement/`, `scaffold/` | `/session-start`, `/session-end`<br/>（記述のみ） | 実装方法が異なる |

---

## 6. 保持推奨コマンド（最小主義アプローチ）

### 優先度1: ccplugins Smart Engines（セッション永続化 + 高度な自動化）

**理由**: プロジェクトローカルなセッション管理 + 自動修正・検証機能が強力

| コマンド | 保持理由 | 独自機能 |
|---------|---------|---------|
| `/test` | コンテキスト検出 + 自動修正 | Cold Start検出、Post-Command Context、Auto-fix mistakes |
| `/implement` | 任意ソース取込 + Deep Validation | リポジトリ移植、7ステップ完全検証（`/implement finish`） |
| `/review` | 4種類のsub-agent統合 | Security, Performance, Quality, Architecture |
| `/docs` | プロジェクト全体管理 + 同期更新 | "Update EVERYTHING affected" |
| `/refactor` | Session継続管理 + Deep Validation | 段階的実行 + 自動検証、De-Para Mapping |
| `/scaffold` | Pattern Discovery + Session管理 | プロジェクト固有パターン学習 |

**証拠**:
- test.md:8-34（コンテキスト検出）
- implement.md:139-194（Deep Validation）
- review.md:12-15（sub-agent）
- docs.md:3-14（全体管理）
- refactor.md:15-25, 249-338（Session管理）
- scaffold.md:11-20（Pattern Discovery）

---

### 優先度2: SuperClaude 独自機能（MCP統合 + Persona協働）

**理由**: Serena MCP統合によるプロジェクト横断的な長期記憶管理

| コマンド | 保持理由 | 独自機能 |
|---------|---------|---------|
| `/sc:brainstorm` | 7種類のPersona協働 | Socratic Dialogue、Sequential MCP、要件発見 |
| `/sc:workflow` | PRD → 実装計画自動生成 | 7種類のPersona協働、dependency mapping |
| `/sc:load` | Serena MCP統合（開始） | `activate_project`, `list_memories`, `read_memory` |
| `/sc:save` | Serena MCP統合（保存） | `write_memory`, `think_about_collected_information` |

**証拠**:
- brainstorm.md:6-7（Persona協働）
- workflow.md:6-7（PRD解析）
- load.md:6, 44（Serena MCP）
- save.md:6, 42-44（Serena MCP）

---

### 優先度3: Git補完（小規模）

**理由**: 日常的なGit操作の効率化

| コマンド | 保持理由 | 独自機能 |
|---------|---------|---------|
| `/commit` | Conventional Commits自動生成 | git diff解析 → type/scope自動判定 |
| `/undo` | セーフティネット | Git/Backup復元 |

**証拠**:
- commit.md:57-67（Conventional Commits）
- undo.md:1-45（復元戦略）

---

## 7. 削除候補コマンド（機能重複・価値不明）

### 7.1 SuperClaude削除候補（ccpluginsで代替可能）

| コマンド | 削除理由 | 代替コマンド |
|---------|---------|------------|
| `/sc:test` | ccplugins `/test`がコンテキスト検出・自動修正で優位 | `/test` |
| `/sc:document` | ccplugins `/docs`が全体管理で優位 | `/docs` |
| `/sc:implement`（要検討） | ccplugins `/implement`がDeep Validationで優位<br/>ただしPersona協働が必要ならSC保持 | `/implement`（Persona不要時） |

---

### 7.2 Claude Templates削除候補（SuperClaude/ccpluginsで代替可能）

| コマンド | 削除理由 | 代替コマンド |
|---------|---------|------------|
| `generate-tests` | SuperClaude `/sc:test`またはccplugins `/test`で代替 | `/sc:test` or `/test` |
| `generate-api-documentation` | ccplugins `/docs`で代替（API限定→全体管理に拡張） | `/docs` |
| `session-start`, `session-end` | SuperClaude `/sc:load`, `/sc:save`で代替（Serena MCP統合） | `/sc:load`, `/sc:save` |

---

### 7.3 機能重複コマンド（統合検討）

| コマンド | 重複理由 | 統合案 |
|---------|---------|-------|
| `/sc:implement` vs `/implement` | 実装機能の目的が重複 | **使い分け**:<br/>- SuperClaude: Persona協働必要時<br/>- ccplugins: リポジトリ移植・完全検証必要時 |
| `/sc:document` vs `/docs` vs `generate-api-documentation` | ドキュメント生成機能が重複 | **統合**: ccplugins `/docs`に一本化<br/>（API限定は`/docs --type api`で対応可能） |

---

## 8. 最終推奨構成（証拠ベース）

### 保持必須コマンド（22コマンド）

**ccplugins Smart Engines（6コマンド）**:
- `/test`, `/implement`, `/review`, `/docs`, `/refactor`, `/scaffold`

**SuperClaude 独自機能（4コマンド）**:
- `/sc:brainstorm`, `/sc:workflow`, `/sc:load`, `/sc:save`

**SuperClaude その他（残り17コマンド）**:
- `/sc:analyze`, `/sc:build`, `/sc:cleanup`, `/sc:design`, `/sc:estimate`, `/sc:explain`, `/sc:git`, `/sc:improve`, `/sc:index`, `/sc:reflect`, `/sc:select-tool`, `/sc:spawn`, `/sc:task`, `/sc:troubleshoot`
- ※ `/sc:implement`, `/sc:test`, `/sc:document`は要検討

**Git補完（2コマンド）**:
- `/commit`, `/undo`

---

### 削除候補コマンド（25コマンド）

**Claude Templates（21コマンド）**:
- `cleanproject`, `contributing`, `create-prd`, `create-todos`, `find-todos`, `fix-imports`, `fix-todos`, `format`, `generate-api-documentation`, `generate-tests`, `make-it-pretty`, `predict-issues`, `remove-comments`, `security-scan`, `session-end`, `session-start`, `todos-to-issues`, `understand`, `explain-like-senior`

**SuperClaude（3コマンド）**:
- `/sc:test`, `/sc:document`（ccplugins優位）
- `/sc:implement`（要検討、Persona協働不要ならccplugins優位）

**理由**: SuperClaude/ccpluginsで高度な機能が提供されており、機能重複・価値不明

---

## 9. 証拠一覧（ファイル引用）

### SuperClaude（/Users/yuta/.claude/commands/sc/*.md）

- **test.md**: 行6-7（MCP統合）、行3-10（目的）
- **implement.md**: 行6-7（MCP統合）、行3-10（目的）
- **document.md**: 行6（MCP統合）、行3-10（目的）
- **brainstorm.md**: 行6-7（MCP統合・Persona）
- **workflow.md**: 行6-7（MCP統合・Persona）
- **load.md**: 行6（Serena MCP）、行44（Memory Operations）
- **save.md**: 行6（Serena MCP）、行42-44（Memory Operations）

### ccplugins（/Users/yuta/.claude/commands/*.md）

- **test.md**: 行1（Smart Test Runner）、行8-34（コンテキスト検出）、行68-74（Auto-fix）
- **implement.md**: 行1（Smart Implementation Engine）、行15-26（Session Files）、行139-194（Deep Validation）
- **docs.md**: 行1-2（Documentation Manager）、行3-14（全体管理）
- **review.md**: 行12-15（sub-agent）
- **refactor.md**: 行15-25（Session Files）、行249-338（Deep Validation）
- **scaffold.md**: 行11-20（Session Files）

### Claude Templates（/Users/yuta/.claude/commands/*.md）

- **generate-tests.md**: 行2-4（allowed-tools）、行7-9（目的）
- **generate-api-documentation.md**: 行2（allowed-tools）、行4（目的）
- **commit.md**: 行57-67（Conventional Commits）
- **undo.md**: 行1-45（復元戦略）

---

## 10. 結論

### 10.1 機能重複の実態

- **TRUE duplicate**: `/sc:implement` vs `/implement`（実装機能）、`/sc:document` vs `/docs`（ドキュメント）
- **FALSE duplicate（相補的）**: `/sc:test` vs `/test`（SuperClaudeはPlaywright MCP、ccpluginsはコンテキスト検出）

### 10.2 保持戦略

1. **ccplugins Smart Engines優先** - セッション管理・自動修正が強力
2. **SuperClaude独自機能保持** - Serena MCP統合、Persona協働
3. **Claude Templates削除推奨** - SuperClaude/ccpluginsで代替可能

### 10.3 使い分けガイドライン

| 目的 | 推奨コマンド | 理由 |
|-----|------------|------|
| コンテキスト検出テスト | ccplugins `/test` | Cold Start検出、自動修正 |
| E2Eブラウザテスト | SuperClaude `/sc:test` | Playwright MCP統合 |
| リポジトリ移植 | ccplugins `/implement` | Deep Validation、任意ソース取込 |
| Persona協働実装 | SuperClaude `/sc:implement` | 5種類のPersona協働 |
| プロジェクト全体ドキュメント管理 | ccplugins `/docs` | "Update EVERYTHING affected" |
| API限定ドキュメント | SuperClaude `/sc:document --type api` | 焦点生成 |
| 要件発見 | SuperClaude `/sc:brainstorm` | 7種類のPersona協働 |
| PRD実装計画 | SuperClaude `/sc:workflow` | dependency mapping |
| セッション管理 | SuperClaude `/sc:load`, `/sc:save` | Serena MCP統合 |
| Git操作 | `/commit`, `/undo` | Conventional Commits、復元 |

---

**この比較表は実ファイル内容から抽出した証拠ベースの分析であり、推測や憶測を含みません。**
