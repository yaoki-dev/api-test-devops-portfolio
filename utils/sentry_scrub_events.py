"""Sentry event-level scrub helpers."""

from __future__ import annotations

import secrets
import sys
from typing import TYPE_CHECKING, Any, cast

from utils.logger import get_logger
from utils.sentry_scrub_primitives import _PATH_PII_PATTERN, _is_sensitive_key, _safe_log_warning
from utils.sentry_scrub_values import (
    MAX_SCRUB_DEPTH,
    _scrub_list_item,
    _scrub_request_field,
    _scrub_request_query_string,
    _scrub_sensitive_data,
    _scrub_url,
)

_logger = get_logger(__name__)

# 再帰防止用の内部識別子。scrub 失敗を Sentry に通知する際にこの tag を付与し、
# _before_send 冒頭で検出して scrub をスキップ通過させることで無限ループ
# (capture_message → _before_send → 例外 → capture_message ...) を遮断する。
# value はプロセス起動ごとにランダム生成し、OSS で公開された固定値を悪用した
# scrub バイパス (任意 event tag への注入で _before_send を素通りさせる攻撃) を防ぐ。
# _has_internal_tag / _emit_scrub_failure_to_sentry は
# 同一モジュール global を参照するため一貫して機能する。
_INTERNAL_TAG_KEY: str = "sentry_internal_event"
_INTERNAL_TAG_VALUE: str = secrets.token_hex(16)


def _has_internal_tag(tags: Any) -> bool:
    """内部識別 tag の有無を dict / list[tuple] 両形式で検出する。

    Sentry SDK の現行版 (sentry-sdk >= 2.x) では ``scope.set_tag`` 経由で event に
    到達する ``tags`` は常に dict 形式 (``Scope._apply_tags_to_event`` 参照)。
    ただし ``_before_send`` 自体は SDK 仕様に従い list[tuple[str, str]] 形式も
    受け入れる契約 (``test_before_send_list_tags_redacts_sensitive_key``) のため、
    防御の対称性として recursion guard も両形式に対応する (defense-in-depth)。

    dict が常態の現行 SDK では list 分岐は一見 YAGNI に見えるが、
    上記の ``_before_send`` list[tuple] 受け入れ契約をテストが独立に検証しているため
    意図的に維持する。当該契約テスト廃止時にのみ本分岐の削除を検討すること。

    判定仕様:
        - dict 形式: ``tags[_INTERNAL_TAG_KEY] == _INTERNAL_TAG_VALUE`` で判定。
        - list 形式: ``(_INTERNAL_TAG_KEY, _INTERNAL_TAG_VALUE)`` タプルの完全一致
          で判定 (key のみ一致 / value が異なるペアは通常 event として扱い、
          recursion guard は発火しない)。
        - 上記以外 (None, str, int 等): 常に False。

    Args:
        tags: event["tags"] 相当の値 (dict / list / その他)。

    Returns:
        内部識別 tag が検出された場合 True。
    """
    if isinstance(tags, dict):
        return tags.get(_INTERNAL_TAG_KEY) == _INTERNAL_TAG_VALUE
    if isinstance(tags, list):
        return (_INTERNAL_TAG_KEY, _INTERNAL_TAG_VALUE) in tags
    return False


def _scrub_exception_frame(frame: Any) -> Any:
    """Sentry exception frame を fail-open でスクラブする。"""
    if not isinstance(frame, dict):
        _safe_log_warning(
            "sentry_exception_frame_unexpected_type",
            actual_type=type(frame).__name__,
            action="skip_frame_scrub",
            pii_leak_risk="HIGH",
        )
        return frame

    scrubbed_frame = dict(frame)
    # ソースコンテキスト (pre_context / context_line / post_context) を除去する。
    # Sentry はデフォルトでエラー行周辺のソース行を収集するが、ソース中にハードコードされた
    # 機密値や PII がそのまま送信されるリスクがある (CWE-312)。_scrub_sensitive_data は
    # vars (変数値) のみを対象としソース行テキストは非カバーのため、防御の深さとして drop する。
    for _source_context_key in ("pre_context", "context_line", "post_context"):
        scrubbed_frame.pop(_source_context_key, None)
    frame_vars = scrubbed_frame.get("vars")
    if isinstance(frame_vars, dict):
        scrubbed_frame["vars"] = _scrub_sensitive_data(frame_vars)
    elif frame_vars is not None:
        _safe_log_warning(
            "sentry_exception_frame_vars_unexpected_type",
            actual_type=type(frame_vars).__name__,
            action="skip_vars_scrub",
        )
    return scrubbed_frame


def _scrub_exception_stacktrace(stacktrace: dict[str, Any]) -> dict[str, Any]:
    """Sentry exception stacktrace を fail-open でスクラブする。"""
    frames = stacktrace.get("frames")
    if isinstance(frames, list):
        scrubbed_stacktrace = dict(stacktrace)
        scrubbed_stacktrace["frames"] = [_scrub_exception_frame(frame) for frame in frames]
        return scrubbed_stacktrace
    if frames is not None:
        _safe_log_warning(
            "sentry_exception_frames_unexpected_type",
            actual_type=type(frames).__name__,
            action="skip_frames_scrub",
        )
    return stacktrace


def _scrub_exception_value_item_extra_keys(scrubbed_value: dict[str, Any]) -> None:
    """exception value item の value/stacktrace 以外のトップレベルキーを in-place で
    機密スクラブする。

    標準 Sentry exception value item は type/module/mechanism 等で PII を含まないが、
    カスタム SDK 統合が token/password 等を value item に直接付与した場合の漏洩を
    防ぐ defense-in-depth。``type`` は ``_is_sensitive_key`` 非該当のため redact されず
    観測性を保つ（S-1 の type 非 redact 方針と両立）。dict 値の反復中に値のみを
    更新する（キーの追加/削除はしないため反復は安全）。
    """
    for key in scrubbed_value:
        if key in ("value", "stacktrace"):
            continue
        item = scrubbed_value[key]
        if _is_sensitive_key(key):
            scrubbed_value[key] = "[REDACTED]"
        elif isinstance(item, dict):
            scrubbed_value[key] = _scrub_sensitive_data(item)
        elif isinstance(item, (list, tuple)):
            scrubbed_value[key] = type(item)(_scrub_list_item(elem, _depth=0) for elem in item)


def _scrub_exception_value_item(value_item: Any) -> Any:
    """Sentry exception values[*] を fail-open でスクラブする。

    value フィールドは例外メッセージ文字列のため PII 保護優先で無条件 [REDACTED] に
    置換する（観測性とのトレードオフ。詳細は _scrub_exception_field docstring 参照）。
    """
    if not isinstance(value_item, dict):
        if isinstance(value_item, (list, tuple)):
            return type(value_item)(_scrub_list_item(item, _depth=0) for item in value_item)
        # str/bytes は PII を含む可能性があるため内容確認せず一律 REDACT。
        # int/float/bool は PII 非含のため素通し。
        if isinstance(value_item, (str, bytes)):
            return "[REDACTED]"
        _safe_log_warning(
            "sentry_exception_value_item_unexpected_type",
            actual_type=type(value_item).__name__,
            action="skip_item",
        )
        return value_item

    scrubbed_value = dict(value_item)
    if isinstance(scrubbed_value.get("value"), (str, bytes)):
        scrubbed_value["value"] = "[REDACTED]"

    stacktrace = scrubbed_value.get("stacktrace")
    if isinstance(stacktrace, dict):
        scrubbed_value["stacktrace"] = _scrub_exception_stacktrace(stacktrace)
    elif stacktrace is not None:
        _safe_log_warning(
            "sentry_exception_stacktrace_unexpected_type",
            actual_type=type(stacktrace).__name__,
            action="skip_stacktrace_scrub",
        )

    # value / stacktrace 以外のトップレベルキーも機密判定する。
    _scrub_exception_value_item_extra_keys(scrubbed_value)

    return scrubbed_value


if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint


# before_send / before_send_transaction でスクラブ対象とするイベントフィールド
# （PII漏洩防止の対象集合）。error / transaction 双方が同一 _before_send を通る。
_SCRUBBED_EVENT_FIELDS: frozenset[str] = frozenset(
    {
        "extra",
        "user",
        "contexts",
        "tags",
        "breadcrumbs",
        # transaction イベント固有の子span配列（spans[*].data/description/tags）を
        # スクラブする。before_send_transaction 経路でのみ実在し、error イベントには
        # 当該キーが無いため _scrub_sentry_field の `if field in event_dict` で安全スキップ。
        "spans",
        # values[*].value は _is_sensitive_key の結果に関わらず
        # 無条件 [REDACTED] 置換（PII漏洩防止のため）
        "exception",
    }
)


def _scrub_span_item(item: Any, _depth: int) -> Any:
    """Sentry transaction span の単一要素をスクラブする。"""
    if _depth >= MAX_SCRUB_DEPTH:
        _safe_log_warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
        return "[MAX_DEPTH_EXCEEDED]"
    if not isinstance(item, dict):
        return _scrub_list_item(item, _depth + 1)

    scrubbed = _scrub_sensitive_data(item, _depth + 1)
    if not isinstance(scrubbed, dict):
        # _depth+1 が MAX_SCRUB_DEPTH に到達すると _scrub_sensitive_data は
        # "[MAX_DEPTH_EXCEEDED]" (str) を返す。str.get() による AttributeError →
        # _before_send の except 捕捉 → イベントのサイレントドロップを防ぐ防御ガード
        # 現呼び出し元 _scrub_sentry_field は _depth=0 固定のため到達
        # しないが、将来 _scrub_span_item が深い再帰文脈から呼ばれた場合の保険。
        return scrubbed
    description = scrubbed.get("description")
    if isinstance(description, str):
        method, separator, target = description.partition(" ")
        value_to_scrub = target if separator else description
        if "?" in value_to_scrub or "#" in value_to_scrub:
            scrubbed_description = _scrub_url(value_to_scrub)
        else:
            scrubbed_description = _PATH_PII_PATTERN.sub("[REDACTED]", value_to_scrub)
        scrubbed["description"] = (
            f"{method} {scrubbed_description}" if separator else scrubbed_description
        )
    return scrubbed


def _scrub_tags_item(item: Any, _depth: int = 0) -> Any:
    """tags フィールド専用の要素スクラブ。``_scrub_list_item`` との違いは (key, value)
    ペア判定を list[2] にも拡張している点で、``_scrub_sentry_field`` が field=="tags"
    の場合のみ本関数を呼ぶ。tags 以外のフィールドには ``_scrub_list_item`` を使用すること。

    Sentry SDK 仕様: tags は ``dict[str, str]`` または ``list[tuple[str, str]]``。
    JSON roundtrip で tuple が list 化されるため list[2] も tag pair として扱う。
    加えて非標準だが custom before_send hook 等で生じうる dict / nested list 形態でも
    機密キーを redact する（defense-in-depth）。
    _depth による再帰深さ保護を行い、MAX_SCRUB_DEPTH 超過時は安全サイドに倒す。
    """
    if _depth >= MAX_SCRUB_DEPTH:
        _safe_log_warning("scrub_max_depth_exceeded", depth=_depth, max=MAX_SCRUB_DEPTH)
        return "[MAX_DEPTH_EXCEEDED]"
    if isinstance(item, (tuple, list)) and len(item) == 2:
        key = item[0]
        scrubbed_value = (
            "[REDACTED]"
            if (isinstance(key, str) and _is_sensitive_key(key))
            else _scrub_list_item(item[1], _depth + 1)
        )
        # type(item) は tuple/list 両対応の汎用ファクトリ（意図的な動的構築）
        return cast(Any, type(item))([key, scrubbed_value])
    if isinstance(item, dict):
        return _scrub_sensitive_data(item, _depth + 1)
    if isinstance(item, list):
        # nested list は汎用 scrub にフォールバック（深さを引き継ぐ）
        return [_scrub_list_item(child, _depth=_depth + 1) for child in item]
    if isinstance(item, tuple):
        # len != 2 の tuple も _scrub_list_item で汎用スクラブ（list との一貫性）
        return tuple(_scrub_list_item(child, _depth + 1) for child in item)
    return item


def _scrub_exception_field(exception_value: dict[str, Any]) -> dict[str, Any]:
    """Sentry exception フィールドを構造検証付きでスクラブする（fail-open）。

    Sentry の exception 構造:
      {values: [{type, value, stacktrace: {frames: [{vars: {...}}]}}]}

    各階層（values→stacktrace→frames→vars）で型を isinstance で検証し、
    未知の構造では警告を残してスキップする（破壊しない）。
    vars 内の機密キーは _scrub_sensitive_data() で redact する。
    values[*].value は例外メッセージ文字列として全体を `[REDACTED]` に置換する。
    これは PII 保護を観測性より優先する意図的なトレードオフであり、
    PII を含まない FileNotFoundError 等の診断情報も失われる。将来改善する場合は、
    特定キーワードのみをマスクする selective redact へ移行する。

    **values[*].type は意図的に redact しない**:
        `type` フィールドは例外クラス名 (`ValueError`, `KeyError` 等) を保持し、
        通常 PII を含まない。例外分類は Sentry UI / alert routing / metric 集計の
        primary key として機能するため、redact すると観測性が壊滅的に低下する。
        ただし将来 `type` に PII 文字列が現れる SDK 拡張 / custom exception
        命名規則が導入された場合は本方針を再評価する必要がある。

    設計トレードオフ (fail-open):
        Sentry SDK の将来バージョンや custom integration により未知の exception
        構造が渡された場合、本関数は破壊せず通過させる（observability 優先）。
        この設計には残存リスクが1点存在する:
        **未知構造の内側に機密データが含まれていた場合、scrub されず Sentry に
        到達する可能性がある**。
        最外殻 ``_before_send`` の ``except Exception`` 二重防御は、本関数が
        ``MemoryError`` / ``RecursionError`` 以外の例外を送出した場合にのみ
        ``_emit_scrub_failure_to_sentry`` 経由で event drop に倒すが、
        fail-open ロジックは例外を送出せず正常完了するため、未知構造による
        PII 漏洩は二重防御では検出されない（許容された残存リスク）。
        fail-closed への変更を検討する場合は、観測性低下（正常な例外イベント
        まで drop される）とのトレードオフを評価すること。

    Args:
        exception_value: Sentry イベントの "exception" 辞書

    Returns:
        スクラブ済み exception 辞書（元データは変更しない）

    """
    values = exception_value.get("values")
    if isinstance(values, dict):
        # dict 型 values: _scrub_sensitive_data で内容をスクラブして返す
        result = dict(exception_value)
        result["values"] = _scrub_sensitive_data(values)
        return result
    if values is None:
        # "values" キー未存在は Sentry exception interface 仕様上の有効な構造
        # (getsentry/sentry interfaces/exception.py: get_path(data, "values",
        # default=[]) で空リスト扱い、Relay schema でも values は必須でない)。
        # よって誤検知 WARNING を出さずに、他キーをベストエフォートスクラブして返す
        # 正常構造に対するログノイズ抑制
        scrubbed = _scrub_sensitive_data(exception_value)
        # _depth=0 開始のため dict 以外（"[MAX_DEPTH_EXCEEDED]"）は構造上発生しないが、
        # cast による型隠蔽を避け isinstance ガードで型安全を明示する。
        return scrubbed if isinstance(scrubbed, dict) else {}
    if not isinstance(values, list):
        # str / int 等、None でも list/dict でもない真に予期しない型のみ WARNING。
        _safe_log_warning(
            "sentry_exception_values_unexpected_type",
            actual_type=type(values).__name__,
            action="exception_scrub_fallback",
        )
        # 構造不明でも _scrub_sensitive_data でベストエフォートスクラブ
        scrubbed = _scrub_sensitive_data(exception_value)
        # _depth=0 開始のため dict 以外（"[MAX_DEPTH_EXCEEDED]"）は構造上発生しないが、
        # cast による型隠蔽を避け isinstance ガードで型安全を明示する。
        return scrubbed if isinstance(scrubbed, dict) else {}

    result = dict(exception_value)
    result["values"] = [_scrub_exception_value_item(val) for val in values]
    return result


def _scrub_sentry_field(event_dict: dict[str, Any], field: str) -> None:
    """Sentryイベントの単一フィールドをスクラブする（_before_send 専用）。

    dict型の場合は _scrub_sensitive_data() で再帰的にスクラブする
    （``exception`` は _scrub_exception_field で values[*].value REDACTION と
    stackframe scrub を適用）。
    list型の場合は field 単位で dispatch する: ``exception`` は各要素へ
    _scrub_exception_value_item を適用し（defense-in-depth）、``tags`` は
    (key, value) ペア形式、その他（breadcrumbs 等）は dict/list 要素形式として
    スクラブする。非PII のデバッグ情報（リクエストID等）は保持する
    （Sentry SDK 仕様: tags は ``list[tuple[str, str]]`` 形式も許容）。
    上記以外の型の場合は安全サイドに置換する（fail-closed）: ``exception`` は
    Sentry exception interface 準拠の無害なプレースホルダ（``ScrubbedException``）へ、
    それ以外は空dictへ置換し、logger.warning を常時出力する（本番監視対応）。
    _scrub_sensitive_data の内部 non-dict ガードと二重防御を構成する。

    Args:
        event_dict: Sentryイベント辞書（破壊的更新）
        field: スクラブ対象フィールド名

    """
    if field in event_dict:
        value = event_dict[field]
        if isinstance(value, dict):
            if field == "exception":
                event_dict[field] = _scrub_exception_field(value)
            else:
                event_dict[field] = _scrub_sensitive_data(value)
        elif isinstance(value, list):
            # field 単位 dispatch: tags は Sentry spec 上 list[tuple[str, str]]
            # （JSON経由で list[list[str, str]] にもなり得る）なので tag pair として処理。
            # 加えて非標準だが custom before_send hook 等で生じうる list[dict] / list[list]
            # 形態でも defense-in-depth で内部の機密キーを redact する
            # tags-as-list-of-dicts 退行修正
            # 他フィールド（breadcrumbs/contexts/extra/user）は汎用要素として
            # 処理し、list[2] with str[0] の偶発的 tag-pair 誤判定で過剰 redact
            # しない。
            if field == "exception":
                # exception が list 形式（Sentry 標準は dict だが custom before_send
                # 等で生じうる）でも values[*].value の REDACTION と stackframe vars
                # scrub を適用し、PII（例外メッセージ・frame 変数）の素通りを防ぐ (defense-in-depth）  # noqa: E501
                # dict 要素は exception 専用スクラブ、非 dict 要素（custom hook が
                # 生成しうる list/tuple/scalar）は汎用 _scrub_list_item で再帰スクラブ
                # する。これにより本関数の tags / spans / else の list 分岐と同様に
                # 「全分岐で非 dict 要素も再帰スクラブ・素通しゼロ」を満たし、dispatch の
                # 一貫性保持のため、fail-openによる非対称を解消。
                event_dict[field] = [
                    _scrub_exception_value_item(item)
                    if isinstance(item, dict)
                    else _scrub_list_item(item, _depth=0)
                    for item in value
                ]
            elif field == "tags":
                event_dict[field] = [_scrub_tags_item(item, _depth=0) for item in value]
            elif field == "spans":
                event_dict[field] = [_scrub_span_item(item, _depth=0) for item in value]
            else:
                event_dict[field] = [_scrub_list_item(item, _depth=0) for item in value]
        else:
            # dict/list以外はスクラブ不可能なため、安全サイドに倒して置換する（fail-closed）。
            # exception フィールドは Sentry exception interface 仕様に準拠した
            # 無害なプレースホルダ構造へ置換し PII 素通りを防ぐ。
            # 他フィールドは空 dict に置換する。
            if field == "exception":
                event_dict[field] = {
                    "values": [
                        {
                            "type": "ScrubbedException",
                            "value": "[REDACTED: unscrubable exception structure]",
                        }
                    ]
                }
                _safe_log_warning(
                    "sentry_field_type_unexpected",
                    field=field,
                    actual_type=type(value).__name__,
                    action="replaced_with_safe_placeholder",
                    event_id=event_dict.get("event_id"),
                )
            else:
                event_dict[field] = {}
                _safe_log_warning(
                    "sentry_field_type_unexpected",
                    field=field,
                    actual_type=type(value).__name__,
                    action="replaced_with_empty_dict",
                    event_id=event_dict.get("event_id"),
                )


# fail-closed防御による退避後、スクラビング失敗イベントを安全にSentryへ通知するフェーズ。
# 以下の定数は、その内部イベント（_INTERNAL_TAG付与）専用のextra許可リストである。

# このセットに含まれるキーのみ _set_internal_extras 経由で設定でき、_before_send の
# scrub をバイパスして Sentry に到達する。PII を含み得るキーを追加してはならない
# 各キーは「scrub バイパスを許可する」明示的な grant であり、セキュリティ境界そのもの。
# 値は _emit_scrub_failure_to_sentry が設定する extra キーと 1:1 で対応させる
# （不足 → 実行時 ValueError / 過剰 → PII 素通りの穴）。
_INTERNAL_EVENT_EXTRA_KEYS: frozenset[str] = frozenset(
    {
        "error_type",
        "error_module",
        "action",
        "event_id",
    }
)


def _set_internal_extras(scope: Any, extras: dict[str, str | None]) -> None:
    """scrub バイパス内部イベント専用の extra セッター。

    許可リスト ``_INTERNAL_EVENT_EXTRA_KEYS`` 外のキーを拒否し、将来の変更者が
    新規 extra キーを無検証で追加して PII を scrub バイパスさせるリスクを
    コードレベルで防止する（コメント規約のみの保証を技術的強制へ格上げ）。

    Args:
        scope: Sentry スコープ（``new_scope()`` の戻り値）。
        extras: 設定する extra キー・値のマッピング。

    Raises:
        ValueError: 許可リスト外のキーが含まれる場合。
    """
    for key in extras:
        if key not in _INTERNAL_EVENT_EXTRA_KEYS:
            raise ValueError(f"Unauthorized key in internal event extra: {key!r}")

    for key, value in extras.items():
        scope.set_extra(key, value)


def _emit_scrub_failure_to_sentry(exc: BaseException, event_id: str | None = None) -> None:
    """scrub 失敗を内部識別 tag 付きで Sentry へ通知する（fail-safe）。

    sentry_sdk.capture_message は再度 _before_send を通るが、付与した
    _INTERNAL_TAG_KEY=_INTERNAL_TAG_VALUE を冒頭で検出して scrub をスキップ
    通過させるため無限再帰しない。内部 SDK 呼び出し自体が例外を投げた場合は
    最終フォールバックとして stderr へ出力し、メインプロセスをクラッシュさせない。

    **SDK バージョン制約**:
        再帰防止ガード（_INTERNAL_TAG_KEY による scrub スキップ）は Sentry SDK 2.x
        の内部動作（``Scope._apply_tags_to_event``）に依存する。
        pyproject.toml の ``sentry-sdk<3.0.0`` 制約により 3.x 以降の
        内部変更から保護している。3.x へ移行する際は本ガードの動作を再検証すること。

    **Security constraint**: ``extra`` フィールドに
    PII を含めてはならない。本制約に違反した場合、内部通知イベントが scrub を
    バイパスして PII がそのまま Sentry に到達する。
    """
    try:
        sentry_sdk = sys.modules.get("sentry_sdk")
        if sentry_sdk is None:
            # SDK 未ロード（テスト・未インストール環境）: stderr フォールバック
            print(
                f"[SENTRY_SCRUB_FAILED] sentry_sdk_not_loaded "
                f"error_type={type(exc).__qualname__} "
                f"error_module={type(exc).__module__}",
                file=sys.stderr,
                flush=True,
            )
            return
        with sentry_sdk.new_scope() as scope:
            scope.set_tag(_INTERNAL_TAG_KEY, _INTERNAL_TAG_VALUE)
            scope.set_level("error")
            # SECURITY: extra は許可リスト（_INTERNAL_EVENT_EXTRA_KEYS）経由でのみ設定 —
            # _before_send scrub バイパスのため、PII を含み得るキーの素通りをコードで防止する。
            extras: dict[str, str | None] = {
                "error_type": type(exc).__qualname__,
                "error_module": type(exc).__module__,
                "action": "event_dropped",
            }
            # event_id は UUID 形式のため PII ではない。
            # None の場合は extra に含めない（従来挙動を維持）。
            if event_id is not None:
                extras["event_id"] = event_id
            _set_internal_extras(scope, extras)
            scope.capture_message("sentry_scrub_failed", level="error")
    except (MemoryError, RecursionError):  # fmt: skip
        # MemoryError/RecursionError も Exception 派生のため、再raise しないと直下の
        # except Exception に捕捉されサイレント隠蔽される。OOM/再帰超過を握り潰さず
        # 即座に fail-fast 伝播させる。コードベース他6箇所の統一パターン
        # `except (MemoryError, RecursionError): raise` に集約し、将来の修正漏れを防ぐ
        # 分離記述から統合、挙動は不変。
        # 再raise後は呼び出し元 _before_send の emit 保護 try/except が捕捉し、明示的に
        # return None するため fail-closed（PII 非送信）は維持される。
        raise
    except Exception as inner_exc:  # noqa: BLE001
        # Sentry 通知自体が失敗 → stderr へ最終フォールバック
        print(
            f"[SENTRY_SCRUB_FAILED] inner_error_type={type(inner_exc).__qualname__} "
            f"inner_error_module={type(inner_exc).__module__} "
            f"original_error_type={type(exc).__qualname__} "
            f"original_error_module={type(exc).__module__}",
            file=sys.stderr,
            flush=True,
        )


def _before_send(event: Event, hint: Hint) -> Event | None:  # noqa: ARG001, C901
    """Sentry送信前フック（機密データ除外）

    再帰防止: scrub 失敗時に発火する内部通知イベント（_INTERNAL_TAG_KEY
    が付与されている）は冒頭で検出し、scrub をスキップして通過させる。
    これにより capture_message → _before_send → 例外 → capture_message
    の無限ループを遮断する（_emit_scrub_failure_to_sentry 参照）。

    Args:
        event: Sentryイベント
        hint: 追加コンテキスト（未使用）

    Returns:
        処理済みイベント、またはNone（送信キャンセル）

    """
    # 再帰防止ガード: 内部通知イベントは scrub をスキップして通過させる
    # dict / list[tuple] 両形式に対応 (defense-in-depth, _has_internal_tag 参照)
    if _has_internal_tag(event.get("tags")):
        return event

    # scrub_exc は except 句で捕捉した例外を try ブロックの外へ持ち出すための変数。
    # _emit_scrub_failure_to_sentry を except コンテキスト外で呼ぶことで sys.exc_info() が
    # アクティブな状態を避け、Sentry SDK が元例外(PII 付き)を内部通知イベントに添付する
    # 事故を防ぐ (fail-closed 防御。詳細は下方 `except Exception` 節を参照)
    scrub_exc: Exception | None = None
    # cast は実行時 no-op（型システム専用）— try 外に置いても動作変化なし
    event_dict = cast(dict[str, Any], event)
    try:
        # リクエストデータのスクラブ。成功時だけ event["request"] を差し替える。
        # _scrub_sensitive_data / _scrub_query_string / _scrub_url は全て non-destructive で
        # 新しいオブジェクトを返すため、top-level dict の shallow copy で十分。
        # 元 request の non-mutation 契約は既存テスト
        # ``test_before_send_fail_closed_without_partial_request_mutation`` で継続検証。
        if "request" in event_dict:
            request = event_dict["request"]
            if isinstance(request, dict):
                scrubbed_request = dict(request)
                for req_field in ("headers", "data", "cookies", "env"):
                    if req_field in scrubbed_request:
                        scrubbed_request[req_field] = _scrub_request_field(
                            scrubbed_request[req_field]
                        )
                if "query_string" in scrubbed_request and isinstance(
                    scrubbed_request["query_string"], (str, bytes)
                ):
                    scrubbed_request["query_string"] = _scrub_request_query_string(
                        scrubbed_request["query_string"]
                    )
                if "url" in scrubbed_request and isinstance(scrubbed_request["url"], str):
                    scrubbed_request["url"] = _scrub_url(scrubbed_request["url"])
                event_dict["request"] = scrubbed_request
            else:
                event_dict["request"] = {}
                _safe_log_warning(
                    "sentry_request_type_unexpected",
                    actual_type=type(request).__name__,
                    action="replaced_with_empty_dict",
                    event_id=event_dict.get("event_id"),
                )

        # 追加データのスクラブ（2層防御）
        # _scrub_sentry_field: 非dict型フィールドを空dictに置換（型安全化・PII漏洩防止）
        # _scrub_sensitive_data: dict内の機密キーを [REDACTED] に置換（PII除外）
        for field in _SCRUBBED_EVENT_FIELDS:
            _scrub_sentry_field(event_dict, field)
    except (MemoryError, RecursionError):  # fmt: skip
        # システム異常（OOM・スタックオーバーフロー）は fail-closed で event を
        # ドロップする。before_send からの例外は Sentry SDK が内部 catch し
        # PII 付きイベントをそのまま送信し続けるリスクがあるため、stderr への
        # 最小通知だけ残して return None で安全に遮断する（CWE-391 対策）。
        try:
            print(
                "[SENTRY_SCRUB_FAILED] before_send system error: MemoryError or RecursionError",
                file=sys.stderr,
                flush=True,
            )
        except Exception:  # noqa: BLE001, S110
            pass
        return None
    except Exception as exc:
        # sys.exc_info() がアクティブな状態で _emit_scrub_failure_to_sentry を
        # 呼ぶと、Sentry SDK が元例外（PII 付き）を内部通知イベントに添付する
        # リスクがあるため、例外コンテキストの外で呼び出す（fail-closed防御）
        scrub_exc = exc

    if scrub_exc is not None:
        try:
            _logger.error(
                "sentry_before_send_drop_event",
                error_type=type(scrub_exc).__qualname__,
                error_module=type(scrub_exc).__module__,
                event_id=event_dict.get("event_id"),
            )
        except Exception:  # noqa: BLE001
            # ロガー自体が失敗した場合のフォールバック（_safe_log_warningはフォールバック専用）
            _safe_log_warning(
                "sentry_before_send_drop_event",
                error_type=type(scrub_exc).__qualname__,
                error_module=type(scrub_exc).__module__,
            )
        # emit 呼び出しを try/exceptで保護する
        # _emit_scrub_failure_to_sentry は内部でシステム異常 (MemoryError/RecursionError) を
        # re-raise する設計（emit 自身の except Exception による隠蔽回避のため）。その re-raise が
        # ここで未捕捉のまま伝播すると下方の return None を飛び越え、scrubbing 失敗イベントの
        # fail-closed ドロップが Sentry SDK の capture_internal_exceptions 挙動に依存してしまう。
        # 呼び出し側で全 Exception を捕捉して return None を保証することで、本関数の
        # `except (MemoryError, RecursionError)` 節が行う return None と一貫した fail-closed を
        # SDK 非依存で確定させる。
        # KeyboardInterrupt / SystemExit は BaseException 直系のため捕捉せず伝播させる。
        try:
            _emit_scrub_failure_to_sentry(scrub_exc, event_id=event_dict.get("event_id"))
        except Exception:  # noqa: BLE001
            try:
                print(
                    "[SENTRY_SCRUB_FAILED] emit failed; event dropped (fail-closed)",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception:  # noqa: BLE001, S110
                pass
        return None

    return event
