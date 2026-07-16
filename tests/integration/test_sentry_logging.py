"""Sentryログ連携の統合テスト。

get_logger().error() から structlog、_sentry_processor、sentry_sdk、
_before_send、transport までの経路を結合状態で検証する。

unitテストでは _sentry_processor と _before_send を個別検証しているため、
本ファイルでは実際の配線、PIIスクラブ、レベルルーティング、cleanupを対象とする。

fake DSNとcapturing transportを使用し、外部ネットワーク通信は行わない。
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
    """Sentry eventをメモリ上に収集し、実送信を防ぐテスト用transport。"""

    def __init__(self) -> None:
        super().__init__()
        self.captured_events: list[dict[str, Any]] = []
        # payload 抽出失敗を記録する。sentry_sdk は transport 呼び出しを
        # capture_internal_exceptions() でラップし例外をログのみで握り潰すため
        # （getsentry/sentry-python 仕様）、ここで握り潰すと captured_events が
        # 空のままになり PII スクラブ検証が空リストに対して vacuously true となる。
        # fixture teardown でこのリストを assert し、抽出失敗を確実に顕在化させる。
        self.capture_errors: list[str] = []

    def capture_envelope(self, envelope: Any) -> None:
        """event payloadを収集し、抽出失敗をteardownで検出できるよう記録する。"""
        for item in envelope.items:
            try:
                payload = item.payload.json
            except Exception as exc:  # noqa: BLE001 - 抽出失敗を確実に捕捉し teardown で顕在化
                self.capture_errors.append(f"{type(exc).__qualname__}: {exc}")
                continue
            if isinstance(payload, dict) and payload.get("type") != "transaction":
                self.captured_events.append(payload)

    def flush(
        self,
        timeout: float = 0.0,
        callback: Any = None,
    ) -> None:
        pass


@pytest.fixture
def captured_events(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[dict[str, Any]]]:
    """Sentryを有効化し、eventをメモリ収集するtransportを提供する。

    teardownでSDKと設定を復元し、payload抽出エラーも失敗として顕在化する。
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

    captured_errors = transport.capture_errors
    try:
        yield transport.captured_events
    finally:
        # 後続テストへの状態リークを防止（assert 失敗時もクリーンアップを必ず実行）
        _reset_sentry_sdk_client_for_test()
        reload_settings()

    # payload 抽出に失敗していた場合は teardown で顕在化させる。
    # これを欠くと captured_events が空のまま PII 検証が vacuously true となり
    # サイレントにリークを見逃す（sentry-sdk 内部 API のバージョン差異対策）。
    # クリーンアップ後に assert することで、失敗してもセッション状態は復元済みにする。
    assert not captured_errors, f"capturing transport で payload 抽出に失敗: {captured_errors}"


def test_logger_error_forwards_to_sentry_with_pii_scrubbed(
    captured_events: list[dict[str, Any]],
) -> None:
    """実logger経路でERROR eventがcaptureされ、passwordがスクラブされることを検証する。"""
    logger = get_logger(__name__)

    logger.error("integration_test_error", password="super-secret-value", user_id=1)  # noqa: S106
    sentry_sdk.flush()

    # 空リストに対するvacuous passを防ぐため、capture成功を先に検証する
    assert len(captured_events) >= 1, (
        f"ERROR ログが Sentry へ転送されていない（captured={len(captured_events)} 件）。"
        " transport 差し替えタイミング / flush / structlog level routing を確認すること"
    )

    # event全体をシリアライズし、ネストした任意の場所へのPII漏洩を検査する
    serialized = json.dumps(captured_events, default=str)

    # （_before_send スクラブが実 logger パスで効く証明）。
    assert "super-secret-value" not in serialized, (
        "PII 値 'super-secret-value' が capture event にリークしている"
        "（_before_send のスクラブが実 logger 経路で機能していない）"
    )

    # スクラブ後も非機密のイベント名は残る（過剰スクラブで全消ししていないことの証明）。
    assert "integration_test_error" in serialized, (
        "非機密のイベント名 'integration_test_error' が失われている（過剰スクラブの疑い）"
    )


def test_logger_warning_does_not_forward_to_sentry(
    captured_events: list[dict[str, Any]],
) -> None:
    logger = get_logger(__name__)

    events_before = len(captured_events)
    logger.warning("integration_test_warning", password="should-not-appear")  # noqa: S106
    sentry_sdk.flush()

    assert len(captured_events) == events_before, (
        "WARNING ログが Sentry event として送信されている（レベルルーティングが誤っている）"
    )


def test_sentry_test_client_cleanup_disables_capture_after_fixture_use(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """cleanup後に旧transportへeventが漏れないことを検証する。"""
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
