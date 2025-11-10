# Week 7 Docker実装完了チェックリスト

*最終更新: 2025年10月23日*

Week 7（Day 37-42）のDocker基盤実装完了の判定基準を定める総合チェックリスト。本チェックリスト全項目合格によって、**Week 8実行前提条件達成**となる。

---

## ✅ 実装完了チェックリスト（5段階評価）

### Phase 1: Dockerfile実装完了判定

#### 1.1 基本構成（必須：5個全て ✅）

- [ ] **builder stage実装**
  - [ ] `FROM python:3.12-slim as builder`で開始
  - [ ] `RUN pip install uv` 実行
  - [ ] `RUN uv sync --frozen` 実行
  - [ ] `/root/.local/`に依存関係インストール確認
  - **判定**: 5点（全て実装） / 3点（3-4個実装） / 1点（1-2個実装） / 0点（未実装）

- [ ] **dev stage実装**
  - [ ] `FROM python:3.12 as dev` で開始
  - [ ] builderから依存関係COPY
  - [ ] `EXPOSE 8000`ポート設定
  - [ ] `CMD ["python", "-m", "uvicorn", ...]` 開発サーバー起動
  - **判定**: 5点（全て実装） / 3点（3個実装） / 1点（1-2個実装） / 0点（未実装）

- [ ] **test stage実装**
  - [ ] `FROM builder as test` で開始
  - [ ] builderから依存関係COPY
  - [ ] `RUN uv sync --frozen` 実行
  - [ ] `CMD ["uv", "run", "pytest", ...]` テスト実行
  - **判定**: 5点（全て実装） / 3点（3個実装） / 1点（1-2個実装） / 0点（未実装）

- [ ] **ci stage実装**
  - [ ] `FROM builder as ci` で開始
  - [ ] builderから依存関係COPY
  - [ ] `RUN uv sync --frozen` 実行
  - [ ] `CMD ["uv", "run", "pytest", "--cov=.", ...]` カバレッジ実行
  - **判定**: 5点（全て実装） / 3点（3個実装） / 1点（1-2個実装） / 0点（未実装）

- [ ] **prod stage実装**
  - [ ] `FROM python:3.12-slim as prod` で開始
  - [ ] builderから依存関係COPY（必要最小限）
  - [ ] `ENTRYPOINT ["python", "-m", "uvicorn", ...]` 本番実行
  - [ ] イメージサイズ最小化確認（< 500MB推奨）
  - **判定**: 5点（全て実装） / 3点（3個実装） / 1点（1-2個実装） / 0点（未実装）

#### 1.2 品質基準（必須：全て ✅）

- [ ] **マルチステージbuild効果測定**
  - [ ] 単一stage vs マルチステージイメージサイズ測定
    ```bash
    docker images | grep api-test-devops
    # builder: < 800MB推奨
    # dev: < 1GB推奨
    # test: < 1GB推奨
    # ci: < 800MB推奨（テスト最適化）
    # prod: < 500MB推奨（本番最適化）
    ```
  - [ ] **判定**: 5点（目標達成） / 3点（75%達成） / 1点（50%達成） / 0点（未測定）

- [ ] **セキュリティスキャン合格**
  - [ ] `docker run --rm aquasec/trivy image api-test-devops:ci` 実行
  - [ ] Critical/High脆弱性 = 0件
  - [ ] Medium脆弱性 ≤ 2件（許容範囲）
  - **判定**: 5点（Critical/High=0） / 3点（Medium≤2） / 0点（不合格）

- [ ] **Layer caching最適化**
  - [ ] `.dockerignore` 設定確認（`**/__pycache__`, `**/*.pyc`, `.git`, `venv/`等除外）
  - [ ] Dockerfile レイヤー順序最適化（変更頻度：低→高順）
  - [ ] 不要なレイヤー統合（RUN連鎖）
  - **判定**: 5点（全て最適化） / 3点（2個最適化） / 1点（1個最適化） / 0点（未最適化）

---

### Phase 2: docker-compose実装完了判定

#### 2.1 環境構成（必須：全て ✅）

- [ ] **dev環境構成**
  - [ ] services.web.image指定（`api-test-devops:dev`）
  - [ ] ports: ["8000:8000"]指定
  - [ ] volumes設定（ソースコード→コンテナ同期）
  - [ ] environment設定（`ENVIRONMENT=development`）
  - **判定**: 5点（全て実装） / 3点（3個実装） / 0点（不完全）

- [ ] **test環境構成**
  - [ ] services.web.image指定（`api-test-devops:test`）
  - [ ] command: ["uv", "run", "pytest", "--cov=.", ...]指定
  - [ ] volumes: ["./:/app"]マウント
  - [ ] environment設定（`ENVIRONMENT=testing`）
  - **判定**: 5点（全て実装） / 3点（3個実装） / 0点（不完全）

- [ ] **ci環境構成**
  - [ ] services.web.image指定（`api-test-devops:ci`）
  - [ ] command: ["uv", "run", "pytest", "--cov=.", "--cov-fail-under=85"]指定
  - [ ] environment設定（`ENVIRONMENT=ci`）
  - **判定**: 5点（全て実装） / 3点（2個実装） / 0点（不完全）

- [ ] **prod環境構成**
  - [ ] services.web.image指定（`api-test-devops:prod`）
  - [ ] ports設定（本番ポート）
  - [ ] environment設定（`ENVIRONMENT=production`）
  - [ ] restart policy: always設定
  - **判定**: 5点（全て実装） / 3点（3個実装） / 0点（不完全）

#### 2.2 動作確認（必須：全て ✅）

- [ ] **dev環境動作確認**
  ```bash
  docker-compose -f docker-compose.yml up dev
  # localhost:8000にアクセス → 200応答確認
  ```
  - **判定**: 5点（成功） / 0点（失敗）

- [ ] **test環境動作確認**
  ```bash
  docker-compose -f docker-compose.yml run --rm test
  # pytest実行 → カバレッジ85%以上
  ```
  - **判定**: 5点（合格） / 3点（60-84%） / 0点（失敗）

- [ ] **ci環境動作確認**
  ```bash
  docker-compose -f docker-compose.yml run --rm ci
  # pytest + ruff + mypy + bandit実行 → 全合格
  ```
  - **判定**: 5点（全合格） / 3点（2個以上失敗） / 0点（非動作）

- [ ] **prod環境動作確認**
  ```bash
  docker-compose -f docker-compose.yml up prod
  # localhost:productionport にアクセス → 200応答確認
  ```
  - **判定**: 5点（成功） / 0点（失敗）

---

### Phase 3: Week 8実行前提条件チェック

#### 3.1 技術要件（必須：全て ✅）

- [ ] **Docker build成功**
  ```bash
  docker build -t api-test-devops:ci --target ci .
  # 出力: "Successfully tagged api-test-devops:ci"
  ```
  - **判定**: 5点（成功） / 0点（失敗）

- [ ] **Docker内pytest実行成功**
  ```bash
  docker run --rm api-test-devops:ci uv run pytest --cov=. --cov-fail-under=85
  # 出力: "passed xxx in X.XXs" + "coverage: XX%"
  # カバレッジ: ≥ 85%
  ```
  - **判定**: 5点（85%以上） / 3点（75-84%） / 0点（失敗または<75%）

- [ ] **docker-compose up成功**
  ```bash
  docker-compose up -d web
  sleep 3
  curl http://localhost:8000/healthcheck
  # 出力: 200 OK
  docker-compose down
  ```
  - **判定**: 5点（成功） / 0点（失敗）

#### 3.2 品質要件（必須：全て ✅）

- [ ] **イメージセキュリティ スコア**
  ```bash
  docker run --rm aquasec/trivy image api-test-devops:ci
  # Critical: 0件
  # High: 0件
  ```
  - **判定**: 5点（0件） / 3点（1-2件） / 1点（3-5件） / 0点（6件以上）

- [ ] **テストカバレッジ 85%以上**
  ```bash
  docker run --rm api-test-devops:ci uv run pytest --cov=. --cov-report=term-missing
  # 出力: "TOTAL ... 85%" (または それ以上)
  ```
  - **判定**: 5点（85%以上） / 3点（80-84%） / 0点（79%以下）

- [ ] **テスト実行時間 <= 30秒**
  ```bash
  time docker run --rm api-test-devops:ci uv run pytest --cov=. --cov-fail-under=85
  # 実行時間: <= 30秒
  ```
  - **判定**: 5点（<=30秒） / 3点（30-45秒） / 1点（45-60秒） / 0点（>60秒）

#### 3.3 ドキュメント要件（必須：全て ✅）

- [ ] **README.md Docker セクション**
  - [ ] Docker環境セットアップ手順記載
  - [ ] docker build / docker-compose up コマンド例記載
  - [ ] 環境別使い分け説明（dev/test/ci/prod）
  - **判定**: 5点（全て記載） / 3点（2個記載） / 0点（1個以下）

- [ ] **DOCKERFILE コメント**
  - [ ] 各stageの目的コメント
  - [ ] key optimization points コメント
  - **判定**: 5点（充実） / 3点（基本的） / 0点（なし）

- [ ] **docker-compose.yml コメント**
  - [ ] 環境別役割説明
  - [ ] volume/port設定理由説明
  - **判定**: 5点（充実） / 3点（基本的） / 0点（なし）

---

## 📊 スコアリング計算式

### 各セクション配点

```
Phase 1: Dockerfile実装完了判定
  - 基本構成5項目: 25点
  - 品質基準3項目: 15点
  → Phase 1合計: 40点

Phase 2: docker-compose実装完了判定
  - 環境構成4項目: 20点
  - 動作確認4項目: 20点
  → Phase 2合計: 40点

Phase 3: Week 8実行前提条件チェック
  - 技術要件3項目: 10点
  - 品質要件3項目: 5点
  - ドキュメント要件3項目: 5点
  → Phase 3合計: 20点

総合スコア: 100点
```

### 判定基準

| スコア | 判定 | Week 8開始可否 | 対応 |
|--------|------|---------------|----|
| 90-100 | A（優秀） | ✅ 開始可 | Week 8予定通り進行 |
| 80-89 | B（合格） | ✅ 開始可 | Week 8 Day 43-44で補強対応 |
| 70-79 | C（要改善） | ⚠️ 条件付き開始 | 未達成項目の即座修正後に開始 |
| <70 | D（不合格） | ❌ 開始延期 | Week 7継続、完了まで進行停止 |

---

## 📋 実行手順（Edge Case対応済み版）

**🆕 Edge Case対応について**
- 本スクリプトには、**3つの基本形edge case検出**を組み込みました
- 実装時間: +30分（スクリプト実行時間内）
- 実装範囲: 
  - Edge Case 1: Dockerfile not found
  - Edge Case 2: docker-compose.yml syntax error
  - Edge Case 3: Volume permission error（警告）
- 次週以降: 詳細edge case対応は Week 9初期以降に実装予定

---

## 📋 実行手順

### Step 1: 環境構築確認（5分）
```bash
cd /Users/yuta/Yuta/python/api-test-devops-portfolio

# Dockerfile確認
[ -f Dockerfile ] && echo "✅ Dockerfile存在" || echo "❌ Dockerfile不在"

# docker-compose.yml確認
[ -f docker-compose.yml ] && echo "✅ docker-compose.yml存在" || echo "❌ docker-compose.yml不在"

# .dockerignore確認
[ -f .dockerignore ] && echo "✅ .dockerignore存在" || echo "❌ .dockerignore不在"
```

### Step 2: Dockerfile検証（10分）
```bash
# build成功確認
docker build -t api-test-devops:ci --target ci . && echo "✅ ci stage build成功" || echo "❌ build失敗"

# 他のstageも順次確認
for stage in builder dev test prod; do
  docker build -t api-test-devops:$stage --target $stage . && echo "✅ $stage stage成功" || echo "❌ $stage stage失敗"
done

# イメージサイズ確認
docker images | grep api-test-devops
```

**🆕 Edge Case 検出（基本形）: Dockerfile構文エラー**
```bash
# Edge Case 1: Dockerfile not found
if [ ! -f Dockerfile ]; then
  echo "❌ [EDGE CASE 1] Dockerfile not found"
  echo "   原因: Dockerfile がプロジェクトルートに存在しません"
  echo "   対応: Dockerfile をプロジェクトルートに作成してください"
  exit 1
else
  echo "✅ [EDGE CASE 1] Dockerfile存在確認完了"
fi

# Edge Case 2: docker-compose syntax error
if [ ! -f docker-compose.yml ]; then
  echo "❌ [EDGE CASE 2] docker-compose.yml not found"
  echo "   原因: docker-compose.yml がプロジェクトルートに存在しません"
  echo "   対応: docker-compose.yml をプロジェクトルートに作成してください"
  exit 1
fi

# docker-compose構文チェック（簡易形式）
docker-compose config > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "❌ [EDGE CASE 2] docker-compose.yml syntax error"
  echo "   原因: YAML形式エラーまたは無効な設定があります"
  echo "   対応: 以下コマンドで詳細を確認してください:"
  echo "        docker-compose config"
  exit 1
else
  echo "✅ [EDGE CASE 2] docker-compose.yml 構文チェック合格"
fi
```

### Step 3: docker-compose検証（10分）
```bash
# dev環境テスト
docker-compose up dev &
sleep 3
curl http://localhost:8000 && echo "✅ dev環境接続成功"
docker-compose down

# test環境テスト
docker-compose run --rm test && echo "✅ test環境成功"

# ci環境テスト
docker-compose run --rm ci && echo "✅ ci環境成功"

# prod環境テスト
docker-compose up prod &
sleep 3
curl http://localhost:8000 && echo "✅ prod環境接続成功"
docker-compose down
```

**🆕 Edge Case 検出（基本形）: Volume permission error**
```bash
# Edge Case 3: Volume permission error 警告
echo "\n📋 [EDGE CASE 3] Volume permission 事前チェック"

# docker-compose.ymlでvolume設定を確認
if grep -q "volumes:" docker-compose.yml; then
  echo "⚠️  Volume設定を検出しました"
  echo "   注意: docker-compose up実行時にパーミッションエラーが発生する可能性があります"
  echo "\n   【一般的な対応】"
  echo "   - Linux: docker-composeコマンドをsudoで実行するか、dockerグループに追加"
  echo "   - Mac/Windows: Docker Desktopのvolume設定を確認"
  echo "   - 具体的には: docker-compose.yml の volumes セクションで relative path を使用"
  echo "\n   ✅ 確認項目:"
  echo "      - [ ] Volume設定がrelative path か確認"
  echo "      - [ ] 実際のdocker-compose up実行時にエラーが出ないか確認"
else
  echo "✅ [EDGE CASE 3] Volume設定なし（パーミッションエラーリスク回避）"
fi
```

### Step 4: セキュリティスキャン（5分）
```bash
# Trivy実行
docker run --rm aquasec/trivy image api-test-devops:ci
```

### Step 5: スコアリング（5分）
上記のチェックリスト項目を確認し、各項目の判定点数を記入してスコア計算。

---

## 🎯 Week 8開始前の最終確認

### ✅ 必須チェック（全て合格が必須）

```markdown
- [ ] Docker build成功（ci stage）
- [ ] docker-compose全環境動作確認
- [ ] pytest実行 → カバレッジ85%以上
- [ ] セキュリティスキャン → Critical/High = 0件
- [ ] テスト実行時間 <= 30秒
- [ ] README.md Docker セクション記載完了
- [ ] 総合スコア >= 80点
```

### ⚠️ Week 8開始判定フロー

```
総合スコア計算
  ↓
A（90-100） → ✅ Week 8開始（Day 43から）
  ↓
B（80-89）  → ✅ Week 8開始（Day 43-44で補強）
  ↓
C（70-79）  → ⚠️ 未達成項目修正後に開始
  ↓
D（<70）    → ❌ Week 7継続（完了まで進行停止）
```

---

## 📚 参考資料

- Dockerfile実装詳細: `docs/プロジェクト再編/Week7_Docker実装プラン.md`
- docker-compose設定: `docker-compose.yml`
- GitHub Actions統合: `docs/プロジェクト再編/Week8_詳細タスク記述_統合版.md`
- セキュリティ基準: `.trivy.yaml` （Trivy設定）

---

**このチェックリストは Week 8実行前の品質保証最終ゲートです。**
**全項目合格を確認してから Week 8 Day 43を開始してください。**
