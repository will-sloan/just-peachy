"""Prepare immutable model-independent N2 windows; see README.md."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import soundfile as sf

HERE = Path(__file__).resolve().parent
RATE = 16000


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def bind(path):
    path = Path(path)
    return {"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size}


def frozen_save(path, value):
    path = Path(path)
    if path.exists():
        if load(path) != value:
            raise ValueError(f"Refuse to replace frozen manifest: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


class AudioAudit:
    def __init__(self):
        self.files = {}

    def verify(self, binding):
        path = binding["path"]
        if path not in self.files:
            actual = bind(path)
            if actual["sha256"] != binding["sha256"]:
                raise ValueError(f"Audio hash mismatch: {path}")
            info = sf.info(path)
            if info.samplerate != RATE or info.channels != 1:
                raise ValueError(f"Expected admitted mono16k: {path}")
            self.files[path] = {**actual, "frames": info.frames, "sample_rate_hz": info.samplerate, "channels": info.channels}
        elif self.files[path]["sha256"] != binding["sha256"]:
            raise ValueError("Conflicting source binding")
        return self.files[path]


def clean_window(source, audit):
    audio = audit.verify(source["decoded_16k_binding"])
    if audio["frames"] != source["samples"] or source["source_gain_applied"] != 1:
        raise ValueError("Changed clean source length/gain")
    return {"window_id": "W_" + fingerprint([source["s6c_role"], audio["sha256"], 0, audio["frames"]])[:24],
            "role": source["s6c_role"], "domain": "clean_source", "identity": source["identity"],
            "source_id": source["source_id"], "audio": audio, "start_sample": 0, "end_sample": audio["frames"],
            "sample_rate_hz": RATE, "gain": 1.0, "whole_clip": True,
            "estimated_active_seconds": source["quality"]["active_seconds_estimated"],
            "unique_source_pcm_sha256": source["decoded_pcm_sha256"],
            "timing_scope": "whole_source_clip_estimated_activity_not_phonetic"}


def prepare(args):
    data, local, out = Path(args.n1_data), Path(args.n1_local), Path(args.out)
    protocol = load(HERE / "protocol.json")
    summary = load(data / "DATA_AUDIT_SUMMARY.json")
    expected = {Path(r["path"]).name: r["sha256"] for r in summary["local_evidence"]}
    for name in ("ECQ_BINDINGS.json", "CORPUS_BINDINGS_240.json"):
        if sha(local / name) != expected[name]:
            raise ValueError(f"N1 private binding drift: {name}")
    panel = load(data / "SCREEN_48.json")
    if sha(data / "SCREEN_48.json") != summary["panel_binding"]["sha256"]:
        raise ValueError("N1 screen drift")
    roster_plan = load(data / "ENROLLMENT_ROSTER_PLAN.json")
    ecq = load(local / "ECQ_BINDINGS.json")
    corpus = load(local / "CORPUS_BINDINGS_240.json")
    if any(ecq["independent_intersections"].values()):
        raise ValueError("E/C/Q disjointness audit failed")
    audit = AudioAudit()
    sources = {s["source_id"]: s for s in ecq["material"]["accepted_sources"]}
    windows = [clean_window(s, audit) for s in sources.values()]
    by_source = {w["source_id"]: w for w in windows}
    galleries = []
    for coverage in ecq["material"]["coverage"]:
        selected = [by_source[sid] for sid in coverage["source_ids"]]
        if any(w["role"] != "E" or w["identity"] != coverage["identity"] for w in selected):
            raise ValueError("E identity/role mismatch")
        if len({w["unique_source_pcm_sha256"] for w in selected}) != len(selected):
            raise ValueError("Repeated E material")
        galleries.append({"template_id": f"clean_source_{coverage['identity']}_{coverage['requested_usable_seconds']}s",
                          "domain": "clean_source", "position": "original", "stream": "mono16k",
                          "identity": coverage["identity"], "requested_active_seconds": coverage["requested_usable_seconds"],
                          "status": coverage["status"], "window_ids": [w["window_id"] for w in selected],
                          "unique_estimated_active_seconds": sum(w["estimated_active_seconds"] for w in selected),
                          "whole_clip_seconds": sum((w["end_sample"] - w["start_sample"]) / RATE for w in selected),
                          "shortfall_seconds": coverage["duration_shortfall_seconds"],
                          "source_ids": coverage["source_ids"]})
    for job in ecq["device_matrix"]["jobs"]:
        if job["stream"] not in protocol["processed_streams"]:
            continue
        if any(sources[sid]["s6c_role"] != "E" for sid in job["exact_ordered_E_source_ids"]):
            raise ValueError("Processed E contains non-E source")
        audio = audit.verify(job["processed_audio"])
        wid = "W_" + fingerprint(["E", audio["sha256"], 0, audio["frames"]])[:24]
        windows.append({"window_id": wid, "role": "E", "domain": "XVF_processed", "identity": job["metadata_identity"],
                        "audio": audio, "start_sample": 0, "end_sample": audio["frames"], "sample_rate_hz": RATE,
                        "gain": job["raw_gain"], "stream": job["stream"], "position": job["position_rir_id"],
                        "source_ids": job["exact_ordered_E_source_ids"],
                        "estimated_active_seconds": job["actual_unique_estimated_active_seconds"],
                        "timing_scope": "full_processed_capture_inherited_source_activity_not_output_projection"})
        galleries.append({"template_id": job["job_id"], "domain": "XVF_processed", "identity": job["metadata_identity"],
                          "stream": job["stream"], "position": job["position_rir_id"], "requested_active_seconds": 15,
                          "status": "AVAILABLE" if job["actual_unique_estimated_active_seconds"] >= 15 else "INSUFFICIENT_DURATION",
                          "window_ids": [wid], "source_ids": job["exact_ordered_E_source_ids"],
                          "unique_estimated_active_seconds": job["actual_unique_estimated_active_seconds"],
                          "whole_clip_seconds": audio["frames"] / RATE,
                          "shortfall_seconds": max(0, 15 - job["actual_unique_estimated_active_seconds"]),
                          "processed_source_delay_samples": job["processed_source_delay_samples"]})
    jobs, truth, q_windows = [], [], []
    for scene in corpus["scenes"]:
        meta, original = scene["summary"], scene["scene"]
        for cell in scene["cells"]:
            audio = audit.verify(cell["audio"])
            cid, tap = meta["case_id"], cell["tap"]
            jid = f"N2_{cid}_{tap}"
            if cid in panel["case_ids"]:
                jobs.append({"job_id": jid, "audio_path": audio["path"], "audio_sha256": audio["sha256"],
                             "frames": audio["frames"], "sample_rate_hz": RATE, "gain": 1.0,
                             "reset_between_scenes": True, "tap": tap})
            shift = cell["output_mapping"]["source_with_rir_to_output_offset_samples"]
            turns = []
            for i, seg in enumerate(original["segments"]):
                if seg.get("kind") != "utterance":
                    continue
                support = [seg["source_start_sample"] + 800 + shift, seg["source_stop_sample"] + 800 + shift] if shift is not None else None
                active = [[a + shift, b + shift] for a, b in seg.get("activity_ranges_samples_estimated", [])] if shift is not None else []
                valid = support is not None and 0 <= support[0] < support[1] <= audio["frames"]
                turn = {"turn_id": f"{cid}_{i}", "identity": seg["speaker_key"], "source_id": seg["source_id"],
                        "transcript_normalized": seg["transcript_normalized"], "transcript": seg["transcript"],
                        "word_times": None, "file_support_samples": support, "activity_ranges_samples_estimated": active,
                        "window_available": valid, "unavailable_reason": None if valid else "MISSING_MAPPING_OR_SUPPORT_OUTSIDE_FILE",
                        "estimated_active_seconds": sum(b-a for a,b in active) / RATE,
                        "role": seg.get("role"), "timing_scope": seg["timing_provenance"]}
                turns.append(turn)
                if cid in panel["case_ids"]:
                    q_windows.append({"window_id": "W_" + fingerprint([jid, i, support])[:24], "role": "Q",
                                      "domain": "XVF_query", "identity": seg["speaker_key"], "job_id": jid,
                                      "turn_id": turn["turn_id"], "audio": audio,
                                      "start_sample": support[0] if support else None, "end_sample": support[1] if support else None,
                                      "sample_rate_hz": RATE, "gain": 1.0, "status": "AVAILABLE" if valid else "UNAVAILABLE",
                                      "definition": "EVALUATOR_ONLY_WHOLE_SOURCE_SUPPORT_IN_PROCESSED_QUERY",
                                      "estimated_active_seconds": turn["estimated_active_seconds"],
                                      "overlap_may_contaminate": meta["overlap"]})
            truth.append({"job_id": jid, "case_id": cid, "tap": tap, "frames": audio["frames"],
                          "reference_class": meta["reference_class"], "complete_reference": meta["complete_reference"],
                          "screen48": cid in panel["case_ids"], "turns": turns, "output_mapping": cell["output_mapping"],
                          "activity_grid_s": 0.02, "exact_word_timing": "UNAVAILABLE", "scene_cast": sorted(original["cast"].values())})
    if len(jobs) != 96 or len(truth) != 480:
        raise ValueError("N1 scene denominator changed")
    # Frozen roster membership is copied; real per-condition shortages stay explicit.
    primary = []
    for domain in protocol["enrollment_domains"]:
        for condition in protocol["primary_rosters"]:
            candidates = [r for r in roster_plan["conditions"] if r["domain"] == domain and r["requested_active_seconds"] == 15 and r["roster_family"] == condition["family"]]
            chosen = max(candidates, key=lambda r: r["intended_size"]) if condition["size"] == "all" else next(r for r in candidates if r["intended_size"] == condition["size"])
            primary.append({**chosen, "mode": condition["mode"], "n2_condition_id": chosen["condition_id"] + "_" + condition["mode"],
                            "closed_assumption_is_not_recognition": condition["mode"] == "closed"})
    available = [{r["identity"] for r in ecq["material"]["coverage"] if r["requested_usable_seconds"] == tier and r["status"] == "AVAILABLE"} for tier in [5,15,30]]
    matched = sorted(set.intersection(*available))
    denominators = []
    for roster in primary:
        members = set(roster["available_identities"])
        for scope in ["screen48", "all240"]:
            cells = [t for t in truth if t["tap"] == "O0" and (scope == "all240" or t["screen48"])]
            denominators.append({"condition_id": roster["n2_condition_id"], "scope": scope, "scenes": len(cells),
                                 "source_turns": sum(len(t["turns"]) for t in cells),
                                 "known_member_turns": sum(u["identity"] in members for t in cells for u in t["turns"]),
                                 "known_reference_stranger_turns": sum(u["identity"] not in members for t in cells for u in t["turns"]),
                                 "scenes_with_absent_members": sum(bool(members - set(t["scene_cast"])) for t in cells),
                                 "incomplete_reference_scenes": sum(not t["complete_reference"] for t in cells),
                                 "short_turns_le_1p5_active_s": sum(u["estimated_active_seconds"] <= 1.5 for t in cells for u in t["turns"])})
    inputs = [bind(HERE / "protocol.json")] + [bind(data / n) for n in ["SCREEN_48.json", "ENROLLMENT_ROSTER_PLAN.json", "DATA_AUDIT_SUMMARY.json", "ECQ_PLAN.md"]] + [bind(local / n) for n in ["ECQ_BINDINGS.json", "CORPUS_BINDINGS_240.json"]]
    payloads = {"AUDIO_ONLY.json": {"schema": "n2-audio-only-v1", "protocol_sha256": inputs[0]["sha256"], "jobs": jobs},
                "WINDOW_MANIFEST.json": {"schema": "n2-identical-encoder-windows-v1", "protocol_sha256": inputs[0]["sha256"], "windows": windows, "gallery_templates": galleries, "diagnostic_Q_windows": q_windows, "same_waveform_windows_for": ["E0", "E1"]},
                "EVALUATOR_TRUTH.json": {"schema": "n2-private-evaluator-only-v1", "NEVER_PASS_TO_RUNTIME": True, "cells": truth},
                "ROSTERS.json": {"schema": "n2-rosters-v1", "primary": primary, "matched_5_15_30_clean_identities": matched, "all_clean_identities": sorted(available[0] | available[1] | available[2]), "denominators": denominators}}
    for name, payload in payloads.items():
        frozen_save(out / name, payload)
    receipt = {"schema": "n2-window-preparation-receipt-v1", "status": "ACTUALLY_RUN_HASH_VERIFIED_NO_MODEL_INFERENCE",
               "inputs": inputs, "outputs": [bind(out / name) for name in payloads], "waveform_files": sorted(audit.files.values(), key=lambda x:x["path"]),
               "screen_cells": len(jobs), "all_bank_cells": len(truth), "E_C_windows": dict(Counter(w["role"] for w in windows)),
               "clean_gallery_tiers": len([g for g in galleries if g["domain"] == "clean_source"]), "processed_gallery_conditions": len([g for g in galleries if g["domain"] == "XVF_processed"]),
               "matched_clean_people_5_15_30": len(matched), "diagnostic_Q_windows": len(q_windows), "unavailable_Q_windows": sum(w["status"] != "AVAILABLE" for w in q_windows),
               "processed_C_calibration": "NOT_ADMITTED_COLLECTION_ONLY", "neural_calls": 0, "hardware_calls": 0,
               "known_failure_retained": "N1_S45_12_20_one_inserted_word_each_tap", "n1_frozen_inputs_modified": False}
    frozen_save(out / "MANIFEST_RECEIPT.json", receipt)
    redacted = {k:v for k,v in receipt.items() if k not in {"inputs", "outputs", "waveform_files"}}
    redacted["private_receipt"] = bind(out / "MANIFEST_RECEIPT.json")
    redacted["protocol_sha256"] = sha(HERE / "protocol.json")
    frozen_save(HERE / "PREPARATION_RECEIPT.json", redacted)
    print(json.dumps(redacted, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n1-data", default=str(HERE.parents[1] / "data"))
    parser.add_argument("--n1-local", default="G:/Just_Peachy_N1/20260924_campaign/local/data")
    parser.add_argument("--out", default="G:/Just_Peachy_N1/20260924_campaign/local/n2/evaluation")
    prepare(parser.parse_args())
