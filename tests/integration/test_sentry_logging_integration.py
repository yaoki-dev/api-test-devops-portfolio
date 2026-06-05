"""Sentry ログ連携の統合テスト（logger → structlog chain → _sentry_processor → capture）。

このファイルは ``utils.logger`` と ``utils.sentry_init`` の**モジュール結合**を検証する。

既存テストは各層を分離して検証している:
- ``tests/unit/test_logger.py``      : ``_sentry_processor`` 単体（sentry_sdk をモック）
- ``tests/unit/test_sentry_init.py`` : ``_before_send`` 単体（scrub ロジック 225 ケース）

本ファイルはそれらの隙間を埋める。``get_logger().error()`` から実際の
``sentry_sdk`` capture までの**経路全体**を貫通させ、設定済み structlog チェーン経由で
PII が ``_before_send`` によりスクラブされることを保証する。

ネットワーク非依存:
- 実在しない fake DSN を使用し、capturing transport が実送信を遮断する
- conftest の ``disable_sentry_for_tests`` (autouse, ``SENTRY__ENABLED=false``) を
  ``monkeypatch.setenv`` で上書きする（後勝ち特性を利用、conftest 編集不要）
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
import sentry_sdk
from sentry_sdk.transport import Transport

from config.settings import reload_settings
from utils.logger import get_logger
from utils.sentry_init import init_sentry, reset_sentry_state

if TYPE_CHECKING:
    from collections.abc import Iterator

pytestmark = pytest.mark.integration

# 実在しないがフォーマット妥当な fake DSN（capturing transport が実ネットワーク送信を遮断）
_FAKE_DSN = "https://public@example.invalid/1"


def _reset_sentry_sdk_client_for_test() -> None:
    """Sentry SDK の global client を無効化し、後続テストへの capture 漏れを防ぐ。"""
    sentry_sdk.get_client().close(timeout=0)
    sentry_sdk.get_global_scope().set_client(None)
    sentry_sdk.get_isolation_scope().set_client(None)
    sentry_sdk.get_current_scope().set_client(None)
    reset_sentry_state()


class _CapturingTransport(Transport):
    """送信 event を収集するテスト用 transport（実ネットワーク送信なし）。

    ``sentry_sdk`` は client から envelope を本 transport に渡す。各 envelope の
    event payload を ``captured_events`` に蓄積し、テスト側で検証可能にする。
    """

    def __init__(self) -> None:
        super().__init__()
        self.captured_events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Any) -> None:
        """envelope 内の event item を収集する。"""
        for item in envelope.items:
            payload = item.payload.json
            if isinstance(payload, dict) and payload.get("type") != "transaction":
                self.captured_events.append(payload)

    def flush(
        self,
        timeout: float = 0.0,
        callback: Any = None,
    ) -> None:
        """no-op（実送信しないため flush 不要）。"""


@pytest.fixture
def captured_events(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Sentry を fake DSN で初期化し、送信 event を捕捉する transport を差し込む。

    conftest の ``disable_sentry_for_tests`` (autouse) を上書きし、``init_sentry()`` で
    ``_before_send`` 配線込みで初期化する。差し込んだ transport の収集リストを yield する。
    """
    monkeypatch.setenv("SENTRY__ENABLED", "true")
    monkeypatch.setenv("SENTRY__DSN", _FAKE_DSN)
    monkeypatch.setenv("ENVIRONMENT", "testing")
    reload_settings()
    _reset_sentry_sdk_client_for_test()

    assert init_sentry() is True, "fake DSN での Sentry 初期化に失敗"

    transport = _CapturingTransport()
    client = sentry_sdk.get_client()
    client.transport = transport  # 実送信を捕捉用に差し替え（before_send 配線は維持）

    yield transport.captured_events

    # 後続テストへの状態リークを防止
    _reset_sentry_sdk_client_for_test()
    reload_settings()


def test_logger_error_forwards_to_sentry_with_pii_scrubbed(
    captured_events: list[dict[str, Any]],
) -> None:
    """get_logger().error() が structlog チェーン経由で Sentry に転送され、
    PII（password）が ``_before_send`` でスクラブされることを検証する。

    検証経路: get_logger().error() → 設定済み structlog processors →
    ``_sentry_processor`` → ``sentry_sdk.capture_*`` → ``_before_send`` →
    capturing transport
    """
    logger = get_logger(__name__)

    # Act: PII（password）を含む ERROR ログを送出（S106: 意図的なダミー機密値）
    logger.error("integration_test_error", password="super-secret-value", user_id=1)  # noqa: S106
    sentry_sdk.flush()

    # Assert 1: ERROR event が実際に capture された（経路貫通の証明）。
    #   これを先に固定しないと、captured_events が空のまま Assert 2 の
    #   "not in" が vacuously True になり PII リークを見逃す（vacuous pass 回避）。
    assert len(captured_events) >= 1, (
        f"ERROR ログが Sentry へ転送されていない（captured={len(captured_events)} 件）。"
        " transport 差し替えタイミング / flush / structlog level routing を確認すること"
    )

    # event dict 群を全文字列化（PII はネスト構造の logentry/extra/contexts 等に分散しうるため、
    # 再帰 walk より一括 serialize → 部分一致の方が漏れ経路を取りこぼさない）。
    # default=str: 非 JSON シリアライズ値が混じってもクラッシュさせず文字列化する堅牢化。
    serialized = json.dumps(captured_events, default=str)

    # Assert 2: PII 値がどの event にも含まれない
    # （_before_send スクラブが実 logger パスで効く証明）。
    assert "super-secret-value" not in serialized, (
        "PII 値 'super-secret-value' が capture event にリークしている"
        "（_before_send のスクラブが実 logger 経路で機能していない）"
    )

    # Assert 3: スクラブ後も非機密のイベント名は残る（過剰スクラブで全消ししていないことの証明）。
    assert "integration_test_error" in serialized, (
        "非機密のイベント名 'integration_test_error' が失われている（過剰スクラブの疑い）"
    )


def test_logger_warning_does_not_forward_to_sentry(
    captured_events: list[dict[str, Any]],
) -> None:
    """WARNINGログはSentryへ転送されないことを保証する。"""
    logger = get_logger(__name__)

    events_before = len(captured_events)
    logger.warning("integration_test_warning", password="should-not-appear")  # noqa: S106
    sentry_sdk.flush()

    assert len(captured_events) == events_before


def test_sentry_test_client_cleanup_disables_capture_after_fixture_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """テスト用 Sentry client cleanup 後は ERROR ログが stale transport に送信されない。"""
    monkeypatch.setenv("SENTRY__ENABLED", "true")
    monkeypatch.setenv("SENTRY__DSN", _FAKE_DSN)
    monkeypatch.setenv("ENVIRONMENT", "testing")
    reload_settings()
    _reset_sentry_sdk_client_for_test()
    assert init_sentry() is True

    transport = _CapturingTransport()
    sentry_sdk.get_client().transport = transport

    _reset_sentry_sdk_client_for_test()
    monkeypatch.setenv("SENTRY__ENABLED", "false")
    reload_settings()

    get_logger(__name__).error("post_cleanup_error")
    sentry_sdk.flush()

    assert sentry_sdk.get_client().is_active() is False
    assert transport.captured_events == []
