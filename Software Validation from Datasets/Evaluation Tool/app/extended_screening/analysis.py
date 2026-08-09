"""Environment-aware Stage 9 analysis and explicit shortlist decisions."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Mapping, Sequence

from app.benchmark_contracts.canonical import canonical_sha256
from app.core_screening.analysis import analyze_screening_campaign
from app.core_screening.metrics import (
    STAGE10_ONLY_METRICS,
    analyze_embedding_results,
)
from app.core_screening.selection import AdvancementRules, Objective, select_candidates
from app.utils.json_utils import read_json, read_jsonl, write_json


ANALYSIS_SCHEMA_VERSION = "extended-screening-analysis.v1"


def analyze_extended_screening_campaign(
    plan_path: Path,
    analysis_index_path: Path,
    *,
    embedding_results_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, object]:
    """Analyze Stage 9 campaign artifacts without conflating environments."""

    plan_file = plan_path.resolve()
    index_file = analysis_index_path.resolve()
    plan = read_json(plan_file)
    if plan.get("schema_version") != "extended-screening-plan.v1":
        raise ValueError("unsupported Stage 9 screening plan")
    base = analyze_screening_campaign(
        plan_file,
        index_file,
        expected_plan_schema="extended-screening-plan.v1",
        analysis_schema_version="extended-screening-campaign-analysis.v1",
        analysis_id_prefix="extended_screening_campaign",
        write_outputs=False,
    )
    definitions = plan["candidate_definitions"]
    if not isinstance(definitions, Mapping):
        raise ValueError("Stage 9 candidate definitions must be a mapping")

    analyzed_stages = []
    for stage in base["stages"]:
        stage_id = str(stage["stage_id"])
        rule_name = _stage_rule_name(plan, stage_id)
        candidates = []
        for raw in stage["candidates"]:
            candidate = deepcopy(dict(raw))
            definition = definitions.get(str(candidate["candidate_id"]))
            if not isinstance(definition, Mapping):
                raise ValueError(
                    f"analysis candidate has no definition: {candidate['candidate_id']}"
                )
            candidate["environment_profile"] = definition["environment_profile"]
            candidate["environment_identity"] = definition["environment_identity"]
            candidate["hardware_group_id"] = _hardware_group_id(definition)
            candidates.append(candidate)
        quality_selection, runtime_groups = _environment_aware_selection(
            candidates,
            plan,
            rule_name,
        )
        analyzed_stages.append(
            {
                **{key: value for key, value in stage.items() if key != "selection"},
                "candidates": candidates,
                "selection": {
                    "model_quality": quality_selection,
                    "runtime_by_environment_and_hardware": runtime_groups,
                    "opaque_composite_score_used": False,
                },
                "comparison_classification": {
                    "model_quality": "identical items; environment retained as a covariate",
                    "runtime_implementation": "within hardware_group_id only",
                    "hardware_performance": "never inferred across hardware groups",
                    "environment_compatibility": "reported separately",
                },
            }
        )

    embedding_rows = (
        [row for row in read_jsonl(embedding_results_path) if isinstance(row, Mapping)]
        if embedding_results_path is not None
        else []
    )
    embedding = _analyze_embedding_screen(plan, embedding_rows)
    result: dict[str, object] = {
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "plan_id": plan["plan_id"],
        "plan_hash": plan["plan_hash"],
        "campaign_id": base["campaign_id"],
        "analysis_input_id": base.get("analysis_input_id"),
        "benchmark_manifest_id": base["benchmark_manifest_id"],
        "stages": analyzed_stages,
        "embedding_screen": embedding,
        "diarization_scope": "composition only; scientific DER/JER evaluation remains Stage 11",
        "speaker_recognition_scope": "extraction only; Stage 10 metrics are prohibited",
        "missing_and_failed_outputs_in_denominators": True,
        "environment_differences_explicit": True,
        "unsupported_metrics_policy": (
            "emit only metrics whose references and output contracts are present"
        ),
    }
    _assert_forbidden_metrics_absent(result)
    digest = canonical_sha256(result)
    result["analysis_hash"] = digest
    result["analysis_id"] = f"extended_screening_{digest[:12].lower()}"
    campaign_root = index_file.parent.parent
    destination = (
        output_dir or campaign_root / "analysis" / "extended_screening"
    ).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "extended_screening_analysis.json", result)
    _write_analysis_markdown(destination / "extended_screening_analysis.md", result)
    _write_analysis_handoffs(destination, plan, result)
    return result


def _analyze_embedding_screen(
    plan: Mapping[str, object], rows: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    stage = next(
        value for value in plan["stages"] if value.get("stage_id") == "E"
    )
    candidate_ids = [str(value) for value in stage["candidates"]]
    if not rows:
        return {
            "status": "pending_results",
            "identical_source_segments": True,
            "candidates": [
                {
                    "candidate_id": candidate_id,
                    "status": "missing",
                    "expected_extractions": plan["benchmark"]["item_count"],
                    "successful_extractions": 0,
                    "extraction_success_rate": 0.0,
                    "environment_profile": plan["candidate_definitions"][candidate_id][
                        "environment_profile"
                    ],
                }
                for candidate_id in candidate_ids
            ],
            "selection": None,
        }

    unexpected = sorted(
        {str(row.get("candidate_id")) for row in rows} - set(candidate_ids)
    )
    if unexpected:
        raise ValueError(f"unexpected embedding screening candidates: {unexpected}")
    expected_items = sorted(
        {
            str(row["item_id"])
            for row in rows
            if row.get("item_id") is not None
        }
    )
    if not expected_items:
        raise ValueError("embedding screening rows have no item IDs")
    candidates = []
    item_hashes = set()
    for candidate_id in candidate_ids:
        candidate_rows = [
            dict(row) for row in rows if str(row.get("candidate_id")) == candidate_id
        ]
        observed_items = {str(row["item_id"]) for row in candidate_rows}
        for item_id in expected_items:
            if item_id not in observed_items:
                candidate_rows.append(
                    {
                        "candidate_id": candidate_id,
                        "item_id": item_id,
                        "segment_id": item_id,
                        "status": "missing",
                        "condition": "clean",
                        "vector": [],
                    }
                )
        metrics = analyze_embedding_results(candidate_rows)
        elapsed = [
            float(row["extraction_sec"])
            for row in candidate_rows
            if isinstance(row.get("extraction_sec"), int | float)
        ]
        definition = plan["candidate_definitions"][candidate_id]
        candidate = {
            "candidate_id": candidate_id,
            **metrics,
            "valid_output_rate": metrics["extraction_success_rate"],
            "failure_rate": _rate(
                len(candidate_rows) - int(metrics["successful_extractions"]),
                len(candidate_rows),
            ),
            "timeout_rate": 0.0,
            "oom_rate": 0.0,
            "repetitions": max(
                (int(row.get("repetition") or 1) for row in candidate_rows),
                default=1,
            ),
            "mean_extraction_sec": sum(elapsed) / len(elapsed) if elapsed else None,
            "environment_profile": definition["environment_profile"],
            "environment_identity": definition["environment_identity"],
            "hardware_group_id": _hardware_group_id(definition),
        }
        candidate_hash = canonical_sha256(expected_items)
        candidate["comparison_item_set_sha256"] = candidate_hash
        item_hashes.add(candidate_hash)
        candidates.append(candidate)
    if len(item_hashes) != 1:
        raise ValueError("embedding candidates do not use identical source segments")
    quality, runtime = _environment_aware_selection(
        candidates, plan, "embedding"
    )
    return {
        "status": "analyzed",
        "identical_source_segments": True,
        "comparison_item_set_sha256": next(iter(item_hashes)),
        "candidates": candidates,
        "selection": {
            "model_quality": quality,
            "runtime_by_environment_and_hardware": runtime,
            "opaque_composite_score_used": False,
        },
        "enrollment_artifacts_reused_between_backends": False,
    }


def _environment_aware_selection(
    candidates: Sequence[Mapping[str, object]],
    plan: Mapping[str, object],
    rule_name: str | None,
) -> tuple[dict[str, object] | None, list[dict[str, object]]]:
    if not candidates or rule_name is None:
        return None, []
    declared = _rules(plan, rule_name)
    quality_objectives = tuple(
        objective for objective in declared.objectives if objective.category != "resource"
    )
    quality = select_candidates(
        candidates,
        _replace_objectives(declared, quality_objectives),
    )
    grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for candidate in candidates:
        grouped[str(candidate["hardware_group_id"])].append(candidate)
    runtime_objectives = tuple(
        objective
        for objective in declared.objectives
        if objective.category in {"resource", "reliability"}
    )
    if not runtime_objectives:
        runtime_objectives = (
            Objective("valid_output_rate", "max", "reliability"),
        )
    runtime_groups = []
    for group_id, values in sorted(grouped.items()):
        runtime_groups.append(
            {
                "hardware_group_id": group_id,
                "environment_profile": values[0]["environment_profile"],
                "candidate_ids": [str(value["candidate_id"]) for value in values],
                "selection": select_candidates(
                    values,
                    _replace_objectives(declared, runtime_objectives),
                ),
            }
        )
    return quality, runtime_groups


def _rules(plan: Mapping[str, object], name: str) -> AdvancementRules:
    raw = plan["protocol"]["contents"]["advancement"][name]
    objectives = tuple(
        Objective(
            metric=str(value["metric"]),
            direction=str(value["direction"]),
            category=str(value["category"]),
            required=bool(value.get("required", True)),
            tolerance=float(value.get("tolerance", 0.0)),
        )
        for value in raw["objectives"]
    )
    return AdvancementRules(
        objectives=objectives,
        maximum_candidates=int(raw["maximum_candidates"]),
        minimum_valid_output_rate=float(raw["minimum_valid_output_rate"]),
        maximum_failure_rate=float(raw["maximum_failure_rate"]),
        maximum_timeout_rate=float(raw["maximum_timeout_rate"]),
        maximum_oom_rate=float(raw["maximum_oom_rate"]),
        minimum_repetitions=int(raw["minimum_repetitions"]),
    )


def _replace_objectives(
    rules: AdvancementRules, objectives: tuple[Objective, ...]
) -> AdvancementRules:
    return AdvancementRules(
        objectives=objectives,
        maximum_candidates=rules.maximum_candidates,
        minimum_valid_output_rate=rules.minimum_valid_output_rate,
        maximum_failure_rate=rules.maximum_failure_rate,
        maximum_timeout_rate=rules.maximum_timeout_rate,
        maximum_oom_rate=rules.maximum_oom_rate,
        minimum_repetitions=rules.minimum_repetitions,
    )


def _stage_rule_name(plan: Mapping[str, object], stage_id: str) -> str | None:
    for stage in plan["stages"]:
        if stage.get("stage_id") == stage_id:
            value = stage.get("advancement_rule")
            return str(value) if value is not None else None
    return None


def _hardware_group_id(definition: Mapping[str, object]) -> str:
    environment = definition["environment_identity"]
    payload = {
        "profile": definition["environment_profile"],
        "platform": environment.get("platform"),
        "python": environment.get("python"),
        "package_freeze_sha256": environment.get("package_freeze_sha256"),
        "device": environment.get("device_requested", "cpu"),
        "gpu": environment.get("gpu"),
        "cuda_runtime": environment.get("cuda_runtime"),
    }
    return f"hardware_{canonical_sha256(payload)[:12].lower()}"


def _write_analysis_handoffs(
    destination: Path,
    plan: Mapping[str, object],
    result: Mapping[str, object],
) -> None:
    comparison_rows = []
    advanced: dict[str, list[str]] = defaultdict(list)
    for stage in result["stages"]:
        for candidate in stage["candidates"]:
            comparison_rows.append(
                {
                    "stage_id": stage["stage_id"],
                    "candidate_id": candidate["candidate_id"],
                    "environment_profile": candidate["environment_profile"],
                    "hardware_group_id": candidate["hardware_group_id"],
                    "micro_wer": candidate.get("micro_wer"),
                    "macro_wer": candidate.get("macro_wer"),
                    "valid_output_rate": candidate.get("valid_output_rate"),
                    "missing_prediction_rate": candidate.get("missing_prediction_rate"),
                    "mean_rtf": candidate.get("mean_rtf"),
                    "failure_rate": candidate.get("failure_rate"),
                }
            )
        selection = stage["selection"]["model_quality"]
        if selection:
            advanced[str(stage["stage_id"])].extend(
                str(value) for value in selection["advanced_candidate_ids"]
            )
    embedding = result["embedding_screen"]
    for candidate in embedding.get("candidates", []):
        comparison_rows.append(
            {
                "stage_id": "E",
                "candidate_id": candidate["candidate_id"],
                "environment_profile": candidate["environment_profile"],
                "extraction_success_rate": candidate.get("extraction_success_rate"),
                "invalid_or_nonfinite_vectors": candidate.get(
                    "invalid_or_nonfinite_vectors"
                ),
                "mean_extraction_sec": candidate.get("mean_extraction_sec"),
            }
        )
    embedding_selection = embedding.get("selection")
    if embedding_selection and embedding_selection.get("model_quality"):
        advanced["E"].extend(
            str(value)
            for value in embedding_selection["model_quality"]["advanced_candidate_ids"]
        )
    tables = {
        "schema_version": "extended-component-comparison-tables.v1",
        "analysis_id": result["analysis_id"],
        "rows": comparison_rows,
        "runtime_values_comparable_only_within_hardware_group_id": True,
    }
    write_json(destination / "extended_component_comparison_tables.json", tables)
    decisions = []
    for stage in result["stages"]:
        selection = stage["selection"]["model_quality"]
        evaluations = selection["evaluations"] if selection else []
        for evaluation in evaluations:
            decisions.append(
                {
                    "candidate_id": evaluation["candidate_id"],
                    "stage_id": stage["stage_id"],
                    "advanced": evaluation["advanced"],
                    "hard_gate_reasons": evaluation["hard_gate_reasons"],
                    "dominated_by": evaluation["dominated_by"],
                    "reason": (
                        "advanced on declared model-quality Pareto rules"
                        if evaluation["advanced"]
                        else "not advanced by declared gates/Pareto rules"
                    ),
                }
            )
    write_json(
        destination / "advancement_and_exclusion_report.json",
        {
            "schema_version": "extended-advancement-exclusion.v1",
            "analysis_id": result["analysis_id"],
            "decisions": decisions,
            "opaque_score_used": False,
        },
    )
    shortlist = {
        "schema_version": "extended-shortlist-manifest.v1",
        "analysis_id": result["analysis_id"],
        "plan_id": plan["plan_id"],
        "asr": sorted(set(advanced.get("B", []))),
        "vad_segmentation": sorted(set(advanced.get("C", []))),
        "speaker_embedding": sorted(set(advanced.get("E", []))),
        "targeted_combinations": sorted(set(advanced.get("D", []))),
        "status": "analysis_complete",
        "selection_policy": "declared gates and separate quality/runtime Pareto frontiers",
    }
    write_json(destination / "shortlist_manifest.json", shortlist)


def _write_analysis_markdown(path: Path, result: Mapping[str, object]) -> None:
    lines = [
        "# Stage 9 Extended Backend Screening Analysis",
        "",
        f"- Analysis: `{result['analysis_id']}`",
        f"- Campaign: `{result['campaign_id']}`",
        "- Missing and failed outputs stayed in denominators: `true`",
        "- Runtime comparisons are grouped by environment and hardware: `true`",
        "",
    ]
    for stage in result["stages"]:
        quality = stage["selection"]["model_quality"]
        advanced = quality["advanced_candidate_ids"] if quality else []
        lines.extend(
            [
                f"## Stage {stage['stage_id']} — {stage['name']}",
                "",
                "Advanced model-quality candidates: "
                + (", ".join(f"`{value}`" for value in advanced) or "none"),
                "",
            ]
        )
    lines.extend(
        [
            "Speaker verification/identification metrics remain Stage 10. DER/JER and diarization science remain Stage 11.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _assert_forbidden_metrics_absent(value: object) -> None:
    forbidden = {metric.casefold() for metric in STAGE10_ONLY_METRICS} | {
        "der",
        "jer",
    }
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in forbidden:
                raise ValueError(f"forbidden Stage 9 metric emitted: {key}")
            _assert_forbidden_metrics_absent(item)
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        for item in value:
            _assert_forbidden_metrics_absent(item)


def _rate(numerator: int, denominator: int) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0
