"""Deterministic Stage 7 experiment planning over frozen Stage 2 contracts."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.manifest_io import file_sha256, read_manifest
from app.benchmark_contracts.rir_registry import RIRRegistry, load_condition_sets
from app.benchmark_contracts.scenario import (
    expand_scenarios,
    pipeline_identity_from_resolution,
)
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.resolver import resolve_pipeline
from app.utils.json_utils import read_json, write_json, write_jsonl


PLAN_SCHEMA_VERSION = "core-screening-plan.v1"
PROTOCOL_SCHEMA_VERSION = "core-screening-protocol.v1"
CATALOG_SCHEMA_VERSION = "core-screening-scenario-catalog.v1"
DEFAULT_PROTOCOL_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "automated_evaluation"
    / "core_screening.v1.yaml"
)
DEFAULT_PIPELINE_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "inference"
    / "live_mic_whisper_base.yaml"
)

ASR_COMPONENTS = ("whisper_tiny", "whisper_base", "whisper_small")
SEGMENTATION_COMPONENTS: dict[str, dict[str, str]] = {
    "full_record": {},
    "energy_observe": {"vad": "energy_vad"},
    "energy_chunks": {"vad": "energy_vad", "segmentation": "vad_chunks"},
    "silero_observe": {"vad": "silero_vad"},
    "silero_chunks": {"vad": "silero_vad", "segmentation": "vad_chunks"},
}


def build_screening_plan(
    benchmark_dir: Path,
    output_dir: Path,
    *,
    protocol_path: Path = DEFAULT_PROTOCOL_PATH,
    selected_pipeline_path: Path = DEFAULT_PIPELINE_PATH,
    segmentation_shortlist: Sequence[str] = (),
    qualified_asr: Sequence[str] = ASR_COMPONENTS,
    finalists: Sequence[str] = (),
) -> dict[str, object]:
    """Write a deterministic A-E plan and only the currently authorized scenarios."""

    protocol = _load_protocol(protocol_path)
    reference_asr = str(protocol["reference_asr"])
    benchmark_root = benchmark_dir.resolve()
    output_root = output_dir.resolve()
    manifest_path = benchmark_root / "small_source_manifest.parquet"
    summary_path = benchmark_root / "manifest_summary.json"
    if not manifest_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError(
            "Stage 7 requires the frozen Stage 2 small manifest and summary"
        )
    summary = read_json(summary_path)
    manifest_identity = _manifest_identity(summary, manifest_path)
    rows = read_manifest(manifest_path)
    controlled_rows = [row for row in rows if row.get("panel") == "controlled_clean"]
    if not controlled_rows:
        raise ValueError("small benchmark manifest has no controlled_clean rows")

    selected_segmentations = _unique_values(segmentation_shortlist)
    selected_asr = _unique_values(qualified_asr)
    selected_finalists = _unique_values(finalists)
    _validate_names(
        selected_segmentations, SEGMENTATION_COMPONENTS, "segmentation shortlist"
    )
    _validate_names(selected_asr, ASR_COMPONENTS, "qualified ASR")

    stage_candidates: dict[str, list[str]] = {
        "B": [_candidate_id("full_record", asr) for asr in ASR_COMPONENTS],
        "C": [
            _candidate_id(strategy, reference_asr)
            for strategy in SEGMENTATION_COMPONENTS
        ],
        "D": [
            _candidate_id(strategy, asr)
            for strategy in selected_segmentations
            for asr in selected_asr
        ],
        "FINAL": list(selected_finalists),
    }
    known_candidate_ids = {
        _candidate_id(strategy, asr)
        for strategy in SEGMENTATION_COMPONENTS
        for asr in ASR_COMPONENTS
    }
    _validate_names(stage_candidates["FINAL"], known_candidate_ids, "finalist")

    candidate_ids = sorted(
        {value for values in stage_candidates.values() for value in values}
    )
    catalog = ComponentCatalog.load()
    candidate_definitions = {
        candidate_id: _candidate_definition(
            candidate_id, selected_pipeline_path, catalog
        )
        for candidate_id in candidate_ids
    }
    conditions = load_condition_sets(RIRRegistry.load())
    scenario_rows: dict[str, dict[str, object]] = {}
    scenario_membership: dict[str, dict[str, list[str]]] = {}
    finalist_repetitions = int(protocol["finalist_validation"]["repetitions"])
    for stage_id in ("B", "C", "D", "FINAL"):
        repetitions = finalist_repetitions if stage_id == "FINAL" else 1
        scenario_membership[stage_id] = {}
        for candidate_id in stage_candidates[stage_id]:
            pipeline = candidate_definitions[candidate_id]["pipeline_identity"]
            expanded = expand_scenarios(
                manifest_identity=manifest_identity,
                manifest_rows=controlled_rows,
                pipeline_identities=[pipeline],
                condition_sets=conditions,
                repetitions=repetitions,
            )
            ids = []
            for scenario in expanded:
                scenario_id = str(scenario["scenario_id"])
                observed = scenario_rows.get(scenario_id)
                if observed is not None and observed != scenario:
                    raise ValueError(
                        f"conflicting Stage 7 scenario identity {scenario_id}"
                    )
                scenario_rows[scenario_id] = scenario
                ids.append(scenario_id)
            scenario_membership[stage_id][candidate_id] = sorted(ids)

    catalog_path = output_root / "screening_scenarios.jsonl"
    output_root.mkdir(parents=True, exist_ok=True)
    write_jsonl(catalog_path, [scenario_rows[key] for key in sorted(scenario_rows)])
    catalog_hash = file_sha256(catalog_path)
    item_set_hash = canonical_sha256(
        sorted(str(row["source_metadata_hash"]) for row in controlled_rows)
    )
    plan: dict[str, object] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "protocol": {
            "path": _tool_relative(protocol_path),
            "sha256": file_sha256(protocol_path),
            "contents": protocol,
        },
        "seed": 3800,
        "reference_asr": reference_asr,
        "benchmark": {
            "manifest": manifest_identity,
            "panel": "controlled_clean",
            "tier": "small",
            "condition_set": "smoke",
            "item_count": len(controlled_rows),
            "item_identity_sha256": item_set_hash,
            "datasets": sorted({str(row["dataset"]) for row in controlled_rows}),
        },
        "scenario_catalog": {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "path": catalog_path.name,
            "sha256": catalog_hash,
            "scenario_count": len(scenario_rows),
        },
        "candidate_definitions": {
            key: _public_candidate_definition(value)
            for key, value in sorted(candidate_definitions.items())
        },
        "stages": [
            _stage_a(protocol),
            _scenario_stage(
                "B",
                "ASR screen",
                stage_candidates["B"],
                scenario_membership["B"],
                fixed={"segmentation": "full_record", "speaker_processing": "disabled"},
                varied_family="asr",
                advancement="asr",
            ),
            _scenario_stage(
                "C",
                "VAD and segmentation screen",
                stage_candidates["C"],
                scenario_membership["C"],
                fixed={"asr": reference_asr, "speaker_processing": "disabled"},
                varied_family="vad_and_segmentation",
                advancement="segmentation",
            ),
            _scenario_stage(
                "D",
                "Targeted cross-check",
                stage_candidates["D"],
                scenario_membership["D"],
                fixed={"source": "Stage C shortlist"},
                varied_family="qualified_asr_x_shortlisted_segmentation",
                advancement="targeted_combinations",
                pending_reason=(
                    None
                    if stage_candidates["D"]
                    else "requires one or two declared Stage C segmentation finalists"
                ),
            ),
            _stage_e(protocol),
            _scenario_stage(
                "FINAL",
                "Repeated finalist validation",
                stage_candidates["FINAL"],
                scenario_membership["FINAL"],
                fixed={"repetitions": finalist_repetitions},
                varied_family="declared_finalists_only",
                advancement=None,
                pending_reason=(
                    None
                    if stage_candidates["FINAL"]
                    else "requires declared Stage D finalists"
                ),
            ),
        ],
        "methodology": {
            "fixed_manifest_reuse": True,
            "one_family_at_a_time": True,
            "full_cartesian_product": False,
            "failed_and_missing_outputs_in_denominators": True,
            "selection": "hard gates, Pareto dominance, then deterministic diverse cap",
            "slower_candidate_policy": (
                "retain non-dominated accuracy, reliability, and robustness tradeoffs"
            ),
        },
        "stage10_exclusions": [
            "EER",
            "FAR",
            "FRR",
            "speaker identification",
            "calibration",
            "unknown-speaker rejection",
        ],
    }
    plan_hash = canonical_sha256(plan)
    plan["plan_hash"] = plan_hash
    plan["plan_id"] = f"screening_plan_{plan_hash[:12].lower()}"
    write_json(output_root / "core_screening_plan.json", plan)
    (output_root / "core_screening_plan.sha256").write_text(
        f"{file_sha256(output_root / 'core_screening_plan.json')}  core_screening_plan.json\n",
        encoding="ascii",
    )
    _write_plan_markdown(output_root / "README.md", plan)
    return plan


def candidate_component_overrides(candidate_id: str) -> dict[str, str]:
    """Return the existing-YAML component selections for one candidate ID."""

    strategy, asr = _split_candidate_id(candidate_id)
    if strategy not in SEGMENTATION_COMPONENTS or asr not in ASR_COMPONENTS:
        raise ValueError(f"unknown Stage 7 candidate {candidate_id!r}")
    return {"asr": asr, **SEGMENTATION_COMPONENTS[strategy]}


def _candidate_definition(
    candidate_id: str,
    selected_pipeline_path: Path,
    catalog: ComponentCatalog,
) -> dict[str, object]:
    overrides = candidate_component_overrides(candidate_id)
    resolution = resolve_pipeline(
        selected_pipeline_path,
        component_overrides=overrides,
        catalog=catalog,
    )
    pipeline = pipeline_identity_from_resolution(resolution)
    components = {
        family: str(component["name"])
        for family, component in pipeline["components"].items()
        if isinstance(component, Mapping)
    }
    strategy, asr = _split_candidate_id(candidate_id)
    return {
        "candidate_id": candidate_id,
        "segmentation_strategy": strategy,
        "asr": asr,
        "component_overrides": overrides,
        "components": components,
        "selected_config_path": _tool_relative(selected_pipeline_path),
        "selected_config_sha256": resolution.selected_config_sha256,
        "resolved_config_sha256": pipeline["resolved_config_sha256"],
        "pipeline_identity": pipeline,
    }


def _public_candidate_definition(value: Mapping[str, object]) -> dict[str, object]:
    result = dict(value)
    result.pop("pipeline_identity", None)
    return result


def _stage_a(protocol: Mapping[str, object]) -> dict[str, object]:
    return {
        "stage_id": "A",
        "name": "Availability and contract qualification",
        "mode": "local_repeated_component_qualification",
        "status": "ready",
        "repetitions": int(protocol["qualification"]["repeated_smokes"]),
        "candidates": [
            "segmentation:full_record",
            "vad:energy_vad",
            "vad:silero_vad",
            "segmentation:vad_chunks",
            "asr:whisper_tiny",
            "asr:whisper_base",
            "asr:whisper_small",
            "speaker_embedding:speechbrain_ecapa",
            "speaker_matching:cosine_threshold_contract",
        ],
        "checks": [
            "config_resolution",
            "dependencies",
            "assets",
            "model_loading",
            "device_placement",
            "valid_output",
            "schema_validation",
            "identity_recording",
            "repeated_smoke_execution",
        ],
    }


def _stage_e(protocol: Mapping[str, object]) -> dict[str, object]:
    return {
        "stage_id": "E",
        "name": "ECAPA fixed-segment extraction qualification",
        "mode": "local_repeated_embedding_qualification",
        "status": "ready",
        "fixed": {"segments": "identical", "audio": "identical"},
        "component": "speechbrain_ecapa",
        "matcher_scope": "cosine contract and composition only",
        "minimum_duration_sec": protocol["embedding_policy"]["minimum_duration_sec"],
        "metrics": [
            "extraction_success",
            "embedding_dimension",
            "l2_norm",
            "invalid_vector_count",
            "repeatability_cosine",
            "minimum_duration_rejection",
            "clean_to_degraded_cosine_drift_when_paired",
        ],
        "forbidden_metrics": [
            "EER",
            "FAR",
            "FRR",
            "identification",
            "unknown_rejection",
        ],
    }


def _scenario_stage(
    stage_id: str,
    name: str,
    candidates: Sequence[str],
    membership: Mapping[str, Sequence[str]],
    *,
    fixed: Mapping[str, object],
    varied_family: str,
    advancement: str | None,
    pending_reason: str | None = None,
) -> dict[str, object]:
    return {
        "stage_id": stage_id,
        "name": name,
        "mode": "campaign_scenarios",
        "status": "pending_selection" if pending_reason else "ready",
        "pending_reason": pending_reason,
        "fixed": dict(fixed),
        "varied_family": varied_family,
        "candidates": list(candidates),
        "scenario_ids_by_candidate": {
            key: list(values) for key, values in sorted(membership.items())
        },
        "advancement_rule": advancement,
    }


def _manifest_identity(
    summary: Mapping[str, object], manifest_path: Path
) -> dict[str, object]:
    identities = summary.get("manifest_identities")
    if not isinstance(identities, Mapping) or not isinstance(
        identities.get("small"), Mapping
    ):
        raise ValueError("manifest summary does not contain the small identity")
    identity = deepcopy(dict(identities["small"]))
    if file_sha256(manifest_path) != identity.get("sha256"):
        raise ValueError("small manifest bytes do not match manifest_summary.json")
    identity["path"] = manifest_path.name
    return identity


def _load_protocol(path: Path) -> dict[str, object]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, Mapping)
        or data.get("schema_version") != PROTOCOL_SCHEMA_VERSION
    ):
        raise ValueError("unsupported core screening protocol")
    if data.get("seed") != 3800:
        raise ValueError("Stage 7 protocol must use seed 3800")
    if data.get("reference_asr") not in ASR_COMPONENTS:
        raise ValueError(
            "Stage 7 reference_asr must be Whisper Tiny, Base, or Small; Base is the default"
        )
    return deepcopy(dict(data))


def _candidate_id(strategy: str, asr: str) -> str:
    return f"{strategy}__{asr}"


def _split_candidate_id(candidate_id: str) -> tuple[str, str]:
    parts = candidate_id.split("__", 1)
    if len(parts) != 2:
        raise ValueError(f"invalid Stage 7 candidate ID {candidate_id!r}")
    return parts[0], parts[1]


def _unique_values(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _validate_names(values: Sequence[str], allowed: object, label: str) -> None:
    known = set(allowed)
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValueError(f"unknown {label} value(s): {unknown}")


def _tool_relative(path: Path) -> str:
    tool_root = Path(__file__).resolve().parents[2]
    resolved = path.resolve()
    try:
        return resolved.relative_to(tool_root).as_posix()
    except ValueError:
        return f"external:{resolved.name}"


def _write_plan_markdown(path: Path, plan: Mapping[str, object]) -> None:
    stages = plan["stages"]
    lines = [
        "# Stage 7 Core Screening Plan",
        "",
        "This directory is generated from the frozen small benchmark manifest. It contains no inference results.",
        "",
        f"- Plan ID: `{plan['plan_id']}`",
        f"- Benchmark items: `{plan['benchmark']['item_count']}`",
        f"- Scenario count: `{plan['scenario_catalog']['scenario_count']}`",
        "- Reference ASR: `whisper_base`",
        "",
        "## Sequence",
        "",
    ]
    for stage in stages:
        lines.append(f"- **{stage['stage_id']} — {stage['name']}**: {stage['status']}")
    lines.extend(
        [
            "",
            "Use `evaluation-tool screening qualify` for Stages A/E, then run only the scenario IDs listed for B/C. Rebuild this plan with the declared Stage C shortlist before D, and with declared finalists before repeated validation.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
