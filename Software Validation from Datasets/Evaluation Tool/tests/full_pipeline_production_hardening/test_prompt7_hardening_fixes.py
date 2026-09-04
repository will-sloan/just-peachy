from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import wave

import pytest
import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_demo.presets import PresetCatalog
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_production_hardening import (
    ANCHOR_PIPELINES,
    MATRIX_PATH,
    PROMPT5_MARKER,
    PROMPT6_MARKER,
    PROMPT7_MARKER,
    RUNTIME_PATH,
    TOOL_ROOT,
    scope_fields,
)
from app.full_pipeline_production_hardening.cli import _material_paths
from app.full_pipeline_production_hardening.gate import _wav_metadata
from app.full_pipeline_production_hardening.health import health
from app.full_pipeline_production_hardening.packaging import (
    _compact_zip,
    validate_compact_package,
)
from app.full_pipeline_production_hardening.plan import build_acceptance_plan
from app.full_pipeline_production_hardening.reporting import (
    _validate_advisory_run_budget,
    _validate_completed_state,
)
from app.full_pipeline_production_hardening.runner import (
    _command,
    _latest_pass,
    _run_budget,
)
from app.full_pipeline_production_hardening.selection import select_candidates


CHALLENGER = "fullpipe_v1_ao_dw_iw"


def test_unknown_only_challenger_is_ranked_but_never_selected(
    tmp_path: Path,
) -> None:
    candidates = (*ANCHOR_PIPELINES, CHALLENGER)
    summary = tmp_path / "all18_finalist_summary.csv"
    resources = tmp_path / "serial_resources.csv"
    _csv(
        summary,
        [
            {
                "pipeline_id": pipeline,
                "wrong_known_time_sec": 0 if pipeline == CHALLENGER else 1,
                "stranger_false_known_time_sec": 0 if pipeline == CHALLENGER else 1,
                "speaker_attributed_wer": 0 if pipeline == CHALLENGER else 0.2,
                "correctly_named_known_rate": 1 if pipeline == CHALLENGER else 0.8,
                "failure_rate": 0,
                "total_rtf": 0.2,
            }
            for pipeline in candidates
        ],
    )
    _csv(
        resources,
        [
            {
                "pipeline_id": pipeline,
                "total_rtf": 0.2,
                "peak_rss_bytes": 100,
                "model_bytes": 100,
                "startup_sec": 1,
                "model_worker_count": 1,
            }
            for pipeline in candidates
        ],
    )
    bindings = {pipeline: _anchor_binding(pipeline) for pipeline in ANCHOR_PIPELINES}
    bindings[CHALLENGER] = {
        **_anchor_binding(CHALLENGER),
        "binding_status": "EXCLUDED_UNRESOLVED_COMMON_DEMO_GALLERY_BINDING",
        "production_role_eligible": False,
        "frozen_anchor": False,
        "exclusion_reason": "exact gallery binding unavailable",
    }
    result = select_candidates(
        candidate_ids=candidates,
        evidence_files={summary.name: summary, resources.name: resources},
        runtime_bindings=bindings,
    )
    assert CHALLENGER not in set(result["roles"].values())
    row = next(row for row in result["candidates"] if row["pipeline_id"] == CHALLENGER)
    assert row["reliability_eligible"] is True
    assert row["production_role_eligible"] is False
    assert row["unknown_only_policy_executed"] is False


def test_plan_uses_explicit_virtual_live_source_not_file_mode(tmp_path: Path) -> None:
    pipeline = ANCHOR_PIPELINES[0]
    binding = _anchor_binding(pipeline)
    source = {
        "input_id": "long",
        "path": str(tmp_path / "long.wav"),
        "sha256": "a" * 64,
        "duration_sec": 3600,
        "roles": [
            "deterministic_replay",
            "controlled_loopback",
            "repeated_session",
            "soak",
        ],
    }
    enrollment = [
        {
            "input_id": f"enroll-{index}",
            "path": str(tmp_path / f"enroll-{index}.wav"),
            "sha256": f"{index}" * 64,
            "duration_sec": 10,
            "roles": ["enrollment_sample"],
        }
        for index in range(1, 4)
    ]
    plan = build_acceptance_plan(
        workspace_root=tmp_path,
        selection={
            "roles": {"PRIMARY": pipeline},
            "candidates": [
                {
                    "pipeline_id": pipeline,
                    "production_role_eligible": True,
                    "runtime_binding": binding,
                }
            ],
        },
        hardening_inputs={"inputs": [source, *enrollment]},
    )
    task = next(row for row in plan["tasks"] if row["kind"] == "controlled_loopback")
    assert task["source_mode"] == "controlled_virtual_loopback"
    assert task["physical_microphone_claimed"] is False
    command, expected_nonzero, interrupt_after = _command(
        task,
        attempt_root=tmp_path / "attempt",
        workspace_root=tmp_path,
    )
    joined = " ".join(command)
    assert "controlled-virtual-loopback" in joined
    assert "app.full_pipeline_demo file" not in joined
    assert expected_nonzero is False
    assert interrupt_after is None


def test_wav_metadata_is_decoded_and_fake_riff_is_rejected(tmp_path: Path) -> None:
    valid = tmp_path / "valid.wav"
    with wave.open(str(valid), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b"\0\0" * 1600)
    metadata = _wav_metadata(valid)
    assert metadata["duration_sec"] == pytest.approx(0.1)
    assert metadata["codec"] == "PCM_S16LE"
    fake = tmp_path / "fake.wav"
    fake.write_bytes(b"RIFFsynthetic")
    with pytest.raises(RuntimeError, match="WAV is invalid"):
        _wav_metadata(fake)


def test_common_demo_overlay_is_hash_bound_and_primary_is_default(
    tmp_path: Path,
) -> None:
    primary = ANCHOR_PIPELINES[1]
    overlay = tmp_path / "overlay.yaml"
    value = {
        "schema_version": "full-pipeline-common-demo-production-overlay.v1",
        **scope_fields(),
        "status": "PASS",
        "roles": {"PRIMARY": primary, "FALLBACK": None, "ALTERNATIVE": None},
        "default_pipeline_id": primary,
        "presets": [{"pipeline_id": primary, "software_ready": True}],
    }
    overlay.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
    digest = sha256_file(overlay)
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    catalog = PresetCatalog(
        matrix,
        production_overlay_path=overlay,
        production_overlay_sha256=digest,
    )
    assert catalog.default_preset_id == primary
    assert catalog.production_role(primary) == "PRIMARY"
    overlay.write_text(
        overlay.read_text(encoding="utf-8") + "# tamper\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="SHA-256 differs"):
        PresetCatalog(
            matrix,
            production_overlay_path=overlay,
            production_overlay_sha256=digest,
        )


def test_health_is_degraded_before_validated_completion() -> None:
    automated = TOOL_ROOT / "automated_runs"
    automated.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=automated) as raw:
        value = health(workspace_root=Path(raw))
    assert value["status"] == "DEGRADED"
    assert value["state"] == "NOT_STARTED"


def test_nominal_twelve_hours_is_never_an_elapsed_kill_switch(tmp_path: Path) -> None:
    value = _run_budget(tmp_path)
    value["started_at_utc"] = (
        (datetime.now(timezone.utc) - timedelta(days=30))
        .isoformat()
        .replace("+00:00", "Z")
    )
    write_json_atomic(tmp_path / "run_budget.json", value)
    reopened = _run_budget(tmp_path)
    assert reopened["elapsed_time_kill_switch_enabled"] is False
    assert reopened["completion_policy"] == "run_to_terminal_or_operator_stop"
    assert "deadline_at_utc" not in reopened
    _validate_advisory_run_budget(reopened)


def test_completion_budget_gate_accepts_past_advisory_target() -> None:
    started = (
        (datetime.now(timezone.utc) - timedelta(days=30))
        .isoformat()
        .replace("+00:00", "Z")
    )
    _validate_advisory_run_budget(
        {
            "schema_version": "full-pipeline-production-hardening-run-budget.v1",
            **scope_fields(),
            "nominal_planning_seconds": 12 * 3600,
            "nominal_planning_hours": 12,
            "elapsed_time_kill_switch_enabled": False,
            "completion_policy": "run_to_terminal_or_operator_stop",
            "started_at_utc": started,
            "restart_policy": "RERUN_IDEMPOTENT_NO_ELAPSED_DEADLINE",
        }
    )


def test_passed_attempt_recovers_missing_latest_pointer(tmp_path: Path) -> None:
    task = {
        "task_id": "task-1",
        "pipeline_id": ANCHOR_PIPELINES[0],
        "candidate_role": "PRIMARY",
        "kind": "startup_self_test",
        "source_mode": "file_simulation_unpaced_preflight",
    }
    task_identity = sha256_bytes(canonical_json_bytes(task))
    plan_identity = "f" * 64
    task_root = tmp_path / "task-1"
    attempt = task_root / "attempts/attempt_001"
    attempt.mkdir(parents=True)
    artifact = attempt / "stdout.log"
    artifact.write_text("ok\n", encoding="utf-8")
    result = {
        **task,
        "status": "PASS",
        "task_identity_sha256": task_identity,
        "plan_identity_sha256": plan_identity,
        "artifacts": [{"path": str(artifact), "sha256": sha256_file(artifact)}],
    }
    write_json_atomic(attempt / "task_result.json", result)
    recovered = _latest_pass(
        task_root,
        task=task,
        task_identity=task_identity,
        plan_identity=plan_identity,
    )
    assert recovered == result
    assert (
        json.loads((task_root / "latest.json").read_text())[
            "recovered_after_pointer_write_interruption"
        ]
        is True
    )


def test_completed_program_state_requires_exact_remaining_prompt(
    tmp_path: Path,
) -> None:
    completion = tmp_path / "completion_marker.json"
    completion.write_text("{}\n", encoding="utf-8")
    state = {
        **scope_fields(),
        "status": PROMPT7_MARKER,
        "current_prompt_index": 7,
        "remaining_prompt_indices": [8],
        "remaining_prompt_status": "PENDING_AUTOMATIC",
        "prompt_7_completion_record": str(completion),
        "prompt_7_completion_record_sha256": sha256_file(completion),
        "completion_state": {
            "prompt_5": PROMPT5_MARKER,
            "prompt_6": PROMPT6_MARKER,
            "prompt_7": PROMPT7_MARKER,
            "prompt_5_scope_id": scope_fields()["scope_id"],
            "prompt_6_scope_id": scope_fields()["scope_id"],
            "prompt_7_scope_id": scope_fields()["scope_id"],
            "prompt_5_original_full_scope_complete": False,
            "prompt_6_original_full_scope_complete": False,
            "prompt_7_original_full_scope_complete": False,
        },
    }
    _validate_completed_state(state, completion_path=completion)
    state["remaining_prompt_indices"] = []
    with pytest.raises(RuntimeError, match="PROGRAM_STATE contract differs"):
        _validate_completed_state(state, completion_path=completion)


def test_compact_zip_reopens_and_validates_exact_members(tmp_path: Path) -> None:
    report = tmp_path / "report"
    bundle = tmp_path / "candidate_bundles/primary"
    report.mkdir(parents=True)
    bundle.mkdir(parents=True)
    (report / "report.md").write_text("ok\n", encoding="utf-8")
    (bundle / "preset.yaml").write_text("ok: true\n", encoding="utf-8")
    package = tmp_path / "packages/candidates.zip"
    _compact_zip(tmp_path, package)
    result = validate_compact_package(tmp_path, package)
    assert result["member_count"] == 2
    package.write_bytes(package.read_bytes() + b"tamper")
    with pytest.raises(Exception):
        validate_compact_package(tmp_path, package)


def test_material_paths_use_exact_workspace_cache_and_models(tmp_path: Path) -> None:
    state = tmp_path / "PROGRAM_STATE.json"
    amendment = tmp_path / "amendment.json"
    state.write_text("{}\n", encoding="utf-8")
    amendment.write_text("{}\n", encoding="utf-8")

    class Args:
        workspace_root = TOOL_ROOT / "automated_runs/_prompt7_material_fix"
        program_state_path = state
        amendment_path = amendment
        prompt5_marker = None
        prompt6_marker = None

    value = _material_paths(Args())
    assert value["classes"]["workspaces"] == [str(Args.workspace_root.resolve())]
    assert str(TOOL_ROOT.resolve()) not in value["classes"]["workspaces"]
    assert value["classes"]["caches"] == [
        str((TOOL_ROOT / "JustPeachyResults/full_pipeline/_shared_cache").resolve())
    ]
    assert value["classes"]["checkpoints"] == [
        str((TOOL_ROOT.parents[1] / "models/cache").resolve())
    ]


def _anchor_binding(pipeline: str) -> dict[str, object]:
    return {
        "pipeline_id": pipeline,
        "binding_status": "BOUND_FROZEN_ANCHOR",
        "production_role_eligible": True,
        "frozen_anchor": True,
        "unknown_only_fallback_allowed": False,
        "frozen_config_path": f"C:/synthetic/{pipeline}.yaml",
        "frozen_config_sha256": "a" * 64,
        "freeze_identity_sha256": "b" * 64,
        "pipeline_config_sha256": "c" * 64,
        "runtime_config_sha256": "d" * 64,
        "decision_policy_sha256": "e" * 64,
        "model_assets": {},
        "runtime_component_identities": {},
        "external_assets": [],
        "environment_interpreters": [],
    }


def _csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
