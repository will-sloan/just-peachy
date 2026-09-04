"""Transparent bounded Prompt-6 metric reconstruction and reports."""

from __future__ import annotations

from collections import defaultdict
import gzip
import json
from pathlib import Path
import re
from typing import Iterable, Mapping, Sequence

from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline_evaluation.io import read_json, sha256_file, write_json_atomic
from app.full_pipeline_evaluation.planning import MATRIX_PATH, RUNTIME_CONFIG_PATH
from app.full_pipeline_evaluation.store import EvaluationStateStore

from . import RELIABILITY_FAULTS, scope_fields
from .controller import layout, validate_terminal
from .deployment import build_extended_deployment_evidence
from .io import ExtendedEvaluationError, storage_preflight, write_csv


REQUIRED_REPORT_FILES = (
    "extended_summary.csv",
    "true_streaming_asr.csv",
    "online_diarization.csv",
    "online_identity.csv",
    "ux_latency.csv",
    "label_revision.csv",
    "native_results.csv",
    "long_session_results.csv",
    "reliability_results.csv",
    "serial_resources.csv",
    "extended_deployment_evidence.json",
    "failure_inventory.csv",
    "licensing_provenance.json",
    "failure_analysis.md",
    "extended_report.md",
    "analysis.json",
)

_ONLINE_PANELS = {
    "online_speaker",
    "integrated",
    "native_ami",
    "native_chime6",
    "noise_rir",
    "speaker_gallery_overlap_stress",
}
_UX_TOKENS = (
    "latency",
    "time_to_",
    "lookahead",
    "boundary_delay",
    "wrong_name_dwell",
    "stall_time",
)
_REVISION_TOKENS = (
    "revision",
    "churn",
    "retroactive",
    "flip",
    "unknown_n_consistency",
)
_ONLINE_DIARIZATION_TOKENS = (
    "boundary",
    "cluster",
    "anonymous",
    "speaker_confusion",
    "short_turn",
    "merge_contamination",
)
_ONLINE_IDENTITY_TOKENS = (
    "identity",
    "known",
    "unknown",
    "name",
    "reacquisition",
)
_SUMMARY_METRICS = {
    "wer",
    "final_wer",
    "cer",
    "der",
    "jer",
    "short_turn_der",
    "correctly_named_known_rate",
    "wrong_known_time_sec",
    "stranger_false_known_time_sec",
    "speaker_attributed_wer",
    "cpwer",
    "correct_transcribed_attributed_word_rate",
    "first_nonempty_partial_latency_sec",
    "first_readable_partial_latency_sec",
    "stable_prefix_latency_sec",
    "endpoint_to_final_latency_sec",
    "time_to_first_anonymous_label_sec",
    "time_to_tentative_known_name_sec",
    "time_to_confirmed_known_name_sec",
    "stable_name_latency_sec",
    "wrong_name_dwell_sec",
    "token_churn_rate",
    "word_churn_rate",
    "identity_revision_count",
    "transcript_revision_count",
    "output_failure_rate",
    "total_rtf",
}


def analyze(*, workspace_root: Path) -> dict[str, object]:
    """Create every requested Prompt-6 table without selecting a winner."""

    paths = layout(workspace_root)
    storage_preflight(paths.root)
    terminal = validate_terminal(workspace_root=paths.root)
    if terminal.get("status") != "PASS":
        raise ExtendedEvaluationError(
            "all bounded Prompt-6 jobs must be explicitly complete/failed before Analyze"
        )
    plan = read_json(paths.plan)
    paths.report.mkdir(parents=True, exist_ok=True)
    records = _job_records(plan)
    store = EvaluationStateStore(paths.database)
    states = store.list_jobs()
    metrics = _metric_rows(paths.results, states, records)
    for row in _extended_event_metric_rows(paths.results, states, records):
        record = records.get(str(row.get("job_id") or ""), {})
        metrics.append(_apply_native_metric_applicability(row, record))

    true_streaming = [
        row
        for row in metrics
        if row["panel_id"] == "true_streaming_asr"
        and row["category"] in {"asr", "streaming", "ux"}
    ]
    online_diarization = [
        row
        for row in metrics
        if row["panel_id"] in _ONLINE_PANELS
        and (
            row["category"] in {"diarization", "speaker_transcription"}
            or any(
                token in str(row["metric_id"]) for token in _ONLINE_DIARIZATION_TOKENS
            )
        )
    ]
    online_identity = [
        row
        for row in metrics
        if row["panel_id"] in _ONLINE_PANELS
        and (
            row["category"] == "identity"
            or any(token in str(row["metric_id"]) for token in _ONLINE_IDENTITY_TOKENS)
        )
    ]
    ux_latency = [
        row
        for row in metrics
        if any(token in str(row["metric_id"]) for token in _UX_TOKENS)
    ]
    label_revision = [
        row
        for row in metrics
        if any(token in str(row["metric_id"]) for token in _REVISION_TOKENS)
    ]
    native_results = [
        row for row in metrics if str(row["panel_id"]).startswith("native_")
    ]
    native_results.extend(_native_support_rows(plan))
    custom = _custom_rows(paths.results, states, records)
    failures = _failure_rows(paths.results, store, records)
    summary = _summary_rows(plan, states, metrics)
    native_audit = _native_applicability_audit(native_results)
    reliability_audit = _reliability_evidence_audit(
        custom["reliability"],
        pipeline_ids=[str(item) for item in plan["pipeline_ids"]],
    )
    long_stream_audit = _long_stream_evidence_audit(
        custom["long_session"],
        pipeline_count=int(plan["pipeline_count"]),
    )
    component_rtf_audit = _component_rtf_evidence_audit(
        custom["serial_resources"],
        expected_count=int(plan["pipeline_count"]),
    )
    evidence_audits = (
        native_audit,
        reliability_audit,
        long_stream_audit,
        component_rtf_audit,
    )

    outputs: dict[str, Sequence[Mapping[str, object]]] = {
        "extended_summary.csv": summary,
        "true_streaming_asr.csv": true_streaming,
        "online_diarization.csv": online_diarization,
        "online_identity.csv": online_identity,
        "ux_latency.csv": ux_latency,
        "label_revision.csv": label_revision,
        "native_results.csv": native_results,
        "long_session_results.csv": custom["long_session"],
        "reliability_results.csv": custom["reliability"],
        "serial_resources.csv": custom["serial_resources"],
        "failure_inventory.csv": failures,
    }
    for filename, rows in outputs.items():
        write_csv(paths.report / filename, rows)

    authorization = read_json(paths.authorization)
    deployment_evidence = build_extended_deployment_evidence(
        plan=plan,
        authorization=authorization,
        serial_resource_rows=custom["serial_resources"],
        serial_resource_path=paths.report / "serial_resources.csv",
    )
    write_json_atomic(paths.deployment_evidence, deployment_evidence)

    provenance = _licensing_provenance(plan)
    write_json_atomic(paths.report / "licensing_provenance.json", provenance)
    (paths.report / "failure_analysis.md").write_text(
        _failure_report(failures), encoding="utf-8"
    )
    (paths.report / "extended_report.md").write_text(
        _extended_report(plan, terminal, failures), encoding="utf-8"
    )
    value = {
        "schema_version": "full-pipeline-extended-analysis.v1",
        **scope_fields(),
        "status": (
            "PASS"
            if all(item.get("status") == "PASS" for item in evidence_audits)
            else "FAIL"
        ),
        "pipeline_count": plan["pipeline_count"],
        "job_count": terminal["job_count"],
        "complete_job_count": terminal["complete_count"],
        "failed_job_count": terminal["failed_count"],
        "metric_row_count": len(metrics),
        "native_support_declaration_count": len(_native_support_rows(plan)),
        "required_report_files": list(REQUIRED_REPORT_FILES),
        "conditional_and_end_to_end_metrics_separate": True,
        "unsupported_native_metrics_retained": True,
        "native_metric_applicability": native_audit,
        "reliability_evidence": reliability_audit,
        "long_stream_evidence": long_stream_audit,
        "component_rtf_evidence": component_rtf_audit,
        "deployment_evidence": {
            "status": "PASS",
            "path": str(paths.deployment_evidence),
            "sha256": sha256_file(paths.deployment_evidence),
            "pipeline_count": deployment_evidence["pipeline_count"],
            "pipeline_membership_changed": False,
            "deployment_evidence_used_as_filter": False,
            "desktop_evidence_relabelled_as_arm": False,
        },
        "weighted_composite_created": False,
        "production_winner_selected": False,
        "prompt5_scientific_outcome_tables_used_for_selection": False,
        "prompt5_deployment_evidence_used_for_reporting": True,
    }
    write_json_atomic(paths.report / "analysis.json", value)
    return value


def _job_records(plan: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    raw = plan.get("jobs")
    if not isinstance(raw, list):
        raise ExtendedEvaluationError("bounded plan job inventory is missing")
    return {
        str(row["job_id"]): row
        for row in raw
        if isinstance(row, Mapping) and row.get("job_id")
    }


def _metric_rows(
    results_root: Path,
    states: Sequence[object],
    records: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for state in states:
        spec = state.spec
        if state.state != "complete":
            continue
        record = records.get(spec.job_id, {})
        panel = str(record.get("panel_id") or spec.source_key)
        root = results_root / spec.job_id
        for view in ("asr", "diarization", "identity", "streaming", "resources"):
            path = root / f"metrics/{view}.json"
            if not path.is_file():
                continue
            for category, metric_id, metric in _flatten_metric_document(
                read_json(path), view
            ):
                row = {
                    **scope_fields(),
                    "panel_id": panel,
                    "pipeline_id": spec.pipeline_id,
                    "job_id": spec.job_id,
                    "category": category,
                    "metric_id": metric_id,
                    "metric_scope": (
                        "end_to_end"
                        if category in {"speaker_transcription", "ux"}
                        else "conditional_component"
                    ),
                    "status": metric.get("status"),
                    "value": metric.get("value"),
                    "numerator": metric.get("numerator"),
                    "denominator": metric.get("denominator"),
                    "unit": metric.get("unit"),
                    "reason": metric.get("reason"),
                    "higher_is_better": metric.get("higher_is_better"),
                    "case_count": spec.case_count,
                    "planned_audio_sec": spec.audio_duration_sec,
                    "details": metric.get("details") or {},
                }
                rows.append(_apply_native_metric_applicability(row, record))
    return rows


def _apply_native_metric_applicability(
    row: Mapping[str, object],
    record: Mapping[str, object],
) -> dict[str, object]:
    """Suppress computed native metrics that lack frozen reference support."""

    value = dict(row)
    panel = str(value.get("panel_id") or "")
    if panel not in {"native_ami", "native_chime6", "native_voices"}:
        return value
    cases = [
        dict(item) for item in record.get("cases", []) if isinstance(item, Mapping)
    ]
    reason = _native_inapplicability_reason(
        panel,
        category=str(value.get("category") or ""),
        metric_id=str(value.get("metric_id") or ""),
        cases=cases,
    )
    if reason is None:
        value["native_metric_applicability"] = "SUPPORTED_BY_FROZEN_REFERENCE_CONTRACT"
        return value
    original = {
        "status": value.get("status"),
        "had_value": value.get("value") is not None,
        "had_sufficient_statistics": value.get("numerator") is not None
        or value.get("denominator") is not None,
    }
    value.update(
        {
            "status": "unsupported",
            "value": None,
            "numerator": None,
            "denominator": None,
            "reason": reason,
            "native_metric_applicability": reason,
            "computed_metric_suppressed": original["status"]
            in {"computed", "supported"}
            or original["had_value"],
            "details": {
                **dict(value.get("details") or {}),
                "suppressed_original": original,
            },
        }
    )
    return value


def _native_inapplicability_reason(
    panel: str,
    *,
    category: str,
    metric_id: str,
    cases: Sequence[Mapping[str, object]],
) -> str | None:
    identity_metric = category == "identity" or any(
        token in metric_id.casefold()
        for token in ("identity", "known", "unknown", "name", "fpir", "fnir")
    )
    speaker_transcription = (
        category == "speaker_transcription"
        or metric_id.casefold()
        in {
            "cpwer",
            "speaker_attributed_wer",
            "correct_transcribed_attributed_word_rate",
        }
    )
    if identity_metric:
        return "unsupported_no_leakage_safe_native_enrollment"
    if panel == "native_chime6":
        if category == "asr" or metric_id.casefold() in {"wer", "cer", "final_wer"}:
            return "unsupported_no_complete_chime6_transcript_reference"
        if speaker_transcription:
            return "unsupported_no_complete_chime6_speaker_transcript_reference"
        if category == "diarization" and not _all_cases_support(
            cases, "diarization", "der_jer_eligible"
        ):
            return "unsupported_incomplete_chime6_diarization_reference"
        return None
    if panel == "native_ami":
        if category == "asr" and not _all_cases_support(cases, "asr", "cpwer_eligible"):
            return "unsupported_incomplete_ami_transcript_reference"
        if speaker_transcription and not _all_cases_support(
            cases, "speaker_attributed_transcript", "cpwer_eligible"
        ):
            return "unsupported_incomplete_ami_cpwer_reference"
        if category == "diarization" and not _all_cases_support(
            cases, "diarization", "der_jer_eligible"
        ):
            return "unsupported_incomplete_ami_diarization_reference"
        return None
    if panel == "native_voices":
        if category in {"diarization", "speaker_transcription"}:
            return "unsupported_voices_acoustic_asr_only"
        if category == "asr" and not all(
            _case_supports(item, "asr")
            and isinstance(item.get("reference_text"), str)
            and bool(str(item.get("reference_text") or "").strip())
            for item in cases
        ):
            return "unsupported_incomplete_voices_asr_reference"
    return None


def _all_cases_support(
    cases: Sequence[Mapping[str, object]],
    view: str,
    eligibility_key: str,
) -> bool:
    return bool(cases) and all(
        _case_supports(item, view) and item.get(eligibility_key) is True
        for item in cases
    )


def _case_supports(case: Mapping[str, object], view: str) -> bool:
    return view in {str(item) for item in case.get("supported_views", [])}


def _flatten_metric_document(
    document: Mapping[str, object], fallback: str
) -> Iterable[tuple[str, str, Mapping[str, object]]]:
    subviews = document.get("subviews")
    if isinstance(subviews, Mapping):
        for category, raw_report in subviews.items():
            if not isinstance(raw_report, Mapping):
                continue
            metrics = raw_report.get("metrics")
            if not isinstance(metrics, Mapping):
                continue
            for metric_id, metric in metrics.items():
                if isinstance(metric, Mapping):
                    yield str(category), str(metric_id), metric
        return
    metrics = document.get("metrics")
    if isinstance(metrics, Mapping):
        for metric_id, metric in metrics.items():
            if isinstance(metric, Mapping):
                yield fallback, str(metric_id), metric


def _extended_event_metric_rows(
    results_root: Path,
    states: Sequence[object],
    records: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    """Derive Prompt-6 online engineering milestones from bound event logs."""

    output: list[dict[str, object]] = []
    eligible_panels = {"true_streaming_asr", "online_speaker", "integrated"}
    for state in states:
        spec = state.spec
        record = records.get(spec.job_id, {})
        panel = str(record.get("panel_id") or spec.source_key)
        if state.state != "complete" or panel not in eligible_panels:
            continue
        event_path = results_root / spec.job_id / "events.jsonl.gz"
        if not event_path.is_file():
            event_path = results_root / spec.job_id / "events.jsonl"
        if not event_path.is_file():
            continue
        by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
        opener = gzip.open if event_path.suffix == ".gz" else open
        with opener(event_path, "rt", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                event = json.loads(line)
                if isinstance(event, dict):
                    by_case[str(event.get("evaluation_case_id") or "unknown")].append(
                        event
                    )
        for case_id, events in sorted(by_case.items()):
            events.sort(key=lambda row: int(row.get("event_sequence") or 0))
            anonymous = [
                row for row in events if row.get("event_type") == "anonymous_speaker"
            ]
            boundaries = [
                row for row in events if row.get("event_type") == "speaker_boundary"
            ]
            identity = [
                row for row in events if row.get("event_type") == "identity_label"
            ]
            speech = [
                row for row in events if row.get("event_type") == "speech_activity"
            ]
            tentative = [
                row for row in identity if row.get("identity_state") == "tentative"
            ]
            confirmed = [
                row for row in identity if row.get("identity_state") == "confirmed"
            ]
            unknown = [
                row for row in identity if row.get("identity_state") == "unknown"
            ]
            lookahead = [
                value
                for row in speech
                if (value := _lookahead_seconds(row)) is not None
            ]
            compute = [
                value
                for row in speech
                if (value := _backend_latency_seconds(row)) is not None
            ]
            event_lag = [
                value
                for row in events
                if (value := _capture_to_emit_seconds(row)) is not None
            ]
            boundary_delay = [
                value
                for row in boundaries
                if (value := _source_to_emit_seconds(row)) is not None
            ]
            cluster_revisions = sum(_revision_number(row) > 0 for row in anonymous)
            reentries = [row for row in anonymous if _revision_detail(row) == "reentry"]
            short_turns = sum(
                any(
                    str(item).startswith("short:")
                    for item in row.get("source_turn_ids", [])
                )
                for row in anonymous
            )
            identity_flips = _identity_flip_count(identity)
            reacquisition = _reacquisition_latencies(reentries, confirmed)
            unknown_labels = {
                str(row.get("unknown_label"))
                for row in anonymous
                if str(row.get("unknown_label") or "").startswith("Unknown_")
            }
            values = (
                (
                    "online_diarization",
                    "segmentation_algorithmic_lookahead_sec",
                    _mean_or_none(lookahead),
                    "seconds",
                    "no structured segmentation lookahead",
                ),
                (
                    "online_diarization",
                    "segmentation_backend_compute_latency_sec",
                    _mean_or_none(compute),
                    "seconds",
                    "no segmentation backend latency",
                ),
                (
                    "online_diarization",
                    "first_anonymous_cluster_event_sec",
                    _first_emitted_seconds(anonymous),
                    "seconds",
                    "no anonymous cluster event",
                ),
                (
                    "online_diarization",
                    "anonymous_cluster_count",
                    float(
                        len({str(row.get("anonymous_speaker_id")) for row in anonymous})
                    ),
                    "count",
                    None,
                ),
                (
                    "online_diarization",
                    "anonymous_cluster_revision_count",
                    float(cluster_revisions),
                    "count",
                    None,
                ),
                (
                    "online_diarization",
                    "speaker_boundary_count",
                    float(len(boundaries)),
                    "count",
                    None,
                ),
                (
                    "online_diarization",
                    "boundary_commitment_delay_sec",
                    _mean_or_none(boundary_delay),
                    "seconds",
                    "no source-clock boundary commits",
                ),
                (
                    "online_diarization",
                    "warm_reentry_count",
                    float(len(reentries)),
                    "count",
                    None,
                ),
                (
                    "online_diarization",
                    "short_turn_inheritance_count",
                    float(short_turns),
                    "count",
                    None,
                ),
                (
                    "online_identity",
                    "first_tentative_name_event_sec",
                    _first_emitted_seconds(tentative),
                    "seconds",
                    "no tentative known-name transition",
                ),
                (
                    "online_identity",
                    "first_confirmed_name_event_sec",
                    _first_emitted_seconds(confirmed),
                    "seconds",
                    "no confirmed known-name transition",
                ),
                (
                    "online_identity",
                    "first_unknown_identity_event_sec",
                    _first_emitted_seconds(unknown),
                    "seconds",
                    "no explicit unknown transition",
                ),
                (
                    "online_identity",
                    "tentative_identity_evidence_duration_sec",
                    _first_number(tentative, "evidence_duration_sec"),
                    "seconds",
                    "no tentative evidence event",
                ),
                (
                    "online_identity",
                    "confirmed_identity_evidence_duration_sec",
                    _first_number(confirmed, "evidence_duration_sec"),
                    "seconds",
                    "no confirmed evidence event",
                ),
                (
                    "online_identity",
                    "identity_flip_count",
                    float(identity_flips),
                    "count",
                    None,
                ),
                (
                    "online_identity",
                    "unknown_label_count",
                    float(len(unknown_labels)),
                    "count",
                    None,
                ),
                (
                    "online_identity",
                    "warm_reacquisition_latency_sec",
                    _mean_or_none(reacquisition),
                    "seconds",
                    "no reentry followed by confirmed name",
                ),
                (
                    "ux",
                    "first_generic_label_event_sec",
                    _first_emitted_seconds(anonymous),
                    "seconds",
                    "no generic speaker label",
                ),
                (
                    "ux",
                    "source_capture_to_event_latency_sec",
                    _mean_or_none(event_lag),
                    "seconds",
                    "capture monotonic timestamps unavailable",
                ),
            )
            for category, metric_id, value, unit, unsupported_reason in values:
                output.append(
                    _event_metric_row(
                        panel_id=panel,
                        pipeline_id=spec.pipeline_id,
                        job_id=spec.job_id,
                        case_id=case_id,
                        category=category,
                        metric_id=metric_id,
                        value=value,
                        unit=unit,
                        unsupported_reason=unsupported_reason,
                    )
                )
    return output


def _event_metric_row(
    *,
    panel_id: str,
    pipeline_id: str,
    job_id: str,
    case_id: str,
    category: str,
    metric_id: str,
    value: float | None,
    unit: str,
    unsupported_reason: str | None,
) -> dict[str, object]:
    return {
        **scope_fields(),
        "panel_id": panel_id,
        "pipeline_id": pipeline_id,
        "job_id": job_id,
        "case_id": case_id,
        "category": category,
        "metric_id": metric_id,
        "metric_scope": "extended_online_engineering",
        "status": "computed" if value is not None else "unsupported",
        "value": value,
        "numerator": None,
        "denominator": None,
        "unit": unit,
        "reason": None if value is not None else unsupported_reason,
        "higher_is_better": None,
        "case_count": 1,
        "details": {
            "source": "checksum_bound_common_runtime_event_log",
            "speech_evidence_algorithmic_lookahead_compute_and_event_time_separate": True,
        },
    }


def _emitted_seconds(row: Mapping[str, object]) -> float | None:
    processing = row.get("processing_timestamps")
    clock = row.get("source_clock")
    if not isinstance(processing, Mapping) or not isinstance(clock, Mapping):
        return None
    emitted = _number(processing.get("emitted_monotonic_ns"))
    epoch = _number(clock.get("monotonic_epoch_ns"))
    if emitted is None or epoch is None:
        return None
    return max(0.0, (emitted - epoch) / 1e9)


def _first_emitted_seconds(rows: Sequence[Mapping[str, object]]) -> float | None:
    values = [value for row in rows if (value := _emitted_seconds(row)) is not None]
    return min(values) if values else None


def _capture_to_emit_seconds(row: Mapping[str, object]) -> float | None:
    processing = row.get("processing_timestamps")
    capture = row.get("capture_timestamps")
    if not isinstance(processing, Mapping) or not isinstance(capture, Mapping):
        return None
    emitted = _number(processing.get("emitted_monotonic_ns"))
    captured = _number(capture.get("capture_end_monotonic_ns"))
    if emitted is None or captured is None or emitted < captured:
        return None
    return (emitted - captured) / 1e9


def _source_to_emit_seconds(row: Mapping[str, object]) -> float | None:
    emitted = _emitted_seconds(row)
    source = _number(row.get("boundary_sec"))
    if source is None:
        capture = row.get("capture_timestamps")
        if isinstance(capture, Mapping):
            source = _number(capture.get("audio_end_sec"))
    if emitted is None or source is None:
        return None
    return max(0.0, emitted - source)


def _lookahead_seconds(row: Mapping[str, object]) -> float | None:
    reason = row.get("event_reason")
    detail = str(reason.get("detail") or "") if isinstance(reason, Mapping) else ""
    match = re.search(r"algorithmic_lookahead_sec=([0-9.]+)", detail)
    return float(match.group(1)) if match else None


def _backend_latency_seconds(row: Mapping[str, object]) -> float | None:
    processing = row.get("processing_timestamps")
    if not isinstance(processing, Mapping):
        return None
    value = _number(processing.get("backend_latency_ms"))
    return value / 1000.0 if value is not None else None


def _revision_number(row: Mapping[str, object]) -> int:
    revision = row.get("revision")
    return (
        int(revision.get("revision_number") or 0)
        if isinstance(revision, Mapping)
        else 0
    )


def _revision_detail(row: Mapping[str, object]) -> str:
    revision = row.get("revision")
    reason = revision.get("reason") if isinstance(revision, Mapping) else None
    return str(reason.get("detail") or "") if isinstance(reason, Mapping) else ""


def _identity_flip_count(rows: Sequence[Mapping[str, object]]) -> int:
    latest: dict[str, str] = {}
    flips = 0
    for row in rows:
        if row.get("identity_state") not in {"tentative", "confirmed"}:
            continue
        label = row.get("speaker_label")
        known = (
            str(label.get("enrolled_speaker_id") or "")
            if isinstance(label, Mapping)
            else ""
        )
        cluster = str(row.get("anonymous_speaker_id") or "")
        if known and cluster in latest and latest[cluster] != known:
            flips += 1
        if known:
            latest[cluster] = known
    return flips


def _reacquisition_latencies(
    reentries: Sequence[Mapping[str, object]],
    confirmed: Sequence[Mapping[str, object]],
) -> list[float]:
    output: list[float] = []
    for reentry in reentries:
        start = _emitted_seconds(reentry)
        cluster = str(reentry.get("anonymous_speaker_id") or "")
        if start is None:
            continue
        later = [
            value
            for row in confirmed
            if str(row.get("anonymous_speaker_id") or "") == cluster
            and (value := _emitted_seconds(row)) is not None
            and value >= start
        ]
        if later:
            output.append(min(later) - start)
    return output


def _first_number(rows: Sequence[Mapping[str, object]], key: str) -> float | None:
    for row in rows:
        value = _number(row.get(key))
        if value is not None:
            return value
    return None


def _mean_or_none(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _native_support_rows(plan: Mapping[str, object]) -> list[dict[str, object]]:
    panels = plan.get("panels")
    if not isinstance(panels, Mapping):
        return []
    output: list[dict[str, object]] = []
    for panel_id in ("native_ami", "native_chime6", "native_voices"):
        raw = panels.get(panel_id)
        if not isinstance(raw, Mapping):
            continue
        support = raw.get("metric_support_contract")
        if not isinstance(support, Mapping):
            continue
        for pipeline in raw.get("pipeline_ids", []):
            for category, status in support.items():
                output.append(
                    {
                        **scope_fields(),
                        "panel_id": panel_id,
                        "pipeline_id": str(pipeline),
                        "job_id": None,
                        "category": str(category),
                        "metric_id": "__metric_support_contract__",
                        "metric_scope": "support_declaration",
                        "status": str(status),
                        "value": None,
                        "reason": str(status),
                    }
                )
    return output


def _custom_rows(
    results_root: Path,
    states: Sequence[object],
    records: Mapping[str, Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    output = {
        "long_session": [],
        "reliability": [],
        "serial_resources": [],
    }
    for state in states:
        spec = state.spec
        record = records.get(spec.job_id, {})
        panel = str(record.get("panel_id") or spec.source_key)
        if panel not in output:
            continue
        row: dict[str, object] = {
            **scope_fields(),
            "panel_id": panel,
            "pipeline_id": spec.pipeline_id,
            "job_id": spec.job_id,
            "job_state": state.state,
            "planned_audio_sec": spec.audio_duration_sec,
            "completed_audio_sec": state.completed_audio_sec,
            "explicit_failure": state.state == "failed",
            "last_error": state.last_error,
        }
        if panel == "reliability":
            row["fault_id"] = record.get("fault_id")
        elif panel == "long_session":
            row["runtime_pace"] = record.get("runtime_pace")
            row["source_provenance"] = record.get("source_provenance")
            row["input_id"] = record.get("long_stream_input_id")
        path = results_root / spec.job_id / "result.json"
        if path.is_file():
            document = read_json(path)
            result = document.get("result")
            row["elapsed_wall_sec"] = document.get("elapsed_wall_sec")
            if isinstance(result, Mapping):
                row.update({str(key): value for key, value in result.items()})
        if panel == "reliability" and row.get("harness_status") not in {
            "PASS",
            "FAIL",
            "UNSUPPORTED",
        }:
            row["harness_status"] = (
                "EXECUTION_FAILED" if state.state == "failed" else "MISSING_EVIDENCE"
            )
        output[panel].append(row)
    return output


def _native_applicability_audit(
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    scientific_rows = [
        row for row in rows if row.get("metric_scope") != "support_declaration"
    ]
    suppressed = [
        row for row in scientific_rows if row.get("computed_metric_suppressed") is True
    ]
    disallowed_remaining = [
        row
        for row in scientific_rows
        if str(row.get("native_metric_applicability") or "").startswith("unsupported_")
        and (
            row.get("value") is not None
            or row.get("numerator") is not None
            or row.get("denominator") is not None
            or str(row.get("status") or "") in {"computed", "supported"}
        )
    ]
    return {
        "status": "PASS" if not disallowed_remaining else "FAIL",
        "native_metric_row_count": len(scientific_rows),
        "suppressed_computed_metric_count": len(suppressed),
        "disallowed_computed_metric_count": len(disallowed_remaining),
        "support_declaration_row_count": len(rows) - len(scientific_rows),
    }


def _reliability_evidence_audit(
    rows: Sequence[Mapping[str, object]],
    *,
    pipeline_ids: Sequence[str],
) -> dict[str, object]:
    expected_pairs = {
        (pipeline_id, fault_id)
        for pipeline_id in pipeline_ids
        for fault_id in RELIABILITY_FAULTS
    }
    expected = len(expected_pairs)
    statuses: dict[str, int] = defaultdict(int)
    pairs: set[tuple[str, str]] = set()
    for row in rows:
        status = str(row.get("harness_status") or "MISSING_EVIDENCE")
        statuses[status] += 1
        pairs.add((str(row.get("pipeline_id")), str(row.get("fault_id"))))
    allowed = {"PASS", "FAIL", "UNSUPPORTED", "EXECUTION_FAILED"}
    explicit = (
        len(rows) == expected and pairs == expected_pairs and set(statuses) <= allowed
    )
    return {
        "status": "PASS" if explicit else "FAIL",
        "expected_fault_result_count": expected,
        "observed_fault_result_count": len(rows),
        "unique_pipeline_fault_count": len(pairs),
        "status_counts": dict(sorted(statuses.items())),
        "unsupported_not_counted_as_pass": True,
        "all_faults_have_explicit_evidence_status": explicit,
    }


def _long_stream_evidence_audit(
    rows: Sequence[Mapping[str, object]],
    *,
    pipeline_count: int,
) -> dict[str, object]:
    expected = pipeline_count * 2
    provenance = defaultdict(set)
    completed_true_realtime = 0
    configured_true_realtime = 0
    for row in rows:
        raw = row.get("source_provenance")
        if isinstance(raw, Mapping):
            provenance[str(row.get("pipeline_id"))].add(
                str(raw.get("provenance_identity_sha256") or "")
            )
        if (
            float(row.get("runtime_pace") or 0.0) == 1.0
            and float(row.get("planned_audio_sec") or 0.0) >= 1800.0
        ):
            configured_true_realtime += 1
        if (
            row.get("job_state") == "complete"
            and float(row.get("runtime_pace") or 0.0) == 1.0
            and float(row.get("input_duration_sec") or 0.0) >= 1800.0
        ):
            completed_true_realtime += 1
    distinct = len(provenance) == pipeline_count and all(
        len(values) == 2 and "" not in values for values in provenance.values()
    )
    return {
        "status": (
            "PASS"
            if len(rows) == expected
            and distinct
            and configured_true_realtime == expected
            else "FAIL"
        ),
        "expected_stream_result_count": expected,
        "observed_stream_result_count": len(rows),
        "pipelines_with_two_distinct_provenances": sum(
            len(values) == 2 and "" not in values for values in provenance.values()
        ),
        "configured_true_1x_30m_stream_count": configured_true_realtime,
        "completed_true_1x_30m_stream_count": completed_true_realtime,
        "failed_streams_retained": sum(
            row.get("job_state") == "failed" for row in rows
        ),
    }


def _component_rtf_evidence_audit(
    rows: Sequence[Mapping[str, object]],
    *,
    expected_count: int,
) -> dict[str, object]:
    false_computed = [
        row
        for row in rows
        if row.get("component_rtf") is not None
        and row.get("component_rtf_measurement_status")
        != "COMPUTED_FROM_MEASURED_PROCESSING_AUDIO_PAIRS"
    ]
    explicit = [
        row
        for row in rows
        if (
            row.get("component_rtf_measurement_status")
            in {
                "COMPUTED_FROM_MEASURED_PROCESSING_AUDIO_PAIRS",
                "UNSUPPORTED_NO_MEASURED_PROCESSING_AUDIO_PAIRS",
            }
            or row.get("job_state") == "failed"
        )
    ]
    return {
        "status": (
            "PASS"
            if not false_computed
            and len(rows) == expected_count
            and len(explicit) == len(rows)
            else "FAIL"
        ),
        "expected_resource_result_count": expected_count,
        "resource_result_count": len(rows),
        "explicit_component_rtf_support_count": len(explicit),
        "false_computed_component_rtf_count": len(false_computed),
    }


def _failure_rows(
    results_root: Path,
    store: EvaluationStateStore,
    records: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    attempts: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in store.attempt_rows():
        attempts[str(row["job_id"])].append(row)
    output: list[dict[str, object]] = []
    for state in store.list_jobs():
        spec = state.spec
        record = records.get(spec.job_id, {})
        result = results_root / spec.job_id
        output.append(
            {
                **scope_fields(),
                "panel_id": record.get("panel_id") or spec.source_key,
                "pipeline_id": spec.pipeline_id,
                "job_id": spec.job_id,
                "engine": record.get("engine"),
                "measurement_class": record.get("measurement_class"),
                "state": state.state,
                "case_count": spec.case_count,
                "completed_cases": state.completed_cases,
                "planned_audio_sec": spec.audio_duration_sec,
                "completed_audio_sec": state.completed_audio_sec,
                "attempt_count": len(attempts.get(spec.job_id, [])),
                "retry_count": state.retry_count,
                "explicit_failure": state.state == "failed",
                "last_error": state.last_error,
                "missing_result": state.state == "complete" and not result.is_dir(),
                "result_root": str(result),
                "result_checksum_sha256": state.result_sha256,
            }
        )
    return output


def _summary_rows(
    plan: Mapping[str, object],
    states: Sequence[object],
    metrics: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    pipeline_ids = [str(item) for item in plan.get("pipeline_ids", [])]
    by_pipeline: dict[str, list[object]] = defaultdict(list)
    for state in states:
        by_pipeline[state.spec.pipeline_id].append(state)
    grouped_metrics: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = (
        defaultdict(list)
    )
    for row in metrics:
        if row.get("metric_id") in _SUMMARY_METRICS:
            grouped_metrics[
                (
                    str(row["pipeline_id"]),
                    str(row["panel_id"]),
                    str(row["category"]),
                    str(row["metric_id"]),
                )
            ].append(row)
    result: list[dict[str, object]] = []
    for pipeline_id in pipeline_ids:
        pipeline_states = by_pipeline[pipeline_id]
        row: dict[str, object] = {
            **scope_fields(),
            "pipeline_id": pipeline_id,
            "extended_set_role": (
                "mandatory_anchor"
                if pipeline_id in set(plan.get("pipeline_ids", [])[:6])
                else "predeclared_development_challenger"
            ),
            "planned_job_count": len(pipeline_states),
            "complete_job_count": sum(
                item.state == "complete" for item in pipeline_states
            ),
            "failed_job_count": sum(item.state == "failed" for item in pipeline_states),
            "completed_audio_sec": sum(
                item.completed_audio_sec for item in pipeline_states
            ),
            "bounded_reduced_evidence": True,
            "weighted_composite_created": False,
            "winner_selected": False,
        }
        for (pipeline, panel, category, metric_id), values in grouped_metrics.items():
            if pipeline != pipeline_id:
                continue
            aggregate = _aggregate_metric(values)
            prefix = f"{panel}__{category}__{metric_id}"
            row[prefix] = aggregate["value"]
            row[f"{prefix}__status"] = aggregate["status"]
            row[f"{prefix}__aggregation"] = aggregate["aggregation"]
        result.append(row)
    return result


def _aggregate_metric(rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    computed = [
        row
        for row in rows
        if row.get("value") is not None
        and str(row.get("status")) in {"computed", "supported"}
    ]
    if not computed:
        return {"value": None, "status": "unsupported", "aggregation": "none"}
    sufficient = [
        row
        for row in computed
        if row.get("numerator") is not None and row.get("denominator") is not None
    ]
    if len(sufficient) == len(computed):
        numerator = sum(float(row["numerator"]) for row in sufficient)
        denominator = sum(float(row["denominator"]) for row in sufficient)
        return {
            "value": numerator / denominator if denominator else None,
            "status": "computed" if denominator else "undefined",
            "aggregation": "micro_sufficient_statistics",
        }
    weights = [float(row.get("case_count") or 1.0) for row in computed]
    denominator = sum(weights)
    return {
        "value": (
            sum(float(row["value"]) * weight for row, weight in zip(computed, weights))
            / denominator
            if denominator
            else None
        ),
        "status": "computed" if denominator else "undefined",
        "aggregation": "case_count_weighted_mean",
    }


def _licensing_provenance(plan: Mapping[str, object]) -> dict[str, object]:
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    source = MATRIX_PATH.parents[2] / "docs/full_pipeline/LICENSE_AND_ASSET_MANIFEST.md"
    pipelines: list[dict[str, object]] = []
    for pipeline_id in plan.get("pipeline_ids", []):
        selected = matrix.resolve(str(pipeline_id))
        pipelines.append(
            {
                "pipeline_id": selected.pipeline_id,
                "asr_alias": selected.asr_alias,
                "diarization_alias": selected.diarization_alias,
                "identity_alias": selected.identity_alias,
                "hybrid_label": selected.hybrid_label,
                "asr_component_id": selected.asr.get("component_id"),
                "asr_license_deployment_status": selected.asr.get(
                    "license_deployment_status"
                ),
                "diarization_embedding_backend_id": selected.diarization.get(
                    "embedding_backend_id"
                ),
                "diarization_embedding_license_deployment_status": (
                    selected.diarization_embedding.get("license_deployment_status")
                ),
                "identity_backend_id": selected.identity.get("backend_id"),
                "identity_license_deployment_status": selected.identity.get(
                    "license_deployment_status"
                ),
                "identity_provenance_warning": selected.identity.get(
                    "provenance_warning"
                ),
                "technical_and_licensing_rankings_separate": True,
            }
        )
    return {
        "schema_version": "full-pipeline-extended-licensing-provenance.v1",
        **scope_fields(),
        "status": "BOUND_EXISTING_DECLARATIONS_NO_NEW_LEGAL_CONCLUSION",
        "source_manifest_path": str(source.resolve()),
        "source_manifest_sha256": sha256_file(source),
        "matrix_path": str(MATRIX_PATH.resolve()),
        "matrix_sha256": sha256_file(MATRIX_PATH),
        "pipelines": pipelines,
    }


def _failure_report(rows: Sequence[Mapping[str, object]]) -> str:
    failed = [row for row in rows if row.get("explicit_failure")]
    missing = [row for row in rows if row.get("missing_result")]
    by_panel: dict[str, int] = defaultdict(int)
    for row in failed:
        by_panel[str(row.get("panel_id"))] += 1
    return f"""# Prompt 6 bounded failure analysis

This inventory retains every terminal job. It does not silently remove failed,
unsupported, or missing evidence.

- Planned terminal jobs: {len(rows)}
- Explicit failures: {len(failed)}
- Complete jobs with missing result trees: {len(missing)}
- Failures by panel: `{json.dumps(dict(sorted(by_panel.items())), sort_keys=True)}`

See `failure_inventory.csv` for job, attempt, error, and checksum fields. Native
metric inapplicability is reported in `native_results.csv`; it is not counted as
an execution failure. No Beaker power or fabricated native known-speaker result
is inferred from desktop telemetry.
"""


def _extended_report(
    plan: Mapping[str, object],
    terminal: Mapping[str, object],
    failures: Sequence[Mapping[str, object]],
) -> str:
    return f"""# Prompt 6 — bounded extended full-pipeline evaluation

## Evidence boundary

- Scope: `{plan["scope_id"]}` / `{plan["scope_class"]}`
- Original full Prompt-6 scope complete: **false**
- Frozen extended pipelines: **{plan["pipeline_count"]}**
- Fixed selection seed: **{plan["selection_seed"]}**
- Terminal jobs: **{terminal["job_count"]}**
- Explicit failed jobs retained: **{sum(bool(row.get("explicit_failure")) for row in failures)}**
- Prompt-5 outcome-dependent pipeline addition: **none**

## Bounded methods

The panel applies the immutable caps recorded in `bounded_plan.json`: 24 native
stateful ASR cases for each ASR representative, 24 online-speaker cases for each
unique frozen hybrid pair, 8 integrated cases per pipeline, fixed AMI/CHiME/VOiCES
native panels, 12 noise/RIR and 12 speaker stress cases per pipeline, two true
incremental 30-minute streams from distinct hash-bound source provenances per
pipeline, all 13 reliability fault records, and one
serial cold + 60-second warmup + 300-second resource run per pipeline.

Accuracy scheduling is capped at two jobs. Resource measurements are serial.
Conditional component and end-to-end metrics remain separate. CHiME WER,
leakage-unsafe native identity, VOiCES diarization/identity, energy, and Beaker
power are explicitly unsupported rather than fabricated.

Reliability evidence uses only PASS, FAIL, UNSUPPORTED, or explicit execution
failure states. A fault that could not be injected is never counted as PASS.
Component RTF is emitted only from measured component processing/audio-duration
pairs; otherwise its numeric field is empty and support is explicit. The
30-hour value is a planning target, not an elapsed-time termination switch.

This bounded stage creates no production winner or unexplained composite score.
`extended_deployment_evidence.json` preserves the Prompt-4-predeclared set,
binds Prompt-5 deployment evidence and the serial desktop resource report, and
records four 2-GiB and four Linux ARM64 portability classes without filtering.
Windows/x86-64 evidence is never relabelled as Raspberry Pi/ARM evidence or a
final target-hardware rank. Selection and hardening happen under later frozen
rules.
"""


__all__ = ["REQUIRED_REPORT_FILES", "analyze"]
