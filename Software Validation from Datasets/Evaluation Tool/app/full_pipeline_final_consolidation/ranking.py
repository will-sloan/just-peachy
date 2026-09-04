"""Transparent multi-view rankings and Pareto analysis; no composite score."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix

from . import scope_fields
from .evidence import CompletionEvidence, EvidenceBundle, load_yaml
from .io import FinalConsolidationError, read_csv, read_json


@dataclass(frozen=True)
class Metric:
    name: str
    direction: str
    aliases: tuple[str, ...]


TECHNICAL_METRICS = (
    Metric(
        "wrong_known_time_sec",
        "min",
        ("wrong_known_time_sec", "wrong_known_speaker_time_sec"),
    ),
    Metric(
        "stranger_false_known_time_sec",
        "min",
        ("stranger_false_known_time_sec", "stranger_false_known_sec"),
    ),
    Metric(
        "premature_wrong_name_exposure_sec",
        "min",
        (
            "premature_wrong_name_exposure_sec",
            "wrong_name_dwell_sec",
            "time_to_false_identification_sec",
        ),
    ),
    Metric("speaker_attributed_wer", "min", ("speaker_attributed_wer", "cpwer")),
    Metric(
        "correctly_named_known_rate",
        "max",
        ("correctly_named_known_rate", "correctly_named_known_speaker_time_rate"),
    ),
    Metric(
        "anonymous_speaker_confusion_rate",
        "min",
        ("speaker_confusion_rate", "anonymous_speaker_confusion_rate"),
    ),
    Metric(
        "first_readable_partial_latency_sec",
        "min",
        ("first_readable_partial_latency_sec", "first_readable_text_latency_sec"),
    ),
    Metric(
        "stable_prefix_latency_sec",
        "min",
        ("stable_prefix_latency_sec", "stable_transcript_latency_sec"),
    ),
    Metric(
        "stable_correct_name_latency_sec",
        "min",
        (
            "stable_name_latency_sec",
            "time_to_confirmed_known_name_sec",
            "stable_correct_name_latency_sec",
        ),
    ),
    Metric(
        "transcript_identity_revision_count",
        "min",
        ("transcript_identity_revision_count",),
    ),
    Metric(
        "reliability_failure_count",
        "min",
        (
            "explicit_failed_job_count",
            "failure_count",
            "output_failure_count",
        ),
    ),
    Metric("total_rtf", "min", ("total_rtf", "realtime_factor", "rtf")),
    Metric(
        "mean_cpu_percent",
        "min",
        ("mean_cpu_percent", "cpu_mean_percent", "average_cpu_percent"),
    ),
    Metric("peak_rss_bytes", "min", ("peak_rss_bytes", "peak_ram_bytes")),
    Metric("model_bytes", "min", ("model_bytes", "total_model_bytes")),
)
UX_METRICS = (
    TECHNICAL_METRICS[0],
    TECHNICAL_METRICS[1],
    TECHNICAL_METRICS[2],
    TECHNICAL_METRICS[6],
    TECHNICAL_METRICS[7],
    TECHNICAL_METRICS[8],
    TECHNICAL_METRICS[9],
)
RESOURCE_METRICS = (
    Metric("total_rtf", "min", ("total_rtf", "realtime_factor", "rtf")),
    Metric(
        "mean_cpu_percent",
        "min",
        ("mean_cpu_percent", "cpu_mean_percent", "average_cpu_percent"),
    ),
    Metric("peak_rss_bytes", "min", ("peak_rss_bytes", "peak_ram_bytes")),
    Metric("model_bytes", "min", ("model_bytes", "total_model_bytes")),
)
DEPLOYMENT_CONTEXT_METRICS = (
    Metric("wer", "min", ("wer", "word_error_rate")),
    Metric("der", "min", ("der", "diarization_error_rate")),
    Metric("jer", "min", ("jer", "jaccard_error_rate")),
)
PARETO_METRICS = (
    TECHNICAL_METRICS[0],
    TECHNICAL_METRICS[1],
    TECHNICAL_METRICS[3],
    TECHNICAL_METRICS[4],
    RESOURCE_METRICS[0],
    RESOURCE_METRICS[2],
)

MATRIX_PRIORITY_CONTRACT = (
    (1, "wrong_known_speaker_time", "minimize"),
    (2, "stranger_false_known_time", "minimize"),
    (3, "premature_wrong_name_exposure", "minimize"),
    (4, "speaker_attributed_word_errors", "minimize"),
    (5, "correctly_named_known_speaker_time", "maximize"),
    (6, "anonymous_speaker_confusion_and_cluster_contamination", "minimize"),
    (7, "time_to_first_readable_text", "minimize"),
    (8, "time_to_stable_transcript", "minimize"),
    (9, "time_to_stable_correct_speaker_name", "minimize"),
    (10, "transcript_and_identity_revisions", "minimize"),
    (11, "real_time_operation_and_reliability", "maintain"),
    (12, "cpu_ram_model_complexity", "minimize_when_scientifically_comparable"),
)


@dataclass(frozen=True)
class RankingResult:
    rows: tuple[Mapping[str, object], ...]
    pareto_rows: tuple[Mapping[str, object], ...]
    roles: Mapping[str, str | None]
    primary: str
    fallback: str | None
    alternative: str | None
    not_worth_continuing: str
    not_worth_reason: str
    policy: Mapping[str, object]


def build_rankings(bundle: EvidenceBundle) -> RankingResult:
    p5 = bundle.completions[5]
    p6 = bundle.completions[6]
    p7 = bundle.completions[7]
    matrix = FullPipelineMatrix(bundle.matrix_path, bundle.runtime_path)
    declared_priorities = _validate_matrix_priority_contract(matrix.matrix)
    core = _core_all18_rows(p5, bundle.pipeline_ids)
    extended_rows = read_csv(p6.one("extended_summary.csv"))
    extended_ids = {
        str(row.get("pipeline_id") or row.get("preset_id") or "")
        for row in extended_rows
    }
    p7_technical = _rank_map(
        read_csv(p7.one("technical_ranking.csv")),
        allowed_ids=set(bundle.pipeline_ids),
        label="Prompt-7 technical ranking",
    )
    p7_licensing = _rank_map(
        read_csv(p7.one("licensing_ranking.csv")),
        allowed_ids=set(bundle.pipeline_ids),
        label="Prompt-7 licensing ranking",
    )
    summary = read_csv(p7.one("production_candidate_summary.csv"))
    catalog = load_yaml(p7.one("production_candidate_catalog.yaml"))
    p6_license = read_json(p6.one("licensing_provenance.json"))
    p7_license = read_json(p7.one("licensing_provenance.json"))
    extended_metrics = _extended_metrics(p6, extended_ids)
    roles, readiness = _roles(catalog, summary, bundle.pipeline_ids)
    selected_ids = {value for value in roles.values() if value}
    if not selected_ids.issubset(extended_ids):
        raise FinalConsolidationError(
            "Prompt-7 selected a pipeline outside the predeclared extended set"
        )

    rows: list[dict[str, object]] = []
    for pipeline_id in bundle.pipeline_ids:
        selection = matrix.resolve(pipeline_id)
        raw = core[pipeline_id]
        metrics = {spec.name: _metric_value(raw, spec) for spec in _unique_metrics()}
        statuses = {spec.name: _metric_status(raw, spec) for spec in _unique_metrics()}
        component_license_evidence = _license_component_evidence(
            selection,
            pipeline_id=pipeline_id,
            p6_document=p6_license,
            p7_document=p7_license,
        )
        license_statuses = sorted(
            {
                status
                for statuses in component_license_evidence.values()
                for status in statuses
            }
        )
        review_count = sum(_needs_review(value) for value in license_statuses)
        rows.append(
            {
                **scope_fields(),
                "schema_version": "full-pipeline-final-ranking.v1",
                "pipeline_id": pipeline_id,
                "asr_alias": selection.asr_alias,
                "diarization_alias": selection.diarization_alias,
                "identity_alias": selection.identity_alias,
                "hybrid_label": selection.hybrid_label,
                **metrics,
                "metric_statuses": statuses,
                "missing_technical_metric_count": sum(
                    metrics[spec.name] is None for spec in TECHNICAL_METRICS
                ),
                "missing_pareto_metric_count": sum(
                    metrics[spec.name] is None for spec in PARETO_METRICS
                ),
                "extended_evidence_status": (
                    "TESTED_IN_PREDECLARED_EXTENDED_SET"
                    if pipeline_id in extended_ids
                    else "NOT_IN_PREDECLARED_EXTENDED_SET"
                ),
                "p5_core_evidence": "EXACT_ALL18_HELDOUT",
                "p6_extended_metrics": extended_metrics.get(pipeline_id),
                "p6_extended_metrics_used_in_all18_rank": False,
                "prompt7_technical_rank": p7_technical.get(pipeline_id),
                "prompt7_licensing_rank": p7_licensing.get(pipeline_id),
                "prompt7_technical_rank_status": (
                    "AVAILABLE"
                    if pipeline_id in p7_technical
                    else "NOT_IN_PROMPT7_TECHNICAL_RANKING"
                ),
                "prompt7_licensing_rank_status": (
                    "AVAILABLE"
                    if pipeline_id in p7_licensing
                    else "NOT_IN_PROMPT7_LICENSING_RANKING"
                ),
                "component_license_statuses": license_statuses,
                "component_license_evidence": component_license_evidence,
                "diarization_embedding_license_statuses": (
                    component_license_evidence["diarization_embedding"]
                ),
                "component_license_review_count": review_count,
                "component_license_review_required": review_count > 0,
                "commercially_cleared_claimed": False,
                "selected_role": next(
                    (role for role, value in roles.items() if value == pipeline_id),
                    None,
                ),
                "software_ready": readiness.get(pipeline_id, False),
                "weighted_composite_score": None,
            }
        )

    _apply_rank(rows, TECHNICAL_METRICS, "technical_performance_rank")
    _apply_rank(rows, UX_METRICS, "user_experience_safety_rank")
    _apply_rank(rows, RESOURCE_METRICS, "resource_efficiency_rank")
    licensing_sorted = sorted(
        rows,
        key=lambda row: (
            int(row["component_license_review_count"]),
            _rank_or_worst(row.get("prompt7_licensing_rank")),
            str(row["pipeline_id"]),
        ),
    )
    for rank, row in enumerate(licensing_sorted, start=1):
        row["deployment_licensing_readiness_rank"] = rank

    eligible = [
        row
        for row in rows
        if int(row["missing_pareto_metric_count"]) == 0
        and _number(row.get("reliability_failure_count")) == 0.0
        and _number(row.get("total_rtf")) is not None
        and float(row["total_rtf"]) <= 1.0
    ]
    if not eligible:
        raise FinalConsolidationError(
            "no all-18 row has complete Pareto metrics, zero failures, and serial RTF <= 1"
        )
    frontier_ids = _pareto_frontier(eligible, PARETO_METRICS)
    pareto_rows: list[dict[str, object]] = []
    for row in rows:
        pipeline_id = str(row["pipeline_id"])
        dominators = sorted(
            str(other["pipeline_id"])
            for other in eligible
            if other is not row and _dominates(other, row, PARETO_METRICS)
        )
        on_frontier = pipeline_id in frontier_ids
        row["pareto_frontier"] = on_frontier
        row["pareto_eligibility"] = (
            "ELIGIBLE"
            if row in eligible
            else "INELIGIBLE_MISSING_FAILURE_OR_NOT_REALTIME"
        )
        row["overall_recommendation"] = (
            str(row["selected_role"]) if row.get("selected_role") else "NOT_SELECTED"
        )
        row["technical_rank_method"] = "ORDERED_LEXICOGRAPHIC_NO_COMPOSITE"
        row["ux_rank_method"] = "ORDERED_SAFETY_LEXICOGRAPHIC_NO_COMPOSITE"
        row["resource_rank_method"] = "ORDERED_SERIAL_RESOURCES_NO_COMPOSITE"
        pareto_rows.append(
            {
                **scope_fields(),
                "schema_version": "full-pipeline-final-pareto-frontier.v1",
                "pipeline_id": pipeline_id,
                "eligible": row in eligible,
                "on_frontier": on_frontier,
                "dominated_by_pipeline_ids": dominators,
                **{spec.name: row.get(spec.name) for spec in PARETO_METRICS},
                "reliability_failure_count": row.get("reliability_failure_count"),
                "definition": "no eligible pipeline is no-worse on every declared dimension and better on at least one",
                "weighted_composite_score_used": False,
            }
        )

    primary = _required_role(roles, "PRIMARY")
    fallback = roles.get("FALLBACK")
    alternative = roles.get("ALTERNATIVE")
    selected = {value for value in roles.values() if value}
    not_worth = _not_worth(rows, selected)
    for row in rows:
        if row["pipeline_id"] == not_worth[0]:
            row["overall_recommendation"] = "NOT_WORTH_CONTINUING"
    policy = {
        "policy_id": "full_pipeline_constraint_pareto_selection.v1",
        "weighted_score_used": False,
        "technical_and_licensing_rankings_separate": True,
        "authoritative_matrix_priorities": declared_priorities,
        "technical_priority_metric_mapping": [
            {
                "rank": rank,
                "matrix_metric": metric,
                "direction": direction,
                "output_metrics": output_metrics,
            }
            for (rank, metric, direction), output_metrics in zip(
                MATRIX_PRIORITY_CONTRACT,
                (
                    ["wrong_known_time_sec"],
                    ["stranger_false_known_time_sec"],
                    ["premature_wrong_name_exposure_sec"],
                    ["speaker_attributed_wer"],
                    ["correctly_named_known_rate"],
                    ["anonymous_speaker_confusion_rate"],
                    ["first_readable_partial_latency_sec"],
                    ["stable_prefix_latency_sec"],
                    ["stable_correct_name_latency_sec"],
                    ["transcript_identity_revision_count"],
                    ["reliability_failure_count", "total_rtf"],
                    ["mean_cpu_percent", "peak_rss_bytes", "model_bytes"],
                ),
                strict=True,
            )
        ],
        "user_experience_safety_order": [spec.name for spec in UX_METRICS],
        "resource_order": [spec.name for spec in RESOURCE_METRICS],
        "pareto_dimensions": [spec.name for spec in PARETO_METRICS],
        "production_roles_consumed_from_prompt7_without_reselection": True,
        "p5_p6_p7_evidence_kept_separate": True,
    }
    return RankingResult(
        rows=tuple(
            sorted(rows, key=lambda row: int(row["technical_performance_rank"]))
        ),
        pareto_rows=tuple(pareto_rows),
        roles=roles,
        primary=primary,
        fallback=fallback,
        alternative=alternative,
        not_worth_continuing=not_worth[0],
        not_worth_reason=not_worth[1],
        policy=policy,
    )


def _validate_matrix_priority_contract(
    matrix_document: Mapping[str, object],
) -> list[Mapping[str, object]]:
    selection = matrix_document.get("selection_policy")
    if not isinstance(selection, Mapping):
        raise FinalConsolidationError("matrix selection_policy is absent")
    if (
        selection.get("policy_id") != "full_pipeline_constraint_pareto_selection.v1"
        or selection.get("weighted_score_used") is not False
        or selection.get("technical_ranking_separate_from_licensing_provenance_ranking")
        is not True
    ):
        raise FinalConsolidationError("matrix selection policy identity differs")
    priorities = selection.get("priorities")
    if not isinstance(priorities, list):
        raise FinalConsolidationError("matrix selection priorities are absent")
    observed = tuple(
        (
            int(raw.get("rank") or -1),
            str(raw.get("metric") or ""),
            str(raw.get("direction") or ""),
        )
        for raw in priorities
        if isinstance(raw, Mapping)
    )
    if observed != MATRIX_PRIORITY_CONTRACT:
        raise FinalConsolidationError(
            "matrix exact 12-priority selection contract differs"
        )
    return [dict(raw) for raw in priorities if isinstance(raw, Mapping)]


def _core_all18_rows(
    completion: CompletionEvidence, pipeline_ids: Sequence[str]
) -> dict[str, dict[str, object]]:
    names = (
        "all18_finalist_summary.csv",
        "all18_asr.csv",
        "all18_diarization.csv",
        "all18_identity.csv",
        "all18_speaker_attributed_transcript.csv",
        "all18_streaming.csv",
        "all18_resources.csv",
    )
    merged = {str(pipeline_id): {} for pipeline_id in pipeline_ids}
    for name in names:
        rows = read_csv(completion.one(name))
        observed: set[str] = set()
        for row in rows:
            pipeline_id = str(row.get("pipeline_id") or "")
            if pipeline_id not in merged or pipeline_id in observed:
                raise FinalConsolidationError(
                    f"Prompt-5 {name} has duplicate/unknown pipeline {pipeline_id!r}"
                )
            observed.add(pipeline_id)
            for key, value in row.items():
                if value not in (None, "") or key not in merged[pipeline_id]:
                    merged[pipeline_id][key] = value
        if observed != set(merged):
            raise FinalConsolidationError(f"Prompt-5 {name} is not exact all-18")
    for row in merged.values():
        transcript = _first_number(
            row,
            ("transcript_revision_count", "partial_revision_count"),
        )
        identity = _first_number(
            row,
            ("identity_revision_count", "ux_identity_revision_count"),
        )
        if transcript is not None and identity is not None:
            row["transcript_identity_revision_count"] = transcript + identity
            row["transcript_identity_revision_count__status"] = "computed_sum"
    return merged


def _extended_metrics(
    completion: CompletionEvidence, extended_ids: set[str]
) -> dict[str, Mapping[str, object]]:
    wanted = {
        "premature_wrong_name_exposure_sec",
        "wrong_name_dwell_sec",
        "stable_name_latency_sec",
        "identity_revision_count",
        "transcript_revision_count",
        "total_rtf",
        "peak_rss_bytes",
        "model_bytes",
        "model_startup_sec",
        "cache_bytes",
        "cache_bytes_after",
        "warmup_duration_sec",
        "worker_process_count",
        "loaded_model_memory_bytes",
        "failure_count",
        "deadline_miss_count",
        "dropped_frame_count",
    }
    output: dict[str, dict[str, object]] = {
        pipeline_id: {
            "evidence_scope": "P6_PREDECLARED_EXTENDED_SET_ONLY",
            "used_to_reselect_roles_in_prompt8": False,
            "metrics": {},
        }
        for pipeline_id in extended_ids
    }
    for name in (
        "extended_summary.csv",
        "online_identity.csv",
        "ux_latency.csv",
        "label_revision.csv",
        "reliability_results.csv",
        "serial_resources.csv",
    ):
        for row in read_csv(completion.one(name)):
            pipeline_id = str(row.get("pipeline_id") or row.get("preset_id") or "")
            if pipeline_id not in output:
                continue
            metrics = output[pipeline_id]["metrics"]
            assert isinstance(metrics, dict)
            metric_id = str(row.get("metric_id") or "")
            if metric_id in wanted:
                metrics[metric_id] = {
                    "value": row.get("value"),
                    "status": row.get("status")
                    or row.get("metric_status")
                    or "computed",
                    "source": name,
                }
            for metric in wanted:
                if row.get(metric) not in (None, ""):
                    metrics[metric] = {
                        "value": row.get(metric),
                        "status": row.get(f"{metric}__status") or "computed",
                        "source": name,
                    }
    return {key: value for key, value in sorted(output.items())}


def _first_number(row: Mapping[str, object], aliases: Sequence[str]) -> float | None:
    for alias in aliases:
        value = _number(row.get(alias))
        if value is not None:
            return value
    return None


def _roles(
    catalog: Mapping[str, object],
    summary: Sequence[Mapping[str, str]],
    pipeline_ids: Sequence[str],
) -> tuple[dict[str, str | None], dict[str, bool]]:
    roles: dict[str, str | None] = {
        "PRIMARY": None,
        "FALLBACK": None,
        "ALTERNATIVE": None,
    }
    raw_roles = catalog.get("roles")
    if isinstance(raw_roles, Mapping):
        for role in roles:
            value = raw_roles.get(role) or raw_roles.get(role.casefold())
            roles[role] = str(value) if value else None
    candidates = catalog.get("candidates")
    readiness: dict[str, bool] = {}
    if isinstance(candidates, list):
        for raw in candidates:
            if not isinstance(raw, Mapping):
                continue
            pipeline_id = str(raw.get("pipeline_id") or raw.get("technical_id") or "")
            role = str(raw.get("selected_role") or raw.get("role") or "").upper()
            if role in roles and pipeline_id:
                roles[role] = pipeline_id
            if pipeline_id:
                readiness[pipeline_id] = _bool(raw.get("software_ready"))
    for row in summary:
        pipeline_id = str(row.get("pipeline_id") or row.get("technical_id") or "")
        role = str(row.get("selected_role") or row.get("role") or "").upper()
        if role in roles and pipeline_id:
            roles[role] = pipeline_id
        if pipeline_id and "software_ready" in row:
            readiness[pipeline_id] = _bool(row.get("software_ready"))
    selected = [value for value in roles.values() if value]
    if len(selected) != len(set(selected)) or not 1 <= len(selected) <= 3:
        raise FinalConsolidationError(
            "Prompt-7 catalog must select one to three unique roles"
        )
    if not roles.get("PRIMARY"):
        raise FinalConsolidationError("Prompt-7 catalog did not select PRIMARY")
    unknown = set(selected) - set(pipeline_ids)
    if unknown:
        raise FinalConsolidationError(
            "Prompt-7 catalog selects unknown pipelines: " + ", ".join(sorted(unknown))
        )
    for pipeline_id in selected:
        if readiness.get(pipeline_id) is not True:
            raise FinalConsolidationError(
                f"Prompt-7 selected pipeline is not software_ready: {pipeline_id}"
            )
    return roles, readiness


def _required_role(roles: Mapping[str, str | None], role: str) -> str:
    value = roles.get(role)
    if not value:
        raise FinalConsolidationError(f"Prompt-7 catalog did not select {role}")
    return value


def _not_worth(
    rows: Sequence[Mapping[str, object]], selected: set[str]
) -> tuple[str, str]:
    candidates = [row for row in rows if str(row["pipeline_id"]) not in selected]
    if not candidates:
        raise FinalConsolidationError(
            "no non-selected pipeline remains for discontinuation analysis"
        )
    ineligible = [
        row for row in candidates if row.get("pareto_eligibility") != "ELIGIBLE"
    ]
    pool = ineligible or [row for row in candidates if not row.get("pareto_frontier")]
    pool = pool or candidates
    worst = max(
        pool,
        key=lambda row: (
            _number(row.get("reliability_failure_count")) or 0.0,
            _number(row.get("wrong_known_time_sec")) or -math.inf,
            _number(row.get("stranger_false_known_time_sec")) or -math.inf,
            int(row.get("technical_performance_rank") or 0),
            str(row["pipeline_id"]),
        ),
    )
    reason = (
        "non-selected and reliability/Pareto-ineligible under the predeclared constraints"
        if worst.get("pareto_eligibility") != "ELIGIBLE"
        else "non-selected, Pareto-dominated, and worst by the declared safety-first lexicographic order"
    )
    return str(worst["pipeline_id"]), reason


def _apply_rank(
    rows: Sequence[dict[str, object]], specs: Sequence[Metric], field: str
) -> None:
    ordered = sorted(rows, key=lambda row: _rank_key(row, specs))
    for rank, row in enumerate(ordered, start=1):
        row[field] = rank


def _rank_key(row: Mapping[str, object], specs: Sequence[Metric]) -> tuple[object, ...]:
    values: list[object] = []
    for spec in specs:
        value = _number(row.get(spec.name))
        if value is None:
            values.extend((1, math.inf))
        elif spec.direction == "min":
            values.extend((0, value))
        else:
            values.extend((0, -value))
    values.append(str(row["pipeline_id"]))
    return tuple(values)


def _pareto_frontier(
    rows: Sequence[Mapping[str, object]], specs: Sequence[Metric]
) -> set[str]:
    return {
        str(row["pipeline_id"])
        for row in rows
        if not any(_dominates(other, row, specs) for other in rows if other is not row)
    }


def _dominates(
    left: Mapping[str, object], right: Mapping[str, object], specs: Sequence[Metric]
) -> bool:
    no_worse = True
    better = False
    for spec in specs:
        left_value = _number(left.get(spec.name))
        right_value = _number(right.get(spec.name))
        if left_value is None or right_value is None:
            return False
        if spec.direction == "min":
            no_worse &= left_value <= right_value
            better |= left_value < right_value
        else:
            no_worse &= left_value >= right_value
            better |= left_value > right_value
    return no_worse and better


def _metric_value(row: Mapping[str, object], spec: Metric) -> float | None:
    if spec.name == "transcript_identity_revision_count":
        direct = _number(row.get(spec.name))
        if direct is not None:
            return direct
        transcript = _first_number(
            row, ("transcript_revision_count", "partial_revision_count")
        )
        identity = _first_number(
            row, ("identity_revision_count", "ux_identity_revision_count")
        )
        return (
            transcript + identity
            if transcript is not None and identity is not None
            else None
        )
    for alias in spec.aliases:
        value = _number(row.get(alias))
        status = str(row.get(f"{alias}__status") or "computed").casefold()
        if value is not None and status not in {"missing", "unsupported", "undefined"}:
            return value
    return None


def _metric_status(row: Mapping[str, object], spec: Metric) -> str:
    if spec.name == "transcript_identity_revision_count":
        return (
            "computed_sum"
            if _metric_value(row, spec) is not None
            else "missing_or_unsupported"
        )
    for alias in spec.aliases:
        if _number(row.get(alias)) is not None:
            return str(row.get(f"{alias}__status") or "computed")
    return "missing"


def _unique_metrics() -> tuple[Metric, ...]:
    result: list[Metric] = []
    seen: set[str] = set()
    for spec in (
        *TECHNICAL_METRICS,
        *RESOURCE_METRICS,
        *DEPLOYMENT_CONTEXT_METRICS,
    ):
        if spec.name not in seen:
            seen.add(spec.name)
            result.append(spec)
    return tuple(result)


def _rank_map(
    rows: Sequence[Mapping[str, str]], *, allowed_ids: set[str], label: str
) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        pipeline_id = str(row.get("pipeline_id") or row.get("technical_id") or "")
        rank = _number(
            row.get("rank") or row.get("technical_rank") or row.get("licensing_rank")
        )
        if pipeline_id and rank is not None:
            if pipeline_id not in allowed_ids or pipeline_id in result or int(rank) < 1:
                raise FinalConsolidationError(
                    f"{label} has invalid/duplicate row: {pipeline_id}"
                )
            result[pipeline_id] = int(rank)
    if not result:
        raise FinalConsolidationError(f"{label} is empty")
    return result


def _license_component_evidence(
    selection,
    *,
    pipeline_id: str,
    p6_document: Mapping[str, object],
    p7_document: Mapping[str, object],
) -> dict[str, list[str]]:
    components = {
        "asr": selection.asr,
        "diarization": selection.diarization,
        "diarization_embedding": selection.diarization_embedding,
        "identity": selection.identity,
    }
    evidence: dict[str, set[str]] = {name: set() for name in components}
    for name, component in components.items():
        for key, value in component.items():
            if any(
                token in str(key).casefold()
                for token in ("license", "provenance", "terms", "warning")
            ):
                text = str(value).strip()
                if text:
                    evidence[name].add(text)
    for key in ("pipelines", "candidates"):
        rows = p6_document.get(key) if key == "pipelines" else p7_document.get(key)
        if not isinstance(rows, list):
            continue
        for raw in rows:
            if (
                not isinstance(raw, Mapping)
                or str(raw.get("pipeline_id") or raw.get("technical_id") or "")
                != pipeline_id
            ):
                continue
            for field, value in raw.items():
                if any(
                    token in str(field).casefold()
                    for token in ("license", "provenance", "redistribution", "warning")
                ):
                    text = str(value or "").strip()
                    if text:
                        normalized = str(field).casefold()
                        if "diarization_embedding" in normalized:
                            evidence["diarization_embedding"].add(text)
                        elif "diarization" in normalized:
                            evidence["diarization"].add(text)
                        elif "identity" in normalized:
                            evidence["identity"].add(text)
                        elif "asr" in normalized:
                            evidence["asr"].add(text)
                        else:
                            for component_values in evidence.values():
                                component_values.add(text)
    repository = str(p7_document.get("repository_redistribution_status") or "").strip()
    if repository:
        for component_values in evidence.values():
            component_values.add(repository)
    return {
        name: sorted(values) if values else ["MISSING_OR_UNSUPPORTED"]
        for name, values in evidence.items()
    }


def _needs_review(value: str) -> int:
    upper = value.upper()
    return int(
        any(
            token in upper
            for token in (
                "REVIEW",
                "UNRESOLVED",
                "GATED",
                "UNKNOWN",
                "MISSING",
                "UNSUPPORTED",
                "UNAVAILABLE",
                "ABSENT",
                "NOT_DECLARED",
                "DO_NOT",
            )
        )
    )


def _rank_or_worst(value: object) -> float:
    number = _number(value)
    return number if number is not None else math.inf


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"true", "1", "yes", "pass", "ready"}


def _number(value: object) -> float | None:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


__all__ = [
    "DEPLOYMENT_CONTEXT_METRICS",
    "PARETO_METRICS",
    "RESOURCE_METRICS",
    "RankingResult",
    "TECHNICAL_METRICS",
    "UX_METRICS",
    "build_rankings",
]
