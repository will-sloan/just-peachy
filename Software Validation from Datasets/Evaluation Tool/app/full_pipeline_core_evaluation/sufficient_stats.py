"""Case/speaker-level sufficient statistics reconstructed from frozen results.

The Prompt-3 result contract stores lossless events, transcripts, diarization,
and selected references.  This module re-scores each recording without neural
inference so bootstrap intervals can resample speakers rather than treating
clips from one person as independent observations.
"""

from __future__ import annotations

from collections import defaultdict
import gzip
import json
import os
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from app.full_pipeline_evaluation import worker
from app.full_pipeline_evaluation.io import canonical_json_bytes, read_json
from app.full_pipeline_evaluation.scorers import score_asr
from app.full_pipeline_evaluation.store import EvaluationStateStore

from .io import CoreEvaluationError, scope_fields
from .selection import source_bucket


BOOTSTRAP_METRICS = {
    "asr": {
        "wer",
        "cer",
        "output_failure_rate",
    },
    "streaming": {
        "first_nonempty_partial_latency_sec",
        "first_readable_partial_latency_sec",
        "stable_prefix_latency_sec",
        "endpoint_to_final_latency_sec",
        "partial_revision_rate_per_minute",
        "token_churn_rate",
        "word_churn_rate",
        "final_wer",
    },
    "diarization": {
        "der",
        "jer",
        "miss_rate",
        "false_alarm_rate",
        "speaker_confusion_rate",
        "boundary_delay_sec",
    },
    "identity": {
        "correctly_named_known_rate",
        "wrong_known_time_sec",
        "stranger_false_known_time_sec",
        "fpir",
        "fnir",
        "unknown_n_consistency",
        "stable_name_latency_sec",
        "identity_revision_count",
    },
    "speaker_transcription": {
        "cpwer",
        "speaker_attributed_wer",
        "correct_transcribed_attributed_word_rate",
        "word_speaker_label_accuracy",
    },
    "ux": {
        "time_to_first_text_sec",
        "time_to_stable_text_sec",
        "time_to_confirmed_known_name_sec",
        "transcript_revision_count",
        "ux_identity_revision_count",
    },
}


def extract_sufficient_statistics(
    campaign_root: Path,
    *,
    output_path: Path,
) -> dict[str, object]:
    campaign_root = Path(campaign_root).resolve()
    manifest = read_json(campaign_root / "campaign_manifest.json")
    paths = read_json(campaign_root / "campaign_paths.json")
    results_root = Path(str(paths["results_root"])).resolve()
    store = EvaluationStateStore(campaign_root / "campaign.sqlite3")
    states = store.list_jobs()
    rows_written = 0
    case_count = 0
    pipeline_count: set[str] = set()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_name(f".{output_path.name}.tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as stream:
            header = {
                "record_type": "header",
                "schema_version": "full-pipeline-core-sufficient-statistics.v1",
                **scope_fields(),
                "campaign_id": manifest["campaign_id"],
                "bootstrap_unit": "reference_speaker_with_fractional_multi_speaker_case_contribution",
                "predictions_used_for_selection": False,
            }
            stream.write(canonical_json_bytes(header) + b"\n")
            for state in states:
                if state.state != "complete":
                    continue
                root = results_root / state.spec.result_relative_path
                for row in _result_case_statistics(
                    root,
                    pipeline_id=state.spec.pipeline_id,
                    source_key=state.spec.source_key,
                ):
                    stream.write(canonical_json_bytes(row) + b"\n")
                    rows_written += 1
                    pipeline_count.add(state.spec.pipeline_id)
                    if row.get("metric_id") == "wer":
                        case_count += 1
    os.replace(temporary, output_path)
    return {
        "schema_version": "full-pipeline-core-sufficient-statistics-extraction.v1",
        **scope_fields(),
        "status": "PASS",
        "output_path": str(output_path.resolve()),
        "statistic_row_count": rows_written,
        "asr_case_pipeline_observation_count": case_count,
        "pipeline_count": len(pipeline_count),
    }


def read_sufficient_statistics(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise CoreEvaluationError("sufficient-statistics row is not an object")
            if value.get("record_type") != "header":
                rows.append(value)
    return rows


def _result_case_statistics(
    root: Path,
    *,
    pipeline_id: str,
    source_key: str,
) -> Iterable[dict[str, object]]:
    cases = _jsonl(root / "references/cases.jsonl")
    if not cases:
        raise CoreEvaluationError(f"result lacks portable case references: {root}")
    context = worker._load_protocol_context("evaluation", cases)  # noqa: SLF001
    events_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _event_rows(root):
        case = str(row.get("evaluation_case_id") or "")
        if case:
            events_by_case[case].append(row)
    transcript_by_case: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _jsonl(root / "predictions/labelled_transcript.jsonl"):
        case = str(row.get("case_id") or "")
        if case:
            transcript_by_case[case].append(row)
    hypotheses = _rttm_by_case(root / "predictions/diarization.rttm", cases)
    statuses = {
        str(row.get("case_id")): row
        for row in _jsonl(root / "diagnostics/case_status.jsonl")
    }
    for case in cases:
        case_id = worker._case_id(case)  # noqa: SLF001
        science = worker._hydrate_case(case, context)  # noqa: SLF001
        events = events_by_case.get(case_id, [])
        transcript = transcript_by_case.get(case_id, [])
        hypothesis_text = " ".join(
            str(row.get("text") or "") for row in transcript
        ).strip()
        complete = (
            str(statuses.get(case_id, {}).get("status") or "failed") == "complete"
        )
        asr_report = score_asr(
            [
                {
                    "utterance_id": case_id,
                    "reference_text": str(science.get("reference_text") or ""),
                    "hypothesis_text": hypothesis_text
                    if complete and hypothesis_text
                    else None,
                    "output_failed": not complete or not hypothesis_text,
                }
            ]
        )
        case_hypotheses = hypotheses.get(case_id, [])
        identity_intervals = worker._identity_intervals(  # noqa: SLF001
            case, science, case_hypotheses, events
        )
        hypothesis_texts: dict[str, list[str]] = defaultdict(list)
        for span in transcript:
            label = worker._anonymous_speaker_id(span)  # noqa: SLF001
            if label:
                hypothesis_texts[label].append(str(span.get("text") or ""))
        case_scoring = {
            "case_id": case_id,
            "events": events,
            "streaming_references": worker._streaming_reference_map(  # noqa: SLF001
                events, science
            ),
            "reference_segments": [
                dict(row) for row in science.get("diarization_segments", [])
            ],
            "hypothesis_segments": case_hypotheses,
            "uem": science.get("uem"),
            "attribution_intervals": identity_intervals,
            "reference_speaker_texts": dict(science.get("speaker_texts", {})),
            "hypothesis_speaker_texts": {
                key: " ".join(value).strip() for key, value in hypothesis_texts.items()
            },
            "speaker_transcript_supported": bool(
                science.get("speaker_transcript_supported")
            ),
        }
        reports = {
            "asr": asr_report,
            **worker._score_isolated_case_views(  # noqa: SLF001
                [case_scoring], all_cases_complete=complete
            ),
        }
        speakers = _speaker_ids(case, science)
        for category, wanted in BOOTSTRAP_METRICS.items():
            report = reports[category]
            for metric_id in sorted(wanted):
                metric = report.metrics[metric_id]
                value = metric.to_jsonable()
                yield {
                    "record_type": "case_metric",
                    **scope_fields(),
                    "pipeline_id": pipeline_id,
                    "source_key": source_key,
                    "source_bucket": source_bucket(case),
                    "case_id": case_id,
                    "reference_speaker_ids": speakers,
                    "bootstrap_group_count": len(speakers),
                    "category": category,
                    "metric_id": metric_id,
                    "status": value["status"],
                    "value": value["value"],
                    "numerator": value["numerator"],
                    "denominator": value["denominator"],
                    "unit": value["unit"],
                    "higher_is_better": value["higher_is_better"],
                    "reason": value["reason"],
                }


def _speaker_ids(
    case: Mapping[str, object], science: Mapping[str, object]
) -> list[str]:
    values = {
        str(value) for value in case.get("global_speaker_ids", []) if str(value).strip()
    }
    direct = str(case.get("reference_speaker_id") or "")
    if direct:
        values.add(direct)
    if not values:
        values.update(
            str(value)
            for value in dict(science.get("speaker_texts", {}))
            if str(value).strip()
        )
    if not values:
        values.add(f"case::{worker._case_id(case)}")  # noqa: SLF001
    return sorted(values)


def _event_rows(root: Path) -> Iterable[dict[str, object]]:
    gz = root / "events.jsonl.gz"
    plain = root / "events.jsonl"
    if gz.is_file():
        with gzip.open(gz, "rt", encoding="utf-8") as stream:
            yield from _decode_lines(stream, gz)
        return
    if plain.is_file():
        with plain.open("r", encoding="utf-8") as stream:
            yield from _decode_lines(stream, plain)
        return
    raise CoreEvaluationError(f"result lacks event stream: {root}")


def _jsonl(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as stream:
        return list(_decode_lines(stream, path))


def _decode_lines(stream: Iterable[str], path: Path) -> Iterable[dict[str, object]]:
    for line_number, line in enumerate(stream, start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise CoreEvaluationError(f"non-object JSONL row {line_number}: {path}")
        yield value


def _rttm_by_case(
    path: Path, cases: Sequence[Mapping[str, object]]
) -> dict[str, list[dict[str, object]]]:
    portable = {
        worker._portable_id(worker._case_id(case)): worker._case_id(case)  # noqa: SLF001
        for case in cases
    }
    result: dict[str, list[dict[str, object]]] = defaultdict(list)
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 8 or fields[0] != "SPEAKER":
            continue
        case_id = portable.get(fields[1])
        if case_id is None:
            raise CoreEvaluationError(
                f"RTTM recording is not a selected case: {fields[1]}"
            )
        start = float(fields[3])
        duration = float(fields[4])
        result[case_id].append(
            {
                "case_id": case_id,
                "start_sec": start,
                "end_sec": start + duration,
                "speaker_id": fields[7],
            }
        )
    return result
