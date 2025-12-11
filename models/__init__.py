"""Pydanticレスポンスモデル - XSS保護対応

JSONPlaceholder APIのレスポンスを型安全に扱うための
Pydanticモデルコレクション。全てのユーザー生成コンテンツに
XSS保護のサニタイゼーションを適用。

実装パターン:
- 型安全性: Pydantic BaseModelによる厳格な型検証
- セキュリティ: html.escape()による防御的サニタイゼーション
- 保守性: 明確な日本語ドキュメントとエラーメッセージ
"""

from models.responses import Album, Comment, Photo, Post, Todo, User

__all__ = ["Album", "Comment", "Photo", "Post", "Todo", "User"]
