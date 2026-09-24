"""Bind saved C105/timing regressions and processed C references. See README.md."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from bind_corpus import Audit, check, csvsave, load, save


def main(args):
    audit = Audit()
    out, local = Path(args.out), Path(args.local)
    sim = Path(args.repo) / "XVF 3800 Testing/XVF Integration Real World RIRs/simulation"
    report = sim / "reports/S6D/20260913T195357Z"
    corpus = load(local / "CORPUS_BINDINGS_240.json")
    ecq = load(local / "ECQ_BINDINGS.json")
    c_ids = {r["source_id"] for r in ecq["material"]["accepted_sources"] if r["s6c_role"] == "C"}
    partition_ref = audit.bind(report / "physical_C_collection_admission_v2/C_CALIBRATION_PARTITION.json")
    partition = load(partition_ref["path"])
    check(partition["disjoint_from_E_Q_verified"] and not partition["Q_used"], "Physical C role admission mismatch")
    check(set(partition["C_source_ids"]).issubset(c_ids), "Physical C includes a non-C clip")
    check(partition["collection_only"] and not partition["gold_time_projection_admitted"], "Re-review changed physical C admission")
    collected, rows = [], []
    for item in partition["actual_acquisition"]:
        case = audit.bind(item["case_result"])
        qualification = audit.bind(item["qualification"])
        streams = []
        for stream in item["streams"]:
            audio = audit.audio(stream["audio"])
            streams.append({**stream, "verified_audio": audio})
            rows.append({"case_id": item["case_id"], "profile": item["capture_profile"], "attempt_id": item["attempt_id"], "stream": stream["name"], "sha256": audio["sha256"], "frames": audio["frames"], "sample_rate_hz": audio["sample_rate_hz"], "subtype": audio["subtype"], "gain": stream["raw_gain"], "status": "HASH_VERIFIED_COLLECTION_ONLY", "exact_projection": "UNAVAILABLE_NOT_ADMITTED", "threshold_fitting": "NOT_ADMITTED_WITHOUT_SEPARATE_C_ONLY_PROJECTION_REVIEW"})
        collected.append({**item, "case_result": case, "qualification": qualification, "streams": streams})
    check(len(collected) == 12 and len(rows) == 72, "Unexpected processed C cardinality")
    for candidate in partition["candidate_case_results"]:
        check(all(s["source_id"] in c_ids for s in candidate["original_source_spans"]), "Physical C source-span role mismatch")
    csvsave(out / "PROCESSED_C_CAPABILITY.csv", rows)
    save(local / "PROCESSED_C_BINDINGS.json", {"partition": partition_ref, "full_partition": partition, "verified_acquisition": collected, "audit_files": list(audit.files.values())})
    csummary = {"status": "VERIFIED_COLLECTION_ONLY", "accepted_saved_cases": 12, "mono_waveform_conditions": 72, "C_source_clips": len(partition["C_source_ids"]), "C_people": len({s["identity"] for s in partition["sources"]}), "source_ids_subset_of_independent_C": True, "E_Q_overlap": False, "exact_gold_projection_admitted": False, "selector_thresholds_admitted": False, "disposition": "Prefer same-device E; processed C is preserved but remains collection-only until a separate C-only timing/projection review. Use clean C as the declared available calibration condition without importing old encoder vectors.", "private_evidence": audit.bind(local / "PROCESSED_C_BINDINGS.json")}
    save(out / "PROCESSED_C_AUDIT.json", csummary)

    # Freeze actual intended/available rosters before any enrollment comparison.
    # Interleave the already-declared corpus seed order for reduced roster sizes;
    # never choose membership from a query's true cast or fill missing E with Q.
    plan = ecq["plan"]
    clean_coverage = ecq["material"]["coverage"]
    device_people = {j["metadata_identity"] for j in ecq["device_matrix"]["jobs"]}
    roster_conditions = []
    for domain, tier in [("clean_source", 5), ("clean_source", 15), ("clean_source", 30), ("XVF_processed", 15)]:
        available = {r["identity"] for r in clean_coverage if r["requested_usable_seconds"] == tier and r["status"] == "AVAILABLE"} if domain == "clean_source" else device_people
        for family, membership in plan["fixed_rosters"].items():
            groups = [[person for person in order if person in membership] for corpus_name, order in sorted(plan["per_corpus_seed_order"].items())]
            ordered = [group[index] for index in range(max(map(len, groups))) for group in groups if index < len(group)]
            check(set(ordered) == set(membership), "Roster corpus seed ordering lost an intended member")
            for size in sorted({0, 1, 2, 4, 8, 15, len(ordered)}):
                if size > len(ordered):
                    continue
                intended = ordered[:size]
                actual = [person for person in intended if person in available]
                absent = [person for person in intended if person not in available]
                casts = [set(scene["scene"]["cast"].values()) for scene in corpus["scenes"]]
                roster_conditions.append({"condition_id": f"{domain}_{tier}s_{family}_R{size:02d}", "domain": domain, "requested_active_seconds": tier, "roster_family": family, "intended_size": size, "actual_available_size": len(actual), "intended_identities": intended, "available_identities": actual, "unavailable_identities": absent, "query_scenes_with_known_reference_strangers": sum(bool(cast - set(actual)) for cast in casts), "query_scenes_with_absent_enrolled_people": sum(bool(set(actual) - cast) for cast in casts), "all_240_queries_retained": True, "scene_truth_used_for_membership": False})
    roster_plan = {"schema": "n1-enrollment-rosters-v1", "status": "FROZEN_BEFORE_NEW_ENROLLMENT_MODEL_COMPARISON", "source_E_C_Q_plan_sha256": Audit().bind(plan["material_manifest"])["sha256"], "membership_rule": "existing fixed roster memberships; sorted corpus names, round-robin each existing per-corpus seed order, deterministic prefixes; unsupported E remains unavailable without replacements", "reference_domains_separate": True, "processed_E_positions_and_streams_separate": True, "processed_C_collection_only": True, "Q_dependent_fitting": False, "vector_spaces": "ReDimNet/TitaNet require independent extraction from the same permitted E and C waveform spans", "conditions": roster_conditions}
    roster_path = out / "ENROLLMENT_ROSTER_PLAN.json"
    if roster_path.exists():
        check(load(roster_path) == roster_plan, "Refuse to alter a frozen roster plan")
    else:
        save(roster_path, roster_plan)

    cases = {scene["summary"]["case_id"]: scene for scene in corpus["scenes"]}
    reasons = {"S45_08_07": "Saved C105 arrival-order/native attribution regression; keep diagnostic even when new UI fixtures pass", "S45_03_03": "Existing short replies/rapid handoff acceptance regression", "S45_06_07": "Existing source-paced long pause/return regression", "S45_12_15": "Already-existing digital silence control; complements one noise-only screen control"}
    regressions, jobs = [], []
    for cid, reason in reasons.items():
        scene = cases[cid]
        regressions.append({"case_id": cid, "taps": ["O0", "O1"], "already_in_screen": scene["summary"]["screen_48"], "reason": reason, "audio_sha256": {c["tap"]: c["audio"]["sha256"] for c in scene["cells"]}, "status": "SAVED_INPUT_VERIFIED_NOT_NEW_N1_INFERENCE", "scope": "explicit diagnostic addition outside fixed48; never alter main-panel denominator"})
        for cell in scene["cells"]:
            jobs.append({"job_id": "N1_REGRESSION_" + cid + "_" + cell["tap"], "audio_path": cell["audio"]["path"], "audio_sha256": cell["audio"]["sha256"], "frames": cell["audio"]["frames"], "sample_rate_hz": 16000, "gain": 1.0, "reset_between_scenes": True, "tap": cell["tap"]})
    boundary_ref = audit.bind(report / "handoff_followup_v1/package/BOUNDARY_REPLAY.json")
    boundary = load(boundary_ref["path"])
    boundary_source_verification = []
    for ref in boundary["sources"]:
        try:
            boundary_source_verification.append({"status": "MATCH", "binding": audit.bind(ref)})
        except (ValueError, OSError) as exc:
            boundary_source_verification.append({"status": "UNAVAILABLE_OR_CHANGED", "expected": ref, "reason": str(exc)})
    save(local / "HISTORICAL_BOUNDARY_BINDINGS.json", {"receipt": boundary_ref, "full_receipt": boundary, "sources": boundary_source_verification})
    regression_report = {"schema": "n1-saved-regressions-v1", "created_utc": datetime.now(timezone.utc).isoformat(), "main_screen_unchanged": True, "saved_scene_additions": regressions, "total_additional_cells": len(jobs), "total_source_seconds": sum(j["frames"] / 16000 for j in jobs), "historical_C105_boundary": {"receipt_sha256": boundary_ref["sha256"], "source_variants": len(boundary["rows"]), "historical_status": boundary["status"], "neural_calls": boundary["neural_calls"], "source_bindings_verified": sum(r["status"] == "MATCH" for r in boundary_source_verification), "source_bindings_unavailable": sum(r["status"] != "MATCH" for r in boundary_source_verification), "N1_status": "REPLAY_RUN_STATUS_IN_C105_REPLAY_RECEIPT.json", "caveat": "Historical event replay did not cure native C105 attribution; source-event fixtures cannot certify neural identity accuracy."}, "existing_nonhardware_timing_tests": ["prototype/tests/test_live_timing.py", "prototype/tests/test_sessions.py", "prototype/tests/test_caption_display.py"], "new_acoustic_scenes_created": 0, "hardware_calls": 0}
    save(out / "REGRESSION_LIST.json", regression_report)
    save(local / "REGRESSION_AUDIO_ONLY.json", {"screen_sha256": audit.bind(out / "REGRESSION_LIST.json")["sha256"], "jobs": jobs})
    print("Verified 12 processed C captures/72 mono conditions; four saved supplemental scenes/eight paired cells; no inference.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=r"C:\Users\amiri\Documents\GitHub\just-peachy")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--local", default=r"G:\Just_Peachy_N1\20260924_campaign\local\data")
    main(parser.parse_args())
