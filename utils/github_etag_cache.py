"""GitHub REST API ETag / Conditional Requests キャッシュ"""

import itertools
import re
from typing import Any
from urllib.parse import quote, urlencode

import httpx
from structlog.typing import FilteringBoundLogger

from utils.github_error_handler import GitHubAPIError
from utils.logger import get_logger

# モジュールレベル logger: ``@staticmethod`` (例: ``_cache_key``) など
# ``self.logger`` を参照できない経路で構造化ログを出力するために使用する
# （structlog のため同名 logger を返し、インスタンス側 ``self.logger`` と一貫。PR#347 #2-6）。
_module_logger = get_logger(__name__)

# ETag形式バリデーション（RFC 9110 §8.8.3 準拠: W/"..." または "..."、
# etagc = %x21 / %x23-7E / obs-text (%x80-FF)。HTAB・DEL・U+0100 等を拒否する）
_ETAG_PATTERN: re.Pattern[str] = re.compile(r'^(?:W/)?"[\x21\x23-\x7e\x80-\xff]*"$')

# cache_invariant_violation logger.error 出力時のキーリスト上限件数 (PII漏洩防止)
_MAX_CACHE_INVARIANT_LOG_KEYS = 5


class GitHubETagCache:
    """ETag / データキャッシュの排他所有クラス（Conditional Requests 対応）

    ``_etag_cache`` / ``_data_cache`` の 2 dict と上限管理を単一クラスに集約し、
    書込 API を本クラスに限定することで状態所有権を型で強制する
    （facade ``AsyncGitHubClient`` はインスタンス保持と委譲のみ）。
    asyncio シングルスレッド環境での利用を前提とし、ロックは持たない。
    """

    def __init__(
        self,
        max_cache_entries: int = 256,
        *,
        logger: FilteringBoundLogger,
    ) -> None:
        """GitHubETagCacheの初期化

        Args:
            max_cache_entries: ETag/dataキャッシュの最大エントリ数（デフォルト256）
            logger: 構造化ログ出力先（facade と同一 logger を共有しログ文脈を一貫させる）

        Raises:
            ValueError: max_cache_entries が 1 未満
        """
        if max_cache_entries < 1:
            raise ValueError("max_cache_entries must be >= 1")
        self.max_cache_entries = max_cache_entries
        self._etag_cache: dict[str, str] = {}  # cache_key (endpoint+sorted query) -> ETag
        # cache_key -> response data（304レスポンス時のキャッシュ返却用）
        self._data_cache: dict[str, dict[str, Any] | list[dict[str, Any]]] = {}
        self.logger = logger

    def _prepare_headers(self, cache_key: str) -> dict[str, str]:
        """ETagキャッシュが存在する場合に If-None-Match ヘッダーを含む dict を返す。"""
        headers: dict[str, str] = {}
        if cache_key in self._etag_cache:
            headers["If-None-Match"] = self._etag_cache[cache_key]
        return headers

    def _handle_304_response(self, cache_key: str) -> dict[str, Any] | list[dict[str, Any]]:
        """304 Not Modified: キャッシュデータを返却する。キャッシュミス時はエラー。"""
        if cache_key in self._data_cache:
            return self._data_cache[cache_key]
        # キャッシュミス時（理論上発生しない: ETagあり=キャッシュあり）
        # Fail-fast: キャッシュ不整合は実装バグの証拠
        # endpoint_only: クエリパラメータを除去してデバッグ可能性を確保しつつ機密パラメータを非露出
        endpoint_only = cache_key.split("?")[0]
        self.logger.error(
            "cache_miss_on_304",
            endpoint=endpoint_only,
            hint="ETag存在時のキャッシュミスは実装バグ",
            etag=self._etag_cache.get(cache_key),
        )
        raise GitHubAPIError(
            f"Cache inconsistency: 304 response without cached data for {endpoint_only}"
        )

    def _update_etag_cache(
        self,
        cache_key: str,
        response: httpx.Response,
        result_json: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        """ETagとデータキャッシュを同時更新する。

        asyncio シングルスレッド環境のため競合は発生しない。

        挿入順序（挿入前退避方式）:
          1. 既存キーを both dict から削除して挿入順を更新する。
          2. _enforce_cache_limit(reserve=1) で挿入前に退避し、新規 1 件分の余地を確保する。
          3. data→ETag の順で保存する（挿入後も上限を超えない, PR#347 review #9）。

        例外発生時は「dataあり/ETagなし」の一時状態になりうるが、ETagなしなら次回は
        通常リクエスト（304非使用）となり安全に回復する。
        「ETagあり/dataなし」はETagが最後に書き込まれるため物理的に発生しない。
        """
        if "ETag" in response.headers:
            etag = response.headers["ETag"]
            # ETag形式バリデーション（RFC 9110 §8.8.3 準拠: W/"..." または "..."）
            if not _ETAG_PATTERN.match(etag):
                # 無効ETag受信時は既存キャッシュを破棄（次回リクエストで304再利用を防止）。
                # pop を logger より先に実行: logger が例外を送出しても（呼び出し元
                # github_client 側で抑制される）キャッシュ無効化を必ず保証する
                # （_enforce_cache_limit の PR#347 B-3 fail-closed と同一方針）。
                self._etag_cache.pop(cache_key, None)
                self._data_cache.pop(cache_key, None)
                self.logger.warning(
                    "invalid_etag_format",
                    endpoint=cache_key.split("?")[0],
                    etag_prefix=etag[:20] if len(etag) > 20 else etag,
                )
                return
            self._etag_cache.pop(cache_key, None)
            self._data_cache.pop(cache_key, None)
            # 挿入前に reserve=1 で退避し、挿入後もエントリ数が max_cache_entries を
            # 超えないようにする。挿入後 enforce では瞬間的に max+1 件になるため、
            # 新規エントリ 1 件分の余地を空けてから挿入する (PR#347 review #9)。
            self._enforce_cache_limit(reserve=1)
            self._data_cache[cache_key] = result_json
            self._etag_cache[cache_key] = etag
        else:
            # pop を logger より先に実行するため、削除前に存在有無を退避する
            # （logger 例外時もキャッシュ無効化を保証。2a と同一方針）。
            had_cached_entry = cache_key in self._etag_cache or cache_key in self._data_cache
            self._etag_cache.pop(cache_key, None)
            self._data_cache.pop(cache_key, None)
            if had_cached_entry:
                self.logger.info("etag_removed", endpoint=cache_key.split("?")[0])

    @staticmethod
    def _cache_key(endpoint: str, params: dict[str, str | int] | None = None) -> str:
        """エンドポイントとクエリパラメータからキャッシュキーを生成する。

        params が None または空の場合は endpoint をそのまま返す。
        params={} は httpx の仕様（空クエリ = クエリなし）に従い、
        params=None と同一のキャッシュキーを生成する。
        params がある場合は ``endpoint?key1=val1&key2=val2`` 形式で返す。
        URLエンコードには ``quote_via=quote`` を使用する（スペースは ``%20``）。
        パラメータはキーでソートされ決定論的なキーを生成する。

        Args:
            endpoint: APIエンドポイントパス（例: ``/users/octocat/repos``）。
            params: クエリパラメータ辞書（None可）

        Returns:
            キャッシュキー文字列
        """
        if not params:
            return endpoint
        try:
            sorted_params = sorted((k, str(v)) for k, v in params.items())
            return f"{endpoint}?{urlencode(sorted_params, quote_via=quote)}"
        except (TypeError, UnicodeEncodeError) as e:
            # PR#347 review #4-[8]: 通常パスの try/except 外で実行されるため、
            # 例外型のみ含む GitHubAPIError に変換して呼び出し元のリトライ/エラー
            # ハンドリング体系に統合。params 値は PII 含有可能性があるため
            # ``from None`` で例外チェーンを切断し、エラーメッセージに含めない。
            # 観測可能性のため endpoint と例外型のみを構造化ログに記録する。
            # params の値は記録しない（PII 非露出。PR#347 #2-6）。
            _module_logger.warning(
                "cache_key_build_failed",
                endpoint=endpoint,
                error_type=type(e).__name__,
            )
            raise GitHubAPIError(
                f"cache_key build failed for endpoint={endpoint!r}: {type(e).__name__}"
            ) from None

    def _enforce_cache_limit(self, reserve: int = 0) -> None:
        """ETag/dataキャッシュを ``max_cache_entries - reserve`` 以下に保つ。

        Args:
            reserve: 直後に挿入する新規エントリ数の予約枠（デフォルト 0）。
                ``_update_etag_cache`` は挿入前に ``reserve=1`` で呼び出すことで、
                挿入後もエントリ数が ``max_cache_entries`` を超えない（瞬間的な
                max+1 を防止, PR#347 review #9）。``max_cache_entries >= 1``
                かつ ``reserve in (0, 1)`` のため退避目標は常に 0 以上。

        _update_etag_cache は _etag_cache と _data_cache を常にペアで書き込むため、
        _etag_cache のみを基準に古いエントリを削除すれば両キャッシュの整合性が保たれる。

        Invariant 違反検出時は logger.error + 両キャッシュ clear で safe-fallback する。
        ``assert`` 文は ``python -O`` モードで silent disable されるため production では使わない。

        Invariant 判定は ``dict.keys()`` の集合等価比較 (defense-in-depth)。
        ``len`` だけでは「同件数だがキー集合が異なる」状態 (例: 1 件抜けて 1 件余分) を
        検出できないため、set-equality でキー差異も検出する。
        """
        # O(1) fast path before O(n) set comparison:
        # サイズが異なれば invariant 違反確定
        # （同件数だがキー集合が異なる場合は下記 set-equality で検出）。
        invariant_violated = (
            len(self._etag_cache) != len(self._data_cache)
            or self._etag_cache.keys() != self._data_cache.keys()
        )
        if invariant_violated:
            # PII漏洩防止 (PR#347 review #3-2): キーパスは GitHub API endpoint
            # (例: /users/octocat, /repos/owner/name) を含み、SENSITIVE_KEYS の
            # redact 対象外。logger.error → Sentry 送信時のログ肥大・PII露出を
            # 抑えるため _MAX_CACHE_INVARIANT_LOG_KEYS 件に制限する。
            # query string は split("?")[0] で除去済み。
            etag_only_cache_keys = self._etag_cache.keys() - self._data_cache.keys()
            data_only_cache_keys = self._data_cache.keys() - self._etag_cache.keys()
            etag_only_count = len(etag_only_cache_keys)
            data_only_count = len(data_only_cache_keys)
            etag_only_keys = sorted(k.split("?")[0] for k in etag_only_cache_keys)[
                :_MAX_CACHE_INVARIANT_LOG_KEYS
            ]
            data_only_keys = sorted(k.split("?")[0] for k in data_only_cache_keys)[
                :_MAX_CACHE_INVARIANT_LOG_KEYS
            ]
            # 通常フローでは発生しない。発生した場合は実装バグの兆候として
            # Sentry に捕捉される logger.error を出力し、両キャッシュを clear して
            # 次回リクエストの fresh fetch に倒す（user request flow は維持）。
            try:
                self.logger.error(
                    "cache_invariant_violation",
                    etag_cache_size=len(self._etag_cache),
                    data_cache_size=len(self._data_cache),
                    etag_only_keys=etag_only_keys,
                    data_only_keys=data_only_keys,
                    etag_only_keys_truncated=etag_only_count > _MAX_CACHE_INVARIANT_LOG_KEYS,
                    data_only_keys_truncated=data_only_count > _MAX_CACHE_INVARIANT_LOG_KEYS,
                    action="cleared_both_caches",
                )
            except Exception:  # noqa: BLE001, S110
                # logger 自体が例外を投げても両キャッシュ clear を必ず実行する。
                # clear をスキップすると invariant 違反が継続し、外側 _update_etag_cache の
                # except に etag_cache_update_failed として埋没する（PR#347 B-3 fail-closed）。
                pass
            self._etag_cache.clear()
            self._data_cache.clear()
            return  # clear() によりサイズ 0 → max_cache_entries 制限は達成済み（while ループ不要）
        excess = len(self._etag_cache) - (self.max_cache_entries - reserve)
        if excess > 0:
            # 削除件数を事前計算し islice でまとめて取得（毎反復 len() 再計算を回避, PR#347）。
            keys_to_evict = list(itertools.islice(self._etag_cache, excess))
            for key in keys_to_evict:
                self._etag_cache.pop(key, None)
                self._data_cache.pop(key, None)
            self.logger.info(
                "cache_entries_evicted",
                evicted_count=excess,
                current_size=len(self._etag_cache),
                max_size=self.max_cache_entries,
            )
