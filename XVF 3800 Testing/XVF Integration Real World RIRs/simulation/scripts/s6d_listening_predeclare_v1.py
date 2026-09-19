"""Metadata-only fixed48 selection and static listening QA; see matching README."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
from s6d_listening_v1 import bind, csv, read, save, verify


class IndexParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.audio, self.articles, self.times = [], [], []
    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag == "audio":
            self.audio.append(attrs)
        if tag == "article":
            self.articles.append(attrs)
        if tag == "li" and "data-times" in attrs:
            self.times.append(json.loads(attrs["data-times"]))


def main(args):
    sim, out, report = args.sim.resolve(), args.output.resolve(), args.report.resolve()
    original_receipt_path = report / "listening/LISTENING_VALIDATION.json"
    original_receipt = read(original_receipt_path)
    for b in original_receipt["output_files"]:
        verify(b)
    index_path = out / "SCENE_AUDIO_INDEX.json"
    rows = read(index_path)["scenes"]
    by_id = {r["case_id"]: r for r in rows}
    parser = IndexParser()
    document = (out / "index.html").read_text(encoding="utf-8")
    parser.feed(document)
    assert len(parser.articles) == 240 and len(parser.audio) == 480
    allowed = {Path(r["streams"][tap]["prepared_pcm16"]["path"]).as_uri() for r in rows for tap in ("O0", "O1")}
    assert {a["src"] for a in parser.audio} == allowed
    assert all("autoplay" not in a and a["preload"] == "none" and "controls" in a for a in parser.audio)
    assert "connect-src 'none'" in document and "http://" not in document and "https://" not in document
    for tap in ("O0", "O1"):
        playlist = [line for line in (out / ("LISTEN_" + tap + ".m3u8")).read_text(encoding="utf-8").splitlines()
                    if line and not line.startswith("#")]
        assert playlist == [r["streams"][tap]["prepared_pcm16"]["path"] for r in rows]
    with (out / "LISTENING_NOTES.csv").open(encoding="utf-8-sig", newline="") as f:
        notes = list(csv.DictReader(f))
    assert len(notes) == 480
    assert all(all(v == "" for k, v in row.items() if k not in ("case_id", "tap")) for row in notes)
    starter = [r for r in rows if r["case_id"] in original_receipt["starter_cases"]]
    starter_categories = {n["category"] for r in starter for n in r["noise_events"]}
    assert "instrumental_music" in starter_categories
    assert {r["family_id"] for r in starter} == {f"F{i:02d}" for i in range(1, 13)}
    assert "S45_08_07" in original_receipt["starter_cases"]
    assert len(parser.times) == sum(len(r["turns"]) for r in rows)
    save(report / "listening/LISTENING_STATIC_QA_V1.json", {
        "status": "PASS_STATIC_AND_AUDIO_BINDINGS", "html_articles": len(parser.articles),
        "mono_players": len(parser.audio), "transcript_timing_rows": len(parser.times),
        "all_playlist_entries_admitted_prepared_mono": True, "all_human_notes_empty": True,
        "starter_music_categories": sorted(starter_categories), "autoplay_absent": True,
        "no_http_or_https_resource_urls": True, "html_csp_blocks_network": True,
        "browser_visual_verification": "NOT_EXECUTED_SECURITY_POLICY_BLOCK",
        "browser_tool_result": "Browser Use rejected local file:/// URL under browser URL policy; no alternate browser/server/CDP workaround attempted.",
        "human_listening_performed": False, "source_receipt": bind(original_receipt_path),
        "html": bind(out / "index.html"), "code": bind(__file__)})

    rir_path = sim / "rir_library/v1/RIR_MANIFEST.json"
    rirs = {r["run_id"]: r for r in read(rir_path)["records"]}
    geometries, features = {}, {}
    for r in rows:
        rid_set = sorted({t["rir_id"] for t in r["turns"]})
        geometry = [{"rir_id": rid, **{k: rirs[rid]["geometry"][k] for k in (
            "speaker_angle_deg_effective", "source_distance_m_effective", "geometry_correction_applied")},
            "manual_half_width_deg": rirs[rid]["geometry"]["angle_label_interval"]["half_width_deg"]} for rid in rid_set]
        geometries[r["case_id"]] = geometry
        feature = {"room:" + r["room_pose"]["room_table"], "pose:" + r["room_pose"]["orientation"],
            "obstructed:" + str(r["room_pose"]["obstructed"]), "actors:" + str(len(r["cast"])),
            "reference_complete:" + str(r["all_speaker_reference_complete"]),
            "overlap_limited:" + str(r["overlap_scoring_limited"])}
        feature |= {"corpus:" + t["dataset"] + "/" + t["quality_partition"] for t in r["turns"]}
        feature |= {"noise:" + n["category"] for n in r["noise_events"]} or {"noise:none"}
        feature |= {"angle:" + str(g["speaker_angle_deg_effective"]) for g in geometry}
        feature |= {"distance_bin:" + str(int(g["source_distance_m_effective"] * 2) / 2) for g in geometry}
        feature |= {"source_level_db:" + str(t["relative_source_db"]) for t in r["turns"]}
        feature |= {"short_reply:" + str(any(t["whole_clip_duration_s"] < 2 for t in r["turns"]))}
        features[r["case_id"]] = feature
    anchors = {"S45_01_01": "Low speech-level control: source relative -6 dB",
        "S45_02_01": "Ordinary sequential-return control", "S45_03_01": "Complete short replies/rapid handoffs",
        "S45_04_01": "Two-talker overlap control", "S45_06_07": "Silent relocation/long-paused return stress",
        "S45_08_07": "Declared historical C105 event-ordering boundary case; no new beam performance used",
        "S45_11_03": "Documented instrumental music with speech, 0 dB SNR control"}
    assert all(cid in by_id for cid in anchors)
    assert min(t["relative_source_db"] for t in by_id["S45_01_01"]["turns"]) == -6
    assert any(n["category"] == "instrumental_music" for n in by_id["S45_11_03"]["noise_events"])
    selected = list(anchors)
    global_counts = Counter(f for cid in selected for f in features[cid])
    decisions = [{"case_id": cid, "reason": reason, "selection_type": "declared_anchor"} for cid, reason in anchors.items()]
    # Fixed round-robin fills each family to four; global rarity and within-family novelty balance metadata.
    for round_number in range(4):
        for family in (f"F{i:02d}" for i in range(1, 13)):
            current = [cid for cid in selected if by_id[cid]["family_id"] == family]
            if len(current) >= 4:
                continue
            seen = set().union(*(features[cid] for cid in current)) if current else set()
            candidates = [r["case_id"] for r in rows if r["family_id"] == family and r["case_id"] not in selected]
            def score(cid):
                return sum((2 if f not in seen else 0) + 1 / (1 + global_counts[f]) for f in features[cid])
            choice = sorted(candidates, key=lambda cid: (-score(cid), cid))[0]
            decisions.append({"case_id": choice, "selection_type": "metadata_greedy",
                "round": round_number + 1, "score": score(choice),
                "new_within_family_features": sorted(features[choice] - seen),
                "reason": "Highest fixed metadata novelty/rarity score; lexical case ID breaks ties"})
            selected.append(choice)
            global_counts.update(features[choice])
    selected = sorted(selected)
    assert len(selected) == 48 and Counter(by_id[cid]["family_id"] for cid in selected) == Counter({f"F{i:02d}": 4 for i in range(1, 13)})
    repeats = [{"case_id": cid, "stratum": stratum, "profile": "P_SCAN6", "additional_attempts": 1,
        "purpose": "Matched same-input same-profile repeat; retain separate hidden state/pass provenance"}
        for cid, stratum in (("S45_01_01", "low_source_level"), ("S45_02_01", "normal_sequential"),
                            ("S45_04_01", "overlap"), ("S45_11_03", "instrumental_music"))]
    scan_rows = [{"case_id": cid, "family": by_id[cid]["family_id"], "room_pose": by_id[cid]["room_pose"],
        "duration_s": by_id[cid]["scene_duration_s"], "input_binding": by_id[cid]["canonical_input"],
        "accepted_historical_capture": by_id[cid]["accepted_capture"], "geometry": geometries[cid],
        "selection_features": sorted(features[cid]), "status": "PREDECLARED_NOT_EXECUTED"} for cid in selected]
    value = {"schema": "s6d_hardware_case_predeclaration_v1", "status": "PREDECLARED_NOT_EXECUTED",
        "created_utc": datetime.now(timezone.utc).isoformat(), "source_index": bind(index_path),
        "accepted_listening_validation": bind(original_receipt_path), "rir_manifest": bind(rir_path),
        "code": bind(__file__), "readme": bind(Path(__file__).with_name("s6d_listening_predeclare_README.md")),
        "algorithm": "Seven transparent anchors, then four family-order rounds until each family has four. Score each candidate as sum across features of 2 if unseen within its family plus 1/(1+global selected feature count). Lexical case ID tie break. Fixed metadata only, no new beam/model results.",
        "prior_outcome_use": "Only S45_08_07 is included explicitly because the V2 contract identifies its prior C105 event-ordering failure. Other anchors are scene design categories.",
        "P_MAIN6": {"unique_scenes": 240, "source_seconds": sum(r["scene_duration_s"] for r in rows),
            "case_ids": sorted(by_id), "cases": [{"case_id": r["case_id"], "duration_s": r["scene_duration_s"],
                "input_binding": r["canonical_input"]} for r in rows]},
        "P_SCAN6": {"unique_scenes": 48, "source_seconds": sum(r["duration_s"] for r in scan_rows),
            "case_ids": selected, "family_counts": dict(Counter(r["family"] for r in scan_rows)), "cases": scan_rows},
        "matched_repeats": repeats, "repeat_seconds": sum(by_id[r["case_id"]]["scene_duration_s"] for r in repeats),
        "minimum_declared_passes_main_scan_repeats": 292, "decisions": decisions,
        "coverage": {"rooms": dict(Counter(by_id[cid]["room_pose"]["room_table"] for cid in selected)),
            "poses": dict(Counter(by_id[cid]["room_pose"]["orientation"] for cid in selected)),
            "corpus_quality": sorted({t["dataset"] + "/" + t["quality_partition"] for cid in selected for t in by_id[cid]["turns"]}),
            "noise_categories": sorted({n["category"] for cid in selected for n in by_id[cid]["noise_events"]})},
        "limits": ["Selection is not capture success, route qualification or safe-output confirmation.",
            "P_MAIN6 and P_SCAN6 are separate physical passes; no fictional same-instant eight-stream evidence.",
            "Qualification, enrollment, two continuous runs and further attempts are outside this table and still count toward480 attempts/6h.",
            "Original scene audio, source levels, timing, RIR v1 and historical exclusions are unchanged.",
            "Geometry is manually labelled acquisition metadata with original five-degree uncertainty, not runtime oracle input."]}
    assert value["P_MAIN6"]["source_seconds"] == 10967
    save(report / "listening/HARDWARE_CASE_PREDECLARATION_V1.json", value)
    print(json.dumps({"status": "PREDECLARED_NOT_EXECUTED", "main": 240, "scan": 48, "repeats": 4,
        "scan_seconds": value["P_SCAN6"]["source_seconds"], "repeat_seconds": value["repeat_seconds"], "coverage": value["coverage"]}), flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--sim", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    main(p.parse_args())
