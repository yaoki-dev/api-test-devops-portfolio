 ✅ 学習したスキル

  1. pytest基礎 - fixture、parametrize、async test
  2. Docker基礎 - multi-stage build、環境分離
  3. 設定管理 - Pydantic Settings、環境変数
  4. HTTPクライアント設計 - エラーハンドリング、リトライ
  5. テストデータ管理 - Factory パターン、モック 


📚 Week 1 Day 1 学習スキル解説

  1. 🧪 pytest基礎 - fixture、parametrize、async test

  🔍 pytestって何？

  Pythonのテストを書くためのツールです。「テストを書くことで、コードが正しく動くことを確認する」のが目的です。

  📦 fixture（フィクスチャ）

  「テストで使う道具を準備してくれる便利な仕組み」

  # 例：テストで使うAPIクライアントを準備
  @pytest.fixture
  def api_client():
      client = HTTPClient("https://api.example.com")
      return client

  def test_get_user(api_client):  # ← fixtureが自動で渡される
      response = api_client.get("/users/1")
      assert response.status_code == 200

  なぜ便利？
  - テスト毎に同じ準備コードを書かなくて済む
  - テストが終わったら自動でお片付けしてくれる

  🔢 parametrize（パラメータ化）

  「同じテストを色んな条件で実行する仕組み」

  @pytest.mark.parametrize("user_id,expected_name", [
      (1, "田中太郎"),
      (2, "佐藤花子"),
      (3, "山田次郎"),
  ])
  def test_get_user_name(user_id, expected_name):
      user = get_user(user_id)
      assert user.name == expected_name

  実際の効果：1つのテスト関数で3回テストが実行される！

  ⚡ async test（非同期テスト）

  「時間のかかる処理（API呼び出しなど）を効率的にテストする方法」

  @pytest.mark.asyncio
  async def test_api_call():
      async with httpx.AsyncClient() as client:
          response = await client.get("https://api.example.com/users")
          assert response.status_code == 200

  同期 vs 非同期の違い：
  - 同期：1つ1つ順番に実行（遅い）
  - 非同期：複数の処理を並行実行（速い）

  ---
  2. 🐳 Docker基礎 - multi-stage build、環境分離

  🔍 Dockerって何？

  「アプリケーションを箱（コンテナ）に入れて、どこでも同じように動かせる技術」

  🏗️ multi-stage build（マルチステージビルド）

  「1つのDockerfileで複数の用途に使える効率的な仕組み」

  # ステージ1：ベース（共通部分）
  FROM python:3.11 as base
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install -r requirements.txt

  # ステージ2：開発環境用
  FROM base as development
  COPY . .
  CMD ["python", "app.py"]

  # ステージ3：本番環境用（軽量化）
  FROM base as production
  COPY app.py .
  CMD ["python", "app.py"]

  利点：
  - 1つのファイルで開発・テスト・本番の全環境に対応
  - 本番環境では不要なファイルを除外して軽量化

  🏠 環境分離

  「開発・テスト・本番で違う設定を使い分ける仕組み」

  # docker-compose.yml
  services:
    app:          # 開発環境
      environment:
        - DEBUG=true

    tests:        # テスト環境
      environment:
        - DEBUG=false
        - TESTING=true

    production:   # 本番環境（別ファイル）
      environment:
        - DEBUG=false
        - LOG_LEVEL=WARNING

  メリット：
  - 環境ごとに最適な設定
  - 本番事故の防止
  - チーム開発での一貫性

  ---
  3. ⚙️ 設定管理 - Pydantic Settings、環境変数

  🔍 設定管理って何？

  「アプリケーションの動作を環境に応じて変更するためのシステム」

  🛡️ Pydantic Settings

  「型安全で自動検証してくれる設定管理システム」

  class APIConfig(BaseModel):
      base_url: str = "https://api.example.com"
      timeout: float = Field(ge=1.0, le=300.0)  # 1〜300秒の範囲
      retry_count: int = Field(ge=0, le=10)     # 0〜10回の範囲

  # 使用時
  config = APIConfig()
  print(config.base_url)  # "https://api.example.com"

  # 不正な値は自動でエラーになる
  config = APIConfig(timeout=-5)  # ❌ ValidationError

  通常の設定 vs Pydantic Settings：
  - 通常：typo、型間違い、範囲外の値でも気づかない
  - Pydantic：起動時に自動チェック、問題があれば教えてくれる

  🌍 環境変数

  「OSレベルで設定値を渡す標準的な方法」

  # 開発環境
  export API_TIMEOUT=30
  export LOG_LEVEL=DEBUG

  # 本番環境  
  export API_TIMEOUT=60
  export LOG_LEVEL=WARNING

  python app.py  # ← 環境に応じて異なる動作

  利点：
  - パスワードをコードに書かずに済む
  - 環境ごとに設定を変更可能
  - 12-Factor Appの原則に準拠

  ---
  4. 🌐 HTTPクライアント設計 - エラーハンドリング、リトライ

  🔍 HTTPクライアントって何？

  「WebAPIと通信するためのプログラム」

  💥 エラーハンドリング

  「API呼び出しで起こりうる様々な問題に対処する仕組み」

  try:
      response = client.get("/api/users")
      response.raise_for_status()  # HTTPエラーをチェック
      return response.json()

  except httpx.TimeoutException:
      logger.warning("APIがタイムアウトしました")

  except httpx.HTTPStatusError as e:
      if e.response.status_code == 404:
          logger.info("ユーザーが見つかりません")
      elif e.response.status_code >= 500:
          logger.error("サーバーエラーが発生しました")

  except httpx.ConnectError:
      logger.error("API接続に失敗しました")

  エラーの種類：
  - 400番台：クライアントのミス（リトライ無意味）
  - 500番台：サーバーの一時的な問題（リトライ有効）
  - タイムアウト：ネットワークが遅い（リトライ有効）

  🔄 リトライ

  「失敗した時に自動的に再挑戦する仕組み」

  for attempt in range(max_retries + 1):
      try:
          response = make_request()
          return response  # 成功したら終了

      except RetriableError:
          if attempt < max_retries:
              wait_time = 2 ** attempt  # 指数バックオフ
              time.sleep(wait_time)
          else:
              raise  # 最後の試行でも失敗したらエラー

  リトライ戦略：
  - 固定間隔：1秒、1秒、1秒...
  - 指数バックオフ：1秒、2秒、4秒、8秒...（推奨）

  ---
  5. 📋 テストデータ管理 - Factory パターン、モック

  🔍 テストデータ管理って何？

  「テストで使うダミーデータを効率的に作成・管理する手法」

  🏭 Factoryパターン

  「テストデータを簡単に量産する仕組み」

  @pytest.fixture
  def user_factory():
      def create_user(name="テストユーザー", age=25, email=None):
          return {
              "name": name,
              "age": age,
              "email": email or f"{name.lower()}@example.com"
          }
      return create_user

  def test_user_validation(user_factory):
      # 様々なパターンのユーザーデータを簡単に作成
      normal_user = user_factory()
      young_user = user_factory(name="太郎", age=16)
      senior_user = user_factory(name="花子", age=65)

  従来の方法 vs Factory：
  - 従来：テスト毎に長いデータ作成コード
  - Factory：必要な部分だけ指定、あとはお任せ

  🎭 モック

  「本物の代わりをする偽物（テスト専用）」

  def test_user_service_with_mock(mocker):
      # データベースの代わりをするモック
      mock_db = mocker.patch('user_service.database')
      mock_db.find_user.return_value = {"id": 1, "name": "テストユーザー"}

      # テスト実行
      user = user_service.get_user(1)

      # モックが期待通りに呼び出されたかチェック
      mock_db.find_user.assert_called_once_with(1)
      assert user["name"] == "テストユーザー"

  モックが必要な理由：
  - 高速化：DBアクセス不要
  - 安定性：外部サービス障害の影響なし
  - 制御：エラーケースも自由に再現

  ---
  🎯 実際の開発での活用例

  🏢 企業での典型的な使い方

  1. pytest + fixture：
  # 毎回同じAPIクライアント設定を使いたい
  @pytest.fixture
  def api_client():
      return APIClient(base_url="https://staging-api.company.com")
  2. Docker multi-stage：
  # 開発者のローカル環境
  docker build --target development -t myapp:dev .

  # CI/CDでのテスト環境
  docker build --target test -t myapp:test .

  # 本番デプロイ
  docker build --target production -t myapp:prod .
  3. Pydantic設定管理：
  # 開発環境では.envファイルから自動読み込み
  # 本番環境では環境変数から自動読み込み
  settings = Settings()  # どちらでも同じコード

  これらのスキルを組み合わせることで、実務レベルの品質とスピードを両立できるようになります！