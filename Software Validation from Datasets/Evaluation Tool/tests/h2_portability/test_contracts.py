from __future__ import annotations

import json
from pathlib import Path

from app.h2_portability.contracts import (
    EXPORTER_DYNAMO,
    EXPORTER_LEGACY,
    H2_DECISION_DIAGNOSTIC,
    ONNX_OPSET,
    PARITY_TOLERANCES,
)
from app.h2_portability.onnx_tooling import COMPONENTS, build_parity_plan
from app.h2_portability.parity import build_case_panel, build_e2e_parity_hook


def test_export_and_tolerance_contracts_are_explicit() -> None:
    assert ONNX_OPSET == 18
    assert EXPORTER_DYNAMO != EXPORTER_LEGACY
    assert tuple(COMPONENTS) == (
        "redimnet2_b2_speaker_embedding",
        "pyannote_segmentation_3_0",
    )
    assert set(PARITY_TOLERANCES) == set(COMPONENTS)
    assert H2_DECISION_DIAGNOSTIC["identity_score_threshold"] > 0


def test_case_manifests_are_deterministic_and_duration_complete() -> None:
    first_cases, first = build_case_panel("redimnet2_b2_speaker_embedding")
    second_cases, second = build_case_panel("redimnet2_b2_speaker_embedding")
    assert first == second
    assert first["case_count"] == 5
    assert [row["sample_count"] for row in first["cases"]] == [
        8_000,
        16_000,
        32_000,
        80_000,
        160_000,
    ]
    assert all("waveform" not in row for row in first["cases"])
    assert all(
        left["input_sha256"] == right["input_sha256"]
        for left, right in zip(first_cases, second_cases, strict=True)
    )


def test_parity_plan_has_no_mutable_threshold_arguments() -> None:
    value = build_parity_plan(
        "redimnet2_b2_speaker_embedding",
        native_artifact_sha256="a" * 64,
        onnx_artifact_sha256="b" * 64,
    )
    assert value["status"] == "PARITY_PLAN_FROZEN_NOT_MEASURED"
    assert value["tolerances"] == PARITY_TOLERANCES[
        "redimnet2_b2_speaker_embedding"
    ]


def test_e2e_hook_requires_both_component_passes(tmp_path: Path) -> None:
    reports = [
        {
            "component_id": component,
            "status": "PARITY_PASS",
            "parity_passed": True,
            "onnx_sha256": str(index) * 64,
            "case_manifest_sha256": "c" * 64,
            "tolerance_contract_sha256": "d" * 64,
        }
        for index, component in enumerate(COMPONENTS, 1)
    ]
    destination = tmp_path / "hook.json"
    value = build_e2e_parity_hook(reports, output_path=destination)
    assert value["status"] == "E2E_CONTRACT_PARITY_PASS"
    assert value["h2_controller_may_schedule_onnx_e2e_smoke"] is True
    assert value["h2_controller_may_claim_arm64_ready"] is False
    assert json.loads(destination.read_text(encoding="utf-8"))[
        "component_parity_passed"
    ] is True


def test_e2e_hook_blocks_when_one_component_is_missing() -> None:
    value = build_e2e_parity_hook(
        [
            {
                "component_id": "redimnet2_b2_speaker_embedding",
                "status": "PARITY_PASS",
                "parity_passed": True,
            }
        ]
    )
    assert value["status"] == "E2E_CONTRACT_PARITY_BLOCKED"
    assert value["component_parity_passed"] is False
