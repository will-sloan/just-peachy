"""Calibration-only automatic Phase-E decision-gate construction."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

import yaml

from app.speaker_enrollment.protocol import SpeakerEnrollmentError, load_config


def build_automatic_joint_gate(
    protocol_root: Path,
    result_base: Path,
    backend: str,
    output_path: Path,
    *,
    enrollment_configurations: int = 2,
) -> dict[str, object]:
    """Select enrollment modes from calibration metrics and retain every live duration."""

    if enrollment_configurations < 1:
        raise SpeakerEnrollmentError("automatic Phase-E gate requires at least one enrollment configuration")
    backend_root = result_base.resolve() / backend
    candidates: list[dict[str, object]] = []
    for phase_dir in (
        "phase_a_enrollment_count",
        "phase_b_enrollment_duration",
        "phase_c_aggregation",
    ):
        for path in sorted((backend_root / phase_dir).glob("*/configuration_result.json")):
            result = _read_json(path)
            if result.get("status") != "complete" or result.get("backend_id") != backend:
                continue
            policy = result.get("selected_open_set_policy")
            if not isinstance(policy, Mapping) or policy.get("evaluation_used_for_selection") is not False:
                raise SpeakerEnrollmentError(f"configuration lacks calibration-only policy evidence: {path}")
            configuration = result.get("configuration")
            if not isinstance(configuration, Mapping):
                raise SpeakerEnrollmentError(f"configuration identity is missing: {path}")
            candidates.append(
                {
                    "configuration_id": str(configuration["configuration_id"]),
                    "signature": (
                        str(configuration.get("enrollment_basis", "")),
                        str(configuration.get("enrollment_count", "")),
                        str(configuration.get("enrollment_target_audio_sec", "")),
                        str(configuration.get("aggregation_method", "")),
                    ),
                    "calibration_known_correct_acceptance": float(
                        policy.get("calibration_known_correct_acceptance") or 0.0
                    ),
                    "calibration_known_wrong_name_rate": float(
                        policy.get("calibration_known_wrong_name_rate") or 0.0
                    ),
                    "calibration_fpir": float(policy.get("calibration_fpir") or 0.0),
                    "estimated_bytes_per_speaker_float32": float(
                        result.get("representation_cost", {}).get(
                            "estimated_bytes_per_speaker_float32", float("inf")
                        )
                    ),
                }
            )
    if not candidates:
        raise SpeakerEnrollmentError(f"no completed calibration-bound enrollment configurations for {backend}")
    candidates.sort(
        key=lambda row: (
            -float(row["calibration_known_correct_acceptance"]),
            float(row["calibration_known_wrong_name_rate"]),
            float(row["calibration_fpir"]),
            float(row["estimated_bytes_per_speaker_float32"]),
            str(row["configuration_id"]),
        )
    )
    selected: list[dict[str, object]] = []
    signatures: set[tuple[str, ...]] = set()
    for row in candidates:
        signature = tuple(str(value) for value in row["signature"])
        if signature in signatures:
            continue
        signatures.add(signature)
        selected.append(row)
        if len(selected) >= enrollment_configurations:
            break
    if len(selected) < enrollment_configurations:
        raise SpeakerEnrollmentError("too few distinct completed enrollment modes for automatic Phase E")

    config = load_config(protocol_root.resolve() / "selection_config.yaml")
    durations = sorted({float(value) for value in config["probe_durations_sec"]})
    completed_durations: set[float] = set()
    for path in sorted((backend_root / "phase_d_probe_duration").glob("*/configuration_result.json")):
        result = _read_json(path)
        if result.get("status") == "complete":
            completed_durations.add(float(result["configuration"]["probe_target_audio_sec"]))
    missing = sorted(set(durations) - completed_durations)
    if missing:
        raise SpeakerEnrollmentError(f"Phase D is incomplete for {backend}; missing durations: {missing}")

    gate: dict[str, object] = {
        "schema_version": "speaker-enrollment-joint-decision.v1",
        "decision_policy": "automatic-calibration-only-frontier.v1",
        "backend_id": backend,
        "enrollment_configuration_ids": [row["configuration_id"] for row in selected],
        "probe_durations_sec": durations,
        "selection_evidence": [
            {key: value for key, value in row.items() if key != "signature"} for row in selected
        ],
        "selection_split": "calibration",
        "evaluation_metrics_used_for_selection": False,
        "selection_rule": (
            "highest calibration known-correct acceptance at the frozen primary FPIR policy; "
            "then lower calibration wrong-name rate, lower calibration FPIR, and lower template storage; "
            "one winner per distinct enrollment mode"
        ),
        "duration_rule": "all frozen causal durations after Phase-D completion",
        "automatic_product_decision": False,
    }
    _write_yaml_atomic(output_path.resolve(), gate)
    return gate


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise SpeakerEnrollmentError(f"JSON object required: {path}")
    return {str(key): item for key, item in value.items()}


def _write_yaml_atomic(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(yaml.safe_dump(dict(value), sort_keys=False), encoding="utf-8", newline="\n")
    os.replace(temporary, path)
