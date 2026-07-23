"""utils/logger.py のユニットテスト"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from utils.logger import _sentry_processor

pytestmark = pytest.mark.unit


class TestSentryProcessor:
    """警告状態fixtureでthrottle経路を分離

    Note: setenv/delenv を使用する場合、ここでは cache_clear() は不要。"""

    # ダミーのWrappedLoggerとmethod_name（未使用だが引数として必要）
    _dummy_logger = None
    _dummy_method = "error"

    def test_silent_skip_on_import_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5a: sentry-sdk未インストール時は非本番・SENTRY_DEBUG未設定でサイレントスキップ

        環境非依存のため get_settings を明示的に mock し ENVIRONMENT の影響を遮断する。
        sys.modules["sentry_sdk"] = None が CPython 仕様により import 文で ImportError を
        発生させるため builtins.__import__ の全置換は不要 (pytest/structlog 等の内部 import
        への副作用を回避)。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = False

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", return_value=mock_settings):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        # 警告が出力されないことを明示検証 (is_production_like=False AND SENTRY_DEBUG未設定)
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" not in captured.err

    @pytest.mark.parametrize("sentry_debug_value", ["true", "1", "yes"])
    def test_warn_on_import_error_when_sentry_debug_enabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        sentry_debug_value: str,
    ) -> None:
        """分岐5c: SENTRY_DEBUG有効時はImportError時にstderr警告出力

        5dとの対称性のため get_settings をモックし、実行環境の ENVIRONMENT 変数に
        依存しない形で SENTRY_DEBUG 経路（is_production=False + SENTRY_DEBUG=有効値）
        のみを独立検証する。logger.py 側で受理される "true"/"1"/"yes" 全てをテスト。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", sentry_debug_value)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = False  # SENTRY_DEBUG 経路のみ検証

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", return_value=mock_settings):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" in captured.err
        assert "sentry-sdk not installed" in captured.err
        # is_production_like() 分岐が実際に評価されたことを検証 (5d と対称な causal path 保証)
        mock_settings.is_production_like.assert_called_once()

    def test_warn_on_import_error_when_production_env(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5d: 本番環境ではSENTRY_DEBUG未設定でもstderr警告出力

        sentry_init.pyのImportError→RuntimeError Fail-Fast方針と整合性を確保し、
        本番デプロイ時のsentry-sdk未インストールを検知可能にする。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = True

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", return_value=mock_settings):
                result = _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        assert result is event_dict
        captured = capsys.readouterr()
        assert "[SENTRY_WARN]" in captured.err
        assert "sentry-sdk not installed" in captured.err
        # is_production_like() 分岐が実際に評価されたことを検証 (causal path 保証)
        mock_settings.is_production_like.assert_called_once()

    def test_sentry_warnings_throttled_across_multiple_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """_sentry_processor の stderr 警告は per-process 1 回のみ出力される

        structlog processor は ERROR ログ毎に呼ばれるため、settings 失敗 × sentry-sdk
        未インストールが持続する環境で log flood が発生する副作用を防ぐ。
        3 回連続呼び出しで警告が計 2 行 (settings + sdk 各 1 回) のみ出力されることを検証。

        早期リターン最適化の保証 (call_count assertion):
        sdk フラグ昇格後は ``_emit_import_error_warnings()`` 内の ``if
        _sentry_sdk_warning_emitted: return`` で get_settings() 呼出し自体が
        skip される。assert により誤って早期リターンを削除した場合のリグレッション
        (= エラーストーム時の累積コスト増) を検出する。

        strict equality (== 1) を採用する理由:
        現行設計では 1 回目の呼出しで sdk フラグが昇格し、2 回目以降は早期リターン
        により get_settings() が呼ばれない。「<= 1」ではなく「== 1」を採用することで、
        将来的に flag 昇格パスが冗長化された場合 (例: 複数の lock acquire 経路で
        重複呼出し) も fail-loud で即検知できる。設計意図の strict 維持を優先。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module,
                "get_settings",
                side_effect=RuntimeError("Settings validation failed"),
            ) as mock_get_settings:
                for _ in range(3):
                    _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        # settings 失敗警告と sentry-sdk 未インストール警告はそれぞれ 1 回のみ
        assert captured.err.count("[SENTRY_WARN] settings load failed") == 1
        assert captured.err.count("sentry-sdk not installed") == 1
        # 早期リターンにより 2 回目以降 get_settings() は呼ばれない (strict equality)
        assert mock_get_settings.call_count == 1, (
            f"早期リターン分岐が機能しておらず get_settings() が "
            f"{mock_get_settings.call_count} 回呼び出された (期待値: 1)"
        )

    def test_throttle_on_settings_success_path(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """分岐5g: settings 成功 × is_prod=True でも sdk 警告は 1 回のみ throttle される

        正規ルート (settings 成功・本番環境) で `sdk_not_installed_emitted` フラグ単独で
        スロットルが機能することを検証する。旧実装の「両フラグ AND」条件では
        settings_emitted が昇格しないため early-return が不発だったリグレッションを防ぐ。

        早期リターン最適化の保証 (call_count assertion):
        1 回目で sdk フラグ昇格後、2 回目以降は ``_emit_import_error_warnings()`` 内の
        早期リターンで get_settings() 呼出しが skip される。assert により最適化の
        リグレッションを検出する。
        """
        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        from utils import logger as logger_module

        mock_settings = MagicMock()
        mock_settings.is_production_like.return_value = True

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(
                logger_module, "get_settings", return_value=mock_settings
            ) as mock_get_settings:
                for _ in range(3):
                    _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        # sdk 警告は 1 回のみ。settings 警告は発生しない (成功ケース)
        assert captured.err.count("sentry-sdk not installed") == 1
        assert "[SENTRY_WARN] settings load failed" not in captured.err
        # 早期リターンにより 2 回目以降 get_settings() は呼ばれない
        assert mock_get_settings.call_count == 1, (
            f"早期リターン分岐が機能しておらず get_settings() が "
            f"{mock_get_settings.call_count} 回呼び出された (期待値: 1)"
        )

    def test_concurrent_emit_warnings_throttled_under_race(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """_sentry_warning_lock が concurrent 呼出下でも throttle を維持する

        pytest capsys はワーカースレッド内 print が差し替え後 stderr を参照しない
        可能性があるため (false negative リスク)、io.StringIO による monkeypatch で
        全スレッドが同一バッファを参照する確定的な検証に変更する (#12 対応)。

        red-green 保証: get_settings を遅延注入し check-and-set の race window を強制露出。
        lock 無し実装では複数スレッドが check を通過し複数警告出力 → test 失敗する。

        #31 対応: race window はテスト worker 関数間で発生する (sleep は lock 内だが
        barrier でレリースした全 thread が _emit_import_error_warnings に同時到達するため、
        lock 取得競合のラウンド時に check-and-set race が顕在化する)。
        """
        import io
        import threading
        import time

        event_dict = {"level": "error", "event": "error message"}
        monkeypatch.setenv("SENTRY_DEBUG", "true")

        from utils import logger as logger_module

        captured_stderr = io.StringIO()
        monkeypatch.setattr(sys, "stderr", captured_stderr)

        def slow_get_settings() -> MagicMock:
            time.sleep(0.05)
            m = MagicMock()
            m.is_production_like.return_value = False
            m.is_production.return_value = False
            return m

        num_threads = 20
        barrier = threading.Barrier(num_threads, timeout=5.0)  # #32: timeout でデッドロック防止

        # worker スレッドの例外を main thread に伝播させる収集機構。
        # 単純な threading.Thread + join では worker 内例外 (BrokenBarrierError 等) が
        # サイレントに握り潰され、デッドロック検知のみ機能する状態だった。
        worker_exceptions: list[BaseException] = []
        worker_exceptions_lock = threading.Lock()

        def worker() -> None:
            try:
                barrier.wait()
                _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)
            except BaseException as exc:  # noqa: BLE001 — 全例外を main thread へ伝播
                with worker_exceptions_lock:
                    worker_exceptions.append(exc)

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            with patch.object(logger_module, "get_settings", side_effect=slow_get_settings):
                threads = [threading.Thread(target=worker) for _ in range(num_threads)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join(timeout=10.0)
                    assert not t.is_alive(), "worker thread deadlocked"

        # worker 内で発生した例外を集約して main thread で再 raise。
        # サイレント握り潰し防止: BrokenBarrierError や AssertionError 等を確実に検知。
        assert not worker_exceptions, (
            f"worker thread(s) raised unexpected exceptions: "
            f"{[type(e).__name__ + ': ' + str(e) for e in worker_exceptions]}"
        )

        output = captured_stderr.getvalue()
        assert output.count("sentry-sdk not installed") == 1, (
            f"concurrent race: expected 1 warning, got {output.count('sentry-sdk not installed')}"
        )

    def test_invalid_exc_info_warning_throttled_across_multiple_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        event_dict = {
            "level": "error",
            "event": "invalid exc_info type",
            "exc_info": "not_an_exception_instance",
        }

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            for _ in range(3):
                _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        assert (
            captured.err.count(
                "[SENTRY_WARN] invalid exc_info type for capture_exception: str; "
                "falling back to capture_message"
            )
            == 1
        )
        assert mock_scope.capture_message.call_count == 3

    def test_sentry_bug_throttled_across_multiple_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """[SENTRY_BUG] は複数回AttributeError発生でもper-process 1回のみ出力される"""
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_sdk.new_scope.side_effect = AttributeError("repeated SDK error")

        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            for _ in range(3):
                _sentry_processor(
                    self._dummy_logger, self._dummy_method, {"level": "error", "event": "test"}
                )

        captured = capsys.readouterr()
        bug_lines = [line for line in captured.err.splitlines() if line.startswith("[SENTRY_BUG]")]
        assert len(bug_lines) == 1

    def test_sentry_send_error_throttled_across_multiple_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """[SENTRY_ERROR] は複数回Sentry送信失敗でも1回のみ出力される"""
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_scope.capture_message.side_effect = RuntimeError("Sentry connection failed")

        event_dict = {"level": "error", "event": "error message"}
        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            for _ in range(3):
                _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        assert captured.err.count("[SENTRY_ERROR]") == 1

    def test_sentry_send_error_warns_again_after_interval(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """[SENTRY_ERROR] は interval (5分) 経過後に再警告される

        timestamp ベース throttle (`_SENTRY_SEND_ERROR_WARN_INTERVAL`) の core 振る舞い
        — 「ネットワーク瞬断後の永続サイレント化を防止」を保護するリグレッションテスト。
        bool flag への誤った退化を検出する (現状の throttle テストは初回1回のみ検証)。
        """
        from utils import logger as logger_module

        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)
        mock_scope.capture_message.side_effect = RuntimeError("Sentry connection failed")

        # time.monotonic を制御: 1 回目=0.0, 2 回目=interval 未満, 3 回目=interval 超過
        interval = logger_module._SENTRY_SEND_ERROR_WARN_INTERVAL
        time_values = iter([0.0, interval - 1.0, interval + 1.0])
        monkeypatch.setattr(logger_module.time, "monotonic", lambda: next(time_values))

        event_dict = {"level": "error", "event": "error message"}
        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            for _ in range(3):
                _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        # 1 回目 (t=0) と 3 回目 (t=interval+1) で警告 → 2 回出力されることを確認
        # 2 回目 (t=interval-1) は throttle により抑制される
        assert captured.err.count("[SENTRY_ERROR]") == 2, (
            f"interval 後再警告失敗: 警告行数 = {captured.err.count('[SENTRY_ERROR]')}"
            " (期待 = 2: 初回 + interval経過後)"
        )

    def test_outside_except_warning_throttled_across_multiple_calls(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("SENTRY_DEBUG", raising=False)

        mock_sdk = MagicMock()
        mock_sdk.get_client.return_value.is_active.return_value = True
        mock_scope = MagicMock()
        mock_sdk.new_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sdk.new_scope.return_value.__exit__ = MagicMock(return_value=False)

        # exc_info=True だが except ブロック外で複数回呼び出す
        event_dict = {"level": "error", "event": "msg", "exc_info": True}
        with patch.dict("sys.modules", {"sentry_sdk": mock_sdk}):
            for _ in range(3):
                _sentry_processor(self._dummy_logger, self._dummy_method, event_dict)

        captured = capsys.readouterr()
        warn_count = captured.err.count(
            "[SENTRY_WARN] logger.exception() called outside except block"
        )
        assert warn_count == 1, f"throttle 失敗: 警告行数 = {warn_count} (期待 = 1)"
