"""Independently check published S6D input schedules and annotate source events."""
import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def read(p):
    return json.loads(Path(p).read_text(encoding="utf-8-sig"))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def binding(p):
    p = Path(p).resolve(strict=True)
    return {"path": str(p), "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def audit(root, output):
    require(not output.exists(), "Fresh audit output directory required")
    receipt = read(root / "INPUT_PLAN_VALIDATION_V1.json")
    for b in receipt["outputs"]:
        require(binding(b["path"]) == b, f"Published output changed: {b['path']}")
    e = read(root / "DEVICE_ENROLLMENT_INPUT_PLAN_V1.json")
    c = read(root / "CONTINUOUS_INPUT_PLAN_V1.json")
    budget = read(root / "BUDGET_FORECAST_V1.json")
    people = {p["metadata_identity"]: p for p in e["people"]}
    require(len(people) == 30 and len(e["planned_passes"]) == 60, "Roster/pass mismatch")
    source_ids = {u["source_id"] for p in people.values() for u in p["utterances"]}
    require(len(source_ids) == 190, "Unique E denominator changed")
    require(Counter(p["metadata_identity"] for p in e["planned_passes"]) == Counter({k: 2 for k in people}), "Not two passes/person")
    for p in e["planned_passes"]:
        original = people[p["metadata_identity"]]
        require([u["source_id"] for u in original["utterances"]] == [u["source_id"] for u in p["source_schedule"]], "E source order differs")
        cursor = 0
        for index, u in enumerate(p["source_schedule"]):
            original_u = original["utterances"][index]
            require(u["source_start_sample"] == cursor, "E source gap/start mismatch")
            require(u["source_stop_sample"] - cursor == original_u["decoded_audio_verified"]["frames"], "E clip cropped or repeated")
            require(u["source_crop_samples"] == [0, original_u["decoded_audio_verified"]["frames"]], "E crop mismatch")
            require(u["decoded_16k_binding"] == original_u["decoded_audio_verified"]["binding"], "E source mismatch")
            cursor = u["source_stop_sample"] + (8000 if index + 1 < len(p["source_schedule"]) else 0)
        require(cursor + p["common_rir_tail_samples"] == p["source_frames"], "RIR tail length mismatch")
        require(math.isclose(p["charged_playback_seconds"], p["source_frames"] / 16000 + 4 + 16383 / 48000), "E charge mismatch")
    annotations = []
    for session in c["sessions"]:
        cursor, speech_rows, relocation, music_after, gaps = 0, [], [], [], []
        expected_refs = []
        for block in session["blocks"]:
            start, stop = block["source_start_sample"], block["source_stop_sample"]
            require(start == cursor and stop > start, "Continuous gap or overlap")
            cursor = stop
            if block["kind"] == "explicit_digital_zero_gap":
                gaps.append({"start_seconds": start / 16000, "stop_seconds": stop / 16000, "kind": "explicit_digital_zero_gap"})
                continue
            local = sorted([s for s in block["source_scene_segments"] if s["kind"] == "utterance"], key=lambda s: s["source_start_sample"])
            for seg in local:
                require(seg["source_id"] not in source_ids, "Conversation Q leaked into E")
                require(seg["convolution_stop_sample"] <= stop - start, "Original convolution would be clipped")
                expected_refs.append((block["case_id"], seg["source_id"], seg["speaker_key"], start + seg["source_start_sample"], start + seg["source_stop_sample"]))
                speech_rows.append({"case_id": block["case_id"], "identity": seg["speaker_key"], "source_id": seg["source_id"],
                    "start_seconds": (start + seg["source_start_sample"]) / 16000,
                    "whole_source_stop_seconds": (start + seg["source_stop_sample"]) / 16000,
                    "rir_tail_stop_seconds": (start + seg["convolution_stop_sample"]) / 16000,
                    "rir_id": seg["rir_id"]})
            if block["family_id"] == "F06":
                for index, seg in enumerate(local):
                    previous = [s for s in local[:index] if s["speaker_key"] == seg["speaker_key"]]
                    if previous and previous[-1]["rir_id"] != seg["rir_id"]:
                        tail = max(s["convolution_stop_sample"] for s in local[:index])
                        require(tail < seg["source_start_sample"], "Seat change lacks source/render-tail silence")
                        relocation.append({"case_id": block["case_id"], "identity": seg["speaker_key"],
                            "previous_rir_id": previous[-1]["rir_id"], "return_rir_id": seg["rir_id"],
                            "all_prior_speech_tails_end_seconds": (start + tail) / 16000,
                            "return_source_start_seconds": (start + seg["source_start_sample"]) / 16000,
                            "render_tail_to_return_gap_seconds": (seg["source_start_sample"] - tail) / 16000,
                            "interpretation": "Measured static path switch between utterances during planned silence; not measured motion."})
            if local:
                tail = max(s["convolution_stop_sample"] for s in local)
                known = {k: sorted({s["speaker_key"] for s in local} & set(v["available_identities"])) for k, v in e["rosters"].items()}
                for noise in block["source_scene_segments"]:
                    if noise.get("category") == "instrumental_music" and noise["source_stop_sample"] > tail:
                        music_after.append({"case_id": block["case_id"], "music_source_id": noise["source_id"],
                            "known_identities_by_gallery": known, "last_speech_render_tail_seconds": (start + tail) / 16000,
                            "music_source_stop_seconds": (start + noise["source_stop_sample"]) / 16000,
                            "music_continues_after_speech_tail_seconds": (noise["source_stop_sample"] - tail) / 16000,
                            "interpretation": "Metadata/source construction support, not human judgment or VAD result."})
        require(cursor == 14400000 and len(gaps) == 2 and len(relocation) == 2, "Missing continuous planned condition")
        actual_refs = [(r["case_id"], r["source_id"], r["identity"], r["conversation_source_start_sample"], r["conversation_source_stop_sample"]) for r in session["Q_evaluation_references"]]
        require(Counter(expected_refs) == Counter(actual_refs), "Q reference/canonical speech schedule mismatch")
        require(any(any(x["known_identities_by_gallery"].values()) for x in music_after), "No known speech followed by music support")
        returns = [identity for identity, n in Counter(s["identity"] for s in speech_rows).items() if n >= 2]
        annotations.append({"session_id": session["session_id"], "source_seconds": 900,
            "explicit_zero_gaps": gaps, "silent_measured_path_changes": relocation,
            "music_support_after_known_speech": music_after, "returning_identity_count": len(returns),
            "source_utterance_instances": len(speech_rows), "unique_source_ids": len({s["source_id"] for s in speech_rows}),
            "source_rows": speech_rows, "scope": "Planned source/render support only; no actual DSP, ASR, identity, physical or phonetic timing observations."})
    require(math.isclose(sum(p["source_seconds"] for p in e["planned_passes"]), budget["required_scope_components"][1]["source_seconds"]), "Budget E source mismatch")
    require(budget["required_total"]["attempts"] == 354 and budget["required_total"]["charged_playback_seconds"] < 21600, "Required budget mismatch")
    require(budget["actual_consumed_attempts"] is None and budget["actual_consumed_playback_seconds"] is None, "Fabricated ledger consumption")
    output.mkdir(parents=True)
    artifact = output / "CONTINUOUS_EVENT_ANNOTATIONS_V1.json"
    artifact.write_text(json.dumps({"sessions": annotations}, indent=2) + "\n", encoding="utf-8")
    result = {"status": "PLAN_REFERENCE_AUDIT_PASS_NO_EXECUTION", "input_receipt": binding(root / "INPUT_PLAN_VALIDATION_V1.json"),
        "helper": binding(__file__), "readme": binding(Path(__file__).with_name("s6d_enrollment_plan_audit_README.md")),
        "event_annotations": binding(artifact), "checks": ["Published plan output hashes", "Original E clips preserved once per position", "Exact two positions per original person", "E gaps and tail charge", "Q references equivalent to canonical source segments", "Two exact900s sessions", "Four total source/render-tail-silent measured path changes", "Known speech then continuing music support in both sessions", "No E/Q source intersection", "No invented consumption ledger"],
        "original_template_quality_counts": dict(Counter(p["original_template_quality_status"] for p in people.values())),
        "original_E_source_quality_counts": dict(Counter(u["quality_disposition"] for p in people.values() for u in p["utterances"])),
        "execution": {"audio_rendered": False, "device_accessed": False, "inference_executed": False}}
    (output / "PLAN_REFERENCE_AUDIT_V1.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "output": str(output), "sessions": [{"id": s["session_id"], "silent_path_changes": len(s["silent_measured_path_changes"]), "source_instances": s["source_utterance_instances"]} for s in annotations]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit(args.plan_root.resolve(), args.output.resolve())
