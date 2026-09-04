from __future__ import annotations

import json
from pathlib import Path

from app.full_pipeline_core_evaluation.reporting import _write_gate


def test_universal_gate_has_exact_schema_and_prompt(tmp_path: Path) -> None:
    path = _write_gate(
        tmp_path / "hash_validation.json",
        gate="hash_validation",
        evidence={"synthetic": True},
    )
    value = json.loads(path.read_text(encoding="utf-8"))

    assert value["schema_version"] == "full-pipeline-eight-day-gate.v1"
    assert value["gate"] == "hash_validation"
    assert value["status"] == "PASS"
    assert value["prompt_index"] == 5
    assert value["original_full_scope_complete"] is False
