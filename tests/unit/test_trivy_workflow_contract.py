"""Trivy reusable workflow の静的契約テスト."""

from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

pytestmark = [pytest.mark.unit, pytest.mark.repo_contract]

CALLER_JOB_IDS = ("pr-trivy-scan", "post-trivy-scan")
CALLER_PERMISSIONS = {"contents": "read", "security-events": "write"}
IMAGE_TAG = "api-test-devops:scan"

# scan/gate 4 ステップと、それぞれに期待する scan-type。ステップ ID 一覧の単一真実源で、
# 各テストはこの dict を回す。ID を 3 箇所の literal で持つと、ステップ追加時に
# 片方だけ更新して新ステップが無検証のまま素通りする経路が生まれるため集約する。
TRIVY_SCAN_TYPES = {
    "fs-scan": "fs",
    "fs-gate": "fs",
    "image-scan": "image",
    "image-gate": "image",
}
FS_SCAN_REF = "."


def _load_yaml(path: str, request: pytest.FixtureRequest) -> dict[str, Any]:
    data = yaml.safe_load((request.config.rootpath / path).read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"{path} の YAML 構造が不正: type={type(data)}"
    return data


def _workflow_on(data: dict[Any, Any]) -> dict[str, Any]:
    on_section = data.get("on", data.get(True))
    assert isinstance(on_section, dict), f"workflow on section が不正: type={type(on_section)}"
    return on_section


@pytest.fixture
def ci_workflow(request: pytest.FixtureRequest) -> dict[str, Any]:
    return _load_yaml(".github/workflows/ci.yml", request)


@pytest.fixture
def trivy_workflow(request: pytest.FixtureRequest) -> dict[str, Any]:
    return _load_yaml(".github/workflows/trivy-scan.yml", request)


@pytest.fixture
def trivy_steps(trivy_workflow: dict[str, Any]) -> dict[str, Any]:
    """id をキーに引けるようにして、step の並び順に依存しない参照を全テストへ提供する。

    id を持たない step は落とすため、必須 step から id が外れると参照側が KeyError で
    落ちる。step の本数ではなく id の実在で契約を固定でき、step 追加では壊れない。
    """
    return {
        step["id"]: step for step in trivy_workflow["jobs"]["trivy-scan"]["steps"] if "id" in step
    }


def test_reusable_trivy_workflow_call_contract(trivy_workflow: dict[str, Any]) -> None:
    workflow_call = _workflow_on(trivy_workflow).get("workflow_call")
    assert isinstance(workflow_call, dict), "trivy-scan.yml は workflow_call で公開する必要がある"

    inputs = workflow_call.get("inputs")
    assert isinstance(inputs, dict), "workflow_call inputs が定義されていない"
    assert inputs["scan-prefix"] == {"required": True, "type": "string"}
    assert inputs["scan-image"] == {"required": True, "type": "boolean"}


def test_reusable_trivy_job_name_permissions_and_verify_action(
    trivy_workflow: dict[str, Any],
) -> None:
    jobs = trivy_workflow.get("jobs")
    assert isinstance(jobs, dict), "trivy-scan.yml に jobs が無い"

    job = jobs["trivy-scan"]
    assert job["name"] == "Trivy scan"
    assert job["runs-on"] == "ubuntu-latest"
    assert job["timeout-minutes"] == 20
    assert job["permissions"] == CALLER_PERMISSIONS

    steps = job["steps"]
    verify_steps = [
        step for step in steps if step.get("uses") == "./.github/actions/trivy-sarif-verify"
    ]
    assert len(verify_steps) == 2, (
        "filesystem/image の 2 箇所で local verify action を使う必要がある"
    )


def test_reusable_trivy_scan_and_gate_contract(
    trivy_workflow: dict[str, Any],
    trivy_steps: dict[str, Any],
) -> None:
    for step_id in TRIVY_SCAN_TYPES:
        assert trivy_steps[step_id]["with"]["scanners"] == "vuln,secret"

    assert trivy_steps["fs-scan"]["with"]["exit-code"] == "0"
    assert trivy_steps["fs-scan"]["with"]["format"] == "sarif"
    assert trivy_steps["verify-fs-scan"]["with"] == {
        "sarif-file": "trivy-${{ inputs.scan-prefix }}-fs-scan.sarif",
        "scan-type": "filesystem",
    }
    assert trivy_steps["fs-gate"]["with"]["exit-code"] == "1"
    assert trivy_steps["fs-gate"]["with"]["severity"] == "CRITICAL,HIGH"
    assert "exit 1" in next(
        step["run"]
        for step in trivy_workflow["jobs"]["trivy-scan"]["steps"]
        if step.get("name", "").startswith("Fail job if fs vulnerabilities")
    )

    assert trivy_steps["image-scan"]["with"]["exit-code"] == "0"
    assert trivy_steps["image-scan"]["with"]["format"] == "sarif"
    assert trivy_steps["verify-image-scan"]["with"] == {
        "sarif-file": "trivy-${{ inputs.scan-prefix }}-image-scan.sarif",
        "scan-type": "image",
    }
    assert trivy_steps["image-gate"]["with"]["exit-code"] == "1"
    assert trivy_steps["image-gate"]["with"]["severity"] == "CRITICAL,HIGH"
    assert "exit 1" in next(
        step["run"]
        for step in trivy_workflow["jobs"]["trivy-scan"]["steps"]
        if step.get("name", "").startswith("Fail job if image vulnerabilities")
    )


def test_reusable_trivy_security_settings_are_pinned(trivy_steps: dict[str, Any]) -> None:
    """走査範囲と抑制設定を固定し、ゲートが黙って弱くなる変更を検知する。

    これらは `scanners` や `exit-code` と違い、緩めてもジョブは緑のまま通る。
    prod 依存に脆弱性が無い状態では退行が永久に顕在化しないため、
    「チェックが実行されなかった」と「合格した」を区別できるのは本テストだけになる。
    """
    for step_id, expected_scan_type in TRIVY_SCAN_TYPES.items():
        with_block = trivy_steps[step_id].get("with", {})
        env_block = trivy_steps[step_id].get("env", {})
        assert with_block.get("scan-type") == expected_scan_type, (
            f"{step_id}: scan-type は期待されたスキャン種別である必要がある: "
            f"{with_block.get('scan-type')!r}"
        )

        # trivyignores はカンマ区切りで複数パスを取れる。完全一致で固定しないと
        # `.trivyignore,.trivyignore-lax` のような追記で任意の CVE を抑制できてしまう。
        assert with_block.get("trivyignores") == ".trivyignore", (
            f"{step_id}: 抑制ファイルは .trivyignore 単体に限定する: "
            f"{with_block.get('trivyignores')!r}"
        )

        # 脆弱性 DB の供給元。trivy の既定 (mirror.gcr.io / ghcr.io) ではなく ECR ミラーを
        # 明示指定しているため、値を書き換えても既定へのフォールバックは起きない。到達可能な
        # 攻撃者管理レジストリへ差し替えられると、空の DB を配って全スキャンを 0 件にできる。
        assert env_block.get("TRIVY_DB_REPOSITORY") == "public.ecr.aws/aquasecurity/trivy-db", (
            f"{step_id}: 脆弱性 DB は指定の ECR ミラーを指す必要がある: "
            f"{env_block.get('TRIVY_DB_REPOSITORY')!r}"
        )

        # YAML の裸の true は bool になるため "true" 文字列と比較してはならない。
        # 修正版のある脆弱性だけをゲート対象にするノイズ抑制方針を固定する。
        assert with_block.get("ignore-unfixed") is True, (
            f"{step_id}: ignore-unfixed は真偽値 True である必要がある: "
            f"{with_block.get('ignore-unfixed')!r}"
        )

    # filesystem 側だけに課す契約。走査対象と走査範囲の両方を固定する。
    for step_id in ("fs-scan", "fs-gate"):
        # npm の devDependencies は filesystem 側だけ走査対象に含める。この env が消えるか
        # 綴りを誤ると trivy は未知の TRIVY_* を黙って無視し、npm 走査が no-op に戻る。
        env_block = trivy_steps[step_id].get("env", {})
        assert env_block.get("TRIVY_INCLUDE_DEV_DEPS") == "true", (
            f"{step_id}: npm devDependencies を走査対象に含める必要がある: "
            f"{env_block.get('TRIVY_INCLUDE_DEV_DEPS')!r}"
        )

        # scan-ref はリポジトリ全体に固定する。狭められても trivy は成功で終わるため
        # ジョブは緑のまま通り、package-lock.json が対象外に落ちて直上の
        # TRIVY_INCLUDE_DEV_DEPS 契約が黙って no-op 化する。
        assert trivy_steps[step_id].get("with", {}).get("scan-ref") == FS_SCAN_REF, (
            f"{step_id}: filesystem の走査範囲はリポジトリ全体に固定する: "
            f"{trivy_steps[step_id].get('with', {}).get('scan-ref')!r}"
        )

    # image 側に付けないのは意図的。Dockerfile は npm 成果物を COPY しないため no-op になる。
    # 付いていたら「イメージにも npm 依存が入った」か「意図の取り違え」のどちらかで、
    # どちらも本テストの前提が崩れているので気付けるようにする。
    for step_id in ("image-scan", "image-gate"):
        assert "TRIVY_INCLUDE_DEV_DEPS" not in trivy_steps[step_id].get("env", {}), (
            f"{step_id}: image スキャンに npm 依存は存在しないため設定しない"
        )


def test_reusable_trivy_action_owner_is_pinned(trivy_steps: dict[str, Any]) -> None:
    """スキャナ本体の供給元を固定する。

    `uses` の owner を書き換えると、CI ランナー上で SARIF 書き込み権限を
    持ったまま任意のリポジトリのコードが走る。SHA でピンされている限り
    zizmor の unpinned-uses は通過してしまい、他に検知手段が無い。

    SHA まで固定しないのは意図的。ピン形式の検査は zizmor が担っており、
    ここで SHA を縛ると Dependabot の更新ごとに本テストが落ちる。
    """
    for step_id in TRIVY_SCAN_TYPES:
        assert trivy_steps[step_id]["uses"].startswith("aquasecurity/trivy-action@"), (
            f"{step_id}: trivy-action は公式リポジトリを指す必要がある: "
            f"{trivy_steps[step_id]['uses']!r}"
        )


def test_reusable_trivy_verify_steps_are_cancellable(trivy_steps: dict[str, Any]) -> None:
    # verify ステップに always() が混入すると、ワークフローキャンセル時も実行され続けて
    # キャンセルが即座に効かなくなる（GitHub 公式が非推奨とする挙動）。過去に fs 側だけ
    # !cancelled() へ移行して image 側が always() のまま取り残された経緯があるため、
    # 両ステップを対称に固定して再発を防ぐ。
    for step_id in ("verify-fs-scan", "verify-image-scan"):
        condition = trivy_steps[step_id]["if"]
        assert "!cancelled()" in condition, (
            f"{step_id} はキャンセル即応のため !cancelled() を使う必要がある: {condition}"
        )
        assert "always()" not in condition, (
            f"{step_id} の always() はキャンセルを遅延させるため禁止: {condition}"
        )


def test_reusable_trivy_buildx_cache_contract(trivy_workflow: dict[str, Any]) -> None:
    steps = trivy_workflow["jobs"]["trivy-scan"]["steps"]

    buildx_step = next(
        step for step in steps if step.get("uses", "").startswith("docker/setup-buildx-action@")
    )
    assert buildx_step["if"] == "${{ inputs.scan-image }}"

    build_step = next(step for step in steps if step.get("id") == "docker-build")
    assert build_step["uses"].startswith("docker/build-push-action@")
    assert build_step["if"] == "${{ inputs.scan-image }}"
    assert build_step["with"]["cache-from"] == "type=gha,scope=api-test-runtime"
    # cache-to は「未設定」であることが契約。ci.yml の publish-image / compose-healthcheck が
    # 同一 scope の唯一の writer で、ここが書くと PR 経由の cache poisoning 経路になる。
    assert "cache-to" not in build_step["with"]
    # セキュリティゲートは常に最新の OS パッケージでスキャンする必要があるため、
    # no-cache: true でキャッシュ再利用を止める。上の cache-from は no-cache が
    # 外れた場合の再利用先を示すもので、no-cache と対で解釈する。
    assert build_step["with"]["no-cache"] is True


def test_compose_healthcheck_no_cache_targets_publish_branch_only(
    ci_workflow: dict[str, Any],
) -> None:
    """no-cache は main push のみ。cache-to は push 全体で継続する（非対称の契約）。

    鮮度を消費するのは main push 限定の publish-image だけなので、no-cache を
    main に絞りビルド時間の重複を避ける。develop push の apt 層鮮度検証は
    post-trivy-scan (no-cache: true) が別途担う。cache-to を push 全体に残す
    のは PR 側の cache-from 読み取り元を維持するためで、両者の条件が異なる
    ことは意図的である（詳細: docs/adr/0005-ci-cache-freshness-vs-build-time.md）。
    """
    steps = ci_workflow["jobs"]["compose-healthcheck"]["steps"]
    build_step = next(step for step in steps if step.get("name") == "Build app(runtime) image")

    non_pr = "github.event_name != 'pull_request'"
    assert build_step["with"]["no-cache"] == "${{ github.ref == 'refs/heads/main' }}"
    assert build_step["with"]["cache-to"] == (
        f"${{{{ {non_pr} && 'type=gha,mode=max,scope=api-test-runtime' || '' }}}}"
    )


def test_publish_image_consumes_healthcheck_freshened_cache(ci_workflow: dict[str, Any]) -> None:
    """公開側が「鮮度の契約」の受け手であることを固定する。

    compose-healthcheck 側の no-cache/cache-to だけでは保証は閉じない。
    publish-image が (1) compose-healthcheck の完了を待ち、(2) 同一 scope から
    読む、の両方を満たして初めて「公開イメージが新鮮なレイヤに基づく」が成立する。
    どちらかが欠けても既存 assert は緑のまま保証だけが失われるため、ここで固定する。
    """
    publish_job = ci_workflow["jobs"]["publish-image"]
    assert "compose-healthcheck" in publish_job["needs"]

    steps = publish_job["steps"]
    build_step = next(step for step in steps if step.get("name") == "Build and push runtime image")
    assert build_step["with"]["cache-from"] == "type=gha,scope=api-test-runtime"
    # publish-image 自身も同一 scope の writer。ADR-0005 は writer が 2 つある前提で
    # 保証範囲を書いているため、ここが変わると ADR の記述が実態から外れる。
    assert build_step["with"]["cache-to"] == "type=gha,mode=max,scope=api-test-runtime"
    # ADR-0005 が arm64 を保証対象外とするのは、公開が multi-arch なのに対し
    # 鮮度を作る compose-healthcheck が runner ネイティブの単一 arch だけを
    # ビルドするという非対称に依存する。ここが単一 arch になれば非保証の前提が
    # 消え、逆に healthcheck 側が multi-arch 化すれば非保証を撤回できる。
    assert build_step["with"]["platforms"] == "linux/amd64,linux/arm64"


def test_api_test_runtime_scope_writers_are_exhaustive(
    ci_workflow: dict[str, Any],
    trivy_workflow: dict[str, Any],
) -> None:
    """api-test-runtime scope へ書き込む job を全列挙で固定する。

    writer が増えると ADR-0005 の鮮度保証（どの job のレイヤが公開されるか）が
    黙って崩れる。個別 job の assert は「増えた writer」を検知できないため、
    両 workflow を走査して writer 集合そのものを契約にする。
    """
    scope = "scope=api-test-runtime"
    writers = {
        f"{workflow_name}:{job_id}"
        for workflow_name, workflow in (("ci", ci_workflow), ("trivy-scan", trivy_workflow))
        for job_id, job in workflow["jobs"].items()
        if isinstance(job, dict)
        for step in job.get("steps", [])
        if scope in str(step.get("with", {}).get("cache-to", ""))
    }
    assert writers == {"ci:compose-healthcheck", "ci:publish-image"}


def test_reusable_trivy_image_tag_is_consistent(
    trivy_workflow: dict[str, Any],
    trivy_steps: dict[str, Any],
) -> None:
    """build / image-scan / image-gate / cleanup が同一タグを指すことを固定する。

    不一致は scan-image が true の実行（main 宛 PR と push）でしか露見せず、
    通常の PR では skip されるため CI が緑のまま潜伏する。
    """
    steps = trivy_workflow["jobs"]["trivy-scan"]["steps"]

    tag = trivy_steps["docker-build"]["with"]["tags"]
    assert tag == IMAGE_TAG
    assert trivy_steps["image-scan"]["with"]["image-ref"] == IMAGE_TAG
    assert trivy_steps["image-gate"]["with"]["image-ref"] == IMAGE_TAG

    cleanup = next(step for step in steps if step.get("name") == "Clean up Docker image")
    assert IMAGE_TAG in cleanup["run"]


def test_trivy_callers_are_job_level_boundaries_only(ci_workflow: dict[str, Any]) -> None:
    jobs = ci_workflow["jobs"]

    pr_job = jobs["pr-trivy-scan"]
    assert pr_job["name"] == "PR Trivy scan"
    assert pr_job["if"] == "github.event_name == 'pull_request'"
    assert pr_job["permissions"] == CALLER_PERMISSIONS
    assert pr_job["uses"] == "./.github/workflows/trivy-scan.yml"
    assert pr_job["with"] == {
        "scan-prefix": "pr",
        "scan-image": (
            "${{ github.base_ref == 'main' || "
            "contains(github.event.pull_request.labels.*.name, 'docker') }}"
        ),
    }

    post_job = jobs["post-trivy-scan"]
    assert post_job["name"] == "Post Trivy Scan"
    assert post_job["if"] == (
        "github.event_name == 'push' && (github.ref == 'refs/heads/main' "
        "|| github.ref == 'refs/heads/develop')"
    )
    assert post_job["permissions"] == CALLER_PERMISSIONS
    assert post_job["uses"] == "./.github/workflows/trivy-scan.yml"
    assert post_job["with"] == {"scan-prefix": "post", "scan-image": True}

    for job_id in CALLER_JOB_IDS:
        job = jobs[job_id]
        assert set(job) <= {"name", "if", "permissions", "uses", "with"}
        assert "steps" not in job
        assert "runs-on" not in job


def test_status_report_keeps_required_trivy_job_ids(ci_workflow: dict[str, Any]) -> None:
    needs = ci_workflow["jobs"]["status-report"]["needs"]
    assert "pr-trivy-scan" in needs
    assert "post-trivy-scan" in needs
