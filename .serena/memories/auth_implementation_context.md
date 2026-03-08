# API認証機能実装コンテキスト

**最終更新**: 2026-02-03 19:30
**ステータス**: 実装中（Phase 1完了）

## クイックリファレンス

```yaml
branch: feature/ast-grep-security-hardening
files_modified:
  - utils/auth.py (300行)
  - tests/unit/test_auth.py (100行)
  - config/settings.py (設定追加)
next_action: コードレビュー準備（2026-02-04 09:00）
blockers: なし
```

## 設計判断サマリー

| 決定事項 | 選択 | 主な理由 |
|----------|------|----------|
| 認証方式 | JWT | ステートレス、スケーラビリティ |
| トークン戦略 | Sliding Window + Absolute | セキュリティと利便性のバランス |
| エラー処理 | 階層的例外 | 詳細な内部ログ、汎用外部レスポンス |

## トークン設定値

```python
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
REFRESH_TOKEN_ABSOLUTE_DAYS = 30
```

## 例外クラス階層

```
AuthError (基底)
├── TokenExpiredError
├── TokenInvalidError
└── RefreshTokenError
```

## 未完了タスク

1. エッジケーステスト追加
2. 統合テスト作成
3. 認証ミドルウェア適用
4. ドキュメント更新

## 復元手順

1. `git status` で状態確認
2. `uv run pytest tests/unit/test_auth.py -v` でテスト確認
3. 品質ゲート実行
4. ハンドオフドキュメント参照: `docs/handoff/2026-02-03_auth_implementation_handoff.md`

## レビュー準備チェックリスト

- [ ] 品質ゲート全合格
- [ ] 設計判断の説明準備
- [ ] セキュリティ考慮点の整理
- [ ] 未実装機能の明確化
