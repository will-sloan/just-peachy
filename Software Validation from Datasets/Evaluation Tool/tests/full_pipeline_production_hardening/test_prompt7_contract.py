from __future__ import annotations

import csv
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_evaluation.io import (
    canonical_json_bytes,
    checksum_map,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_production_hardening import (
    ANCHOR_PIPELINES,
    PROMPT7_MARKER,
    SCOPE_CLASS,
    SCOPE_ID,
    TOOL_ROOT,
    MATRIX_PATH,
    RUNTIME_PATH,
    scope_fields,
)
from app.full_pipeline_production_hardening.acceptance_worker import (
    _slow_consumer,
    _worker_recovery,
)
from app.full_pipeline_production_hardening.cli import _material_paths
from app.full_pipeline_production_hardening import gate
from app.full_pipeline_production_hardening.gate import (
    _validate_hardening_inputs,
)
from app.full_pipeline_production_hardening.packaging import validate_candidate_bundle
from app.full_pipeline_production_hardening.plan import FAULTS, build_acceptance_plan
from app.full_pipeline_production_hardening.runner import _last_json
from app.full_pipeline_production_hardening.selection import (
    h2_simplicity_rows,
    select_candidates,
)
from app.full_pipeline_production_hardening.universal import validate_completion


def test_selection_is_pareto_non_composite_and_licensing_separate(
    tmp_path: Path,
) -> None:
    summary = tmp_path / "all18_finalist_summary.csv"
    resources = tmp_path / "serial_resources.csv"
    identity = tmp_path / "online_identity.csv"
    _csv(
        summary,
        [
            {
                "pipeline_id": pipeline,
                "wrong_known_time_sec": index / 100,
                "stranger_false_known_time_sec": (6 - index) / 100,
                "speaker_attributed_wer": 0.10 + index / 1000,
                "correctly_named_known_rate": 0.90 - index / 1000,
                "speaker_confusion_rate": 0.10,
                "failure_rate": 0,
                "total_rtf": 0.5 + index / 100,
            }
            for index, pipeline in enumerate(ANCHOR_PIPELINES)
        ],
    )
    _csv(
        resources,
        [
            {
                "pipeline_id": pipeline,
                "total_rtf": 0.5 + index / 100,
                "peak_rss_bytes": 1_000_000 + index,
                "model_bytes": 2_000_000 + index,
                "startup_sec": 1 + index / 10,
                "model_worker_count": 2 + (index % 2),
            }
            for index, pipeline in enumerate(ANCHOR_PIPELINES)
        ],
    )
    _csv(
        identity,
        [
            {
                "pipeline_id": pipeline,
                "metric_id": metric,
                "value": index / 100
                if metric == "wrong_name_dwell_sec"
                else 1 + index / 100,
                "status": "computed",
            }
            for index, pipeline in enumerate(ANCHOR_PIPELINES)
            for metric in ("wrong_name_dwell_sec", "stable_name_latency_sec")
        ],
    )
    result = select_candidates(
        candidate_ids=ANCHOR_PIPELINES,
        evidence_files={
            summary.name: summary,
            resources.name: resources,
            identity.name: identity,
        },
        runtime_bindings={
            pipeline: _binding(pipeline) for pipeline in ANCHOR_PIPELINES
        },
    )
    assert result["weighted_score_used"] is False
    assert result["technical_and_licensing_rankings_separate"] is True
    assert 1 <= result["selected_pipeline_count"] <= 3
    assert result["roles"]["PRIMARY"] in ANCHOR_PIPELINES
    assert len(result["candidates"]) == 6
    assert all(
        row["metrics"]["premature_wrong_name_exposure_sec"] is not None
        for row in result["candidates"]
    )
    simplicity = h2_simplicity_rows(result)
    assert len(simplicity) == 4
    assert all(row["same_model_benefit_assumed"] is False for row in simplicity)


def test_acceptance_plan_is_exact_seventeen_serial_tasks_per_candidate(
    tmp_path: Path,
) -> None:
    selection = {
        "roles": {
            "PRIMARY": ANCHOR_PIPELINES[0],
            "FALLBACK": ANCHOR_PIPELINES[1],
            "ALTERNATIVE": None,
        },
        "candidates": [
            {
                "pipeline_id": pipeline,
                "production_role_eligible": True,
                "runtime_binding": _binding(pipeline),
            }
            for pipeline in ANCHOR_PIPELINES[:2]
        ],
    }
    long_input = {
        "input_id": "long",
        "path": str(tmp_path / "long.wav"),
        "sha256": "0" * 64,
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
            "input_id": f"enrollment_{index}",
            "path": str(tmp_path / f"e{index}.wav"),
            "sha256": str(index) * 64,
            "duration_sec": 10,
            "roles": ["enrollment_sample"],
        }
        for index in range(1, 4)
    ]
    plan = build_acceptance_plan(
        workspace_root=tmp_path,
        selection=selection,
        hardening_inputs={"inputs": [long_input, *enrollment]},
    )
    assert plan["parallel_candidate_runs"] == 1
    assert plan["task_count"] == 34
    for pipeline in selection["roles"].values():
        if pipeline is None:
            continue
        tasks = [row for row in plan["tasks"] if row["pipeline_id"] == pipeline]
        assert len(tasks) == 17
        assert {
            row.get("fault_id") for row in tasks if row["kind"] == "recovery_fault"
        } == set(FAULTS)


def test_hardening_input_manifest_requires_hash_bound_role_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    long_wav = tmp_path / "long.wav"
    long_wav.write_bytes(b"RIFFsynthetic")
    inputs = [
        {
            "input_id": "long",
            "path": str(long_wav),
            "sha256": sha256_file(long_wav),
            "duration_sec": 3600,
            "roles": [
                "deterministic_replay",
                "controlled_loopback",
                "repeated_session",
                "soak",
            ],
        }
    ]
    for index in range(3):
        wav = tmp_path / f"enroll_{index}.wav"
        wav.write_bytes(f"sample-{index}".encode())
        inputs.append(
            {
                "input_id": f"enroll_{index}",
                "path": str(wav),
                "sha256": sha256_file(wav),
                "duration_sec": 10,
                "roles": ["enrollment_sample"],
            }
        )
    monkeypatch.setattr(
        gate,
        "_wav_metadata",
        lambda path: {
            "container": "WAV",
            "codec": "PCM_S16LE",
            "channels": 1,
            "sample_width_bytes": 2,
            "sample_rate_hz": 16000,
            "frame_count": int((3600 if Path(path).name == "long.wav" else 10) * 16000),
            "duration_sec": 3600 if Path(path).name == "long.wav" else 10,
        },
    )
    manifest = tmp_path / "hardening_input_manifest.json"
    write_json_atomic(
        manifest,
        {
            "schema_version": "full-pipeline-hardening-input-manifest.v1",
            **scope_fields(),
            "outcome_independent": True,
            "inputs": inputs,
        },
    )
    value = _validate_hardening_inputs(manifest)
    assert len(value["inputs"]) == 4
    assert value["required_roles"] == [
        "controlled_loopback",
        "deterministic_replay",
        "enrollment_sample",
        "repeated_session",
        "soak",
    ]


def test_universal_validator_requires_exact_three_gates(tmp_path: Path) -> None:
    artifact = tmp_path / "result.csv"
    artifact.write_text("pipeline_id,status\np,PASS\n", encoding="utf-8")
    gate_refs = {}
    artifacts = [
        {"path": str(artifact), "sha256": sha256_file(artifact), "required": True}
    ]
    for gate_name in (
        "hash_validation",
        "firewall_validation",
        "prerequisite_validation",
    ):
        path = tmp_path / f"{gate_name}.json"
        write_json_atomic(
            path,
            {
                "schema_version": "full-pipeline-eight-day-gate.v1",
                **scope_fields(),
                "prompt_index": 7,
                "gate": gate_name,
                "status": "PASS",
            },
        )
        ref = {"path": str(path), "sha256": sha256_file(path)}
        gate_refs[gate_name] = ref
        artifacts.append({**ref, "required": True})
    manifest = tmp_path / "artifact_manifest.json"
    write_json_atomic(
        manifest,
        {
            "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
            **scope_fields(),
            "prompt_index": 7,
            "artifacts": artifacts,
        },
    )
    completion = tmp_path / "completion_marker.json"
    write_json_atomic(
        completion,
        {
            "schema_version": "full-pipeline-eight-day-stage-completion.v1",
            **scope_fields(),
            "prompt_index": 7,
            "status": "COMPLETE",
            "completion_marker": PROMPT7_MARKER,
            "adapter_id": "test-adapter",
            "adapter_contract_sha256": "a" * 64,
            "artifact_manifest": {
                "path": str(manifest),
                "sha256": sha256_file(manifest),
            },
            "gate_records": gate_refs,
        },
    )
    evidence = validate_completion(
        completion,
        prompt_index=7,
        marker=PROMPT7_MARKER,
        required_basenames=("result.csv",),
    )
    assert evidence.sha256 == sha256_file(completion)


def test_candidate_bundle_validation_is_checksum_bound(tmp_path: Path) -> None:
    pipeline = ANCHOR_PIPELINES[0]
    selection = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH).resolve(pipeline)
    asset = tmp_path.parent / f"{tmp_path.name}_synthetic_asset.bin"
    asset.write_bytes(b"locked-asset")
    frozen_core = {
        "pipeline_id": pipeline,
        "identity_policy": {"decision_policy_sha256": "a" * 64},
    }
    frozen = {
        **frozen_core,
        "freeze_identity_sha256": sha256_bytes(canonical_json_bytes(frozen_core)),
    }
    (tmp_path / "frozen_pipeline_config.yaml").write_text(
        yaml.safe_dump(frozen, sort_keys=True), encoding="utf-8"
    )
    preset = {
        "schema_version": "full-pipeline-production-candidate-preset.v1",
        **scope_fields(),
        "pipeline_id": pipeline,
        "pipeline_config_sha256": selection.pipeline_config_sha256,
        "runtime_config_sha256": selection.runtime_config_sha256,
        "frozen_config_sha256": sha256_file(tmp_path / "frozen_pipeline_config.yaml"),
        "freeze_identity_sha256": frozen["freeze_identity_sha256"],
        "decision_policy_sha256": "a" * 64,
        "scientific_thresholds_changed": False,
        "implicit_downloads_allowed": False,
        "offline_execution_required": True,
        "runtime_binding_status": "BOUND_FROZEN_ANCHOR",
        "common_demo_overlay_path": "common_demo_production_catalog.yaml",
    }
    overlay = {
        "schema_version": "full-pipeline-common-demo-production-overlay.v1",
        **scope_fields(),
        "status": "PASS",
        "roles": {"PRIMARY": pipeline, "FALLBACK": None, "ALTERNATIVE": None},
        "default_pipeline_id": pipeline,
        "presets": [{"pipeline_id": pipeline, "software_ready": True}],
    }
    (tmp_path / "common_demo_production_catalog.yaml").write_text(
        yaml.safe_dump(overlay, sort_keys=False), encoding="utf-8"
    )
    preset["common_demo_overlay_sha256"] = sha256_file(
        tmp_path / "common_demo_production_catalog.yaml"
    )
    (tmp_path / "production_candidate.yaml").write_text(
        yaml.safe_dump(preset, sort_keys=True), encoding="utf-8"
    )
    (tmp_path / "asset_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "full-pipeline-production-candidate-assets.v1",
                "pipeline_id": pipeline,
                "implicit_downloads_allowed": False,
                "offline_execution_required": True,
                "external_asset_attestations": [
                    {
                        "path": str(asset),
                        "sha256": sha256_file(asset),
                        "sha256_scope": "file",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "environment_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "full-pipeline-production-candidate-environments.v1",
                "pipeline_id": pipeline,
                "network_downloads_allowed": False,
                "implicit_environment_creation_allowed": False,
                "environment_interpreter_attestations": [
                    {
                        "interpreter_path": str(asset),
                        "interpreter_sha256": sha256_file(asset),
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    for name, payload in {
        "demo_preset.yaml": "schema_version: test\n",
        "result_baseline.json": "{}\n",
        "launch.ps1": "exit 0\n",
        "validate.ps1": "exit 0\n",
        "health.ps1": "exit 0\n",
        "KNOWN_LIMITATIONS.md": "# limits\n",
        "TROUBLESHOOTING.md": "# help\n",
    }.items():
        (tmp_path / name).write_text(payload, encoding="utf-8")
    write_json_atomic(
        tmp_path / "checksums.json",
        {
            "schema_version": "full-pipeline-production-candidate-checksums.v1",
            **scope_fields(),
            "pipeline_id": pipeline,
            "entries": checksum_map(tmp_path, exclude=("checksums.json",)),
        },
    )
    value = validate_candidate_bundle(tmp_path, pipeline_id=pipeline)
    assert value["status"] == "PASS"
    (tmp_path / "asset_manifest.json").write_text(
        '{"changed":true}\n', encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="checksum map differs"):
        validate_candidate_bundle(tmp_path, pipeline_id=pipeline)


def test_recovery_workers_are_bounded_and_model_free(tmp_path: Path) -> None:
    worker = _worker_recovery("pipeline")
    queue = _slow_consumer("pipeline")
    assert worker["status"] == "PASS"
    assert worker["initial_worker_exit_observed"] is True
    assert queue["status"] == "PASS"
    assert queue["bounded_queue"] is True


def test_last_json_handles_progress_before_final_payload(tmp_path: Path) -> None:
    path = tmp_path / "mixed.log"
    path.write_text('progress 1/2\n{"status":"PASS","value":2}\n', encoding="utf-8")
    assert _last_json(path) == {"status": "PASS", "value": 2}


def test_material_paths_has_exact_nine_classes(tmp_path: Path) -> None:
    state = tmp_path / "PROGRAM_STATE.json"
    amendment = tmp_path / "amendment.json"
    state.write_text("{}\n", encoding="utf-8")
    amendment.write_text("{}\n", encoding="utf-8")
    args = SimpleNamespace(
        workspace_root=TOOL_ROOT / "automated_runs/_prompt7_unit_contract_path",
        program_state_path=state,
        amendment_path=amendment,
        prompt5_marker=None,
        prompt6_marker=None,
    )
    value = _material_paths(args)
    assert set(value["classes"]) == {
        "inputs",
        "workspaces",
        "caches",
        "temporary",
        "logs",
        "results",
        "reports",
        "packages",
        "checkpoints",
    }
    assert value["scope_id"] == SCOPE_ID
    assert value["scope_class"] == SCOPE_CLASS


def _csv(path: Path, rows: list[dict[str, object]]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _binding(pipeline: str) -> dict[str, object]:
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
