from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sys

import pytest

from app.artifact_contracts import atomic as atomic_module
from app.artifact_contracts.atomic import file_sha256
from app.artifact_contracts.environment import finalize_environment_fingerprint
from app.artifact_contracts.registry import (
    LATEST_ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
)
from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.scenario import finalize_scenario
from app.campaign_exchange import (
    CampaignExchangeError,
    MergeRejectedError,
    create_worker_assignment,
    export_worker_results,
    merge_worker_results,
    prepare_worker_campaign_copy,
    run_worker_assignment,
    validate_assignment_set,
    validate_merged_results,
    validate_worker_assignment,
    validate_worker_transfer,
)
from app.campaign_exchange.assignments import (
    ASSIGNMENT_HASH_EXCLUSIONS,
    assignment_environment_hashes,
)
from app.campaign_exchange import common as exchange_common
from app.campaign_exchange.common import atomic_copy_tree, atomic_write_json, content_hash
from app.campaign_executor.executor import CampaignExecutor
from app.campaign_executor.planner import plan_campaign
from app.campaign_executor.state import CampaignStateStore
from app.cli.main import build_parser


TOOL_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = TOOL_ROOT.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage2"
COMMIT_A = "a" * 40
COMMIT_B = "b" * 40
CREATED = datetime(2032, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_exchange_json_publication_retries_transient_windows_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "preflight.json"
    atomic_write_json(target, {"value": "old"})
    original_replace = atomic_module.os.replace
    attempts = 0

    def access_denied_once(source: Path, destination: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            error = PermissionError("simulated Windows access denial")
            error.winerror = 5
            raise error
        original_replace(source, destination)

    monkeypatch.setattr(atomic_module.os, "replace", access_denied_once)
    atomic_write_json(target, {"value": "new"})

    assert attempts == 2
    assert json.loads(target.read_text(encoding="utf-8")) == {"value": "new"}
    assert not list(tmp_path.glob("*.tmp-*"))


def test_exchange_tree_publication_retries_transient_windows_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "result.json").write_text('{"valid": true}\n', encoding="utf-8")
    original_replace = exchange_common.os.replace
    attempts = 0

    def access_denied_once(source_path: Path, destination_path: Path) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            error = PermissionError("simulated Windows directory access denial")
            error.winerror = 5
            raise error
        original_replace(source_path, destination_path)

    monkeypatch.setattr(exchange_common.os, "replace", access_denied_once)
    atomic_copy_tree(source, destination)

    assert attempts == 2
    assert (destination / "result.json").read_text(encoding="utf-8") == '{"valid": true}\n'
    assert not list(tmp_path.glob("*.tmp-*"))


def _scenario(
    repetition: int,
    *,
    dataset: str = "cmu_arctic",
    component_name: str = "fixture_asr",
) -> dict[str, object]:
    value = json.loads(
        (FIXTURES / "golden_scenario_source.json").read_text(encoding="utf-8")
    )
    identity = json.loads(
        (FIXTURES / "golden_manifest_identity.json").read_text(encoding="utf-8")
    )
    value["benchmark_manifest"] = {**identity, "path": "golden_manifest.parquet"}
    value["repetition"] = repetition
    value["dataset_slice"]["dataset"] = dataset
    component = value["pipeline"]["components"]["asr"]
    component["name"] = component_name
    component["config_contents"]["name"] = component_name
    component["config_contents_sha256"] = canonical_sha256(component["config_contents"])
    result = finalize_scenario(value)
    result["artifact_contract"] = {
        "schema_version": "scenario-artifact-requirements.v1",
        "scenario_type": "synthetic_executor",
        "capabilities": [],
    }
    return result


def _plan(
    tmp_path: Path,
    scenarios: list[dict[str, object]],
    *,
    campaign_id: str = "campaign_stage6test",
    registry: ArtifactRegistry | None = None,
) -> Path:
    catalog_root = tmp_path / "catalog"
    catalog_root.mkdir(parents=True)
    shutil.copy2(FIXTURES / "golden_manifest.parquet", catalog_root / "golden_manifest.parquet")
    catalog = catalog_root / "resolved_scenarios.jsonl"
    catalog.write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in reversed(scenarios)),
        encoding="utf-8",
    )
    return plan_campaign(
        scenario_catalog=catalog,
        automated_runs_root=tmp_path / "automated_runs",
        campaign_id=campaign_id,
        created_at=CREATED,
        registry=registry,
    ).campaign_root


def _assignment(
    campaign_root: Path,
    worker_id: str,
    **kwargs: object,
) -> tuple[dict[str, object], Path]:
    value = create_worker_assignment(
        campaign_root,
        worker_id=worker_id,
        expected_git_commit=str(kwargs.pop("expected_git_commit", COMMIT_A)),
        expected_environment_profile=str(
            kwargs.pop("expected_environment_profile", "test_only_contract")
        ),
        created_at=CREATED,
        **kwargs,
    )
    return value, campaign_root / "worker_assignments" / f"worker_{worker_id}.yaml"


def _execute(campaign_root: Path, worker_id: str, scenario_ids: list[str]) -> None:
    def command(lease, scenario_root: Path) -> list[str]:
        return [
            sys.executable,
            "-u",
            "-m",
            "app.campaign_executor.synthetic_worker",
            "--scenario-root",
            str(scenario_root),
            "--behavior",
            "success",
        ]

    result = CampaignExecutor(
        campaign_root,
        project_root=PROJECT_ROOT,
        worker_id=worker_id,
        command_builder=command,
        lease_seconds=2.0,
        heartbeat_seconds=0.2,
        minimum_free_disk_bytes=0,
        telemetry_enabled=False,
    ).run(scenario_ids=scenario_ids)
    assert result.succeeded == len(scenario_ids)


def _fingerprint(
    assignment: dict[str, object],
    *,
    machine: str,
    package_version: str = "1.0",
    commit: str | None = None,
    profile: str | None = None,
    corrupt_models: bool = False,
) -> dict[str, object]:
    model_hashes, component_hashes = assignment_environment_hashes(assignment)
    if corrupt_models:
        model_hashes = dict(model_hashes)
        model_hashes[next(iter(model_hashes))] = "F" * 64
    freeze = [{"name": "fixture", "version": package_version}]
    value = {
        "schema_version": "environment-fingerprint.v1",
        "captured_at_utc": "2032-01-02T03:04:05.000000Z",
        "git": {
            "commit": commit or assignment["expected_git_commit"],
            "dirty": False,
            "changed_path_count": 0,
        },
        "os": {
            "system": "Windows",
            "release": "fixture",
            "version": "fixture",
            "machine": machine,
        },
        "python": {
            "executable": f"C:\\Python-{machine}\\python.exe",
            "version": "3.12.0",
            "implementation": "CPython",
        },
        "packages": {
            "profile_identity": profile or assignment["expected_environment_profile"],
            "freeze": freeze,
            "freeze_sha256": canonical_sha256(freeze),
        },
        "hardware": {
            "cpu": f"CPU-{machine}",
            "logical_cpu_count": 8,
            "ram_bytes": 16 * 1024**3,
        },
        "accelerator": {
            "gpus": [{"index": "0", "name": f"GPU-{machine}", "uuid": machine}],
            "driver": "fixture",
            "cuda_runtime": None,
        },
        "model_hashes": model_hashes,
        "component_config_hashes": component_hashes,
        "clock": {
            "timezone_name": "UTC",
            "utc_offset_seconds": 0,
            "wall_clock": "fixture",
            "wall_clock_resolution_sec": 1e-06,
            "monotonic_clock": "fixture",
            "monotonic_resolution_sec": 1e-06,
        },
    }
    return finalize_environment_fingerprint(value)


def _export(
    campaign_root: Path,
    assignment: dict[str, object],
    assignment_path: Path,
    destination: Path,
    *,
    machine: str,
    package_version: str = "1.0",
) -> dict[str, object]:
    return export_worker_results(
        campaign_root,
        assignment_path,
        destination,
        environment_fingerprint=_fingerprint(
            assignment, machine=machine, package_version=package_version
        ),
        actual_git_commit=COMMIT_A,
        actual_environment_profile="test_only_contract",
        created_at=CREATED,
    )


def _scenarios(count: int = 8) -> list[dict[str, object]]:
    return [
        _scenario(
            index + 1,
            dataset="cmu_arctic" if index % 2 == 0 else "librispeech",
            component_name="fixture_asr" if index % 3 else "fixture_asr_alt",
        )
        for index in range(count)
    ]


def test_two_worker_partition_is_deterministic_nonoverlapping_and_complete(
    tmp_path: Path,
) -> None:
    root = _plan(tmp_path, _scenarios(12))
    first, _ = _assignment(root, "amir", partition_index=0, partition_count=2)
    second, _ = _assignment(root, "friend", partition_index=1, partition_count=2)
    assert set(first["scenario_ids"]).isdisjoint(second["scenario_ids"])
    manifest = json.loads((root / "campaign_manifest.json").read_text(encoding="utf-8"))
    assert set(first["scenario_ids"]) | set(second["scenario_ids"]) == set(
        manifest["scenario_ids"]
    )
    report = validate_assignment_set(root)
    assert report["missing_scenario_ids"] == []
    assert report["overlaps"] == []


def test_worker_assignment_accepts_current_campaign_registry(tmp_path: Path) -> None:
    root = _plan(
        tmp_path,
        _scenarios(2),
        registry=ArtifactRegistry.load_version(LATEST_ARTIFACT_REGISTRY_VERSION),
    )
    manifest = json.loads((root / "campaign_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifact_registry_version"] == LATEST_ARTIFACT_REGISTRY_VERSION

    assignment, assignment_path = _assignment(root, "amir")

    assert assignment_path.is_file()
    assert assignment["scenario_ids"] == manifest["scenario_ids"]
    assert validate_worker_assignment(root, assignment_path)["valid"] is True


def test_assignment_supports_all_selectors_and_stable_cap(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios())
    manifest = json.loads((root / "campaign_manifest.json").read_text(encoding="utf-8"))
    start, end = manifest["scenario_ids"][0], manifest["scenario_ids"][-1]
    assignment, _ = _assignment(
        root,
        "selector",
        scenario_range=(start, end),
        component_filters={"asr": "fixture_asr"},
        datasets=["cmu_arctic"],
        panels=["controlled_clean"],
        maximum_scenario_count=2,
    )
    assert 1 <= len(assignment["scenario_ids"]) <= 2
    assert assignment["scenario_ids"] == sorted(assignment["scenario_ids"])


def test_assignment_rejects_nonexistent_and_unapproved_overlap(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(3))
    scenario_id = json.loads((root / "campaign_manifest.json").read_text())["scenario_ids"][0]
    with pytest.raises(CampaignExchangeError, match="unknown requested"):
        _assignment(root, "missing", scenario_ids=["scenario_000000000000"])
    _assignment(root, "first", scenario_ids=[scenario_id])
    with pytest.raises(CampaignExchangeError, match="overlaps"):
        _assignment(root, "second", scenario_ids=[scenario_id])


def test_bilateral_reproducibility_overlap_is_explicit(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(2))
    scenario_id = json.loads((root / "campaign_manifest.json").read_text())["scenario_ids"][0]
    _assignment(root, "first", scenario_ids=[scenario_id], allow_overlap=True)
    _assignment(root, "second", scenario_ids=[scenario_id], allow_overlap=True)
    report = validate_assignment_set(root)
    assert report["overlaps"][0]["allowed"] is True


def test_assignment_detects_commit_profile_seed_and_model_mismatch(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(3))
    assignment, path = _assignment(root, "amir", maximum_scenario_count=2)
    with pytest.raises(CampaignExchangeError, match="Git commit"):
        validate_worker_assignment(root, path, actual_git_commit=COMMIT_B)
    with pytest.raises(CampaignExchangeError, match="environment profile"):
        validate_worker_assignment(root, path, actual_environment_profile="wrong")

    tampered = deepcopy(assignment)
    tampered["seed"] = 999
    digest = content_hash(tampered, ASSIGNMENT_HASH_EXCLUSIONS)
    tampered["assignment_sha256"] = digest
    tampered["assignment_id"] = f"assignment_{digest[:12].lower()}"
    with pytest.raises(CampaignExchangeError, match="seed mismatch"):
        validate_worker_assignment(root, tampered)

    tampered = deepcopy(assignment)
    tampered["identity_catalog"]["models"].pop(next(iter(tampered["identity_catalog"]["models"])))
    digest = content_hash(tampered, ASSIGNMENT_HASH_EXCLUSIONS)
    tampered["assignment_sha256"] = digest
    tampered["assignment_id"] = f"assignment_{digest[:12].lower()}"
    with pytest.raises(CampaignExchangeError, match="identities mismatch"):
        validate_worker_assignment(root, tampered)


def test_assignment_set_rejects_mismatched_expected_commits(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(4))
    ids = json.loads((root / "campaign_manifest.json").read_text())["scenario_ids"]
    _assignment(root, "first", scenario_ids=ids[:2], expected_git_commit=COMMIT_A)
    _assignment(root, "second", scenario_ids=ids[2:], expected_git_commit=COMMIT_B)
    with pytest.raises(CampaignExchangeError, match="different Git commits"):
        validate_assignment_set(root)


def test_assignment_resume_requeues_only_that_workers_stopped_scenarios(
    tmp_path: Path, monkeypatch
) -> None:
    root = _plan(tmp_path, _scenarios(2))
    scenario_ids = json.loads((root / "campaign_manifest.json").read_text())["scenario_ids"]
    assignment, assignment_path = _assignment(
        root,
        "amir",
        scenario_ids=[scenario_ids[0]],
    )
    state = CampaignStateStore(root / "database" / "campaign.sqlite")
    for scenario_id in scenario_ids:
        state.request_stop(
            "campaign_stage6test",
            scenario_id=scenario_id,
            reason="operator pause",
        )

    captured: dict[str, object] = {}

    class FakeExecutor:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def run(self, *, scenario_ids, max_scenarios, dry_run):
            captured["scenario_ids"] = scenario_ids
            captured["dry_run"] = dry_run
            return object()

    monkeypatch.setattr("app.campaign_exchange.execution.CampaignExecutor", FakeExecutor)
    monkeypatch.setattr(
        "app.campaign_exchange.execution.current_git_commit",
        lambda _root: COMMIT_A,
    )
    run_worker_assignment(
        root,
        assignment_path,
        project_root=PROJECT_ROOT,
        environment_profile="test_only_contract",
        resume_stopped=True,
        telemetry_enabled=False,
    )

    assert captured["scenario_ids"] == tuple(assignment["scenario_ids"])
    assert state.scenario("campaign_stage6test", scenario_ids[0]).state == "pending"
    assert state.scenario("campaign_stage6test", scenario_ids[1]).state == "stopped"


@pytest.mark.parametrize(
    ("fingerprint_kwargs", "message"),
    [
        ({"commit": COMMIT_B}, "Git commit"),
        ({"profile": "wrong"}, "profile"),
        ({"corrupt_models": True}, "model identities"),
    ],
)
def test_export_rejects_mismatched_execution_identity(
    tmp_path: Path, fingerprint_kwargs: dict[str, object], message: str
) -> None:
    root = _plan(tmp_path, _scenarios(1))
    assignment, path = _assignment(root, "amir")
    _execute(root, "amir", assignment["scenario_ids"])
    with pytest.raises(CampaignExchangeError, match=message):
        export_worker_results(
            root,
            path,
            tmp_path / "bad_transfer",
            environment_fingerprint=_fingerprint(
                assignment, machine="A", **fingerprint_kwargs
            ),
            created_at=CREATED,
        )


def test_complete_two_worker_split_run_transfer_and_merge(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(6))
    first, first_path = _assignment(root, "amir", partition_index=0, partition_count=2)
    second, second_path = _assignment(root, "friend", partition_index=1, partition_count=2)
    friend_root = tmp_path / "friend_checkout" / root.name
    copy_report = prepare_worker_campaign_copy(root, second_path, friend_root)
    assert copy_report["database_mode"] == "independent_local_copy"
    friend_assignment = friend_root / "worker_assignments" / second_path.name
    _execute(root, "amir", first["scenario_ids"])
    _execute(friend_root, "friend", second["scenario_ids"])
    transfer_a = tmp_path / "transfer_a"
    transfer_b = tmp_path / "transfer_b"
    _export(root, first, first_path, transfer_a, machine="A", package_version="1.0")
    _export(
        friend_root,
        second,
        friend_assignment,
        transfer_b,
        machine="B",
        package_version="1.1",
    )
    report = merge_worker_results(root, [transfer_a, transfer_b], created_at=CREATED)
    assert report["status"] == "accepted_with_warnings"
    assert report["missing_scenario_ids"] == []
    assert {item["field"] for item in report["environment_differences"]} >= {
        "package_freeze_sha256",
        "hardware",
    }
    assert validate_merged_results(root)["scenario_count"] == 6
    analysis = json.loads((root / "analysis" / "analysis_input_index.json").read_text())
    assert len(analysis["scenario_results"]) == 6
    assert not any((transfer_a / "database").glob("*"))


@pytest.mark.parametrize("mutation", ["missing", "corrupt"])
def test_transfer_detects_missing_files_and_checksum_corruption(
    tmp_path: Path, mutation: str
) -> None:
    root = _plan(tmp_path, _scenarios(1))
    assignment, path = _assignment(root, "amir")
    _execute(root, "amir", assignment["scenario_ids"])
    transfer = tmp_path / "transfer"
    _export(root, assignment, path, transfer, machine="A")
    runner_log = transfer / "scenarios" / assignment["scenario_ids"][0] / "logs" / "runner.log"
    if mutation == "missing":
        runner_log.unlink()
    else:
        runner_log.write_text("modified", encoding="utf-8")
    with pytest.raises(CampaignExchangeError, match="incomplete or modified"):
        validate_worker_transfer(transfer, campaign_root=root)


def test_partial_completed_transfer_merges_and_reports_missing_work(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(3))
    assignment, path = _assignment(root, "amir")
    _execute(root, "amir", assignment["scenario_ids"][:1])
    transfer = tmp_path / "partial_transfer"
    manifest = _export(root, assignment, path, transfer, machine="A")
    assert len(manifest["unexported_scenarios"]) == 2
    report = merge_worker_results(root, [transfer], created_at=CREATED)
    assert len(report["missing_scenario_ids"]) == 2


def test_byte_identical_duplicate_is_recognized(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(1))
    assignment, path = _assignment(root, "amir")
    _execute(root, "amir", assignment["scenario_ids"])
    transfer = tmp_path / "transfer"
    clone = tmp_path / "transfer_clone"
    _export(root, assignment, path, transfer, machine="A")
    shutil.copytree(transfer, clone)
    report = merge_worker_results(root, [transfer, clone], created_at=CREATED)
    assert report["duplicates"][0]["classification"] == "byte_identical_duplicate"
    assert report["conflicts"] == []


def test_merge_recovers_byte_identical_unindexed_publication(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(1))
    assignment, path = _assignment(root, "amir")
    _execute(root, "amir", assignment["scenario_ids"])
    transfer = tmp_path / "transfer"
    _export(root, assignment, path, transfer, machine="A")
    scenario_id = assignment["scenario_ids"][0]
    target = root / "analysis" / "merged_results" / "scenarios" / scenario_id
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(transfer / "scenarios" / scenario_id, target)

    report = merge_worker_results(root, [transfer], created_at=CREATED)

    assert report["conflicts"] == []
    assert any(
        item["classification"] == "byte_identical_interrupted_publication"
        for item in report["duplicates"]
    )
    assert validate_merged_results(root)["scenario_count"] == 1


def test_conflicting_duplicate_is_rejected_without_overwrite(tmp_path: Path) -> None:
    scenarios = _scenarios(1)
    root_a = _plan(tmp_path / "a", scenarios)
    root_b = _plan(tmp_path / "b", scenarios)
    first, first_path = _assignment(root_a, "amir", allow_overlap=True)
    second, second_path = _assignment(root_b, "friend", allow_overlap=True)
    _execute(root_a, "amir", first["scenario_ids"])
    _execute(root_b, "friend", second["scenario_ids"])

    scenario_root = root_b / "scenarios" / second["scenario_ids"][0]
    runner_log = scenario_root / "logs" / "runner.log"
    runner_log.write_text(runner_log.read_text(encoding="utf-8") + "friend-marker\n", encoding="utf-8")
    checksums_path = scenario_root / "checksums.json"
    checksums = json.loads(checksums_path.read_text(encoding="utf-8"))
    checksums["entries"]["logs/runner.log"]["bytes"] = runner_log.stat().st_size
    checksums["entries"]["logs/runner.log"]["sha256"] = file_sha256(runner_log)
    checksums_path.write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf-8")

    transfer_a = tmp_path / "conflict_a"
    transfer_b = tmp_path / "conflict_b"
    _export(root_a, first, first_path, transfer_a, machine="A")
    _export(root_b, second, second_path, transfer_b, machine="B")
    with pytest.raises(MergeRejectedError):
        merge_worker_results(root_a, [transfer_a, transfer_b], created_at=CREATED)
    report = json.loads((root_a / "analysis" / "merge_validation_report.json").read_text())
    assert report["status"] == "rejected"
    assert report["conflicts"][0]["classification"] == "conflicting_duplicate"
    assert not (root_a / "analysis" / "merged_results" / "merged_result_index.json").exists()


def test_long_transfer_path_remains_portable_in_indexes(tmp_path: Path) -> None:
    root = _plan(tmp_path, _scenarios(1))
    assignment, path = _assignment(root, "amir")
    _execute(root, "amir", assignment["scenario_ids"])
    transfer = tmp_path / ("long_" + "x" * 60) / ("nested_" + "y" * 60)
    _export(root, assignment, path, transfer, machine="A")
    assert validate_worker_transfer(transfer, campaign_root=root)["valid"] is True
    merge_worker_results(root, [transfer], created_at=CREATED)
    index = json.loads(
        (root / "analysis" / "merged_results" / "merged_result_index.json").read_text()
    )
    assert "\\" not in index["scenario_results"][0]["relative_path"]
    assert str(tmp_path) not in json.dumps(index)


def test_assignment_status_reports_only_the_selected_worker(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scenarios = _scenarios(2)
    root = _plan(tmp_path, scenarios)
    assignment, assignment_path = _assignment(
        root,
        "amir",
        scenario_ids=[str(scenarios[0]["scenario_id"])],
    )
    _execute(root, "amir", assignment["scenario_ids"])
    capsys.readouterr()
    args = build_parser().parse_args(
        [
            "campaign",
            "status",
            "--campaign-root",
            str(root),
            "--assignment",
            str(assignment_path),
        ]
    )

    args.func(args)

    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "worker-assignment-status-summary.v1"
    assert report["assignment_id"] == assignment["assignment_id"]
    assert report["worker_id"] == "amir"
    assert report["total_scenarios"] == 1
    assert report["complete_scenarios"] == 1
    assert report["remaining_scenarios"] == 0
    assert report["state_counts"] == {"succeeded": 1}
    assert report["stop_requested"] is False
    assert report["stop_reason"] is None


def test_stage6_cli_and_public_schemas_are_available() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "campaign",
            "assign",
            "--campaign-root",
            "automated_runs/campaign_example",
            "--worker-id",
            "amir",
            "--environment-profile",
            "test_only_contract",
            "--partition-index",
            "0",
            "--partition-count",
            "2",
        ]
    )
    assert args.campaign_action == "assign"
    for name in (
        "worker_assignment.v1.schema.json",
        "worker_result_transfer.v1.schema.json",
        "merged_result_index.v1.schema.json",
        "merge_validation_report.v1.schema.json",
        "analysis_input_index.v1.schema.json",
    ):
        value = json.loads(
            (TOOL_ROOT / "configs" / "automated_evaluation" / "schemas" / name).read_text()
        )
        assert value["$id"].endswith(".v1")
