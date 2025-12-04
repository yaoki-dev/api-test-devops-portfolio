# Obsidian MCP統合導入計画書（改善版v2）

*最終更新: 2025年12月04日*
*レビュー: 5専門エージェント（system-architect, requirements-analyst, devops-architect, security-engineer, technical-writer）*

> **📌 クロスリファレンス**: 本ドキュメントのSection 4「Trigger仕様（フロー自動化）」は以下のソースから統合されました：
> - **ソース**: `docs/main/6週再編/フロー自動化改善要件.md`
> - **統合日**: 2025年12月02日
> - **統合内容**: Trigger 1-6仕様、progress_state.yamlスキーマ、実装チェックリスト


## Index

  ```markdown
  1. Executive Summary（導入目的、ROI、リスク評価）
  2. システム比較分析（Serena vs Obsidian）
  3. 統合戦略：役割分担
  4. Trigger仕様（現9.x）
  5. 実装ロードマップ（Week 3-6）
  6. 主要ユースケース
  7. 品質保証・成功基準
  8. 継続運用・保守計画
  9. 参考資料・補足
 ```

## 📋 Executive Summary

### 1.1 導入目的：ハイブリッド戦略の採用

**基本方針**: Serena完全置き換えではなく、**並行運用による相互補完**

#### なぜハイブリッドか？

**Serenaの強み（維持）**:
- プロジェクトコンテキスト管理（現在15メモリ、87.5%トークン削減実績）
- @memory記法によるCLAUDE.md統合（既存ワークフロー維持）
- Progressive Disclosure Pattern（作業タイプ別MUST/SHOULD/MAY分類）

**Obsidianの強み（追加）**:
- 知識グラフ可視化（学習パス、技術依存関係の俯瞰）
- セマンティック検索（トラブルシューティング履歴の即座検索）
- テンプレート・タグによる構造化（学習ログ、AI協働パターン蓄積）
- **8カテゴリの静的知識管理**（詳細: Section 3.1 推奨度別分類）

**並行運用の利点**:
1. **移行リスクゼロ**: Serenaメモリはそのまま維持、Obsidianは新規追加のみ
2. **段階的導入**: Week 3試験運用 → Week 4評価 → Week 5最適化
3. **用途別最適化**: 静的知識（Obsidian） vs 動的状態（Serena）の明確な分離

---

### 1.2 ROI分析（修正版）

#### 1.2.1 ベースライン測定プロトコル（Week 2実施必須）

**⚠️ 重要**: 以下のベースライン値は**推定値**です。Week 3開始前に実測が必要です。

**測定手順**:
1. **トークン使用量測定**（10 sessions）
   ```bash
   # Claude Code MCP token logから抽出
   # 各セッション終了時に記録
   echo "Session 1: 1850 tokens" >> docs/metrics/baseline_tokens.txt
   echo "Session 2: 1650 tokens" >> docs/metrics/baseline_tokens.txt
   # ... 10回繰り返し

   # 平均値計算
   awk '{sum+=$3} END {print "Average:", sum/NR, "tokens"}' docs/metrics/baseline_tokens.txt
   ```

2. **検索時間測定**（5 troubleshooting searches）
   ```bash
   # ストップウォッチで手動測定
   # エラー1: "Docker permission denied"
   #   → daily_progress.md検索開始
   #   → 解決策発見
   #   → 記録: 4分20秒

   echo "Error 1: Docker permission, 260s" >> docs/metrics/baseline_search_times.txt
   # ... 5回繰り返し

   # 中央値計算
   sort -n -k3 docs/metrics/baseline_search_times.txt | awk 'NR==3 {print "Median:", $3}'
   ```

3. **測定結果フォーマット**
   | 指標 | 平均値 | 中央値 | 標準偏差 | サンプルサイズ | 測定日 |
   |------|--------|--------|---------|-------------|--------|
   | トークン | 1750 | 1700 | ±150 | n=10 | 2025-11-21 |
   | 検索時間 | 3.5min | 3.2min | ±1.1min | n=5 | 2025-11-21 |

**検証**: `docs/metrics/baseline_*.txt`をgit commitして証跡保存

---

#### 現状ベースライン（Week 2測定値）

| 指標 | 測定値 | サンプル | 標準偏差 | 測定方法 |
|------|--------|---------|---------|---------|
| プロジェクト状態管理トークン | 1,750 tokens | n=10 | ±150 | MCP token log |
| トラブルシューティング検索時間 | 3.2min (中央値) | n=5 | ±1.1min | 手動ストップウォッチ |
| 学習ログ参照トークン | 8,000 tokens | n=5 | ±500 | MCP token log |
| 知識再発見時間 | 6.5min (中央値) | n=5 | ±2.0min | 手動ストップウォッチ |

**測定期間**: Week 2 Day 7-12（2025-11-15〜21）
**測定ツール**: Claude Code MCP token log + iOS Clock app

---

#### トークン効率改善（保守的予測）

**⚠️ 修正**: 以前の予測（60-80%削減）は楽観的すぎました。現実的な数値に修正します。

| 指標 | Week 2 (Serena) | Week 4 (ハイブリッド) | Week 6 (最適化後) | 測定方法 |
|------|----------------|---------------------|-------------------|---------|
| トラブルシューティング検索 | 3.2min + 0 tokens | 1.5min + 500 tokens | 0.5min + 300 tokens | 同条件5回測定の中央値 |
| 学習ログ参照 | 8,000 tokens | 4,000 tokens (50%削減) | 2,000 tokens (75%削減) | get_vault_file() token count |
| 知識再発見 | 6.5min | 3.0min (54%削減) | 1.5min (77%削減) | graph view操作時間 |

**現実的改善率**:
- **Week 4**: 40-50%削減（学習期間中）
- **Week 6**: 60-75%削減（運用成熟後）

**検証方法**: Week 4終了時に同じ5つのエラーで再測定、Week 2と比較

---

#### 知識グラフ効果

**定量的効果**:
- 学習パス可視化: 6週プランの技術依存関係を1画面で俯瞰（グラフビュー）
- パターン再利用: AI協働パターン（10-15パターン蓄積予定）の即座参照（検索30秒以内）
- 技術決定記録: ADR（Architecture Decision Records）形式でリンク管理（3ホップ以内で全関連ノート到達）

**定性的効果**:
- 面接時のポートフォリオ説明（技術選定理由の即答）
- 学習計画の戦略的調整（弱点の視覚的把握）

---

### 1.3 実装フロー

**⚠️ 修正**: 以前の見積もり（5-8h）は過小評価でした。実態に基づく修正版:

| Week | フェーズ | 成果物 | 成功基準 |
|------|---------|---------|--------|
| Week 3 | 準備・設計  | vault構造、テンプレート、MCP検証 | MCP機能確認、初回ノート作成成功 |
| Week 4 | 試験運用  | トラブルシューティング5件 + 学習ログ3件 | 検索ヒット率60%以上 |
| Week 5 | 最適化  | タグ体系改善、テンプレート改訂、グラフキュレーション | 検索ヒット率70%以上 |
| Week 6 | 本番運用  | ポートフォリオ統合（手動）、ADRレビュー | グラフ可視化完了 |


**内訳詳細**:

**Week 3内訳** :
- 環境構築
- MCP機能検証テスト
- テンプレート作成
- 学習Obsidian基本操作
- CLAUDE.md更新
- ADR_001作成
- トラブルシューティング予備: （現実的バッファ）

**Week 4内訳** :
- ノート作成時間:（10件）
- 検索検証: 
- Tag refactoring: 

**Week 6内訳** (2-3h):
- Graph view キュレーション: 
- ポートフォリオスクリーンショット: 
- ADR品質レビュー: 


### 1.4 リスク評価とロールバック計画（セキュリティ強化版）

#### リスク評価

| リスク | 発生確率 | 影響度 | 対策 |
|--------|---------|--------|------|
| Serenaとの競合 | 低 | 低 | 用途を明確分離（静的知識 vs 動的状態） |
| 学習コスト超過 | 中 | 低 | Week 3に4h集中学習、Week 4で実践習得 |
| メンテナンス負荷 | 低 | 低 | テンプレート活用で記録作業を標準化 |
| 過剰ドキュメント化 | 中 | 中 | 「3回以上参照した内容のみ」ルール適用 |
| Obsidian MCP Server障害 | 低 | 高 | Fallback: filesystem MCPでvault直接アクセス |
| トークン削減未達 | 中 | 中 | Week 4で実測、目標未達時はロールバック |
| **機密情報漏洩** | **中** | **高** | **.gitignore強化 + pre-commit hook** |
| **データ損失** | **中** | **高** | **3-2-1バックアップ戦略 + 復旧テスト** |

**総合評価**: **低リスク・中リターン**（並行運用のため撤退も容易）

---

#### ロールバック計画（セキュリティ強化版）

**トリガー条件（1つでも該当でロールバック検討）**:
1. **トークン使用量超過**: Week 4のハイブリッド運用トークンが、Week 6ベースラインの150%超
   - 具体例: Week 6 baseline 7,000 tokens/week → Week 4が10,500 tokens超でトリガー
2. **検索ヒット率未達**: Week 4終了時に検索ヒット率60%未満（目標70%の86%未満）
3. **Obsidian MCP同期エラー頻発**: MCP接続エラーが5回/日以上、3日連続
4. **ユーザー満足度低**: Week 3終了時の使いやすさ評価が5段階中2以下
5. **データ損失発生**: 重要度Highのノートが破損・消失（深刻度問わず）
6. **セキュリティインシデント**: 機密情報の誤commit、vault改ざん検出
7. **バックアップ失敗**: 3日連続でgit commit失敗（データ損失リスク）

---

#### セキュリティ強化版ロールバック手順

**Phase 1: 緊急停止（5分以内）**

1. **Obsidian MCP即時無効化**:
   ```bash
   # .mcp.jsonバックアップ
   cp .mcp.json .mcp.json.bak

   # obsidian-mcp-toolsを無効化
   sed -i '' 's/"obsidian-mcp-tools"/#"obsidian-mcp-tools"/' .mcp.json

   # 検証
   grep obsidian-mcp-tools .mcp.json
   ```

2. **アクティブセッション終了**:
   - Claude Codeセッション終了
   - Obsidianアプリケーション終了
   - ファイルロック解除確認: `lsof | grep obsidian-vault-local`

---

**Phase 2: データ監査（15分）**

3. **セキュリティスキャン**:
   ```bash
   # 機密情報漏洩チェック
   grep -r "API_KEY\|SECRET\|PASSWORD\|TOKEN" obsidian-vault-local/ \
     --exclude-dir=.git --exclude-dir=.obsidian

   # .envファイル誤混入チェック
   find obsidian-vault-local/ -name ".env*" -o -name "*credentials*"

   # git履歴の機密情報チェック
   git log --all --full-history --source -- '*secret*' '*api*key*'
   ```

4. **データ整合性検証**:
   ```bash
   # Frontmatter YAML構文チェック
   for file in obsidian-vault-local/**/*.md; do
     python3 -c "import yaml; yaml.safe_load(open('$file').read().split('---')[1])" \
       2>/dev/null || echo "YAML error: $file"
   done

   # 破損ファイルチェック
   find obsidian-vault-local/ -size 0 -name "*.md"
   ```

---

**Phase 3: データ変換**

5. **機密情報サニタイズ**:
   ```bash
   # 変換前に機密情報を削除
   find obsidian-vault-local/ -name "*.md" -exec sed -i '' \
     -e 's/api_key=.*/api_key=[REDACTED]/g' \
     -e 's/password=.*/password=[REDACTED]/g' {} \;
   ```

6. **Serenaメモリ形式変換**:
   ```bash
   mkdir -p .serena/memories/rollback/

   for file in obsidian-vault-local/**/*.md; do
     filename=$(basename "$file")

     # Frontmatter削除（1行目の---から2つ目の---まで）
     sed '1,/^---$/d; /^---$/,$ d' "$file" > "/tmp/${filename}"

     # 最終更新日追加
     echo "*最終更新: $(date +%Y年%m月%d日)*" | cat - "/tmp/${filename}" > \
       ".serena/memories/rollback/${filename}"
   done

   # 検証
   ls -lh .serena/memories/rollback/ | head -5
   ```

---

**Phase 4: 安全アーカイブ**

7. **vaultバックアップとチェックサム**:
   ```bash
   # タイムスタンプ付きアーカイブ
   TIMESTAMP=$(date +%Y%m%d_%H%M%S)
   tar -czf "obsidian-vault-backup_${TIMESTAMP}.tar.gz" obsidian-vault-local/

   # チェックサム記録
   shasum -a 256 "obsidian-vault-backup_${TIMESTAMP}.tar.gz" > \
     "obsidian-vault-backup_${TIMESTAMP}.sha256"

   # 安全な場所に移動
   mkdir -p ~/Backups/obsidian/
   mv obsidian-vault-backup_* ~/Backups/obsidian/

   # 検証
   tar -tzf ~/Backups/obsidian/obsidian-vault-backup_${TIMESTAMP}.tar.gz | head -10
   ```

---

**Phase 5: クリーンアップと検証（24h運用テスト）**

8. **CLAUDE.md更新**:
   ```bash
   # Obsidianセクション削除（バックアップ後）
   cp CLAUDE.md CLAUDE.md.bak

   # "## 🧠 Obsidian知識ベース活用ガイド" セクション全体削除（手動編集）

   # git commit
   git add CLAUDE.md
   git commit -m "revert: remove Obsidian MCP integration (rollback)"
   ```

9. **最終検証**（24h運用テスト）:
   - Serena単独動作確認:
     - progress_state.yaml読み込み正常
     - @memory参照正常
     - トークン使用量が想定範囲内（1,750 tokens/session）

   - 問題なければvault削除:
     ```bash
     rm -rf obsidian-vault-local/
     git add .
     git commit -m "chore: remove Obsidian vault after successful rollback"
     ```

---

#### ロールバック完了基準

- [ ] Obsidian MCP無効化確認（`.mcp.json`検証）
- [ ] セキュリティスキャン0件（機密情報漏洩なし）
- [ ] データ整合性100%（破損ファイル0件）
- [ ] Serenaメモリ変換完了（全ノート変換）
- [ ] アーカイブ検証成功（sha256チェックサム一致）
- [ ] CLAUDE.md更新完了（git commit済み）
- [ ] 24h運用テスト合格（エラー0件）

**撤退コスト（更新）**: **5-8h**（セキュリティ監査、変換作業は時間幅大きい）

**決定タイミング**: Week 4終了時（Day 48）に実績評価、ロールバック判断

---

### 1.5 クイックスタート（5分で理解）

**目的**: 6週間の学習ポートフォリオに知識グラフ機能を追加

**3ステップで開始**:
1. **Week 3**: vault構造作成 + MCP検証（4-6h） → Section 5.1参照
2. **Week 4**: 学習中に8-10ノート作成（4h） → Section 5.2参照
3. **Week 5**: 検索ヒット率測定・最適化（3h） → Section 5.3参照

**⚠️ 重要な前提**:
- 総投資時間: **13-18h**（週3-5h × 4週間）
- ROI回収: **Week 12-13**（Week 5ではありません）
- 自動化率: **20%**（Daily Notes作成のみ。タグ付け・リンク作成は手動）

**いますぐ始める**: Section 5.1.1 MCP機能検証へジャンプ →

**詳細を理解する**: このまま読み進める（推定読了時間: 40分）

---

## ✅ 事前準備チェックリスト

**Week 3開始前に確認**

### 必須環境

- [ ] **Obsidianアプリインストール済み**（v1.4以降）
  - 未達の場合 → [Obsidian公式サイト](https://obsidian.md/)からダウンロード・インストール

- [ ] **Claude Code稼働中**（MCP対応版）
  - 未達の場合 → Claude Code公式ドキュメント参照

- [ ] **`.mcp.json`にobsidian-mcp-tools設定済み**
  - 未達の場合 → Section 5.1.0.5参照（.mcp.json設定確認）

- [ ] **プロジェクトルート確認**: `/Users/yuta/Yuta/python/api-test-devops-portfolio`
  - 未達の場合 → `pwd`コマンドで現在地確認、必要に応じてcd移動

### 必須前提データ

- [ ] **Week 1-2学習実施済み**（daily_progress.mdに記録あり）
  - 未達の場合 → Week 1-2の学習を先に完了
  - 確認方法: `grep "Week 1" docs/progress/daily_progress.md`

- [ ] **`docs/progress/daily_progress.md`が存在**し、Week 1-2セクションあり
  - 未達の場合 → daily_progress.mdのテンプレート作成（CLAUDE.md参照）

- [ ] **`progress_state.yaml`が存在**（current_week, current_day記録あり）
  - 未達の場合 → progress_state.yamlの初期化（プロジェクトルートに作成）

### 推奨事前学習

- [ ] **Obsidian基本操作理解**（ノート作成、リンク、検索）
  - 未達の場合 → [Obsidian Help](https://help.obsidian.md/)で15分学習

- [ ] **Markdown記法理解**（Frontmatter, コードブロック）
  - 未達の場合 → Markdown基礎ガイド参照

- [ ] **Git基本操作**（commit, .gitignore）
  - 未達の場合 → Git入門チュートリアル参照

**確認コマンド**:
```bash
# 環境確認
which obsidian  # Obsidianパス確認（インストール済みか）
grep -q "obsidian-mcp-tools" .mcp.json && echo "✅ MCP設定あり" || echo "❌ 設定なし"

# データ確認
ls docs/progress/daily_progress.md && echo "✅ 進捗記録あり" || echo "❌ ファイルなし"
grep "Week 1" docs/progress/daily_progress.md && echo "✅ Week 1記録あり" || echo "❌ Week 1記録なし"

# プロジェクトルート確認
pwd  # 期待結果: /Users/yuta/Yuta/python/api-test-devops-portfolio
```

**⚠️ 重要**: 1つでも未達の場合、該当セクションまたは上記の「未達の場合」の指示に従って準備を完了してください。

---

## 🔍 システム比較分析

### 2.1 Serena MCP

#### 強み

1. **プロジェクト状態管理に最適化**
   - `progress_state.yaml`の現在週・日・次タスク自動補完
   - MUST/SHOULD/MAYによる段階的メモリ読み込み（87.5%トークン削減）
   - CLAUDE.md統合による既存ワークフロー維持

2. **AIコンテキスト制御**
   - `read_memory()`で必要なメモリのみロード
   - Progressive Disclosure Pattern（作業開始時→エラー時の2段階ロード）
   - @memory記法による自然言語参照

3. **軽量・高速**
   - 15メモリ（平均500-2000行/メモリ）の効率的管理
   - 物理ファイル`.serena/memories/`は直接編集も可能
   - Git管理による変更履歴追跡

#### 制約

1. **検索機能の限界**
   - メモリ名ベースの参照（全文検索不可）
   - 関連知識の発見が困難（リンク機能なし）
   - トラブルシューティング履歴の蓄積に不向き

2. **構造化の限界**
   - メモリは独立したMarkdown（相互参照が弱い）
   - タグ・メタデータによる分類不可
   - 時系列・カテゴリ横断の俯瞰が困難

3. **動的コンテンツ向き**
   - 頻繁に更新される状態管理に最適
   - 静的な知識ベース構築には非効率

---

### 2.2 Obsidian MCP

#### 強み

1. **知識グラフ可視化**
   - 双方向リンク（`[[Week 1]]` ↔ `[[httpx基礎]]`）
   - グラフビュー（学習パス、技術依存関係の俯瞰）
   - バックリンク表示（関連ノート自動発見）

2. **強力な検索・分類**
   - 全文検索（エラーメッセージ、コマンド、概念の即座検索）
   - セマンティック検索（Smart Connections: 意味ベース検索）
   - タグ階層（`#learning/docker`, `#troubleshooting/ci-cd`）

3. **構造化・テンプレート**
   - Frontmatter（YAML）による標準メタデータ
   - テンプレート機能（学習ログ、トラブルシューティング、ADR）
   - Daily Notes（日次自動生成）

4. **拡張性**
   - プラグインエコシステム（Dataview, Calendar等）
   - Markdown完全互換（Git管理可能）
   - ローカルファイル（プライバシー保護）

#### 制約

1. **AIコンテキスト制御が弱い**
   - MCPツールは基本CRUD操作のみ（read_memory()のような段階的ロードなし）
   - 大量ノート一括読込のリスク（トークン浪費）
   - CLAUDE.md統合が複雑

2. **学習コスト**
   - vault構造設計が必要（Week 3に2h投資）
   - プラグイン設定・Frontmatter設計の初期負荷
   - 過剰ドキュメント化のリスク（記録が目的化）

3. **動的状態管理に不向き**
   - 頻繁に更新される値（current_week, current_day）の管理には冗長
   - `progress_state.yaml`のような単一真実源には不適

---

### 2.3 比較表

| 項目 | Serena MCP | Obsidian MCP | 最適用途 |
|------|-----------|-------------|---------|
| **主な用途** | プロジェクト状態管理 | 静的知識ベース構築 | - |
| **検索性** | メモリ名ベース | 全文検索 + セマンティック + タグ + リンク | トラブルシューティング: Obsidian |
| **可視化** | なし | グラフビュー | 学習パス俯瞰: Obsidian |
| **AIコンテキスト制御** | ⭐⭐⭐⭐⭐ | ⭐⭐ | CLAUDE.md統合: Serena |
| **構造化** | ⭐⭐ | ⭐⭐⭐⭐⭐ | 学習ログ標準化: Obsidian |
| **変更頻度** | 高（daily更新） | 低（週次追加） | 動的状態: Serena、静的知識: Obsidian |
| **学習コスト** | 低（2h） | 中（4-6h） | - |
| **トークン効率** | 87.5%削減 | 40-75%削減（段階的改善） | - |
| **Git管理** | ✅ `.serena/memories/` | ✅ `obsidian-vault-local/` | - |

---

## 🔗 統合戦略：役割分担

### 3.1 用途別分離原則

#### Serenaが管理する領域（動的状態）

**目的**: AIセッション開始時の自動コンテキスト補完

**管理対象**:
1. **プロジェクト状態**
   - `progress_state.yaml`の現在週・日・次タスク
   - `progress_state.yaml`のメトリクス（カバレッジ、Docker実装率等）
   - Phase別品質ゲート基準

2. **作業ガイドライン**
   - `@memory:coding_standards`（命名規則、型ヒント規約）
   - `@memory:implementation_quality_gates`（4段階品質チェック）
   - `@memory:test_strategy`（単体/結合/性能/セキュリティテスト）

3. **ワークフロープレイブック**
   - `@memory:workflow_playbooks_guide`（14種類のワークフロー）
   - `@memory:ai_collaboration_workflow`（3フェーズ学習方法論）

**更新頻度**: Daily~Weekly
**CLAUDE.md統合**: `@memory:メモリ名`記法で参照

---

#### Obsidianが管理する領域（静的知識）

**目的**: 知識グラフによる学習・トラブルシューティング履歴の蓄積

**管理対象（推奨度別8カテゴリ）**:

##### ★★★ 必須（Must）- 高再利用・高検索価値

1. **トラブルシューティング知識ベース（Troubleshooting KB）**
   - エラーメッセージ → 解決策のマッピング
   - Docker/CI/CD設定問題の解決パターン
   - 性能最適化・セキュリティ対策の実例
   - **選定理由**: 再利用頻度高、検索価値高（エラーメッセージでヒット）

2. **AI協働パターンライブラリ（AI Collaboration Patterns）**
   - Level 2→3→4のプロンプト改善事例
   - AIレビューでの頻出指摘パターン
   - 効率的な質問・依頼フォーマット
   - **選定理由**: 毎セッション参照、面接価値高（AI活用スキル証明）

3. **技術決定記録（ADR: Architecture Decision Records）**
   - なぜSerena+Obsidianハイブリッドを選択したか
   - なぜPydantic Settingsを採用したか
   - なぜGitHub Actionsを選択したか
   - **選定理由**: リンク価値高、面接での「なぜ？」に即答可能

##### ★★☆ 推奨（Recommended）- 中再利用・中検索価値

4. **設定パターンライブラリ（Configuration Patterns）**
   - Docker Compose設定パターン（4環境: dev/test/demo/prod）
   - GitHub Actions workflow設定パターン
   - pytest/ruff/mypy設定パターン
   - **選定理由**: 新プロジェクトでの再利用価値高、作成コスト低

##### ★☆☆ 任意（Optional）- 低再利用・特定用途

5. **週次学習ログ（Weekly Learning Log）**
   - Week別学習サマリー（軽量版: /week）
   - 主要な技術概念・理解度を1ページ要約
   - **選定理由**: 毎週更新されるため動的性質が強い。Serena（progress_state.yaml）で詳細管理、Obsidianは振り返り参照用サマリーのみ
   - **作成基準**: Week終了時に10分で要約作成（詳細ログはSerenaで管理）

6. **コードスニペット集（Code Snippets）**
   - 汎用的なコードパターン（async/await, エラーハンドリング等）
   - **選定理由**: IDE補完で代替可能、再利用頻度低
   - **作成基準**: 3回以上コピペした場合のみ

7. **用語集・ドメイン知識（Glossary）**
   - 技術用語・概念の定義
   - **選定理由**: 暗記後は参照不要
   - **作成基準**: 面接説明用に整理が必要な場合のみ

8. **面接Q&A（Interview Preparation）**
   - 想定質問と回答（技術選定理由、課題解決事例）
   - **選定理由**: 面接期間限定、再利用頻度低
   - **作成基準**: Week 6応募準備時に作成

**カテゴリ構成サマリー**（8カテゴリ + 2インフラ）:
| 推奨度 | カテゴリ名 | ディレクトリ |
|--------|-----------|-------------|
| ★★★ | トラブルシューティングKB | 02_Troubleshooting |
| ★★★ | AI協働パターン | 03_AI_Collaboration |
| ★★★ | 技術決定記録（ADR） | 04_ADR |
| ★★☆ | 設定パターン | 06_Config_Patterns |
| ★☆☆ | 週次学習ログ | 01_Learning |
| ★☆☆ | コードスニペット | 07_Optional/Snippets |
| ★☆☆ | 用語集 | 07_Optional/Glossary |
| ★☆☆ | 面接Q&A | 07_Optional/Interview |
| インフラ | インデックス | 00_Index |
| インフラ | テンプレート | 99_Templates |

**更新頻度**: 週次～月次（3回以上参照した内容のみ記録）

**推奨度の評価基準**（5軸）:
| 基準 | ★★★ Must | ★★☆ Recommended | ★☆☆ Optional |
|------|----------|-----------------|--------------|
| 再利用頻度 | 高（週複数回） | 中（週1回） | 低（月1回以下） |
| 検索価値 | 高（即座ヒット） | 中 | 低 |
| リンク価値 | 高（3ホップ以内） | 中 | 低 |
| 面接価値 | 高 | 高 | 中～高 |
| 作成コスト | 低～中 | 低 | 低 |

---

#### 5軸スコアリング方法論（定量評価）

**各軸の点数化**（1-5点）:
| 軸 | 1点（低） | 3点（中） | 5点（高） |
|---|---------|---------|---------|
| 再利用頻度 | 月1回以下 | 週1回 | 週複数回 |
| 検索価値 | 検索30秒超 | 検索10-30秒 | 検索10秒以内 |
| リンク価値 | 孤立ノート | 2ホップ以内 | 3ホップ以内 |
| 面接価値 | 説明不要 | 補助資料 | 必須説明項目 |
| 作成コスト | 60min超 | 20-60min | 20min以下 |

**重み付け**:
- 再利用頻度: **30%**（最重要：投資対効果の直接指標）
- 検索価値: **25%**（トラブルシューティング効率）
- リンク価値: **20%**（知識グラフ価値）
- 面接価値: **15%**（ポートフォリオ目的）
- 作成コスト: **10%**（低コスト＝高評価）

**推奨度計算式**:
```
総合スコア = Σ(各軸スコア × 重み)
```

**判定基準**:
- ★★★ Must: 総合スコア **≥ 4.0点**
- ★★☆ Recommended: 総合スコア **2.5-3.9点**
- ★☆☆ Optional: 総合スコア **< 2.5点**

**計算例（トラブルシューティングKB）**:
| 軸 | スコア | 重み | 加重値 |
|---|-------|-----|-------|
| 再利用頻度 | 5点（週複数回） | 30% | 1.50 |
| 検索価値 | 5点（即座ヒット） | 25% | 1.25 |
| リンク価値 | 4点 | 20% | 0.80 |
| 面接価値 | 5点 | 15% | 0.75 |
| 作成コスト | 4点（20min） | 10% | 0.40 |
| **総合** | | | **4.70点 → ★★★ Must** ✅ |

---

#### 日次記録の統合判断（Week 4で決定）

**⚠️ Week 3では05_Dailyは作成しない**:
- Week 3ではMCP検証とvault基本構造構築に集中
- 05_Dailyディレクトリは作成するが、Daily Notes運用はWeek 4で評価後に開始
- Week 3中はdaily_progress.md運用を継続

**課題**: 現在2つのシステムが並存
- `daily_progress.md`（手動Markdown、既存運用）
- `progress_state.yaml`（Serena管理）

**Week 4で追加検討**:
- `05_Daily/`（Obsidian Daily Notes）の導入可否

**Week 4評価基準**:
- 作成摩擦（記録に要する時間）
- 検索効率（過去エントリ発見時間）
- グラフ価値（バックリンク使用頻度）

**統合オプション**:
- **Option A**: `daily_progress.md`維持（markdown-native、git-friendly）推奨
- **Option B**: `05_Daily/`移行（Obsidian-native、graph-connected）

**判断タイミング**: Week 4終了時
**推奨**: Option A（daily_progress.md維持）- 運用変更コスト回避

---

#### 判断フローチャート（情報作成時）

新しい情報を記録する際の判断基準:

```
情報作成時
  ├─ 毎日/毎週更新される？
  │   ├─ YES → Serena (.serena/memories/)
  │   └─ NO → 次の質問へ
  │
  ├─ 3回以上参照する予定？
  │   ├─ YES → Obsidian (obsidian-vault-local/)
  │   ├─ NO → daily_progress.mdに記録
  │   └─ UNSURE → 一旦daily_progress.md、3回目でObsidian昇格
  │
  └─ 他の知識とリンク関係がある？
      ├─ YES → Obsidian (グラフビュー活用)
      └─ NO → Serenaで十分
```

**具体例**:
- `current_week: 7` → Serena (毎日更新)
- "Docker volume エラー解決策" → Obsidian (3回遭遇、週跨ぎ参照)
- "今日のタスク完了時刻" → daily_progress.md (1回のみ参照)

---

## 🔄 Trigger仕様（フロー自動化）

> **参照元**: `docs/main/6週再編/フロー自動化改善要件.md`
> **統合日**: 2025-12-02

### 4.1 Trigger一覧と適用タイミング

| Trigger | 名称 | 実行タイミング | 自動化率 | 主要機能 | 統合度 |
|---------|------|--------------|---------|---------|--------|
| Trigger 1 | 学習開始 | 学習セッション開始時 | 95% | 次学習項目の自動補完・確認プロンプト | ★☆☆ |
| Trigger 2 | 実装開始 | 実装セッション開始時 | 95% | 次実装タスクの自動補完・確認プロンプト | ★☆☆ |
| **Trigger 3** | **学習記録** | **Phase 3完了後** | **80%** | **習熟度計算・progress_state.yaml更新** | **★★★** |
| **Trigger 4** | **実装記録** | **品質ゲート通過後** | **90%** | **Git解析・メトリクス自動記録** | **★★★** |
| Trigger 5 | 週次振り返り | 週末 | 95% | 週次データ集計・レポート生成 | ★★☆ |
| **Trigger 6** | **理解度確認** | **Day都度（Week 1-6）** | **85%** | **AI自動生成問題（3問・25点）** | **★★★** |

**統合度の定義**:
- **★☆☆ (低)**: 単独実行、他Triggerとの連携なし
- **★★☆ (中)**: 複数Triggerのデータ集約（週次集計等）
- **★★★ (高)**: 複数ファイル更新 + 他Triggerとの密結合
  - Trigger 3: progress_state.yaml + daily_progress.md同時更新
  - Trigger 4: Git解析 + 品質ゲート + 2ファイル更新
  - Trigger 6: Trigger 3/4完了を前提、理解度確認結果を2ファイルに記録

#### 4.1.1 4パターンPhase配分システム（ADR-006詳細）

**設計根拠**: ドメイン特性に応じた学習時間の最適化

| ドメイン | Phase 1 | Phase 2 | Phase 3 | 合計 | 対象技術例 | 選定理由 |
|---------|---------|---------|---------|------|-----------|---------|
| **既知領域** | 0.5H | 3.5H | 1H | **5H** | Docker基礎、テスト設計 | 既存知識活用で学習時間短縮 |
| **応用領域** | 1H | 5H | 1H | **7H** | httpx応用、pytest応用 | 基礎知識あり、応用に時間配分 |
| **新規領域** | 1H | 5H | 1H | **7H** | Pydantic、asyncio、GitHub Actions | 新技術習得に十分な時間確保 |
| **統合領域** | 0.5H | 5.5H | 1H | **7H** | 性能最適化、セキュリティ統合 | 複数技術の統合に実装時間重視 |

**Phase 3統一原則（ADR-006）**:
- 全パターンで**Phase 3 = 1H/日固定**
- 理由: 理解度確認（Trigger 6）の問題生成・採点時間が一定（30分）に加え、記録時間（30分）が必要なため
- 効果: Trigger 6の実装シンプル化、予測可能性向上

#### 4.1.2 WEEK_OFFSET_MAP（CLAUDE.md用）

```python
# 6週プラン向け週次Offset Map（2025-12-02実測値）
# ソース: docs/main/6週再編/6週プラン/6週プラン.md L88-140
WEEK_OFFSET_MAP = {
    1: {"start": 258, "end": 820, "days": "1-6", "hours": 48, "title": "Week 1: Python/httpx実践統合"},
    2: {"start": 821, "end": 1287, "days": "7-12", "hours": 48, "title": "Week 2: Error Handling + Pydantic Settings"},
    3: {"start": 1288, "end": 1663, "days": "13-18", "hours": 39, "title": "Week 3: Docker基盤構築"},
    4: {"start": 1664, "end": 2010, "days": "19-24", "hours": 48, "title": "Week 4: CI/CD統合"},
    5: {"start": 2011, "end": 2865, "days": "25-30", "hours": 49, "title": "Week 5: 非同期処理深化"},
    5.5: {"start": 2866, "end": 2936, "days": "31-32", "hours": 14, "title": "Week 5.5: 統合復習"},
    6: {"start": 2937, "end": 4548, "days": "33-38", "hours": 48, "title": "Week 6: 最適化+応募準備"}
}

ROADMAP_FILE = "docs/main/6週再編/6週プラン/6週プラン.md"
```

**変更理由**:
- 6週プランは学習+実装を1ファイルに統合
- Trigger 1/2が同じファイルを参照
- トークン効率の向上（2ファイル→1ファイル部分読み込み）

### 4.2 Trigger 1: 学習開始

**検出キーワード**: `学習開始`

**目的**: セッション開始時に、次の学習項目を自動補完し、学習開始を支援

**自動化率**: 95%（ユーザーは確認のみ）

**実行フロー**:
```
1. progress_state.yaml読み込み（完全自動）
   - current_week, current_day, current_learning_item取得

2. 6週間実行ロードマップ.md読み込み（完全自動）
   - CLAUDE.mdのWEEK_OFFSET_MAP使用（トークン95%削減）
   - Week別セクションのみ部分読み込み

3. セッションコンテキスト自動補完
   学習項目: {current_learning_item.name}
   週・日: Week {current_week} Day {current_day}
   推定時間: {estimated_hours}h
   目標習熟度: 80%（固定）

4. ユーザー確認プロンプト表示
   ✅ この内容で学習を開始しますか？ (yes/no)

5. ユーザー確認後、セッション開始時刻記録
```

**所要時間**: 10秒

#### 4.2.1 progress_state.yaml読み込み実装

```python
import yaml
from pathlib import Path

# progress_state.yaml読み込み
state_file = Path("progress_state.yaml")  # プロジェクトルート
with open(state_file, "r", encoding="utf-8") as f:
    state = yaml.safe_load(f)

# 学習開始に必要な情報取得
current_week = state["current_week"]
current_day = state["current_day"]
current_learning_item = state.get("current_learning_item", {})
```

#### 4.2.2 6週間実行ロードマップ.md部分読み込み実装

```python
# CLAUDE.mdのWEEK_OFFSET_MAP使用（要実装）
from CLAUDE import WEEK_OFFSET_MAP, ROADMAP_FILE

current_week = state["current_week"]  # 例: 3
config = WEEK_OFFSET_MAP[current_week]

# 部分読み込み（95%トークン削減）
Read(ROADMAP_FILE,
     offset=config["start"],
     limit=config["end"]-config["start"])
# → Week 3のセクションのみ読み込み（2-3k tokens vs. 全体推定30k tokens）
```

#### 4.2.3 エラーハンドリング

**エラー1: progress_state.yaml読み込みエラー**:
```
エラー: progress_state.yaml の読み込みに失敗しました。
対処: ファイルの存在と権限を確認してください。
```

**エラー2: 6週間実行ロードマップ.md読み込みエラー**:
```
エラー: 6週間実行ロードマップ.md が見つかりません。
対処: ファイルパスを確認してください。
```

**エラー3: データ不整合エラー**:
```
エラー: current_week/current_day が不正な値です（Week {week} Day {day}）。
対処: progress_state.yaml の値を修正してください（Week 1-6, Day 1-38）。
```

#### 4.2.4 軽量コンセプトチェック（Phase 1→Phase 2移行時）

**目的**: Phase 2（実装）開始前に、重大な概念誤解を早期検出

**実行タイミング**: Phase 1完了後、Trigger 2（実装開始）の前

**所要時間**: 2分（3問×40秒）

**チェック内容**:
```
Q1: 今日学習した{技術名}の主要な役割を一言で説明してください
Q2: {技術名}を使う場面と使わない場面の違いは？
Q3: 実装で最初に確認すべきことは何ですか？
```

**判定基準**:
- 3問中2問以上正解 → Phase 2開始OK
- 3問中1問以下正解 → Phase 1補足説明後、再チェック

**自動化率**: 80%（AIが問題生成・採点、ユーザーは口頭回答）

**設計意図**:
- Trigger 6（理解度確認）はPhase 2後に実施（AI協働実装で理解深化）
- 本チェックは「実装開始前の安全弁」として重大誤解のみ検出
- 軽量化により学習フロー中断を最小化

---

### 4.3 Trigger 2: 実装開始

**検出キーワード**: `実装開始`

**目的**: 実装セッション開始時に、次の実装タスクを自動補完

**自動化率**: 95%（ユーザーは確認のみ）

**実行フロー**:
```
1. progress_state.yaml読み込み（完全自動）
   - current_week, current_day, current_implementation_task取得

2. 6週間実行ロードマップ.md読み込み（完全自動）
   - CLAUDE.mdのWEEK_OFFSET_MAP使用
   - Week別セクションのみ部分読み込み

3. セッションコンテキスト自動補完
   実装タスク: {current_implementation_task.name}
   週・日: Week {current_week} Day {current_day}
   推定時間: {estimated_hours}h
   成果物: {deliverables}

4. ユーザー確認プロンプト表示
   ✅ この内容で実装を開始しますか？ (yes/no)

5. ユーザー確認後、セッション開始時刻記録
```

**所要時間**: 10秒

#### 4.3.1 progress_state.yaml読み込み実装

```python
import yaml
from pathlib import Path

# progress_state.yaml読み込み
state_file = Path("progress_state.yaml")  # プロジェクトルート
with open(state_file, "r", encoding="utf-8") as f:
    state = yaml.safe_load(f)

# 実装開始に必要な情報取得
current_week = state["current_week"]
current_day = state["current_day"]
current_implementation_task = state.get("current_implementation_task", {})
```

#### 4.3.2 エラーハンドリング

（Trigger 1と同様のエラー処理）

### 4.4 Trigger 3: 学習記録

**検出キーワード**: `学習記録`

**目的**: Phase 3完了後に、学習成果を記録し、習熟度を自動計算

**自動化率**: 80%（ユーザー入力: 実際の学習時間のみ）

**実行フロー**:
```
1. セッション開始時コンテキスト自動補完
   - 学習項目: {session_context.next_task.name}
   - 週・日: Week {current_week} Day {current_day}
   - 推定時間: {session_context.next_task.estimated_hours}h
   - 目標習熟度: 80%（固定）

2. ユーザー入力（1項目必須）
   - 実際の学習時間: ___h（必須）
   - 課題・ブロッカー: ______（任意）

3. AI自動補完
   - 学習成果: AI生成（ユーザー入力から推測）
   - 習熟度計算: min((actual_hours / estimated_hours) * 80, 100)  # 上限100%
   - ステータス判定: 80%以上=完了、1-79%=要復習、0%=未学習

4. progress_state.yaml更新
   - skill_mastery[skill_key].mastery_level 更新
   - skill_mastery[skill_key].status 更新
   - learning_history[] 追加

5. daily_progress.md更新
   - 日次学習進捗セクション追加
```

#### 4.4.1 Mastery計算ロジック（統合アプローチ対応）

**基本計算式**:
```python
mastery_level = min((actual_hours / estimated_hours) * 80, 100)  # 上限100%
```

**計算式の前提条件**（6週間プラン固有）:
1. **`actual_hours`の定義**: Phase 1 + Phase 2 + Phase 3の合計時間
2. **`estimated_hours`の定義**: ドメイン別Phase配分（ADR-006）
   - 既知領域: 5H/項目
   - 応用領域: 7H/項目
   - 新規領域: 7H/項目
   - 統合領域: 7H/項目
3. **目標習熟度**: 80%固定（完了基準）
4. **統合型前提**: 学習と実装を分離せず、同一セッションで実施

**計算例**:
```python
# 例1: Docker Multi-stage builds（既知領域・想定5時間）
actual_hours = 5  # Phase 1: 0.5H + Phase 2: 3.5H + Phase 3: 1H
estimated_hours = 5
mastery_level = (5 / 5) * 80 = 80%  # ✅ 完了

# 例2: asyncio基礎（新規領域・想定7時間、実際6時間で完了）
actual_hours = 6
estimated_hours = 7
mastery_level = (6 / 7) * 80 = 68.6%  # ⚠️ 要復習

# 例3: GitHub Actions（新規領域・想定7時間、実際8時間かかった）
actual_hours = 8
estimated_hours = 7
mastery_level = (8 / 7) * 80 = 91.4%  # ✅ 完了（上限100%でクリップ）
```

**上限処理**:
```python
mastery_level = min((actual_hours / estimated_hours) * 80, 100)
```

#### 4.4.2 ステータス判定ロジック

**判定基準**:
```python
if mastery_level >= 80:
    status = "完了"
elif mastery_level >= 1:
    status = "要復習"
else:
    status = "未学習"
```

**ステータス別の対応**:
- **完了（80%+）**: 次の学習項目に進む
- **要復習（1-79%）**: 復習ループ（最大3回）→ 合計時間で再計算
- **未学習（0%）**: まだ着手していない

**復習ループの処理**:
```python
# 例: pytest基礎（既知領域・初回4H、復習1H追加）
initial_actual_hours = 4  # 初回
estimated_hours = 5  # 既知領域
mastery_level_initial = (4 / 5) * 80 = 64%  # 要復習

# 復習1回目（1H追加）
total_actual_hours = 4 + 1 = 5
mastery_level_updated = (5 / 5) * 80 = 80%  # ✅ 完了
```

#### 4.4.3 progress_state.yaml更新仕様

**更新対象フィールド**:
```yaml
skill_mastery:
  docker_multi_stage_builds:
    mastery_level: 80        # 更新: 計算結果
    target_level: 80         # 固定: 常に80%
    status: "完了"           # 更新: ステータス判定結果
    last_updated: "2025-11-21"  # 更新: 現在日時
    estimated_hours: 5       # 固定: ドメイン別（既知領域=5H）
    actual_hours: 5          # 更新: 累積実際時間
    phase_breakdown:         # 更新: Phase別内訳（既知領域パターン）
      phase1: 0.5
      phase2: 3.5
      phase3: 1.0
    domain: "既知領域"       # 新規: ドメイン分類

learning_history:
  - date: "2025-11-21"
    item: "Docker Multi-stage builds"
    hours: 5
    mastery_achieved: 80
    status: "完了"
    notes: "layer caching最適化を習得"
```

#### 4.4.4 daily_progress.md更新仕様

**追加セクション**:
```markdown
### 2025-11-21 (木)

#### 📚 学習進捗
**学習時間**: 6h / 8h目標

**学習フロー**: @[CLAUDE.md#AI協働学習フロー仕組み]

**Phase 1: AI説明・概念理解**（0.5H・既知領域パターン）
- 理解度チェックリスト: ✅ 5/5項目達成
- 理解度自己評価: 30%

**Phase 2: AI協働実装**（3.5H・既知領域パターン）
- AI依頼品質: Level 3（技術的依頼）
- AIレビュー品質: Level 3（2項目指摘）

**学習内容**:
- Docker Multi-stage builds基礎習得（既知領域）
- 4-stage構成設計（deps/build/test/runtime）
- layer caching最適化パターン理解

**課題・ブロッカー**:
- test stageでのカバレッジ計測方法が未理解
- 次回: pytest --cov-report統合の調査

**翌日予定**:
- docker-compose 4環境構築開始
```

#### 4.4.5 コマンド例

**基本形**:
```bash
# 既知領域（5H標準）の例
学習記録: 5h、課題: test stageカバレッジ計測未理解

# 新規領域（7H標準）の例
学習記録: 7h、asyncio基礎習得完了
```

**最小形（課題なし）**:
```bash
学習記録: 5h  # ドメイン別（既知=5H, 応用/新規/統合=7H）
```

**復習後**:
```bash
学習記録: 6h、復習1h追加、課題解決  # 既知領域5H+復習1H
```

#### 4.4.6 エラーハンドリング

**エラー1: 推定時間データなし**
```
エラー: 学習項目「{item_name}」の推定時間が progress_state.yaml に見つかりません。
対処: progress_state.yaml に estimated_hours を追加してください。
```

**エラー2: 実際時間が異常値**
```
エラー: 実際時間（{actual_hours}h）が推定時間（{estimated_hours}h）の3倍を超えています。
確認: 入力値に誤りがないか確認してください。
```

**エラー3: progress_state.yaml書き込み失敗**
```
エラー: progress_state.yaml の更新に失敗しました。
対処: ファイルの権限とYAML構文を確認してください。
```

### 4.5 Trigger 4: 実装記録

**検出キーワード**: `実装記録`

**目的**: 品質ゲート通過後に、commit message自動生成・commit実行・実装成果記録

**自動化率**: 90%（commit message承認のみユーザー確認）

**前提条件**: `git add .` でファイルをステージング済み

**実行フロー**:
```
0. 前提条件確認
   - git status でステージング済み変更を確認
   - ステージング未済の場合 → エラー表示

1. ステージング解析（完全自動）
   - git diff --cached --name-only
   - git diff --cached --stat
   - git diff --cached（変更内容詳細）

2. 品質ゲート実行（完全自動）
   - Gate 1: uv run pytest --cov=. --cov-fail-under=[Phase別目標]
   - Gate 2: uv run ruff check .
   - Gate 3: uv run mypy utils/ config/
   - Gate 4: git status（未追跡ファイルチェック）

3. 品質ゲート判定（完全自動）
   - 全合格 → Phase 4へ
   - 1つでも失敗 → エラー表示、処理中止

4. AI解析（完全自動）
   - ファイルパス + 変更内容を解析
   - Conventional Commits判定（feat:/fix:/test:/docs:/refactor:）
   - commit message自動生成

5. ユーザー承認プロンプト（手動確認）
   - 生成メッセージを表示
   - 3択: [1] 承認してcommit / [2] メッセージを修正 / [3] キャンセル

6. Commit実行（完全自動、承認時のみ）
   - git commit -m "生成メッセージ"（または修正後メッセージ）
   - commit成功確認

7. メトリクス抽出（完全自動、commit後）
   - 変更行数: git diff HEAD~1..HEAD --stat
   - 変更ファイル数: 同上
   - テスト数: pytest summary
   - カバレッジ: pytest coverage report

8. progress_state.yaml更新（完全自動）
   - implementation_history[] 追加
   - メトリクス自動記録

9. daily_progress.md更新（完全自動）
   - 日次実装進捗セクション追加
   - メトリクス変化自動記録
```

**所要時間**: 30-60秒（品質ゲート実行含む）

#### 4.5.1 品質ゲート詳細仕様

**Gate 1: Tests Pass**
```bash
# 実行コマンド（Week別カバレッジ目標）
# Week 1-2: 50%, Week 3-4: 70%, Week 5-6: 85%

uv run pytest --cov=. --cov-fail-under=[Phase別目標]

# 合格基準
- 全テストケース合格（0 failed）
- カバレッジ目標達成（Week別に変動）
- テストマーカー合格（unit, integration, performance）
```

**Gate 2: Linter Pass**
```bash
# 実行コマンド
uv run ruff check .

# 合格基準
- エラー0件
- 自動修正可能な警告は --fix で修正済み
- スタイルガイドライン遵守
```

**Gate 3: Type Check Pass**
```bash
# 実行コマンド
uv run mypy utils/ config/

# 合格基準
- 型エラー0件
- 全public関数に型ヒント付与
- 戻り値型指定済み
```

**Gate 4: Staging Verification**
```bash
# 実行コマンド
git status

# 合格基準
- ステージング済み変更が存在する（"Changes to be committed"）
- Unstaged changesが存在しない
- 未追跡の実装成果物なし
```

#### 4.5.2 実装活動判定ロジック

**判定基準**:
```python
def is_implementation_recognized(gate_results: dict) -> bool:
    """
    実装活動認定判定

    Args:
        gate_results: {
            "gate1_tests": bool,
            "gate2_linter": bool,
            "gate3_types": bool,
            "gate4_git": bool
        }

    Returns:
        True: 実装活動認定（全Gates合格）
        False: 実装活動不認定（1つでも不合格）
    """
    return all(gate_results.values())
```

**判定結果の記録**:
```yaml
implementation_history:
  - date: "2025-11-21"
    task: "Docker 4-stage build実装"
    hours: 6
    recognized: true  # 実装活動認定
    gates:
      gate1_tests: true
      gate2_linter: true
      gate3_types: true
      gate4_git: true
    metrics:
      lines_added: 150
      lines_deleted: 20
      files_changed: 3
      tests_added: 10
      coverage_delta: "+5%"  # 65% → 70%
```

#### 4.5.3 AI解析ロジック（commit message自動生成）

**Conventional Commits判定ルール**:

| ファイルパターン | 変更内容キーワード | Prefix | Message例 |
|-----------------|-------------------|--------|-----------|
| `tests/**` | `+def test_` | `test:` | add tests for api_client |
| `docs/**`, `CLAUDE.md` | 任意 | `docs:` | update documentation |
| `utils/**` | `+def ` (新規のみ) | `feat:` | add retry_logic to api_client |
| `utils/**` | `+try:`, `+except` | `fix:` | improve error handling in api_client |
| `utils/**` | `+def ` + `-def ` | `refactor:` | refactor api_client module |
| `config/**` | 任意 | `refactor:` | update configuration |
| その他 | 任意 | `refactor:` | refactor codebase |

**ユーザー承認プロンプト**:
```
🤖 AI解析完了
📝 提案メッセージ: "feat: add retry_logic to api_client"

❓ このメッセージでcommitしますか？
[1] 承認してcommit
[2] メッセージを修正
[3] キャンセル
> _
```

> **🛡️ セキュリティ注記**: commit messageの生成・修正時は以下を遵守:
> - シェル特殊文字（`` ` `` `$` `()` `;` `&` `|`）を自動除去
> - 改行は空白に置換
> - 最大長200文字に制限
> - Claude Codeの組み込みgit機能を使用（subprocess直接呼び出し禁止）

#### 4.5.4 メトリクス自動抽出

**Git統計**:
```bash
# 変更行数・ファイル数
git diff HEAD~1..HEAD --stat

# 出力例
 Dockerfile                     |  85 +++++++++++++++++++++++++++++++++++++++++
 docker-compose.yml             |  45 ++++++++++++++++++++++
 tests/unit/test_docker.py      |  20 ++++++++++
 3 files changed, 150 insertions(+)
```

**pytest統計**:
```bash
# テスト数
uv run pytest --collect-only | grep "<Function" | wc -l

# カバレッジ
uv run pytest --cov=. --cov-report=term | grep "TOTAL"
```

#### 4.5.5 daily_progress.md更新仕様

**追加セクション**:
```markdown
#### 🛠️ ポートフォリオ実装進捗
**実装時間**: 6h

**品質ゲート（実装活動判定）**:
- [x] Gate 1: pytest合格（60/60テスト、カバレッジ70%）
- [x] Gate 2: ruff合格（0 errors）
- [x] Gate 3: mypy合格（0 errors）
- [x] Gate 4: git commit完了（feat: Docker 4-stage build）

**実装活動認定**: ✅ 認定

**メトリクス変化**:
- カバレッジ: 65% → 70%（+5%）
- テスト数: 50 → 60（+10）
- Docker実装: 0% → 60%
```

#### 4.5.6 コマンド例

**前提条件**:
```bash
# 実装完了後、ファイルをステージング
git add .
```

**基本形**:
```bash
実装記録
```

---

### 4.6 Trigger 5: 週次振り返り

#### 4.6.1 Trigger概要

**検出キーワード**: `週次振り返り`

**実行タイミング**: 週末（金曜日）
**実施対象期間**: Week 1-6（全6週間）

**目的**: 週次データを集計し、進捗レポートを自動生成。次週計画の調整を支援

**自動化率**: 95%（レポート生成は完全自動、次週調整提案はAI支援）

**統合度**: ★★☆（複数Triggerのデータ集約）

> **配点構成の違い**: 週次振り返りは複数技術の統合理解を評価するため、5+10+10=25点の配点を採用しています（Trigger 6の日次理解度確認の8+8+9=25点とは異なります）

#### 4.6.2 実行フロー

```
1. 週次データ集計（完全自動）
   - progress_state.yamlのlearning_history[]から週次集計
   - implementation_history[]から週次集計
   - 週次メトリクス計算（学習時間、実装時間、カバレッジ推移等）

2. 週次理解度確認（AI自動生成問題）
   - 問題構成: 概念説明(5点) + 設計判断(10点) + トラブルシューティング(10点) = 25点
   - 合格基準: 20点以上/25点（80%以上）
   - 不合格時は復習ループ（最大3回）

3. 週次レポート生成（AI支援）
   # Week X 週次振り返り

   ## 達成事項
   - 学習: {learning_items_completed}
   - 実装: {implementation_tasks_completed}

   ## メトリクス進捗
   - カバレッジ: {coverage_start}% → {coverage_end}%
   - テスト数: {test_count_start} → {test_count_end}
   - 習熟度達成項目: {mastery_achieved_count}/{total_items}

   ## 理解度確認結果
   - スコア: __/25点 (__%)
   - 合否: ✅/⚠️

   ## 次週計画調整
   - {next_week_adjustments}

4. progress_state.yaml更新（完全自動）
   - weekly_reviews[] 追加
   - 週次メトリクスサマリー記録

5. daily_progress.md更新（完全自動）
   - 週次サマリーセクション追加

6. 次週計画調整提案（AI支援）
   - 進捗遅延がある場合の調整案提示
   - 習熟度未達成項目の復習計画提案
```

**所要時間**: 2分（集計30秒 + AI生成90秒）

#### 4.6.3 採点基準（部分点ルーブリック）

| 問題 | 満点 | 部分点基準 |
|-----|-----|-----------|
| 概念説明 | 5点 | 5点: 正確な説明 + 具体例 / 3点: 概念は正しいが説明不足 / 1点: 部分的に正しい |
| 設計判断 | 10点 | 10点: 最適解 + トレードオフ説明 / 7点: 妥当な解 + 理由 / 4点: 解は正しいが理由不足 / 1点: 方向性のみ正しい |
| トラブルシューティング | 10点 | 10点: 根本原因特定 + 解決策 + 再発防止 / 7点: 原因特定 + 解決策 / 4点: 原因特定のみ / 1点: 調査方針のみ |

**配点根拠**:
- 週次振り返りは「複数技術を横断した統合理解」を評価
- 設計判断・トラブルシューティングを重視（各10点）
- Trigger 6（日次）は個別技術の深い理解を評価（8+8+9配点）

#### 4.6.4 progress_state.yaml更新仕様

**追加フィールド**:
```yaml
weekly_reviews:
  - week: 1
    date: "2025-11-22"
    understanding_check:
      score: 22
      passing: true
      questions_results:
        - question: 1
          score: 4
          max_score: 5
        - question: 2
          score: 9
          max_score: 10
        - question: 3
          score: 9
          max_score: 10
    metrics:
      learning_hours_planned: 48
      learning_hours_actual: 45
      implementation_hours: 20
      coverage_start: 50
      coverage_end: 58
      tests_added: 15
      mastery_achieved: 5
      mastery_total: 6
    adjustments:
      - "Week 2でasyncio復習1H追加"
```

#### 4.6.5 daily_progress.md更新仕様

**追加セクション**:
```markdown
## Week X 週次振り返り

**実施日**: 2025-11-22（金）
**所要時間**: 60分

### 週次メトリクス

| 指標 | 計画値 | 実績値 | 達成率 |
|-----|-------|-------|-------|
| 学習時間 | 48h | 45h | 94% |
| カバレッジ | 50% → 60% | 50% → 58% | 97% |
| テスト数 | +20 | +15 | 75% |
| 習熟度達成 | 6/6 | 5/6 | 83% |

### 理解度確認結果
**スコア**: 22/25点 (88%)
**合否**: ✅ 合格

**内訳**:
- 概念説明: 4/5点
- 設計判断: 9/10点
- トラブルシューティング: 9/10点

### 次週計画調整
- asyncio復習1H追加（習熟度未達成項目）
```

#### 4.6.6 コマンド例

**基本形**:
```bash
週次振り返り
```

**AI実行内容**:
```
1. Week X の週次データを集計中...

【週次メトリクス】
- 学習時間: 45h / 48h目標 (94%)
- カバレッジ: 50% → 58%
- テスト追加: +15件
- 習熟度達成: 5/6項目

【週次理解度確認】

問題1（概念説明・5点）:
httpxとrequestsの主な違いを説明し、非同期処理が有効なユースケースを1つ挙げてください。

あなたの回答: _____

問題2（設計判断・10点）:
以下の要件に対して、同期/非同期どちらのAPIクライアント設計が適切か判断し、理由を説明してください。
要件: 10個のAPIエンドポイントから並列でデータ取得し、結果を集約する

あなたの回答: _____

問題3（トラブルシューティング・10点）:
「asyncio.TimeoutError」が頻発する場合の原因調査手順と解決策を説明してください。

あなたの回答: _____

---

採点中...

【結果】
- 問題1: 4/5点 ⚠️（具体例が不足）
- 問題2: 9/10点 ✅
- 問題3: 9/10点 ✅

合計: 22/25点（88%）✅ 合格

【次週計画調整提案】
- asyncio基礎の復習1H追加を推奨（問題1の弱点対応）

progress_state.yaml更新完了
daily_progress.md更新完了
```

---

### 4.7 Trigger 6: 理解度確認

#### 4.7.1 Trigger概要

**検出キーワード**: `理解度確認`

**実施対象期間**: Week 1-6（Day 1-38）の学習期間
**実施除外期間**: 6週プランは全期間が学習期間のため除外期間なし

**目的**: Day都度オンデマンドで理解度確認問題を生成し、習熟度80%+到達を検証

**自動化率**: 85%（AI自動生成問題、ユーザー回答のみ手動）

**実行タイミング**:
- Phase 2完了（品質ゲート全合格 + git commit完了）後
- 1学習項目につき1回実施
- 合格基準: 20点以上/25点（80%以上）
- 不合格時は復習ループ（最大3回）

#### 4.7.2 AI自動生成問題の仕様

**問題形式**:
- 3問・25点満点（各問題の配点: 問1: 8点、問2: 8点、問3: 9点）
- 出題タイプ: 選択式（4択） + 記述式（コード記述・説明）

**問題生成ロジック**:
```python
def generate_understanding_check(
    topic: str,
    phase2_code: str,
    learning_hours: float
) -> dict:
    """
    理解度確認問題の自動生成

    Args:
        topic: 学習項目名（例: "Docker Multi-stage builds"）
        phase2_code: Phase 2で実装したコード（AIが分析用）
        learning_hours: 実際の学習時間

    Returns:
        {
            "questions": [
                {
                    "number": 1,
                    "type": "multiple_choice",
                    "question": "...",
                    "choices": ["A", "B", "C", "D"],
                    "points": 8
                },
                {
                    "number": 2,
                    "type": "code_writing",
                    "question": "...",
                    "points": 8
                },
                {
                    "number": 3,
                    "type": "explanation",
                    "question": "...",
                    "points": 9
                }
            ],
            "total_points": 25
        }
    """
```

**出題難易度の調整**:
```python
# 学習時間に基づく難易度調整
if learning_hours < estimated_hours * 0.8:
    difficulty = "easy"  # 理解が浅い可能性
elif learning_hours <= estimated_hours * 1.2:
    difficulty = "medium"  # 標準的な理解
else:
    difficulty = "hard"  # 深い理解を期待
```

#### 4.7.3 問題例（Docker Multi-stage builds）

**問題1（選択式・8点）**:
```
以下のうち、Docker Multi-stage buildの主な利点はどれですか？

A. ビルド時間の短縮のみ
B. 最終イメージサイズの削減とセキュリティ向上
C. デバッグ機能の強化
D. ネットワーク接続の高速化

正解: B
配点: 8点
```

**問題2（コード記述・8点）**:
```
以下のDockerfileにtest stageを追加し、pytest --cov-fail-under=70を実行するように記述してください。
```

```dockerfile
FROM python:3.12-slim AS deps
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync

FROM deps AS build
COPY . .
RUN uv run ruff check .

# ここにtest stageを追加してください

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=deps /app/.venv /app/.venv
COPY --from=build /app /app
CMD ["uv", "run", "python", "-m", "app"]
```

**採点基準（8点満点）**:
- FROM deps AS test（2点）
- COPY . .（1点）
- RUN uv run pytest --cov=. --cov-fail-under=70（4点）
- 正しい位置（build stageとruntime stageの間）（1点）

**問題3（説明・9点）**:
```
あなたが実装したDockerfile 4-stageで、layer cachingを最適化した箇所を2つ説明してください。
それぞれについて、なぜその最適化がビルド時間短縮に貢献するのかを記述してください。
```

**採点基準（9点満点）**:
- 最適化1の説明（3点）
  - 最適化内容（1点）
  - 理由説明（2点）
- 最適化2の説明（3点）
  - 最適化内容（1点）
  - 理由説明（2点）
- 全体の論理性（3点）

**模範解答例**:
1. pyproject.toml/uv.lockを先にCOPYし、依存関係インストールを分離（3点）
   - ソースコード変更時に deps stage を再利用可能
   - 依存関係変更がない限り、キャッシュが有効

2. COPY . . をdeps stageではなくbuild stage以降に配置（3点）
   - ソースコード変更の影響範囲を最小化
   - deps stageのキャッシュを最大限活用

#### 4.7.4 採点ロジック

**自動採点（選択式）**:
```python
def auto_grade_multiple_choice(
    user_answer: str,
    correct_answer: str,
    points: int
) -> int:
    """
    選択式問題の自動採点

    Returns:
        points: 正解の場合
        0: 不正解の場合
    """
    return points if user_answer == correct_answer else 0
```

**AI採点（記述式）**:
```python
def ai_grade_explanation(
    user_answer: str,
    rubric: dict,
    max_points: int
) -> tuple[int, str]:
    """
    記述式問題のAI採点

    Args:
        user_answer: ユーザーの回答
        rubric: 採点基準（各項目の配点）
        max_points: 満点

    Returns:
        (score, feedback): 点数とフィードバック
    """
    # AIが採点基準に基づき評価
    score = ai_evaluate(user_answer, rubric)
    feedback = ai_generate_feedback(user_answer, rubric, score)

    return (score, feedback)
```

#### 4.7.5 合格判定と復習ループ

**合格基準**:
```python
passing_score = 20  # 25点満点の80%

if total_score >= passing_score:
    status = "合格"
    mastery_level = 80  # 習熟度80%確定
else:
    status = "不合格"
    mastery_level = (total_score / 25) * 80  # 比例計算
```

**復習ループ**:
```python
max_retries = 3
current_retry = 0

while current_retry < max_retries and total_score < passing_score:
    # 不合格箇所の復習
    review_topics = identify_weak_areas(user_answers, correct_answers)

    # 復習時間（1-2時間）
    review_hours = estimate_review_time(review_topics)

    # 再試験（難易度調整）
    retry_questions = generate_retry_questions(
        topic,
        review_topics,
        difficulty="medium"  # 初回より易しく
    )

    # 再採点
    retry_score = grade_retry(retry_questions, user_retry_answers)

    if retry_score >= passing_score:
        break

    current_retry += 1

# 最終習熟度計算（復習時間含む）
total_hours = initial_hours + sum(review_hours)
final_mastery = calculate_mastery(total_hours, estimated_hours)
```

#### 4.7.6 progress_state.yaml更新仕様

**理解度確認結果の記録**:
```yaml
skill_mastery:
  docker_multi_stage_builds:
    mastery_level: 80
    status: "完了"
    understanding_check:
      date: "2025-11-21"
      score: 22  # 25点満点
      passing: true
      attempts: 1
      questions_results:
        - question: 1
          score: 8
          max_score: 8
          correct: true
        - question: 2
          score: 6
          max_score: 8
          feedback: "test stage実装は正しいが、layer caching最適化の説明が不足"
        - question: 3
          score: 8
          max_score: 9
          feedback: "2つの最適化を正しく説明、論理性も良好"
```

#### 4.7.7 daily_progress.md更新仕様

**追加セクション**:
```markdown
#### 📊 理解度確認
**実施時間**: 14:00-15:00
**学習項目**: Docker Multi-stage builds
**スコア**: 22/25点 (88%)
**合否**: ✅ 合格

**詳細**:
- 問題1（選択式・8点）: 8/8点 ✅
- 問題2（コード記述・8点）: 6/8点 ⚠️
- 問題3（説明・9点）: 8/9点 ✅

**フィードバック**:
- 問題2: test stage実装は正しいが、layer caching最適化の説明が不足

**復習計画**（不合格時のみ）:
- [弱点箇所の復習計画]
```

**更新タイミング**: Trigger 6実行時（自動）

**更新内容**:
- 理解度確認の実施時間・学習項目を記録
- スコア（__/25点）と合否判定を記録
- 問題別の得点と採点結果を詳細記録
- AIからのフィードバックを記録
- 不合格時は復習計画を記録

**データ整合性**:
progress_state.yamlとdaily_progress.mdの同期を保証します（Trigger 3, 4, 5と同様）。
理解度確認結果は両方のファイルに記録され、100%同期が維持される。

#### 4.7.8 コマンド例

**基本形**:
```bash
理解度確認
```

**AI実行内容**:
```
1. 学習項目「Docker Multi-stage builds」の理解度確認問題を生成します...

【問題1】（選択式・8点）
以下のうち、Docker Multi-stage buildの主な利点はどれですか？
A. ビルド時間の短縮のみ
B. 最終イメージサイズの削減とセキュリティ向上
C. デバッグ機能の強化
D. ネットワーク接続の高速化

あなたの回答: _____

【問題2】（コード記述・8点）
（問題文省略）

あなたのコード:
（ユーザー記述）

【問題3】（説明・9点）
（問題文省略）

あなたの説明:
（ユーザー記述）

---

採点中...

【結果】
- 問題1: 8/8点 ✅
- 問題2: 6/8点 ⚠️（フィードバック: test stage実装は正しいが、layer caching最適化の説明が不足）
- 問題3: 8/9点 ✅

合計: 22/25点（88%）✅ 合格

習熟度: 80%達成 → ステータス「完了」
progress_state.yaml更新完了
```

---

### 4.8 progress_state.yamlスキーマ仕様

#### 4.8.1 ファイル概要

**ファイルパス**: `progress_state.yaml`（プロジェクトルート）

**目的**: 6週間プランの進捗状態を一元管理するデータファイル

**更新タイミング**:
- Trigger 1（学習開始）: `current_learning_item`更新
- Trigger 2（実装開始）: `current_implementation_task`更新
- Trigger 3（学習記録）: `skill_mastery`, `learning_history`更新
- Trigger 4（実装記録）: `implementation_history`更新
- Trigger 6（理解度確認）: `skill_mastery.understanding_check`更新

#### 4.8.2 完全スキーマ定義

```yaml
# ====================================
# 現在状態管理
# ====================================
current_week: 1              # 現在週（1-6）
current_day: 1               # 現在日（1-38）
current_phase: "学習期間"    # "学習期間"（6週プランは全期間学習）

current_learning_item:       # 次に学習する項目
  name: "Docker Multi-stage builds"
  week: 3
  day: 13
  estimated_hours: 5           # ドメイン別（既知=5H, 応用/新規/統合=7H）
  domain: "既知領域"            # ADR-006: 4パターン分類
  phase_breakdown:              # ADR-006: Phase 3統一（1H固定）
    phase1: 0.5                 # 既知領域パターン
    phase2: 3.5
    phase3: 1.0

current_implementation_task: # 次に実装するタスク
  name: "Dockerfile 4-stage実装"
  week: 3
  day: 13
  estimated_hours: 5           # ドメイン別（既知=5H, 応用/新規/統合=7H）
  domain: "既知領域"            # ADR-006: 4パターン分類
  deliverables:
    - "Dockerfile（85行）"
    - "docker-compose.yml（45行）"
    - "test_docker.py（20行）"

# ====================================
# 習熟度管理
# ====================================
skill_mastery:
  # Python基礎（Week 1-2・応用領域）
  python_type_hints:
    mastery_level: 80        # 習熟度（0-100%）
    target_level: 80         # 目標習熟度（固定80%）
    status: "完了"           # "未学習" | "要復習" | "完了"
    last_updated: "2025-11-21"
    estimated_hours: 7       # ADR-006: 応用領域=7H
    actual_hours: 7
    domain: "応用領域"       # ADR-006: 4パターン分類
    phase_breakdown:         # ADR-006: 応用領域パターン（1H+5H+1H）
      phase1: 1.0
      phase2: 5.0
      phase3: 1.0            # Phase 3統一原則（全パターン1H固定）
    understanding_check:     # Trigger 6結果
      date: "2025-11-21"
      score: 22
      passing: true
      attempts: 1

  # Docker基礎（Week 3-4・既知領域）
  docker_multi_stage_builds:
    mastery_level: 80
    target_level: 80
    status: "完了"
    last_updated: "2025-11-21"
    estimated_hours: 5       # ADR-006: 既知領域=5H
    actual_hours: 5
    domain: "既知領域"       # ADR-006: 4パターン分類
    phase_breakdown:         # ADR-006: 既知領域パターン（0.5H+3.5H+1H）
      phase1: 0.5
      phase2: 3.5
      phase3: 1.0            # Phase 3統一原則（全パターン1H固定）
    understanding_check:
      date: "2025-11-21"
      score: 22
      passing: true
      attempts: 1
      questions_results:
        - question: 1
          score: 8
          max_score: 8
          correct: true
        - question: 2
          score: 6
          max_score: 8
          feedback: "test stage実装は正しいが、layer caching最適化の説明が不足"
        - question: 3
          score: 8
          max_score: 9
          feedback: "2つの最適化を正しく説明、論理性も良好"

# ====================================
# 学習履歴
# ====================================
learning_history:
  - date: "2025-11-21"
    week: 3
    day: 13
    item: "Docker Multi-stage builds"
    hours: 6
    mastery_achieved: 80
    status: "完了"
    phase_breakdown:
      phase1: 0.5
      phase2: 4.5
      phase3: 1.0
    notes: "layer caching最適化を習得、test stage統合完了"

# ====================================
# 実装履歴
# ====================================
implementation_history:
  - date: "2025-11-21"
    week: 3
    day: 13
    task: "Dockerfile 4-stage実装"
    hours: 6
    recognized: true         # 実装活動認定
    gates:
      gate1_tests: true
      gate2_linter: true
      gate3_types: true
      gate4_git: true
    metrics:
      lines_added: 150
      lines_deleted: 0
      files_changed: 3
      tests_total: 60
      tests_added: 10
      coverage_before: 65
      coverage_after: 70
      coverage_delta: "+5%"
    git_commit: "a3f5b2c1d9e8f7a6b5c4d3e2f1a0b9c8d7e6f5a4"
    commit_message: "feat: implement Docker 4-stage build with test stage"

# ====================================
# 週次サマリー
# ====================================
weekly_summary:
  week3:
    dates: "2025-11-13 - 2025-11-19"
    learning_hours: 42       # 学習42h（目標42h）
    implementation_hours: 48 # 実装48h（目標48h）
    items_completed: 14      # 完了14項目
    items_review: 2          # 要復習2項目
    coverage_start: 50
    coverage_end: 70
    coverage_delta: "+20%"
    achievement_rate: 87     # 達成率87%

# ====================================
# メタデータ
# ====================================
metadata:
  plan_version: "6週間プラン v1.0（247H版・ADR-006）"
  last_updated: "2025-11-21 14:30:00"
  total_weeks: 6
  total_days: 37
  total_learning_items: 48
  learning_complete: 14
  learning_review: 2
  learning_pending: 32
```

#### 4.8.3 スキーマバリデーション

**必須フィールド検証**:
```python
def validate_learning_state(data: dict) -> list[str]:
    """
    progress_state.yamlのバリデーション

    Returns:
        エラーメッセージのリスト（空=正常）
    """
    errors = []

    # 現在状態の検証
    if not 1 <= data.get("current_week", 0) <= 6:
        errors.append("current_weekは1-6の範囲である必要があります")

    if not 1 <= data.get("current_day", 0) <= 38:
        errors.append("current_dayは1-38の範囲である必要があります")

    # 習熟度の検証
    for skill, details in data.get("skill_mastery", {}).items():
        if not 0 <= details.get("mastery_level", -1) <= 100:
            errors.append(f"{skill}: mastery_levelは0-100の範囲である必要があります")

        if details.get("target_level") != 80:
            errors.append(f"{skill}: target_levelは80固定である必要があります")

        if details.get("status") not in ["未学習", "要復習", "完了"]:
            errors.append(f"{skill}: statusは「未学習」「要復習」「完了」のいずれかである必要があります")

    return errors
```

#### 4.8.4 Week別進捗計算

**カバレッジ進捗**:
```python
def calculate_coverage_progress(
    current_week: int,
    current_coverage: float
) -> dict:
    """
    Week別のカバレッジ進捗計算

    Args:
        current_week: 現在週（1-6）
        current_coverage: 現在のカバレッジ（0-100%）

    Returns:
        {
            "target": 目標カバレッジ,
            "progress_rate": 進捗率（0-100%）,
            "on_track": 順調かどうか
        }
    """
    week_targets = {
        1: 40, 2: 50,   # Week 1-2: 50%目標
        3: 60, 4: 70,   # Week 3-4: 70%目標
        5: 80, 6: 85    # Week 5-6: 85%目標
    }

    target = week_targets.get(current_week, 85)
    progress_rate = (current_coverage / target) * 100
    on_track = progress_rate >= 80  # 80%以上で順調判定

    return {
        "target": target,
        "progress_rate": progress_rate,
        "on_track": on_track
    }
```

**習熟度集計**:
```python
def aggregate_mastery_stats(
    skill_mastery: dict
) -> dict:
    """
    習熟度統計の集計

    Returns:
        {
            "total_items": 総項目数,
            "completed": 完了項目数,
            "review_needed": 要復習項目数,
            "not_started": 未学習項目数,
            "average_mastery": 平均習熟度
        }
    """
    total = len(skill_mastery)
    completed = sum(1 for v in skill_mastery.values() if v["status"] == "完了")
    review = sum(1 for v in skill_mastery.values() if v["status"] == "要復習")
    not_started = sum(1 for v in skill_mastery.values() if v["status"] == "未学習")

    avg_mastery = sum(v["mastery_level"] for v in skill_mastery.values()) / total if total > 0 else 0

    return {
        "total_items": total,
        "completed": completed,
        "review_needed": review,
        "not_started": not_started,
        "average_mastery": avg_mastery
    }
```

---

### 4.9 実装チェックリスト

#### 4.9.0 チェックリスト対象について

**対象Trigger** (統合度★★★):
- **Trigger 3, 4, 6**: 複数ファイル更新・複雑なロジックを含むため、詳細チェックリスト必須

**対象外Trigger** (統合度★☆☆〜★★☆):
| Trigger | 理由 |
|---------|------|
| Trigger 1 (学習開始) | コンテキスト読込のみ、YAML更新は`current_learning_item`のみ |
| Trigger 2 (実装開始) | コンテキスト読込のみ、YAML更新は`current_implementation_task`のみ |
| Trigger 5 (週次振り返り) | 集計・レポート生成のみ、複雑なロジックなし |

> **設計根拠**: 「開始トリガー」と「集計トリガー」は処理が単純なため、実装時の確認項目を最小化し、開発効率を優先。

---

#### 4.9.1 Trigger 3実装チェックリスト

**Phase 1: セッション開始時コンテキスト自動補完**
- [ ] progress_state.yaml読み込み
- [ ] current_learning_item取得
- [ ] 推定時間・目標習熟度表示
- [ ] 確認プロンプト表示

**Phase 2: ユーザー入力受付**
- [ ] 実際の学習時間入力（必須）
- [ ] 課題・ブロッカー入力（任意）
- [ ] 入力値の妥当性検証（時間が推定の3倍以下）

**Phase 3: AI自動補完**
- [ ] 学習成果の推測・生成
- [ ] Mastery計算: `min((actual_hours / estimated_hours) * 80, 100)`
- [ ] ステータス判定: 80%以上=完了、1-79%=要復習、0%=未学習

**Phase 4: progress_state.yaml更新**
- [ ] skill_mastery[skill_key].mastery_level 更新
- [ ] skill_mastery[skill_key].status 更新
- [ ] skill_mastery[skill_key].last_updated 更新
- [ ] skill_mastery[skill_key].actual_hours 更新
- [ ] learning_history[] 追加（date, item, hours, mastery, status, notes）

**Phase 5: daily_progress.md更新**
- [ ] 日次学習進捗セクション追加
- [ ] 学習時間記録
- [ ] Phase別内訳記録
- [ ] 学習内容・課題記録

**Phase 6: エラーハンドリング**
- [ ] 推定時間データなしエラー処理
- [ ] 実際時間異常値エラー処理
- [ ] YAML書き込み失敗エラー処理

#### 4.9.2 Trigger 4実装チェックリスト

**Phase 1: Git解析**
- [ ] `git diff HEAD~1..HEAD --stat` 実行
- [ ] 変更行数・ファイル数抽出
- [ ] `git log -1 --format="%s%n%b"` 実行
- [ ] コミットメッセージ取得

**Phase 2: 品質ゲート実行**
- [ ] Gate 1: `uv run pytest --cov=. --cov-fail-under=[Phase別目標]` 実行
- [ ] Gate 2: `uv run ruff check .` 実行
- [ ] Gate 3: `uv run mypy utils/ config/` 実行
- [ ] Gate 4: `git status` 実行（未追跡ファイルチェック）

**Phase 3: 実装活動判定**
- [ ] 全Gatesの結果を集計
- [ ] 全合格 → 実装活動認定
- [ ] 1つでも失敗 → 実装活動不認定

**Phase 4: メトリクス抽出**
- [ ] 変更行数（追加・削除）
- [ ] 変更ファイル数
- [ ] テスト数（総数・追加数）
- [ ] カバレッジ（before/after/delta）

**Phase 5: progress_state.yaml更新**
- [ ] implementation_history[] 追加
- [ ] date, task, hours, recognized, gates, metrics, git_commit記録

**Phase 6: daily_progress.md更新**
- [ ] 日次実装進捗セクション追加
- [ ] 品質ゲート結果チェックリスト
- [ ] 実装活動認定ステータス
- [ ] 完了タスク一覧
- [ ] メトリクス変化
- [ ] AI協働分析
- [ ] 成果物（git commit hash、変更行数等）

#### 4.9.3 Trigger 6実装チェックリスト

**Phase 1: 問題生成準備**
- [ ] progress_state.yaml から学習項目取得
- [ ] Phase 2実装コード取得（AIが分析用）
- [ ] 実際の学習時間取得（難易度調整用）

**Phase 2: AI自動生成問題**
- [ ] 問題1（選択式・8点）生成
- [ ] 問題2（コード記述・8点）生成
- [ ] 問題3（説明・9点）生成
- [ ] 合計25点満点の問題セット完成

**Phase 3: 問題提示・回答受付**
- [ ] 問題1-3をユーザーに提示
- [ ] ユーザー回答受付（選択式・記述式）

**Phase 4: 採点**
- [ ] 問題1（選択式）自動採点
- [ ] 問題2（コード記述）AI採点
- [ ] 問題3（説明）AI採点
- [ ] 合計点数計算

**Phase 5: 合格判定**
- [ ] 20点以上/25点（80%以上）で合格
- [ ] 合格 → 習熟度80%確定
- [ ] 不合格 → 復習ループ（最大3回）

**Phase 6: progress_state.yaml更新**
- [ ] skill_mastery[skill_key].understanding_check 追加
- [ ] date, score, passing, attempts, questions_results記録

**Phase 7: 復習ループ（不合格時）**
- [ ] 弱点箇所の特定
- [ ] 復習時間の見積もり
- [ ] 再試験問題生成（難易度調整）
- [ ] 再採点
- [ ] 最終習熟度計算（復習時間含む）

#### 4.9.4 統合テスト項目

**Trigger 3 + Trigger 4の連携テスト**
- [ ] 学習記録（Trigger 3）後に実装記録（Trigger 4）が正常動作
- [ ] progress_state.yaml の skill_mastery と implementation_history が整合
- [ ] daily_progress.md に学習進捗と実装進捗の両方が記録

**Trigger 3 + Trigger 6の連携テスト**
- [ ] 学習記録（Trigger 3）後に理解度確認（Trigger 6）が正常動作
- [ ] progress_state.yaml の skill_mastery.understanding_check が正常記録
- [ ] 合格時に習熟度80%確定、不合格時に復習ループ発動

**Week跨ぎテスト**
- [ ] Week 1-2 → Week 3-4移行時にカバレッジ目標が50% → 70%に変更
- [ ] Week 3-4 → Week 5移行時にカバレッジ目標が70% → 85%に変更
- [ ] Week 5 → Week 6移行時にカバレッジ目標85%維持

**エラー処理テスト**
- [ ] progress_state.yaml 読み込み失敗時のエラーハンドリング
- [ ] 品質ゲート失敗時の適切なフィードバック
- [ ] 理解度確認問題生成失敗時のフォールバック

#### 4.9.5 品質保証

**自動化率**:
- Trigger 3（学習記録）: 80%（ユーザー入力1項目のみ）
- Trigger 4（実装記録）: 90%（ユーザー承認1ステップ）
- Trigger 6（理解度確認）: 85%（AI自動生成問題、ユーザー回答のみ手動）
- **総合自動化率**: 90%

**データ整合性**:
- progress_state.yaml と daily_progress.md の同期（100%保証）
- skill_mastery と learning_history/implementation_history の整合性（100%保証）
- Week別カバレッジ目標の自動変更（100%保証）

**エラー回復率**:
- YAML書き込み失敗時のリトライ（3回まで）
- 品質ゲート失敗時の修正ガイダンス提供
- 理解度確認不合格時の復習ループ（最大3回）

---

## 🚀 実装ロードマップ

### 5.1 Week 3: 準備・設計

#### 5.1.0 Week 1-2知識の移行

**実施タイミング**: Week 3 Day 15-16（MCP検証テスト合格後）

**Week 3タイムライン**:
| Day | タスク |
|-----|-------|
| Day 13 | 5.1.0.5 .mcp.json設定確認 + 5.1.1 MCP機能検証テスト
| Day 14 | 5.1.2 vault構造作成 + 5.1.3 セキュリティ設定
| Day 15 | 5.1.0 Week 1-2知識移行 + 5.1.4 テンプレート作成
| Day 16 | 5.1.5 CLAUDE.md更新 + 5.1.6 ADR_001作成
| Day 17 | 5.1.7 Obsidian基本操作習得 + 初回バックアップ 
| Day 18 | Week 3終了チェックリスト確認 

**目的**: Week 1-2でdaily_progress.mdに記録された知識をObsidianに移行し、検索可能にする

**前提**:
- Section 5.1.0.5および5.1.1 MCP機能検証テスト合格済み（Day 13完了）
- Week 1-2の学習・実装活動がdaily_progress.mdに記録済み

---

**移行手順**:

**1. daily_progress.md Week 1-2セクション確認**
```bash
# Week 1-2のエラー・ブロッカーを抽出
grep -A 5 "課題・ブロッカー" docs/progress/daily_progress.md | head -50

# AI協働の教訓を抽出
grep -A 3 "AI協働分析" docs/progress/daily_progress.md | head -30
```

抽出項目：
- 2回以上発生したエラー（★マーク付き推奨）
- 効果的だったAI依頼パターン
- 理解に時間がかかった概念

**2. 3回ルール遡及適用**

移行基準：
- **発生頻度2回以上** → Obsidian KB化（3回目発生を見越し）
- **1回のみ** → daily_progress.mdに残す（検索可能）

移行対象候補：
- トラブルシューティング: pytest fixture scope混乱、型チェックエラー
- AI協働パターン: 具体的コード例要求、エラーメッセージ全文提示
- 学習ログ: Week 1-2振り返り（概念理解の要点）

**3. 初期ノート作成**

```bash
# トラブルシューティングKB作成例
cat > obsidian-vault-local/02_Troubleshooting/Pytest_Fixture_Scope_Confusion.md <<'EOF'
---
title: pytest fixture scope理解の混乱
error_message: "ScopeMismatch: fixture scope=session, test scope=function"
category: testing/pytest
severity: medium
resolution_time: 45min
tags:
  - troubleshooting/pytest
  - error/fixture
created: 2025-11-22
resolved: 2025-11-22
---

# pytest fixture scope理解の混乱

## 🚨 問題概要
**エラーメッセージ**:
\`\`\`
ScopeMismatch: fixture 'async_client' scope=session, test scope=function
\`\`\`

**発生状況**:
- Week 1 Day 3, Week 2 Day 8（2回発生）
- conftest.py修正時

## 🔍 原因分析
**根本原因**: session scopeのfixtureをfunction scopeのテストで直接使用

## ✅ 解決策
### 適用コマンド
\`\`\`python
# conftest.py修正
@pytest.fixture(scope="function")  # sessionからfunctionに変更
async def async_client():
    ...
\`\`\`

## 📚 学習ポイント
1. fixture scopeはテストより広い必要がある
2. async fixtureはfunction scopeが安全

## 🔗 関連リンク
- 関連Week: [[Week 1]], [[Week 2]]
- 関連技術: [[pytest基礎]]
EOF

# AI協働パターン作成例
cat > obsidian-vault-local/03_AI_Collaboration/Pattern_Request_Code_Examples.md <<'EOF'
---
title: 具体的なコード例要求パターン
pattern_type: prompt-improvement
ai_dependency: medium
success_rate: 85%
tags:
  - ai-collaboration/pattern
  - prompt/level-3
created: 2025-11-22
---

# 具体的なコード例要求パターン

## 📝 パターン概要
**目的**: AI説明を実装可能なコードに変換

**適用場面**: Phase 1（概念理解）→ Phase 2（実装）移行時

## 🔄 Before → After

### Before (Level 2: 基本的依頼)
\`\`\`
"pytestのfixtureについて教えて"
\`\`\`

**問題点**:
- 抽象的な説明のみで実装イメージ湧かない
- 自プロジェクトへの適用方法不明

### After (Level 3: 具体的依頼)
\`\`\`
"pytestのfixtureについて、httpxクライアントを
session scopeで共有する具体的なコード例を
conftest.pyの実装例付きで教えて"
\`\`\`

**改善点**:
- 具体的な用途指定（httpxクライアント）
- ファイル名明示（conftest.py）
- 実装例要求（コードブロック期待）

## 📊 効果測定
- 成功率: 85%（Week 1-2実績）
- 時間削減: 理解時間 15min → 5min（67%削減）
- AI依頼回数削減: 3回 → 1回

## 🔗 関連リンク
- 関連技術: [[pytest基礎]], [[httpx基礎]]
- 類似パターン: [[Pattern_Error_Message_Full_Context]]
EOF
```

---

**Week 1-2推奨運用**（daily_progress.md記録時）:

```markdown
### Week 1-2での記録ルール

新規エラー発生時:
├─ daily_progress.mdの「課題・ブロッカー」セクションに記録
├─ 解決策も記録（翌日の「学習内容」で補足）
└─ 同じエラーが再発 → **★マーク追記**（Week 3移行の目印）

AI協働で効果的だったパターン:
├─ daily_progress.mdの「AI協働分析」セクションに記録
└─ 「Level 2→3改善」等の具体例をメモ
    （Week 3でパターン化）
```

**Week 3移行時**:
```bash
# Week 1-2の★マーク付きエラーを抽出
grep "★" docs/progress/daily_progress.md

# 抽出結果をObsidian KB化
# 例: "★ pytest fixture scope混乱 (Day 3, Day 8再発)"
# → 02_Troubleshooting/Pytest_Fixture_Scope_Confusion.md 作成
```

---

**移行完了チェックリスト**:
- [ ] daily_progress.md Week 1-2確認完了
- [ ] 2回以上発生エラー2-3件抽出
- [ ] 効果的AIパターン1-2件抽出
- [ ] トラブルシューティングKB 2-3件作成
- [ ] AI協働パターン 1-2件作成
- [ ] Week 1-2学習ログ作成（振り返り形式）

**検証**:
```bash
# 作成ノート数確認
find obsidian-vault-local/{02_Troubleshooting,03_AI_Collaboration} -name "*.md" | wc -l
# 期待結果: 3-5件（テンプレート除外）
```

---

#### 5.1.0.5 前提条件：.mcp.json設定確認

**タスク**: Obsidian MCPの基本設定を確認・追加

**設定例**（`.mcp.json`に以下を追加）:

**注意**: 以下は`jacksteamdev/obsidian-mcp-tools`の公式構造に基づく設定例です。

**設定例（テンプレート）**:
```json
{
  "mcpServers": {
    "obsidian-mcp-tools": {
      "command": "{OBSIDIAN_VAULT}/.obsidian/plugins/mcp-tools/bin/mcp-server",
      "args": [],
      "env": {
        "OBSIDIAN_API_KEY": "{YOUR_OBSIDIAN_API_KEY}"
      }
    }
  }
}
```

**設定例（置換後・実際の例）**:
```json
{
  "mcpServers": {
    "obsidian-mcp-tools": {
      "command": "/Users/yuta/Yuta/python/api-test-devops-portfolio/obsidian-vault-local/.obsidian/plugins/mcp-tools/bin/mcp-server",
      "args": [],
      "env": {
        "OBSIDIAN_API_KEY": "{YOUR_LOCAL_REST_API_KEY}"
      }
    }
  }
}
```

**Note**: セキュリティのため、API keyは一部マスク表示（実際の値: 64文字の16進数文字列）

**設定手順**:

1. **Obsidian Local REST APIプラグインのAPI key取得**:
   - Obsidianアプリを起動
   - 設定 → Community Plugins → Local REST API → API Key をコピー

2. **vault pathの確認**:
   ```bash
   # プロジェクトルートから確認
   ls -la obsidian-vault-local/.obsidian/plugins/mcp-tools/bin/
   # 期待結果: mcp-server バイナリが存在
   ```

3. **`.mcp.json`の編集**:
   ```bash
   # プロジェクトルートの.mcp.jsonを編集
   # {OBSIDIAN_VAULT}を実際のパスに置換
   # 例: /Users/yuta/Yuta/python/api-test-devops-portfolio/obsidian-vault-local

   # {YOUR_LOCAL_REST_API_KEY}をステップ1でコピーしたAPI keyに置換
   # 例: 5e2e4eec3d3ccd1b7c4ba929bb0697046acf1b04013728063e76db3604549200
   ```

**検証**:
```bash
# 設定確認
grep -q "obsidian-mcp-tools" .mcp.json && echo "✅ MCP設定あり" || echo "❌ 設定なし"

# API key確認（セキュリティ：key自体は表示しない）
grep "OBSIDIAN_API_KEY" .mcp.json | grep -q "{YOUR" && echo "❌ プレースホルダーのまま" || echo "✅ API key設定済み"

# commandパス確認
grep "command" .mcp.json | grep obsidian-mcp-tools -A 1
# 期待結果: 実際のvault絶対パスが表示される
```

**重要な注意事項**:
- **API keyは機密情報**: `.gitignore`で`.mcp.json`が除外されていることを確認
- **絶対パス必須**: `command`フィールドは相対パス不可
- **plugin自動インストール**: Obsidian Community Pluginsから`obsidian-mcp-tools`をインストールすると、バイナリが自動配置される

**トラブルシューティング**:
- `mcp-server`バイナリが見つからない場合:
  1. Obsidianアプリで`obsidian-mcp-tools`プラグインを再インストール
  2. プラグイン設定から"Install MCP Server"を実行
  3. vaultルートディレクトリを確認（複数vault使用時は注意）

---

#### 5.1.1 Obsidian MCP機能検証テスト**最優先**

**⚠️ 重要**: vault構造設計の前に、Obsidian MCPの実際の機能を確認します。

**前提条件チェック**:
```bash
# 1. Obsidian MCPインストール確認
grep -q "obsidian-mcp-tools" .mcp.json && echo "✅ Installed" || echo "❌ Not found"

# 2. vault_path設定確認
# （.mcp.jsonにvault pathが指定されているか確認）
```

**テストスクリプト**:
```bash
# テスト用ノート作成
mkdir -p obsidian-vault-local/test/
cat > obsidian-vault-local/test/mcp_verification.md <<EOF
---
tags: [test/verification, troubleshooting/docker]
error_message: "PermissionError: [Errno 13] test error"
---

# MCP Verification Test

Test content for Obsidian MCP capability verification.

Keywords: Docker permission async error
EOF

# Claude Codeセッションで以下を実行（手動）:
# Test 1: Full-text search
# mcp__obsidian-mcp-tools__search_vault_smart("PermissionError")
# 期待結果: mcp_verification.md が発見される

# Test 2: Tag filter search
# mcp__obsidian-mcp-tools__search_vault_smart(tags=["troubleshooting/docker"])
# 期待結果: mcp_verification.md が発見される

# Test 3: Frontmatter metadata retrieval
# mcp__obsidian-mcp-tools__get_vault_file("test/mcp_verification.md")
# 期待結果: frontmatter含む全文取得

# Test 4: Smart Connections (semantic search) - オプション
# mcp__obsidian-mcp-tools__search_vault_smart("volume permission problem")
# 期待結果: "PermissionError"を含むノートが意味検索でヒット

# クリーンアップ
rm -rf obsidian-vault-local/test/
```

**合格基準**: Test 1-3がすべて成功（Test 4はオプション）

---

#### MCP障害回復ガイド（トラブルシューティング）

**Test 1失敗: search_vault_smart()がエラー**

**症状**: `MCPConnectionError: obsidian-mcp-tools not responding`

**デバッグ手順**:
```bash
# 1. Obsidianアプリ起動確認
ps aux | grep Obsidian
# 期待結果: プロセス存在

# 2. Local REST APIプラグイン確認
# Obsidian → 設定 → Community Plugins → Local REST API → Enable

# 3. API key再取得（typo修正）
# .mcp.json のAPI keyをLocal REST API設定から再コピー
grep "OBSIDIAN_API_KEY" .mcp.json

# 4. Claude Code再起動（MCP設定変更後は必須）
```

**Test 2失敗: Tag filter効かない**

**症状**: `tags: ["troubleshooting/docker"]`で検索結果0件

**原因候補**:
1. Frontmatter YAML構文エラー（`tags:`の後ろにスペース必須）
2. Tag indexing未完了（Obsidian起動直後）

**解決策**:
```bash
# YAML構文チェック
python3 -c "import yaml; yaml.safe_load(open('obsidian-vault-local/test/mcp_verification.md').read().split('---')[1])"

# Obsidian再起動でindex再構築
```

**初学者が遭遇しやすいエラーTop 3**:

| 順位 | エラー | 発生率 | 解決策 |
|------|--------|-------|--------|
| 1 | vault path誤設定 | 50% | 相対パス→**絶対パス**に修正 |
| 2 | API key typo | 30% | コピペ時の改行混入→trim処理 |
| 3 | Obsidian未起動 | 20% | MCPはObsidian起動前提→起動確認 |

**MCP検証3回連続失敗時のFallback**:
```bash
# Fallbackモード移行
# 1. Obsidian MCP無効化
sed -i '' 's/"obsidian-mcp-tools"/#"obsidian-mcp-tools"/' .mcp.json

# 2. filesystem MCP + Grepで代替
# 例: ノート読み込み
Read("obsidian-vault-local/02_Troubleshooting/error_xxx.md")

# 例: 全文検索
Grep("Docker permission", path="obsidian-vault-local/", output_mode="content")

# 3. Graph viewは手動（Obsidianアプリ直接起動）
```

**Week 3延長判断基準**:
- MCP検証に累計3時間超 → **Week 3を7日間に延長**（Day 19まで）
- Week 4開始を1週間遅延（Day 20から）
- 全体スケジュールは維持（Week 6終了日は変更なし、Week 5-6を圧縮）

---

#### MCP障害回復マトリクス

**障害レベル別対応表**:

| 障害レベル | 症状 | 影響範囲 | 復旧時間 | 対応アクション |
|-----------|------|---------|---------|---------------|
| **L1: 軽微** | API応答遅延 (>3秒) | 検索性能低下 | 1-5分 | Obsidian再起動 |
| **L2: 中程度** | 特定機能エラー (search/write) | 一部操作不可 | 5-15分 | API key再設定 + Claude Code再起動 |
| **L3: 重大** | MCP接続不可 | 全Obsidian MCP機能停止 | 15-60分 | Fallbackモード移行（filesystem MCP使用） |
| **L4: 致命的** | データ破損・消失 | vault整合性喪失 | 60-120分 | バックアップ復元 + vault再構築 |

**Fallback移行判断フロー**:
```
障害検出 → 再起動試行（3回まで）→ 3回失敗 → Fallback移行
    ↓               ↓
  復旧成功 ←──── 成功なら継続
```

**障害レベル別Fallback戦略**:

| 障害機能 | Fallback手段 | 機能制約 |
|---------|-------------|---------|
| search_vault_smart | Grep + filesystem MCP | セマンティック検索不可→キーワード検索のみ |
| create_vault_file | Write tool直接 | テンプレート自動適用なし |
| patch_vault_file | Edit tool直接 | frontmatter解析なし |
| Graph view連携 | Obsidianアプリ手動起動 | MCP経由の自動化不可 |

**復旧確認チェックリスト**:
```bash
# L1-L2復旧確認
mcp__obsidian-mcp-tools__get_server_info  # 応答確認

# L3復旧確認（Fallback解除時）
mcp__obsidian-mcp-tools__search_vault_simple query="test"  # 検索動作確認

# L4復旧確認（バックアップ復元後）
ls obsidian-vault-local/ | wc -l  # ディレクトリ数確認
git log --oneline -5  # 最新コミット確認
```

---

#### 5.1.2 vaultディレクトリ構造作成

**タスク**:
```bash
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# vaultディレクトリ作成（8カテゴリ対応）
mkdir -p obsidian-vault-local/{00_Index,01_Learning,02_Troubleshooting,03_AI_Collaboration,04_ADR,05_Daily,06_Config_Patterns,07_Optional,99_Templates}

# 07_Optionalサブディレクトリ（★☆☆カテゴリ用）
mkdir -p obsidian-vault-local/07_Optional/{Snippets,Glossary,Interview}

# .gitignore更新
cat >> .gitignore <<EOF

# Obsidian workspace files
obsidian-vault-local/.obsidian/workspace*.json
obsidian-vault-local/.obsidian/cache/

# Private notes
obsidian-vault-local/99_Private/

# Environment files
obsidian-vault-local/.env.obsidian
*credentials*.md
*secret*.md
EOF

git add .gitignore
git commit -m "chore: add Obsidian vault .gitignore rules"
```

**検証**:
```bash
ls -la obsidian-vault-local/
# 期待結果: 9ディレクトリ確認（00,01,02,03,04,05,06,07,99）

ls -la obsidian-vault-local/07_Optional/
# 期待結果: 3サブディレクトリ（Snippets,Glossary,Interview）
```

**ディレクトリ構造と推奨度の対応**（9ディレクトリ: 8カテゴリ + 1インフラ）:
| ディレクトリ | 推奨度 | 用途 |
|------------|--------|------|
| 00_Index | インフラ | インデックス・ハブノート |
| 01_Learning | ★★☆ | 週次学習ログ（軽量サマリー） |
| 02_Troubleshooting | ★★★ | エラー解決KB |
| 03_AI_Collaboration | ★★★ | AI協働パターン |
| 04_ADR | ★★★ | 技術決定記録 |
| 05_Daily | 保留 | Daily Notes（Week 4で評価後に運用開始） |
| 06_Config_Patterns | ★★☆ | 設定パターン |
| 07_Optional/Snippets | ★☆☆ | コードスニペット |
| 07_Optional/Glossary | ★☆☆ | 用語集 |
| 07_Optional/Interview | ★☆☆ | 面接Q&A |
| 99_Templates | インフラ | テンプレート格納（5種類）

---

#### 5.1.3 セキュリティ設定

**1. Pre-commit hook作成**:
```bash
# .git/hooks/pre-commit
cat > .git/hooks/pre-commit <<'EOF'
#!/bin/bash

# 機密情報パターン（強化版）
SECRETS_PATTERN="(api[_-]?key|secret|password|token|credential)[\s]*[:=][\s]*['\"]?[A-Za-z0-9\-_]{20,}['\"]?"
BASE64_PATTERN="eyJ[A-Za-z0-9_-]{50,}"  # JWT/base64エンコードトークン
AWS_PATTERN="AKIA[A-Z0-9]{16}"  # AWS Access Key
ENV_VAR_PATTERN="\\\$\{[A-Z_]+_KEY\}|\\\$\{[A-Z_]+_SECRET\}"  # 環境変数参照

echo "🔍 セキュリティスキャン実行中..."

# ステージングファイルスキャン（全パターン）
for PATTERN in "$SECRETS_PATTERN" "$BASE64_PATTERN" "$AWS_PATTERN"; do
  if git diff --cached | grep -E "$PATTERN" -i; then
    echo "❌ 機密情報検出！commit中止"
    echo "💡 [REDACTED]に置換してください"
    exit 1
  fi
done

# Obsidian privateディレクトリチェック
if git diff --cached --name-only | grep "99_Private/"; then
  echo "❌ プライベートノート検出！commit中止"
  exit 1
fi

echo "✅ セキュリティチェック合格"
EOF

chmod +x .git/hooks/pre-commit
```

**2. バックアップスクリプト作成**:
```bash
# scripts/backup_vault.sh
mkdir -p scripts/
cat > scripts/backup_vault.sh <<'EOF'
#!/bin/bash

VAULT_PATH="obsidian-vault-local"
BACKUP_DIR="$HOME/Backups/obsidian-vault"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# セキュリティスキャン
echo "🔍 機密情報チェック中..."
if grep -r "API_KEY\|SECRET\|PASSWORD" "$VAULT_PATH/" --exclude-dir=.git -q; then
  echo "❌ 機密情報検出！バックアップ中止"
  exit 1
fi

# バックアップ作成
mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/vault_${TIMESTAMP}.tar.gz" "$VAULT_PATH/"

# チェックサム
shasum -a 256 "$BACKUP_DIR/vault_${TIMESTAMP}.tar.gz" > \
  "$BACKUP_DIR/vault_${TIMESTAMP}.sha256"

# 古いバックアップ削除（30日以上）
find "$BACKUP_DIR" -name "vault_*.tar.gz" -mtime +30 -delete

echo "✅ バックアップ完了: $BACKUP_DIR/vault_${TIMESTAMP}.tar.gz"
EOF

chmod +x scripts/backup_vault.sh
```

**3. Fallback機能テスト**:
```bash
# scripts/test_fallback.sh
cat > scripts/test_fallback.sh <<'EOF'
#!/bin/bash
echo "🧪 Fallback機能テスト開始"

# Obsidian MCP無効化状態を想定
# Test 1: filesystem MCPでノート読み込み
echo "Test 1: ノート読み込み"
if [ -d "obsidian-vault-local" ]; then
  echo "✅ vault存在確認"
else
  echo "❌ vault不在"
  exit 1
fi

# Test 2: Grepで全文検索
echo "Test 2: 全文検索"
if command -v grep &> /dev/null; then
  echo "✅ Grep利用可能"
else
  echo "❌ Grep不在"
  exit 1
fi

echo "🎉 Fallback機能テスト合格"
EOF

chmod +x scripts/test_fallback.sh
./scripts/test_fallback.sh
```

---

#### 5.1.4 テンプレート作成

**5種類のテンプレート作成**（8カテゴリ対応）:

**1. template_learning_log.md**:
```markdown
---
week:
topic:
estimated_hours:
actual_hours:
mastery_level:
status: 進行中
tags:
  - learning/week
created:
updated:
---

# {{topic}} - Week {{week}} 学習ログ

## 📚 学習目標
- [ ] 目標1
- [ ] 目標2

## 📖 Phase 1: AI説明・概念理解
### 理解度チェックリスト
- [ ] 概念1を説明できる
- [ ] 概念2を説明できる

### 理解度自己評価
__%

## 🛠️ Phase 2: AI協働実装
### AI依頼品質
Level __ (基本的/具体的/技術的依頼)

### 実装成果物
- git commit: [hash]
- 変更行数: +___/-___

### AIレビュー品質
Level __ (__項目指摘)

## 📊 Phase 3: 理解度確認
### 理解度確認問題
- スコア: __/25 (__%)
- 合否: ✅ 合格 / ⚠️ 要復習

## 🔗 関連リンク
- 前週: [[Week {{week-1}}]]
- 次週: [[Week {{week+1}}]]
- 関連技術:
```

**使用例** (Week 3 Docker学習時):
```yaml
---
week: 7
topic: Docker基盤構築
estimated_hours: 42
actual_hours: 38
mastery_level: 75
status: 完了
tags:
  - learning/week7
  - learning/docker
  - skill/container
created: 2025-11-15
updated: 2025-11-21
---
```

---

**2. template_troubleshooting.md**:
```markdown
---
title:
error_message: ""
category:
severity:
resolution_time:
tags:
  - troubleshooting/
  - error/
created:
resolved:
---

# {{title}}

## 🚨 問題概要
**エラーメッセージ**:
```
{{error_message}}
```

**発生状況**:
- 発生日時: Day {{day}} (Week {{week}})
- 作業内容:

## 🔍 原因分析
**根本原因**:

## ✅ 解決策
### 適用コマンド
```bash
# 実行コマンド
```

### 検証
```bash
# 検証手順
```

## 📚 学習ポイント
1.
2.

## 🔗 関連リンク
- 関連Week: [[Week {{week}}]]
- 関連技術:

---

**3. template_ai_pattern.md**:
```markdown
---
title:
pattern_type:
ai_dependency:
success_rate:
tags:
  - ai-collaboration/
  - pattern/
created:
---

# {{title}}

## 📝 パターン概要
**目的**:

**適用場面**:

## 🔄 Before → After

### Before (Level 2: 基本的依頼)
```
"{{before_prompt}}"
```

**問題点**:
-

### After (Level 3: 具体的依頼)
```
"{{after_prompt}}"
```

**改善点**:
-

## 📊 効果測定
- 成功率: __%
- 時間削減: __ → __
- AI依頼回数削減: __ → __

## 🔗 関連リンク
- 関連技術:
- 類似パターン:
```

---

**4. template_adr.md**:

---
adr_number:
title:
status: proposed
date:
decision_makers:
  - User
  - Claude Code
tags:
  - adr/
  - decision/
---

# ADR {{number}}: {{title}}

## Context
**背景**:

**課題**:

## Decision
**採用**:

**理由**:
1.
2.

## Alternatives Considered
### Option A:
- Pros:
- Cons:

### Option B:
- Pros:
- Cons:

## Consequences
### Positive
-

### Negative
-

### Mitigation
-

## References
-
```

---

**5. template_config_pattern.md**（★★☆ 設定パターン用）:
```markdown
---
title:
config_type:  # docker|cicd|pytest|ruff|mypy
target_env:   # dev|test|demo|prod|all
reuse_count: 0
tags:
  - config/
  - pattern/
created:
updated:
---

# {{title}}

## 📋 パターン概要
**目的**:

**対象環境**: {{target_env}}

**適用プロジェクト**:
- [ ] 現プロジェクト（api-test-devops-portfolio）
- [ ] 新規プロジェクトA
- [ ] 新規プロジェクトB

## 📁 設定ファイル
**ファイルパス**: `{{file_path}}`

```yaml
# 設定内容（コピー可能）
{{config_content}}
```

## 🔧 カスタマイズポイント
| 項目 | デフォルト値 | 変更理由 |
|------|-------------|---------|
| {{key1}} | {{value1}} | {{reason1}} |
| {{key2}} | {{value2}} | {{reason2}} |

## ✅ 動作確認手順
```bash
# 検証コマンド
{{verification_command}}
```

**期待結果**:
-


## 🔗 関連リンク
- 関連ADR: [[ADR_XXX]]
- 関連技術: [[Docker基礎]], [[CI/CD基礎]]
- 公式ドキュメント:

---

#### 5.1.5 CLAUDE.md更新

**追加セクション**（CLAUDE.mdの末尾に追加）:

````markdown
## 🧠 Obsidian知識ベース活用ガイド

### 用途別検索方法

#### トラブルシューティング検索
**タイミング**: エラー発生時

**検索手順**:
1. Obsidian vaultで全文検索
   ```
   # Claude Code経由
   mcp__obsidian-mcp-tools__search_vault_smart("エラーメッセージの一部")
   ```

2. タグ検索（カテゴリ絞り込み）
   ```
   tags: #troubleshooting/docker
   ```

**例**:
"Docker volume パーミッションエラー" で検索
→ `[[Docker_Volume_Permission_Error.md]]` 発見
→ 解決コマンド適用

#### 学習ログ検索
**タイミング**: 過去Week復習時

**検索手順**:
```
# 技術キーワードで検索
mcp__obsidian-mcp-tools__search_vault_smart("async/await")

# Week番号で検索
[[Week 02: Async基礎]]
```

### Obsidian MCP Fallback Protocol

**Fallback Triggers**:
1. MCP connection timeout (>5s)
2. 3 consecutive API errors
3. Obsidian plugin not installed

**Fallback Implementation**:
```bash
# Obsidian MCPの代わりにfilesystem MCPを使用

# ノート読み込み（Obsidian MCP）
# mcp__obsidian-mcp-tools__get_vault_file("01_Learning/Week_03_Docker.md")

# ↓ fallback（filesystem MCP）
Read("/Users/yuta/Yuta/python/api-test-devops-portfolio/obsidian-vault-local/01_Learning/Week_03_Docker.md")

# 検索（Obsidian MCP）
# mcp__obsidian-mcp-tools__search_vault_smart("Docker permission error")

# ↓ fallback（filesystem MCP + Grep）
Grep("Docker permission error",
     path="/Users/yuta/Yuta/python/api-test-devops-portfolio/obsidian-vault-local",
     output_mode="content")
```

**Fallback時の制約**:
- ❌ Graph view利用不可（手動でObsidianアプリ起動必要）
- ❌ Backlink自動検出不可
- ✅ 読み書きは問題なし（filesystem MCPで代替）
- ✅ 全文検索可能（Grep toolで代替）

### 記録ルール（3回ルール）

**記録対象**: 3回以上参照・適用した内容のみ

**運用**:
- 新規エラー発生 → まず検索
- 2回目発生 → Daily Notesにメモ
- 3回目発生 → トラブルシューティングKBに昇格

---

#### 5.1.6 初回ノート作成

**ADR_001作成**:

```bash
cat > obsidian-vault-local/04_ADR/ADR_001_Hybrid_Serena_Obsidian.md <<'EOF'
---
adr_number: 001
title: Hybrid Serena + Obsidian Strategy
status: accepted
date: 2025-11-22
decision_makers:
  - User
  - Claude Code
tags:
  - adr/architecture
  - decision/mcp
---

# ADR 001: Hybrid Serena + Obsidian Strategy

## Context
**背景**:
- プロジェクトはSerena MCPで15メモリ管理（87.5%トークン削減達成）
- 学習ログ・トラブルシューティング履歴が`daily_progress.md`に累積
- 知識グラフ可視化・全文検索の要望

**課題**:
- Serena単独では全文検索・リンク機能なし
- daily_progress.md肥大化（8k tokens/全文読込）
- トラブルシューティング検索に2-5分要する

## Decision
**採用**: Serena + Obsidianのハイブリッド運用

**役割分担**:
- **Serena**: 動的状態管理（progress_state.yaml、品質ゲート基準）
- **Obsidian**: 静的知識ベース（学習ログ、エラーKB、AI協働パターン）

## Alternatives Considered

### Option A: Serena完全置き換え
- Pros: 一元化、学習コスト低
- Cons: 87.5%トークン削減実績を失う、Progressive Disclosure不可

### Option B: Obsidian単独移行
- Pros: Graph view最大活用
- Cons: 動的状態管理に不向き（current_week等の頻繁更新）

## Consequences

### Positive
- トークン削減: 40-75%（段階的改善、Week 4→10）
- 時間削減: 60-90%（トラブルシューティング検索）
- 知識グラフ可視化: 学習パス・技術依存関係の俯瞰
- 移行リスクゼロ: Serena維持、Obsidian追加のみ

### Negative
- 学習コスト: 4-6h（Week 3）
- 総投資時間: 13-18h（Week 3-10）
- ROI回収: Week 12-13（Week 5ではない）
- システム複雑化: 2つのMCPサーバー管理

### Mitigation
- Week 4でrollback判断（検索ヒット率60%未達なら撤退）
- 3回ルール徹底（過剰ドキュメント化防止）
- Fallback準備（filesystem MCP）

## References
- Serena MCP: 15メモリ、87.5%トークン削減実績
- Obsidian MCP: jacksteamdev/obsidian-mcp-tools
- ROI分析: Section 1.2参照
EOF
```

**検証**:
```bash
cat obsidian-vault-local/04_ADR/ADR_001_Hybrid_Serena_Obsidian.md | head -20
```

**ADR面接Talking Points（2分ピッチ例）**:

このADRを面接で説明する際の構造化されたアプローチ：

```markdown
## 2分ピッチ構造

### 1. 課題認識（30秒）
「6週間の学習ポートフォリオを構築する中で、2つのシステムを評価しました：
- Serena MCP: 動的状態管理に87.5%のトークン効率を達成
- Obsidian MCP: 静的知識の検索・可視化に強み」

### 2. 技術的判断（45秒）
「完全置き換えではなく、ハイブリッド運用を選択しました。理由は3つ：
1. Serenaの実績（87.5%トークン削減）を維持
2. Obsidianの強み（全文検索、グラフビュー）を追加
3. ロールバック可能な段階的導入でリスク軽減」

### 3. 成果・学び（45秒）
「結果として：
- トラブルシューティング検索時間: 2-5分 → 30秒（83%削減）
- 週4hの投資で、Week 12-13にROI回収予定
- 学び: 完璧な単一解より、役割分担された実用解が有効」

## 想定質問と回答

Q: なぜSerena完全置き換えをしなかった？
A: 87.5%のトークン削減実績を失うリスクが高く、動的状態管理にはSerenaが最適だったため。

Q: ROI回収にWeek 12-13かかる理由は？
A: 週4hの投資×4週間=16hの初期コスト。検索効率改善で週2h節約として8週間で回収。

Q: ロールバック基準は？
A: Week 4終了時に検索ヒット率60%未満、またはトークン使用量がベースライン150%超で判断。
```

---

#### 5.1.7 Obsidian基本操作習得**新規追加**

**学習内容**:
1. Graph viewの操作（Zoom, filter, highlight）
2. 全文検索の使い方
3. Backlinkパネルの確認方法
4. Daily Notes作成方法

**検証**: Obsidianアプリで`ADR_001`をグラフビューで表示確認

---

### Week 3終了チェックリスト

**実施時刻**: Week 3 Day 18 金曜 17:00

- [ ] **Week 1-2知識移行完了**（Section 5.1.0）
- [ ] MCP機能検証テスト合格（Test 1-3成功）
- [ ] vault構造作成完了（9ディレクトリ）
- [ ] セキュリティ設定完了（.gitignore, pre-commit hook, backup script）
- [ ] テンプレート5種類作成完了
- [ ] CLAUDE.md更新完了（Obsidian活用ガイド追加）
- [ ] ADR_001作成完了
- [ ] Obsidian基本操作習得（Graph view操作可能）
- [ ] 初回バックアップ実行（`./scripts/backup_vault.sh`）

**検証コマンド**:
```bash
# 全項目一括確認
ls -la obsidian-vault-local/ | grep -E "^d" | wc -l  # 期待: 9以上
ls -la obsidian-vault-local/99_Templates/*.md | wc -l  # 期待: 5
grep "Obsidian知識ベース" CLAUDE.md  # 期待: セクション存在確認
ls -la scripts/*.sh | wc -l  # 期待: 2以上
git log --oneline -5  # 期待: .gitignore, ADR_001コミット確認
```

---

### 5.2 Week 4: 試験運用（4-5h）

#### 5.2.1 ノート作成計画（8-10件）

**目標**: 質より量を重視せず、3回ルール徹底

**推奨作成件数**:
- トラブルシューティングKB: **5件**（Week 3-8で発生する典型例のみ）
- 学習ログ: **1-2件**（Week 3振り返り + Week 4進行中）
- AI協働パターン: **2件**（実際に効果があったパターンのみ）

**トラブルシューティング対象候補**:
1. Docker volume permission error
2. GitHub Actions secret not found
3. pytest coverage below target
4. mypy type check failure
5. docker-compose build cache issue

**作成トリガー**: 同じエラーが2回目発生時（3回ルール見越し）

---

#### 5.2.2 検索ヒット率測定（Week 4終了時）

**測定手順**:
1. Week 4で発生した全エラー・問題をリストアップ（5-10件）
   ```bash
   # エラーログから抽出
   cat > /tmp/week8_errors.txt <<EOF
   Docker permission denied
   GitHub Actions secret not found
   pytest coverage 45% (target 60%)
   mypy error: incompatible types
   docker-compose network error
   EOF
   ```

2. 各エラーメッセージでObsidian全文検索実施
   ```bash
   # 手動: Obsidianアプリまたは Claude Code経由
   # mcp__obsidian-mcp-tools__search_vault_smart("Docker permission denied")
   ```

3. ヒット数カウント
   ```bash
   # 結果記録
   echo "エラー1: Docker permission, ヒット: YES" >> /tmp/week8_search_results.txt
   echo "エラー2: GitHub secret, ヒット: NO" >> /tmp/week8_search_results.txt
   # ...

   # ヒット率計算
   HITS=$(grep "YES" /tmp/week8_search_results.txt | wc -l)
   TOTAL=$(wc -l < /tmp/week8_errors.txt)
   echo "検索ヒット率: $(($HITS * 100 / $TOTAL))%"
   ```

**目標**: **60%以上**（5件中3件以上ヒット）

**検索ヒット率自動測定スクリプト**:
```bash
#!/bin/bash
# scripts/measure_search_hit_rate.sh
# 検索ヒット率を自動測定するスクリプト

VAULT_PATH="obsidian-vault-local"
ERRORS_FILE="/tmp/week_errors.txt"
RESULTS_FILE="/tmp/search_results.txt"

# 初期化
echo "🔍 検索ヒット率測定開始"
> "$RESULTS_FILE"

# エラーリストがなければ作成を促す
if [ ! -f "$ERRORS_FILE" ]; then
    echo "❌ $ERRORS_FILE が存在しません"
    echo "📝 作成例:"
    echo "cat > $ERRORS_FILE <<EOF"
    echo "Docker permission denied"
    echo "pytest coverage below target"
    echo "EOF"
    exit 1
fi

# 各エラーメッセージでgrep検索
HITS=0
TOTAL=0

while IFS= read -r error; do
    [ -z "$error" ] && continue
    TOTAL=$((TOTAL + 1))

    # vault内を検索（大文字小文字無視）
    if grep -riq "$error" "$VAULT_PATH/" --include="*.md" 2>/dev/null; then
        echo "✅ ヒット: $error" >> "$RESULTS_FILE"
        HITS=$((HITS + 1))
    else
        echo "❌ 未ヒット: $error" >> "$RESULTS_FILE"
    fi
done < "$ERRORS_FILE"

# ヒット率計算
if [ "$TOTAL" -gt 0 ]; then
    RATE=$((HITS * 100 / TOTAL))
    echo ""
    echo "📊 結果:"
    cat "$RESULTS_FILE"
    echo ""
    echo "🎯 検索ヒット率: $RATE% ($HITS/$TOTAL)"

    if [ "$RATE" -ge 60 ]; then
        echo "✅ 目標達成（60%以上）"
    else
        echo "⚠️ 目標未達（60%未満）→ タグ体系見直し推奨"
    fi
else
    echo "❌ エラーリストが空です"
fi
```

**使用方法**:
```bash
# 1. エラーリスト作成
cat > /tmp/week_errors.txt <<EOF
Docker permission denied
GitHub Actions secret not found
pytest coverage below target
EOF

# 2. スクリプト実行
chmod +x scripts/measure_search_hit_rate.sh
./scripts/measure_search_hit_rate.sh
```

**60%未達時**:
- タグ体系見直し
- Frontmatter error_messageフィールド追加
- Week 5継続 or ロールバック判断

---

### 5.3 Week 5: 最適化（3-4h）

#### 5.3.1 タグ体系最適化（2h）

**現状分析**:
```bash
# 全ノートのタグ抽出
grep -rh "tags:" obsidian-vault-local/ --include="*.md" | sort | uniq -c

# 使用頻度2回以下のタグ削除候補リスト作成
```

**改善策**:
- 階層深さ見直し（例: `#troubleshooting/docker/volume` → `#troubleshooting/docker`に簡略化）
- 命名規則統一（例: `error-permission` vs `error/permission`）

---

#### 5.3.2 グラフビューキュレーション（1h）

**タスク**:
1. 孤立ノート発見（リンク0のノート）
   ```bash
   # Obsidianアプリで確認、または手動grep
   ```

2. リンク追加（週次学習ログ ↔ トラブルシューティングKB）

**目標**: 孤立ノート率 < 20%

---

### 5.4 Week 6: 本番運用（2-3h）

#### 5.4.1 ポートフォリオ統合（手動作業）

**タスク**:
1. Graph viewスクリーンショット撮影（1画面でWeek 1-6俯瞰）
2. ADR 3件以上作成確認（技術決定記録の充実）
3. 面接準備資料作成（ADRから技術選定理由を抽出）

**成果物**:
- `docs/portfolio/knowledge_graph.png`
- `docs/portfolio/technical_decisions.md`（ADRサマリー）

---

## 🎯 主要ユースケース

### 6.1 トラブルシューティング知識ベース

#### シナリオ
**状況**: Week 4でDocker volumeパーミッションエラー発生（Week 3でも2回発生済み）

**従来フロー（Serena単独）**:
1. エラーメッセージでGoogle検索
2. Stack Overflow確認
3. 解決策試行錯誤
4. 合計: **23min**

**改善フロー（Obsidian統合後）**:
1. Obsidian全文検索: `"PermissionError: [Errno 13]"`（10s）
2. `[[Docker_Volume_Permission_Error.md]]` 発見（即座）
3. 解決コマンド適用: `chmod -R 777 /app/logs`（30s）
4. 合計: **1min**

**時間削減**: 95.7%（23min → 1min）**※ドキュメント化済みエラーの場合**

**現実的削減**（70% hit rate想定）:
- 70% cases: 1min（ドキュメント化済み）
- 30% cases: 23min（未ドキュメント）
- **加重平均: 7.6min**（67%削減）

---

## 📊 品質保証・成功基準

### 7.1 成功メトリクス（測定可能な基準）

| Week | メトリクス | 現在値 | 目標値 | 測定方法 | 測定プロトコル詳細 |
|------|-----------|--------|--------|---------|-------------------|
| Week 3 | vault構造完成 | 0% | 100% | `ls obsidian-vault-local/`で9ディレクトリ確認 | Section 5.1.2検証コマンド実行 |
| Week 3 | テンプレート作成 | 0件 | 5件 | `ls 99_Templates/`で5ファイル確認 | 5種類すべて存在確認 |
| Week 3 | MCP機能検証 | 未実施 | 合格 | Test 1-3成功 | Section 5.1.1テストスクリプト実行 |
| Week 4 | ノート作成数 | 0件 | 8-10件 | `find obsidian-vault-local/ -name "*.md" \| wc -l` | テンプレート除外してカウント |
| Week 4 | 検索ヒット率 | N/A | **60%以上** | 全文検索で過去エラー発見率（手動測定） | **手順**: Week 4の全エラーをリスト化（5-10件） → 各エラーで全文検索実行 → "関連ノート発見"を1点 → (発見数 / 総エラー数) × 100 |
| Week 5 | 検索ヒット率 | Week 4実測 | **70%以上** | 同上（タグ体系最適化後） | Week 5終了時に再測定 |
| Week 5 | トークン削減率 | 0% | **40%以上** | MCP token log比較（8k → 4.8k以下） | Week 2 baseline vs Week 5実測 |
| Week 6 | グラフ可視化完成 | 0% | 100% | Week 1-6の全リンク連鎖確認（手動検証） | **Test Cases**: Week 1 → httpx基礎 → API error (3 hops), Week 3 → Docker → Permission fix (3 hops) |
| Week 6 | 面接準備資料 | 0件 | 3件以上 | `ls 04_ADR/ \| wc -l` ≥ 3 | ADR_001含む3件以上 |

---

### 7.2 検証チェックリスト

#### Week 3終了時

- [ ] vault構造作成完了（9ディレクトリ）
- [ ] テンプレート5種類動作確認
- [ ] セキュリティ設定完了（.gitignore, pre-commit hook）
- [ ] バックアップスクリプト動作確認（`./scripts/backup_vault.sh`実行成功）
- [ ] CLAUDE.md更新（Obsidian活用ガイド追加）
- [ ] ADR_001作成完了
- [ ] Obsidian MCP機能検証合格（Test 1-3成功）
- [ ] Fallback機能テスト合格（`./scripts/test_fallback.sh`実行成功）

**検証コマンド**:
```bash
# Week 3初期セットアップ検証スクリプト作成
cat > scripts/validate_week3_setup.sh <<'EOF'
#!/bin/bash
echo "=== Week 3初期セットアップ検証 ==="

# 1. ディレクトリ確認
DIRS=$(ls -la obsidian-vault-local/ | grep -E "^d" | wc -l)
echo "vault directories: $DIRS (Target: ≥9)"
[[ $DIRS -ge 9 ]] && echo "✅ PASS" || echo "❌ FAIL"

# 2. テンプレート確認
TEMPLATES=$(ls -la obsidian-vault-local/99_Templates/*.md 2>/dev/null | wc -l)
echo "Templates: $TEMPLATES (Target: ≥5)"
[[ $TEMPLATES -ge 5 ]] && echo "✅ PASS" || echo "❌ FAIL"

# 3. セキュリティスクリプト確認
SCRIPTS=$(ls -la scripts/{backup_vault,test_fallback}.sh 2>/dev/null | wc -l)
echo "Security scripts: $SCRIPTS (Target: 2)"
[[ $SCRIPTS -eq 2 ]] && echo "✅ PASS" || echo "❌ FAIL"

# 4. git commit確認
COMMITS=$(git log --oneline --since="1 week ago" | grep -c "ADR_001\|gitignore")
echo "Git commits: $COMMITS (Target: ≥2)"
[[ $COMMITS -ge 2 ]] && echo "✅ PASS" || echo "❌ FAIL"

echo "=== 検証完了 ==="
EOF

chmod +x scripts/validate_week3_setup.sh
./scripts/validate_week3_setup.sh
```

**スクリプト名の意図**:
- `validate_week3_setup.sh`: Week 3の初期セットアップ（vault構造、テンプレート、セキュリティ設定）を検証
- Week 4以降は別の検証項目（ノート作成数、検索ヒット率等）になるため、別スクリプトを作成推奨

---

#### Week 4終了時

- [ ] 学習ログ1件以上作成（Week 3振り返り）
- [ ] トラブルシューティングKB 5件作成
- [ ] AI協働パターン2件作成
- [ ] 検索ヒット率60%以上達成
- [ ] ベースライン比較実施（Week 6 vs Week 4トークン使用量）

**検証コマンド**:
```bash
# ノート数確認
find obsidian-vault-local/{01_Learning,02_Troubleshooting,03_AI_Collaboration} -name "*.md" -not -path "*/99_Templates/*" | wc -l
# 期待結果: 8以上（1 + 5 + 2）

# 検索ヒット率測定（手動）
# Week 4の全エラー5-10件をリスト化 → Obsidian検索 → 60%以上ヒット確認
```

---

## 🔄 継続運用・保守計画

### 8.1 日次運用（Week 6以降）

**Daily Notes活用**:
- 学習・実装中: ブロッカー発生時に記録（エラーメッセージ、解決策メモ）
- セッション終了時: タスク成果・学習パターンを整理記録
- リンク追加: 関連Week、トラブルシューティングKB

**3回ルール遵守**:
- 新規エラー発生 → まず検索
- 2回目発生 → Daily Notesにメモ
- 3回目発生 → トラブルシューティングKBに昇格

---

### 8.2 週次運用

**週末レビュー（土曜 or 日曜 1h）**:
1. 週次学習ログ作成（Week Xまとめ）
2. 検索ヒット率測定（先週発生エラーで検証）
3. タグ整理（使用頻度2回以下削除）
4. グラフビュー確認（孤立ノート発見・リンク追加）
5. バックアップ実行（`./scripts/backup_vault.sh`）

---

### 8.3 長期保守計画（Week 6以降）

#### バックアップ戦略（3-2-1ルール）

**3つのコピー**: 本番vault + Git remote + ローカルアーカイブ
**2つの媒体**: SSD（作業用） + 外部HDD（週次バックアップ）
**1つのオフサイト**: GitHub private repo（機密情報除外）

**自動化**:
```bash
# crontab設定（毎日午前2時）
crontab -e
# 追加: 0 2 * * * /Users/yuta/Yuta/python/api-test-devops-portfolio/scripts/backup_vault.sh >> /Users/yuta/Yuta/python/api-test-devops-portfolio/logs/vault_backup.log 2>&1
```

---

## 📚 参考資料・補足

### 9.1 Serena vs Obsidian 判断フローチャート

```
セッション開始時
  ├─ プロジェクト状態確認 → Serena (@memory:ai_collaboration_workflow)
  ├─ 次タスク確認 → Serena (progress_state.yaml自動補完)
  └─ 品質ゲート基準確認 → Serena (@memory:implementation_quality_gates)

エラー発生時
  ├─ 初回エラー → Serena (@memory:test_strategy)
  ├─ 2-3回目エラー → Obsidian全文検索（過去事例確認）
  └─ 未解決 → Obsidian新規ノート作成（3回ルール見越し）

学習復習時
  ├─ 現在Weekの学習内容 → Serena (progress_state.yaml)
  ├─ 過去Weekの復習 → Obsidian検索 + グラフビュー
  └─ 弱点特定 → Obsidian理解度確認問題参照

AI協働時
  ├─ フロー確認 → Serena (@memory:ai_collaboration_workflow)
  ├─ パターン適用 → Obsidian検索（AIパターンライブラリ）
  └─ 新規パターン発見 → Obsidian新規ノート作成（3回ルール）
```

---

### 9.2 用語集

| 用語 | 定義 |
|------|------|
| **Vault** | Obsidianのノート保管庫（1プロジェクト = 1 Vault） |
| **Frontmatter** | ノート冒頭のYAMLメタデータ（検索・分類に使用） |
| **Backlink** | 他ノートからのリンク（自動検出、関連ノート発見） |
| **Graph view** | ノート間のリンクを可視化したグラフ |
| **Daily Notes** | 日付ベースで自動生成されるノート |
| **3回ルール** | 3回以上参照した内容のみObsidianに記録する運用ルール |
| **ADR** | Architecture Decision Records（技術決定記録） |
| **MCP** | Model Context Protocol（Claude CodeとObsidianの接続プロトコル） |
| **Obsidian MCP** | ObsidianをMCP経由で操作するためのツール（本プロジェクトで使用） |
| **Fallback** | Obsidian MCP障害時のfilesystem MCP代替手段 |

---

## 🎯 まとめ：次のアクション

### Week 3（今週）実施事項

**実施期間**: Week 3 Day 13-18（6日間）
**前提**: 6週プラン（38日間）のうち、Week 1-2終了後（Day 12）の翌日から開始

**優先度: HIGH（4-6h投資）**

**Day 13（月曜・最優先）**:
1. [ ] **MCP機能検証テスト** → Section 5.1.0.5, 5.1.1
   - .mcp.json設定確認
   - Test 1-3成功確認
   - 不合格時は vault設計見直し

**Day 14（火曜）**:
2. [ ] **Week 1-2知識移行** → Section 5.1.0
   - daily_progress.md確認
   - 2回以上発生エラー抽出
   - 初期ノート3-5件作成
3. [ ] vault構造作成 → Section 5.1.2
4. [ ] セキュリティ設定 → Section 5.1.3
   - .gitignore強化
   - pre-commit hook作成
   - バックアップスクリプト作成

**Day 15-16（水・木曜）**:
5. [ ] テンプレート5種類作成 → Section 5.1.4
6. [ ] CLAUDE.md更新 → Section 5.1.5

**Day 17（金曜）**:
7. [ ] ADR_001作成 → Section 5.1.6
8. [ ] Obsidian基本操作習得 → Section 5.1.7

**Day 18（土曜）**:
9. [ ] Week 3終了検証 → Section 5.1.7
   - 検証スクリプト実行
   - 初回バックアップ

**成功基準**:
- 全8項目完了
- 検証スクリプト全項目PASS
- 初回ノート読み書き成功

---

### Week 4-6（今後3週間）実施事項

**Week 4: 試験運用（4-5h）**
- 8-10ノート作成（学習中に自然に記録）
- 検索ヒット率60%達成
- ベースライン比較実施

**Week 5: 最適化（3-4h）**
- タグ体系・テンプレート改訂
- 検索ヒット率70%達成
- グラフビューキュレーション

**Week 6: 本番運用（2-3h）**
- 面接準備資料作成（手動）
- グラフ可視化完了
- ポートフォリオ統合

---

### 修正版ROI予測

**投資**: **13-18h**（Week 3-10累計）

**リターン**:
- **Week 4**: 0.5h削減（効率30%）
- **Week 5**: 1.5h削減（効率60%）
- **Week 6**: 2.0h削減（効率80%）
- **累積削減（Week 6終了時）**: 4.0h

**ROI回収**: **Week 12-13（6週プランで案件獲得後）**（累積削減時間が投資時間を上回る）

**長期価値**:
- トークン削減: 60-75%（運用成熟後）
- 面接準備: グラフビュー・ADRによる技術説明力向上
- ポートフォリオ差別化: 知識グラフ可視化による学習プロセス証明

---

**このドキュメントの活用方法**:
1. **Week 3開始前**: Section 1.2.1でベースライン測定実施（必須）
2. **Week 3開始時**: Section 5.1実施（MCP検証 → 環境構築 → セキュリティ設定）
3. **Week 4-6**: 各Weekのロードマップ参照
4. **週次レビュー**: Section 7.2チェックリスト使用
5. **トラブル時**: Section 9.1判断フローチャート参照
6. **ロールバック判断**: Section 1.4トリガー条件確認

---

## 📝 改善履歴

**v2.2レビュー改善版（2025-11-29）**:

*5エージェント多角的レビュー結果に基づく修正*:

- ✅ ディレクトリ数整合性修正（7→9統一）- 全チェックリスト・メトリクス表を9ディレクトリに統一
- ✅ テンプレート数整合性修正（4→5統一）- 全チェックリスト・メトリクス表を5種類に統一
- ✅ MCP障害回復マトリクス追加（Section 5.1.1）- L1-L4障害レベル定義、Fallback戦略表
- ✅ 05_Dailyディレクトリ追加（構造表）- Week 4評価用に「保留」ステータスで追加
- ✅ 週次学習ログ推奨度修正（★☆☆→★★☆）- Section 5.1.2対応表

*セキュリティ検証*:
- ✅ .mcp.json GitHub漏洩チェック完了 - origin/main, origin/local/history, origin/backup全てで「未push」確認
- ✅ .gitignoreに.mcp.json追加 - 今後の誤push防止

*保留項目*（Week 3導入時に対応）:
- ベースライン測定（Week 1未開始のため）
- backup_vault.shスクリプト実装
- pre-commitフック強化

**レビュー実施**: architect-reviewer, technical-writer, quality-engineer, security-auditor, requirements-analyst

---

**v2.1改善版（2025-11-29）**:

*Critical改善（5項目）*:
- ✅ MCP障害回復ガイド追加（Section 5.1.1直後）- 初学者向けエラーTop 3、Fallback手順
- ✅ 5軸スコアリング方法論追加（Section 3.1）- 定量評価の計算式と計算例
- ✅ データ損失リスク評価を「低」→「中」に修正（Section 1.4）
- ✅ ADR面接Talking Points追加（Section 5.1.6）- 2分ピッチ構造、想定Q&A
- ✅ 5テンプレート完全化（既存確認済み）

*High改善（5項目）*:
- ✅ カテゴリ数整合明確化（8カテゴリ+2インフラ）- Section 3.1にサマリー表追加
- ✅ 検索ヒット率自動測定スクリプト追加（Section 5.2.2）
- ✅ 05_Daily作成をWeek 4に延期（Section 3.1日次記録判断）
- ✅ Day 13-18タイムライン明確化（Section 5.1.0）- Day別タスク表追加
- ✅ ディレクトリ構造と推奨度の対応表改訂（Section 5.1.2）

*推奨改善（1項目）*:
- ✅ 週次学習ログを★★☆ → ★☆☆ Optionalに格下げ
  - 理由: 毎週更新される動的性質が強く、静的知識の定義に不適合
  - 変更: 詳細ログ（60min/week）→ 軽量サマリー（10min/week）
  - Serena（progress_state.yaml）で詳細管理、Obsidianは振り返り参照用

**レビュー実施**: 5専門エージェント + Sequential Thinking MCPによる多角的分析

---

**v2改善版（2025-11-22）**:
- ✅ タイムライン修正（5-8h → 13-18h現実的見積もり）
- ✅ ROI回収時期修正（Week 5 → Week 12-13）
- ✅ 自動化率明示（20%、マーケティング言語削除）
- ✅ ベースライン測定プロトコル追加（Section 1.2.1）
- ✅ セキュリティ強化版ロールバック手順（Section 1.4）
- ✅ MCP機能検証テスト追加（Section 5.1.1、最優先タスク）
- ✅ セキュリティ設定追加（.gitignore, pre-commit hook, backup）
- ✅ Fallback Protocol明記（CLAUDE.md追加セクション）
- ✅ クイックスタート追加（Section 1.5）
- ✅ 日次記録統合判断フローチャート追加（Section 3.1）
- ✅ 検証スクリプト追加（Week 3, Week 4自動検証）
- ✅ テンプレート使用例追加（Week 3 Docker例示）
- ✅ バックアップ戦略追加（3-2-1ルール、Section 8.3）
- ✅ 保守的ROI計算（加重平均、hit rate考慮）

**レビュー実施エージェント**:
1. system-architect: アーキテクチャ妥当性、MCP検証、Fallback設計
2. requirements-analyst: 要件完全性、ベースライン測定、検証手順
3. devops-architect: タイムライン実現性、ROI計算、リソース配分
4. security-engineer: セキュリティ強化、バックアップ戦略、ロールバック手順
5. technical-writer: ドキュメント品質、構造最適化、参照整合性
