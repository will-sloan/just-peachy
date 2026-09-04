"""Create the compact, checksum-bound H2 timeboxed analysis package."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import unicodedata
import zipfile
from typing import Any, Iterable


PRIMARY_JOBS = (
    "h2p7_h2_known_only_heldout_b5b5707476",
    "h2p7_h2_session_memory_enhanced_heldout_850ae96d34",
)
DEVELOPMENT_FALLBACK_JOBS = (
    "h2p5_h2_known_only_development_6c846e3824",
    "h2p5_h2_session_memory_enhanced_development_a6462711fc",
)
CRITICAL = (
    "wer", "cer", "punctuation_insensitive_wer",
    "der", "jer", "miss_rate", "false_alarm_rate", "confusion_rate",
    "short_turn_der_lt_0_5_sec", "short_turn_der_0_5_to_1_0_sec",
    "short_turn_der_1_0_to_2_0_sec", "correctly_named_known_time_sec",
    "wrong_known_time_sec", "stranger_false_known_time_sec", "fpir", "fnir",
    "unknown_n_consistency", "warm_identity_accuracy", "cold_identity_accuracy",
    "wrong_name_dwell_sec", "speaker_attributed_wer", "cpwer",
    "correct_transcribed_attributed_word_rate", "first_nonempty_partial_latency_sec",
    "first_readable_partial_latency_sec", "stable_prefix_latency_sec",
    "endpoint_to_final_latency_sec", "time_to_first_text_sec", "time_to_stable_text_sec",
    "time_to_tentative_known_name_sec", "time_to_confirmed_known_name_sec",
    "stable_name_latency_sec", "transcript_revision_count", "token_churn_rate",
    "word_churn_rate", "identity_revision_count", "ux_identity_revision_count",
    "total_rtf", "peak_rss_bytes", "process_cpu_mean_percent", "process_cpu_p95_percent",
    "output_failure_rate", "failure_count", "dropped_audio_sec", "stall_time_sec",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} is not a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                row = json.loads(line)
                if isinstance(row, dict):
                    yield row


def normalize_words(text: str) -> list[str]:
    value = unicodedata.normalize("NFKC", text).casefold()
    value = "".join(" " if unicodedata.category(char).startswith("P") else char for char in value)
    return re.sub(r"\s+", " ", value).strip().split()


def edit_distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row_index, ref in enumerate(reference, start=1):
        current = [row_index]
        for column, hyp in enumerate(hypothesis, start=1):
            current.append(min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (ref != hyp)))
        previous = current
    return previous[-1]


def punctuation_insensitive_wer(tool_root: Path, result: Path, split: str) -> tuple[float | None, int, int]:
    case_file = result / "references/cases.jsonl"
    prediction_file = result / "predictions/transcript.jsonl"
    reference_file = tool_root / f"benchmarks/full_pipeline/full_speech_pipeline_v1/{split}/references/speaker_attributed_transcript.jsonl"
    if not all(path.is_file() for path in (case_file, prediction_file, reference_file)):
        return None, 0, 0
    case_map = {row["protocol_case_id"]: (row["source_key"], row["source_case_id"]) for row in iter_jsonl(case_file)}
    references: dict[tuple[str, str], list[str]] = {}
    for row in iter_jsonl(reference_file):
        key = (str(row.get("source_key")), str(row.get("source_case_id")))
        segments = sorted(row.get("segments") or [], key=lambda item: (item.get("start_sec", 0), item.get("end_sec", 0)))
        references[key] = normalize_words(" ".join(str(item.get("scorable_transcript") or "") for item in segments))
    hypotheses: dict[str, list[tuple[float, str]]] = {}
    for row in iter_jsonl(prediction_file):
        if row.get("state") != "final":
            continue
        hypotheses.setdefault(str(row.get("case_id")), []).append((float(row.get("start_sec") or 0), str(row.get("text") or "")))
    errors = words = 0
    for case_id, source in case_map.items():
        reference = references.get(source)
        if reference is None:
            continue
        hypothesis = normalize_words(" ".join(text for _, text in sorted(hypotheses.get(case_id, []))))
        errors += edit_distance(reference, hypothesis)
        words += len(reference)
    return (errors / words if words else None), errors, words


def flatten_metrics(job_id: str, manifest_row: dict[str, Any], result: Path) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    metrics_root = result / "metrics"
    if not metrics_root.is_dir():
        return output
    for metric_file in sorted(metrics_root.glob("*.json")):
        if metric_file.name == "summary.json":
            continue
        payload = read_json(metric_file)
        for subview_id, subview in (payload.get("subviews") or {}).items():
            for metric_id, metric in (subview.get("metrics") or {}).items():
                output.append({
                    "job_id": job_id,
                    "configuration_id": manifest_row.get("configuration_id"),
                    "mode": manifest_row.get("mode"),
                    "split": manifest_row.get("split"),
                    "category": metric.get("category") or subview_id,
                    "subview": subview_id,
                    "metric_id": metric_id,
                    "display_name": metric.get("display_name"),
                    "value": metric.get("value"),
                    "unit": metric.get("unit"),
                    "status": metric.get("status"),
                    "higher_is_better": metric.get("higher_is_better"),
                    "numerator": metric.get("numerator"),
                    "denominator": metric.get("denominator"),
                    "definition": metric.get("definition"),
                    "reason": metric.get("reason"),
                })
    pi_wer, errors, words = punctuation_insensitive_wer(Path(manifest_row["tool_root"]), result, str(manifest_row.get("split")))
    if pi_wer is not None:
        output.append({
            "job_id": job_id, "configuration_id": manifest_row.get("configuration_id"),
            "mode": manifest_row.get("mode"), "split": manifest_row.get("split"),
            "category": "asr", "subview": "asr", "metric_id": "punctuation_insensitive_wer",
            "display_name": "Punctuation-insensitive word error rate", "value": pi_wer,
            "unit": "ratio", "status": "computed", "higher_is_better": False,
            "numerator": errors, "denominator": words,
            "definition": "Word Levenshtein errors after Unicode NFKC, case-folding, punctuation removal, and whitespace collapse.",
            "reason": None,
        })
    return output


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def metric_map(rows: list[dict[str, Any]], job_id: str) -> dict[str, Any]:
    return {row["metric_id"]: row.get("value") for row in rows if row["job_id"] == job_id and row.get("status") == "computed"}


def combined_mode_metric_map(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    """Combine held-out accuracy with serial-resource evidence for one mode."""

    resource_ids = {
        "total_rtf", "peak_rss_bytes", "process_cpu_mean_percent",
        "process_cpu_p95_percent", "model_startup_sec", "model_bytes",
        "dropped_audio_sec", "stall_time_sec", "maximum_queue_depth",
    }
    output: dict[str, Any] = {}
    for row in rows:
        if row.get("mode") != mode or row.get("status") != "computed":
            continue
        metric_id = str(row["metric_id"])
        config = str(row.get("configuration_id") or "")
        if metric_id in resource_ids:
            if "SERIAL_RESOURCE" in config:
                output[metric_id] = row.get("value")
        elif row.get("split") == "evaluation":
            output[metric_id] = row.get("value")
        elif metric_id not in output:
            output[metric_id] = row.get("value")
    return output


def number(value: Any, digits: int = 4) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return "not measured"


def choose_roles(state: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[str, str, str]:
    candidates = [job for job in PRIMARY_JOBS if state["jobs"][job].get("state") == "COMPLETE"]
    evidence = "held-out"
    if len(candidates) < 2:
        candidates = [job for job in DEVELOPMENT_FALLBACK_JOBS if state["jobs"][job].get("state") == "COMPLETE"]
        evidence = "development-only preliminary"
    if not candidates:
        return "not selected", "not selected", "insufficient completed comparison"
    def rank(job: str) -> tuple[float, float, float, float]:
        metrics = metric_map(rows, job)
        def risk(metric_id: str) -> float:
            value = metrics.get(metric_id)
            return float(value) if isinstance(value, (int, float)) else float("inf")
        utility = metrics.get("correct_transcribed_attributed_word_rate")
        return (
            risk("stranger_false_known_time_sec"),
            risk("wrong_known_time_sec"),
            risk("wrong_name_dwell_sec"),
            -float(utility) if isinstance(utility, (int, float)) else float("inf"),
        )
    ordered = sorted(candidates, key=rank)
    return ordered[0], (ordered[1] if len(ordered) > 1 else "not selected"), evidence


def deterministic_zip(source: Path, target: Path) -> None:
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path == target:
                continue
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), date_time=(2026, 9, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())


def generate_critical_bootstrap(
    state: dict[str, Any],
    manifest_by_id: dict[str, dict[str, Any]],
    summary_root: Path,
) -> int:
    """Bootstrap speakers for only the two predeclared retained held-out modes."""

    if not all(state["jobs"][job_id].get("state") == "COMPLETE" for job_id in PRIMARY_JOBS):
        return 0
    from app.h2_product_program import science as h2_science
    from app.h2_product_program.contracts import H2Job

    per_case: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    for job_id in PRIMARY_JOBS:
        definition = manifest_by_id[job_id]
        job = H2Job.from_jsonable(definition)
        result = Path(str(state["jobs"][job_id]["result_path"])).resolve()
        per_case_path = result / "diagnostics/per_case_metrics.jsonl"
        if not per_case_path.is_file():
            raise RuntimeError(f"retained held-out result lacks per-case metrics: {job_id}")
        sources.append({
            "job_id": job_id,
            "pipeline_id": job.pipeline_id,
            "mode": job.mode,
            "result_root": str(result),
            "result_sha256": state["jobs"][job_id].get("result_sha256"),
        })
        for raw in iter_jsonl(per_case_path):
            per_case.extend(h2_science._flatten_per_case_metrics(job, raw))
    intervals = list(h2_science.hierarchical_speaker_case_bootstrap(
        per_case,
        repetitions=2000,
        seed=3800,
    ))
    if not intervals:
        raise RuntimeError("critical retained-mode speaker bootstrap produced no intervals")
    interval_columns = sorted({key for row in intervals for key in row})
    source_columns = sorted({key for row in sources for key in row})
    write_csv(summary_root / "BOOTSTRAP_INTERVALS.csv", intervals, interval_columns)
    shutil.copy2(summary_root / "BOOTSTRAP_INTERVALS.csv", summary_root / "bootstrap_intervals.csv")
    write_csv(summary_root / "BOOTSTRAP_SOURCE_RESULTS.csv", sources, source_columns)
    return len(intervals)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--deadline-utc", required=True)
    args = parser.parse_args()
    tool_root, workspace = Path(args.tool_root).resolve(), Path(args.workspace).resolve()
    results_root, summary_root = Path(args.results_root).resolve(), Path(args.summary_root).resolve()
    summary_root.mkdir(parents=True, exist_ok=True)
    state = read_json(workspace / "program_state.json")
    manifest = read_json(workspace / "job_manifest.json")
    manifest_by_id = {row["job_id"]: {**row, "tool_root": str(tool_root)} for row in manifest["jobs"]}

    inventory: list[dict[str, Any]] = []
    all_metrics: list[dict[str, Any]] = []
    for job_id, job_state in state["jobs"].items():
        definition = manifest_by_id[job_id]
        result_raw = job_state.get("result_path")
        result = Path(result_raw).resolve() if result_raw else None
        result_exists = bool(result and result.exists())
        checksum_valid: bool | None = None
        if job_state.get("state") == "COMPLETE" and result_exists and job_state.get("result_sha256"):
            if result.is_file():
                checksum_valid = sha256_file(result) == str(job_state["result_sha256"])
            elif (result / "checksums.json").is_file():
                checksum_valid = sha256_file(result / "checksums.json") == str(job_state["result_sha256"])
        inventory.append({
            "job_id": job_id, "phase_index": definition.get("phase_index"), "phase_name": definition.get("phase_name"),
            "configuration_id": definition.get("configuration_id"), "mode": definition.get("mode"),
            "split": definition.get("split"), "job_kind": definition.get("job_kind"),
            "state": job_state.get("state"), "completed_cases": job_state.get("completed_cases"),
            "completed_audio_sec": job_state.get("completed_audio_sec"), "result_path": result_raw,
            "result_sha256": job_state.get("result_sha256"), "checksum_valid": checksum_valid,
            "last_error": job_state.get("last_error"),
        })
        if job_state.get("state") == "COMPLETE" and result and result.is_dir():
            all_metrics.extend(flatten_metrics(job_id, definition, result))

    metric_columns = ["job_id", "configuration_id", "mode", "split", "category", "subview", "metric_id", "display_name", "value", "unit", "status", "higher_is_better", "numerator", "denominator", "definition", "reason"]
    write_csv(summary_root / "TIMEBOXED_ALL_METRICS.csv", all_metrics, metric_columns)
    write_csv(summary_root / "TIMEBOXED_JOB_INVENTORY.csv", inventory, list(inventory[0]))

    critical_rows: list[dict[str, Any]] = []
    for job_id in (*DEVELOPMENT_FALLBACK_JOBS, *PRIMARY_JOBS):
        if job_id not in state["jobs"]:
            continue
        row = {"job_id": job_id, "configuration_id": manifest_by_id[job_id]["configuration_id"], "mode": manifest_by_id[job_id]["mode"], "split": manifest_by_id[job_id]["split"], "state": state["jobs"][job_id]["state"]}
        values = metric_map(all_metrics, job_id)
        row.update({metric: values.get(metric) for metric in CRITICAL})
        critical_rows.append(row)
    write_csv(summary_root / "TIMEBOXED_CRITICAL_METRICS.csv", critical_rows, ["job_id", "configuration_id", "mode", "split", "state", *CRITICAL])

    bootstrap_interval_count = generate_critical_bootstrap(
        state, manifest_by_id, summary_root
    )

    primary_id, fallback_id, evidence_level = choose_roles(state, all_metrics)
    primary_name = manifest_by_id.get(primary_id, {}).get("mode", primary_id)
    fallback_name = manifest_by_id.get(fallback_id, {}).get("mode", fallback_id)
    p = combined_mode_metric_map(all_metrics, str(primary_name))
    f = combined_mode_metric_map(all_metrics, str(fallback_name))
    complete = sum(row["state"] == "COMPLETE" for row in inventory)
    superseded = sum(row["state"] == "SUPERSEDED" for row in inventory)
    failed = [row for row in inventory if row["state"] in {"FAILED", "BLOCKED", "STOPPED", "RUNNING"}]

    heldout_core_complete = all(state["jobs"][job].get("state") == "COMPLETE" for job in PRIMARY_JOBS)
    package_status = (
        "COMPLETE_H2_TIMEBOXED_PRODUCT_PIPELINE_PROGRAM"
        if heldout_core_complete
        else "PARTIAL_H2_TIMEBOXED_RESULTS"
    )
    report = f"""# H2 Timeboxed Product-Pipeline Final Report

Generated: {utc_now()}  
Hard deadline: {args.deadline_utc}  
Scientific status: `{package_status}`

## Decision

- Primary: **{primary_name}** (`{primary_id}`)
- Fallback: **{fallback_name}** (`{fallback_id}`)
- Basis: {evidence_level}; lexicographic safety ranking—stranger false-known time, wrong-known time, wrong-name dwell, then correctly transcribed-and-attributed word rate. No opaque composite score was used.
- Alternative: none. The anonymous-only third mode was deliberately deferred to protect the deadline and the two directly usable product modes.

## Primary result snapshot

| Measure | Primary | Fallback | Direction |
|---|---:|---:|---|
| Word error rate | {number(p.get('wer'))} | {number(f.get('wer'))} | lower |
| Punctuation-insensitive WER | {number(p.get('punctuation_insensitive_wer'))} | {number(f.get('punctuation_insensitive_wer'))} | lower |
| Diarization error rate | {number(p.get('der'))} | {number(f.get('der'))} | lower |
| Stranger false-known seconds | {number(p.get('stranger_false_known_time_sec'))} | {number(f.get('stranger_false_known_time_sec'))} | lower |
| Wrong-known seconds | {number(p.get('wrong_known_time_sec'))} | {number(f.get('wrong_known_time_sec'))} | lower |
| Unknown label consistency | {number(p.get('unknown_n_consistency'))} | {number(f.get('unknown_n_consistency'))} | higher |
| Correctly transcribed + attributed word rate | {number(p.get('correct_transcribed_attributed_word_rate'))} | {number(f.get('correct_transcribed_attributed_word_rate'))} | higher |
| Stable-name latency (s) | {number(p.get('stable_name_latency_sec'))} | {number(f.get('stable_name_latency_sec'))} | lower |
| Total RTF | {number(p.get('total_rtf'))} | {number(f.get('total_rtf'))} | lower; <1 is real time |
| Peak RSS memory (bytes) | {number(p.get('peak_rss_bytes'), 0)} | {number(f.get('peak_rss_bytes'), 0)} | lower |

## Interpretation

WER and punctuation-insensitive WER measure transcription only; they must not be confused with speaker-attributed WER. DER/JER measure anonymous speaker segmentation and clustering. Wrong-known and stranger false-known duration are the main naming-safety measures. Correctly transcribed-and-attributed word rate is the strict end-to-end product measure and will normally be materially lower than component-only ASR accuracy because every upstream timing, clustering, identity, and alignment error can invalidate a word.

RTF below 1.0 means processing faster than audio duration on this Windows/x86-64 host. It does **not** predict Raspberry Pi or Arduino performance; ARM64 hardware measurement remains required. Cached/replay accuracy jobs are excluded from real-time claims. Unsupported metrics are never treated as zero.

## Evidence accounting

- Completed manifest jobs: {complete}
- Explicitly superseded/deferred jobs: {superseded}
- Non-success states retained in inventory: {len(failed)}
- Every metric, including unsupported/undefined status and its reason, is in `TIMEBOXED_ALL_METRICS.csv`.
- Every manifest job, including deferrals and failures, is in `TIMEBOXED_JOB_INVENTORY.csv`.
- Speaker-cluster bootstrap intervals: {bootstrap_interval_count}; generated only from the two retained, identically scoped held-out modes using the predeclared 2,000-repetition seed-3800 analysis plan.
- Development-host timing from `h2p2_h2_post_promotion_integration_66f22e24ab` is contaminated context and is not used for final resource conclusions; its signed disclosure is included.

## Scope and scientific validity

The amendment was written before held-out evaluation opened. Frozen model, segmentation, clustering, enrollment, identity, buffering, transcript, and label policies were not retuned. Completed results were not rewritten. The two retained held-out modes use the same evaluation cases. Speaker-level bootstrap is retained when it completed before the cutoff.

See `METRIC_GUIDE.md` for definitions, `LIMITATIONS_AND_DEFERRED_WORK.md` for what was omitted, and `REPRODUCIBILITY_MANIFEST.json` for hashes and paths.
"""
    (summary_root / "FINAL_TIMEBOXED_REPORT.md").write_text(report, encoding="utf-8")

    role_entries = [
        (primary_id, str(primary_name), "PRIMARY", p),
        (fallback_id, str(fallback_name), "FALLBACK", f),
    ]
    role_entries = [entry for entry in role_entries if entry[0] in manifest_by_id]
    ranking_rows: list[dict[str, Any]] = []
    category_orders = {
        "USER_EXPERIENCE_SAFETY": sorted(
            role_entries,
            key=lambda entry: (
                float(entry[3].get("stranger_false_known_time_sec", float("inf"))),
                float(entry[3].get("wrong_known_time_sec", float("inf"))),
                float(entry[3].get("wrong_name_dwell_sec", float("inf"))),
            ),
        ),
        "TECHNICAL_PERFORMANCE": sorted(
            role_entries,
            key=lambda entry: (
                float(entry[3].get("wer", float("inf"))),
                float(entry[3].get("der", float("inf"))),
                -float(entry[3].get("correct_transcribed_attributed_word_rate", float("-inf"))),
            ),
        ),
        "RESOURCE_EFFICIENCY": sorted(
            role_entries,
            key=lambda entry: (
                float(entry[3].get("total_rtf", float("inf"))),
                float(entry[3].get("peak_rss_bytes", float("inf"))),
            ),
        ),
        "DEPLOYMENT_LICENSING_READINESS": role_entries,
        "OVERALL_RECOMMENDATION": role_entries,
    }
    bases = {
        "USER_EXPERIENCE_SAFETY": "stranger false-known, wrong-known, then wrong-name dwell; ascending",
        "TECHNICAL_PERFORMANCE": "WER, DER, then correctly transcribed-and-attributed word rate; lexicographic",
        "RESOURCE_EFFICIENCY": "serial total RTF then peak RSS; ascending",
        "DEPLOYMENT_LICENSING_READINESS": "same AG-H2 model stack; no mode-specific licensing distinction",
        "OVERALL_RECOMMENDATION": "predeclared safety-first ordering; no composite score",
    }
    for category, ordered in category_orders.items():
        for rank, (job_id, mode, role, values) in enumerate(ordered, start=1):
            ranking_rows.append({
                "ranking_category": category, "rank": rank, "role": role,
                "pipeline_id": manifest_by_id[job_id].get("pipeline_id"), "mode": mode,
                "evidence_level": evidence_level, "basis": bases[category],
                "wer": values.get("wer"), "der": values.get("der"),
                "stranger_false_known_time_sec": values.get("stranger_false_known_time_sec"),
                "wrong_known_time_sec": values.get("wrong_known_time_sec"),
                "correct_transcribed_attributed_word_rate": values.get("correct_transcribed_attributed_word_rate"),
                "total_rtf": values.get("total_rtf"), "peak_rss_bytes": values.get("peak_rss_bytes"),
            })
    ranking_columns = [
        "ranking_category", "rank", "role", "pipeline_id", "mode", "evidence_level", "basis",
        "wer", "der", "stranger_false_known_time_sec", "wrong_known_time_sec",
        "correct_transcribed_attributed_word_rate", "total_rtf", "peak_rss_bytes",
    ]
    write_csv(summary_root / "FINAL_PIPELINE_RANKING.csv", ranking_rows, ranking_columns)

    dimensions = [
        ("stranger_false_known_time_sec", "min"), ("wrong_known_time_sec", "min"),
        ("der", "min"), ("correct_transcribed_attributed_word_rate", "max"),
    ]
    if all(isinstance(entry[3].get("total_rtf"), (int, float)) for entry in role_entries):
        dimensions.append(("total_rtf", "min"))
    assessable = [
        entry for entry in role_entries
        if all(isinstance(entry[3].get(metric), (int, float)) for metric, _direction in dimensions)
    ]
    frontier: set[str] = set()
    for candidate in assessable:
        dominated = False
        for other in assessable:
            if other[0] == candidate[0]:
                continue
            weak = all(
                other[3][metric] <= candidate[3][metric] if direction == "min"
                else other[3][metric] >= candidate[3][metric]
                for metric, direction in dimensions
            )
            strict = any(
                other[3][metric] < candidate[3][metric] if direction == "min"
                else other[3][metric] > candidate[3][metric]
                for metric, direction in dimensions
            )
            if weak and strict:
                dominated = True
                break
        if not dominated:
            frontier.add(candidate[0])
    pareto_rows = []
    for job_id, mode, role, values in role_entries:
        pareto_rows.append({
            "job_id": job_id, "pipeline_id": manifest_by_id[job_id].get("pipeline_id"),
            "mode": mode, "role": role,
            "assessment": "PARETO_FRONTIER" if job_id in frontier else "DOMINATED" if job_id in {entry[0] for entry in assessable} else "NOT_ASSESSABLE_MISSING_METRIC",
            "dimensions": ";".join(f"{metric}:{direction}" for metric, direction in dimensions),
            **{metric: values.get(metric) for metric, _direction in dimensions},
        })
    pareto_columns = ["job_id", "pipeline_id", "mode", "role", "assessment", "dimensions", *[metric for metric, _direction in dimensions]]
    write_csv(summary_root / "PIPELINE_PARETO_FRONTIER.csv", pareto_rows, pareto_columns)

    failure_analysis = f"""# Pipeline Failure Analysis

Evidence level: **{evidence_level}**. Primary mode: **{primary_name}**. Unsupported metrics are not interpreted as zero.

## Component observations for the primary

- ASR: WER {number(p.get('wer'))}; punctuation-insensitive WER {number(p.get('punctuation_insensitive_wer'))}; CER {number(p.get('cer'))}. ASR substitutions/deletions/insertions propagate directly into WER and also cap speaker-attributed accuracy.
- Endpointing/streaming: stable-prefix latency {number(p.get('stable_prefix_latency_sec'))} s; endpoint-to-final latency {number(p.get('endpoint_to_final_latency_sec'))} s; transcript revisions {number(p.get('transcript_revision_count'))}. Late or unstable text increases UI delay and transcript churn.
- Segmentation/clustering: DER {number(p.get('der'))}; JER {number(p.get('jer'))}; miss rate {number(p.get('miss_rate'))}; false-alarm rate {number(p.get('false_alarm_rate'))}. These errors create missing, merged, or fragmented speaker evidence before identity scoring.
- Identity/open set: wrong-known time {number(p.get('wrong_known_time_sec'))} s; stranger false-known time {number(p.get('stranger_false_known_time_sec'))} s; FPIR {number(p.get('fpir'))}; FNIR {number(p.get('fnir'))}; Unknown consistency {number(p.get('unknown_n_consistency'))}. False-known errors are the principal safety failure.
- Transcript attribution/alignment: speaker-attributed WER {number(p.get('speaker_attributed_wer'))}; cpWER {number(p.get('cpwer'))}; correctly transcribed-and-attributed word rate {number(p.get('correct_transcribed_attributed_word_rate'))}. The gap from plain WER measures accumulated segmentation, identity, and alignment loss.
- Resources: serial total RTF {number(p.get('total_rtf'))}; peak RSS {number(p.get('peak_rss_bytes'), 0)} bytes. Only serial measurements are used for deployment estimates.

## Propagation map

ASR and endpoint errors affect WER and word timing. Segmentation errors affect DER and the speech supplied to clustering/identity. Cluster fragmentation and merging affect speaker labels, warm re-entry, and Unknown consistency. Identity/open-set errors cause false-known, wrong-known, or delayed names. Transcript alignment converts upstream timestamp and label errors into speaker-attributed WER and label revisions. Queue/resource saturation increases latency, stalls, and dropped audio.

See `TIMEBOXED_ALL_METRICS.csv` for exact definitions and `TIMEBOXED_JOB_INVENTORY.csv` for every failure or deferral.
"""
    (summary_root / "PIPELINE_FAILURE_ANALYSIS.md").write_text(failure_analysis, encoding="utf-8")

    tuning_flags: list[str] = []
    if isinstance(p.get("punctuation_insensitive_wer"), (int, float)) and p["punctuation_insensitive_wer"] > 0.15:
        tuning_flags.append("ASR_TARGET_ADAPTATION_CANDIDATE — only after error-stratum review and real-device audio collection.")
    if any(isinstance(p.get(metric), (int, float)) and p[metric] > 0 for metric in ("stranger_false_known_time_sec", "wrong_known_time_sec")):
        tuning_flags.append("POLICY_CHANGE_ONLY — investigate calibration/memory behavior on development data before considering embedding training.")
    if isinstance(p.get("cold_identity_accuracy"), (int, float)) and p["cold_identity_accuracy"] < 0.80:
        tuning_flags.append("SPEAKER_EMBEDDING_SHORT_DURATION_CANDIDATE — confirm with duration-stratified, speaker-bootstrap evidence before adaptation.")
    tuning_flags.append("SEGMENTATION_REAL_DEVICE_DATA_REQUIRED — collect XVF/room audio before any segmentation fine-tuning decision.")
    fine_tuning = "# Fine-Tuning Candidates\n\nNo fine-tuning was performed. These are screening decisions, not authorization to train.\n\n" + "\n".join(f"- {flag}" for flag in tuning_flags) + "\n\nEvery candidate must rerun the frozen held-out and reliability tests and must be rejected if false-known safety regresses.\n"
    (summary_root / "FINE_TUNING_CANDIDATES.md").write_text(fine_tuning, encoding="utf-8")

    xvf = """# XVF3800 Integration Handoff

XVF integration is intentionally not implemented in this campaign.

## Timestamped input contract

For each processed-audio frame/event provide: monotonic source timestamp, sample index/rate/channels, processed PCM, signal energy, angle of arrival (AoA), AoA confidence, and direction-change events. Preserve the raw device clock and the host-clock mapping; never infer alignment from arrival order alone.

## Runtime boundary

The backend-neutral streaming runtime consumes audio frames exactly as it does today. Spatial metadata is an optional synchronized side channel used by a future segmentation/clustering policy. Missing or low-confidence AoA must degrade to audio-only behavior, never to a forced identity.

## Frozen future ablations

1. audio only;
2. audio + energy;
3. audio + AoA;
4. audio + energy + AoA;
5. processed XVF audio + metadata.

Measure WER, DER/JER, false-known/wrong-known time, correctly attributed word rate, identity revisions, latency, RTF/RAM, dropped frames, and failure recovery on the same recordings. Actual CM5/UNO Q hardware, carrier, microphone geometry, clock synchronization, and room recordings are required before deployment claims.
"""
    (summary_root / "XVF3800_INTEGRATION_HANDOFF.md").write_text(xvf, encoding="utf-8")

    shutil.copy2(summary_root / "TIMEBOXED_JOB_INVENTORY.csv", summary_root / "RESULT_FILE_INVENTORY.csv")
    demo_source = tool_root / "docs/full_pipeline/H2_DEMO_RUNBOOK.md"
    if demo_source.is_file():
        shutil.copy2(demo_source, summary_root / "DEMO_RUNBOOK.md")
    final_runbook = f"""# Final H2 Runbook

Primary mode: `{primary_name}`. Fallback mode: `{fallback_name}`. Both use `fullpipe_v1_ag_dr_ir`; the fallback is a safer/simpler product-mode alternative, not a second neural architecture.

1. Verify `H2_TIMEBOXED_FINAL_RESULTS.zip` with the SHA-256 in `UPLOAD_THIS_FILE_TO_CHATGPT.txt`.
2. Inspect `FROZEN_POLICY.json`, `frozen_configurations/`, and `h2_configuration_registry.yaml` before launching.
3. Follow `DEMO_RUNBOOK.md` for the desktop UI, microphone, file simulation, enrollment, and export commands.
4. Treat Windows serial RTF/RAM as desktop evidence only. Run the ARM64 acceptance list in `ARM64_HARDWARE_ASSESSMENT.md` on the actual device.
5. Do not change frozen thresholds or policies when reproducing held-out results.

The source repository remains the authoritative location for model assets and raw result trees; the compact package contains hashes and inventories rather than biometric embeddings, raw audio, model weights, or caches.
"""
    (summary_root / "FINAL_RUNBOOK.md").write_text(final_runbook, encoding="utf-8")

    definitions: dict[str, dict[str, Any]] = {}
    for row in all_metrics:
        definitions.setdefault(row["metric_id"], row)
    guide_lines = [
        "# Metric Guide", "",
        "All ratios use 0–1 scale unless the unit says otherwise. Unsupported, undefined, and not measured are never zero.", "",
        "## How to read the results", "",
        "Use held-out rows for final accuracy claims and development rows only for context. Read plain WER/CER as transcription quality, DER/JER as anonymous speaker separation, identity duration/FPIR/FNIR as known-versus-unknown naming safety, and speaker-attributed WER/cpWER plus correctly-transcribed-and-attributed word rate as end-to-end outcomes. A component can look good while the end-to-end rate remains poor because every word must survive ASR, timing, segmentation, clustering, identity, and alignment.", "",
        "Counts and seconds depend on panel duration, so compare modes only on the identical held-out cases. Rates are easier to compare across panels, but their denominator and applicability still matter. The long CSV preserves numerator, denominator, status, and unsupported reason. Confidence intervals in `BOOTSTRAP_INTERVALS.csv` resample reference-speaker clusters with their cases intact; they describe sampling uncertainty, not device-to-device or room-to-room uncertainty.", "",
        "For runtime, total RTF < 1 means faster than real time on the measured Windows host. Cache/replay timing and the partial cutoff diagnostic are not final runtime evidence. Latency fields separate speech evidence time from computation only when their metric definition says so; do not add or subtract differently defined latency fields.", "",
        "## Metric definitions", "",
    ]
    for metric_id in sorted(definitions):
        row = definitions[metric_id]
        direction = (
            "higher is better" if row.get("higher_is_better") is True
            else "lower is better" if row.get("higher_is_better") is False
            else "direction is not declared"
        )
        guide_lines += [f"## `{metric_id}`", "", f"{row.get('definition') or 'Definition not supplied by the evaluator.'}", "", f"Unit: `{row.get('unit')}`; {direction}.", ""]
    (summary_root / "METRIC_GUIDE.md").write_text("\n".join(guide_lines), encoding="utf-8")

    limitations = """# Limitations and Deferred Work

The hard deadline prioritised a defensible two-mode product decision and exportable evidence. It did not invalidate any completed job.

Explicit deferrals:

- 30–60 minute and eight-source long-session expansions;
- the third anonymous-session mode's held-out repeat;
- the three long standardized serial-resource sweeps. The partial known-only sweep is retained only as a non-final engineering diagnostic because its measured runtime showed that all three sweeps would exceed the hard cutoff;
- Original Sherpa reduced regression;
- Common Voice 60+, CHiME-6, and VOiCES diagnostic reruns already covered by earlier component evidence;
- any job that could not finish before the hard deadline (listed explicitly in the inventory).

Consequences: confidence intervals may be absent if the speaker bootstrap did not finish; rare long-session memory drift and thermal drift are less strongly characterised; and native-corpus generalisation relies more heavily on pre-existing component studies. No metric was silently removed, imputed, or reported as zero. Windows resource measurements do not establish ARM64 device readiness.

The signed development CPU-interference disclosure is preserved. Final real-time conclusions use only completed serial resource jobs, not parallel or cache-replay timing and not the contaminated post-promotion integration timing.
"""
    (summary_root / "LIMITATIONS_AND_DEFERRED_WORK.md").write_text(limitations, encoding="utf-8")

    hardware_source = workspace / "timeboxed_completion/HARDWARE_ASSESSMENT.md"
    if hardware_source.is_file():
        shutil.copy2(hardware_source, summary_root / "ARM64_HARDWARE_ASSESSMENT.md")
    else:
        (summary_root / "ARM64_HARDWARE_ASSESSMENT.md").write_text("# ARM64 Hardware Assessment\n\nPending evidence-sourced host comparison; no desktop result is presented as ARM64 proof.\n", encoding="utf-8")

    copied = {
        "SCOPE_AMENDMENT.json": workspace / "timeboxed_completion/scope_amendment.json",
        "SCOPE_AMENDMENT_REVISION_2.json": workspace / "timeboxed_completion/scope_amendment.revision_2.json",
        "SCOPE_AMENDMENT_REVISION_3.json": workspace / "timeboxed_completion/scope_amendment.revision_3.json",
        "CRITICAL_ANALYSIS_PLAN.json": workspace / "timeboxed_completion/critical_analysis_plan.json",
        "PROGRAM_STATE_PRE_COLLECTION.json": workspace / "program_state.json",
        "JOB_MANIFEST.json": workspace / "job_manifest.json",
        "PROTOCOL_MANIFEST.json": workspace / "protocol_manifest.json",
        "FROZEN_POLICY.json": workspace / "frozen_policy.json",
        "RUNTIME_IMPLEMENTATION_IDENTITY.json": workspace / "runtime_implementation_identity.json",
        "CPU_INTERFERENCE_RECEIPT.json": workspace / "engineering_validation/development_host_cpu_interference_receipt.json",
        "SELECTOR_CORRECTION_ACTIVATION.json": workspace / "diagnostics/pre_freeze_selector_correction_activation.json",
        "H2_PROGRAM_CONFIG.yaml": tool_root / "configs/automated_evaluation/h2_product_program.v17.yaml",
        "TIMEBOXED_COMPLETION_README.md": tool_root / "scripts/H2_TIMEBOXED_COMPLETION_README.md",
        "h2_timeboxed_completion.py": tool_root / "scripts/h2_timeboxed_completion.py",
        "h2_timeboxed_report.py": tool_root / "scripts/h2_timeboxed_report.py",
        "h2_timeboxed_freeze_bootstrap.py": tool_root / "scripts/h2_timeboxed_freeze_bootstrap.py",
        "watch_h2_timeboxed_second_pass.ps1": tool_root / "scripts/watch_h2_timeboxed_second_pass.ps1",
        "test_h2_timeboxed_completion.py": tool_root / "tests/test_h2_timeboxed_completion.py",
        "PARTIAL_SERIAL_RESOURCE_DIAGNOSTIC.json": workspace / "dynamic_queues/h2p6_h2_known_only_serial_resource_1e27a1e89d/campaign_progress.json",
    }
    for name, source in copied.items():
        if source.is_file():
            shutil.copy2(source, summary_root / name)
    frozen_source = summary_root / "frozen_configurations"
    if heldout_core_complete and not frozen_source.is_dir():
        raise RuntimeError("held-out completed but frozen configuration directory is missing")
    if frozen_source.is_dir():
        binding = frozen_source / "h2_demo_runtime_binding.frozen.json"
        frozen_policy = workspace / "frozen_policy.json"
        if not binding.is_file() or not frozen_policy.is_file():
            raise RuntimeError("frozen policy exists without the required demo runtime binding")
        policy = read_json(frozen_policy)
        registry = (
            "schema_version: h2-configuration-registry.v1\n"
            f"freeze_identity_sha256: {json.dumps(policy.get('freeze_identity_sha256'))}\n"
            "demo_runtime_binding:\n"
            "  path: frozen_configurations/h2_demo_runtime_binding.frozen.json\n"
            f"  sha256: {sha256_file(binding)}\n"
        )
        (summary_root / "h2_configuration_registry.yaml").write_text(registry, encoding="utf-8")

        candidate_rows = []
        for job_id, mode, role, values in role_entries:
            candidate_rows.append({
                "role": role, "pipeline_id": manifest_by_id[job_id].get("pipeline_id"),
                "product_mode": mode, "frozen_config": f"frozen_configurations/{mode}.json",
                "heldout_state": state["jobs"][job_id].get("state"), "evidence_level": evidence_level,
                "total_rtf": values.get("total_rtf"), "peak_rss_bytes": values.get("peak_rss_bytes"),
                "linux_arm64_classification": "LIKELY_PORTABLE",
            })
        write_csv(
            summary_root / "production_candidate_summary.csv", candidate_rows,
            ["role", "pipeline_id", "product_mode", "frozen_config", "heldout_state", "evidence_level", "total_rtf", "peak_rss_bytes", "linux_arm64_classification"],
        )
        catalog_lines = ["schema_version: h2-timeboxed-production-candidates.v1", "candidates:"]
        for row in candidate_rows:
            catalog_lines += [
                f"  - role: {row['role']}", f"    pipeline_id: {row['pipeline_id']}",
                f"    product_mode: {row['product_mode']}", f"    frozen_config: {row['frozen_config']}",
                f"    heldout_state: {row['heldout_state']}", f"    evidence_level: {row['evidence_level']}",
                f"    linux_arm64_classification: {row['linux_arm64_classification']}",
            ]
        (summary_root / "production_candidate_catalog.yaml").write_text("\n".join(catalog_lines) + "\n", encoding="utf-8")

    shutil.copy2(summary_root / "FINAL_TIMEBOXED_REPORT.md", summary_root / "FINAL_PIPELINE_REPORT.md")
    (summary_root / "PRIMARY_PIPELINE.md").write_text(
        f"# Primary Pipeline\n\n`fullpipe_v1_ag_dr_ir` with `{primary_name}`. Selected by the declared safety-first held-out ordering. See `FINAL_PIPELINE_REPORT.md` and the matching frozen configuration.\n",
        encoding="utf-8",
    )
    (summary_root / "FALLBACK_PIPELINE.md").write_text(
        f"# Fallback Pipeline\n\n`fullpipe_v1_ag_dr_ir` with `{fallback_name}`. This is the alternate product-memory mode on the same H2 neural stack, retained for a simpler/safety-competitive operational choice.\n",
        encoding="utf-8",
    )
    (summary_root / "ALTERNATIVE_PIPELINE.md").write_text(
        "# Alternative Pipeline\n\nNo distinct neural alternative is endorsed by this timeboxed H2-only campaign. Original Sherpa remains a comparison target until its deferred regression is run.\n",
        encoding="utf-8",
    )

    zip_path = summary_root / "H2_TIMEBOXED_FINAL_RESULTS.zip"
    state["status"] = package_status
    state["detail"] = (
        "Critical H2 held-out comparison and checksum-bound timeboxed package completed"
        if heldout_core_complete
        else "Hard-deadline results package completed; one or more core held-out jobs are incomplete"
    )
    state["completed_at_utc"] = utc_now()
    state["timeboxed_final_zip"] = str(zip_path)
    state["timeboxed_final_zip_sha256"] = None
    write_json(workspace / "program_state.json", state)
    shutil.copy2(workspace / "program_state.json", summary_root / "PROGRAM_STATE_FINAL.json")
    (summary_root / "UPLOAD_THIS_FILE_TO_CHATGPT.txt").unlink(missing_ok=True)

    repro_files = [
        path for path in sorted(summary_root.rglob("*"))
        if path.is_file()
        and path.name not in {"REPRODUCIBILITY_MANIFEST.json"}
        and path.suffix.lower() != ".zip"
    ]
    repro = {
        "schema_version": "h2-timeboxed-reproducibility.v1", "created_at_utc": utc_now(),
        "status": package_status,
        "workspace": str(workspace), "results_root": str(results_root), "summary_root": str(summary_root),
        "job_manifest_sha256": sha256_file(workspace / "job_manifest.json"),
        "scope_amendment_sha256": sha256_file(workspace / "timeboxed_completion/scope_amendment.json"),
        "files": [{"path": path.relative_to(summary_root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)} for path in repro_files],
    }
    write_json(summary_root / "REPRODUCIBILITY_MANIFEST.json", repro)
    deterministic_zip(summary_root, zip_path)
    zip_sha = sha256_file(zip_path)
    pointer = f"UPLOAD THIS FILE TO CHATGPT:\n{zip_path}\n\nSHA-256:\n{zip_sha}\n"
    (summary_root / "UPLOAD_THIS_FILE_TO_CHATGPT.txt").write_text(pointer, encoding="utf-8")

    state["timeboxed_final_zip_sha256"] = zip_sha
    write_json(workspace / "program_state.json", state)
    collection = {"schema_version": "h2-timeboxed-collection.v1", "created_at_utc": utc_now(), "status": state["status"], "zip_path": str(zip_path), "zip_sha256": zip_sha, "primary": primary_name, "fallback": fallback_name, "evidence_level": evidence_level}
    write_json(workspace / "timeboxed_completion/collection_receipt.json", collection)
    print(pointer.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
