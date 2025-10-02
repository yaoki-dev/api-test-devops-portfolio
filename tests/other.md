https://github.com/yuta158/api-test-_portfolio.gitのmainにポートフォリオには含めない学習関連のファイル等も含まれています
本セッションでは段階的に以下のファイルをステージしてコミットする方針でした
ポートフォリオとして関係ないファイルや正常動作しないコードはgithubから削除してください
ローカルのコードは変えないでください
#
git add config/ utils/ tests/
  git add pyproject.toml uv.lock .gitignore .pre-commit-config.yaml
# 実装ガイド - 技術力証明
  git add docs/guides/ci_cd_guide.md
  git add docs/guides/docker_guide.md
  git add docs/guides/owasp_compliance_checklist.md
  git add docs/guides/performance_benchmark_guide.md
  git add docs/guides/unified_measurement_guide.md

  # セキュリティドキュメント - OWASP準拠証明
  git add docs/security/security_testing_procedures.md
  git add docs/security/claude_squad_security_assessment.md

  # 品質保証ドキュメント
  git add docs/quality/INTEGRATED_QUALITY_ASSURANCE_GUIDE.md

  # アーキテクチャ設計
  git add docs/architecture/UNIFIED_ARCHITECTURE_BLUEPRINT.md
  git add docs/architecture/document_integration_strategy.md

  # コンプライアンス
  git add docs/compliance/compliance_system_master.md

  # API仕様
  git add docs/api/api_documentation.md
  git add docs/api/openapi.yaml

  # プロジェクト概要（面接で使用）
  git add docs/project-overview/project_index_summary.md
  git add docs/project-overview/technical_stack.md
  git add docs/project-overview/project_index_detail.md