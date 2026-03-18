"""models/responses.py のユニットテスト

Pydanticレスポンスモデルとsanitize_user_content関数のテスト。
XSS保護機能の検証を含む。
"""

import pytest
from pydantic import ValidationError

from models.responses import (
    Address,
    Album,
    Comment,
    Company,
    Geo,
    Photo,
    Post,
    Todo,
    User,
    sanitize_user_content,
)

pytestmark = pytest.mark.unit


class TestSanitizeUserContent:
    """sanitize_user_content関数のテスト"""

    def test_sanitize_basic_html(self) -> None:
        """基本的なHTMLタグをエスケープする"""
        result = sanitize_user_content("<script>alert('XSS')</script>")
        assert "&lt;script&gt;" in result
        assert "<script>" not in result

    def test_sanitize_quotes(self) -> None:
        """シングル・ダブルクォートをエスケープする"""
        result = sanitize_user_content("test'\"value")
        assert "&#x27;" in result  # シングルクォート
        assert "&quot;" in result  # ダブルクォート

    def test_sanitize_ampersand(self) -> None:
        """アンパサンドをエスケープする"""
        result = sanitize_user_content("foo & bar")
        assert "&amp;" in result

    def test_sanitize_none_returns_empty(self) -> None:
        """Noneの場合は空文字列を返す"""
        result = sanitize_user_content(None)
        assert result == ""

    def test_sanitize_empty_string(self) -> None:
        """空文字列はそのまま返す"""
        result = sanitize_user_content("")
        assert result == ""

    def test_sanitize_normal_text(self) -> None:
        """通常テキストは変更されない"""
        text = "Hello World 123"
        result = sanitize_user_content(text)
        assert result == text


class TestPostModel:
    """Postモデルのテスト"""

    def test_post_creation(self) -> None:
        """正常なPost作成"""
        post = Post(id=1, userId=1, title="Test Title", body="Test Body")
        assert post.id == 1
        assert post.user_id == 1
        assert post.title == "Test Title"
        assert post.body == "Test Body"

    def test_post_xss_sanitization(self) -> None:
        """PostのXSSサニタイゼーション"""
        post = Post(
            id=1,
            userId=1,
            title="<script>alert('XSS')</script>",
            body="<img src=x onerror=alert('XSS')>",
        )
        assert "<script>" not in post.title
        assert "<img" not in post.body
        assert "&lt;script&gt;" in post.title

    def test_post_alias_mapping(self) -> None:
        """userIdからuser_idへのエイリアスマッピング"""
        post = Post(id=1, userId=99, title="Test", body="Body")
        assert post.user_id == 99

    def test_post_invalid_id_zero_raises_validation_error(self) -> None:
        """id=0でValidationErrorが発生する（境界値テスト: ge=1）"""
        with pytest.raises(ValidationError) as exc_info:
            Post(id=0, userId=1, title="Test", body="Body")
        assert "id" in str(exc_info.value)

    def test_post_title_exceeds_max_length_raises_validation_error(self) -> None:
        """title>200文字でValidationErrorが発生する（境界値テスト: max_length=200）"""
        long_title = "a" * 201
        with pytest.raises(ValidationError) as exc_info:
            Post(id=1, userId=1, title=long_title, body="Body")
        assert "title" in str(exc_info.value)


class TestCommentModel:
    """Commentモデルのテスト"""

    def test_comment_creation(self) -> None:
        """正常なComment作成"""
        comment = Comment(
            id=1,
            postId=1,
            name="John Doe",
            email="john@example.com",
            body="Great post!",
        )
        assert comment.id == 1
        assert comment.post_id == 1
        assert comment.name == "John Doe"

    def test_comment_xss_sanitization(self) -> None:
        """CommentのXSSサニタイゼーション"""
        comment = Comment(
            id=1,
            postId=1,
            name="<script>evil()</script>",
            email="<a href='javascript:void(0)'>click</a>",
            body="<div onclick='alert()'>text</div>",
        )
        assert "<script>" not in comment.name
        assert "<a href" not in comment.email
        assert "<div onclick" not in comment.body


class TestUserModel:
    """Userモデルのテスト"""

    def test_user_creation(self) -> None:
        """正常なUser作成"""
        user = User(
            id=1,
            name="John Doe",
            username="johndoe",
            email="john@example.com",
            address=Address(
                street="123 Main St",
                suite="Apt 1",
                city="New York",
                zipcode="10001",
                geo=Geo(lat="40.7128", lng="-74.0060"),
            ),
            phone="1-234-567-8901",
            website="example.com",
            company=Company(
                name="ACME Corp",
                catchPhrase="Making things happen",
                bs="synergy",
            ),
        )
        assert user.id == 1
        assert user.name == "John Doe"
        assert user.company.name == "ACME Corp"

    def test_user_xss_sanitization(self) -> None:
        """UserのXSSサニタイゼーション"""
        user = User(
            id=1,
            name="<script>alert('name')</script>",
            username="<img src=x>",
            email="<a>email</a>",
            address=Address(
                street="<script>street</script>",
                suite="<img>suite",
                city="<a>city</a>",
                zipcode="12345",
                geo=Geo(lat="0.0", lng="0.0"),
            ),
            phone="<script>phone</script>",
            website="<script>site</script>",
            company=Company(
                name="<b>Company</b>",
                catchPhrase="<i>Phrase</i>",
                bs="<u>BS</u>",
            ),
        )
        assert "<script>" not in user.name
        assert "<img" not in user.username
        assert "<b>" not in user.company.name


class TestTodoModel:
    """Todoモデルのテスト"""

    def test_todo_creation(self) -> None:
        """正常なTodo作成"""
        todo = Todo(id=1, userId=1, title="Buy groceries", completed=False)
        assert todo.id == 1
        assert todo.user_id == 1
        assert todo.title == "Buy groceries"
        assert todo.completed is False

    def test_todo_xss_sanitization(self) -> None:
        """TodoのXSSサニタイゼーション"""
        todo = Todo(id=1, userId=1, title="<script>malicious()</script>", completed=True)
        assert "<script>" not in todo.title
        assert "&lt;script&gt;" in todo.title


class TestAlbumModel:
    """Albumモデルのテスト"""

    def test_album_creation(self) -> None:
        """正常なAlbum作成"""
        album = Album(id=1, userId=1, title="Vacation Photos")
        assert album.id == 1
        assert album.user_id == 1
        assert album.title == "Vacation Photos"

    def test_album_xss_sanitization(self) -> None:
        """AlbumのXSSサニタイゼーション"""
        album = Album(id=1, userId=1, title="<script>bad()</script>")
        assert "<script>" not in album.title


class TestPhotoModel:
    """Photoモデルのテスト"""

    def test_photo_creation(self) -> None:
        """正常なPhoto作成"""
        photo = Photo(
            id=1,
            albumId=1,
            title="Beach Sunset",
            url="https://example.com/photo.jpg",
            thumbnailUrl="https://example.com/thumb.jpg",
        )
        assert photo.id == 1
        assert photo.album_id == 1
        assert photo.title == "Beach Sunset"

    def test_photo_xss_sanitization(self) -> None:
        """PhotoのXSSサニタイゼーション"""
        photo = Photo(
            id=1,
            albumId=1,
            title="<script>photo_xss()</script>",
            url="https://example.com/photo.jpg",
            thumbnailUrl="https://example.com/thumb.jpg",
        )
        assert "<script>" not in photo.title
        assert "&lt;script&gt;" in photo.title
