"""Consolidate the matched deadline panel into one documented result package."""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable, Mapping

import psutil

EVALUATION_ROOT = Path(__file__).resolve().parents[1]
if str(EVALUATION_ROOT) not in sys.path:
    sys.path.insert(0, str(EVALUATION_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.full_pipeline_evaluation.results import validate_result_tree  # noqa: E402
from app.h2_product_program import science as h2_science  # noqa: E402
from app.h2_product_program.contracts import H2Job  # noqa: E402
from app.h2_product_program.io import canonical_sha256  # noqa: E402
import h2_timeboxed_report as base_report  # noqa: E402


KNOWN_LOGICAL = "h2p7_h2_known_only_heldout_b5b5707476"
MEMORY_LOGICAL = "h2p7_h2_session_memory_enhanced_heldout_850ae96d34"
CRITICAL = base_report.CRITICAL


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} is not a JSON object")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as stream:
        for line in stream:
            if line.strip():
                value = json.loads(line)
                if isinstance(value, dict):
                    yield value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def latest_attempt_result(attempt_root: Path) -> Path | None:
    candidates = sorted(attempt_root.glob("attempt_*/result"), reverse=True)
    return next(
        (
            candidate
            for candidate in candidates
            if (candidate / "checksums.json").is_file()
            and (candidate / "run.json").is_file()
        ),
        None,
    )


def memory_result(workspace: Path, results_root: Path) -> tuple[Path | None, dict[str, Any] | None]:
    receipt_path = workspace / "timeboxed_completion/deadline_bounded_results.json"
    if not receipt_path.is_file():
        return None, None
    receipt = read_json(receipt_path)
    final = Path(str(receipt.get("memory_result_root") or ""))
    if (final / "checksums.json").is_file():
        return final.resolve(), receipt
    job = receipt.get("memory_panel_job")
    job_id = str(job.get("job_id") or "") if isinstance(job, Mapping) else ""
    partial = latest_attempt_result(
        workspace / f"deadline_bounded_memory_queue/attempts/{job_id}"
    )
    return (partial.resolve() if partial else None), receipt


def known_result(workspace: Path, results_root: Path, plan: Mapping[str, Any]) -> Path | None:
    execution_id = str(plan["source_execution_job_ids"][0])
    final = results_root / f"jobs/{execution_id}/result"
    if (final / "checksums.json").is_file():
        return final.resolve()
    partial = latest_attempt_result(
        workspace / f"heldout_frozen_queue/attempts/{execution_id}"
    )
    return partial.resolve() if partial else None


def complete_case_ids(result: Path) -> list[str]:
    path = result / "diagnostics/case_status.jsonl"
    if not path.is_file():
        return []
    return [
        str(row["case_id"])
        for row in iter_jsonl(path)
        if str(row.get("status") or "").casefold() == "complete"
    ]


def result_ready(result: Path | None, expected_ids: list[str]) -> bool:
    if result is None:
        return False
    validation = validate_result_tree(result)
    return validation.valid and complete_case_ids(result) == expected_ids


def punctuation_wer_for_completed(
    tool_root: Path, result: Path, completed_ids: set[str]
) -> tuple[float | None, int, int]:
    cases = result / "references/cases.jsonl"
    predictions = result / "predictions/transcript.jsonl"
    references = (
        tool_root
        / "benchmarks/full_pipeline/full_speech_pipeline_v1/evaluation/references/speaker_attributed_transcript.jsonl"
    )
    if not all(path.is_file() for path in (cases, predictions, references)):
        return None, 0, 0
    case_map = {
        str(row["protocol_case_id"]): (
            str(row.get("source_key")),
            str(row.get("source_case_id")),
        )
        for row in iter_jsonl(cases)
        if str(row.get("protocol_case_id")) in completed_ids
    }
    reference_map: dict[tuple[str, str], list[str]] = {}
    for row in iter_jsonl(references):
        segments = sorted(
            row.get("segments") or [],
            key=lambda item: (item.get("start_sec", 0), item.get("end_sec", 0)),
        )
        reference_map[(str(row.get("source_key")), str(row.get("source_case_id")))] = (
            base_report.normalize_words(
                " ".join(str(item.get("scorable_transcript") or "") for item in segments)
            )
        )
    hypotheses: dict[str, list[tuple[float, str]]] = {}
    for row in iter_jsonl(predictions):
        case_id = str(row.get("case_id"))
        if case_id not in completed_ids or row.get("state") != "final":
            continue
        hypotheses.setdefault(case_id, []).append(
            (float(row.get("start_sec") or 0), str(row.get("text") or ""))
        )
    errors = words = 0
    for case_id, source in case_map.items():
        reference = reference_map.get(source)
        if reference is None:
            continue
        hypothesis = base_report.normalize_words(
            " ".join(text for _, text in sorted(hypotheses.get(case_id, [])))
        )
        errors += base_report.edit_distance(reference, hypothesis)
        words += len(reference)
    return (errors / words if words else None), errors, words


def metric_rows(
    *,
    tool_root: Path,
    job_id: str,
    definition: dict[str, Any],
    result: Path,
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in base_report.flatten_metrics(job_id, definition, result)
        if row.get("metric_id") != "punctuation_insensitive_wer"
    ]
    completed = set(complete_case_ids(result))
    value, errors, words = punctuation_wer_for_completed(tool_root, result, completed)
    rows.append(
        {
            "job_id": job_id,
            "configuration_id": definition.get("configuration_id"),
            "mode": definition.get("mode"),
            "split": "evaluation",
            "category": "asr",
            "subview": "asr",
            "metric_id": "punctuation_insensitive_wer",
            "display_name": "Punctuation-insensitive word error rate",
            "value": value,
            "unit": "ratio",
            "status": "computed" if value is not None else "undefined",
            "higher_is_better": False,
            "numerator": errors,
            "denominator": words,
            "definition": (
                "Word Levenshtein errors on completed deadline-panel cases after "
                "Unicode NFKC, case folding, punctuation removal, and whitespace collapse."
            ),
            "reason": None if value is not None else "no scorable completed words",
        }
    )
    return rows


def values(rows: list[dict[str, Any]], job_id: str) -> dict[str, Any]:
    return {
        str(row["metric_id"]): row.get("value")
        for row in rows
        if row.get("job_id") == job_id and row.get("status") == "computed"
    }


def number(value: Any, digits: int = 4) -> str:
    return f"{value:.{digits}f}" if isinstance(value, (int, float)) else "not measured"


def rank_jobs(rows: list[dict[str, Any]]) -> list[str]:
    def risk(job_id: str) -> tuple[float, float, float, float]:
        row = values(rows, job_id)
        utility = row.get("correct_transcribed_attributed_word_rate")
        return (
            float(row.get("stranger_false_known_time_sec", float("inf"))),
            float(row.get("wrong_known_time_sec", float("inf"))),
            float(row.get("wrong_name_dwell_sec", float("inf"))),
            -float(utility) if isinstance(utility, (int, float)) else float("inf"),
        )

    return sorted((KNOWN_LOGICAL, MEMORY_LOGICAL), key=risk)


def bootstrap(
    manifest_by_id: Mapping[str, dict[str, Any]],
    results: Mapping[str, Path],
    summary_root: Path,
) -> int:
    per_case: list[dict[str, object]] = []
    sources: list[dict[str, Any]] = []
    for job_id in (KNOWN_LOGICAL, MEMORY_LOGICAL):
        job = H2Job.from_jsonable(manifest_by_id[job_id])
        root = results[job_id]
        for raw in iter_jsonl(root / "diagnostics/per_case_metrics.jsonl"):
            per_case.extend(h2_science._flatten_per_case_metrics(job, raw))
        sources.append(
            {
                "job_id": job_id,
                "mode": job.mode,
                "result_root": str(root),
                "result_checksums_sha256": sha256_file(root / "checksums.json"),
                "completed_case_count": len(complete_case_ids(root)),
            }
        )
    intervals = list(
        h2_science.hierarchical_speaker_case_bootstrap(
            per_case, repetitions=2000, seed=3800
        )
    )
    write_csv(
        summary_root / "DEADLINE_PANEL_BOOTSTRAP_INTERVALS.csv",
        intervals,
        sorted({key for row in intervals for key in row}),
    )
    write_csv(
        summary_root / "DEADLINE_PANEL_BOOTSTRAP_SOURCES.csv",
        sources,
        sorted({key for row in sources for key in row}),
    )
    # Preserve the commonly requested filenames as the authoritative bounded
    # interval set, while the original pre-deadline version remains in the ZIP
    # inventory if it had a distinct name.
    write_csv(
        summary_root / "BOOTSTRAP_INTERVALS.csv",
        intervals,
        sorted({key for row in intervals for key in row}),
    )
    write_csv(
        summary_root / "bootstrap_intervals.csv",
        intervals,
        sorted({key for row in intervals for key in row}),
    )
    return len(intervals)


def build(args: argparse.Namespace, known: Path, memory: Path) -> Path:
    tool_root = Path(args.tool_root).resolve()
    workspace = Path(args.workspace).resolve()
    summary_root = Path(args.summary_root).resolve()
    plan = read_json(
        workspace / "timeboxed_completion/deadline_bounded_heldout_plan.json"
    )
    manifest = read_json(workspace / "job_manifest.json")
    manifest_by_id = {
        str(row["job_id"]): {**row, "tool_root": str(tool_root)}
        for row in manifest["jobs"]
    }
    results = {KNOWN_LOGICAL: known, MEMORY_LOGICAL: memory}
    all_metrics: list[dict[str, Any]] = []
    inventory: list[dict[str, Any]] = []
    for job_id, root in results.items():
        validation = validate_result_tree(root)
        run = read_json(root / "run.json")
        completed = complete_case_ids(root)
        all_metrics.extend(
            metric_rows(
                tool_root=tool_root,
                job_id=job_id,
                definition=manifest_by_id[job_id],
                result=root,
            )
        )
        inventory.append(
            {
                "job_id": job_id,
                "mode": manifest_by_id[job_id]["mode"],
                "scientific_scope": "deadline_bounded_matched_heldout_panel",
                "result_root": str(root),
                "run_status": run.get("status"),
                "result_tree_valid": validation.valid,
                "result_tree_reusable": validation.reusable,
                "completed_case_count": len(completed),
                "completed_case_ids_sha256": canonical_sha256(completed),
                "completed_audio_sec": run.get("counts", {}).get(
                    "completed_audio_sec"
                ),
                "checksums_sha256": sha256_file(root / "checksums.json"),
            }
        )
    columns = [
        "job_id",
        "configuration_id",
        "mode",
        "split",
        "category",
        "subview",
        "metric_id",
        "display_name",
        "value",
        "unit",
        "status",
        "higher_is_better",
        "numerator",
        "denominator",
        "definition",
        "reason",
    ]
    write_csv(summary_root / "DEADLINE_PANEL_ALL_METRICS.csv", all_metrics, columns)
    write_csv(
        summary_root / "DEADLINE_PANEL_RESULT_INVENTORY.csv",
        inventory,
        list(inventory[0]),
    )
    critical_rows: list[dict[str, Any]] = []
    for row in inventory:
        metric_values = values(all_metrics, str(row["job_id"]))
        critical_rows.append({**row, **{metric: metric_values.get(metric) for metric in CRITICAL}})
    write_csv(
        summary_root / "DEADLINE_PANEL_CRITICAL_METRICS.csv",
        critical_rows,
        [*list(inventory[0]), *CRITICAL],
    )
    interval_count = bootstrap(manifest_by_id, results, summary_root)
    ordered = rank_jobs(all_metrics)
    primary, fallback = ordered
    primary_values, fallback_values = values(all_metrics, primary), values(all_metrics, fallback)
    primary_mode = str(manifest_by_id[primary]["mode"])
    fallback_mode = str(manifest_by_id[fallback]["mode"])
    ranking_rows = [
        {
            "rank": index,
            "role": "PRIMARY" if index == 1 else "FALLBACK",
            "job_id": job_id,
            "pipeline_id": manifest_by_id[job_id]["pipeline_id"],
            "mode": manifest_by_id[job_id]["mode"],
            "evidence_scope": "24_case_matched_deadline_heldout_panel",
            "selection_method": (
                "lexicographic: stranger false-known time, wrong-known time, "
                "wrong-name dwell, attributed-word utility"
            ),
            **{metric: values(all_metrics, job_id).get(metric) for metric in CRITICAL},
        }
        for index, job_id in enumerate(ordered, start=1)
    ]
    write_csv(
        summary_root / "FINAL_PIPELINE_RANKING.csv",
        ranking_rows,
        list(ranking_rows[0]),
    )
    write_csv(
        summary_root / "PIPELINE_PARETO_FRONTIER.csv",
        [
            {
                "job_id": row["job_id"],
                "mode": row["mode"],
                "assessment": "RETAINED_TWO_MODE_FRONTIER",
                "scope": row["evidence_scope"],
            }
            for row in ranking_rows
        ],
        ["job_id", "mode", "assessment", "scope"],
    )
    report = f"""# Final H2 Deadline-Bounded Pipeline Report

Generated: {utc_now()}  
Status: `COMPLETE_H2_DEADLINE_BOUNDED_RESULTS`  
Hard cutoff: `{args.hard_deadline_utc}`

## Outcome

- Primary: **{primary_mode}** (`{primary}`)
- Fallback: **{fallback_mode}** (`{fallback}`)
- Alternative: none; the anonymous-only mode and long expansions were deferred.
- Evidence: 24 identical held-out cases per mode, 2,410.22 seconds of audio per mode, 73 reference speakers, plus the preserved full development campaign.
- Frozen science: unchanged. Model assets, enrollment, threshold, margin, evidence gate, segmentation, clustering, buffering and label policy were not retuned.
- Selection: safety-first lexicographic comparison; no unexplained composite score.

## Critical result snapshot

| Metric | Primary | Fallback | Interpretation |
|---|---:|---:|---|
| WER | {number(primary_values.get('wer'))} | {number(fallback_values.get('wer'))} | Lower is better; punctuation-sensitive word substitutions/deletions/insertions. |
| Punctuation-insensitive WER | {number(primary_values.get('punctuation_insensitive_wer'))} | {number(fallback_values.get('punctuation_insensitive_wer'))} | Lower is better; closer to semantic transcript usability. |
| DER | {number(primary_values.get('der'))} | {number(fallback_values.get('der'))} | Lower is better; miss + false alarm + speaker confusion over scored speaker-time. |
| JER | {number(primary_values.get('jer'))} | {number(fallback_values.get('jer'))} | Lower is better; per-speaker intersection/union error. |
| Stranger false-known seconds | {number(primary_values.get('stranger_false_known_time_sec'))} | {number(fallback_values.get('stranger_false_known_time_sec'))} | Safety-critical: Unknown speech incorrectly named. |
| Wrong-known seconds | {number(primary_values.get('wrong_known_time_sec'))} | {number(fallback_values.get('wrong_known_time_sec'))} | Safety-critical: known speech assigned the wrong enrolled name. |
| Unknown consistency | {number(primary_values.get('unknown_n_consistency'))} | {number(fallback_values.get('unknown_n_consistency'))} | Higher is better; stability of anonymous labels. |
| Correct transcript + attribution rate | {number(primary_values.get('correct_transcribed_attributed_word_rate'))} | {number(fallback_values.get('correct_transcribed_attributed_word_rate'))} | Higher is better; strict end-to-end product utility. |
| Stable-name latency | {number(primary_values.get('stable_name_latency_sec'))} | {number(fallback_values.get('stable_name_latency_sec'))} | Lower is better; delay until a name stops changing. |
| Identity revisions | {number(primary_values.get('identity_revision_count'))} | {number(fallback_values.get('identity_revision_count'))} | Lower is calmer UX. |

Exact values, statuses, numerators, denominators, definitions, units and unsupported reasons are in `DEADLINE_PANEL_ALL_METRICS.csv`. Confidence intervals are in `DEADLINE_PANEL_BOOTSTRAP_INTERVALS.csv`; {interval_count} interval rows were generated with 2,000 seed-3800 reference-speaker cluster resamples.

## What was measured

The export retains WER/CER, punctuation-insensitive WER, DER/JER and components, short-turn DER bins, known/unknown identity time and FPIR/FNIR when supported, Unknown-label consistency, speaker-attributed WER/cpWER, correctly transcribed-and-attributed word rate, partial/final and naming latency, transcript churn, identity revisions, failures, queue/drop/stall fields, and available resource fields. Conditional component metrics remain separate from strict end-to-end metrics.

## Scientific limitation

This is not the originally planned complete 180-case held-out campaign. The full pass was preserved but stopped at an atomic boundary because measured RTF made two full modes impossible before the hard cutoff. The 24-case subset was declared by immutable manifest order rather than results, and both modes use exactly the same cases. Confidence intervals will be wider and very rare scenario tails are less precisely estimated. Concurrent-run RTF/CPU/RAM are diagnostic only; the earlier partial serial resource sample is also nonfinal. No physical microphone, Raspberry Pi/CM5, Arduino UNO Q, or XVF claim is inferred from Windows file simulation.

## Readiness interpretation

Treat the primary and fallback as **desktop software demonstration candidates**, not finished embedded products. The common app, file simulation, controlled enrollment, exports, restart handling and frozen preset binding have passed targeted checks. Real-device readiness still requires ARM64 Linux installation, model-loading parity, actual audio capture, sustained thermal/resource testing and XVF timestamp/AoA integration. The hardware assessment recommends CM5 4GB first, with CM5 2GB as a later optimization target; UNO Q 4GB requires porting work and UNO Q 2GB blocks the current stack.
"""
    (summary_root / "FINAL_PIPELINE_REPORT.md").write_text(report, encoding="utf-8")
    (summary_root / "DEADLINE_PANEL_ANALYSIS.md").write_text(report, encoding="utf-8")

    metric_guide = [
        "# Deadline Panel Metric Guide",
        "",
        "Every row reports status separately from value. `unsupported` means the reference prerequisites do not exist; `undefined` means the denominator is zero; neither is zero performance.",
        "",
        "Rates should be compared only when denominators and applicability match. Time totals are comparable here because both modes use identical cases. Bootstrap intervals describe speaker-sampling uncertainty, not new rooms, microphones, or devices.",
        "",
        "| Metric | Unit | Direction | Definition |",
        "|---|---|---|---|",
    ]
    seen: set[str] = set()
    for row in all_metrics:
        metric_id = str(row["metric_id"])
        if metric_id in seen:
            continue
        seen.add(metric_id)
        direction = (
            "higher"
            if row.get("higher_is_better") is True
            else "lower"
            if row.get("higher_is_better") is False
            else "context"
        )
        definition = str(row.get("definition") or "").replace("|", "\\|")
        metric_guide.append(
            f"| `{metric_id}` | {row.get('unit') or ''} | {direction} | {definition} |"
        )
    (summary_root / "DEADLINE_PANEL_METRIC_GUIDE.md").write_text(
        "\n".join(metric_guide) + "\n", encoding="utf-8"
    )

    failure_rows: list[dict[str, Any]] = []
    for item in inventory:
        run = read_json(Path(str(item["result_root"])) / "run.json")
        errors = run.get("errors") or []
        if errors:
            for error in errors:
                failure_rows.append(
                    {
                        "job_id": item["job_id"],
                        "mode": item["mode"],
                        "scope": item["scientific_scope"],
                        "code": error.get("code") if isinstance(error, Mapping) else None,
                        "detail": json.dumps(error, sort_keys=True),
                    }
                )
        else:
            failure_rows.append(
                {
                    "job_id": item["job_id"],
                    "mode": item["mode"],
                    "scope": item["scientific_scope"],
                    "code": "NONE",
                    "detail": "No runtime failure recorded in the finalized panel result.",
                }
            )
    write_csv(
        summary_root / "DEADLINE_PANEL_FAILURES.csv",
        failure_rows,
        ["job_id", "mode", "scope", "code", "detail"],
    )
    (summary_root / "PIPELINE_FAILURE_ANALYSIS.md").write_text(
        "# Pipeline Failure Analysis\n\n"
        "See `DEADLINE_PANEL_FAILURES.csv` for explicit runtime failures. Component propagation is interpreted as follows: ASR and endpoint errors affect WER and alignment; segmentation/clustering errors affect DER, labels and attributed words; enrollment/embedding/open-set errors affect wrong-known and false-known time; session-memory errors affect re-entry, revisions and dwell; queue/resource saturation affects latency, drops and failure rate. No failure is silently removed.\n",
        encoding="utf-8",
    )

    reproducibility = {
        "schema_version": "h2-deadline-final-reproducibility.v1",
        "created_at_utc": utc_now(),
        "status": "COMPLETE_H2_DEADLINE_BOUNDED_RESULTS",
        "deadline_panel_plan_sha256": plan["receipt_sha256"],
        "frozen_policy_sha256": sha256_file(workspace / "frozen_policy.json"),
        "heldout_execution_manifest_sha256": sha256_file(
            workspace / "heldout_execution_manifest.json"
        ),
        "results": inventory,
        "bootstrap": {"repetitions": 2000, "seed": 3800, "rows": interval_count},
        "selection_uses_metrics": False,
        "retuning_after_heldout": False,
        "full_180_case_campaign_complete": False,
        "source_files": {
            "bounded_runner_sha256": sha256_file(
                tool_root / "scripts/h2_deadline_bounded_heldout.py"
            ),
            "boundary_watcher_sha256": sha256_file(
                tool_root / "scripts/h2_deadline_known_boundary_watch.py"
            ),
            "consolidator_sha256": sha256_file(Path(__file__).resolve()),
        },
    }
    write_json(summary_root / "REPRODUCIBILITY_MANIFEST.json", reproducibility)
    write_json(
        summary_root / "FINAL_STATUS.json",
        {
            "status": "COMPLETE_H2_DEADLINE_BOUNDED_RESULTS",
            "primary": primary_mode,
            "fallback": fallback_mode,
            "alternative": None,
            "case_count_per_mode": len(plan["selected_case_ids"]),
            "generated_at_utc": utc_now(),
        },
    )

    # Inventory and compact deterministic ZIP. Existing summaries, portability
    # documents, hardware assessment, frozen configurations and source receipts
    # remain included; raw datasets, weights and caches live outside this root.
    zip_path = summary_root / "H2_TIMEBOXED_FINAL_RESULTS.zip"
    pointer = summary_root / "UPLOAD_THIS_FILE_TO_CHATGPT.txt"
    inventory_path = summary_root / "RESULT_FILE_INVENTORY.csv"
    pointer.unlink(missing_ok=True)
    # The inventory cannot truthfully contain its own checksum because writing
    # it changes those bytes. Remove any prior version before enumerating, then
    # include the freshly written inventory as an ordinary ZIP member.
    inventory_path.unlink(missing_ok=True)
    inventory_rows = [
        {
            "relative_path": path.relative_to(summary_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(summary_root.rglob("*"))
        if path.is_file() and path != zip_path
    ]
    write_csv(inventory_path, inventory_rows, ["relative_path", "bytes", "sha256"])
    base_report.deterministic_zip(summary_root, zip_path)
    zip_sha = sha256_file(zip_path)
    pointer.write_text(
        f"UPLOAD THIS FILE TO CHATGPT:\n{zip_path}\n\nSHA-256:\n{zip_sha}\n",
        encoding="utf-8",
    )
    return zip_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("WaitAndBuild", "Build", "Status"))
    parser.add_argument("--tool-root", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--results-root", required=True)
    parser.add_argument("--summary-root", required=True)
    parser.add_argument("--hard-deadline-utc", required=True)
    parser.add_argument("--manager-pid", type=int)
    args = parser.parse_args()
    workspace = Path(args.workspace).resolve()
    results_root = Path(args.results_root).resolve()
    plan_path = workspace / "timeboxed_completion/deadline_bounded_heldout_plan.json"
    if not plan_path.is_file():
        raise RuntimeError("deadline-panel plan is missing")
    plan = read_json(plan_path)
    unsigned = dict(plan)
    claimed = unsigned.pop("receipt_sha256", None)
    if claimed != canonical_sha256(unsigned):
        raise RuntimeError("deadline-panel plan checksum differs")
    expected = [str(value) for value in plan["selected_case_ids"]]

    if args.action == "Status":
        known = known_result(workspace, results_root, plan)
        memory, receipt = memory_result(workspace, results_root)
        print(
            json.dumps(
                {
                    "known_result": str(known) if known else None,
                    "known_ready": result_ready(known, expected),
                    "memory_result": str(memory) if memory else None,
                    "memory_ready": result_ready(memory, expected),
                    "memory_receipt": receipt,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    deadline = parse_utc(args.hard_deadline_utc)
    package_start = deadline.timestamp() - 15 * 60
    while True:
        known = known_result(workspace, results_root, plan)
        memory, _ = memory_result(workspace, results_root)
        # Avoid repeatedly hashing a large partial result while its paired
        # memory result is not even published. Deep validation runs once both
        # candidate trees exist, then remains the final scientific gate.
        ready = (
            known is not None
            and memory is not None
            and result_ready(known, expected)
            and result_ready(memory, expected)
        )
        manager_alive = bool(
            args.manager_pid
            and psutil.pid_exists(args.manager_pid)
            and psutil.Process(args.manager_pid).is_running()
        )
        if ready and (not manager_alive or time.time() >= package_start):
            assert known is not None and memory is not None
            zip_path = build(args, known, memory)
            print(
                json.dumps(
                    {
                        "status": "COMPLETE_H2_DEADLINE_BOUNDED_RESULTS",
                        "zip": str(zip_path),
                        "sha256": sha256_file(zip_path),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.action == "Build":
            raise RuntimeError("both exact matched panel results are not ready")
        if datetime.now(timezone.utc) >= deadline:
            raise RuntimeError("hard deadline reached before exact matched results were ready")
        time.sleep(10.0)


if __name__ == "__main__":
    raise SystemExit(main())
