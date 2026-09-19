"""Prepare bound S6D E-enrollment and continuous INPUT PLANS; never render or run."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import soundfile as sf


SIM = Path(__file__).resolve().parent.parent
RUN = "20260913T195357Z"
PRIOR_RUN = "20260910T123540Z"
PRIOR = SIM / "reports" / "S6C" / PRIOR_RUN
REPORT = SIM / "reports" / "S6D" / RUN
PACK = SIM.parent / "Just_Peachy_S6D_Expanded_Capture_Pack_V2" / "Just_Peachy_S6D_Expanded_Capture_Pack_V2"
EXPECTED = {
    "enrollment_plan": "6cbcd082b2afb7f640363d533211b93a3d79e69582f3e34a5306c3a20bca2e84",
    "material": "1ba3916e84c1769c565a61bcef25836b3b857d520e35f4a81449b6a515971ec8",
    "queries": "8bef70a50354b9cafc43a3410259f4a757f3fbd1748862b1a86a11336fe12895",
    "scenes": "69131a703ffc631b461bbf3c46c12de50ecdae2afd77d357d61c72ebf306fd18",
    "A15": "8042fbec1cdd4632d90b9d2148c37114e3fcd1aa8cc39a442d22a575e4177018",
    "B15": "3592836b444ec2a4b398b6f48b3b2937c499d7b3d1a9627af9769138e33d679c",
}
ROOM_KEYS = ("room_table", "recorder_position", "orientation", "obstructed")
POSITIONS = (
    "JPXVF_P1_R06_T01_D01_S01_F00_NAT_CU_R04",
    "JPXVF_P1_R06_T01_D01_S01_F00_NAT_CU_R12",
)
CONVERSATIONS = {
    "CONT_MAIN_TABLE_900": [
        "S45_02_01", "S45_03_15", "S45_04_14", "S45_06_07", "S45_12_02", "S45_12_01",
        "S45_02_16", "S45_03_10", "S45_09_14", "S45_11_07", "S45_05_14", "S45_01_08",
        "S45_12_17", "S45_12_16", "S45_04_09", "S45_06_12", "S45_02_11", "S45_11_12",
    ],
    "CONT_LIBRARY_900": [
        "S45_02_03", "S45_03_07", "S45_04_11", "S45_06_09", "S45_12_04", "S45_12_03",
        "S45_02_08", "S45_03_02", "S45_04_01", "S45_11_04", "S45_05_06", "S45_01_05",
        "S45_12_14", "S45_12_13", "S45_04_06", "S45_06_04", "S45_07_03", "S45_11_09",
    ],
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


VERIFIED = {}


def bind(path, expected=None):
    p = Path(path).resolve(strict=True)
    key = str(p)
    if key not in VERIFIED:
        VERIFIED[key] = {"path": key, "bytes": p.stat().st_size, "sha256": sha(p)}
    out = dict(VERIFIED[key])
    if expected:
        if isinstance(expected, str):
            require(out["sha256"] == expected, f"SHA mismatch: {p}")
        else:
            require(out["sha256"] == expected["sha256"], f"SHA mismatch: {p}")
            require(out["bytes"] == expected["bytes"], f"Size mismatch: {p}")
    return out


def bound_json(binding):
    bind(binding["path"], binding)
    return read(binding["path"])


def audio(binding, channels, frames=None, pcm_sha=None):
    verified = bind(binding["path"], binding)
    info = sf.info(binding["path"])
    require(info.samplerate == 16000 and info.channels == channels and info.subtype == "FLOAT",
            f"Unexpected audio header: {binding['path']}")
    if frames is not None:
        require(info.frames == frames, f"Frame mismatch: {binding['path']}")
    h = hashlib.sha256()
    peak = 0.0
    with sf.SoundFile(binding["path"]) as f:
        for block in f.blocks(blocksize=65536, dtype="float32", always_2d=True):
            require(np.isfinite(block).all(), f"Nonfinite audio: {binding['path']}")
            peak = max(peak, float(np.abs(block).max(initial=0)))
            h.update(block.astype("<f4", copy=False).tobytes())
    if pcm_sha:
        require(h.hexdigest() == pcm_sha, f"Decoded PCM hash mismatch: {binding['path']}")
    return {"binding": verified, "sample_rate_hz": info.samplerate, "channels": info.channels,
            "frames": info.frames, "subtype": info.subtype, "float32_pcm_sha256": h.hexdigest(),
            "peak_abs": peak, "finite": True}


def save(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def geometry_key(g):
    return {k: g[k] for k in ROOM_KEYS}


def audit_disjoint(selected, material, queries):
    c = [s for s in material["accepted_sources"] if s["s6c_role"] == "C"]
    q = queries["rows"]
    specifications = {
        "source_id": lambda s: s.get("source_id"),
        "original_sha256": lambda s: s.get("source_binding", {}).get("sha256"),
        "decoded_pcm_sha256": lambda s: s.get("decoded_pcm_sha256"),
        "prompt_group": lambda s: s.get("prompt_group"),
        "native_prompt_key": lambda s: s.get("native_prompt_key"),
    }
    checks = {}
    for label, rows in (("C", c), ("Q", q)):
        for name, extract in specifications.items():
            a = {extract(s) for s in selected} - {None, ""}
            b = {extract(s) for s in rows} - {None, ""}
            overlap = sorted(a & b)
            checks[f"selected_E_{label}_{name}"] = overlap
            require(not overlap, f"E/{label} intersection: {name}")
    inherited = material["leakage_audit"]
    require(all(not x for x in inherited["exact_intersections"].values()), "Inherited ECQ leakage")
    require(not inherited["Q_parent_books_shared"], "Q book leakage")
    require(not inherited["E_C_parent_chapters_shared"], "E/C chapter leakage")
    return {"checked_selected_E_intersections": checks, "inherited_material_audit": inherited,
            "C_candidate_count": len(c), "Q_occurrence_count": len(q),
            "scope": "Exact admitted source/hash/prompt keys plus inherited parent lineage; no exhaustive acoustic alias detector."}


def prepare(output):
    require(not output.exists(), f"Fresh output directory required: {output}")
    paths = {
        "enrollment_plan": PRIOR / "enrollment" / "ENROLLMENT_PLAN_V2.json",
        "material": PRIOR / "enrollment_inventory" / "v2" / "ECQ_MANIFEST.json",
        "queries": SIM / "staging" / "s6c" / PRIOR_RUN / "source_inventory" / "v2" / "Q_OCCURRENCES.json",
        "scenes": SIM / "scene_bank" / "s45_v2_20260909T031300Z" / "SCENE_MANIFEST.json",
        "rir_manifest": SIM / "rir_library" / "v1" / "RIR_MANIFEST.json",
        "gallery_index": PRIOR / "RESEARCH_GALLERY_INDEX.json",
        "template_index": PRIOR / "enrollment" / "TEMPLATE_INDEX.json",
        "material_review": PRIOR / "independent_review" / "SOURCE_MATERIAL_REVIEW_V1.json",
        "pack": PACK / "Codex_S6D_Expanded_Beam_Capture_V2.md",
        "capture_and_telemetry_plan": PACK / "CAPTURE_AND_TELEMETRY_PLAN.md",
        "integration_ideas": PACK / "BEAM_INTEGRATION_IDEAS.md",
        "capture_transport": SIM / "scripts" / "s6d_capture_transport.py",
        "capture_owner": SIM / "scripts" / "s6d_capture_owner.py",
        "hardware_predeclaration": REPORT / "listening" / "HARDWARE_CASE_PREDECLARATION_V1.json",
        "pacing": REPORT / "pacing" / "PACING_AUDIT.json",
    }
    authorities = {k: bind(p, EXPECTED.get(k)) for k, p in paths.items()}
    docs = {k: read(paths[k]) for k in ("enrollment_plan", "material", "queries", "scenes", "rir_manifest", "gallery_index", "template_index")}
    plan, material, scenes = docs["enrollment_plan"], docs["material"], docs["scenes"]
    require(plan["canonical_case_count"] == 240 and len(scenes["scenes"]) == 240, "Original bank mismatch")
    require(math.isclose(sum(s["duration_s"] for s in scenes["scenes"]), 10967), "Original source seconds changed")
    for key in ("material_manifest", "scene_manifest"):
        bound_json(plan[key])
    bound_json(docs["gallery_index"]["plan"])
    transport_ast = ast.parse(paths["capture_transport"].read_text(encoding="utf-8-sig"))
    constants = {}
    for node in transport_ast.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    require(constants.get("TRANSPORT_PRE_ROLL_SEC") == 1.0 and constants.get("TRANSPORT_POST_ROLL_SEC") == 3.0
            and constants.get("MAX_CALLBACK_FRAMES") == 16384, "Capture timing changed; review recipe")
    guard = 4.0 + 16383 / 48000
    sources = {s["source_id"]: s for s in material["accepted_sources"]}
    templates = {(r["metadata_identity"], r["enrollment_tier"]): r for r in docs["template_index"]["rows"]}
    people, roster_out, unavailable = [], {}, []
    selected_sources = []
    for letter in ("A", "B"):
        label, condition = f"{letter}15", f"FIXED_ROTATION_{letter}"
        row = next(r for r in docs["gallery_index"]["rows"] if r["gallery_condition"] == condition and r["enrollment_tier"] == 15 and r["case_id"] is None)
        gallery = bound_json(row["manifest"])
        require(row["manifest"]["sha256"] == EXPECTED[label], f"Original {label} changed")
        intended = next(r for r in plan["galleries"] if r["gallery_condition"] == condition and r["enrollment_tier"] == 15 and r["case_id"] is None)
        available = intended["available_identities"]
        require(len(gallery["profiles"]) == len(available) == 15, f"Actual {label} size mismatch")
        profiles = {p["profile_id"]: p for p in gallery["profiles"]}
        mapped = []
        for identity in available:
            tr = templates[(identity, 15)]["receipt"]
            t = bound_json(tr)
            require(t["status"] == "COMPLETE" and t["quality_status"] in ("PASS", "REVIEW_LOW_CONSISTENCY"), f"Bad E template: {identity}")
            require(t["identity"]["plan_sha256"] == EXPECTED["enrollment_plan"], "Template plan mismatch")
            require(t["identity"]["backend_sha256"] == gallery["backend_sha256"], "Backend mismatch")
            profile = profiles[t["profile_id"]]
            for kind in ("metadata", "vector"):
                bind(profile[kind]["path"], profile[kind])
                bind(t[kind]["path"], t[kind])
                require(profile[kind]["sha256"] == t[kind]["sha256"], "Gallery/template mismatch")
            utterances = []
            for index, (sid, source_b) in enumerate(zip(t["identity"]["source_ids"], t["identity"]["source_bindings"], strict=True)):
                source = sources[sid]
                require(source["identity"] == identity and source["s6c_role"] == "E", f"Non-E source: {sid}")
                require(source["quality_disposition"] in ("PASS", "REVIEW") and source["whole_clip"] is True
                        and source["native_eligibility"] is True, f"Unadmitted clip: {sid}")
                require(source["source_gain_applied"] == 1.0, f"Unexpected E gain: {sid}")
                require(source_b["sha256"] == source["decoded_16k_binding"]["sha256"], "E waveform mismatch")
                bind(source["source_binding"]["path"], source["source_binding"])
                a = audio(source_b, 1, source["samples"], source["decoded_pcm_sha256"])
                utterances.append({"index": index, "source_id": sid, "metadata_identity": identity,
                    "role": "E", "transcript": source["transcript"], "dataset": source["dataset"],
                    "quality_partition": source["quality_partition"], "quality_disposition": source["quality_disposition"],
                    "quality_review_flags": source.get("quality_review_flags", []),
                    "parent_book": source["parent_book"],
                    "parent_chapter": source["parent_chapter"], "prompt_group": source["prompt_group"],
                    "native_prompt_key": source["native_prompt_key"], "source_binding": source["source_binding"],
                    "decoded_audio_verified": a, "source_crop_samples": [0, source["samples"]],
                    "whole_clip_seconds": source["samples"] / 16000,
                    "estimated_active_seconds": source["quality"]["active_seconds_estimated"],
                    "estimated_activity_ranges_samples": source["quality"]["active_ranges_samples_estimated"],
                    "source_gain_scalar": 1.0, "unique_enrollment_key": sid})
                selected_sources.append(source)
            whole = sum(u["whole_clip_seconds"] for u in utterances)
            active = sum(u["estimated_active_seconds"] for u in utterances)
            require(math.isclose(whole, t["actual_whole_clip_sec"], abs_tol=1e-8), "Whole E tier mismatch")
            require(math.isclose(active, t["actual_estimated_unique_usable_sec"], abs_tol=1e-6) and active >= 15, "Active E tier mismatch")
            c = [s for s in material["accepted_sources"] if s["identity"] == identity and s["s6c_role"] == "C"]
            people.append({"roster": label, "metadata_identity": identity, "display_name": profile["display_name"],
                "profile_id": t["profile_id"], "dataset": plan["people"][identity]["dataset"],
                "nominal_tier_seconds": 15, "actual_unique_whole_clip_seconds": whole,
                "actual_unique_estimated_active_seconds": active, "template_receipt": tr,
                "original_template_quality_status": t["quality_status"],
                "original_gallery_profile": profile, "utterances": utterances,
                "C_calibration_candidates": [{"source_id": s["source_id"], "role": "C", "decoded_16k_binding": s["decoded_16k_binding"],
                    "samples": s["samples"], "estimated_active_seconds": s["quality"]["active_seconds_estimated"]} for s in c],
                "C_audio_verified_here": False})
            mapped.append(t["profile_id"])
        require(set(mapped) == set(profiles), f"Incomplete gallery mapping: {label}")
        roster_out[label] = {"manifest": row["manifest"], "gallery_id": gallery["gallery_id"],
            "backend_sha256": gallery["backend_sha256"], "available_identities": available,
            "unavailable_intended_identities": intended["unavailable_identities"]}
        for identity in intended["unavailable_identities"]:
            tiers = sorted(tier for (person, tier) in templates if person == identity and tier < 15)
            unavailable.append({"roster": label, "metadata_identity": identity, "disposition": "NOT_IN_ORIGINAL_ACTUAL_A15_B15",
                "existing_shorter_tier_receipts": [templates[(identity, tier)] for tier in tiers],
                "action": "Preserve unavailable at15; do not substitute Q or add a person/change the fixed original 30-person comparison."})
    require(len(people) == 30 and len({p["metadata_identity"] for p in people}) == 30, "Original roster identity overlap")
    require(len(selected_sources) == len({s["source_id"] for s in selected_sources}), "Repeated enrollment source")
    leakage = audit_disjoint(selected_sources, material, docs["queries"])
    rirs = {r["run_id"]: r for r in docs["rir_manifest"]["records"]}
    positions = []
    for rid in POSITIONS:
        r = rirs[rid]
        s = scenes["selected_rirs"][rid]
        require(r["status"] == "EXTRACTED" and not r["limitations"] and r["can_proceed_to_hil_proof"], "Ineligible proposed E RIR")
        require(s["file"]["sha256"] == r["output"]["sha256"], "Scene/RIR lineage mismatch")
        positions.append({"position_id": rid.rsplit("_", 1)[-1], "rir_id": rid, "geometry": r["geometry"],
            "time_origin": r["time_origin"], "audio_verified": audio(r["output"], 4, r["output"]["frames"]),
            "status": r["status"], "limitations": r["limitations"], "can_proceed_to_hil_proof": True,
            "library_simulation_ready_flag": r["simulation_ready"], "library_physical_replay_validated_flag": r["physical_replay_validated"],
            "eligibility_scope": "Measured extracted v1 path admitted by frozen S4.5 scene manifest; fresh S6D transport/capture qualification remains required."})
    require(geometry_key(positions[0]["geometry"]) == geometry_key(positions[1]["geometry"]), "Incompatible positions")
    tail_samples = max(p["audio_verified"]["frames"] - 1 for p in positions)
    passes = []
    for person in people:
        cursor = 0
        source_schedule = []
        for index, u in enumerate(person["utterances"]):
            stop = cursor + u["decoded_audio_verified"]["frames"]
            source_schedule.append({"source_id": u["source_id"], "source_start_sample": cursor, "source_stop_sample": stop,
                "source_crop_samples": u["source_crop_samples"], "input_gain_scalar": 1.0,
                "decoded_16k_binding": u["decoded_audio_verified"]["binding"]})
            cursor = stop + (8000 if index < len(person["utterances"]) - 1 else 0)
        source_frames = cursor + tail_samples
        for position in positions:
            passes.append({"planned_pass_id": f"E_{person['roster']}_{person['metadata_identity']}_{position['position_id']}",
                "role": "enrollment", "profile": "P_MAIN6", "status": "INPUT_PLAN_ONLY_NOT_BUILT_NOT_CAPTURED",
                "metadata_identity": person["metadata_identity"], "roster": person["roster"], "nominal_tier_seconds": 15,
                "rir_id": position["rir_id"], "source_schedule": source_schedule, "sample_rate_hz": 16000,
                "source_frames": source_frames, "source_seconds": source_frames / 16000,
                "whole_utterance_seconds": person["actual_unique_whole_clip_seconds"],
                "internal_gap_seconds": (len(source_schedule) - 1) * .5,
                "common_rir_tail_samples": tail_samples, "charged_playback_seconds": source_frames / 16000 + guard,
                "input_payload_binding": None, "output_capture_binding": None})
    require(len(passes) == 60, "Enrollment pass count")
    enrollment = {"schema": "s6d_device_enrollment_input_plan_v1", "status": "PROPOSED_INPUT_PLAN_ONLY",
        "generated_utc": datetime.now(timezone.utc).isoformat(), "authority_sections": ["Pack7.3D", "Pack7.5BXR9", "Pack7.1", "originalS6CECQandA15/B15"],
        "authorities": authorities, "rosters": roster_out, "people": people, "unavailable_intended_people": unavailable,
        "leakage_audit": leakage, "positions": positions, "planned_passes": passes,
        "selection": "Exact original tier15 template receipts in actual A15/B15; no Q accuracy, new model performance, later14-person roster, or source substitution used.",
        "construction_recipe": {
            "approval_state": "Root review required before payload construction; capture admission is a separate owner gate.",
            "dry_sequence": "Original bound FLOAT mono16k E files in template order, complete once per position, unity gain, 8000 exact zero samples between files.",
            "convolution": "Convolve each continuous dry sequence with each existing FLOAT MIC0..3 RIR in full; common output length includes max selected RIR length minus1. No RIR regeneration, channel normalization, source trimming, or invented distance delay.",
            "input_gain_candidate": 1.0,
            "headroom_admission": "Inspect future candidate input finite/peak/rails before PCM24 packing. Unity is the candidate. If headroom fails, block construction admission and predeclare ONE common scalar across all60 candidates before capture; preserve original clean templates and bind a matched scaled-clean condition if scalar differs. Never pick per-file/channel gains or use Q outcomes.",
            "tail_samples": tail_samples, "transport": {"pre_roll_seconds": 1, "post_roll_seconds": 3, "max_terminal_callback_frames_48k": 16383},
            "original_clean_comparator": "Original source-clean E templates are byte-bound above. New processed templates must use the SAME complete E utterances/window policy; retain per-source boundaries when deriving enrollment files rather than letting gaps or repeated positions create extra unique speech.",
            "processed_template_conditions": "P_MAIN6 six raw streams × two positions remain12 conditions. Each ASR/PP/beam/position variant shares the SAME unique E sources. Never average copies blindly or select conditions on Q.",
            "host_gain_policy": "Archive raw streams unchanged. Auto-ASR model input inherits documented O0 adapter then+3dB exactly once; auto-PP inherits O1 unity. Focused-tap model-input gains must be predeclared and calibrated only on disjoint C if needed before derived template/inference work; no per-probe normalization.",
            "frame_mapping": "Retain source E offsets, common RIR50ms significant-origin convention, guarded input origin, packed native/decoded frame origin, and actual output availability. Admit a measured common transport alignment; do not independently time-warp beam/mic channels or assume zero DSP delay.",
            "model_policy": plan["enrollment"],
            "calibration": "Only bound disjoint C candidates may calibrate thresholds/multiple-beam maxima and tap levels. No C capture or inference is scheduled in this60-pass plan; additional C capture would require explicit budget allocation.",
        },
        "missing_inputs_and_limits": [
            "No60 enrollment microphone payloads or device capture manifests yet; input peak/headroom after convolution not measured by this plan.",
            "No measured per-tap gain/delay/capture acceptance for these new E runs yet; focused-tap policy remains a later predeclared C-only gate.",
            "Two positions are Library Conference Room, Square Table End, FLAT and clear; they do not represent other rooms, upright or obstructed device poses. Cross-room scoring must be labeled.",
            "Manual azimuth±5degrees, nominal front/rear-folded geometry and unknown absolute3D/device axes remain limitations; no new position was physically measured.",
            "Existing v1 simulation_ready/physical_replay flags remain false. Canonical S4.5 admitted use and EXTRACTED status do not prove current hardware acceptance or acoustic field validation.",
            "13 intended roster people have no original actual tier15 profile; listed shorter receipts are evidence only, not automatically added people/passes.",
            "Admitted E clips retain original REVIEW quality flags, such as activity near a clip boundary. Original gallery templates with REVIEW_LOW_CONSISTENCY also remain in their actual roster with that label, not upgraded or silently excluded.",
            "E/C HiFi same-book fallbacks for11697,6671,9136 retain distinct chapters and no Q shared books; this is not exhaustive undocumented acoustic-alias detection.",
        ],
        "execution": {"audio_files_created": 0, "hardware_attempts": 0, "model_calls": 0, "human_recordings": 0, "inference_results": None},
    }
    conversation = prepare_conversations(scenes, rirs, docs["queries"], roster_out, guard, authorities)
    e_seconds = sum(p["source_seconds"] for p in passes)
    base_seconds, base_passes = 13307, 292
    total_passes = base_passes + 60 + 2
    total_source = base_seconds + e_seconds + 1800
    total_charge = total_source + total_passes * guard
    extra_passes = 12 + 24
    extra_seconds = extra_passes * 45
    scenario_charge = total_charge + extra_seconds + extra_passes * guard
    require(total_passes <= 480 and total_charge < 21600, "Planned required scope exceeds branch budget")
    budget = {"schema": "s6d_device_enrollment_budget_forecast_v1", "status": "PLANNED_SCENARIO_NOT_CONSUMPTION_LEDGER",
        "source_manifest_original_seconds": 10967, "guard_seconds_per_attempt": guard,
        "max_physical_attempts": 480, "max_charged_playback_seconds": 21600,
        "ledger_path": str(REPORT / "physical_ledger.json"), "ledger_existed_at_plan_read": (REPORT / "physical_ledger.json").exists(),
        "actual_consumed_attempts": None, "actual_consumed_playback_seconds": None,
        "root_reported_state": "Root reported zero physical playback/setters and no physical ledger before this offline plan. No synthetic ledger entries created.",
        "required_scope_components": [
            {"name": "P_MAIN6all240+P_SCAN6fixed48+fourmatchedrepeats", "attempts": base_passes, "source_seconds": base_seconds},
            {"name": "originalA15/B15E30people_twopositions", "attempts": 60, "source_seconds": e_seconds},
            {"name": "two15minutecontinuousinputs", "attempts": 2, "source_seconds": 1800}],
        "required_total": {"attempts": total_passes, "source_seconds": total_source,
            "guard_and_callback_seconds": total_passes * guard, "charged_playback_seconds": total_charge,
            "remaining_attempts": 480 - total_passes, "remaining_playback_seconds": 21600 - total_charge},
        "additional_reserve_scenario": {"not_scheduled_or_authorized_by_this_plan": True,
            "qualification_attempts_assumed": 12, "hypothesis_attempts_assumed": 24,
            "max_source_seconds_each_assumed": 45, "extra_charged_seconds": extra_seconds + extra_passes * guard,
            "total_attempts": total_passes + extra_passes, "total_charged_seconds": scenario_charge,
            "remaining_attempts": 480 - total_passes - extra_passes, "remaining_playback_seconds": 21600 - scenario_charge,
            "note": "Reserve only: qualification lengths, extra INPUT_QA, telemetry contrasts, cold excerpts, C calibration and failed/repeated attempts must be charged by actual owner ledger; no unbounded implicit retries."},
        "duration_denominators": {"unique_E_people": 30, "unique_E_utterances": len(selected_sources),
            "unique_E_whole_clip_seconds": sum(p["actual_unique_whole_clip_seconds"] for p in people),
            "unique_E_estimated_active_seconds": sum(p["actual_unique_estimated_active_seconds"] for p in people),
            "physical_E_source_seconds_with_two_positions_gaps_and_tails": e_seconds,
            "logical_E_streams_if_complete": 360, "independence_note": "360logical streams/60passes/30people are different counts; positions and beams do not multiply unique E duration."},
        "storage_forecast": {
            "new_input_float4_bytes_excluding_headers": round((e_seconds + 1800) * 16000 * 4 * 4),
            "new_E_and_cont_packed_output_pcm24_bytes_upper_excluding_headers": math.ceil((e_seconds + 1800 + 62 * guard) * 48000 * 2 * 3),
            "scope": "Input and one packed output only; decoded archive, derivatives, logs and metadata add bytes. No PCM payload created here.",
            "total_additional_payload_cap_gib": 40, "C_free_floor_gib": 50, "G_free_floor_gib": 75},
    }
    output.mkdir(parents=True)
    save(output / "DEVICE_ENROLLMENT_INPUT_PLAN_V1.json", enrollment)
    save(output / "CONTINUOUS_INPUT_PLAN_V1.json", conversation)
    save(output / "BUDGET_FORECAST_V1.json", budget)
    epoch = output / "source_epoch_v1"
    epoch.mkdir()
    for path in (Path(__file__), Path(__file__).with_name("s6d_enrollment_plan_README.md")):
        shutil.copyfile(path, epoch / path.name)
    write_overview(output, enrollment, conversation, budget)
    receipt = {"status": "INPUT_PLAN_BINDING_CHECKS_PASS_NO_EXECUTION", "generated_utc": datetime.now(timezone.utc).isoformat(),
        "verified_file_count": len(VERIFIED), "verified_input_files": list(VERIFIED.values()),
        "checks": {"actual_original_A15_B15": [15, 15], "distinct_people": 30, "all_selected_sources_role_E": True,
            "selected_E_sources_verified_header_sha_pcm_finite": len(selected_sources), "no_E_C_Q_intersection_on_checked_keys": True,
            "selected_RIR_audio_header_sha_finite": 2, "same_receiver_configuration": True,
            "enrollment_passes_planned": 60, "continuous_source_frames": [14400000, 14400000],
            "continuous_original_4mic_inputs_verified": 36, "all_canonical240_unchanged": True,
            "no_audio_created_no_model_calls_no_device_io": True},
        "outputs": [bind(p) for p in sorted(output.rglob("*")) if p.is_file()],
        "limits": "Planning checks only; no input-render, DSP, identity, ASR, beam, GUI, CM5, physical capture or scientific performance result."}
    save(output / "INPUT_PLAN_VALIDATION_V1.json", receipt)
    print(json.dumps({"output": str(output), "people": 30, "E_utterances": len(selected_sources),
        "planned_E_source_seconds": e_seconds, "required_charged_seconds": total_charge,
        "with_reserve_charged_seconds": scenario_charge, "hardware_attempts_executed": 0,
        "status": receipt["status"]}))


def prepare_conversations(scenes, rirs, queries, rosters, guard, authorities):
    scene_index = {s["case_id"]: s for s in scenes["scenes"]}
    q_by_case = {}
    for row in queries["rows"]:
        q_by_case.setdefault(row["case_id"], []).append(row)
    results = []
    for session_id, ids in CONVERSATIONS.items():
        require(len(ids) == len(set(ids)) == 18, "Conversation scene repetition")
        config = scene_index[ids[0]]["receiver_configuration"]
        blocks, references, cursor = [], [], 0
        for index, cid in enumerate(ids):
            s = scene_index[cid]
            require(s["duration_s"] == 45 and s["receiver_configuration"] == config, "Conversation incompatible room or duration")
            a = audio(s["canonical_audio"], 4, 720000)
            rir_details = []
            for rid in sorted({x["rir_id"] for x in s["segments"] if x.get("rir_id")}):
                r = rirs[rid]
                require(geometry_key(r["geometry"]) == config, f"Mixed receiver: {cid}/{rid}")
                require(r["can_proceed_to_hil_proof"], "Unadmitted conversation RIR")
                require(scenes["selected_rirs"][rid]["file"]["sha256"] == r["output"]["sha256"], "RIR binding mismatch")
                rir_details.append({"rir_id": rid, "geometry": r["geometry"], "status": r["status"],
                    "limitations": r["limitations"], "binding": r["output"], "time_origin": r["time_origin"]})
            music = [x for x in s["segments"] if x.get("category") == "instrumental_music"]
            speech = [x for x in s["segments"] if x["kind"] == "utterance"]
            block = {"block_index": len(blocks), "kind": "original_canonical_four_mic_scene", "case_id": cid,
                "family_id": s["family_id"], "source_start_sample": cursor, "source_stop_sample": cursor + 720000,
                "canonical_input_verified": a, "copy_samples": [0, 720000], "gain_change": 1.0,
                "original_family_headroom_scalar": s["common_family_headroom_scalar"],
                "original_relative_source_scalar": s["relative_source_level_scalar"],
                "source_scene_segments": s["segments"], "rir_bindings": rir_details,
                "all_speaker_reference_complete": s["all_speaker_reference_complete"],
                "coverage_limitations": s["coverage_limitations"], "overlap_scoring_limited": s["overlap_scoring_limited"],
                "music_follows_source_speech_without_reset": bool(music and speech and max(x["source_stop_sample"] for x in music) > max(x["source_stop_sample"] for x in speech)),
                "known_identities_by_original_gallery": {k: sorted({x["speaker_key"] for x in speech} & set(v["available_identities"])) for k, v in rosters.items()}}
            blocks.append(block)
            for q in q_by_case.get(cid, []):
                references.append({"original_Q_occurrence_id": q["occurrence_id"], "case_id": cid,
                    "source_id": q["source_id"], "identity": q["identity"], "role": "Q_EVALUATION_ONLY_NOT_ENROLLMENT_OR_CALIBRATION",
                    "transcript": q["transcript"], "decoded_16k_binding": q["decoded_16k_binding"],
                    "source_crop_samples": q["source_crop_samples"],
                    "conversation_source_start_sample": cursor + q["scene_source_start_sample"],
                    "conversation_source_stop_sample": cursor + q["scene_source_stop_sample"]})
            cursor += 720000
            if index in (3, 11):
                blocks.append({"block_index": len(blocks), "kind": "explicit_digital_zero_gap", "source_start_sample": cursor,
                    "source_stop_sample": cursor + 720000, "seconds": 45, "reason": "Declared long pause for physical DSP state recovery; no device reset."})
                cursor += 720000
        require(cursor == 14400000, "Continuous exact900s length")
        require(any(b.get("music_follows_source_speech_without_reset") for b in blocks), "Missing within-block speech then music")
        require(any(b.get("family_id") == "F06" for b in blocks), "Missing existing silent relocation")
        results.append({"session_id": session_id, "status": "PROPOSED_INPUT_PLAN_ONLY_NOT_BUILT_NOT_CAPTURED",
            "profile": "P_MAIN6", "physical_passes_planned": 1, "receiver_configuration": config,
            "source_frames": cursor, "source_seconds": 900, "carrier_seconds": 904,
            "charged_playback_seconds": 900 + guard, "blocks": blocks, "Q_evaluation_references": references,
            "audio_payload_binding": None, "capture_binding": None})
    return {"schema": "s6d_continuous_microphone_input_plan_v1", "status": "PROPOSED_INPUT_PLAN_ONLY",
        "authorities": authorities, "sessions": results,
        "selection_algorithm": "Fixed metadata-only18 distinct45s scenes per compatible receiver; include F02returns,F03short,F04overlap,F06silent relocation,F12speech/music and music-only, plus two explicit45s pauses after source blocks4 and12. No model performance used.",
        "construction_recipe": "After root review, copy exact full canonical FLOAT MIC0..3 scene samples in listed order into one900s FLOAT four-channel stream per session. Insert only two declared45s digital-zero gaps. Preserve all original scene timing, source/RIR/noise gain and convolution tails; no per-scene reset, normalization, resampling, crossfade or channel alignment. Existing canonical inputs are pre-XVF microphone simulations, not already processed mono outputs.",
        "physical_protocol": "One initial owner/reset before each separate session, one1s transport pre-roll,900s source input,3s post-roll and bounded terminal callback charge. Keep packed capture, XVF DSP, telemetry and stream identity continuous across all blocks and pauses. Reset/restoration only after accepted termination of the entire session. Confirm evaluation-firmware duration allowance and watchdog/restoration first.",
        "clocks": ["original corpus clip and crop samples", "original scene source/RIR origin", "concatenated900s source offsets", "guarded packed-native/decoded capture time", "actual host delivery/model event availability"],
        "denominators": "These are reused Q evaluation sources with new continuous physical state, not new utterances or enrollment material. Preserve repeated source_id references; report unique clips separately from utterance instances. Never send Q references to runtime gallery/calibration logic.",
        "missing_inputs_and_limits": ["Two microphone payloads not constructed; output acceptance and actual continuous state not demonstrated.",
            "Artificial corpus turns retain long internal pauses/tails. Whole canonical scene joins may change source/noise mixture abruptly; report join offsets and preserve adverse boundary effects.",
            "F06 contains measured-path switches during silence, not measured walking or continuously changing room impulse responses.",
            "Music source/noise-only support is metadata-bound; real corpus speech quality strata and incomplete overlap references remain distinct.",
            "Known/withheld status depends on original A15 or B15; per-block mapping is listed. No assumption every scene participant is enrolled.",
            "Cold-reset excerpt comparison, extra INPUT_QA, telemetry contrasts or retries require separate entries in the same480attempt/6h ledger; none scheduled here.",
            "These two15min hardware sessions do not satisfy the separate two30min continuous HOST application-session requirement."],
        "execution": {"audio_files_created": 0, "physical_attempts": 0, "model_calls": 0}}


def write_overview(output, enrollment, conversation, budget):
    d = budget["duration_denominators"]
    b = budget["required_total"]
    reserve = budget["additional_reserve_scenario"]
    lines = ["# S6D device enrollment and continuous input plans", "", "PROPOSED INPUT PLAN ONLY. No microphone payload, playback, model inference, or device enrollment was produced.", "",
        f"Original actual A15/B15 comprise30 disjoint people and {d['unique_E_utterances']} exact E utterances. The nominal15s tier contains {d['unique_E_whole_clip_seconds']:.6f}s unique whole clips and {d['unique_E_estimated_active_seconds']:.6f}s estimated active support. These remain the unique denominators across all positions and beams.", "",
        "Enrollment proposes exactly60 P_MAIN6 passes: each person at Library Conference Room/Square Table End/FLAT/clear measured R04(-80degrees,0.90m) and R12(+75degrees,0.74m). Both are bound existing v1 EXTRACTED RIRs with no record limitations; current physical acceptance remains pending. The13 intended unavailable tier15 identities remain unavailable; shorter-tier receipts are listed without changing the actual roster.", "",
        "DEVICE_ENROLLMENT_INPUT_PLAN_V1.json contains all30 identities, exact ordered E clip/transcript/hash/header references, original gallery/template bindings, disjoint C candidates, E/C/Q checks, two positions,60 source schedules and the reviewed-later construction recipe. Unity source gain is proposed; any headroom failure blocks input admission until one common scalar is explicitly predeclared. No per-file normalization or Q calibration.", "",
        "CONTINUOUS_INPUT_PLAN_V1.json proposes one900s continuous four-mic input for Arise Kitchen Main Table/End of table/FLAT/clear and one for Library Conference Room/Square Table End/FLAT/clear. Each uses18 original45s canonical microphone scenes plus two45s digital-zero pauses, with all source references shifted by exact sample offsets. Existing returns, short turns, overlap, silent relocation and known speech continuing into music-only support are retained. The DSP stays running within a session. These are Q evaluation inputs only and never enrollment material.", "",
        f"Required planned scope is {b['attempts']} attempts: original292 + enrollment60 + continuous2; {b['source_seconds']:.6f}s source plus {b['guard_and_callback_seconds']:.6f}s guards/callback allowance = {b['charged_playback_seconds']:.6f}s ({b['charged_playback_seconds']/3600:.3f}h). Remaining branch allowance is {b['remaining_attempts']} attempts and {b['remaining_playback_seconds']:.6f}s.", "",
        f"An illustrative reserve of12 qualification +24 hypothesis attempts at45s source each brings the forecast to {reserve['total_attempts']} attempts and {reserve['total_charged_seconds']:.6f}s, leaving {reserve['remaining_playback_seconds']:.6f}s. Extra INPUT_QA, failed attempts, telemetry comparisons, C calibration and cold excerpts must fit the actual owner ledger; the reserve is not a schedule or authorization. BUDGET_FORECAST_V1.json has the full arithmetic and storage estimates. No actual-consumption ledger was invented.", "",
        "INPUT_PLAN_VALIDATION_V1.json binds the verified source files and output plans. Validation checked original roster/template linkage; all selected E original and decoded hashes, FLOAT16k mono headers, PCM hashes and finite samples; no selected E/C/Q intersections on admitted keys; RIR hashes/geometry; and36 canonical four-mic inputs/room/length/reference offsets. Library flags remain as originally recorded: no new field or hardware validation claim.", "",
        "Before construction: root reviews these exact plans, confirms the new input source-level/headroom recipe and reference extraction convention. Before capture: owner admits built payload hashes, route/input QA, per-tap policy, safety confirmation, duration/storage budget and watchdog/restoration. Reproduction commands, purpose and I/O are in source_epoch_v1/s6d_enrollment_plan_README.md.", "",
        "All scientific identity/ASR/beam benefit results remain unavailable. Same E utterances in correlated auto/focused/ASR/PP copies cannot increase unique speech duration or independent sample counts.", ""]
    (output / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=REPORT / "device_enrollment")
    args = parser.parse_args()
    prepare(args.output.resolve())


if __name__ == "__main__":
    main()
