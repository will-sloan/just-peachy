"""Audit completed source-paced cells and emit transcript-free metrics. See README.md."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import string
import sys

from bind_corpus import Audit, check, csvsave, load, save
from run_baseline_screen import source_bindings, stable_hash


def jsonl(path):
    with Path(path).open(encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def normalized_words(value):
    # Same ASCII punctuation deletion/casefold convention as authoritative S4.5
    # lexical reference preparation. Preserve reference-normalized words as given.
    return str(value or "").lower().translate(str.maketrans("", "", string.punctuation)).split()


def edit_distance(reference, hypothesis):
    previous = list(range(len(hypothesis) + 1))
    for i, word in enumerate(reference, 1):
        current = [i]
        for j, other in enumerate(hypothesis, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j-1] + (word != other)))
        previous = current
    return previous[-1]


def number(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def run(args):
    root, output = Path(args.run), Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    audit = Audit()
    admission_ref = audit.bind(root / "ADMISSION.json")
    admission = load(admission_ref["path"])
    contract = admission["contract"]
    check(stable_hash(contract) == admission["contract_sha256"], "Admission contract digest mismatch")
    manifest_ref = audit.bind(contract["manifest"])
    manifest = load(manifest_ref["path"])
    expected = {j["job_id"]: j for j in manifest["jobs"]}
    check(len(expected) == len(manifest["jobs"]), "Duplicate expected job IDs")
    source_integrity = "NOT_RECHECKED_NO_SOURCE_ARGUMENT"
    if args.source:
        check(source_bindings(Path(args.source)) == contract["source_bindings"], "Frozen source differs")
        source_integrity = "PASS"
    for ref in contract["models"]:
        audit.bind(ref)
    runtime_match = sys.version == contract["runtime"]["python"] and all(importlib.metadata.version(name) == version for name, version in contract["runtime"]["packages"].items())
    check(runtime_match, "Analysis host runtime differs from baseline contract")
    completed = {}
    if args.allow_partial:
        for checkpoint in (root / "cells").glob("*/CHECKPOINT.json"):
            data = load(checkpoint)
            if data["status"] == "COMPLETE":
                completed[checkpoint.parent.name] = data["result"]["path"]
    else:
        index = load(root / "RESULT_INDEX.json")
        check(index["status"] == "COMPLETE" and not index["failed"], "Run is not complete; use --allow-partial only for an explicit interim audit")
        completed = index["completed"]
    check(set(completed).issubset(expected), "Unexpected output cells")
    if not args.allow_partial:
        check(set(completed) == set(expected), "Missing completed cells")
    corpus = load(args.corpus)
    catalogue = {s["summary"]["case_id"]: s for s in corpus["scenes"]}
    rows, event_counts, clock_counts, archive_counts = [], Counter(), Counter(), Counter()
    totals = Counter()
    lexical_totals = defaultdict(Counter)
    private_receipts = []
    for job_id, result_path in sorted(completed.items()):
        job = expected[job_id]
        checkpoint = load(root / "cells" / job_id / "CHECKPOINT.json")
        result_ref = audit.bind(checkpoint["result"])
        check(Path(result_ref["path"]) == Path(result_path), "Result index/checkpoint mismatch")
        result = load(result_path)
        check(result["status"] == "COMPLETE" and all(result["checks"].values()), "Completed cell checks failed")
        expected_cache = stable_hash({"contract": admission["contract_sha256"], "job": job})
        check(result["cache_key"] == checkpoint["cache_key"] == expected_cache, "Cell cache binding mismatch")
        check(result["input"]["audio_sha256"] == job["audio_sha256"], "Result audio mismatch")
        audit.bind({"path": job["audio_path"], "sha256": job["audio_sha256"]})
        for ref in result["evidence"]:
            audit.bind(ref)
        snapshot = load(Path(result["attempt"]) / "FINAL_SNAPSHOT.json")
        session = Path(result["session"])
        finalization = load(session / "session_finalization_v3.json")
        check(finalization["state"] == "COMPLETED" and not finalization["live_lanes_at_finalization"] and finalization["event_and_transcript_handles_closed"], "Native finalization incomplete")
        check(finalization["source_samples"] == result["delivered_frames"] == job["frames"], "Whole-source frame mismatch")
        check(snapshot["saved_audio_only"] and not snapshot["people"] and not snapshot["selected_ids"], "Saved-only/profile firewall mismatch")
        check(snapshot["mode"] == "anonymous_conversation" and snapshot["recipe"] == "balanced", "Mode/profile mismatch")
        events = jsonl(session / "events.jsonl")
        clocks = jsonl(session / "s7_clocks.jsonl")
        transcript_events = jsonl(session / "labelled_transcript.jsonl")
        latest = jsonl(session / "latest_labelled_transcript.jsonl")
        check(len({row["utterance_id"] for row in latest}) == len(latest), "Duplicate latest hypothesis utterance IDs")
        nonfinal_latest = sum(not row.get("is_final") for row in latest)
        cell_events = Counter(e.get("event_type", "unspecified") for e in events)
        cell_clocks = Counter(e.get("kind", "unspecified") for e in clocks)
        publication_events = Counter(e.get("event_type", "unspecified") for e in clocks if e.get("kind") == "event_publication")
        event_counts.update(cell_events)
        clock_counts.update(cell_clocks)
        archive_events = []
        for ref in result["evidence"]:
            path = Path(ref["path"])
            if path.name == "events.jsonl" and path.parent != session:
                archive_events.extend(jsonl(path))
        cell_archive_counts = Counter(e.get("kind", "unspecified") for e in archive_events)
        archive_counts.update(cell_archive_counts)
        effective_events = [e["payload"] for e in archive_events if e.get("kind") == "research_effective_config"]
        check(len(effective_events) == 1, "Missing or duplicate actual effective runtime event")
        effective = effective_events[0]
        check(effective["input_gain"] == 1.0, "Actual runtime applied a second input gain")
        check(all(effective["profile"]["runtime"][name] == 1 for name in ("asr_threads", "speaker_threads", "punctuation_threads")), "Actual model runtime thread count differs")
        check(effective["profile"]["input"]["asr_tap"] == effective["profile"]["input"]["identity_tap"] == job["tap"], "Actual tap mismatch")
        check(effective["profile"]["punctuation"]["mode"] == "final_only", "Actual final punctuation mode differs")
        bad_clocks = 0
        for event in clocks:
            for left, right in [("queue_admission_monotonic_sec", "worker_receipt_monotonic_sec"), ("worker_receipt_monotonic_sec", "caption_policy_start_monotonic_sec"), ("caption_policy_start_monotonic_sec", "caption_policy_finish_monotonic_sec"), ("tracker_start_monotonic_sec", "tracker_finish_monotonic_sec"), ("naming_start_monotonic_sec", "naming_finish_monotonic_sec"), ("emit_enter_monotonic_sec", "publication_monotonic_sec"), ("publication_monotonic_sec", "emit_complete_monotonic_sec")]:
                if number(event.get(left)) and number(event.get(right)) and event[left] > event[right] + 1e-9:
                    bad_clocks += 1
        spans = [span for row in snapshot["rows"] for span in row.get("word_spans", [])]
        span_ids = [span["id"] for span in spans]
        duplicate_span_ids = len(span_ids) - len(set(span_ids))
        missing_first_labels = sum("first_shown_label" not in span for span in spans)
        missing_committed_labels = sum("committed_label" not in span for span in spans)
        exact_word_times = sum(span.get("exact_word_start_sec") is not None or span.get("exact_word_end_sec") is not None for span in spans)
        span_revision_count = sum(max(0, len(span.get("speaker_history", [])) - 1) for span in spans)
        check(not duplicate_span_ids and not missing_first_labels and not missing_committed_labels, "Final snapshot ownership fields incomplete")
        # Clock violations remain visible evidence; do not clamp/rewrite them.
        raw_fields = sum(bool(r.get("raw_asr_text")) for r in snapshot["rows"])
        formatted_fields = sum(bool(r.get("final_punctuated_display_text")) for r in snapshot["rows"])
        format_differences = sum(bool(r.get("final_punctuated_display_text")) and r["final_punctuated_display_text"] != r.get("raw_asr_text") for r in snapshot["rows"])
        corrected_fields = sum(bool(r.get("optional_corrected_text")) for r in snapshot["rows"])
        cid = Path(job["audio_path"]).parent.name
        scene = catalogue[cid]
        row = {"job_id": job_id, "case_id": cid, "tap": job["tap"], "status": result["status"], "reference_class": scene["summary"]["reference_class"], "audio_sha256": job["audio_sha256"], "cache_key": result["cache_key"], "source_frames": job["frames"], "delivered_frames": result["delivered_frames"], "source_seconds": job["frames"] / job["sample_rate_hz"], "elapsed_seconds": result["elapsed_seconds"], "session_event_rows": len(events), "archive_event_rows": len(archive_events), "clock_rows": len(clocks), "transcript_event_rows": len(transcript_events), "latest_utterances": len(latest), "caption_rows": len(snapshot["rows"]), "unique_word_spans": len(set(span_ids)), "duplicate_span_ids": duplicate_span_ids, "span_speaker_revisions_after_first": span_revision_count, "span_missing_first_label": missing_first_labels, "span_missing_committed_label": missing_committed_labels, "exact_word_times": exact_word_times, "observed_clock_order_violations": bad_clocks, "raw_asr_fields": raw_fields, "formatted_final_fields": formatted_fields, "raw_formatted_differing_fields": format_differences, "optional_corrected_fields": corrected_fields, "text_partial_events": cell_archive_counts["transcript_partial"], "text_final_events": cell_archive_counts["transcript_final"], "label_revision_decisions": sum(e.get("event_type") == "transcript_label_revision" for e in clocks), "asr_loads_process_cumulative": result["model_cache"]["asr_loads"], "speaker_loads_process_cumulative": result["model_cache"]["speaker_loads"], "source_history_reset": True, "private_gallery_queries": snapshot["metrics"].get("gallery_queries", 0), "wer_reference_words": None, "wer_edits": None, "wer": None, "wer_status": "NOT_REQUESTED"}
        if args.include_lexical:
            if scene["summary"]["reference_class"] == "complete_nonoverlap":
                reference = [word for u in sorted(scene["scene"]["segments"], key=lambda x: x.get("source_start_sample", 0)) if u.get("kind") == "utterance" for word in u["transcript_normalized"].split()]
                hypothesis = [word for u in sorted(latest, key=lambda x: (x.get("source_start_sec", 0), x.get("utterance_id", ""))) for word in normalized_words(u["text"])]
                if not reference:
                    row["wer_status"] = "OMITTED_EMPTY_REFERENCE_DENOMINATOR"
                elif nonfinal_latest:
                    row["wer_status"] = "OMITTED_NONFINAL_LATEST_HYPOTHESIS"
                else:
                    edits = edit_distance(reference, hypothesis)
                    row.update(wer_reference_words=len(reference), wer_edits=edits, wer=edits / len(reference), wer_status="DESCRIPTIVE_COMPLETE_NONOVERLAP_ONLY")
                    lexical_totals[job["tap"]].update({"cells": 1, "reference_words": len(reference), "edits": edits})
            else:
                row["wer_status"] = {"empty_control": "OMITTED_EMPTY_DENOMINATOR", "complete_overlap": "OMITTED_NEEDS_DECLARED_SPEAKER_PERMUTATION_CONVENTION", "incomplete_ambient_reference": "OMITTED_INCOMPLETE_ALL_SPEAKER_TRUTH"}[scene["summary"]["reference_class"]]
        rows.append(row)
        totals.update({k: row[k] for k in ("source_frames", "delivered_frames", "session_event_rows", "archive_event_rows", "clock_rows", "transcript_event_rows", "caption_rows", "unique_word_spans", "duplicate_span_ids", "span_speaker_revisions_after_first", "span_missing_first_label", "span_missing_committed_label", "exact_word_times", "observed_clock_order_violations", "raw_asr_fields", "formatted_final_fields", "raw_formatted_differing_fields", "optional_corrected_fields", "text_partial_events", "text_final_events", "label_revision_decisions", "private_gallery_queries")})
        private_receipts.append(result_ref)
    check(rows, "No completed cells available")
    paired = defaultdict(set)
    for row in rows:
        paired[row["case_id"]].add(row["tap"])
    complete = len(rows) == len(expected) and all(taps == {"O0", "O1"} for taps in paired.values())
    lexical = {tap: {**dict(values), "micro_wer": values["edits"] / values["reference_words"]} for tap, values in lexical_totals.items()}
    summary = {"schema": "n1-baseline-analysis-v1", "status": "PASS" if complete and not totals["observed_clock_order_violations"] else "COMPLETE_WITH_CLOCK_FINDINGS" if complete else "PARTIAL_NOT_ACCEPTANCE", "created_utc": datetime.now(timezone.utc).isoformat(), "expected_cells": len(expected), "completed_cells": len(rows), "completed_scenes": len(paired), "complete_paired_scenes": sum(t == {"O0", "O1"} for t in paired.values()), "missing_job_ids": sorted(set(expected) - completed.keys()), "source_integrity": source_integrity, "model_assets_integrity": "PASS", "runtime_versions_integrity": "PASS", "source_model_config_cache_keys": "PASS", "all_evidence_hashes": "PASS", "all_frames_delivered": totals["source_frames"] == totals["delivered_frames"], "counter_totals": dict(totals), "native_event_types": dict(event_counts), "clock_kinds": dict(clock_counts), "archive_event_kinds": dict(archive_counts), "reference_classes_cells": dict(Counter(r["reference_class"] for r in rows)), "lexical_complete_nonoverlap": lexical, "lexical_scope": "optional descriptive aggregate exact edit distance, original raw model text; only complete nonoverlap; no timing alignment, no model comparison", "lexical_normalization": "lowercase, delete ASCII string.punctuation, split whitespace; authoritative reference-normalized text preserved", "neural_output_reuse": "NONE_HISTORICAL; matching new N1 checkpoints only", "GUI_rendering": "SEPARATE_RECEIPT; these are common core/snapshot results", "physical_microphone_latency": "NOT_TESTED", "Pi_hardware_performance": "NOT_TESTED_OFFLINE", "isolated_resource_benchmark": "NOT_TESTED_CONCURRENT_SCREEN", "exact_word_phonetic_reference_timing": "UNAVAILABLE", "punctuation_reference": "SOURCE_SCRIPT_ONLY_NO_INDEPENDENT_CONVERSATIONAL_GOLD", "admission": admission_ref, "result_receipt_sha256": stable_hash(private_receipts), "source_file_count": len(contract["source_bindings"]), "model_asset_count": len(contract["models"]), "hashes_reverified": len(audit.files)}
    if args.c105_result and Path(args.c105_result).exists():
        c105_ref = audit.bind(args.c105_result)
        c105 = load(c105_ref["path"])
        check(c105["status"] == "COMPLETE_REPLAY_ONLY" and c105["neural_calls"] == 0, "Unexpected C105 execution scope")
        for ref in c105["sources"] + [c105["helper"], c105["application_source"]]:
            audit.bind(ref)
        check(len(c105["rows"]) == 10 and all(r["raw_words_identical"] for r in c105["rows"]), "C105 replay word preservation failed")
        c105_summary = {"status": "ACTUALLY_RUN_PASS_SOURCE_EVENT_REPLAY_ONLY", "variants": 10, "raw_words_preserved_all_variants": True, "source_binding_checks": len(c105["sources"]), "neural_calls": 0, "hardware_calls": 0, "recorded_case": "C105/S45_08_07/O0", "scope": "Exact historical observed pair plus evaluator ordering overlays; original historical application implementation, not current-neural or GUI accuracy", "current_neural_attribution_fix_proven": False, "private_result": c105_ref, "helper": c105["helper"], "historical_application_source": c105["application_source"]}
        save(output / "C105_REPLAY_RECEIPT.json", c105_summary)
        summary["historical_C105_source_event_replay"] = c105_summary
    summary["speaker_revision_counts_scope"] = "Observed native snapshots only; a zero count does not establish synthetic revision-fixture coverage or neural attribution correctness"
    summary["text_event_count_scope"] = "Actual conversation archive kind=transcript_partial/transcript_final; native dispatch journal and S7 event-publication clocks are counted separately"
    summary["actual_effective_profile_verified"] = {"gain": 1.0, "threads_per_model": 1, "tap_matches_audio_manifest": True, "punctuation": "final_only"}
    csvsave(output / (args.prefix + "_CELLS.csv"), rows)
    save(output / (args.prefix + "_SUMMARY.json"), summary)
    print(json.dumps({"status": summary["status"], "cells": len(rows), "expected": len(expected), "paired_scenes": summary["complete_paired_scenes"], "clock_findings": totals["observed_clock_order_violations"]}))
    return 0 if summary["status"] in {"PASS", "PARTIAL_NOT_ACCEPTANCE"} else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Private runner output directory")
    parser.add_argument("--source", required=True, help="Frozen prototype directory for source hash recheck")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--prefix", default="BASELINE_ANALYSIS")
    parser.add_argument("--corpus", default=r"G:\Just_Peachy_N1\20260924_campaign\local\data\CORPUS_BINDINGS_240.json")
    parser.add_argument("--include-lexical", action="store_true", help="Descriptive raw-text WER only for complete nonoverlap references")
    parser.add_argument("--allow-partial", action="store_true", help="Interim audit explicitly marked not acceptance")
    parser.add_argument("--c105-result", default=r"G:\Just_Peachy_N1\20260924_campaign\local\data\c105_boundary_exact_replay\RESULT.json", help="Existing exact historical source-event replay receipt; never runs the historical code")
    raise SystemExit(run(parser.parse_args()))
