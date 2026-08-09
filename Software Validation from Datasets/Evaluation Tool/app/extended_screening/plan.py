"""Deterministic Stage 9 planning over qualified extended backends only."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from app.benchmark_contracts.canonical import canonical_sha256
from app.benchmark_contracts.manifest_io import file_sha256, read_manifest
from app.benchmark_contracts.rir_registry import RIRRegistry, load_condition_sets
from app.benchmark_contracts.scenario import (
    expand_scenarios,
    pipeline_identity_from_resolution,
)
from app.core_screening.plan import DEFAULT_PIPELINE_PATH
from app.extended_screening.contracts import (
    DEFAULT_PROTOCOL_PATH,
    eligible_backend_rows,
    load_protocol,
    load_qualification_registry,
    validate_catalog_qualification_alignment,
)
from app.inference_pipeline.catalog import ComponentCatalog
from app.inference_pipeline.resolver import PipelineResolutionError, resolve_pipeline
from app.utils.json_utils import read_json, write_json, write_jsonl


PLAN_SCHEMA_VERSION = "extended-screening-plan.v1"
CATALOG_SCHEMA_VERSION = "extended-screening-scenario-catalog.v1"
TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCHMARK_ROOT = TOOL_ROOT / "benchmarks" / "v1"
DEFAULT_OUTPUT_ROOT = TOOL_ROOT / "benchmarks" / "stage9"

CORE_ASR = ("whisper_tiny", "whisper_base", "whisper_small")
CORE_EMBEDDING = ("speechbrain_ecapa",)
CORE_VAD_STRATEGIES: dict[str, dict[str, str]] = {
    "full_record": {},
    "energy_observe": {"vad": "energy_vad"},
    "energy_chunks": {"vad": "energy_vad", "segmentation": "vad_chunks"},
    "silero_observe": {"vad": "silero_vad"},
    "silero_chunks": {"vad": "silero_vad", "segmentation": "vad_chunks"},
}
EXTENDED_VAD_STRATEGIES: dict[str, dict[str, str]] = {
    "webrtc_observe": {"vad": "webrtc_vad"},
    "webrtc_chunks": {"vad": "webrtc_vad", "segmentation": "vad_chunks"},
    "sherpa_onnx_observe": {"vad": "sherpa_onnx_vad"},
    "sherpa_onnx_chunks": {
        "vad": "sherpa_onnx_vad",
        "segmentation": "vad_chunks",
    },
}


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    stage_family: str
    varied_family: str
    varied_component: str
    component_overrides: Mapping[str, str]
    environment_profile: str
    qualification_backend_ids: tuple[str, ...] = ()
    scientific_scope: str = "screen"


def build_extended_screening_plan(
    benchmark_dir: Path = DEFAULT_BENCHMARK_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_ROOT,
    *,
    protocol_path: Path = DEFAULT_PROTOCOL_PATH,
    selected_pipeline_path: Path = DEFAULT_PIPELINE_PATH,
    asr_shortlist: Sequence[str] = (),
    vad_shortlist: Sequence[str] = (),
    embedding_shortlist: Sequence[str] = (),
    finalists: Sequence[str] = (),
) -> dict[str, object]:
    """Write Stage 9 scenarios and handoff reports without running inference."""

    protocol = load_protocol(protocol_path)
    registry = load_qualification_registry()
    catalog = ComponentCatalog.load()
    validate_catalog_qualification_alignment(registry, catalog)
    qualification_summary = _qualification_summary(protocol)
    qualification_results = {
        str(row["backend_id"]): dict(row)
        for row in qualification_summary["results"]
        if isinstance(row, Mapping)
    }
    eligible_rows = eligible_backend_rows(registry)
    eligible_by_family = _eligible_components_by_family(eligible_rows)

    manifest_path = benchmark_dir.resolve() / "small_source_manifest.parquet"
    summary_path = benchmark_dir.resolve() / "manifest_summary.json"
    if not manifest_path.is_file() or not summary_path.is_file():
        raise FileNotFoundError("Stage 9 requires the frozen Stage 2 small manifest")
    summary = read_json(summary_path)
    manifest_identity = _manifest_identity(summary, manifest_path)
    controlled_rows = [
        row
        for row in read_manifest(manifest_path)
        if row.get("panel") == "controlled_clean"
    ]
    if not controlled_rows:
        raise ValueError("small manifest has no controlled_clean rows")
    item_set_hash = canonical_sha256(
        sorted(str(row["source_metadata_hash"]) for row in controlled_rows)
    )

    specifications: dict[str, CandidateSpec] = {}
    asr_ids = []
    for component in (*CORE_ASR, *eligible_by_family.get("asr", ())):
        candidate_id = f"full_record__{component}"
        profile, backend_ids = _candidate_environment(
            {"asr": component}, catalog, eligible_rows
        )
        specifications[candidate_id] = CandidateSpec(
            candidate_id,
            "asr",
            "asr",
            component,
            {"asr": component},
            profile,
            backend_ids,
        )
        asr_ids.append(candidate_id)

    vad_strategies = {**CORE_VAD_STRATEGIES, **EXTENDED_VAD_STRATEGIES}
    vad_ids = []
    for strategy, overrides in vad_strategies.items():
        requested = {"asr": "whisper_base", **overrides}
        candidate_id = f"{strategy}__whisper_base"
        profile, backend_ids = _candidate_environment(
            requested, catalog, eligible_rows
        )
        specifications[candidate_id] = CandidateSpec(
            candidate_id,
            "vad",
            "vad_and_segmentation",
            strategy,
            requested,
            profile,
            backend_ids,
        )
        vad_ids.append(candidate_id)

    embedding_ids = []
    for component in (*CORE_EMBEDDING, *eligible_by_family.get("speaker_embedding", ())):
        requested = {"asr": "whisper_base", "speaker_embedding": component}
        candidate_id = f"fixed_segments__{component}"
        profile, backend_ids = _candidate_environment(
            requested, catalog, eligible_rows
        )
        specifications[candidate_id] = CandidateSpec(
            candidate_id,
            "embedding",
            "speaker_embedding",
            component,
            requested,
            profile,
            backend_ids,
        )
        embedding_ids.append(candidate_id)

    composition_ids = []
    for component in eligible_by_family.get("diarization", ()):
        requested = {"asr": "whisper_base", "diarization": component}
        candidate_id = f"composition__{component}"
        profile, backend_ids = _candidate_environment(
            requested, catalog, eligible_rows
        )
        specifications[candidate_id] = CandidateSpec(
            candidate_id,
            "diarization_composition",
            "diarization",
            component,
            requested,
            profile,
            backend_ids,
            scientific_scope="composition_only",
        )
        composition_ids.append(candidate_id)

    targeted_ids = _targeted_specs(
        specifications,
        asr_shortlist=asr_shortlist,
        vad_shortlist=vad_shortlist,
        embedding_shortlist=embedding_shortlist,
        catalog=catalog,
        eligible_rows=eligible_rows,
    )
    finalist_ids = _unique(finalists)
    unknown_finalists = sorted(set(finalist_ids) - set(specifications))
    if unknown_finalists:
        raise ValueError(f"unknown Stage 9 finalist(s): {unknown_finalists}")

    definitions = {
        candidate_id: _resolve_candidate(
            spec,
            selected_pipeline_path,
            catalog,
            qualification_summary,
            qualification_results,
            item_set_hash,
        )
        for candidate_id, spec in sorted(specifications.items())
    }
    conditions = load_condition_sets(RIRRegistry.load())
    stage_candidates = {
        "B": asr_ids,
        "C": vad_ids,
        "E": embedding_ids,
        "Q": composition_ids,
        "D": targeted_ids,
        "FINAL": finalist_ids,
    }
    scenario_rows: dict[str, dict[str, object]] = {}
    membership: dict[str, dict[str, list[str]]] = {}
    final_repetitions = int(protocol["screening"]["repetitions_for_finalists"])
    for stage_id, candidate_ids in stage_candidates.items():
        membership[stage_id] = {}
        repetitions = final_repetitions if stage_id == "FINAL" else 1
        for candidate_id in candidate_ids:
            expanded = expand_scenarios(
                manifest_identity=manifest_identity,
                manifest_rows=controlled_rows,
                pipeline_identities=[definitions[candidate_id]["pipeline_identity"]],
                condition_sets=conditions,
                repetitions=repetitions,
            )
            ids = []
            for scenario in expanded:
                scenario_id = str(scenario["scenario_id"])
                observed = scenario_rows.get(scenario_id)
                if observed is not None and observed != scenario:
                    raise ValueError(f"conflicting Stage 9 scenario {scenario_id}")
                scenario_rows[scenario_id] = scenario
                ids.append(scenario_id)
            membership[stage_id][candidate_id] = sorted(ids)

    output_root = output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    scenario_path = output_root / "extended_screening_scenarios.jsonl"
    write_jsonl(scenario_path, [scenario_rows[key] for key in sorted(scenario_rows)])
    stages = _stages(stage_candidates, membership, protocol)
    plan: dict[str, object] = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "seed": 3800,
        "reference_asr": "whisper_base",
        "protocol": {
            "path": _tool_relative(protocol_path),
            "sha256": file_sha256(protocol_path),
            "contents": protocol,
        },
        "qualification_registry": {
            "path": _tool_relative(
                TOOL_ROOT
                / "configs"
                / "automated_evaluation"
                / "extended_qualification_registry.v1.yaml"
            ),
            "sha256": file_sha256(
                TOOL_ROOT
                / "configs"
                / "automated_evaluation"
                / "extended_qualification_registry.v1.yaml"
            ),
            "source_summary_sha256": file_sha256(
                TOOL_ROOT
                / "runs"
                / "extended_backend_qualification"
                / "qualification_summary.json"
            ),
        },
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
            "path": scenario_path.name,
            "sha256": file_sha256(scenario_path),
            "scenario_count": len(scenario_rows),
        },
        "candidate_definitions": {
            key: _public_definition(value)
            for key, value in sorted(definitions.items())
        },
        "stages": stages,
        "methodology": {
            "fixed_manifest_reuse": True,
            "identical_items_across_candidates": True,
            "one_family_at_a_time": True,
            "full_cartesian_product": False,
            "failed_and_missing_outputs_in_denominators": True,
            "environment_aware": True,
            "runtime_comparisons_grouped_by_environment_and_hardware": True,
            "speaker_recognition_metrics_deferred_to_stage10": True,
            "diarization_science_deferred_to_stage11": True,
        },
    }
    plan_hash = canonical_sha256(plan)
    plan["plan_hash"] = plan_hash
    plan["plan_id"] = f"extended_screening_{plan_hash[:12].lower()}"
    write_json(output_root / "extended_screening_plan.json", plan)
    (output_root / "extended_screening_plan.sha256").write_text(
        f"{file_sha256(output_root / 'extended_screening_plan.json')}  extended_screening_plan.json\n",
        encoding="ascii",
    )
    _write_required_handoffs(
        output_root,
        plan,
        registry,
        qualification_results,
        controlled_rows,
        stage_candidates,
        membership,
        scenario_rows,
    )
    return plan


def _eligible_components_by_family(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, tuple[str, ...]]:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(str(row["catalog_family"]), []).append(
            str(row["catalog_name"])
        )
    return {key: tuple(sorted(values)) for key, values in grouped.items()}


def _candidate_environment(
    overrides: Mapping[str, str],
    catalog: ComponentCatalog,
    eligible_rows: Sequence[Mapping[str, object]],
) -> tuple[str, tuple[str, ...]]:
    backend_ids = []
    profiles = set()
    eligible_lookup = {
        (str(row["catalog_family"]), str(row["catalog_name"])): row
        for row in eligible_rows
    }
    for family, component in overrides.items():
        row = eligible_lookup.get((family, component))
        if row is not None:
            backend_ids.append(str(row["backend_id"]))
            profiles.add(str(row["profile"]))
    if len(profiles) > 1:
        raise PipelineResolutionError(
            "targeted combination crosses incompatible Stage 8 profiles: "
            + ", ".join(sorted(profiles))
        )
    return (next(iter(profiles), "core-cpu"), tuple(sorted(backend_ids)))


def _targeted_specs(
    specifications: dict[str, CandidateSpec],
    *,
    asr_shortlist: Sequence[str],
    vad_shortlist: Sequence[str],
    embedding_shortlist: Sequence[str],
    catalog: ComponentCatalog,
    eligible_rows: Sequence[Mapping[str, object]],
) -> list[str]:
    selected_asr = _unique(asr_shortlist)
    selected_vad = _unique(vad_shortlist)
    selected_embedding = _unique(embedding_shortlist)
    allowed_asr = {
        spec.varied_component
        for spec in specifications.values()
        if spec.stage_family == "asr"
    }
    allowed_vad = set(CORE_VAD_STRATEGIES) | set(EXTENDED_VAD_STRATEGIES)
    allowed_embedding = {
        spec.varied_component
        for spec in specifications.values()
        if spec.stage_family == "embedding"
    }
    _validate_selected(selected_asr, allowed_asr, "ASR shortlist")
    _validate_selected(selected_vad, allowed_vad, "VAD shortlist")
    _validate_selected(selected_embedding, allowed_embedding, "embedding shortlist")
    result = []
    strategies = {**CORE_VAD_STRATEGIES, **EXTENDED_VAD_STRATEGIES}
    for strategy in selected_vad:
        for asr in selected_asr:
            overrides = {"asr": asr, **strategies[strategy]}
            profile, backend_ids = _candidate_environment(
                overrides, catalog, eligible_rows
            )
            candidate_id = f"target__{strategy}__{asr}"
            specifications[candidate_id] = CandidateSpec(
                candidate_id,
                "targeted",
                "shortlisted_vad_x_asr",
                f"{strategy}__{asr}",
                overrides,
                profile,
                backend_ids,
            )
            result.append(candidate_id)
        for embedding in selected_embedding:
            overrides = {
                "asr": "whisper_base",
                "speaker_embedding": embedding,
                **strategies[strategy],
            }
            profile, backend_ids = _candidate_environment(
                overrides, catalog, eligible_rows
            )
            candidate_id = f"embedding_target__{strategy}__{embedding}"
            specifications[candidate_id] = CandidateSpec(
                candidate_id,
                "embedding_targeted",
                "segmentation_x_embedding",
                f"{strategy}__{embedding}",
                overrides,
                profile,
                backend_ids,
            )
            result.append(candidate_id)
    return result


def _resolve_candidate(
    spec: CandidateSpec,
    selected_pipeline_path: Path,
    catalog: ComponentCatalog,
    qualification_summary: Mapping[str, object],
    qualification_results: Mapping[str, Mapping[str, object]],
    item_set_hash: str,
) -> dict[str, object]:
    resolution = resolve_pipeline(
        selected_pipeline_path,
        component_overrides=spec.component_overrides,
        environment_profile=spec.environment_profile,
        catalog=catalog,
    )
    pipeline = pipeline_identity_from_resolution(resolution)
    environment = _environment_identity(
        spec.environment_profile,
        spec.qualification_backend_ids,
        qualification_summary,
        qualification_results,
    )
    pipeline["environment_identity"] = environment
    return {
        "candidate_id": spec.candidate_id,
        "stage_family": spec.stage_family,
        "varied_family": spec.varied_family,
        "varied_component": spec.varied_component,
        "scientific_scope": spec.scientific_scope,
        "component_overrides": dict(spec.component_overrides),
        "environment_profile": spec.environment_profile,
        "environment_identity": environment,
        "qualification_backend_ids": list(spec.qualification_backend_ids),
        "selected_config_path": _tool_relative(selected_pipeline_path),
        "selected_config_sha256": resolution.selected_config_sha256,
        "resolved_config_sha256": pipeline["resolved_config_sha256"],
        "comparison_item_set_sha256": item_set_hash,
        "component_identities": resolution.component_identity_summary()["components"],
        "pipeline_identity": pipeline,
    }


def _environment_identity(
    profile: str,
    backend_ids: Sequence[str],
    summary: Mapping[str, object],
    results: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    if not backend_ids:
        return {
            "profile": profile,
            "classification": "core_control",
            "actual_execution_fingerprint_required": True,
        }
    artifacts = {
        str(row["profile"]): row
        for row in summary.get("source_profile_artifacts", [])
        if isinstance(row, Mapping)
    }
    source = artifacts.get(profile)
    if source is None:
        raise ValueError(f"Stage 8 summary has no environment evidence for {profile}")
    environment = source.get("environment")
    if not isinstance(environment, Mapping):
        raise ValueError(f"Stage 8 environment evidence is malformed for {profile}")
    return {
        "profile": profile,
        "classification": "extended_isolated",
        "qualification_artifact_sha256": source["sha256"],
        "python": environment.get("python"),
        "platform": environment.get("platform"),
        "device_requested": environment.get("device_requested"),
        "torch": environment.get("torch"),
        "cuda_runtime": environment.get("cuda_runtime"),
        "gpu": environment.get("gpu"),
        "package_freeze_sha256": environment.get("package_freeze_sha256"),
        "backend_ids": list(backend_ids),
        "model_assets": {
            backend_id: [
                {
                    "asset_id": asset.get("asset_id"),
                    "sha256": asset.get("sha256"),
                    "size_bytes": asset.get("size_bytes"),
                    "verification_status": asset.get("verification_status"),
                }
                for asset in results[backend_id].get("asset_identities", [])
                if isinstance(asset, Mapping)
            ]
            for backend_id in backend_ids
        },
    }


def _stages(
    candidates: Mapping[str, Sequence[str]],
    membership: Mapping[str, Mapping[str, Sequence[str]]],
    protocol: Mapping[str, object],
) -> list[dict[str, object]]:
    return [
        {
            "stage_id": "A",
            "name": "Stage 8 qualification evidence gate",
            "mode": "qualification_registry",
            "status": "complete",
        },
        _scenario_stage(
            "B",
            "Extended ASR screen",
            candidates["B"],
            membership["B"],
            "asr",
            {"segmentation": "full_record", "speaker_processing": False, "diarization": False},
        ),
        _scenario_stage(
            "C",
            "Extended VAD and segmentation screen",
            candidates["C"],
            membership["C"],
            "segmentation",
            {"asr": "whisper_base", "collar_policy": "core_screening.v1"},
        ),
        {
            **_scenario_stage(
                "E",
                "Extended fixed-segment embedding extraction screen",
                candidates["E"],
                membership["E"],
                "embedding",
                {"segments": "identical", "recognition_metrics": "deferred_to_stage10"},
            ),
            "mode": "embedding_campaign_scenarios",
        },
        {
            **_scenario_stage(
                "Q",
                "Diarization composition qualification only",
                candidates["Q"],
                membership["Q"],
                None,
                {"scientific_evaluation": "deferred_to_stage11"},
            ),
            "mode": "composition_only_scenarios",
        },
        _scenario_stage(
            "D",
            "Targeted interactions",
            candidates["D"],
            membership["D"],
            "targeted_combinations",
            {"source": "declared shortlists only"},
            pending=not candidates["D"],
        ),
        _scenario_stage(
            "FINAL",
            "Repeated finalist validation",
            candidates["FINAL"],
            membership["FINAL"],
            None,
            {"repetitions": protocol["screening"]["repetitions_for_finalists"]},
            pending=not candidates["FINAL"],
        ),
    ]


def _scenario_stage(
    stage_id: str,
    name: str,
    candidates: Sequence[str],
    membership: Mapping[str, Sequence[str]],
    advancement: str | None,
    fixed: Mapping[str, object],
    *,
    pending: bool = False,
) -> dict[str, object]:
    return {
        "stage_id": stage_id,
        "name": name,
        "mode": "campaign_scenarios",
        "status": "pending_selection" if pending else "ready",
        "fixed": dict(fixed),
        "candidates": list(candidates),
        "scenario_ids_by_candidate": {
            key: list(value) for key, value in sorted(membership.items())
        },
        "advancement_rule": advancement,
    }


def _write_required_handoffs(
    output_root: Path,
    plan: Mapping[str, object],
    registry: Mapping[str, object],
    qualification_results: Mapping[str, Mapping[str, object]],
    rows: Sequence[Mapping[str, object]],
    stage_candidates: Mapping[str, Sequence[str]],
    membership: Mapping[str, Mapping[str, Sequence[str]]],
    scenario_rows: Mapping[str, Mapping[str, object]],
) -> None:
    definitions = plan["candidate_definitions"]
    comparison_rows = [
        {
            "candidate_id": candidate_id,
            "stage_family": value["stage_family"],
            "varied_component": value["varied_component"],
            "environment_profile": value["environment_profile"],
            "device": value["environment_identity"].get("device_requested", "cpu"),
            "qualification_backend_ids": value["qualification_backend_ids"],
            "comparison_item_set_sha256": value["comparison_item_set_sha256"],
            "screening_status": "planned",
        }
        for candidate_id, value in sorted(definitions.items())
    ]
    tables = {
        "schema_version": "extended-component-comparison-tables.v1",
        "plan_id": plan["plan_id"],
        "rows": comparison_rows,
        "metric_values_available_after_campaign_analysis": True,
    }
    write_json(output_root / "extended_component_comparison_tables.json", tables)
    _write_comparison_markdown(
        output_root / "extended_component_comparison_tables.md", tables
    )

    excluded = []
    for row in registry["backends"]:
        if not isinstance(row, Mapping):
            continue
        result = qualification_results[str(row["backend_id"])]
        disposition = str(row["disposition"])
        if disposition == "exclude":
            action = "excluded"
        elif disposition == "composition_only":
            action = "deferred_to_stage11_after_composition"
        else:
            action = "advanced_to_stage9_screening"
        excluded.append(
            {
                "backend_id": row["backend_id"],
                "status": row["status"],
                "action": action,
                "reason": result["explanation"],
            }
        )
    advancement = {
        "schema_version": "extended-advancement-exclusion.v1",
        "plan_id": plan["plan_id"],
        "decisions": excluded,
        "post_screening_advancement": "pending campaign analysis",
        "opaque_score_used": False,
    }
    write_json(output_root / "advancement_and_exclusion_report.json", advancement)
    _write_decision_markdown(
        output_root / "advancement_and_exclusion_report.md", advancement
    )

    profiles = sorted(
        {str(value["environment_profile"]) for value in definitions.values()}
    )
    compatibility = {
        "schema_version": "extended-environment-compatibility-matrix.v1",
        "plan_id": plan["plan_id"],
        "profiles": profiles,
        "candidate_profiles": {
            key: value["environment_profile"] for key, value in sorted(definitions.items())
        },
        "profile_pairs": [
            {
                "left": left,
                "right": right,
                "single_process_composable": left == right,
                "reason": (
                    "same isolated environment"
                    if left == right
                    else "different isolated profiles; compare results but do not compose components"
                ),
            }
            for left in profiles
            for right in profiles
        ],
    }
    write_json(output_root / "environment_compatibility_matrix.json", compatibility)
    _write_environment_markdown(
        output_root / "environment_compatibility_matrix.md", compatibility
    )

    dataset_counts: dict[str, int] = {}
    for row in rows:
        key = str(row["dataset"])
        dataset_counts[key] = dataset_counts.get(key, 0) + 1
    coverage = {
        "schema_version": "extended-benchmark-coverage.v1",
        "plan_id": plan["plan_id"],
        "benchmark_manifest_id": plan["benchmark"]["manifest"]["manifest_id"],
        "item_count": len(rows),
        "item_set_sha256": plan["benchmark"]["item_identity_sha256"],
        "datasets": dict(sorted(dataset_counts.items())),
        "conditions": "smoke",
        "scenario_count": plan["scenario_catalog"]["scenario_count"],
        "scenarios_per_candidate": {
            candidate_id: len(ids)
            for stage in membership.values()
            for candidate_id, ids in stage.items()
        },
        "identical_items_required": True,
        "missing_and_failed_outputs_in_denominators": True,
    }
    write_json(output_root / "benchmark_coverage_report.json", coverage)
    _write_coverage_markdown(output_root / "benchmark_coverage_report.md", coverage)

    shortlist = {
        "schema_version": "extended-shortlist-manifest.v1",
        "plan_id": plan["plan_id"],
        "plan_hash": plan["plan_hash"],
        "asr": [],
        "vad_segmentation": [],
        "speaker_embedding": [],
        "targeted_combinations": list(stage_candidates["D"]),
        "finalists": list(stage_candidates["FINAL"]),
        "status": "pending_scientific_results",
        "selection_policy": "hard gates plus declared Pareto frontiers; no opaque score",
    }
    write_json(output_root / "shortlist_manifest.json", shortlist)

    scenario_ids_by_profile: dict[str, set[str]] = {}
    candidate_ids_by_profile: dict[str, set[str]] = {}
    for stage_membership in membership.values():
        for candidate_id, scenario_ids in stage_membership.items():
            profile = str(definitions[candidate_id]["environment_profile"])
            scenario_ids_by_profile.setdefault(profile, set()).update(
                str(value) for value in scenario_ids
            )
            candidate_ids_by_profile.setdefault(profile, set()).add(candidate_id)
    profile_catalogs = []
    for profile in sorted(scenario_ids_by_profile):
        safe_profile = profile.replace("-", "_")
        path = output_root / f"scenarios_{safe_profile}.jsonl"
        write_jsonl(
            path,
            [
                scenario_rows[scenario_id]
                for scenario_id in sorted(scenario_ids_by_profile[profile])
            ],
        )
        profile_catalogs.append(
            {
                "environment_profile": profile,
                "path": path.name,
                "sha256": file_sha256(path),
                "scenario_count": len(scenario_ids_by_profile[profile]),
                "candidate_ids": sorted(candidate_ids_by_profile[profile]),
            }
        )
    write_json(
        output_root / "scenario_catalogs_by_environment.json",
        {
            "schema_version": "extended-environment-scenario-catalogs.v1",
            "plan_id": plan["plan_id"],
            "catalogs": profile_catalogs,
            "global_scenario_ids_preserved": True,
        },
    )


def _write_comparison_markdown(path: Path, payload: Mapping[str, object]) -> None:
    lines = [
        "# Stage 9 Extended Component Comparison Table",
        "",
        "| Candidate | Family | Environment | Status |",
        "|---|---|---|---|",
    ]
    for row in payload["rows"]:
        lines.append(
            f"| `{row['candidate_id']}` | {row['stage_family']} | `{row['environment_profile']}` | {row['screening_status']} |"
        )
    lines.extend(["", "Metric columns are populated only after validated campaign analysis.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_decision_markdown(path: Path, payload: Mapping[str, object]) -> None:
    lines = [
        "# Stage 9 Advancement and Exclusion Report",
        "",
        "| Backend | Stage 8 status | Stage 9 action | Reason |",
        "|---|---|---|---|",
    ]
    for row in payload["decisions"]:
        lines.append(
            f"| `{row['backend_id']}` | `{row['status']}` | {row['action']} | {row['reason']} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_environment_markdown(path: Path, payload: Mapping[str, object]) -> None:
    lines = [
        "# Stage 9 Environment Compatibility Matrix",
        "",
        "| Left | Right | Single-process composition |",
        "|---|---|---|",
    ]
    for row in payload["profile_pairs"]:
        lines.append(
            f"| `{row['left']}` | `{row['right']}` | {'yes' if row['single_process_composable'] else 'no'} |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_coverage_markdown(path: Path, payload: Mapping[str, object]) -> None:
    lines = [
        "# Stage 9 Benchmark Coverage",
        "",
        f"- Fixed items: `{payload['item_count']}`",
        f"- Scenarios: `{payload['scenario_count']}`",
        f"- Item-set hash: `{payload['item_set_sha256']}`",
        "- Missing and failed outputs remain in denominators: `true`",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _qualification_summary(protocol: Mapping[str, object]) -> dict[str, object]:
    path = TOOL_ROOT / str(protocol["qualification"]["summary_path"])
    payload = read_json(path)
    if payload.get("schema_version") != "extended-backend-qualification-summary.v1":
        raise ValueError("unsupported Stage 8 qualification summary")
    return payload


def _manifest_identity(
    summary: Mapping[str, object], manifest_path: Path
) -> dict[str, object]:
    identities = summary.get("manifest_identities")
    if not isinstance(identities, Mapping) or not isinstance(
        identities.get("small"), Mapping
    ):
        raise ValueError("manifest summary has no small identity")
    identity = deepcopy(dict(identities["small"]))
    if file_sha256(manifest_path) != identity.get("sha256"):
        raise ValueError("small manifest hash mismatch")
    identity["path"] = manifest_path.name
    return identity


def _public_definition(value: Mapping[str, object]) -> dict[str, object]:
    result = deepcopy(dict(value))
    result.pop("pipeline_identity", None)
    return result


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values))


def _validate_selected(values: Sequence[str], allowed: set[str], label: str) -> None:
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"unknown {label} value(s): {unknown}")


def _tool_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(TOOL_ROOT).as_posix()
    except ValueError:
        return f"external:{path.name}"
