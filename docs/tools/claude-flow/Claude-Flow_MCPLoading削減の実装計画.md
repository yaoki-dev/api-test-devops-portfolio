# Claude Flow MCP Tool Loading削減 実装計画書

*最終更新: 2025年11月08日*

**v2.0 更新内容**:

- 34ツール完全版に変更（Week 7-10一括実装）
- トークン削減率: 67.8% → 62.2%
- 段階的実装を廃止（忘れる心配を解消）

**ステータス**: ✅ 実装準備完了 → 実装開始可能

---

## 📋 目次

1. [エグゼクティブサマリー](#エグゼクティブサマリー)
2. [実装前確認事項](#実装前確認事項)
3. [実装ロードマップ](#実装ロードマップ)
4. [トラブルシューティング](#トラブルシューティング)
5. [検証・測定](#検証測定)
6. [付録](#付録)

---

## エグゼクティブサマリー

### 目的

Claude Flow MCPツールを**90個から34個に削減**し、起動時トークン消費を**62.2%削減**（51,300 → 19,380トークン）

**Week 7-10全ツール一括実装**: 段階的実装を避け、全34ツールを最初から実装することで忘れる心配を解消

### 推奨アプローチ

**Option 1: Filtered Fork Approach**

| 項目 | 詳細 |
|------|------|
| 実装時間 | **4時間**（1セッション完結可能） |
| 信頼性 | Claude Flow v2.7.0安定版ベース |
| 保守性 | npm標準ワークフロー |
| トークン削減 | **31,920トークン/セッション** |
| ツール数 | **34ツール** (Week 7-10完全版) |
| ROI | **1週間で投資回収** |

### 実装フェーズ

```
Phase 1: 準備（30分）
  ├─ npm scopeアカウント作成
  ├─ リポジトリフォーク
  └─ 依存関係インストール

Phase 2: フィルタリング実装（2時間）
  ├─ ツールリスト定義（Week 7-10完全版: 34ツール）
  ├─ サーバーロジック修正
  └─ ビルド・動作確認

Phase 3: パッケージ公開（1時間）
  ├─ package.json更新
  ├─ npm公開
  └─ READMEドキュメント作成

Phase 4: プロジェクト統合（30分）
  ├─ .mcp.json作成
  ├─ Claude Code再起動・動作確認
  └─ ドキュメント更新
```

### 技術的制約（調査済み）

**設定のみのアプローチは全て不可能**:

| アプローチ | 技術的制約 | 結論 |
|----------|----------|-----|
| `permissions.denied` | 使用制限のみ、ロード阻止不可 | ❌ トークン削減なし |
| `allowedMcpServers` | サーバーレベル制御のみ | ❌ ツールレベル制御不可 |
| Claude Flow環境変数 | フィルタリングサポートなし | ❌ 機能なし |
| GitHub Issue #7328 | Claude Codeツールフィルタリング | ⏳ 未実装 |

**確定事実**: ツールロード削減には実装が必須

---

## 実装前確認事項

### ✅ チェックリスト

実装Phase 1開始前に、以下を確認してください：

- [ ] **npm scopeアカウント**: `npm login`可能な状態（10分で作成可能）
- [ ] **実装時間確保**: 連続4時間（または2時間×2セッション）
- [ ] **Node.js v18+**: `node --version`で確認
- [ ] **npm v9+**: `npm --version`で確認
- [ ] **git動作確認**: `git --version`で確認
- [ ] **ベースライン測定**: 実装前のトークン消費量記録（任意）
- [ ] **ロールバック準備**: gitブランチ作成推奨
- [ ] **Week 7開始日**: 2025-10-01までに完了必須

### 🔍 環境確認コマンド

```bash
# Node.jsバージョン確認（v18以上推奨）
node --version
# 期待値: v18.0.0以上

# npmバージョン確認（v9以上推奨）
npm --version
# 期待値: 9.0.0以上

# gitバージョン確認
git --version
# 期待値: 2.0.0以上

# npmアカウント確認
npm whoami
# 未ログイン時: npm login を実行
```

### 📝 npm scopeアカウント作成（10分）

**初回のみ実施**:

```bash
# npmアカウント作成（未作成の場合）
npm adduser
# → Username: your-username
# → Password: ********
# → Email: your-email@example.com

# ログイン確認
npm whoami
# → your-username が表示されればOK
```

**パッケージ名決定**:

- 推奨形式: `@your-username/claude-flow-lite`
- 例: `@yuta/claude-flow-lite`、`@api-test-devops/claude-flow-lite`

---

## 実装ロードマップ

### 実装計画確定

- リポジトリ: <https://github.com/ruvnet/claude-flow>
- Node.js: v20.19.4
- ワークスペース: /Users/yuta/Yuta/python/api-test-devops-portfolio
- ブランチ戦略:
  - 実装ブランチ: claude_flow_lite（ベース: main）
  - 履歴管理: local/historyで実装中のコミット管理
  - 完成後にmainへpush

### Phase 1: 準備（30分）

#### Step 1.1: リポジトリクローン（10分）

```bash
# 作業ディレクトリ作成
mkdir -p ~/workspace
cd ~/workspace

# Claude Flowリポジトリクローン（正しいリポジトリ）
git clone --depth 1 https://github.com/ruvnet/claude-flow.git ruv-claude-flow
cd ruv-claude-flow

# ブランチ作成
git checkout -b lite/v2.7.30

# 現在のディレクトリ確認
pwd
# → ~/workspace/ruv-claude-flow
```

**確認ポイント**:

- ✅ `package.json`が存在すること（ルートディレクトリ）
- ✅ `src/mcp/`ディレクトリが存在すること
- ✅ `src/mcp/mcp-server.js`が存在すること（JavaScript実装）

#### Step 1.2: 依存関係インストール（10分）

```bash
# 依存関係インストール
npm install

# ビルドテスト（JavaScript実装のため、TypeScriptコンパイル不要）
# ビルドスクリプトが存在するか確認
npm run build 2>/dev/null || echo "Build script not required (JavaScript)"

# パッケージ動作確認
node src/mcp/mcp-server.js --version 2>/dev/null || echo "Server file exists"

# 期待される動作:
# - npm install成功
# - src/mcp/mcp-server.jsファイル存在確認
```

**エラー発生時**:

```bash
# Node.jsバージョンが古い場合
# → Node.js v18以上をインストール
nvm install 18
nvm use 18

# npm install失敗時
# → キャッシュクリア
npm cache clean --force
npm install
```

#### Step 1.3: 既存構造確認（10分）

```bash
# src/mcp/mcp-server.jsの構造確認（JavaScript実装）
# initializeTools()メソッド確認（約106行目）
cat src/mcp/mcp-server.js | grep -n "initializeTools()" | head -3

# 期待される出力:
# 80:    this.tools = this.initializeTools();
# 106:  initializeTools() {
# 107:    return {

# ツール定義構造確認（オブジェクト形式）
cat src/mcp/mcp-server.js | head -120 | tail -20

# handleToolsList()メソッド確認（約1096行目）
cat src/mcp/mcp-server.js | grep -n "handleToolsList" | head -2

# package.json確認
cat package.json | grep '"name"'
# → "name": "claude-flow"
```

**記録推奨**:

- `initializeTools()`開始行: 106行目
- `handleToolsList()`開始行: 1096行目
- ツール定義形式: JavaScriptオブジェクト（`{tool_name: {...}}`）

---

### Phase 2: フィルタリング実装（2時間）

**実装方針（Option A - 推奨）**:
`src/mcp/mcp-server.js`の`initializeTools()`メソッドを直接修正し、34ツールのみを定義します。別ファイル作成は不要です。

#### Step 2.1: 許可ツールリスト定義（10分）

まず、必要な34ツール名を明確化します（実装時の参照用）:

```javascript
/**
 * Week 7-10 で使用する34ツールのリスト
 *
 * 削減効果: 90ツール → 34ツール（62.2%削減）
 * トークン削減: 51,300 → 19,380トークン（31,920トークン節約/セッション）
 */
const ALLOWED_TOOLS = [
  // CRITICAL: Memory Management (5ツール)
  'memory_usage',      // 記憶読み書き基本操作
  'memory_search',     // 記憶検索・パターンマッチング
  'memory_persist',    // 永続化・クロスセッション保持
  'memory_namespace',  // 名前空間管理・整理
  'cache_manage',      // キャッシュ管理・最適化

  // CRITICAL: Swarm Management (6ツール)
  'swarm_init',        // Swarm初期化・トポロジー設定
  'swarm_status',      // ステータス確認・ヘルスチェック
  'swarm_scale',       // 自動スケーリング・Agent数調整
  'agent_spawn',       // Agent生成・役割割り当て
  'agent_list',        // Agent一覧・能力確認
  'coordination_sync', // 同期調整・協調動作

  // CRITICAL: Workflow Automation (3ツール)
  'workflow_create',   // ワークフロー作成・定義
  'workflow_execute',  // 実行・並列タスク処理
  'automation_setup',  // 自動化設定・トリガー管理

  // CRITICAL: GitHub Integration (4ツール)
  'github_repo_analyze',  // リポジトリ分析・メトリクス取得
  'github_pr_manage',     // PR管理・マージ・レビュー
  'github_issue_track',   // Issue追跡・トリアージ
  'github_code_review',   // コードレビュー自動化

  // CRITICAL: Performance (2ツール)
  'performance_report',   // パフォーマンスレポート生成
  'bottleneck_analyze',   // ボトルネック分析・特定

  // ADDITIONAL: System Operations (9ツール)
  'terminal_execute',  // Docker/CI/CDコマンド実行
  'config_manage',     // 設定管理・環境変数
  'features_detect',   // 機能検出・プラグイン
  'security_scan',     // セキュリティスキャン
  'backup_create',     // バックアップ作成
  'restore_system',    // システム復元
  'log_analysis',      // ログ分析・エラー検出
  'diagnostic_run',    // 診断実行・問題特定
  'health_check',      // ヘルスチェック・監視

  // NEW: DevOps Automation (5ツール) - Week 8-9一括実装
  'docker_build',         // Docker自動ビルド
  'ci_pipeline_run',      // CI/CDパイプライン実行
  'deployment_status',    // デプロイステータス確認
  'code_quality_check',   // コード品質チェック
  'dependency_audit'      // 依存関係監査
];

console.error('[claude-flow-lite] Total allowed tools:', ALLOWED_TOOLS.length);
// → Expected: 34
```

#### Step 2.2: サーバーロジック修正（1時間50分）

**修正対象ファイル**: `src/mcp/mcp-server.js`

**修正箇所**: `initializeTools()`メソッド（約106行目）

**実装方針**:
元の90ツールの定義をすべて削除し、必要な34ツールのみを新規に定義します。既存のツール定義構造（オブジェクト形式）を維持します。

**修正前（既存コード - 抜粋）**:

```javascript
// src/mcp/mcp-server.js 106行目付近
initializeTools() {
  return {
    // Swarm Coordination Tools (12個)
    swarm_init: {
      name: 'swarm_init',
      description: 'Initialize swarm with topology and configuration',
      inputSchema: { /* ... */ }
    },
    agent_spawn: { /* ... */ },
    task_orchestrate: { /* ... */ },
    // ... 90ツール全て定義されている
  };
}
```

**修正後（34ツールのみ定義）**:

```javascript
// src/mcp/mcp-server.js 106行目付近
initializeTools() {
  // ==========================================
  // Claude Flow Lite: 34 Essential Tools
  // Token Reduction: 62.2% (51,300 → 19,380 tokens)
  // ==========================================

  const ALLOWED_TOOLS = [
    'memory_usage', 'memory_search', 'memory_persist', 'memory_namespace', 'cache_manage',
    'swarm_init', 'swarm_status', 'swarm_scale', 'agent_spawn', 'agent_list', 'coordination_sync',
    'workflow_create', 'workflow_execute', 'automation_setup',
    'github_repo_analyze', 'github_pr_manage', 'github_issue_track', 'github_code_review',
    'performance_report', 'bottleneck_analyze',
    'terminal_execute', 'config_manage', 'features_detect', 'security_scan',
    'backup_create', 'restore_system', 'log_analysis', 'diagnostic_run', 'health_check',
    'docker_build', 'ci_pipeline_run', 'deployment_status', 'code_quality_check', 'dependency_audit'
  ];

  console.error('[claude-flow-lite] ==========================================');
  console.error('[claude-flow-lite] Initializing Claude Flow Lite');
  console.error('[claude-flow-lite] Loading', ALLOWED_TOOLS.length, 'tools (90 → 34, 62.2% reduction)');
  console.error('[claude-flow-lite] Expected token savings: ~31,920 tokens/session');
  console.error('[claude-flow-lite] ==========================================');

  return {
    // ===== MEMORY MANAGEMENT (5ツール) =====
    memory_usage: {
      name: 'memory_usage',
      description: 'Store/retrieve persistent memory with TTL and namespacing',
      inputSchema: {
        type: 'object',
        properties: {
          action: { type: 'string', enum: ['store', 'retrieve', 'list', 'delete', 'search'] },
          key: { type: 'string' },
          value: { type: 'string' },
          namespace: { type: 'string', default: 'default' },
          ttl: { type: 'number' }
        },
        required: ['action']
      }
    },
    memory_search: {
      name: 'memory_search',
      description: 'Search memory with patterns',
      inputSchema: {
        type: 'object',
        properties: {
          pattern: { type: 'string' },
          namespace: { type: 'string' },
          limit: { type: 'number', default: 10 }
        },
        required: ['pattern']
      }
    },
    memory_persist: {
      name: 'memory_persist',
      description: 'Cross-session persistence',
      inputSchema: {
        type: 'object',
        properties: {
          sessionId: { type: 'string' }
        }
      }
    },
    memory_namespace: {
      name: 'memory_namespace',
      description: 'Namespace management',
      inputSchema: {
        type: 'object',
        properties: {
          namespace: { type: 'string' },
          action: { type: 'string' }
        },
        required: ['namespace', 'action']
      }
    },
    cache_manage: {
      name: 'cache_manage',
      description: 'Manage coordination cache',
      inputSchema: {
        type: 'object',
        properties: {
          action: { type: 'string' },
          key: { type: 'string' }
        },
        required: ['action']
      }
    },

    // ===== SWARM MANAGEMENT (6ツール) =====
    swarm_init: {
      name: 'swarm_init',
      description: 'Initialize swarm with topology and configuration',
      inputSchema: {
        type: 'object',
        properties: {
          topology: { type: 'string', enum: ['hierarchical', 'mesh', 'ring', 'star'] },
          maxAgents: { type: 'number', default: 8 },
          strategy: { type: 'string', default: 'auto' }
        },
        required: ['topology']
      }
    },
    swarm_status: {
      name: 'swarm_status',
      description: 'Monitor swarm health and performance',
      inputSchema: {
        type: 'object',
        properties: {
          swarmId: { type: 'string' }
        }
      }
    },
    swarm_scale: {
      name: 'swarm_scale',
      description: 'Auto-scale agent count',
      inputSchema: {
        type: 'object',
        properties: {
          swarmId: { type: 'string' },
          targetSize: { type: 'number' }
        }
      }
    },
    agent_spawn: {
      name: 'agent_spawn',
      description: 'Create specialized AI agents',
      inputSchema: {
        type: 'object',
        properties: {
          type: { type: 'string', enum: ['coordinator', 'analyst', 'optimizer', 'researcher', 'coder', 'tester', 'reviewer'] },
          name: { type: 'string' },
          capabilities: { type: 'array' },
          swarmId: { type: 'string' }
        },
        required: ['type']
      }
    },
    agent_list: {
      name: 'agent_list',
      description: 'List active agents & capabilities',
      inputSchema: {
        type: 'object',
        properties: {
          swarmId: { type: 'string' }
        }
      }
    },
    coordination_sync: {
      name: 'coordination_sync',
      description: 'Sync agent coordination',
      inputSchema: {
        type: 'object',
        properties: {
          swarmId: { type: 'string' }
        }
      }
    },

    // ===== WORKFLOW AUTOMATION (3ツール) =====
    workflow_create: {
      name: 'workflow_create',
      description: 'Create custom workflows',
      inputSchema: {
        type: 'object',
        properties: {
          name: { type: 'string' },
          steps: { type: 'array' },
          triggers: { type: 'array' }
        },
        required: ['name', 'steps']
      }
    },
    workflow_execute: {
      name: 'workflow_execute',
      description: 'Execute predefined workflows',
      inputSchema: {
        type: 'object',
        properties: {
          workflowId: { type: 'string' },
          params: { type: 'object' }
        },
        required: ['workflowId']
      }
    },
    automation_setup: {
      name: 'automation_setup',
      description: 'Setup automation rules',
      inputSchema: {
        type: 'object',
        properties: {
          rules: { type: 'array' }
        },
        required: ['rules']
      }
    },

    // ===== GITHUB INTEGRATION (4ツール) =====
    github_repo_analyze: {
      name: 'github_repo_analyze',
      description: 'Repository analysis',
      inputSchema: {
        type: 'object',
        properties: {
          repo: { type: 'string' },
          analysis_type: { type: 'string', enum: ['code_quality', 'performance', 'security'] }
        },
        required: ['repo']
      }
    },
    github_pr_manage: {
      name: 'github_pr_manage',
      description: 'Pull request management',
      inputSchema: {
        type: 'object',
        properties: {
          repo: { type: 'string' },
          action: { type: 'string', enum: ['review', 'merge', 'close'] },
          pr_number: { type: 'number' }
        },
        required: ['repo', 'action']
      }
    },
    github_issue_track: {
      name: 'github_issue_track',
      description: 'Issue tracking & triage',
      inputSchema: {
        type: 'object',
        properties: {
          repo: { type: 'string' },
          action: { type: 'string' }
        },
        required: ['repo', 'action']
      }
    },
    github_code_review: {
      name: 'github_code_review',
      description: 'Automated code review',
      inputSchema: {
        type: 'object',
        properties: {
          repo: { type: 'string' },
          pr: { type: 'number' }
        },
        required: ['repo', 'pr']
      }
    },

    // ===== PERFORMANCE (2ツール) =====
    performance_report: {
      name: 'performance_report',
      description: 'Generate performance reports with real-time metrics',
      inputSchema: {
        type: 'object',
        properties: {
          format: { type: 'string', default: 'summary', enum: ['summary', 'detailed', 'json'] },
          timeframe: { type: 'string', default: '24h', enum: ['24h', '7d', '30d'] }
        }
      }
    },
    bottleneck_analyze: {
      name: 'bottleneck_analyze',
      description: 'Identify performance bottlenecks',
      inputSchema: {
        type: 'object',
        properties: {
          component: { type: 'string' },
          metrics: { type: 'array' }
        }
      }
    },

    // ===== SYSTEM OPERATIONS (9ツール) =====
    terminal_execute: {
      name: 'terminal_execute',
      description: 'Execute terminal commands',
      inputSchema: {
        type: 'object',
        properties: {
          command: { type: 'string' },
          args: { type: 'array' }
        },
        required: ['command']
      }
    },
    config_manage: {
      name: 'config_manage',
      description: 'Configuration management',
      inputSchema: {
        type: 'object',
        properties: {
          action: { type: 'string' },
          config: { type: 'object' }
        },
        required: ['action']
      }
    },
    features_detect: {
      name: 'features_detect',
      description: 'Feature detection',
      inputSchema: {
        type: 'object',
        properties: {
          component: { type: 'string' }
        }
      }
    },
    security_scan: {
      name: 'security_scan',
      description: 'Security scanning',
      inputSchema: {
        type: 'object',
        properties: {
          target: { type: 'string' },
          depth: { type: 'string' }
        },
        required: ['target']
      }
    },
    backup_create: {
      name: 'backup_create',
      description: 'Create system backups',
      inputSchema: {
        type: 'object',
        properties: {
          components: { type: 'array' },
          destination: { type: 'string' }
        }
      }
    },
    restore_system: {
      name: 'restore_system',
      description: 'System restoration',
      inputSchema: {
        type: 'object',
        properties: {
          backupId: { type: 'string' }
        },
        required: ['backupId']
      }
    },
    log_analysis: {
      name: 'log_analysis',
      description: 'Log analysis & insights',
      inputSchema: {
        type: 'object',
        properties: {
          logFile: { type: 'string' },
          patterns: { type: 'array' }
        },
        required: ['logFile']
      }
    },
    diagnostic_run: {
      name: 'diagnostic_run',
      description: 'System diagnostics',
      inputSchema: {
        type: 'object',
        properties: {
          components: { type: 'array' }
        }
      }
    },
    health_check: {
      name: 'health_check',
      description: 'System health monitoring',
      inputSchema: {
        type: 'object',
        properties: {
          components: { type: 'array' }
        }
      }
    },

    // ===== DEVOPS AUTOMATION (5ツール) - Week 8-9一括実装 =====
    docker_build: {
      name: 'docker_build',
      description: 'Docker automated build with multi-stage support',
      inputSchema: {
        type: 'object',
        properties: {
          context: { type: 'string' },
          dockerfile: { type: 'string' },
          tags: { type: 'array' }
        }
      }
    },
    ci_pipeline_run: {
      name: 'ci_pipeline_run',
      description: 'CI/CD pipeline execution for GitHub Actions',
      inputSchema: {
        type: 'object',
        properties: {
          workflow: { type: 'string' },
          branch: { type: 'string' }
        }
      }
    },
    deployment_status: {
      name: 'deployment_status',
      description: 'Deployment status verification',
      inputSchema: {
        type: 'object',
        properties: {
          environment: { type: 'string' },
          service: { type: 'string' }
        }
      }
    },
    code_quality_check: {
      name: 'code_quality_check',
      description: 'Code quality check with static analysis',
      inputSchema: {
        type: 'object',
        properties: {
          path: { type: 'string' },
          rules: { type: 'array' }
        }
      }
    },
    dependency_audit: {
      name: 'dependency_audit',
      description: 'Dependency audit for vulnerabilities',
      inputSchema: {
        type: 'object',
        properties: {
          manifest: { type: 'string' },
          severity: { type: 'string' }
        }
      }
    }
  };
}
```

**重要ポイント**:

1. **34ツールのみ定義**: 元の90ツールを削除し、必要な34ツールのみを新規定義
2. **デバッグログ追加**: 起動時に34ツール読み込みを確認可能
3. **既存構造維持**: オブジェクト形式（`{tool_name: {...}}`）を維持
4. **Week 8-9ツール一括実装**: DevOpsカテゴリの5ツールも最初から含める

#### Step 2.3: 動作確認（30分）

**JavaScript構文チェック**:

```bash
# Node.js構文チェック（ビルド不要）
node --check src/mcp/mcp-server.js

# エラーがなければ何も出力されず、終了コード0で完了
echo $?  # 0が表示されればOK
```

**エラー発生時のデバッグ**:

```bash
# Node.js詳細エラー出力
node --check src/mcp/mcp-server.js 2>&1

# 典型的なエラーと対策:
# 1. "SyntaxError: Unexpected token"
#    → 構文エラー: カンマ・括弧の不足を確認
#
# 2. "ReferenceError: ALLOWED_TOOLS is not defined"
#    → ALLOWED_TOOLS配列の定義位置確認（initializeTools()内）
#
# 3. "SyntaxError: Invalid or unexpected token"
#    → 文字列リテラルのクォート確認
```

**ローカルテスト実行**:

```bash
# MCP Inspectorでツール一覧確認
npx @modelcontextprotocol/inspector node src/mcp/mcp-server.js

# 期待される出力（stderr）:
# [claude-flow-lite] ==========================================
# [claude-flow-lite] Initializing Claude Flow Lite
# [claude-flow-lite] Loading 34 tools (90 → 34, 62.2% reduction)
# [claude-flow-lite] Expected token savings: ~31,920 tokens/session
# [claude-flow-lite] ==========================================
#
# MCP Inspector起動: http://localhost:3000
```

**Inspector UIでの確認**:

1. ブラウザで`http://localhost:3000`を開く
2. "List Tools"ボタンクリック
3. 表示されるツール数が**34個**であることを確認
4. 以下のツールが含まれることを確認:
   - `memory_usage`、`memory_search`、`memory_persist`、`memory_namespace`、`cache_manage`（Memory: 5個）
   - `swarm_init`、`swarm_status`、`swarm_scale`、`agent_spawn`、`agent_list`、`coordination_sync`（Swarm: 6個）
   - `workflow_create`、`workflow_execute`、`automation_setup`（Workflow: 3個）
   - `github_repo_analyze`、`github_pr_manage`、`github_issue_track`、`github_code_review`（GitHub: 4個）
   - `performance_report`、`bottleneck_analyze`（Performance: 2個）
   - `terminal_execute`、`config_manage`、`features_detect`、`security_scan`、`backup_create`、`restore_system`、`log_analysis`、`diagnostic_run`、`health_check`（System: 9個）
   - `docker_build`、`ci_pipeline_run`、`deployment_status`、`code_quality_check`、`dependency_audit`（DevOps: 5個）

**コマンドライン動作確認**:

```bash
# 標準入力でツール一覧取得
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | node src/mcp/mcp-server.js

# 期待される出力（簡略版）:
# {"jsonrpc":"2.0","id":1,"result":{"tools":[
#   {"name":"memory_usage","description":"Store/retrieve persistent memory..."},
#   {"name":"swarm_init","description":"Initialize swarm..."},
#   ... (合計34ツール)
# ]}}
```

**検証成功基準**:

- ✅ 構文チェックエラーなし（`node --check` 終了コード0）
- ✅ ツール数が正確に34個（Inspector UIまたはJSON-RPC応答で確認）
- ✅ デバッグログでツール数・削減率表示（stderr出力）
- ✅ 90→34削減が正しく動作

---

### Phase 3: パッケージ公開（1時間）

#### Step 3.1: package.json更新（15分）

**修正対象**: `package.json`

**修正内容**:

```json
{
  "name": "@your-username/claude-flow-lite",
  "version": "2.7.0-lite.1",
  "description": "Lightweight Claude Flow MCP server with 34 essential tools (Week 7-10). Token reduction: 62.2% (51,300 → 19,380 tokens)",
  "keywords": [
    "mcp",
    "model-context-protocol",
    "claude-flow",
    "lite",
    "filtered",
    "token-optimization"
  ],
  "author": "Your Name <your-email@example.com>",
  "license": "MIT",
  "repository": {
    "type": "git",
    "url": "https://github.com/your-username/claude-flow-lite.git"
  },
  "homepage": "https://github.com/your-username/claude-flow-lite#readme",
  "bugs": {
    "url": "https://github.com/your-username/claude-flow-lite/issues"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

**重要**: `@your-username`を実際のnpmアカウント名に置き換え

**確認コマンド**:

```bash
# package.json内容確認
cat package.json | grep '"name"'
# → "name": "@your-username/claude-flow-lite",

cat package.json | grep '"version"'
# → "version": "2.7.0-lite.1",
```

#### Step 3.2: npm公開（15分）

**公開前確認**:

```bash
# npmログイン状態確認
npm whoami
# → your-username （ログイン中）

# パッケージ名重複確認
npm view @your-username/claude-flow-lite
# → 404 Not Found （新規パッケージなのでOK）

# 公開前ドライラン（推奨）
npm publish --dry-run

# 期待される出力:
# npm notice
# npm notice 📦  @your-username/claude-flow-lite@2.7.0-lite.1
# npm notice === Tarball Contents ===
# npm notice 25.8kB src/mcp/mcp-server.js
# npm notice 1.2kB  package.json
# npm notice 5.1kB  README.md
# npm notice === Tarball Details ===
# npm notice name:          @your-username/claude-flow-lite
# npm notice version:       2.7.0-lite.1
# npm notice package size:  14.2 kB
# npm notice unpacked size: 38.7 kB
# npm notice total files:   6
```

**本番公開**:

```bash
# 公開実行
npm publish --access public --tag lite

# 期待される出力:
# + @your-username/claude-flow-lite@2.7.0-lite.1

# 公開確認
npm view @your-username/claude-flow-lite

# 期待される出力:
# @your-username/claude-flow-lite@2.7.0-lite.1 | MIT | deps: none | versions: 1
# Lightweight Claude Flow MCP server with 34 essential tools (Week 7-10)
# https://github.com/your-username/claude-flow-lite#readme
```

**エラー発生時**:

```bash
# 1. "You must be logged in to publish packages"
npm login

# 2. "Package name too similar to existing package"
# → package.jsonのnameを変更（例: claude-flow-lite-29tools）

# 3. "You do not have permission to publish"
# → npm adduser で新規アカウント作成
```

#### Step 3.3: READMEドキュメント作成（30分）

**新規ファイル作成**: プロジェクトルートに`README.md`

```markdown
# Claude Flow Lite 🚀

Lightweight version of [Claude Flow](https://github.com/ruvnet/claude-flow) MCP server with **34 essential tools** for Week 7-10 implementation.

[![npm version](https://badge.fury.io/js/%40your-username%2Fclaude-flow-lite.svg)](https://www.npmjs.com/package/@your-username/claude-flow-lite)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Node.js](https://img.shields.io/badge/node-%3E%3D18.0.0-brightgreen)](https://nodejs.org/)

## ✨ Token Savings

| Version | Tools | Tokens | Reduction |
|---------|-------|--------|-----------|
| **Original** | 90 tools | ~51,300 tokens | - |
| **Lite** | **34 tools** | **~19,380 tokens** | **62.2%** ↓ |

**Annual savings**: 36,160,800 tokens (20 sessions/week × 52 weeks)

---

## 🎯 Included Tools (34)

### Critical Tools (20)
- **Memory Management (5)**: `memory_usage`, `memory_search`, `memory_persist`, `memory_namespace`, `cache_manage`
- **Swarm Management (6)**: `swarm_init`, `swarm_status`, `swarm_scale`, `agent_spawn`, `agent_list`, `coordination_sync`
- **Workflow Automation (3)**: `workflow_create`, `workflow_execute`, `automation_setup`
- **GitHub Integration (4)**: `github_repo_analyze`, `github_pr_manage`, `github_issue_track`, `github_code_review`
- **Performance (2)**: `performance_report`, `bottleneck_analyze`

### Additional Tools (9)
- **System Operations**: `terminal_execute`, `config_manage`, `features_detect`, `security_scan`, `backup_create`, `restore_system`, `log_analysis`, `diagnostic_run`, `health_check`

See [docs/required_tools.md](docs/required_tools.md) for detailed tool descriptions.

---

## 📦 Installation

### Global Installation
```bash
npm install -g @your-username/claude-flow-lite
```

### Project-Specific Installation

```bash
npm install --save-dev @your-username/claude-flow-lite
```

<!-- ==========================================
     FALLBACK IMPROVEMENT
     追加日: 2025-11-10
     対象: ローカル専用フォールバック設定（npm unavailable + no network対応）
     修正ファイル: Claude-Flow_MCPLoading削減の実装計画.md
     ========================================== -->

### Local-Only Installation (Fallback)

**使用ケース**: npm package unavailable、ネットワーク接続なし

```bash
# Clone repository to local workspace
cd ~/workspace
git clone https://github.com/yuta-scope/ruv-claude-flow.git
cd ruv-claude-flow

# Install dependencies
npm install

# Verify installation
node src/mcp/mcp-server.js --version
# → {"version":"2.7.0-lite.7"}
```

**ローカルパス設定**:

- macOS/Linux: `/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js`
- Windows: `C:\Users\YourUser\workspace\ruv-claude-flow\src\mcp\mcp-server.js`

<!-- ========================================== -->

---

## 🚀 Usage

### Configuration

Add to **`.mcp.json`** in your project root:

<!-- ==========================================
     FALLBACK IMPROVEMENT
     追加日: 2025-11-10
     対象: 3-Tier Fallback Architecture設定例
     修正ファイル: Claude-Flow_MCPLoading削減の実装計画.md
     ========================================== -->

#### Primary: npm Package (推奨)

```json
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@your-username/claude-flow-lite@2.7.0-lite.7",
        "mcp",
        "start"
      ],
      "env": {}
    }
  }
}
```

#### Fallback: Local Source (npm unavailable時)

```json
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js"
      ],
      "env": {}
    }
  }
}
```

#### Advanced: Wrapper-Based Auto-Failover [ Task 17 ]

```json
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server-wrapper.js"
      ],
      "env": {
        "CLAUDE_FLOW_FALLBACK_PATH": "/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js",
        "CLAUDE_FLOW_DEBUG": "true"
      }
    }
  }
}
```

**Wrapper動作仕様**:

```
Tier 1: npm package (npx @yuta-scope/claude-flow-lite)
  ↓ (on failure: ENOENT, network error)
Tier 2: Local source (CLAUDE_FLOW_FALLBACK_PATH)
  ↓ (on failure: file not found)
Tier 3: Error notification with recovery guidance
```

<!-- ========================================== -->

### Restart Claude Code

1. Close Claude Code
2. Reopen project
3. Verify MCP Server loads **34 tools** (Settings → MCP Servers)

---

## 📊 Performance Metrics

### Token Consumption (Per Session)

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Tools loaded | 90 | 34 | 56 tools (62.2%) |
| Token consumption | 51,300 | 19,380 | 31,920 tokens |
| Session overhead | High | Low | 62.2% ↓ |

### ROI Analysis

| Period | Sessions | Token Savings | Cumulative |
|--------|----------|---------------|------------|
| **Week 1** | 20 | 695,400 | 695,400 |
| **Month 1** | 80 | 2,781,600 | 2,781,600 |
| **Year 1** | 1,040 | 36,160,800 | 36,160,800 |

**Investment recovery**: 1 week (20 sessions)

---

## 🔧 Development

### Prerequisites

- Node.js v18+
- npm v9+

### Build from Source

```bash
# Clone repository
git clone https://github.com/your-username/claude-flow-lite.git
cd claude-flow-lite

# Install dependencies
npm install

# Syntax check (no build needed for JavaScript)
node --check src/mcp/mcp-server.js

# Local testing
npx @modelcontextprotocol/inspector node src/mcp/mcp-server.js
```

<!-- ==========================================
     FALLBACK IMPROVEMENT
     追加日: 2025-11-10
     対象: ローカル開発でのフォールバック設定
     修正ファイル: Claude-Flow_MCPLoading削減の実装計画.md
     ========================================== -->

### Local Development with Fallback

**Use Case**: npm package開発中、ネットワーク接続なし

```bash
# ローカルソースで直接起動
cd /Users/yuta/workspace/ruv-claude-flow
node src/mcp/mcp-server.js

# 期待される出力:
# [claude-flow-lite] ==========================================
# [claude-flow-lite] Initializing Claude Flow Lite
# [claude-flow-lite] Loading 34 tools (90 → 34, 62.2% reduction)
# [claude-flow-lite] Expected token savings: ~31,920 tokens/session
# [claude-flow-lite] ==========================================
```

**プロジェクト統合（開発版）**:

```json
{
  "mcpServers": {
    "claude-flow-lite-dev": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js"
      ],
      "env": {
        "NODE_ENV": "development"
      }
    }
  }
}
```

**メリット**:

- npm publish不要
- リアルタイム修正反映
- デバッグログ有効

<!-- ========================================== -->

### Testing

```bash
# Unit tests (if implemented)
npm test

# MCP Inspector
npx @modelcontextprotocol/inspector node src/mcp/mcp-server.js
# → Open http://localhost:3000
# → Click "List Tools"
# → Verify 34 tools displayed
```

---

## 🗂️ Version History

### v2.7.0-lite.1 (2025-11-08)

- Initial release
- 34 essential tools for Week 7-10
- 62.2% token reduction
- Based on Claude Flow v2.7.30

### Roadmap

#### Week 7-10 (v2.7.0-lite.1) - **All-in-One Implementation**

- **All 34 tools implemented from the start**
- No incremental updates needed (29→32→34 eliminated)
- Week 8-9 tools already included:
  - Docker/CI/CD: `docker_build`, `ci_pipeline_run`, `deployment_status`
  - Optimization: `code_quality_check`, `dependency_audit`
- Total: **34 tools** (constant)

**Design Decision**: 一括実装により、段階的更新を回避し、忘れる心配を解消

---

## 📝 License

MIT License - see [LICENSE](LICENSE) for details

---

## 🙏 Acknowledgments

Based on [Claude Flow](https://github.com/ruvnet/claude-flow) by ruvnet.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/claude-flow-lite/issues)
- **Documentation**: [docs/](docs/)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## 🔗 Related Projects

- [Claude Flow (Original)](https://github.com/ruvnet/claude-flow)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Claude Code](https://claude.com/code)

---

**Made with ❤️ for token efficiency**

```

**ファイル保存確認**:
```bash
# README.md作成確認
ls -lh README.md
# → -rw-r--r--  1 user  staff  5.8K Nov  8 12:00 README.md

# 重要セクション確認
cat README.md | grep "## ✨ Token Savings"
cat README.md | grep "62.2%"
```

---

### Phase 4: プロジェクト統合（30分）

#### Step 4.1: `.mcp.json`作成（10分）

**作成場所**: プロジェクトルート

<!-- ==========================================
     FALLBACK IMPROVEMENT
     追加日: 2025-11-10
     対象: プロジェクト統合時のフォールバック設定
     修正ファイル: Claude-Flow_MCPLoading削減の実装計画.md
     ========================================== -->

**Primary Configuration (推奨): npm package使用**

```bash
# プロジェクトルートに移動
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# .mcp.json作成 (npm package)
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@your-username/claude-flow-lite@2.7.0-lite.7",
        "mcp",
        "start"
      ],
      "env": {},
      "disabled": false
    }
  }
}
EOF

# ファイル作成確認
ls -lh .mcp.json
# → -rw-r--r--  1 user  staff  234B Nov  8 12:00 .mcp.json

# 内容確認
cat .mcp.json
```

**重要**: `@your-username`を実際のnpmアカウント名に置き換え

**Fallback Configuration: npm unavailable時のローカルソース使用**

```bash
# ネットワーク接続なし、またはnpmパッケージ取得失敗時
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite-local": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js"
      ],
      "env": {},
      "disabled": false
    }
  }
}
EOF
```

**Windows環境の場合**:

```json
{
  "mcpServers": {
    "claude-flow-lite-local": {
      "type": "stdio",
      "command": "node",
      "args": [
        "C:\\Users\\YourUser\\workspace\\ruv-claude-flow\\src\\mcp\\mcp-server.js"
      ],
      "env": {},
      "disabled": false
    }
  }
}
```

**設定切替方法**:

```bash
# Primary (npm) → Fallback (local) 切替
cp .mcp.json .mcp.json.npm.bak
cp .mcp.json.local .mcp.json
# Claude Code再起動

# Fallback → Primary 復帰
cp .mcp.json.npm.bak .mcp.json
# Claude Code再起動
```

<!-- ========================================== -->

**.gitignore確認**:

```bash
# .mcp.jsonをgit管理対象とする（推奨）
git add .mcp.json
git status
# → new file:   .mcp.json

# コミット（任意）
git commit -m "feat: add Claude Flow Lite MCP configuration (34 tools, 62.2% token reduction)"
```

#### Step 4.2: Claude Code再起動・動作確認（10分）

**再起動手順**:

1. Claude Codeを完全終了
2. プロジェクトを再度開く
3. MCP Serversが自動起動するまで待機（10-30秒）

**動作確認**:

```bash
# Claude Code UI: Settings → MCP Servers → claude-flow-lite
# 期待される表示:
# ✅ claude-flow-lite (connected)
#    Status: Running
#    Tools: 34
#    Transport: stdio
```

**ログ確認**（任意）:

```bash
# Claude Code MCP ログ確認（Mac）
tail -f ~/Library/Application\ Support/Claude/mcp.log | grep "claude-flow-lite"

# 期待される出力:
# [claude-flow-lite] ==========================================
# [claude-flow-lite] Tool Filtering Summary
# [claude-flow-lite] ==========================================
# [claude-flow-lite] Total available tools: 90
# [claude-flow-lite] Allowed tools: 34
# [claude-flow-lite] Filtered tools: 34
# [claude-flow-lite] Reduction: 62.2%
# [claude-flow-lite] Expected token savings: ~31,920 tokens/session
# [claude-flow-lite] ==========================================
# [claude-flow-lite] ✅ Tool filtering successful!
```

**トークン消費確認**:

```bash
# 新規セッション開始
# Claude Code UI: 右上のトークン使用量確認
# 期待値: ~19,380トークン（従来 ~51,300トークン）

# 削減率計算
# (51,300 - 19,380) / 51,300 × 100 = 62.2%
```

#### Step 4.3: ドキュメント更新（10分）

**更新対象**: `docs/claude_flow/required_tools.md`

**更新内容**（末尾に追記）:

```markdown
## 制約事項と対策（更新版）

### 1. ツールフィルタリング実装完了 ✅

**対策実施日**: 2025年11月08日

**実装内容**:
- `@your-username/claude-flow-lite@2.7.0-lite.1`使用
- 34ツールのみロード（90→34、62.2%削減）
- トークン消費: 51,300 → 19,380（**31,920トークン節約/セッション**）

**設定ファイル**:
- `.mcp.json`: プロジェクト固有設定（gitコミット済み）
- `~/.claude.json`: グローバル設定（変更不要、他プロジェクト安全）

**パッケージ管理**:
```bash
# インストール
npm install -g @your-username/claude-flow-lite

# 更新
npm update -g @your-username/claude-flow-lite

# バージョン確認
npm view @your-username/claude-flow-lite version
```

**バージョン戦略（修正版）**:

- Week 7-10: `2.7.0-lite.1` (34ツール) ← **一括実装版**
- バージョンアップ不要（段階的実装を廃止）
- 全ツール最初から含まれる（Docker/CI/CD + 最適化ツール）
- 本番リリース準備完了

**ROI実績**:

- 実装時間: 4時間
- 回収期間: 1週間（20セッション）
- 年間削減: 36,160,800トークン

**動作確認**:

- ✅ MCP Server起動: 34ツール
- ✅ トークン削減: 62.2%
- ✅ エラー発生: なし
- ✅ 既存プロジェクト影響: なし

```

**ファイル保存確認**:
```bash
# 更新確認
git diff docs/claude_flow/required_tools.md

# コミット
git add docs/claude_flow/required_tools.md
git commit -m "docs(claude_flow): update with implementation results (62.2% token reduction)"
```

---

## トラブルシューティング

### Phase 1: 準備フェーズ

#### エラー: `git clone`失敗

**症状**:

```
fatal: unable to access 'https://github.com/ruvnet/claude-flow.git/':
Could not resolve host: github.com
```

**原因**:

- ネットワーク接続問題
- GitHub接続制限

**解決策**:

```bash
# 1. ネットワーク確認
ping github.com

# 2. SSH鍵使用
git clone git@github.com:ruvnet/claude-flow.git ruv-claude-flow

# 3. プロキシ設定（企業環境）
git config --global http.proxy http://proxy.example.com:8080
```

#### エラー: `npm install`失敗

**症状**:

```
npm ERR! code ENOENT
npm ERR! syscall open
npm ERR! path /path/to/package.json
```

**原因**:

- ディレクトリ間違い
- `package.json`不在

**解決策**:

```bash
# 現在のディレクトリ確認
pwd
# → ~/workspace/ruv-claude-flow （正しい）

# package.json存在確認
ls -lh package.json

# ディレクトリ移動
cd ~/workspace/ruv-claude-flow
```

---

### Phase 2: フィルタリング実装フェーズ

#### エラー: TypeScriptコンパイル失敗

**症状**:

```
lib/server.ts:123:45 - error TS2307: Cannot find module './allowed-tools.js' or its corresponding type declarations.
```

**原因**:

- `lib/allowed-tools.ts`未作成
- import文のパス間違い

**解決策**:

```bash
# 1. ファイル存在確認
ls -lh lib/allowed-tools.ts

# 2. import文確認（拡張子.js必須）
cat lib/server.ts | grep "import.*allowed-tools"
# → import { ALLOWED_TOOL_NAMES } from './allowed-tools.js';

# 3. 拡張子修正
# TypeScriptでは、importパスに.js拡張子必須（ビルド後のJSファイルを指す）
```

#### エラー: フィルタリング後ツール数0

**症状**:

```
[claude-flow-lite] Filtered tools: 0
[claude-flow-lite] ⚠️  WARNING: Filtered tool count mismatch!
[claude-flow-lite] Expected: 29, Actual: 0
```

**原因**:

- `allTools`配列の構造が想定と異なる
- ツール名のキーが`name`ではない

**デバッグ**:

```bash
# allTools配列の構造確認
cat lib/server.ts | grep -A 3 "const allTools = \["

# ツール定義例確認
cat lib/server.ts | grep -A 1 "memory_usage"

# 期待される構造:
# {
#   name: 'memory_usage',
#   description: '...',
#   inputSchema: { ... }
# }

# もしツール名のキーがtool_nameの場合:
# const filteredTools = allTools.filter(tool =>
#   ALLOWED_TOOL_NAMES.includes(tool.tool_name)  // ← nameをtool_nameに修正
# );
```

---

### Phase 3: パッケージ公開フェーズ

#### エラー: npm公開権限エラー

**症状**:

```
npm ERR! code E403
npm ERR! 403 403 Forbidden - PUT https://registry.npmjs.org/@your-username/claude-flow-lite
npm ERR! 403 You do not have permission to publish "@your-username/claude-flow-lite". Are you logged in as the correct user?
```

**原因**:

- npmアカウント未ログイン
- アカウント名の間違い

**解決策**:

```bash
# 1. ログイン状態確認
npm whoami
# → Not logged in （ログインが必要）

# 2. ログイン実行
npm login
# → Username: your-username
# → Password: ********
# → Email: your-email@example.com

# 3. package.json確認
cat package.json | grep '"name"'
# → "name": "@your-username/claude-flow-lite"
#   ^^^^^^^^^^^^^^^^ npmアカウント名と一致必須
```

#### エラー: パッケージ名重複

**症状**:

```
npm ERR! code E409
npm ERR! 409 Conflict - PUT https://registry.npmjs.org/@your-username/claude-flow-lite
npm ERR! 409 Cannot publish over existing version.
```

**原因**:

- 同じバージョン番号で再公開しようとした

**解決策**:

```bash
# バージョン番号を上げて再公開
npm version 2.7.0-lite.2
npm publish --access public --tag lite
```

---

### Phase 4: プロジェクト統合フェーズ

#### エラー: Claude Code MCP起動失敗

**症状**:
Claude Code UI: MCP Servers画面で「claude-flow-lite」が"Failed to start"表示

**原因**:

- `.mcp.json`のJSON構文エラー
- パッケージ名の間違い
- ネットワーク接続問題（npm registry）

**デバッグ**:

```bash
# 1. JSON構文チェック
cat .mcp.json | jq .
# エラー時: parse error at line X
# → JSON構文修正

# 2. 手動起動テスト
npx @your-username/claude-flow-lite@2.7.0-lite.1 mcp start

# 期待される出力:
# [claude-flow-lite] ==========================================
# [claude-flow-lite] Tool Filtering Summary
# ...

# 3. Claude Code MCP ログ確認
tail -50 ~/Library/Application\ Support/Claude/mcp.log

# 4. パッケージ名確認
npm view @your-username/claude-flow-lite
# → パッケージが存在することを確認
```

#### エラー: トークン削減効果が見られない

**症状**:
Claude Code起動後もトークン消費量が51,300トークンのまま

**原因**:

- `.mcp.json`が読み込まれていない
- グローバル設定（`~/.claude.json`）が優先されている
- MCP Server切り替え失敗

**解決策**:

```bash
# 1. Claude Code完全再起動
killall "Claude Code"  # Mac
# または: Claude Code → Quit

# 2. .mcp.json確認
cat .mcp.json | jq '.mcpServers["claude-flow-lite"]'

# 3. グローバル設定確認（競合チェック）
cat ~/.claude.json | jq '.mcpServers["claude-flow"]'
# → グローバル設定のclaude-flowを無効化する必要はない
#   .mcp.jsonが優先される

# 4. MCP Server選択確認
# Claude Code UI: Settings → MCP Servers
# → claude-flow-lite が有効、claude-flow が無効であることを確認
```

<!-- ==========================================
     FALLBACK IMPROVEMENT
     追加日: 2025-11-10
     対象: npm unavailable + network failureシナリオのトラブルシューティング
     修正ファイル: Claude-Flow_MCPLoading削減の実装計画.md
     ========================================== -->

#### エラー: npm package取得失敗（ネットワーク障害）

**症状**:

```
[claude-flow-lite] Failed to start
npm ERR! code ENETUNREACH
npm ERR! errno ENETUNREACH
npm ERR! network request to https://registry.npmjs.org/@your-username%2fclaude-flow-lite failed
```

**原因**:

- ネットワーク接続なし
- npm registry接続障害
- プロキシ設定問題

**即座復旧（Local Fallback）**:

```bash
# 1. ローカルソースが利用可能か確認
ls -lh /Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js
# → -rw-r--r--  ... mcp-server.js （存在確認）

# 2. .mcp.json をローカル設定に切替
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite-local": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js"
      ],
      "env": {},
      "disabled": false
    }
  }
}
EOF

# 3. Claude Code再起動
killall "Claude Code"
# プロジェクト再度開く

# 4. 動作確認
# Claude Code UI: Settings → MCP Servers → claude-flow-lite-local
# → ✅ Running, 34 tools
```

**恒久対策（ネットワーク復旧後）**:

```bash
# npm設定に戻す
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@your-username/claude-flow-lite@2.7.0-lite.7",
        "mcp",
        "start"
      ],
      "env": {},
      "disabled": false
    }
  }
}
EOF

# Claude Code再起動
```

#### エラー: Local Fallback起動失敗

**症状**:

```
[claude-flow-lite-local] Failed to start
Error: Cannot find module '/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js'
```

**原因**:

- ローカルソースのパス間違い
- リポジトリ未クローン
- ファイル移動・削除

**解決策**:

```bash
# 1. ファイル存在確認
ls -lh /Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js

# 存在しない場合 → リポジトリクローン
cd ~/workspace
git clone https://github.com/yuta-scope/ruv-claude-flow.git
cd ruv-claude-flow
npm install

# 2. 正しいパス取得
pwd
# → /Users/yuta/workspace/ruv-claude-flow

# 絶対パス確認
realpath src/mcp/mcp-server.js
# → /Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js

# 3. .mcp.json のパス修正
# args配列の絶対パスを上記の結果に置き換え

# 4. 動作テスト（手動起動）
node /Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js
# 期待される出力:
# [claude-flow-lite] Initializing Claude Flow Lite
# [claude-flow-lite] Loading 34 tools (90 → 34, 62.2% reduction)
```

#### エラー: Wrapper未実装エラー（Future）

**症状**:

```
Error: Cannot find module 'mcp-server-wrapper.js'
```

**原因**:

- Wrapper-based auto-failoverがまだ実装されていない
- Advanced設定を使用しようとした

**解決策**:

```bash
# 現時点では Primary または Fallback 設定を使用
# Wrapper実装は将来のタスク

# Primary設定に戻す
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "npx",
      "args": [
        "@your-username/claude-flow-lite@2.7.0-lite.7",
        "mcp",
        "start"
      ],
      "env": {},
      "disabled": false
    }
  }
}
EOF
```

<!-- ========================================== -->

---

## 検証・測定

### ベースライン測定（実装前）

**目的**: 実装前のトークン消費量を記録し、削減効果を定量化

**測定手順**:

```markdown
# ベースライン測定シート

## 測定日時
YYYY-MM-DD HH:MM

## Claude Flow現状
- ツール数: 90
- 推定トークン消費: 51,300トークン
- MCP Server起動時間: ___秒
- エラー発生: なし

## 測定方法
1. Claude Code起動
2. 新規セッション開始
3. MCP Servers画面確認（Settings → MCP Servers → claude-flow）
4. Context使用量記録

## スクリーンショット
保存先: `docs/claude_flow/before_optimization.png`
```

**記録推奨項目**:

- 日時
- ツール数（90）
- トークン消費量（目視またはAPI）
- スクリーンショット

---

### 実装後測定（検証）

**目的**: 実装効果の確認、目標達成率の測定

**測定手順**:

```markdown
# 実装後測定シート

## 測定日時
YYYY-MM-DD HH:MM

## Claude Flow Lite実装結果
- ツール数: 29
- 推定トークン消費: 19,380トークン
- MCP Server起動時間: ___秒
- エラー発生: なし

## 削減効果
- ツール削減率: 62.2% (90 → 29)
- トークン削減率: 62.2% (51,300 → 19,380)
- 削減量: 31,920トークン/セッション

## 測定方法
1. Claude Code再起動
2. 新規セッション開始
3. MCP Servers画面確認（Settings → MCP Servers → claude-flow-lite）
4. Context使用量記録

## スクリーンショット
保存先: `docs/claude_flow/after_optimization.png`
```

---

### 成功基準チェックリスト

#### 定量的指標

- [ ] **ツール削減率**: 62.2% (90→29) 達成
  - 測定: MCP Server起動時ツール数確認
  - 目標値: 34ツール
  - 実測値: ___ツール

- [ ] **トークン削減**: 31,920トークン/セッション 達成
  - 測定: Claude Code Dashboard確認
  - 目標値: ~19,380トークン
  - 実測値: ___トークン

- [ ] **実装時間**: 4時間以内 達成
  - 測定: タイムトラッキング
  - 目標値: 4時間
  - 実測値: ___時間

- [ ] **エラー率**: 0% 達成
  - 測定: Week 7-10実行時エラー監視
  - 目標値: 0%
  - 実測値: ___%

#### 定性的指標

- [ ] Week 7開始までに導入完了
  - 目標日: 2025-10-01
  - 完了日: ___________

- [ ] 既存プロジェクト（グローバル設定）に影響なし
  - 確認: 他プロジェクトでClaude Flow動作確認

- [ ] Week 8-10での追加ツール拡張が容易
  - 確認: `lib/allowed-tools.ts`への追加手順理解

- [ ] ドキュメント整備完了
  - 確認: `docs/claude_flow/required_tools.md`更新済み

---

### ROI計算（実測値）

**トークン節約実績**:

```markdown
# ROI実績レポート

## 測定期間
Week 7開始日（2025-10-01）から Week 10終了日（2025-10-60）まで

## トークン削減実績
- 週あたりセッション数: 20回
- トークン削減/セッション: 31,920トークン
- 週間削減量: 695,400トークン
- 4週間累計削減量: 2,781,600トークン

## 投資回収
- 実装投資: 4時間
- 回収期間: 1週間（20セッション）
- 回収完了日: 2025-10-07

## 年間予測削減量
- 52週 × 695,400トークン/週 = 36,160,800トークン/年
```

---

## 付録

### A. Week 8-10ツール拡張ガイド

#### Week 8: Docker/CI/CD強化（+3ツール）

**追加ツール**:

1. `docker_build`: Docker自動ビルド
2. `ci_pipeline_run`: CI/CDパイプライン実行
3. `deployment_status`: デプロイステータス確認

**拡張手順**:

```bash
# 1. lib/allowed-tools.ts 修正
cd ~/workspace/claude-flow-lite/src/claude-flow

# SYSTEM配列に追加
export const ALLOWED_TOOLS = {
  // ...
  SYSTEM: [
    'terminal_execute',
    'config_manage',
    'features_detect',
    'security_scan',
    'backup_create',
    'restore_system',
    'log_analysis',
    'diagnostic_run',
    'health_check',
    // ✨ Week 8追加
    'docker_build',        // Docker自動ビルド
    'ci_pipeline_run',     // CI/CDパイプライン実行
    'deployment_status'    // デプロイステータス確認
  ]
}

# 2. ビルド・テスト
npm run build
npx @modelcontextprotocol/inspector npx ts-node lib/index.ts
# → 32ツール表示確認

# 3. バージョンアップ
npm version 2.7.0-lite.2

# 4. 公開
npm publish --access public --tag lite

# 5. プロジェクト設定更新
cd /Users/yuta/Yuta/python/api-test-devops-portfolio
# .mcp.json修正: 2.7.0-lite.1 → 2.7.0-lite.2

# 6. Claude Code再起動
```

---

### B. ローカルのみ使用（npm公開スキップ版）

**使用ケース**: npm公開せず、プロジェクト内でのみ使用

**実装手順（Phase 3スキップ版）**:

```bash
# Phase 1-2は通常通り実行
# Phase 3: パッケージ公開 → スキップ

# Phase 4: プロジェクト統合（修正版）
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# .mcp.json作成（ローカルパス指定）
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yuta/workspace/claude-flow-lite/src/claude-flow/build/index.js"
      ],
      "env": {},
      "disabled": false
    }
  }
}
EOF

# ビルド確認
ls -lh /Users/yuta/workspace/claude-flow-lite/src/claude-flow/build/index.js

# Claude Code再起動
```

**メリット**:

- npm公開不要（プライバシー保護）
- 公開手続きスキップ（15分短縮）

**デメリット**:

- 別マシンで使用する場合、手動コピー必要
- バージョン管理が手動

---

### C. 段階的実装（2セッション分割版）

**使用ケース**: 4時間連続確保困難、疲労軽減

**Day 1（2時間）: Phase 1-2**

```markdown
## Day 1 実装内容（2時間）

### Phase 1: 準備（30分）
- npm scopeアカウント作成
- リポジトリフォーク
- 依存関係インストール

### Phase 2: フィルタリング実装（1時間30分）
- ツールリスト定義
- サーバーロジック修正
- ビルド・動作確認

### Day 1終了時チェックリスト
- [ ] ビルドエラーなし
- [ ] ツール数が正確に34個
- [ ] Inspector UIで34ツール表示確認

### Day 2への引き継ぎ事項
- ビルド成功（build/ディレクトリ確認）
- npmアカウント名記録
- 次回作業: Phase 3-4（2時間）
```

**Day 2（2時間）: Phase 3-4**

```markdown
## Day 2 実装内容（2時間）

### Phase 3: パッケージ公開（1時間）
- package.json更新
- npm公開
- READMEドキュメント作成

### Phase 4: プロジェクト統合（1時間）
- .mcp.json作成
- Claude Code再起動・動作確認
- ドキュメント更新

### Day 2終了時チェックリスト
- [ ] npm公開成功
- [ ] .mcp.json作成完了
- [ ] Claude Code動作確認
- [ ] トークン削減効果確認（62.2%）
```

---

### D. Claude Flow本家アップデート対応

**頻度**: 3-6ヶ月毎（推奨）

**アップデート手順**:

```bash
# 1. 本家最新版確認
cd ~/workspace/claude-flow-lite
git remote add upstream https://github.com/modelcontextprotocol/servers.git
git fetch upstream

# 2. 変更履歴確認
git log upstream/main --oneline --since="3 months ago" src/claude-flow/

# 3. マージ実施
git checkout lite/v2.7.0
git merge upstream/main

# 競合解決（手動）
# lib/server.ts: フィルタリングロジック保持
# lib/allowed-tools.ts: 変更なし

# 4. フィルタリングロジック再確認
cat lib/server.ts | grep -A 10 "filteredTools"

# 5. ビルド・テスト
npm run build
npx @modelcontextprotocol/inspector npx ts-node lib/index.ts

# 6. 新バージョン公開
npm version 2.8.0-lite.1
npm publish --access public --tag lite

# 7. プロジェクト設定更新
cd /Users/yuta/Yuta/python/api-test-devops-portfolio
# .mcp.json修正: 2.7.0-lite.X → 2.8.0-lite.1
```

---

### E. よくある質問（FAQ）

#### Q1: TypeScriptの知識が浅いが実装可能か？

**A**: **可能**。以下の理由から、TypeScript初学者でも実装可能：

1. **修正範囲が限定的**: 既存コード50行のみ修正、新規実装不要
2. **既存パターン踏襲**: `allTools.filter()`という標準的な配列操作のみ
3. **型定義不要**: フィルタリングロジックは既存の型を使用
4. **ビルドコマンド確立**: `npm run build`で自動コンパイル

**必要な最低限のTypeScript知識**:

- 配列の`filter()`メソッド理解
- `import`/`export`構文理解
- アロー関数`=>`の基本理解

**推奨学習リソース**:

- [TypeScript Playground](https://www.typescriptlang.org/play)で`filter()`を5分試す
- Claude Flowの既存`lib/server.ts`を読み、パターンを理解

---

#### Q2: 実装中にエラーが発生した場合のロールバック方法は？

**A**: **即座復旧可能**。以下のロールバック手順を推奨：

**レベル1: .mcp.json削除（10秒）**

```bash
# プロジェクトルート
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# .mcp.json削除
rm .mcp.json

# Claude Code再起動
# → グローバル設定（~/.claude.json）のclaude-flow（90ツール）に

```

**レベル2: git checkout（30秒）**

```bash
# gitコミット済みの場合
git checkout .mcp.json

# 変更破棄
git reset --hard HEAD
```

**レベル3: プロジェクトバックアップ（事前準備）**

```bash
# 実装開始前にブランチ作成推奨
git checkout -b feature/claude-flow-lite-implementation

# 実装失敗時
git checkout main
git branch -D feature/claude-flow-lite-implementation
```

---

#### Q3: 実装完了後、Week 8-10で追加ツールを使いたい場合は？

**A**: **簡単に拡張可能**。付録Aの手順に従って実施：

1. `lib/allowed-tools.ts`のSYSTEM配列に追加
2. `npm version 2.7.0-lite.2`でバージョンアップ
3. `npm publish`で再公開
4. `.mcp.json`のバージョン番号更新
5. Claude Code再起動

**所要時間**: 30分（新規ツール3個追加の場合）

---

#### Q4: Claude Flow本家の破壊的変更があった場合の対処法は？

**A**: **段階的移行**を推奨：

1. **破壊的変更の影響範囲評価**（1時間）
   - リリースノート確認
   - API変更点の特定
   - フィルタリングロジックへの影響評価

2. **テスト環境で検証**（2時間）
   - 別ブランチでマージ実施
   - ビルド・Inspector確認
   - 34ツール維持確認

3. **本番反映**（1時間）
   - mainブランチマージ
   - バージョンアップ（例: 3.0.0-lite.1）
   - npm公開・プロジェクト設定更新

**最悪の場合**: 破壊的変更が大きく、フィルタリングロジック全体の書き直しが必要な場合

- 実装時間: 6-8時間（新規実装扱い）
- 代替案: 旧バージョン（2.7.0-lite.X）を継続使用

---

<!-- ==========================================
     FALLBACK IMPROVEMENT
     追加日: 2025-11-10
     対象: フォールバック関連FAQ追加
     修正ファイル: Claude-Flow_MCPLoading削減の実装計画.md
     ========================================== -->

#### Q5: ネットワーク接続がない環境で使用できるか？

**A**: **完全に可能**。ローカルソースのフォールバック設定により、オフライン環境でも使用可能：

**初回セットアップ（ネットワーク必要）**:

```bash
# リポジトリクローン（事前準備）
cd ~/workspace
git clone https://github.com/yuta-scope/ruv-claude-flow.git
cd ruv-claude-flow
npm install
```

**オフライン使用時の設定**:

```json
{
  "mcpServers": {
    "claude-flow-lite-local": {
      "type": "stdio",
      "command": "node",
      "args": [
        "/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js"
      ],
      "env": {},
      "disabled": false
    }
  }
}
```

**メリット**:

- ネットワーク不要で常時使用可能
- npmレジストリ障害時の影響回避
- 企業VPN/プロキシ環境での安定動作

**デメリット**:

- 初回セットアップ時のみネットワーク必要
- バージョンアップは手動（git pull）

---

#### Q6: npm package とローカルソース、どちらを使うべきか？

**A**: **環境・目的に応じて選択**を推奨：

**npm package推奨シナリオ**:

- ✅ 安定したネットワーク環境
- ✅ 本番プロジェクト（バージョン管理明確）
- ✅ チーム共有プロジェクト（設定統一）
- ✅ 定期的なアップデート希望

**ローカルソース推奨シナリオ**:

- ✅ オフライン環境
- ✅ 企業VPN/プロキシ制限環境
- ✅ 開発・カスタマイズ環境
- ✅ npmレジストリ接続不安定な環境

**両方維持する方法**:

```bash
# Primary設定（npm）: .mcp.json
cat > .mcp.json << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite": {
      "type": "stdio",
      "command": "npx",
      "args": ["@your-username/claude-flow-lite@2.7.0-lite.7", "mcp", "start"],
      "env": {},
      "disabled": false
    }
  }
}
EOF

# Fallback設定（ローカル）: .mcp.json.local
cat > .mcp.json.local << 'EOF'
{
  "mcpServers": {
    "claude-flow-lite-local": {
      "type": "stdio",
      "command": "node",
      "args": ["/Users/yuta/workspace/ruv-claude-flow/src/mcp/mcp-server.js"],
      "env": {},
      "disabled": false
    }
  }
}
EOF

# 緊急時切替（10秒）
cp .mcp.json.local .mcp.json
# Claude Code再起動
```

**切替コスト**: 10秒（ファイルコピー + Claude Code再起動）

---

#### Q7: ローカルソース使用時のバージョンアップ方法は？

**A**: **git pullで簡単に更新可能**：

**定期更新手順**（3ヶ月毎推奨）:

```bash
# 1. ローカルリポジトリ更新
cd /Users/yuta/workspace/ruv-claude-flow
git fetch origin
git log HEAD..origin/main --oneline  # 変更履歴確認

# 2. 更新実施
git pull origin main

# 3. 依存関係更新
npm install

# 4. 動作確認
node src/mcp/mcp-server.js
# 期待される出力:
# [claude-flow-lite] Initializing Claude Flow Lite
# [claude-flow-lite] Loading 34 tools (90 → 34, 62.2% reduction)

# 5. Claude Code再起動
# .mcp.json は変更不要（パスは同じ）
```

**緊急パッチ適用**（バグ修正時）:

```bash
# 特定コミットを指定してチェックアウト
git checkout <commit-hash>

# または特定ブランチに切替
git checkout stable/v2.7
```

**所要時間**: 5分（git pull + npm install + 動作確認）

**メリット**:

- npmレジストリ経由不要（直接ソース更新）
- バージョン管理が明確（git commit hash）
- ロールバックが容易（git checkout）

<!-- ========================================== -->

---

### F. 実装チェックリスト（印刷用）

```markdown
# Claude Flow Lite 実装チェックリスト

## 実装前準備
- [ ] Node.js v18+ インストール確認
- [ ] npm v9+ インストール確認
- [ ] npm login 実行済み
- [ ] npm scopeアカウント名決定
- [ ] 実装時間確保（4時間連続 or 2時間×2）
- [ ] gitブランチ作成（推奨）
- [ ] ベースライン測定完了（任意）

---

## Phase 1: 準備（30分）
- [ ] リポジトリクローン完了
- [ ] ブランチ作成（lite/v2.7.0）
- [ ] npm install 成功
- [ ] npm run build 成功
- [ ] lib/server.ts 構造確認

---

## Phase 2: フィルタリング実装（2時間）
- [ ] lib/allowed-tools.ts 作成完了
- [ ] 34ツールリスト定義完了
- [ ] lib/server.ts import文追加
- [ ] フィルタリングロジック追加
- [ ] return文変更（allTools → filteredTools）
- [ ] npm run build 成功
- [ ] Inspector UI確認（34ツール表示）
- [ ] デバッグログ確認（✅ Tool filtering successful!）

---

## Phase 3: パッケージ公開（1時間）
- [ ] package.json name更新（@your-username/claude-flow-lite）
- [ ] package.json version更新（2.7.0-lite.1）
- [ ] npm publish --dry-run 確認
- [ ] npm publish 成功
- [ ] npm view確認（公開済み）
- [ ] README.md 作成完了

---

## Phase 4: プロジェクト統合（30分）
- [ ] プロジェクトルートに.mcp.json作成
- [ ] .mcp.json args更新（@your-username/claude-flow-lite@2.7.0-lite.1）
- [ ] git add .mcp.json
- [ ] Claude Code再起動
- [ ] MCP Server起動確認（claude-flow-lite, 34ツール）
- [ ] トークン消費確認（~19,380トークン）
- [ ] docs/claude_flow/required_tools.md 更新
- [ ] git commit完了

---

## 検証・測定
- [ ] ツール削減率確認（62.2% = 90→29）
- [ ] トークン削減量確認（31,920トークン/セッション）
- [ ] 実装時間記録（___時間）
- [ ] エラー発生なし
- [ ] スクリーンショット保存（任意）
- [ ] ROI計算完了

---

## 完了確認
- [ ] Week 7開始日までに完了（2025-10-01）
- [ ] 既存プロジェクト影響なし確認
- [ ] Week 8-10拡張手順理解
- [ ] ドキュメント整備完了
- [ ] 実装完了報告（任意）

---

**実装完了日**: ___________
**実装者**: ___________
**所要時間**: ___________時間
**トークン削減実績**: ___________トークン/セッション
```

---

## 次のステップ

実装計画書を理解し、以下のいずれかを選択してください：

### ✅ Option A: 実装即座開始（推奨）

**条件**:

- すべての確認事項が「問題なし」
- 連続4時間確保可能
- npm scopeアカウント作成済み

**次のアクション**:

```bash
# Phase 1: 準備開始
mkdir -p ~/workspace
cd ~/workspace
git clone https://github.com/modelcontextprotocol/servers.git claude-flow-lite
cd claude-flow-lite/src/claude-flow
git checkout -b lite/v2.7.0
npm install
npm run build
```

---

### ❓ Option B: 追加質問・調査

**条件**:

- 不明点が残っている
- Claude Flow構造の事前確認が必要
- npm scopeアカウント未作成

**次のアクション**:

- 実装前確認事項8項目に回答
- Claude Flow構造調査（30分）
- npm scopeアカウント作成（10分）

---

### 📝 Option C: 実装計画の再検討

**条件**:

- npm公開せずローカルのみ使用したい
- 実装時間を2セッションに分割したい
- Week 8-10追加ツール要件を明確化したい

**次のアクション**:

- 付録B（ローカル版）の確認
- 付録C（2セッション分割版）の確認
- Week 8-10ツール要件の事前確認

---

**実装開始の最終確認**:

> 「上記の実装計画書を理解し、Phase 1を開始してよいですか？」
>
> - ✅ 理解した → Phase 1開始
> - ❓ 不明点がある → 質問
> - 📝 計画変更したい → 代替案検討

---

**ドキュメント作成日**: 2025年11月08日
**最終更新日**: 2025年11月08日
**バージョン**: v1.0
**ステータス**: ✅ 実装準備完了
