"""Audit saved accepted audio/reference bindings and freeze a model-free screen. See README.md."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re
import csv
import string
import wave

import numpy as np
import soundfile as sf


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def csvsave(path, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()} for row in rows)


def check(ok, message):
    if not ok:
        raise ValueError(message)


class Audit:
    def __init__(self):
        self.files = {}

    def bind(self, ref):
        if not isinstance(ref, dict):
            ref = {"path": str(ref)}
        path = Path(ref["path"]).resolve(strict=True)
        key = str(path)
        if key not in self.files:
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            self.files[key] = {"path": key, "sha256": digest.hexdigest(), "bytes": path.stat().st_size}
        got = self.files[key]
        check(not ref.get("sha256") or got["sha256"] == ref["sha256"], "Hash mismatch: " + key)
        check("bytes" not in ref or got["bytes"] == ref["bytes"], "Size mismatch: " + key)
        return got

    def audio(self, ref, pcm_sha=None):
        binding = self.bind(ref)
        info = sf.info(binding["path"])
        check(info.channels == 1 and info.samplerate == 16000 and info.frames > 0, "Expected mono 16k audio")
        if pcm_sha:
            samples, _ = sf.read(binding["path"], dtype="float32")
            check(np.isfinite(samples).all(), "Nonfinite waveform")
            check(hashlib.sha256(samples.astype("<f4").tobytes()).hexdigest() == pcm_sha, "Decoded float32 hash mismatch")
        return {**binding, "frames": info.frames, "sample_rate_hz": info.samplerate, "channels": info.channels, "subtype": info.subtype}


def partition(scene):
    if not any(s.get("kind") == "utterance" for s in scene["segments"]):
        return "empty_control"
    if not scene["all_speaker_reference_complete"]:
        return "incomplete_ambient_reference"
    if scene["overlap_intervals"]:
        return "complete_overlap"
    return "complete_nonoverlap"


def choose_panel(scenes):
    """Four per family, paired contrasts preserved. No prediction/model output input."""
    chosen = []
    for family in sorted({s["family_id"] for s in scenes}):
        pool = [s for s in scenes if s["family_id"] == family]
        def score(group):
            corpora = {u["dataset"] for s in group for u in s["segments"] if u.get("dataset")}
            rooms = {s["receiver_configuration"]["room_table"] for s in group}
            sources = {u["source_id"] for s in group for u in s["segments"] if u.get("kind") == "utterance"}
            noise = {str(s.get("noise_policy")) for s in group}
            qualities = {u.get("quality_partition") for s in group for u in s["segments"] if u.get("quality_partition")}
            classes = {partition(s) for s in group}
            historical = {s["source_partition"] for s in group}
            # Metadata coverage, followed by a fixed SHA tie break. Matched families
            # retain whole pairs so their physical contrast remains interpretable.
            points = (len(classes) * 100 + len(corpora) * 40 + len(historical) * 25
                      + ("Upper Loeb" in rooms) * 20 + len(rooms) * 10
                      + len(qualities) * 10 + len(noise) * 5 + len(sources))
            tie = hashlib.sha256(("N1-screen-v1|" + "|".join(sorted(s["case_id"] for s in group))).encode()).hexdigest()
            return points, tie
        candidates = itertools.combinations(pool, 4)
        if family in {"F05", "F07", "F08"}:
            groups = defaultdict(list)
            for scene in pool:
                groups[scene["matched_pair_id"]].append(scene)
            candidates = (tuple(a + b) for a, b in itertools.combinations(groups.values(), 2) if len(a) == len(b) == 2)
        chosen.extend(max(candidates, key=score))
    return sorted(chosen, key=lambda s: s["case_id"])


def run(args):
    repo, out, local = Path(args.repo), Path(args.out), Path(args.local)
    check(not local.resolve().is_relative_to(Path(args.worktree).resolve()), "Private outputs must be outside the Git worktree")
    out.mkdir(parents=True, exist_ok=True)
    local.mkdir(parents=True, exist_ok=True)
    audit = Audit()
    sim = repo / "XVF 3800 Testing/XVF Integration Real World RIRs/simulation"
    s45 = sim / "reports/S4_5/20260909T031300Z"
    s6c = sim / "reports/S6C/20260910T123540Z"
    s6d = sim / "reports/S6D/20260913T195357Z"
    accepted_ref = audit.bind(s45 / "ACCEPTED_CAPTURES.json")
    accepted = load(accepted_ref["path"])
    scene_ref = audit.bind(accepted["scene_manifest"])
    manifest = load(scene_ref["path"])
    scenes = manifest["scenes"]
    inputs_ref = audit.bind(sim / "reports/S6B/20260909T230840Z/INPUT_INDEX.json")
    inputs = load(inputs_ref["path"])["rows"]
    acceptance = {r["case_id"]: r for r in accepted["accepted"] if not r["excluded_from_240"]}
    input_map = {(r["case_id"], r["stream"]): r for r in inputs}
    check(len(acceptance) == len(scenes) == 240 and len(input_map) == 480, "Expected 240 accepted paired scenes")
    check(set(acceptance) == {s["case_id"] for s in scenes}, "Accepted/scene set mismatch")

    # Freeze identities before reading any historical model output. Only metadata
    # and input bindings are consumed by screen selection.
    screen = choose_panel(scenes)
    panel = {"schema": "n1-screen-v1", "selection": "model-free metadata coverage; exactly four per family; fixed SHA tie-break", "scene_manifest_sha256": scene_ref["sha256"], "case_ids": [s["case_id"] for s in screen], "taps": ["O0", "O1"], "cells": 96, "selected_before_new_predictions": True, "historical_holdout": False}
    panel_path = out / "SCREEN_48.json"
    if panel_path.exists():
        check(load(panel_path) == panel, "Refuse to change an already frozen screen")
    else:
        save(panel_path, panel)
    panel_ref = audit.bind(panel_path)

    catalogue, private, transcripts, errors = [], [], [], []
    for index, scene in enumerate(sorted(scenes, key=lambda s: s["case_id"])):
        cid = scene["case_id"]
        accepted_case = acceptance[cid]
        case_ref = audit.bind(accepted_case["case_result"])
        capture = load(case_ref["path"])
        check(capture["status"] == "PASS" and capture["audio_integrity_status"] == "PASS", cid + " capture failed")
        check(capture["input_scene_sha256"] == accepted_case["input_scene_sha256"] == scene["canonical_audio"]["sha256"], cid + " canonical identity mismatch")
        cells = []
        for tap in ("O0", "O1"):
            row = input_map[cid, tap]
            check(row["raw_audio"]["sha256"] == capture["output_audio"][tap]["sha256"], cid + " mixed physical pair")
            check(Path(row["raw_audio"]["path"]).parent == Path(case_ref["path"]).parent, cid + " mixed pass")
            raw = audit.audio(capture["output_audio"][tap])
            prepared = audit.audio(row["audio"])
            check(raw["frames"] == prepared["frames"] == capture["framing"]["decoded_frames"], cid + " frame mismatch")
            check(prepared["subtype"] == "PCM_16", "Prepared format changed")
            with wave.open(prepared["path"], "rb") as handle:
                pcm_hash = hashlib.sha256(handle.readframes(handle.getnframes())).hexdigest()
            check(pcm_hash == row["audio_pcm_sha256"] == row["baseline_journal"]["sha256"], cid + " historical PCM mismatch")
            check(row["input_gain"] == 1 and row["already_gained"], cid + " duplicate gain")
            check(abs(row["historical_gain_applied_once"] - (10 ** (3/20) if tap == "O0" else 1)) < 1e-12, "Unexpected gain provenance")
            telemetry = audit.bind(row["telemetry"])
            support_ref = audit.bind(row["support"])
            support = load(support_ref["path"])["support"]
            check(support["capture_minus_source_offset_samples"] == capture["payload"]["capture_minus_source_offset_samples"], cid + " offset mismatch")
            cells.append({"tap": tap, "audio": prepared, "raw_audio": raw, "audio_pcm_sha256": pcm_hash, "gain_applied_once": row["historical_gain_applied_once"], "runtime_gain": 1.0, "capture_id": capture["batch"], "case_result": case_ref, "telemetry": telemetry, "support": support_ref, "output_mapping": support["output_mappings"][tap], "historical_prediction_bindings_not_reused": {k: row[k] for k in ["baseline_events", "baseline_summary", "baseline_receipt_chain"]}})
        utterances = [u for u in scene["segments"] if u.get("kind") == "utterance"]
        for segment_index, segment in enumerate(scene["segments"]):
            if segment.get("kind") != "utterance":
                continue
            source = manifest["selected_sources"][segment["source_id"]]
            check(segment["transcript"] == source["transcript"], "Full transcript source mismatch")
            check(segment["transcript_normalized"] == source["transcript_normalized"], "Normalized transcript mismatch")
            check(hashlib.sha256(segment["transcript"].encode("utf-8")).hexdigest() == segment["transcript_sha256"], "Transcript digest mismatch")
            check(bool(segment["transcript_normalized"].strip()), "Unexpected empty speech transcript")
            check(0 <= segment["source_start_sample"] < segment["source_stop_sample"] <= scene["duration_s"] * 16000, "Invalid utterance span")
            transcripts.append({"case_id": cid, "segment_index": segment_index, **segment, "source_provenance": source})
        reference_class = partition(scene)
        words = sum(len(u["transcript_normalized"].split()) for u in utterances)
        rooms = scene["receiver_configuration"]["room_table"]
        check("loeb caf" not in rooms.lower(), "Excluded Loeb Caf entered catalogue")
        summary = {"case_id": cid, "family_id": scene["family_id"], "family": scene["family"], "room": rooms, "corpora": sorted({u["dataset"] for u in utterances}), "quality_partitions": sorted({u["quality_partition"] for u in utterances}), "actor_ids": sorted(scene["cast"].values()), "roles": sorted({u.get("role", "unspecified") for u in utterances}), "historical_source_partition": scene["source_partition"], "reference_class": reference_class, "complete_reference": scene["all_speaker_reference_complete"], "overlap": bool(scene["overlap_intervals"]), "utterances": len(utterances), "reference_words": words, "scheduled_duration_s": scene["duration_s"], "prepared_frames": cells[0]["audio"]["frames"], "sample_rate_hz": 16000, "channels": 1, "prepared_format": "PCM_16", "raw_format": cells[0]["raw_audio"]["subtype"], "capture_id": capture["batch"], "capture_minus_source_offset_samples": capture["payload"]["capture_minus_source_offset_samples"], "O0_sha256": cells[0]["audio"]["sha256"], "O1_sha256": cells[1]["audio"]["sha256"], "O0_gain_already_applied": cells[0]["gain_applied_once"], "O1_gain_already_applied": 1.0, "runtime_gain": 1.0, "original_normalized_transcripts": "LOCAL_FULL_AUDIT", "activity_reference": "estimated 20ms grid; preserved source and mapping provenance", "exact_word_timing": "UNAVAILABLE", "exact_phonetic_timing": "UNAVAILABLE", "punctuation_reference": "original source text only; not independent conversational gold", "metric_limitations": "empty: insertion/hallucination controls only; no WER denominator" if not words else ("incomplete all-speaker truth: target-conditioned lexical scoring only" if not scene["all_speaker_reference_complete"] else ("overlap: speaker/permutation lexical scoring; activity is estimated" if scene["overlap_intervals"] else "lexical scoring supported; timing/activity approximate")), "screen_48": cid in panel["case_ids"]}
        catalogue.append(summary)
        private.append({"summary": summary, "scene": scene, "cells": cells})
        if (index + 1) % 40 == 0:
            print(json.dumps({"phase": "corpus", "scenes_verified": index + 1}), flush=True)
    classes = Counter(r["reference_class"] for r in catalogue)
    check(classes == {"complete_nonoverlap": 156, "complete_overlap": 47, "incomplete_ambient_reference": 26, "empty_control": 11}, "Population differs; investigate before proceeding")
    check(len(transcripts) == 777, "Expected 777 full utterance occurrences")
    csvsave(out / "CORPUS_CATALOGUE_240.csv", catalogue)
    csvsave(out / "SCREEN_48.csv", [r for r in catalogue if r["screen_48"]])
    save(local / "CORPUS_BINDINGS_240.json", {"source_manifests": [accepted_ref, scene_ref, inputs_ref], "scenes": private})
    save(local / "FULL_TRANSCRIPT_AUDIT.json", {"occurrences": transcripts, "note": "Full original and normalized text audited locally, source equality and hashes checked; no transcription was invented."})

    # E/C/Q disjointness: independently recompute source, file/PCM and prompt/text
    # intersections from the full local rows, then verify every admitted decoded WAV.
    eplan_ref = audit.bind(s6c / "enrollment/ENROLLMENT_PLAN_V2.json")
    eplan = load(eplan_ref["path"])
    material_ref = audit.bind(eplan["material_manifest"])
    material = load(material_ref["path"])
    query_ref = audit.bind(eplan["query_manifest"])
    queries = load(query_ref["path"])["rows"]
    qlookup = {(q["case_id"], q["segment_index"]): q for q in queries}
    for record in transcripts:
        query = qlookup[record["case_id"], record["segment_index"]]
        check(query["transcript"] == record["transcript"] and query["normalized_text"] == record["transcript_normalized"], "Q text/scene mismatch")
        check(query["source_id"] == record["source_id"], "Q source mismatch")
    roles = {"E": [], "C": [], "Q": queries}
    for row in material["accepted_sources"]:
        roles[row["s6c_role"]].append(row)
    intersections = {}
    normalized_text = lambda r: " ".join(r["transcript"].lower().translate(str.maketrans("", "", string.punctuation)).split())
    for rows in roles.values():
        for row in rows:
            check(row["prompt_group"] == "TEXT_" + hashlib.sha256(normalized_text(row).encode("utf-8")).hexdigest(), "Prompt group does not match full locally read text")
    key_funcs = {"source_id": lambda r: r["source_id"], "original_sha256": lambda r: r["source_binding"]["sha256"], "decoded_pcm_sha256": lambda r: r["decoded_pcm_sha256"], "normalized_text": normalized_text, "prompt_group": lambda r: r.get("prompt_group"), "native_prompt_key": lambda r: r.get("native_prompt_key")}
    for left, right in [("E", "C"), ("E", "Q"), ("C", "Q")]:
        for key, func in key_funcs.items():
            intersection = {func(r) for r in roles[left] if func(r)} & {func(r) for r in roles[right] if func(r)}
            intersections[left + "_" + right + "_" + key] = sorted(intersection)
            check(not intersection, "E/C/Q leakage: " + left + right + key)
    for role, rows in roles.items():
        seen = set()
        for row in rows:
            binding = row["decoded_16k_binding"]
            if binding["path"] in seen:
                continue
            seen.add(binding["path"])
            audit.audio(binding, row["decoded_pcm_sha256"])
        print(json.dumps({"phase": "reference_audio", "role": role, "unique_decoded_verified": len(seen)}), flush=True)

    device_ref = audit.bind(s6d / "device_enrollment/template_matrix_v1/run_01/DEVICE_TEMPLATE_INPUTS.json")
    device = load(device_ref["path"])
    reference_index_ref = audit.bind(device["capture_reference_index"])
    reference_index = load(reference_index_ref["path"])
    check(device["E_C_Q_source_intersections_empty"], "Device source overlap declared")
    E_ids = {r["source_id"] for r in roles["E"]}
    matrix = []
    for row in material["coverage"]:
        matrix.append({"identity": row["identity"], "dataset": row["dataset"], "requested_seconds": row["requested_usable_seconds"], "domain": "clean_source", "stream": "mono16k", "position": "original", "status": row["status"], "unique_clips": row["unique_clip_count"], "unique_whole_clip_seconds": row["actual_whole_clip_seconds"], "estimated_active_seconds": row["actual_estimated_usable_seconds"], "C_status": row["calibration_status"], "encoder_policy": "re-extract separately per encoder; no cross-model vector reuse"})
    for index, job in enumerate(device["jobs"]):
        check(set(job["exact_ordered_E_source_ids"]).issubset(E_ids), "Device E has non-E source")
        audio = audit.audio(job["processed_audio"])
        audit.bind(job["capture_case"])
        matrix.append({"identity": job["metadata_identity"], "dataset": eplan["people"][job["metadata_identity"]]["dataset"], "requested_seconds": job["nominal_tier_seconds"], "domain": "XVF_S6D_processed_same_device_family_distinct_configuration", "stream": job["stream"], "position": job["position_rir_id"], "status": "AUDIO_HASH_VERIFIED", "unique_clips": len(set(job["exact_ordered_E_source_ids"])), "unique_whole_clip_seconds": job["actual_unique_whole_clip_seconds"], "estimated_active_seconds": job["actual_unique_estimated_active_seconds"], "C_status": "clean_C_available; domain shift must be declared", "encoder_policy": "re-extract separately per encoder; no cross-model vector reuse"})
        if (index + 1) % 120 == 0:
            print(json.dumps({"phase": "device_E_audio", "verified": index + 1}), flush=True)
    csvsave(out / "ENROLLMENT_CAPABILITY_MATRIX.csv", matrix)
    save(local / "ECQ_BINDINGS.json", {"plan": eplan, "material": material, "query_manifest": queries, "device_matrix": device, "device_reference_index": reference_index, "independent_intersections": intersections})
    capability = {"clean_E_clips": len(roles["E"]), "clean_C_clips": len(roles["C"]), "query_occurrences": len(queries), "clean_people": len(eplan["people"]), "clean_matrix_rows": len(material["coverage"]), "same_device_E_people": len({j["metadata_identity"] for j in device["jobs"]}), "same_device_E_cells": len(device["jobs"]), "E_C_Q_intersections": intersections, "leakage_limit": material["leakage_audit"]["alias_limit"], "same_book_E_C_fallback_people": material["leakage_audit"]["same_book_fallback_people"], "personal_profile_access": False, "personal_gallery_modified": False, "vector_reuse_across_encoders": False}
    save(out / "ECQ_AUDIT.json", capability)

    selected_rows = [r for r in catalogue if r["screen_48"]]
    summary = {"schema": "n1-data-audit-v1", "status": "PASS", "created_utc": datetime.now(timezone.utc).isoformat(), "scenes": 240, "waveform_tap_cells": 480, "accepted_physical_pairs_verified": 240, "prepared_and_raw_waveforms_verified": 960, "full_transcript_occurrences_audited": len(transcripts), "reference_classes": dict(classes), "screen_reference_classes": dict(Counter(r["reference_class"] for r in selected_rows)), "screen_families": dict(Counter(r["family_id"] for r in selected_rows)), "screen_corpora": dict(Counter(c for r in selected_rows for c in r["corpora"])), "screen_rooms": dict(Counter(r["room"] for r in selected_rows)), "screen_historical_partitions": dict(Counter(r["historical_source_partition"] for r in selected_rows)), "screen_total_audio_s_both_taps": sum(r["prepared_frames"] / 16000 * 2 for r in selected_rows), "panel_binding": panel_ref, "exact_word_timed_occurrences": sum(bool(t.get("word_times")) for t in transcripts), "punctuated_original_occurrences": sum(bool(re.search(r"[.,?!;:]", t["transcript"])) for t in transcripts), "exact_word_and_phonetic_timing": "UNAVAILABLE; all activity is estimated and preserved without rescore alignment", "punctuation_reference": "SOURCE_TEXT_ONLY; no independent conversational punctuation gold", "Loeb_Caf_scenes": 0, "Upper_Loeb_scenes": sum(r["room"] == "Upper Loeb" for r in catalogue), "gain_policy": "O0 +3dB already once, O1 unity; both prepared inputs runtime gain 1.0", "timing_policy": "800-sample/50ms RIR convention already included, not physical latency; keep original per-tap saved approximate mapping", "inference_ground_truth_firewall": "Runner uses separate audio-only job list; local references never passed to model", "all_240_retained": True, "historical_180_60_labels_metadata_only": True, "reference_capability": capability, "unique_bound_files": len(audit.files), "verified_file_bytes": sum(v["bytes"] for v in audit.files.values())}
    save(local / "FILE_HASH_AUDIT.json", {"files": list(audit.files.values())})
    for name in ["CORPUS_BINDINGS_240.json", "FULL_TRANSCRIPT_AUDIT.json", "ECQ_BINDINGS.json", "FILE_HASH_AUDIT.json"]:
        summary.setdefault("local_evidence", []).append(audit.bind(local / name))
    # This inference-only manifest deliberately omits transcript, actors, source
    # activity, family, seats and enrolled target identities.
    jobs = [{"job_id": f"N1_BASELINE_{scene['summary']['case_id']}_{cell['tap']}", "audio_path": cell["audio"]["path"], "audio_sha256": cell["audio"]["sha256"], "frames": cell["audio"]["frames"], "sample_rate_hz": 16000, "gain": 1.0, "reset_between_scenes": True, "tap": cell["tap"]} for scene in private if scene["summary"]["screen_48"] for cell in scene["cells"]]
    save(local / "BASELINE_SCREEN_AUDIO_ONLY.json", {"screen_sha256": panel_ref["sha256"], "jobs": jobs})
    save(out / "DATA_AUDIT_SUMMARY.json", summary)
    print(json.dumps({"status": "PASS", "scenes": 240, "cells": 480, "screen_cells": 96, "verified_files": len(audit.files), "summary": str(out / "DATA_AUDIT_SUMMARY.json")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=r"C:\Users\amiri\Documents\GitHub\just-peachy")
    parser.add_argument("--worktree", default=r"G:\Just_Peachy_N1\20260924_campaign\worktree")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--local", default=r"G:\Just_Peachy_N1\20260924_campaign\local\data")
    run(parser.parse_args())
