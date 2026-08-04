"""ci.yml の zizmor fail-closed ゲートの運用契約テスト."""

import re
from typing import Any

import pytest
import yaml

# Module-level marker: 外部プロセスを起動せず ci.yml の YAML 構造のみを検証するため unit。
# このマーカーを欠くと CI の `-m "(unit or integration) and not external"` から漏れ、
# ゲートを守るはずの本ファイル自身が無音で実行されなくなる。
# repo_contract: request.config.rootpath 経由でリポジトリ全体を静的検査するため、
# ビルドコンテキストが絞られた test コンテナでは走らせない（pyproject.toml の marker 定義参照）
pytestmark = [pytest.mark.unit, pytest.mark.repo_contract]

# zizmor の非ゼロ終了 (exit 11-14) を無効化する引数。--no-exit-codes は zizmor --help の
# "Disable all error codes besides success and tool failure"、--format sarif は findings を
# SARIF へ流して終了コードを立てず、--fix は違反そのものを自動書き換えで消す。
EXIT_CODE_SUPPRESSING_ARGS = ("--no-exit-codes", "--fix", "--format sarif")

# 監査設定を差し込み severity を remap しうる引数。zizmor 1.29.0 は git リポジトリ内では
# リポジトリルートと .github/ から zizmor.yml を自動探索する (非 git ディレクトリでは発火せず、
# ここを取り違えると「設定は読まれない」という誤った結論になる)。よって --config / ZIZMOR_CONFIG /
# 設定ファイル実在 / --no-config 脱落 の 4 経路すべてを塞ぐ必要がある。
CONFIG_LOADING_ARGS = ("--config", "-c")

# 監査 step の run に現れてはならないシェルのコマンド区切り。GitHub Actions 公式ドキュメント
# の通り、既定 shell (`bash --noprofile --norc -eo pipefail {0}`) は `-e` に加え `-o pipefail`
# も適用する。実測 (bash -e -o pipefail、GitHub Actions の既定を再現):
#   `false | cat` / `false | tee x` / `false ; true` / 改行 + `true` はいずれも exit 1 で安全。
#   -e がパイプライン全体・逐次実行の失敗を検知するため、後続コマンドの成功で握り潰されない。
#   唯一の真の fail-open は `false &`（バックグラウンド実行）で exit 0 になる。`-e` はバック
#   グラウンドジョブの失敗を検知できないため、シェルオプションに関係なく握り潰される。
# それでも `|` / `;` / 改行を禁止に含めるのは、上記の安全性が defaults.run.shell によるシェル
# 上書き（test_audit_step_uses_default_shell で別途禁止）に依存する前提付きの安全性だから。
# 「区切り文字を 1 つも含まない単一コマンド」という閉じた文法条件にしておけば、シェル上書き
# ガードが将来欠けても、あるいは `|| echo skipped` のような未知の組み合わせが来ても、この
# 契約テスト単体で防御が成立する。`||` は `|` に、`&&` は `&` に含まれるため個別列挙は不要。
RUN_COMMAND_SEPARATORS = ("|", "&", ";", "\n")

# ゲートの挙動を外部から変える環境変数。token 系は online audit を有効化してゲート結果を
# ネットワーク状態に依存させ、ZIZMOR_CONFIG は severity remap を注入する。
FORBIDDEN_ENV_NAMES = ("GH_TOKEN", "GITHUB_TOKEN", "ZIZMOR_GITHUB_TOKEN", "ZIZMOR_CONFIG")

# ci.yml は --no-config で自動探索を止めているが、そのフラグが外れた瞬間に remap が効く。
# 設定ファイルの不在を独立に固定し、フラグ脱落と設定ファイル追加の二重防御にする。
# 網羅範囲は zizmor 1.29.0 で実測済み。High 検出 1 件 (exit 14) の workflow に対し
# severity remap を仕込むと、root と .github/ は exit 0 に反転する (= 攻撃経路)。
# 一方 .github/workflows/ は --strict-collection が workflow として収集を試みて exit 1
# (fail-closed)、.github/actions/ は探索対象外で exit 14 のまま。下の 4 パスで過不足ない。
ZIZMOR_CONFIG_PATHS = ("zizmor.yml", "zizmor.yaml", ".github/zizmor.yml", ".github/zizmor.yaml")

# 監査 step に固定するフラグ。--no-config と --strict-collection は脱落が実測で fail-open に
# なる (前者は zizmor.yml 自動探索が復活して severity remap を許し、後者は解析不能ファイルが
# 混在すると exit 0 に落ちる)。残り 3 つは脱落しても fail-open にはならないが、ゲートの契約
# そのものなので無断改変を落とす。
REQUIRED_AUDIT_ARGS = (
    "--offline",
    "--no-config",
    "--strict-collection",
    "--persona regular",
    "--min-severity high",
)

# 監査対象パス。片方が外れると .github/actions 配下の composite action が無検査で通る。
REQUIRED_AUDIT_PATHS = (".github/workflows", ".github/actions")

# ゲートが所属すべき job。PR をブロックする required status check はこの job だけ。
AUDIT_JOB = "pr-validation"

# job-level if はゲートの実行条件そのもの。GitHub は skip された job を required check の
# 成功として扱うため、条件を改変すれば「PR は緑のまま監査ゼロ」が成立する。値ごと固定する。
AUDIT_JOB_IF = "github.event_name == 'pull_request'"

# zizmor 公式の抑止コメント (docs/usage.md)。監査される側の workflow 行に置くだけで、
# ci.yml も設定ファイルも変更せずに個別の High 検出を消せる (実測 exit 14 → 0)。
# Issue #557 が定義する 4 層 (Actions / Shell / Tool / Config) のいずれにも該当しない第 5 の
# 経路であり、ゲート step の文字列一致では原理的に見えない。
# `zizmor:ignore` (空白なし) は zizmor に認識されない (実測 exit 14) が、検出漏れより
# 過検出のほうが安全なため両形式にマッチさせる。
INLINE_IGNORE_PATTERN = re.compile(r"zizmor:\s*ignore")


def _normalize(run: str) -> str:
    """`--flag=value` と `--flag value` を同一視する。

    両形式とも zizmor が受け付けるため、= 形式だけを見る素朴な部分文字列判定は
    `--format sarif` を取りこぼしてゲート無効化を素通しする。
    末尾に空白を足し、最終トークンの引数名も境界付きで判定できるようにする。
    """
    return " ".join(run.replace("=", " ").split()) + " "


class TestZizmorGateContract:
    @pytest.fixture
    def ci_workflow(self, request: pytest.FixtureRequest) -> dict[str, Any]:
        """pytest rootpath 基準で解決し、テストファイル移動によるパス破損を防ぐ。"""
        ci_path = request.config.rootpath / ".github" / "workflows" / "ci.yml"
        data = yaml.safe_load(ci_path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"ci.yml の構造が不正: type={type(data)}, path={ci_path}"
        assert isinstance(data.get("jobs"), dict), f"ci.yml に jobs が無い: path={ci_path}"
        return data

    @pytest.fixture
    def audit_steps(self, ci_workflow: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
        """zizmor で実監査を行う step を (job名, step) で返す。--version 表示 step は除く。"""
        return [
            (job_name, step)
            for job_name, job in ci_workflow["jobs"].items()
            for step in job.get("steps", [])
            if "zizmor" in step.get("run", "") and "--version" not in step.get("run", "")
        ]

    def test_audit_step_exists(self, audit_steps: list[tuple[str, dict[str, Any]]]) -> None:
        """他の不在 assert が空集合に対して vacuous pass するのを防ぐアンカー。

        ゲート step の削除・改名・composite action への移動・zizmor 呼び出しの変数化を
        ここで落とす。step の本数ではなく「監査が1件以上ある」を固定するため、
        step 追加では壊れない。
        """
        assert audit_steps, (
            "ci.yml に zizmor の監査 step が存在しない。"
            "ゲートが削除されたか、run から zizmor 呼び出しが消えている。"
        )

    def test_audit_step_has_no_fail_open(
        self, audit_steps: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """step 層の fail-open (continue-on-error / if / shell 握り潰し / 終了コード抑止) を禁じる。

        step-level if はゲートを無音でスキップさせる純粋なキルスイッチで、正当な用途が無い。
        job-level if は PR 限定実行という本来の役割を持つため、ここではなく
        test_audit_job_if_condition_is_pinned で値ごと固定する。

        shell 層は「区切り文字ゼロの単一コマンド」を要求することで塞ぐ。zizmor 以外の
        コマンドが step に存在しなければ、終了コードを決めるのは zizmor しか残らない。
        """
        for job_name, step in audit_steps:
            where = f"{job_name} / {step.get('name')!r}"
            assert "continue-on-error" not in step, f"{where}: continue-on-error でゲートが無効化"
            assert "if" not in step, f"{where}: step-level if でゲートが無音スキップされる"

            run = step["run"].strip()
            for separator in RUN_COMMAND_SEPARATORS:
                assert separator not in run, (
                    f"{where}: run に区切り {separator!r} があり、単一コマンドではない。"
                    "zizmor の終了コードが step の結果になることを保証できない "
                    "(`&&` のように実際は伝播する区切りも含めて一律禁止している。"
                    "例外を設けると判定が『安全な組み合わせの列挙』に戻り、"
                    "`| tee` や `|| echo` のような未知の組み合わせを取りこぼすため)"
                )

            normalized = _normalize(run)
            for arg in EXIT_CODE_SUPPRESSING_ARGS:
                assert arg not in normalized, f"{where}: {arg} が zizmor の終了コードを抑止する"

    def test_audit_step_uses_default_shell(
        self,
        ci_workflow: dict[str, Any],
        audit_steps: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """既定 shell を固定する。単一コマンドの終了コード伝播が既定挙動に依るため。

        カスタム shell は `command [options] {0} [more_options]` というテンプレートで、
        runner が {0} を一時スクリプトのパスに置換して実行する (GitHub 公式 workflow syntax)。
        つまり run を 1 文字も変えずに、shell 側だけで終了コードを握り潰す余地がある。
        さらに shell は workflow / job の defaults.run 経由でも上書きでき、その場合 step を
        見ても気付けない。env と同じく 3 階層すべてで未設定を固定する。
        """
        for job_name, step in audit_steps:
            where = f"{job_name} / {step.get('name')!r}"
            defaults_sources = (
                ("workflow の defaults.run", ci_workflow.get("defaults")),
                ("job の defaults.run", ci_workflow["jobs"][job_name].get("defaults")),
            )
            for label, defaults in defaults_sources:
                shell = ((defaults or {}).get("run") or {}).get("shell")
                assert shell is None, f"{where}: {label} で shell が {shell!r} に上書きされている"
            assert "shell" not in step, (
                f"{where}: step で shell が {step.get('shell')!r} に上書きされている。"
                f"カスタム shell は run を変えずに終了コードを握り潰せる"
            )

    def test_audit_step_loads_no_external_config(
        self, audit_steps: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """設定ファイルの読み込みを禁じる。severity remap で high 検出を exit 0 に落とせるため。"""
        for job_name, step in audit_steps:
            normalized = _normalize(step["run"])
            for arg in CONFIG_LOADING_ARGS:
                assert f"{arg} " not in normalized, (
                    f"{job_name} / {step.get('name')!r}: {arg} で severity remap を注入可能"
                )

    def test_audit_job_has_no_fail_open(
        self,
        ci_workflow: dict[str, Any],
        audit_steps: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """job 層の continue-on-error を禁じる。

        step 側が健全でも、job に1行足すだけでゲート全体が非ブロッキング化するため分けて固定する。
        """
        for job_name in {job_name for job_name, _ in audit_steps}:
            assert "continue-on-error" not in ci_workflow["jobs"][job_name], (
                f"{job_name}: job レベル continue-on-error でゲート全体が非ブロッキング化"
            )

    def test_audit_step_env_is_clean(
        self,
        ci_workflow: dict[str, Any],
        audit_steps: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """workflow / job / step の 3 階層すべてで禁止環境変数と --gh-token を塞ぐ。

        workflow レベル env は全 step へ伝播するため、step だけ見ると注入を見逃す。
        """
        workflow_env = set(ci_workflow.get("env") or {})
        for job_name, step in audit_steps:
            where = f"{job_name} / {step.get('name')!r}"
            env_keys = (
                workflow_env
                | set(ci_workflow["jobs"][job_name].get("env") or {})
                | set(step.get("env") or {})
            )
            for name in FORBIDDEN_ENV_NAMES:
                assert name not in env_keys, f"{where}: env に {name} が注入されている"
            assert "--gh-token" not in step["run"], f"{where}: --gh-token が渡されている"

    def test_audit_step_runs_in_pr_validation(
        self, audit_steps: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """PR をブロックしない job への移設を禁じる。

        required status check は pr-validation だけなので、同じ if を持つ新設 job へ
        移すだけで「監査は走るが PR は止まらない」状態を作れる。
        """
        for job_name, step in audit_steps:
            assert job_name == AUDIT_JOB, (
                f"{job_name} / {step.get('name')!r}: 監査が {AUDIT_JOB} の外にある。"
                f"required check 対象外の job では PR をブロックできない"
            )

    def test_audit_step_keeps_required_args(
        self, audit_steps: list[tuple[str, dict[str, Any]]]
    ) -> None:
        """必須フラグと監査対象パスの脱落を禁じる."""
        for job_name, step in audit_steps:
            where = f"{job_name} / {step.get('name')!r}"
            normalized = _normalize(step["run"])
            for arg in REQUIRED_AUDIT_ARGS:
                assert f"{arg} " in normalized, f"{where}: {arg} が欠落している"
            for path in REQUIRED_AUDIT_PATHS:
                assert f"{path} " in normalized, f"{where}: 監査対象 {path} が外れている"

    def test_audit_job_if_condition_is_pinned(
        self,
        ci_workflow: dict[str, Any],
        audit_steps: list[tuple[str, dict[str, Any]]],
    ) -> None:
        """job-level if の改変を禁じる。

        `&& false` の連結や schedule への差し替えで job ごと skip させると、GitHub は
        skip を required check の成功として扱うため、PR は緑のまま監査が一度も走らない。
        step 側の健全性では防げないので値ごと固定する。
        """
        for job_name in {job_name for job_name, _ in audit_steps}:
            actual = ci_workflow["jobs"][job_name].get("if")
            assert actual == AUDIT_JOB_IF, (
                f"{job_name}: job-level if が {actual!r} に改変されている "
                f"(期待: {AUDIT_JOB_IF!r})。job が skip されるとゲートが無音化する"
            )

    def test_audited_paths_have_no_inline_ignore(self, request: pytest.FixtureRequest) -> None:
        """監査対象内のインライン抑止コメントを禁じる。

        ゲート step 自体が健全でも、監査される側の workflow に 1 行足すだけで High 検出を
        個別に消せる。step の文字列一致では原理的に見えないため独立して固定する。
        検査範囲を REQUIRED_AUDIT_PATHS から導出し、監査対象の増減に追従させる。
        """
        found: list[str] = []
        for audit_path in REQUIRED_AUDIT_PATHS:
            root = request.config.rootpath / audit_path
            targets = sorted(root.rglob("*.yml")) + sorted(root.rglob("*.yaml"))
            # rglob は存在しないディレクトリでも例外を出さず空を返す。監査パスが改名・削除
            # されると「0 件を検査して合格」という無音の骨抜きが成立するため件数を固定する。
            assert targets, f"監査対象 {audit_path} に yaml が 1 件も無い。パスが失われている"
            for path in targets:
                for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if INLINE_IGNORE_PATTERN.search(line):
                        found.append(f"{path.relative_to(request.config.rootpath)}:{lineno}")
        assert not found, (
            f"インライン抑止が High 検出を個別に無効化しうる: {found}。"
            "正当な false positive の場合は本テストに allowlist を追加し、"
            "抑止する理由と再評価時期をコメントで明記すること"
        )

    def test_no_zizmor_config_file(self, request: pytest.FixtureRequest) -> None:
        """将来版が自動探索に対応した場合に備え、設定ファイルの実在を禁じる。"""
        found = [path for path in ZIZMOR_CONFIG_PATHS if (request.config.rootpath / path).exists()]
        assert not found, f"zizmor 設定ファイルが severity remap を持ちうる: {found}"
