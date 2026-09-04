"""Strict validation and derivation of the Task-1 frozen decision."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from typing import Mapping

import yaml

from app.controlled_diarization.contracts import (
    FROZEN_PIPELINE_SCHEMA_VERSION,
    TOOL_ROOT,
    canonical_json,
    load_config,
    load_pipeline_registry,
    sha256_file,
    sha256_text,
)
from app.controlled_diarization.runner import queue_status
from app.diarization_evaluation.artifacts import write_json_atomic
from app.diarization_final_evaluation.contracts import (
    AUTHORIZATION_ROOT,
    EXPECTED_PIPELINES,
    EXPECTED_PROTOCOLS,
    FROZEN_RUNTIME_CONFIG,
    TASK1_ROOT,
    TASK1_SELECTION,
    TASK1_SELECTION_CHECKSUM,
    V1_PROTOCOL_ROOT,
    V2_PROTOCOL_ROOT,
)


class FrozenDecisionError(RuntimeError):
    """The development-only decision cannot authorize evaluation."""


def load_selection() -> dict[str, object]:
    if not TASK1_SELECTION.is_file():
        raise FrozenDecisionError(f"missing Task-1 selection: {TASK1_SELECTION}")
    payload = yaml.safe_load(TASK1_SELECTION.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, Mapping):
        raise FrozenDecisionError("Task-1 selection is not a mapping")
    return dict(payload)


def selected_pipelines(selection: Mapping[str, object] | None = None) -> tuple[str, ...]:
    value = selection or load_selection()
    return tuple(str(item) for item in value.get("selected_pipeline_ids", []))


def validate_frozen_decision(*, write_authorizations: bool = True) -> dict[str, object]:
    errors: list[str] = []
    selection = load_selection()
    actual_selection_sha = sha256_file(TASK1_SELECTION).lower()
    recorded_selection_sha = ""
    if TASK1_SELECTION_CHECKSUM.is_file():
        recorded_selection_sha = TASK1_SELECTION_CHECKSUM.read_text(encoding="utf-8").split()[0].lower()
    if actual_selection_sha != recorded_selection_sha:
        errors.append("selection checksum mismatch")

    pipelines = selected_pipelines(selection)
    if pipelines != EXPECTED_PIPELINES:
        errors.append(f"unexpected frozen pipeline order: {pipelines}")
    if selection.get("evaluation_authorized") is not True:
        errors.append("evaluation_authorized is not true")
    if selection.get("EVALUATION_NOT_INSPECTED") is not True:
        errors.append("EVALUATION_NOT_INSPECTED is not true")
    for key in (
        "controlled_evaluation_run",
        "chime6_finalist_evaluation_run",
        "hybrid_run",
        "asr_run",
        "fine_tuning_run",
    ):
        if selection.get(key) is not False:
            errors.append(f"pre-evaluation firewall flag is not false: {key}")
    if not selection.get("selection_rationale"):
        errors.append("selection rationale is missing")

    protocol_ids = dict(selection.get("protocol_ids") or {})
    for name, expected in EXPECTED_PROTOCOLS.items():
        if protocol_ids.get(name) != expected:
            errors.append(f"protocol identity mismatch: {name}")
    v1_summary = _json(V1_PROTOCOL_ROOT / "protocol_summary.json")
    v2_summary = _json(V2_PROTOCOL_ROOT / "protocol_summary.json")
    if v1_summary.get("benchmark_id") != EXPECTED_PROTOCOLS["controlled_v1"]:
        errors.append("controlled V1 benchmark identity changed")
    if v2_summary.get("protocol_id") != EXPECTED_PROTOCOLS["product_v2"]:
        errors.append("Product V2 protocol identity changed")
    if v2_summary.get("evaluation_results_inspected") is not False:
        errors.append("Product V2 protocol reports inspected evaluation")

    if not FROZEN_RUNTIME_CONFIG.is_file():
        errors.append("frozen runtime configuration is missing")
        registry = {}
    else:
        registry = load_pipeline_registry(load_config(FROZEN_RUNTIME_CONFIG))
    selected_rows = {
        str(row.get("pipeline_id")): row
        for row in selection.get("selected_pipelines", [])
        if isinstance(row, Mapping)
    }
    config_hashes: dict[str, str] = {}
    for pipeline in pipelines:
        expected = str(selected_rows.get(pipeline, {}).get("configuration_sha256") or "")
        observed = registry.get(pipeline).configuration_sha256 if pipeline in registry else ""
        config_hashes[pipeline] = observed
        if not expected or observed != expected:
            errors.append(f"frozen configuration hash mismatch: {pipeline}")

    development = dict(selection.get("development_result_identity") or {})
    identity_rows = list(development.get("manifest_rows") or [])
    observed_rows: list[dict[str, str]] = []
    for row in identity_rows:
        relative = str(dict(row).get("path") or "")
        expected = str(dict(row).get("sha256") or "").lower()
        path = TASK1_ROOT / relative
        if not path.is_file():
            errors.append(f"development checksum manifest missing: {relative}")
            continue
        observed = sha256_file(path).lower()
        observed_rows.append({"path": relative, "sha256": observed})
        if observed != expected:
            errors.append(f"development checksum manifest changed: {relative}")
    if int(development.get("checksum_manifests") or -1) != len(identity_rows):
        errors.append("development checksum-manifest count mismatch")
    if sha256_text(canonical_json(observed_rows)) != str(development.get("sha256") or ""):
        errors.append("development result identity digest mismatch")

    code = dict(selection.get("git_and_result_affecting_code_identity") or {})
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=TOOL_ROOT.parents[1], capture_output=True, text=True, check=True
    ).stdout.strip()
    if head != code.get("git_head"):
        errors.append("Git HEAD differs from frozen development code identity")
    for row in code.get("product_code_files", []):
        item = dict(row)
        path = TOOL_ROOT / str(item.get("path") or "")
        if not path.is_file() or sha256_file(path) != item.get("sha256"):
            errors.append(f"Task-1 result-affecting code changed: {item.get('path')}")
    diff = subprocess.run(
        [
            "git", "diff", "--binary", "--",
            "Software Validation from Datasets/Evaluation Tool/app/controlled_diarization",
            "Software Validation from Datasets/Evaluation Tool/app/diarization_product_v2",
            "Software Validation from Datasets/Evaluation Tool/configs/automated_evaluation/diarization_product_v2.development.yaml",
        ],
        cwd=TOOL_ROOT.parents[1], capture_output=True, check=True,
    ).stdout
    if hashlib.sha256(diff).hexdigest() != code.get("result_affecting_diff_sha256"):
        errors.append("frozen result-affecting development diff changed")

    development_counts: dict[str, object] = {}
    if not errors:
        for label, benchmark, result in (
            ("controlled_v1", V1_PROTOCOL_ROOT, TASK1_ROOT / "v1"),
            ("product_v2", V2_PROTOCOL_ROOT, TASK1_ROOT / "v2"),
        ):
            value = queue_status(
                pipelines=pipelines,
                tiers=("development",),
                config_path=FROZEN_RUNTIME_CONFIG,
                benchmark_root=benchmark,
                result_root=result,
            )
            development_counts[label] = value
            for row in value["rows"]:
                if int(row["valid"]) != int(row["planned"]):
                    errors.append(f"selected development evidence incomplete: {label}/{row['pipeline_id']}")

    authorization_paths: dict[str, str] = {}
    if not errors and write_authorizations:
        AUTHORIZATION_ROOT.mkdir(parents=True, exist_ok=True)
        for label, summary, benchmark in (
            ("controlled_v1", v1_summary, V1_PROTOCOL_ROOT),
            ("product_v2", v2_summary, V2_PROTOCOL_ROOT),
        ):
            gate = {
                "schema_version": FROZEN_PIPELINE_SCHEMA_VERSION,
                "benchmark_id": summary.get("benchmark_id"),
                "protocol_id": summary.get("protocol_id", summary.get("benchmark_id")),
                "development_decision_status": "frozen",
                "evaluation_tuning_prohibited": True,
                "source_selection_path": str(TASK1_SELECTION),
                "source_selection_sha256": actual_selection_sha,
                "pipelines": [
                    {"pipeline_id": pipeline, "configuration_sha256": config_hashes[pipeline]}
                    for pipeline in pipelines
                ],
                "benchmark_root": str(benchmark),
            }
            path = AUTHORIZATION_ROOT / f"{label}.frozen_gate.json"
            write_json_atomic(path, gate)
            authorization_paths[label] = str(path)

    result = {
        "schema_version": "diarization-final-frozen-decision-validation.v1",
        "valid": not errors,
        "errors": errors,
        "selection_path": str(TASK1_SELECTION),
        "selection_sha256": actual_selection_sha,
        "selected_pipeline_ids": list(pipelines),
        "selected_configuration_sha256": config_hashes,
        "protocol_ids": protocol_ids,
        "development_checksum_manifests": len(observed_rows),
        "development_identity_sha256": development.get("sha256"),
        "development_counts": development_counts,
        "git_head": head,
        "result_affecting_diff_sha256": hashlib.sha256(diff).hexdigest(),
        "evaluation_not_inspected_at_authorization": selection.get("EVALUATION_NOT_INSPECTED"),
        "authorization_paths": authorization_paths,
    }
    if write_authorizations:
        write_json_atomic(AUTHORIZATION_ROOT / "frozen_decision_validation.json", result)
    return result


def require_valid_decision() -> dict[str, object]:
    value = validate_frozen_decision(write_authorizations=True)
    if not value["valid"]:
        raise FrozenDecisionError("; ".join(str(item) for item in value["errors"]))
    return value


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))

