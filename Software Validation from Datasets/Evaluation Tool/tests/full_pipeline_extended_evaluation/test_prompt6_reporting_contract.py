from __future__ import annotations

import json
from pathlib import Path

from app.full_pipeline_evaluation.io import write_json_atomic
from app.full_pipeline_extended_evaluation import (
    PROMPT5_COMPLETION_MARKER,
    PROMPT6_COMPLETION_MARKER,
    scope_fields,
)
from app.full_pipeline_extended_evaluation.io import artifact_ref, sha256_file
from app.full_pipeline_extended_evaluation.reporting import (
    _require_material_path,
    _update_program_state,
    _verify_universal_refs,
    _write_gate,
)


def test_universal_prompt6_gate_and_manifest_are_rehashable(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence.csv"
    evidence.write_text("status\nPASS\n", encoding="utf-8")
    gates = {
        name: _write_gate(
            tmp_path / "gates" / f"{name}.json",
            gate=name,
            evidence={"synthetic": True},
        )
        for name in (
            "hash_validation",
            "firewall_validation",
            "prerequisite_validation",
        )
    }
    manifest_path = tmp_path / "artifact_manifest.json"
    write_json_atomic(
        manifest_path,
        {
            "schema_version": "full-pipeline-eight-day-artifact-manifest.v1",
            **scope_fields(),
            "prompt_index": 6,
            "artifacts": [
                {**artifact_ref(path), "required": True}
                for path in [evidence, *gates.values()]
            ],
        },
    )
    completion = {
        "artifact_manifest": artifact_ref(manifest_path),
        "gate_records": {name: artifact_ref(path) for name, path in gates.items()},
    }

    _verify_universal_refs(completion, prompt_index=6)
    gate = json.loads(gates["hash_validation"].read_text(encoding="utf-8"))
    assert gate["schema_version"] == "full-pipeline-eight-day-gate.v1"
    assert gate["prompt_index"] == 6
    assert gate["status"] == "PASS"


def test_program_state_advances_exactly_from_prompt5_to_prompt6(tmp_path: Path) -> None:
    state_path = tmp_path / "PROGRAM_STATE.json"
    completion = tmp_path / "completion_marker.json"
    completion.write_text('{"synthetic":true}\n', encoding="utf-8")
    write_json_atomic(
        state_path,
        {
            "status": PROMPT5_COMPLETION_MARKER,
            "current_prompt_index": 5,
            "remaining_prompt_indices": [6, 7, 8],
            "completion_state": {"prompt_5": PROMPT5_COMPLETION_MARKER},
        },
    )

    _update_program_state(state_path, completion_path=completion)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["status"] == PROMPT6_COMPLETION_MARKER
    assert state["current_prompt_index"] == 6
    assert state["remaining_prompt_indices"] == [7, 8]
    assert state["prompt_6_completion_record_sha256"] == sha256_file(completion)
    _update_program_state(state_path, completion_path=completion)


def test_artifacts_must_resolve_under_declared_material_paths(tmp_path: Path) -> None:
    report = tmp_path / "report"
    report.mkdir()
    artifact = report / "summary.csv"
    artifact.write_text("status\nPASS\n", encoding="utf-8")
    binding = {
        "material_paths": {
            "inputs": [],
            "workspaces": [str(tmp_path / "workspace")],
            "caches": [],
            "temporary": [],
            "logs": [],
            "results": [],
            "reports": [str(report)],
            "packages": [],
            "checkpoints": [],
        }
    }

    _require_material_path(artifact, binding)
