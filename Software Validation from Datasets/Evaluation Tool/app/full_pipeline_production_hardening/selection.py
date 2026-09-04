"""Predeclared, non-composite Pareto selection for Prompt-7 candidates."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix, PipelineSelection

from . import MATRIX_PATH, RUNTIME_PATH, scope_fields
from .io import HardeningError, read_csv


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    direction: str
    aliases: tuple[str, ...]
    preferred_files: tuple[str, ...]
    conservative_aggregation: str = "worst"


PRIORITIES = (
    MetricSpec(
        "wrong_known_time_sec",
        "minimize",
        ("wrong_known_time_sec", "wrong_known_speaker_time_sec"),
        ("all18_finalist_summary.csv", "online_identity.csv", "extended_summary.csv"),
    ),
    MetricSpec(
        "stranger_false_known_time_sec",
        "minimize",
        ("stranger_false_known_time_sec", "stranger_false_known_sec"),
        ("all18_finalist_summary.csv", "online_identity.csv", "extended_summary.csv"),
    ),
    MetricSpec(
        "premature_wrong_name_exposure_sec",
        "minimize",
        ("premature_wrong_name_exposure_sec", "wrong_name_dwell_sec"),
        ("online_identity.csv", "ux_latency.csv", "extended_summary.csv"),
    ),
    MetricSpec(
        "speaker_attributed_wer",
        "minimize",
        ("speaker_attributed_wer", "cpwer"),
        ("all18_finalist_summary.csv", "extended_summary.csv"),
    ),
    MetricSpec(
        "correctly_named_known_rate",
        "maximize",
        ("correctly_named_known_rate", "correctly_named_known_speaker_time_rate"),
        ("all18_finalist_summary.csv", "online_identity.csv", "extended_summary.csv"),
        "worst",
    ),
    MetricSpec(
        "anonymous_confusion_rate",
        "minimize",
        ("speaker_confusion_rate", "anonymous_confusion_rate", "der"),
        (
            "all18_finalist_summary.csv",
            "online_diarization.csv",
            "extended_summary.csv",
        ),
    ),
    MetricSpec(
        "first_readable_text_latency_sec",
        "minimize",
        ("first_readable_partial_latency_sec", "first_readable_text_latency_sec"),
        ("true_streaming_asr.csv", "ux_latency.csv", "all18_finalist_summary.csv"),
    ),
    MetricSpec(
        "stable_transcript_latency_sec",
        "minimize",
        ("stable_prefix_latency_sec", "stable_transcript_latency_sec"),
        ("true_streaming_asr.csv", "ux_latency.csv", "all18_finalist_summary.csv"),
    ),
    MetricSpec(
        "stable_correct_name_latency_sec",
        "minimize",
        ("stable_name_latency_sec", "time_to_stable_correct_speaker_name_sec"),
        ("online_identity.csv", "ux_latency.csv", "extended_summary.csv"),
    ),
    MetricSpec(
        "revision_count",
        "minimize",
        ("revision_count", "identity_revision_count", "transcript_revision_count"),
        ("label_revision.csv", "all18_finalist_summary.csv", "extended_summary.csv"),
    ),
    MetricSpec(
        "failure_rate",
        "minimize",
        (
            "failure_rate",
            "output_failure_rate",
            "failure_count",
            "failed_job_count",
            "explicit_failed_job_count",
        ),
        (
            "reliability_results.csv",
            "extended_summary.csv",
            "all18_finalist_summary.csv",
        ),
    ),
    MetricSpec(
        "total_rtf",
        "minimize",
        ("total_rtf", "realtime_factor", "rtf"),
        ("serial_resources.csv", "all18_finalist_summary.csv", "extended_summary.csv"),
    ),
)

RESOURCE_SPECS = (
    MetricSpec(
        "peak_rss_bytes",
        "minimize",
        ("peak_rss_bytes", "peak_ram_bytes"),
        ("serial_resources.csv",),
    ),
    MetricSpec("model_bytes", "minimize", ("model_bytes",), ("serial_resources.csv",)),
    MetricSpec(
        "startup_sec",
        "minimize",
        ("startup_sec", "startup_latency_sec"),
        ("serial_resources.csv",),
    ),
    MetricSpec(
        "model_worker_count",
        "minimize",
        ("model_worker_count", "worker_count"),
        ("serial_resources.csv",),
    ),
)


def select_candidates(
    *,
    candidate_ids: Sequence[str],
    evidence_files: Mapping[str, Path],
    runtime_bindings: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_PATH)
    candidates = list(dict.fromkeys(str(item) for item in candidate_ids))
    if not 6 <= len(candidates) <= 8 or set(candidates) - set(matrix.pipeline_ids):
        raise HardeningError("candidate pool is not the predeclared six-plus-two set")
    evidence = _load_evidence(evidence_files)
    rows: list[dict[str, object]] = []
    for pipeline_id in candidates:
        binding = runtime_bindings.get(pipeline_id)
        if not isinstance(binding, Mapping):
            raise HardeningError(
                f"candidate lacks a frozen runtime binding: {pipeline_id}"
            )
        if (
            binding.get("pipeline_id") != pipeline_id
            or binding.get("unknown_only_fallback_allowed") is not False
        ):
            raise HardeningError(
                f"candidate runtime binding is not fail-closed: {pipeline_id}"
            )
        selection = matrix.resolve(pipeline_id)
        metrics: dict[str, float | None] = {}
        provenance: dict[str, object] = {}
        for spec in (*PRIORITIES, *RESOURCE_SPECS):
            value, source = _metric_value(evidence, pipeline_id=pipeline_id, spec=spec)
            metrics[spec.metric_id] = value
            provenance[spec.metric_id] = source
        licensing = _licensing_record(selection)
        required = {
            "wrong_known_time_sec",
            "stranger_false_known_time_sec",
            "speaker_attributed_wer",
            "correctly_named_known_rate",
            "failure_rate",
            "total_rtf",
        }
        missing_required = sorted(key for key in required if metrics[key] is None)
        reliability_eligible = (
            not missing_required
            and float(metrics["failure_rate"] or 0.0) == 0.0
            and float(metrics["total_rtf"] or math.inf) <= 1.0
        )
        production_role_eligible = bool(
            reliability_eligible
            and binding.get("production_role_eligible") is True
            and binding.get("binding_status") == "BOUND_FROZEN_ANCHOR"
            and binding.get("frozen_anchor") is True
        )
        rows.append(
            {
                **scope_fields(),
                "pipeline_id": pipeline_id,
                "asr_alias": selection.asr_alias,
                "diarization_alias": selection.diarization_alias,
                "identity_alias": selection.identity_alias,
                "hybrid_label": selection.hybrid_label,
                "metrics": metrics,
                "metric_provenance": provenance,
                "missing_required_metrics": missing_required,
                "reliability_eligible": reliability_eligible,
                "production_role_eligible": production_role_eligible,
                "runtime_binding_status": binding.get("binding_status"),
                "runtime_binding": dict(binding),
                "unknown_only_policy_executed": False,
                "ineligibility_reason": (
                    "missing_required_metrics"
                    if missing_required
                    else "failure_rate_nonzero"
                    if float(metrics["failure_rate"] or 0.0) != 0.0
                    else "not_realtime"
                    if float(metrics["total_rtf"] or math.inf) > 1.0
                    else None
                ),
                "production_role_ineligibility_reason": (
                    None
                    if production_role_eligible
                    else binding.get("exclusion_reason")
                    or "candidate_did_not_satisfy_reliability_constraints"
                ),
                **licensing,
            }
        )
    eligible = [row for row in rows if row["reliability_eligible"] is True]
    if not eligible:
        raise HardeningError(
            "no predeclared candidate satisfies reliability constraints"
        )
    frontier_ids = _pareto_frontier(eligible, PRIORITIES)
    technical = sorted(eligible, key=_technical_key)
    for rank, row in enumerate(technical, start=1):
        row["technical_rank"] = rank
        row["pareto_frontier"] = row["pipeline_id"] in frontier_ids
    licensing = sorted(
        rows,
        key=lambda row: (
            int(row["component_license_review_count"]),
            str(row["pipeline_id"]),
        ),
    )
    for rank, row in enumerate(licensing, start=1):
        row["licensing_rank"] = rank

    role_eligible = [row for row in rows if row["production_role_eligible"] is True]
    if not role_eligible:
        raise HardeningError(
            "no frozen anchor is both reliability-qualified and runtime-bound"
        )
    role_frontier_ids = _pareto_frontier(role_eligible, PRIORITIES)
    frontier = [
        row
        for row in technical
        if row["pipeline_id"] in role_frontier_ids
        and row["production_role_eligible"] is True
    ]
    primary = frontier[0]
    fallback_pool = [
        row for row in frontier[1:] if _safety_nondominated_against(row, primary)
    ]
    fallback = min(fallback_pool, key=_resource_key) if fallback_pool else None
    used = {str(primary["pipeline_id"])}
    if fallback is not None:
        used.add(str(fallback["pipeline_id"]))
    alternatives = [
        row
        for row in frontier
        if str(row["pipeline_id"]) not in used
        and _adds_alternative_value(row, primary, fallback)
    ]
    alternative = (
        min(
            alternatives,
            key=lambda row: (
                int(row["component_license_review_count"]),
                int(row["technical_rank"]),
            ),
        )
        if alternatives
        else None
    )
    roles = {
        "PRIMARY": str(primary["pipeline_id"]),
        "FALLBACK": str(fallback["pipeline_id"]) if fallback else None,
        "ALTERNATIVE": str(alternative["pipeline_id"]) if alternative else None,
    }
    for row in rows:
        row["selected_role"] = next(
            (
                role
                for role, pipeline in roles.items()
                if pipeline == row["pipeline_id"]
            ),
            None,
        )
    return {
        "schema_version": "full-pipeline-production-candidate-selection.v1",
        **scope_fields(),
        "status": "PASS",
        "selection_policy_id": "full_pipeline_constraint_pareto_selection.v1",
        "weighted_score_used": False,
        "priorities": [
            {
                "rank": index,
                "metric_id": spec.metric_id,
                "direction": spec.direction,
            }
            for index, spec in enumerate(PRIORITIES, start=1)
        ],
        "technical_and_licensing_rankings_separate": True,
        "candidate_pool": candidates,
        "pareto_frontier_pipeline_ids": sorted(frontier_ids),
        "production_role_frontier_pipeline_ids": sorted(role_frontier_ids),
        "roles": roles,
        "selected_pipeline_count": sum(value is not None for value in roles.values()),
        "candidates": rows,
        "held_out_thresholds_changed": False,
        "production_threshold_retuning_performed": False,
    }


def h2_simplicity_rows(
    selection_result: Mapping[str, object],
) -> list[dict[str, object]]:
    raw = selection_result.get("candidates")
    rows = (
        [dict(row) for row in raw if isinstance(row, Mapping)]
        if isinstance(raw, list)
        else []
    )
    lookup = {str(row["pipeline_id"]): row for row in rows}
    output: list[dict[str, object]] = []
    for asr in ("ao", "ag"):
        h2 = lookup.get(f"fullpipe_v1_{asr}_dr_ir")
        if h2 is None:
            continue
        for label, comparator_id in (
            ("H4", f"fullpipe_v1_{asr}_dw_ir"),
            ("H5", f"fullpipe_v1_{asr}_dr_ie"),
        ):
            comparator = lookup.get(comparator_id)
            if comparator is None:
                continue
            h2_metrics = h2["metrics"]
            other_metrics = comparator["metrics"]
            assert isinstance(h2_metrics, Mapping)
            assert isinstance(other_metrics, Mapping)
            measured: dict[str, object] = {}
            supported = 0
            for metric in (
                "total_rtf",
                "peak_rss_bytes",
                "model_bytes",
                "startup_sec",
                "model_worker_count",
            ):
                left = h2_metrics.get(metric)
                right = other_metrics.get(metric)
                delta = (
                    float(left) - float(right)
                    if left is not None and right is not None
                    else None
                )
                measured[f"h2_{metric}"] = left
                measured[f"comparator_{metric}"] = right
                measured[f"h2_minus_comparator_{metric}"] = delta
                supported += int(delta is not None)
            output.append(
                {
                    **scope_fields(),
                    "asr_alias": asr.upper(),
                    "h2_pipeline_id": h2["pipeline_id"],
                    "comparator_hybrid_label": label,
                    "comparator_pipeline_id": comparator_id,
                    "measurement_status": "MEASURED"
                    if supported == 5
                    else "PARTIAL"
                    if supported
                    else "UNSUPPORTED",
                    "same_model_benefit_assumed": False,
                    **measured,
                }
            )
    return output


def _load_evidence(files: Mapping[str, Path]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for name, path in files.items():
        if path.suffix.casefold() == ".csv":
            result[name] = read_csv(path)
    return result


def _metric_value(
    evidence: Mapping[str, Sequence[Mapping[str, str]]],
    *,
    pipeline_id: str,
    spec: MetricSpec,
) -> tuple[float | None, dict[str, object]]:
    for filename in spec.preferred_files:
        rows = [
            row
            for row in evidence.get(filename, ())
            if str(row.get("pipeline_id") or row.get("preset_id") or "") == pipeline_id
        ]
        values: list[float] = []
        fields: list[str] = []
        for row in rows:
            value, field = _row_metric_value(row, spec.aliases)
            if value is not None and field is not None:
                values.append(value)
                fields.append(field)
        if values:
            value = max(values) if spec.direction == "minimize" else min(values)
            return value, {
                "source_file": filename,
                "source_fields": sorted(set(fields)),
                "observation_count": len(values),
                "aggregation": "single"
                if len(values) == 1
                else "conservative_worst_case",
            }
    return None, {
        "source_file": None,
        "observation_count": 0,
        "aggregation": "missing",
    }


def _row_metric_value(
    row: Mapping[str, str], aliases: Sequence[str]
) -> tuple[float | None, str | None]:
    metric_id = str(row.get("metric_id") or "")
    if metric_id in aliases:
        value = _number(row.get("value"))
        status = str(row.get("status") or "computed").casefold()
        if value is not None and status not in {"missing", "unsupported", "undefined"}:
            return value, f"metric_id={metric_id}"
    for alias in aliases:
        keys = [key for key in row if key == alias or key.endswith(f"__{alias}")]
        for key in keys:
            value = _number(row.get(key))
            status = str(row.get(f"{key}__status") or "computed").casefold()
            if value is not None and status not in {
                "missing",
                "unsupported",
                "undefined",
            }:
                return value, key
    return None, None


def _number(value: object) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _pareto_frontier(
    rows: Sequence[Mapping[str, object]], specs: Sequence[MetricSpec]
) -> set[str]:
    frontier: set[str] = set()
    for candidate in rows:
        if not any(
            _dominates(other, candidate, specs)
            for other in rows
            if other is not candidate
        ):
            frontier.add(str(candidate["pipeline_id"]))
    return frontier


def _dominates(
    left: Mapping[str, object],
    right: Mapping[str, object],
    specs: Sequence[MetricSpec],
) -> bool:
    left_metrics = left["metrics"]
    right_metrics = right["metrics"]
    assert isinstance(left_metrics, Mapping)
    assert isinstance(right_metrics, Mapping)
    no_worse = True
    strictly_better = False
    for spec in specs:
        left_value = _or_worst(left_metrics.get(spec.metric_id), spec.direction)
        right_value = _or_worst(right_metrics.get(spec.metric_id), spec.direction)
        if spec.direction == "minimize":
            no_worse &= left_value <= right_value
            strictly_better |= left_value < right_value
        else:
            no_worse &= left_value >= right_value
            strictly_better |= left_value > right_value
    return no_worse and strictly_better


def _technical_key(row: Mapping[str, object]) -> tuple[object, ...]:
    metrics = row["metrics"]
    assert isinstance(metrics, Mapping)
    return tuple(
        _or_worst(metrics.get(spec.metric_id), spec.direction)
        * (1.0 if spec.direction == "minimize" else -1.0)
        for spec in PRIORITIES
    ) + (str(row["pipeline_id"]),)


def _resource_key(row: Mapping[str, object]) -> tuple[object, ...]:
    metrics = row["metrics"]
    assert isinstance(metrics, Mapping)
    return tuple(
        _or_worst(metrics.get(spec.metric_id), "minimize") for spec in RESOURCE_SPECS
    ) + (int(row["technical_rank"]), str(row["pipeline_id"]))


def _safety_nondominated_against(
    candidate: Mapping[str, object], primary: Mapping[str, object]
) -> bool:
    safety = PRIORITIES[:3]
    return not _dominates(primary, candidate, safety)


def _adds_alternative_value(
    candidate: Mapping[str, object],
    primary: Mapping[str, object],
    fallback: Mapping[str, object] | None,
) -> bool:
    chosen = [primary, *([fallback] if fallback is not None else [])]
    distinct = any(
        candidate["asr_alias"] != row["asr_alias"]
        or candidate["identity_alias"] != row["identity_alias"]
        for row in chosen
    )
    cleaner = int(candidate["component_license_review_count"]) < min(
        int(row["component_license_review_count"]) for row in chosen
    )
    return distinct or cleaner


def _or_worst(value: object, direction: str) -> float:
    number = _number(value)
    if number is not None:
        return number
    return math.inf if direction == "minimize" else -math.inf


def _licensing_record(selection: PipelineSelection) -> dict[str, object]:
    statuses: list[str] = []
    for component in (
        selection.asr,
        selection.diarization,
        selection.diarization_embedding,
        selection.identity,
    ):
        for key, value in component.items():
            name = str(key).casefold()
            if any(
                token in name for token in ("license", "provenance", "terms", "warning")
            ):
                text = str(value).strip()
                if text:
                    statuses.append(text)
    risks = [
        value
        for value in statuses
        if any(
            token in value.upper()
            for token in ("REVIEW", "UNRESOLVED", "GATED", "DO_NOT", "UNKNOWN")
        )
    ]
    return {
        "component_license_review_count": len(set(risks)),
        "component_license_statuses": sorted(set(statuses)),
        "component_license_risks": sorted(set(risks)),
        "repository_redistribution_status": "UNRESOLVED_NO_REPOSITORY_LICENSE_FILE",
        "commercially_cleared_claimed": False,
    }


__all__ = ["PRIORITIES", "h2_simplicity_rows", "select_candidates"]
