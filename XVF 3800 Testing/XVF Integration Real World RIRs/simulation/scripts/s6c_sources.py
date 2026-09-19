"""S6C local source/E-C-Q inventory and nested enrollment tiers. README_S6C_SOURCES.md."""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import scipy
from scipy.signal import resample_poly
import soundfile as sf

from s4_sources import active_stats, identity as cv_identity
from s4_h2_analysis import normalize
from s45_sources import qc_reasons

SIM = Path(__file__).resolve().parents[1]
REPO = SIM.parents[2]
DATA = REPO / "Software Validation from Datasets/Raw Datasets (Not formatted)"
S45 = SIM / "staging/s45_sources"
S4 = SIM / "staging/s4_sources"
S45_REPORT = SIM / "reports/S4_5/20260909T031300Z"
CV = DATA / "Common Voice/cv-corpus-26.0-2026-06-12/prepared/en"
HIFI = DATA / "Hi Fi TTS/hi_fi_tts_v0"
RATE = 16000
SEED = "s6c-ecq-source-v1-20260910T123540Z"
SCHEMA = "s6c-source-inventory.v2"
PER_ROLE_LIMIT = 80
TIERS = (5, 15, 30)
CALIBRATION_SECONDS = 30


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def stable(value):
    return digest((SEED + "|" + str(value)).encode("utf-8"))


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def bind(path):
    p = Path(path).resolve()
    before = p.stat()
    h = hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    after = p.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("Source changed during binding: " + str(p))
    return {"path": str(p), "bytes": after.st_size, "sha256": h.hexdigest()}


def verify(binding):
    actual = bind(binding["path"])
    assert actual["sha256"].lower() == binding["sha256"].lower(), binding["path"]
    assert actual["bytes"] == binding["bytes"], binding["path"]
    return actual


def save_new(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write("\n")


def write_csv(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("x", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for row in rows:
            w.writerow({k: "" if v is None else json.dumps(v, separators=(",", ":"))
                        if isinstance(v, (list, dict)) else v for k, v in row.items()})


def text_key(text):
    return "TEXT_" + digest(normalize(text).encode("utf-8"))


def parent_key(row):
    if row["dataset"] == "CMU ARCTIC":
        return "CMU_PROMPT_" + row["sentence_id"]
    if row["dataset"] == "HiFiTTS":
        return row["parent_book"]
    return text_key(row["transcript"])


def native_prompt_key(row):
    """Native prompt identifiers survive transcription edits; text is separate."""
    sentence = str(row.get("sentence_id") or "").strip()
    if not sentence:
        return None
    if row["dataset"] == "Common Voice":
        return "COMMON_VOICE_SENTENCE_" + sentence
    if row["dataset"] == "CMU ARCTIC":
        return "CMU_PROMPT_" + sentence
    return None


def source_path_key(path):
    return str(Path(path).resolve()).casefold()


def locations(run_id, revision="v2"):
    if not re.fullmatch(r"\d{8}T\d{6}Z", run_id):
        raise ValueError("run-id must be YYYYMMDDTHHMMSSZ")
    if not re.fullmatch(r"v(?:[2-9]|[1-9]\d+)", revision):
        raise ValueError("New source revisions start at v2; v1 is preserved outside revision children")
    return (SIM / "reports/S6C" / run_id / "enrollment_inventory" / revision,
            SIM / "staging/s6c" / run_id / "source_inventory" / revision)


def authorities():
    names = {
        "sources": S45 / "SOURCE_AND_SPLIT_MANIFEST.json",
        "pre_qc": S45 / "ROSTER_AND_SELECTION_BEFORE_QC.json",
        "source_qc": S45 / "SOURCE_QC.json",
        "legacy_q": S45 / "LEGACY_DEVELOPMENT_PROBES.json",
        "scene_manifest": S45_REPORT / "SCENE_MANIFEST.json",
        "rights": S45_REPORT / "RIGHTS_AND_SPLITS.json",
        "reference_manifest": SIM / "scene_bank/s45_v2_20260909T031300Z/REFERENCE_SCENE_MANIFEST.json",
        "reference_captures": S45_REPORT / "REFERENCE_CAPTURES.json",
        "s4_sources": S4 / "SOURCE_AND_SPLIT_MANIFEST.json",
        "s4_qc": S4 / "SHORTLIST_QUALITY.json",
        "source_code": Path(__file__),
        "readme": Path(__file__).with_name("README_S6C_SOURCES.md"),
        "activity_code": Path(__file__).with_name("s4_sources.py"),
        "qc_code": Path(__file__).with_name("s45_sources.py"),
        "normalization_code": Path(__file__).with_name("s4_h2_analysis.py"),
        "s6b_index": SIM / "reports/S6B/20260909T230840Z/LOCAL_ARTIFACT_INDEX.json",
    }
    bindings = {k: bind(v) for k, v in names.items()}
    objects = {k: read(v) for k, v in names.items() if v.suffix == ".json"}
    return objects, bindings


def q_manifest(objects):
    scene = objects["scene_manifest"]
    selected = scene["selected_sources"]
    rows = []
    for s in scene["scenes"]:
        for index, seg in enumerate(s["segments"]):
            if seg.get("kind") != "utterance":
                continue
            src = selected[seg["source_id"]]
            assert src["identity"] == seg["speaker_key"]
            rows.append({"occurrence_id": f"{s['case_id']}:segment:{index}",
                "case_id": s["case_id"], "segment_index": index,
                "source_id": seg["source_id"], "identity": src["identity"],
                "dataset": src["dataset"], "role": seg.get("role"),
                "historical_split": s["split"], "transcript": src["transcript"],
                "normalized_text": normalize(src["transcript"]),
                "prompt_group": text_key(src["transcript"]),
                "sentence_id": src.get("sentence_id"),
                "native_prompt_key": native_prompt_key(src),
                "parent_key": parent_key(src), "parent_book": src.get("parent_book"),
                "parent_chapter": src.get("parent_chapter"),
                "source_binding": src["source_binding"],
                "decoded_16k_binding": src["decoded_16k_binding"],
                "decoded_pcm_sha256": src["decoded_pcm_sha256"],
                "source_crop_native_samples": src.get("source_crop_native_samples"),
                "source_crop_samples": seg.get("source_crop_samples"),
                "scene_source_start_sample": seg["source_start_sample"],
                "scene_source_stop_sample": seg["source_stop_sample"],
                "source_aliases": [src["source_id"], str(src["source_binding"]["path"]),
                                   str(src["decoded_16k_binding"]["path"])],
                "quality_disposition": src.get("quality_disposition"),
                "no_evaluator_data_for_runtime": True})
    assert len(rows) == 777 and len(scene["scenes"]) == 240
    assert len({x["source_id"] for x in rows}) == 449
    assert len({x["identity"] for x in rows}) == 43
    assert len({x["occurrence_id"] for x in rows}) == 777
    return rows


def cv_catalogue(people, objects, metadata_bindings):
    """Read installed prepared older-cohort SQLite, never the general/private gallery."""
    db = CV / "state/common_voice_phase3.sqlite3"
    metadata_bindings.append({**bind(db), "scope": "read-only prepared older-cohort metadata index"})
    c = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    evidence = objects["sources"]["metadata_and_rights_evidence"]["cv"]
    historical = Path(evidence["historical_exclusion_binding"]["path"])
    metadata_bindings.append(verify(evidence["historical_exclusion_binding"]))
    excluded = set()
    with historical.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            hit = c.execute("select client_id from candidates where path=?",
                            (Path(row["logical_audio_path"]).name,)).fetchone()
            assert hit is not None
            excluded.add(cv_identity(hit[0]))
    assert len(excluded) == 413
    assert not excluded.intersection(people)
    sql = """select c.*,d.duration_ms,a.audio_sha256,a.readable,a.channels,
             coalesce(u.split,'validated_unassigned') upstream_split
             from candidates c join durations d on d.path=c.path
             join audio_validation a on a.path=c.path left join upstream u on u.path=c.path
             where c.locale='en'"""
    for raw in c.execute(sql):
        rr = dict(raw)
        pid = cv_identity(rr.pop("client_id"))
        if pid not in people:
            continue
        name = rr["path"]
        yield {"source_id": "CV26_" + Path(name).stem, "identity": pid,
            "dataset": "Common Voice", "release": "cv-corpus-26.0-2026-06-12",
            "source_path": str(CV / "clips" / name), "transcript": rr["transcript"],
            "sentence_id": rr["sentence_id"], "parent_book": None, "parent_chapter": None,
            "session_group": None, "session_group_status": "not supplied in prepared metadata",
            "quality_partition": "self_reported_60plus_real_recording",
            "metadata_duration_sec": rr["duration_ms"] / 1000,
            "upstream_split": rr["upstream_split"],
            "source_age_label": rr["source_age_label"],
            "metadata_row_sha256": digest(json.dumps(rr, sort_keys=True, ensure_ascii=False).encode()),
            "metadata_path": str(db), "indexed_source_sha256": rr["audio_sha256"].lower(),
            "native_eligibility": (int(rr["up_votes"]) >= 2 and int(rr["down_votes"]) == 0
                                   and rr["readable"] == 1 and rr["channels"] == 1
                                   and rr["upstream_split"] in ("train", "validated_unassigned")),
            "native_eligibility_rule": "older prepared cohort; >=2 up votes; 0 down votes; readable mono; train/validated_unassigned"}
    c.close()


def native_catalogue(people, objects, metadata_bindings):
    for directory in sorted((DATA / "CMU Arctic").glob("cmu_us_*_arctic")):
        sid = directory.name.split("_")[2]
        pid = "CMU_ARCTIC_" + sid
        if pid not in people:
            continue
        text_path = directory / "etc/txt.done.data"
        metadata_bindings.append(bind(text_path))
        for line_number, line in enumerate(text_path.read_text(encoding="utf-8-sig").splitlines(), 1):
            match = re.fullmatch(r'\(\s*(\S+)\s+"(.*)"\s*\)', line.strip())
            if not match:
                continue
            prompt, transcript = match.groups()
            yield {"source_id": f"CMU_{sid}_{prompt}", "identity": pid, "dataset": "CMU ARCTIC",
                "release": "installed_18_speaker_cmu_arctic", "source_path": str(directory / "wav" / (prompt + ".wav")),
                "transcript": transcript, "sentence_id": prompt, "parent_book": None,
                "parent_chapter": None, "session_group": None,
                "session_group_status": "recording session not supplied in minimal local release",
                "quality_partition": "studio_project_design", "metadata_duration_sec": None,
                "metadata_path": str(text_path), "metadata_line_number": line_number,
                "metadata_row_sha256": digest(line.encode()), "upstream_split": None, "native_eligibility": True}
    for path in sorted(HIFI.glob("*_manifest_*_train.json")):
        sid, _, quality, _ = path.stem.split("_")
        pid = "HIFITTS_" + sid
        if pid not in people:
            continue
        metadata_bindings.append(bind(path))
        for line_number, line in enumerate(path.open(encoding="utf-8-sig"), 1):
            row = json.loads(line)
            relative = Path(row["audio_filepath"])
            assert not relative.is_absolute() and ".." not in relative.parts
            book = "LIBRIVOX_BOOK_" + relative.parts[2]
            yield {"source_id": "HIFI_" + sid + "_" + relative.stem, "identity": pid,
                "dataset": "HiFiTTS", "release": "hi_fi_tts_v0", "source_path": str(HIFI / relative),
                "transcript": row["text_no_preprocessing"], "sentence_id": relative.stem,
                "parent_book": book, "parent_chapter": relative.stem.rsplit("_", 1)[0],
                "session_group": None, "session_group_status": "book/chapter known; recording session not supplied",
                "quality_partition": quality, "metadata_duration_sec": row["duration"],
                "metadata_path": str(path), "metadata_line_number": line_number,
                "metadata_row_sha256": digest(line.rstrip("\r\n").encode()), "upstream_split": "train",
                "native_eligibility": True}
    yield from cv_catalogue(people, objects, metadata_bindings)


def exclusion_reasons(row, guard):
    reasons = []
    if row["source_id"] in guard["q_ids"]: reasons.append("canonical_Q_source_id")
    if source_path_key(row["source_path"]) in guard["q_paths"]: reasons.append("canonical_Q_original_parent_path")
    if text_key(row["transcript"]) in guard["q_text"]: reasons.append("canonical_Q_normalized_text")
    if parent_key(row) in guard["q_parents"]: reasons.append("canonical_Q_parent_or_prompt_group")
    if native_prompt_key(row) and native_prompt_key(row) in guard["q_native_prompts"]:
        reasons.append("canonical_Q_native_sentence_or_prompt_ID")
    if row["source_id"] in guard["old_probe_ids"]: reasons.append("preserved_prior_probe_role")
    if source_path_key(row["source_path"]) in guard["excluded_paths"]: reasons.append("previously_excluded_or_S4_material")
    if row["source_id"] in guard["excluded_ids"]: reasons.append("previously_rejected_source")
    if row.get("indexed_source_sha256") in guard["forbidden_hashes"]: reasons.append("forbidden_original_bytes")
    if not row["native_eligibility"]: reasons.append("native_votes_split_or_integrity_rule")
    if not normalize(row["transcript"]): reasons.append("empty_normalized_text")
    duration = row["metadata_duration_sec"]
    if duration is not None and not .25 <= duration <= 10: reasons.append("outside_inherited_duration_limits")
    return sorted(set(reasons))


def inventory(run_id, revision="v2"):
    report, staging = locations(run_id, revision)
    target = report / "INVENTORY_RECEIPT.json"
    if target.exists():
        result = read(target)
        for b in result["outputs"].values(): verify(b)
        for b in result["authorities"].values(): verify(b)
        print(json.dumps({"status": "VERIFIED_EXISTING_INVENTORY", "receipt": str(target)}), flush=True)
        return
    report.mkdir(parents=True, exist_ok=True); staging.mkdir(parents=True, exist_ok=True)
    obj, bindings = authorities()
    q = q_manifest(obj)
    q_people = {r["identity"] for r in q}
    people = {p["identity"]: p for p in obj["sources"]["people"] if p["identity"] in q_people}
    old = {s["source_id"]: s for s in obj["sources"]["sources"]}
    rights = {p: next((s["rights"] for s in old.values() if s["identity"] == p), None) for p in people}
    assert all(rights.values())
    reference_ids = {x["source_id"] for s in obj["reference_manifest"]["scenes"] for x in s["segments"] if x.get("kind") == "utterance"}
    assert len(reference_ids) == 34 and not obj["reference_captures"]["accepted"]
    optional_sources = obj["reference_manifest"]["selected_sources"]
    forced_e_text = {text_key(optional_sources[x]["transcript"]) for x in reference_ids}
    forced_e_cmu = {parent_key(optional_sources[x]) for x in reference_ids if optional_sources[x]["dataset"] == "CMU ARCTIC"}
    excluded_paths = {source_path_key(s["source_binding"]["path"]) for s in obj["s4_sources"]["sources"]}
    excluded_paths.update(source_path_key(CV / "clips" / s["clip"]) for s in obj["s4_qc"]["rejected"] if s.get("clip"))
    forbidden_hashes = {s["source_binding"]["sha256"] for s in obj["s4_sources"]["sources"]}
    forbidden_hashes.update(obj["sources"]["metadata_and_rights_evidence"]["cv"]["historical_source_hashes"])
    forbidden_hashes.update(s["source_binding"]["sha256"] for s in q)
    rejected = obj["source_qc"]["rejected"]
    forbidden_hashes.update(s["source_binding"]["sha256"] for s in rejected if s.get("source_binding"))
    excluded_paths.update(source_path_key(s["source_binding"]["path"]) for s in rejected if s.get("source_binding"))
    guard = {"q_ids": {s["source_id"] for s in q}, "q_paths": {source_path_key(s["source_binding"]["path"]) for s in q},
        "q_text": {s["prompt_group"] for s in q}, "q_parents": {s["parent_key"] for s in q},
        "q_native_prompts": {s["native_prompt_key"] for s in q if s["native_prompt_key"]},
        "old_probe_ids": {s["source_id"] for s in old.values() if s["usage"] == "probe"},
        "excluded_paths": excluded_paths, "excluded_ids": {s["source_id"] for s in rejected}, "forbidden_hashes": forbidden_hashes}
    book_groups = obj["sources"]["metadata_and_rights_evidence"]["hifi"]["book_groups"]
    e_books = {"LIBRIVOX_BOOK_" + b for b, v in book_groups.items() if v["usage"] == "enrollment_reference"}
    c_books = {}; fallback_people = []
    for pid, p in people.items():
        if p["dataset"] != "HiFiTTS": continue
        sid = pid.removeprefix("HIFITTS_")
        available = ["LIBRIVOX_BOOK_" + b for b, v in book_groups.items() if sid in v["readers"]
                     and "LIBRIVOX_BOOK_" + b not in e_books | guard["q_parents"]]
        c_books[pid] = min(available, key=lambda b: stable(pid + b)) if available else None
        if not available: fallback_people.append(pid)
    forced_e_chapters = {optional_sources[x].get("parent_chapter") for x in reference_ids if optional_sources[x]["dataset"] == "HiFiTTS"}
    metadata = []; reason_counts = collections.Counter(); corpus_counts = collections.Counter(); candidates = []
    catalog_path = staging / "CATALOGUE_SCREEN.jsonl"
    with catalog_path.open("x", encoding="utf-8", newline="\n") as out:
        for index, row in enumerate(native_catalogue(people, obj, metadata), 1):
            corpus_counts[row["dataset"]] += 1
            reasons = exclusion_reasons(row, guard)
            role = None
            if not reasons:
                if row["dataset"] == "HiFiTTS":
                    book = row["parent_book"]
                    if book == c_books[row["identity"]]: role = "C"
                    elif book in e_books:
                        role = "E"
                        if row["identity"] in fallback_people and row["parent_chapter"] not in forced_e_chapters:
                            role = "E" if int(stable("chapter|" + row["parent_chapter"])[0], 16) < 8 else "C"
                    else: reasons.append("outside_frozen_enrollment_calibration_book_pool")
                else:
                    group = native_prompt_key(row) or parent_key(row)
                    force_e = text_key(row["transcript"]) in forced_e_text or group in forced_e_cmu
                    role = "E" if force_e or int(stable("role|" + group)[0], 16) < 8 else "C"
            previous = old.get(row["source_id"])
            row.update({"prompt_group": text_key(row["transcript"]), "parent_key": parent_key(row),
                "native_prompt_key": native_prompt_key(row),
                "historical_identity_split": people[row["identity"]]["split"],
                "historical_source_role": previous["usage"] if previous else None,
                "historical_book_role": book_groups.get(row.get("parent_book", "").removeprefix("LIBRIVOX_BOOK_"), {}).get("usage") if row.get("parent_book") else None,
                "optional_reference_prepared": row["source_id"] in reference_ids,
                "s6c_role": role, "metadata_exclusion_reasons": reasons})
            out.write(json.dumps({k: row[k] for k in ("source_id", "identity", "dataset", "source_path", "prompt_group", "native_prompt_key", "parent_key", "metadata_duration_sec", "s6c_role", "historical_source_role", "metadata_exclusion_reasons")}, ensure_ascii=False) + "\n")
            reason_counts.update(reasons)
            if not reasons: candidates.append(row)
            if index % 25000 == 0: print(json.dumps({"phase": "metadata_inventory", "rows": index, "eligible_before_role_conflicts": len(candidates)}), flush=True)
    # Freeze cross-corpus lexical conflicts before QC. Enrollment precedence is a
    # deterministic design rule, never an audio/model-quality decision.
    text_roles = collections.defaultdict(set)
    native_roles = collections.defaultdict(set)
    for row in candidates: text_roles[row["prompt_group"]].add(row["s6c_role"])
    for row in candidates:
        if row["native_prompt_key"]: native_roles[row["native_prompt_key"]].add(row["s6c_role"])
    conflicts = {g for g, roles in text_roles.items() if len(roles) > 1}
    native_conflicts = {g for g, roles in native_roles.items() if len(roles) > 1}
    pools = collections.defaultdict(list)
    for row in candidates:
        if row["prompt_group"] in conflicts and row["s6c_role"] == "C":
            reason_counts["global_E_C_text_conflict_E_precedence"] += 1
            continue
        if row["native_prompt_key"] in native_conflicts and row["s6c_role"] == "C":
            reason_counts["global_E_C_native_prompt_conflict_E_precedence"] += 1
            continue
        row["selection_key"] = ("0" if row["optional_reference_prepared"] else "1" if row["historical_source_role"] == "enrollment_reference" else "2") + stable(row["source_id"])
        pools[(row["identity"], row["s6c_role"])].append(row)
    chosen = []
    for key in sorted(pools):
        seen_text = set(); seen_source = set(); seen_prompt = set()
        for row in sorted(pools[key], key=lambda x: (x["selection_key"], x["source_path"])):
            if row["prompt_group"] in seen_text or source_path_key(row["source_path"]) in seen_source: continue
            if row["native_prompt_key"] and row["native_prompt_key"] in seen_prompt: continue
            if len(seen_source) >= PER_ROLE_LIMIT: break
            p = Path(row["source_path"])
            if not p.is_file(): reason_counts["native_file_missing"] += 1; continue
            info = sf.info(p)
            if not .25 <= info.duration <= 10 or info.channels != 1:
                reason_counts["native_header_outside_duration_or_mono_limits"] += 1; continue
            row["metadata_duration_sec"] = info.duration
            row["native_header"] = {"sample_rate_hz": info.samplerate, "channels": info.channels, "frames": info.frames}
            row["source_binding"] = bind(p)
            if row.get("indexed_source_sha256"):
                assert row["source_binding"]["sha256"] == row["indexed_source_sha256"], str(p)
            if row["source_binding"]["sha256"] in forbidden_hashes:
                reason_counts["forbidden_original_bytes_after_binding"] += 1; continue
            row["rights"] = rights[row["identity"]]
            seen_text.add(row["prompt_group"]); seen_source.add(source_path_key(row["source_path"])); seen_prompt.add(row["native_prompt_key"]); chosen.append(row)
    e = [r for r in chosen if r["s6c_role"] == "E"]; c = [r for r in chosen if r["s6c_role"] == "C"]
    assert not {r["prompt_group"] for r in e}.intersection(r["prompt_group"] for r in c)
    assert not {r["native_prompt_key"] for r in e if r["native_prompt_key"]}.intersection(r["native_prompt_key"] for r in c if r["native_prompt_key"])
    assert not {source_path_key(r["source_path"]) for r in e}.intersection(source_path_key(r["source_path"]) for r in c)
    q_path = staging / "Q_OCCURRENCES.json"; save_new(q_path, {"schema": SCHEMA, "rows": q})
    freeze_path = staging / "EC_CANDIDATE_FREEZE.json"
    freeze = {"schema": SCHEMA, "revision": revision, "created_utc": utc(), "seed": SEED, "authorities": bindings,
        "metadata_bindings": metadata, "people": list(people.values()), "candidates": chosen,
        "query_manifest": bind(q_path), "forbidden_original_hashes": sorted(forbidden_hashes),
        "forbidden_decoded_hashes": sorted({r["decoded_pcm_sha256"] for r in q} | {r["decoded_pcm_sha256"] for r in obj["s4_sources"]["sources"]}),
        "optional_reference_source_ids": sorted(reference_ids), "optional_reference_captures": 0,
        "hifi_enrollment_books": sorted(e_books), "hifi_calibration_book_by_person": c_books,
        "hifi_same_book_different_chapter_fallback": fallback_people,
        "selection_policy": {"per_person_per_role_candidate_cap": PER_ROLE_LIMIT, "roles_fixed_before_waveform_QC": True,
            "global_text_conflict_rule": "E precedence; conflicting C candidates omitted before waveform QC",
            "eligible_audio": "whole original permitted train/validated_unassigned clips; no source Q or prior probe/rejected/S4 clip substitution",
            "enrollment_tiers_estimated_unique_usable_seconds": list(TIERS), "calibration_target_seconds": CALIBRATION_SECONDS,
            "tier_rule": "minimal nested deterministic whole-clip prefix meeting estimated usable duration; no looping/cropping/time stretch",
            "gallery_condition_note": "E/C are source pools only. Every tested gallery must filter its identity calibration set to the frozen known roster; strangers must be absent from both gallery and identity calibration."}}
    save_new(freeze_path, freeze)
    aliases = {p: {"research_name": "Research Person " + str(i + 1).zfill(3),
                  "corpus_qualified_identity": p, "documented_aliases": people[p].get("known_aliases", []),
                  "global_person_uniqueness": "unresolved across corpora; no contributor lookup or biometric re-identification"}
               for i, p in enumerate(sorted(people))}
    alias_path = report / "RESEARCH_PERSON_ALIASES.json"; save_new(alias_path, aliases)
    plan = {"schema": SCHEMA, "status": "FROZEN_METADATA_PLAN_NO_MODELS_OR_ENROLLMENT_EXECUTED", "created_utc": utc(),
        "authorities": bindings, "native_catalogue_rows_by_corpus": dict(corpus_counts),
        "exclusion_reason_counts_nonexclusive": dict(reason_counts),
        "query_occurrences": 777, "unique_query_source_ids": 449, "query_metadata_identities": 43,
        "optional_references": 34, "optional_reference_captures": 0,
        "candidate_count": len(chosen), "candidate_role_counts": dict(collections.Counter(r["s6c_role"] for r in chosen)),
        "hifi_same_book_calibration_fallback_people": fallback_people,
        "outputs": {"candidate_freeze": bind(freeze_path), "query_manifest": bind(q_path),
                    "catalogue_screen": bind(catalog_path), "person_aliases": bind(alias_path)},
        "limitations": ["Metadata identities are not proven globally unique people.", "Estimated speech is not phonetic truth.",
            "Book/chapter grouping is not a verified recording session. Same-book fallback remains dependent.",
            "This stage prepares source pools only; it does not load a gallery or validate identification.",
            "Existing local license assertions/attributions are preserved; no automatic training or redistribution clearance."]}
    save_new(target, plan)
    print(json.dumps({"status": plan["status"], "candidates": len(chosen), "receipt": str(target)}), flush=True)


def nested_tiers(rows, targets=TIERS):
    result = []
    for target in targets:
        selected = []; usable = 0.0; wall = 0.0
        for row in rows:
            if usable + 1e-9 >= target: break
            selected.append(row["source_id"]); usable += row["quality"]["active_seconds_estimated"]; wall += row["duration_sec"]
        result.append({"requested_usable_seconds": target, "status": "AVAILABLE" if usable + 1e-9 >= target else "UNAVAILABLE",
            "source_ids": selected, "unique_clip_count": len(selected), "actual_estimated_usable_seconds": usable,
            "actual_whole_clip_seconds": wall, "duration_shortfall_seconds": max(0.0, target - usable),
            "selection": "nested whole-clip prefix; unavailable tiers retain only the honest smaller available prefix"})
    for a, b in zip(result, result[1:]): assert b["source_ids"][:len(a["source_ids"])] == a["source_ids"]
    return result


def candidate_row_hash(row):
    return digest(json.dumps(row, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False, allow_nan=False).encode("utf-8"))


def validate_clip_record(record, row, freeze_sha256):
    """A same-freeze checkpoint must still belong to this exact candidate."""
    assert record["status"] in ("ACCEPTED", "REJECTED"), "Unknown checkpoint status"
    assert record["freeze_sha256"] == freeze_sha256
    assert record["candidate_row_sha256"] == candidate_row_hash(row)
    assert record["source_id"] == row["source_id"]
    assert record["identity"] == row["identity"]
    assert record["role"] == row["s6c_role"]
    if record["status"] == "ACCEPTED":
        source = record["source"]
        for key, value in row.items():
            assert key in source and source[key] == value, "Checkpoint frozen-field mismatch: " + key
        assert source["source_binding"] == row["source_binding"]
        assert source["quality"] == record["quality"]
    return record


def preparation_authority(report, frozen, freeze_binding):
    """Keep the completed metadata executor distinct from a reviewed prepare fix."""
    import ast
    admission_path = report / "PREPARATION_CODE_ADMISSION.json"
    if not admission_path.exists():
        for key in ("source_code", "readme"):
            verify(frozen["authorities"][key])
        return None
    admission = read(admission_path)
    assert admission["status"] == "PREPARATION_ONLY_CODE_ADMISSION"
    assert admission["candidate_freeze"] == freeze_binding
    verify(admission["candidate_freeze"])
    for key in ("source_code", "readme"):
        prior = admission["metadata_executor_snapshot"][key]
        assert prior["sha256"] == frozen["authorities"][key]["sha256"]
        assert prior["bytes"] == frozen["authorities"][key]["bytes"]
        verify(prior)
        current = admission["preparation_executor"][key]
        expected_path = Path(__file__) if key == "source_code" else Path(__file__).with_name("README_S6C_SOURCES.md")
        assert Path(current["path"]).resolve() == expected_path.resolve()
        verify(current)
    old_tree = ast.parse(Path(admission["metadata_executor_snapshot"]["source_code"]["path"]).read_text(encoding="utf-8"))
    new_tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    old_functions = {x.name: x for x in old_tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))}
    new_functions = {x.name: x for x in new_tree.body if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert not set(old_functions) - set(new_functions)
    assert set(new_functions) - set(old_functions) == {"candidate_row_hash", "validate_clip_record", "preparation_authority"}
    for name in old_functions:
        if name not in {"prepare", "self_test"}:
            assert ast.dump(old_functions[name], include_attributes=False) == ast.dump(new_functions[name], include_attributes=False), name
    old_other = [x for x in old_tree.body if not isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
    new_other = [x for x in new_tree.body if not isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert [ast.dump(x, include_attributes=False) for x in old_other] == [ast.dump(x, include_attributes=False) for x in new_other]
    return bind(admission_path)


def prepare(run_id, revision="v2"):
    report, staging = locations(run_id, revision)
    inv = read(report / "INVENTORY_RECEIPT.json")
    verify(inv["outputs"]["candidate_freeze"])
    frozen = read(inv["outputs"]["candidate_freeze"]["path"])
    assert frozen["revision"] == revision
    verify(frozen["query_manifest"])
    prepare_code_admission = preparation_authority(report, frozen, inv["outputs"]["candidate_freeze"])
    for key in ("activity_code", "qc_code", "normalization_code"):
        verify(frozen["authorities"][key])
    result_path = report / "ECQ_MANIFEST.json"
    if result_path.exists():
        completion_path = report / "PREPARATION_RECEIPT.json"
        if not completion_path.exists():
            raise RuntimeError("Partial finalization without completion receipt; preserve and inspect this revision")
        completion = read(completion_path)
        assert completion["status"] == "PASS_SOURCE_ACCOUNTING_ONLY"
        assert Path(completion["manifest"]["path"]).resolve() == result_path.resolve()
        verify(completion["manifest"])
        verify(completion["tier_coverage"])
        result = read(result_path)
        verify(result["query_manifest"])
        for row in result["accepted_sources"]:
            verify(row["source_binding"]); verify(row["decoded_16k_binding"])
        print(json.dumps({"status": "VERIFIED_EXISTING_PREPARATION", "manifest": str(result_path)}), flush=True)
        return
    if shutil.disk_usage(staging).free < 50 * 1024**3:
        raise RuntimeError("C: metadata volume is below its 50 GiB preservation floor")
    payload = Path("G:/Just_Peachy_S6C") / run_id / "source_inventory" / revision
    payload.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(payload).free < 77 * 1024**3:
        raise RuntimeError("Need at least 77 GiB free before bounded G: source preparation; 75 GiB floor preserved")
    accepted = []; rejected = []; deferred = []; totals = collections.Counter(); seen_hash = {}; seen_pcm = {}
    forbidden_hashes = set(frozen["forbidden_original_hashes"]); forbidden_pcm = set(frozen["forbidden_decoded_hashes"])
    checkpoints = staging / "clip_receipts"; checkpoints.mkdir(exist_ok=True)
    decoded = payload / "decoded_16k"; decoded.mkdir(exist_ok=True)
    for index, row in enumerate(frozen["candidates"], 1):
        key = (row["identity"], row["s6c_role"])
        if totals[key] + 1e-9 >= (max(TIERS) if key[1] == "E" else CALIBRATION_SECONDS):
            deferred.append(row["source_id"]); continue
        receipt_path = checkpoints / (row["source_id"] + ".json")
        if receipt_path.exists():
            record = read(receipt_path)
            validate_clip_record(record, row, inv["outputs"]["candidate_freeze"]["sha256"])
            verify(row["source_binding"])
            if record["status"] == "ACCEPTED": verify(record["source"]["decoded_16k_binding"])
        else:
            sb = verify(row["source_binding"])
            x, rate = sf.read(row["source_path"], dtype="float64", always_2d=True)
            if x.shape[1] != 1 or not len(x) or not np.isfinite(x).all():
                raise RuntimeError("Frozen source ceased to be finite mono")
            d = math.gcd(int(rate), RATE)
            y = resample_poly(x[:, 0], RATE // d, int(rate) // d, window=("kaiser", 5.0), padtype="constant").astype("float32")
            pcm_hash = digest(y.astype("<f4").tobytes()); quality = active_stats(y)
            hard, review = qc_reasons(quality, len(y) / RATE)
            if sb["sha256"] in forbidden_hashes: hard.append("Q_or_excluded_original_hash_alias")
            if pcm_hash in forbidden_pcm: hard.append("Q_or_excluded_decoded_PCM_alias")
            if sb["sha256"] in seen_hash: hard.append("duplicate_prepared_original_bytes")
            if pcm_hash in seen_pcm: hard.append("duplicate_prepared_decoded_PCM")
            record = {"freeze_sha256": inv["outputs"]["candidate_freeze"]["sha256"],
                "candidate_row_sha256": candidate_row_hash(row),
                "status": "REJECTED" if hard else "ACCEPTED", "source_id": row["source_id"],
                "identity": row["identity"], "role": row["s6c_role"], "reasons": hard, "quality": quality}
            if not hard:
                output = decoded / (row["source_id"] + "_" + pcm_hash[:12] + ".wav")
                if output.exists():
                    prior, prior_rate = sf.read(output, dtype="float32")
                    assert prior_rate == RATE and np.array_equal(prior, y)
                else:
                    if shutil.disk_usage(payload).free - y.nbytes - 4096 < 75 * 1024**3:
                        raise RuntimeError("G: 75 GiB preservation floor reached")
                    sf.write(output, y, RATE, subtype="FLOAT")
                record["source"] = {**row, "source_binding": sb, "decoded_16k_binding": bind(output),
                    "decoded_pcm_sha256": pcm_hash, "sample_rate_hz": RATE, "samples": len(y), "duration_sec": len(y) / RATE,
                    "native_sample_rate_hz": int(rate), "native_samples": len(x), "source_crop_native_samples": [0, len(x)],
                    "whole_clip": True, "source_gain_applied": 1.0, "quality": quality,
                    "quality_disposition": "REVIEW" if review else "PASS", "quality_review_flags": review,
                    "domain": "clean-source reference domain; NOT XVF processed; inherited corpus conditions",
                    "processing": "mono16k float32 antialiased resample; no denoise, trim, concat, gain, loop, stretch or model call"}
            validate_clip_record(record, row, inv["outputs"]["candidate_freeze"]["sha256"])
            save_new(receipt_path, record)
        if record["status"] == "ACCEPTED":
            source = record["source"]
            assert source["source_binding"]["sha256"] not in seen_hash
            assert source["decoded_pcm_sha256"] not in seen_pcm
            seen_hash[source["source_binding"]["sha256"]] = source["source_id"]
            seen_pcm[source["decoded_pcm_sha256"]] = source["source_id"]
            accepted.append({**source, "preparation_clip_receipt": bind(receipt_path)})
            totals[key] += source["quality"]["active_seconds_estimated"]
        else: rejected.append({**{k: v for k, v in record.items() if k != "quality"}, "quality": record["quality"]})
        if (len(accepted) + len(rejected)) % 20 == 0:
            print(json.dumps({"phase": "source_QC_no_models", "candidate_position": index, "accepted": len(accepted), "rejected": len(rejected)}), flush=True)
    coverage = []
    for person in frozen["people"]:
        pid = person["identity"]
        erows = [r for r in accepted if r["identity"] == pid and r["s6c_role"] == "E"]
        crows = [r for r in accepted if r["identity"] == pid and r["s6c_role"] == "C"]
        tiers = nested_tiers(erows)
        csec = sum(r["quality"]["active_seconds_estimated"] for r in crows)
        for tier in tiers:
            coverage.append({"identity": pid, "dataset": person["dataset"], "historical_split": person["split"], **tier,
                "calibration_status": "TARGET_AVAILABLE" if csec >= CALIBRATION_SECONDS - 1e-9 else "SMALLER_AVAILABLE" if crows else "UNAVAILABLE",
                "calibration_source_ids": [r["source_id"] for r in crows], "calibration_unique_clips": len(crows),
                "calibration_estimated_usable_seconds": csec,
                "same_book_E_C_fallback": pid in frozen["hifi_same_book_different_chapter_fallback"],
                "canonical_Q_kept_regardless_of_enrollment": True})
    verify(frozen["query_manifest"])
    q = read(frozen["query_manifest"]["path"])["rows"]
    sets = {role: [r for r in accepted if r["s6c_role"] == role] for role in ("E", "C")}
    intersections = {}
    for label, fn in (("source_ids", lambda r: r["source_id"]), ("original_sha256", lambda r: r["source_binding"]["sha256"]),
                      ("decoded_pcm_sha256", lambda r: r["decoded_pcm_sha256"]), ("normalized_text", lambda r: text_key(r["transcript"])),
                      ("native_prompt_keys", native_prompt_key)):
        ss = {role: {fn(r) for r in rr if fn(r) is not None} for role, rr in {**sets, "Q": q}.items()}
        for a, b in (("E", "C"), ("E", "Q"), ("C", "Q")):
            shared = sorted(ss[a] & ss[b]); assert not shared, (label, a, b, shared)
            intersections[f"{a}_{b}_{label}"] = shared
    qbooks = {r["parent_book"] for r in q if r["parent_book"]}
    assert not {r["parent_book"] for r in accepted if r["parent_book"]} & qbooks
    e_chapters = {r["parent_chapter"] for r in sets["E"] if r["parent_chapter"]}
    c_chapters = {r["parent_chapter"] for r in sets["C"] if r["parent_chapter"]}
    assert not e_chapters & c_chapters
    manifest = {"schema": SCHEMA, "status": "SOURCE_PREPARATION_COMPLETE_WITH_EXPLICIT_COVERAGE_LIMITS", "created_utc": utc(),
        "preparation_code_admission": prepare_code_admission,
        "inventory_receipt": bind(report / "INVENTORY_RECEIPT.json"), "candidate_freeze": inv["outputs"]["candidate_freeze"],
        "query_manifest": frozen["query_manifest"], "accepted_sources": accepted, "rejected_candidates": rejected,
        "unneeded_frozen_candidates_not_decoded": deferred, "coverage": coverage,
        "leakage_audit": {"exact_intersections": intersections, "Q_parent_books_shared": [], "E_C_parent_chapters_shared": [],
            "same_book_fallback_people": frozen["hifi_same_book_different_chapter_fallback"],
            "known_parent_path_prompt_and_exact_bytes_checked": True,
            "unknown_crop_or_codec_alias_exhaustive_acoustic_detection": False,
            "alias_limit": "Canonical original parents and prepared aliases, exact native/decoded bytes, prompt/text groups and known book/chapter lineage are excluded. No exhaustive search for undocumented transformed recordings across unrelated corpus files or unique-human re-identification."},
        "resampler": {"scipy_version": scipy.__version__, "numpy_version": np.__version__, "soundfile_version": sf.__version__,
                      "implementation": "scipy.signal.resample_poly", "window": ["kaiser", 5.0], "padtype": "constant", "rate_hz": RATE, "output_dtype": "float32", "gain": 1.0},
        "execution": {"model_calls": 0, "downloads": 0, "hardware_passes": 0, "private_gallery_access": False,
                      "gallery_loading_or_identification_executed": False, "calibration_fit_executed": False},
        "reference_domains": "Original clean-source templates only; no XVF-processed template claim.",
        "unique_evidence": "Distinct native whole files with no original/decoded byte or within-role per-person text duplicate. These are distinct clips, not proven statistically independent sessions.",
        "C_condition_guard": "Before fitting a gallery condition, filter C to that frozen known roster; the tested strangers must be absent from both its E templates and identity-calibration set."}
    save_new(result_path, manifest)
    write_csv(report / "ENROLLMENT_TIER_COVERAGE.csv", coverage)
    summary = {"schema": SCHEMA, "status": "PASS_SOURCE_ACCOUNTING_ONLY", "created_utc": utc(),
        "manifest": bind(result_path), "tier_coverage": bind(report / "ENROLLMENT_TIER_COVERAGE.csv"),
        "accepted_clips": len(accepted), "rejected_clips": len(rejected), "deferred_unneeded_candidates": len(deferred),
        "role_counts": dict(collections.Counter(r["s6c_role"] for r in accepted)),
        "tier_available_people": {str(t): sum(r["requested_usable_seconds"] == t and r["status"] == "AVAILABLE" for r in coverage) for t in TIERS},
        "calibration_people_any": len({r["identity"] for r in accepted if r["s6c_role"] == "C"}),
        "Q_occurrences_preserved": len(q), "Q_source_ids": len({r["source_id"] for r in q}), "Q_people": len({r["identity"] for r in q}),
        "new_decoded_bytes": sum(r["decoded_16k_binding"]["bytes"] for r in accepted),
        "model_calls": 0, "hardware_passes": 0, "no_identification_result_claim": True}
    save_new(report / "PREPARATION_RECEIPT.json", summary)
    print(json.dumps(summary), flush=True)


def self_test():
    def item(i, secs): return {"source_id": i, "duration_sec": secs + 1, "quality": {"active_seconds_estimated": secs}}
    examples = nested_tiers([item("a", 4), item("b", 3), item("c", 10), item("d", 14)])
    assert [x["source_ids"] for x in examples] == [["a", "b"], ["a", "b", "c"], ["a", "b", "c", "d"]]
    assert all(x["status"] == "AVAILABLE" for x in examples)
    tiny = nested_tiers([item("short", 4)])
    assert all(x["status"] == "UNAVAILABLE" and x["actual_estimated_usable_seconds"] == 4 for x in tiny)
    assert all(x["status"] == "UNAVAILABLE" and not x["source_ids"] for x in nested_tiers([]))
    assert text_key("Hello, WORLD!") == text_key("hello world")
    row = {"source_id": "alias", "dataset": "CMU ARCTIC", "sentence_id": "p01", "source_path": "test_alias.wav", "transcript": "Held query words.", "native_eligibility": True, "metadata_duration_sec": 2}
    guard = {"q_ids": set(), "q_paths": set(), "q_text": {text_key("held query words")}, "q_parents": {"CMU_PROMPT_p01"}, "q_native_prompts": set(), "old_probe_ids": set(), "excluded_paths": set(), "excluded_ids": set(), "forbidden_hashes": set()}
    assert set(exclusion_reasons(row, guard)) == {"canonical_Q_normalized_text", "canonical_Q_parent_or_prompt_group"}
    changed = {**row, "transcript": "Different crop transcript", "gain": 4, "crop": [1600, 32000]}
    assert "canonical_Q_parent_or_prompt_group" in exclusion_reasons(changed, guard)
    cv = {**row, "dataset": "Common Voice", "sentence_id": "native-prompt-7", "transcript": "Edited metadata words"}
    guard["q_native_prompts"] = {"COMMON_VOICE_SENTENCE_native-prompt-7"}
    assert "canonical_Q_native_sentence_or_prompt_ID" in exclusion_reasons(cv, guard)
    assert native_prompt_key({**cv, "sentence_id": ""}) is None
    assert cv_identity("same contributor") == cv_identity("same contributor")
    frozen_row = {"source_id": "source_a", "identity": "person_a", "s6c_role": "E",
                  "source_binding": {"path": "a.wav", "bytes": 4, "sha256": "a"}}
    record = {"status": "ACCEPTED", "freeze_sha256": "same_freeze", "candidate_row_sha256": candidate_row_hash(frozen_row),
              "source_id": "source_a", "identity": "person_a", "role": "E", "quality": {},
              "source": {**frozen_row, "quality": {}}}
    validate_clip_record(record, frozen_row, "same_freeze")
    for change in ("source_id", "identity", "s6c_role", "source_binding"):
        swapped = json.loads(json.dumps(record))
        swapped["source"][change] = "different" if change != "source_binding" else {"path": "other.wav", "bytes": 4, "sha256": "b"}
        try: validate_clip_record(swapped, frozen_row, "same_freeze")
        except AssertionError: pass
        else: raise AssertionError("Same-freeze swapped accepted source payload admitted: " + change)
    bad_status = {**record, "status": "PENDING"}
    try: validate_clip_record(bad_status, frozen_row, "same_freeze")
    except AssertionError: pass
    else: raise AssertionError("Unfinished checkpoint status admitted")
    other_row = {**frozen_row, "source_id": "source_b", "identity": "person_b", "s6c_role": "C"}
    try: validate_clip_record(record, other_row, "same_freeze")
    except AssertionError: pass
    else: raise AssertionError("Same-freeze checkpoint counted under another candidate quota")
    for bad in ("../bad", "2026", "20260910T123540Z/else"):
        try: locations(bad)
        except ValueError: pass
        else: raise AssertionError("Unsafe run id accepted")
    test_root = locations("20260910T123540Z")[1] / "checks"
    test_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=test_root) as directory:
        fixture = Path(directory) / "query_manifest.json"
        fixture.write_text('{"rows": []}', encoding="utf-8")
        original = bind(fixture); verify(original)
        fixture.write_text('{"rows": [1]}', encoding="utf-8")
        try: verify(original)
        except AssertionError: pass
        else: raise AssertionError("Changed query/completion artifact binding accepted")
    print(json.dumps({"status": "PASS", "checks": "nested whole-clip prefixes, unavailable tiers, text/known-parent/native-prompt aliases, exact artifact mutation rejection, full frozen-row checkpoint identity and same-freeze swapped-payload rejection, allowed checkpoint status, deterministic pseudonyms, namespace guard", "model_calls": 0}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("inventory", "prepare", "self-test"))
    p.add_argument("--run-id", default="20260910T123540Z")
    p.add_argument("--revision", default="v2", help="isolated source inventory revision, v2 or later")
    args = p.parse_args()
    if args.command == "self-test": self_test()
    elif args.command == "inventory": inventory(args.run_id, args.revision)
    else: prepare(args.run_id, args.revision)


if __name__ == "__main__":
    main()
