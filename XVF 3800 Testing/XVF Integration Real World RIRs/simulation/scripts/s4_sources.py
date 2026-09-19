"""Bounded, read-only Common Voice source adapter for the S4 development bank."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import numpy as np
import scipy
from scipy.signal import resample_poly
import soundfile as sf

SIM = Path(__file__).resolve().parents[1]
DATA = SIM.parents[2] / "Software Validation from Datasets"
RELEASE = "cv-corpus-26.0-2026-06-12"
EN = DATA / "Raw Datasets (Not formatted)" / "Common Voice" / RELEASE / "prepared" / "en"
OUT = SIM / "staging" / "s4_sources"
RATE = 16000
SEED = "s4-source-v1"


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(x):
    return hashlib.sha256(x).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def bind(path):
    p = Path(path)
    s = p.stat()
    return {"path": str(p), "sha256": file_hash(p), "bytes": s.st_size, "mtime_ns": s.st_mtime_ns}


def save(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_suffix(p.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temp.replace(p)


def identity(cid):
    # Same contributor maps to the same pseudonym across release and locale.
    return "CV_" + digest(("common-voice-contributor|" + cid).encode())[:20]


def row_hash(row):
    return digest(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def active_stats(audio, rate=RATE):
    """20 ms non-overlap RMS, >= max(-50 dBFS, frame p95 -25 dB)."""
    x = np.asarray(audio, dtype=np.float64)
    n = int(round(rate * .02))
    frames = x[:len(x) // n * n].reshape(-1, n)
    if not len(frames) or not np.isfinite(x).all():
        raise ValueError("Empty or non-finite source")
    rms = np.sqrt(np.mean(frames * frames, axis=1))
    p95 = float(np.percentile(rms, 95))
    threshold = max(10 ** (-50 / 20), p95 * 10 ** (-25 / 20))
    active = rms >= threshold
    active_rms = float(np.sqrt(np.mean(frames[active] ** 2))) if active.any() else 0.
    peak = float(np.max(np.abs(x)))
    p10 = float(np.percentile(rms, 10))
    active_ranges = []
    changes = np.diff(np.r_[False, active, False].astype(np.int8))
    for a, b in zip(np.flatnonzero(changes == 1), np.flatnonzero(changes == -1)):
        active_ranges.append([int(a * n), int(b * n)])
    rails = np.abs(x) >= .999
    transitions = np.diff(np.r_[False, rails, False].astype(np.int8))
    runs = np.flatnonzero(transitions == -1) - np.flatnonzero(transitions == 1)
    return {
        "estimator": "frame_rms_20ms_p95_minus25dB_absolute_floor_minus50dBFS_v1",
        "frame_samples": n, "threshold_rms": threshold,
        "active_rms": active_rms,
        "active_rms_dbfs": float(20 * np.log10(max(active_rms, 1e-15))),
        "active_seconds_estimated": float(active.sum() * n / rate),
        "active_fraction_estimated": float(active.mean()),
        "active_ranges_samples_estimated": active_ranges,
        "peak": peak, "dc_offset": float(np.mean(x)),
        "rms_frame_p10": p10, "rms_frame_p95": p95,
        "frame_p95_to_p10_db": float(20 * np.log10(max(p95, 1e-15) / max(p10, 1e-15))),
        "samples_abs_ge_0_999": int(rails.sum()),
        "max_run_abs_ge_0_999": int(runs.max()) if len(runs) else 0,
        "crest_factor_db": float(20 * np.log10(max(peak, 1e-15) / max(active_rms, 1e-15))),
        "mask_scope": "Estimated numerical source activity for preparation/scoring only; not phonetic boundaries or H2 input metadata",
    }


def quality_reasons(stats, seconds):
    reasons = []
    if not 2.7 <= seconds <= 6.6:
        reasons.append("duration_outside_declared_shortlist_range")
    if stats["active_seconds_estimated"] < 1.2:
        reasons.append("insufficient_estimated_active_speech")
    if stats["active_rms_dbfs"] < -36:
        reasons.append("would_require_excessive_amplification")
    if stats["peak"] > 1 or stats["max_run_abs_ge_0_999"] > 2 or stats["samples_abs_ge_0_999"] > 3:
        reasons.append("source_rail_or_overrange")
    if abs(stats["dc_offset"]) > .01:
        reasons.append("large_dc_offset")
    if stats["frame_p95_to_p10_db"] < 12:
        reasons.append("weak_pause_to_speech_contrast_possible_noise")
    return reasons


def connect():
    p = EN / "state/common_voice_phase3.sqlite3"
    c = sqlite3.connect(p.as_uri() + "?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "SOURCE_AND_SPLIT_MANIFEST.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        for s in old["sources"]:
            if file_hash(s["source_binding"]["path"]) != s["source_binding"]["sha256"]:
                raise RuntimeError("Frozen source bytes changed")
            if file_hash(s["decoded_16k_binding"]["path"]) != s["decoded_16k_binding"]["sha256"]:
                raise RuntimeError("Frozen decoded bytes changed")
        print(json.dumps({"status": "REUSED_VERIFIED", "manifest": str(manifest_path), "counts": old["counts"]}))
        return
    c = connect()
    source_selection = DATA / "Evaluation Tool/benchmarks/speaker_breadth/commonvoice_60plus_v1/source_selection.tsv"
    old_ids, old_hashes = set(), set()
    with source_selection.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            path = Path(r["logical_audio_path"]).name
            cid = c.execute("select client_id from candidates where path=?", (path,)).fetchone()
            if cid is None:
                raise RuntimeError("Could not resolve historical Common Voice split identity")
            old_ids.add(cid[0])
            old_hashes.add(r["audio_sha256"].lower())
    metadata_sql = """select c.*, d.duration_ms, coalesce(u.split,'validated_unassigned') as upstream_split,
        a.audio_sha256 as prior_audio_sha256, a.readable, a.channels as prior_channels
        from candidates c join durations d on d.path=c.path
        left join upstream u on u.path=c.path join audio_validation a on a.path=c.path
        where c.locale='en' and cast(c.down_votes as integer)=0 and cast(c.up_votes as integer)>=2
        and d.duration_ms between 2800 and 6500 and a.readable=1 and a.channels=1"""
    grouped = {}
    for row in c.execute(metadata_sql):
        r = dict(row)
        if r["client_id"] not in old_ids and r["upstream_split"] in ("train", "validated_unassigned") and r["transcript"].strip():
            grouped.setdefault(r["client_id"], []).append(r)
    eligible = sorted((cid for cid, rows in grouped.items() if len(rows) >= 5), key=lambda cid: digest((SEED + "|" + cid).encode()))
    if len(eligible) < 15:
        raise RuntimeError("Too few clean metadata candidates outside historical splits")
    ledger_path = OUT / "SPLIT_FREEZE_BEFORE_AUDIO_QC.json"
    reserve_ids = eligible[:3]
    dev_candidate_ids = eligible[3:15]
    ledger = {
        "schema": "s4_source_split_freeze_v1", "frozen_utc": utc(), "seed": SEED,
        "reason": "Assign whole stable contributor IDs before shortlist waveform QC and before any S4 model/device results",
        "historical_protocol_binding": bind(source_selection), "historical_contributors_excluded": len(old_ids),
        "eligible_new_contributors": len(eligible),
        "reserve_ids": [identity(cid) for cid in reserve_ids],
        "development_candidate_priority": [identity(cid) for cid in dev_candidate_ids],
        "other_contributors": "Unassigned to S4; no claim of unseen model pretraining",
        "identity_namespace": "SHA256(common-voice-contributor|client_id) first20 hex; release/locale do not create new identities",
    }
    if ledger_path.exists():
        prior = json.loads(ledger_path.read_text())
        for key in ("reserve_ids", "development_candidate_priority", "historical_protocol_binding"):
            if prior[key] != ledger[key]:
                raise RuntimeError("Frozen selection changed; use a new version")
        ledger = prior
    else:
        save(ledger_path, ledger)
    sources, rejected, people = [], [], []
    seen_bytes = set(old_hashes)
    seen_decoded = set()
    decoded_count = 0
    for role, ids in (("downstream_reserve", reserve_ids), ("development", dev_candidate_ids)):
        for cid in ids:
            if role == "development" and sum(p["split"] == "development" for p in people) >= 6:
                break
            rows = sorted(grouped[cid], key=lambda r: digest((SEED + "|" + r["path"]).encode()))
            accepted = []
            used_texts = set()
            target = 3 if role == "downstream_reserve" else 5
            for r in rows[:8]:
                if len(accepted) >= target:
                    break
                norm = " ".join(r["transcript"].lower().split())
                if norm in used_texts:
                    continue
                p = EN / "clips" / r["path"]
                if not p.is_file():
                    rejected.append({"clip": r["path"], "identity": identity(cid), "reasons": ["not_materialized"]})
                    continue
                source_bind = bind(p)
                if source_bind["sha256"] != r["prior_audio_sha256"].lower():
                    raise RuntimeError("Consumed source byte hash differs from existing audio-validation index")
                if source_bind["sha256"] in seen_bytes:
                    rejected.append({"clip": r["path"], "identity": identity(cid), "reasons": ["known_source_byte_duplicate"]})
                    continue
                x, sr = sf.read(p, dtype="float64", always_2d=True)
                decoded_count += 1
                if x.shape[1] != 1 or not np.isfinite(x).all():
                    rejected.append({"clip": r["path"], "identity": identity(cid), "reasons": ["invalid_or_multichannel"]})
                    continue
                g = math.gcd(int(sr), RATE)
                native_hash = digest(x.astype("<f8").tobytes())
                y = resample_poly(x[:, 0], RATE // g, int(sr) // g, window=("kaiser", 5.0), padtype="constant").astype("float32")
                decoded_hash = digest(y.astype("<f4").tobytes())
                stats = active_stats(y)
                reasons = quality_reasons(stats, len(y) / RATE)
                if decoded_hash in seen_decoded:
                    reasons.append("decoded_pcm_duplicate")
                if reasons:
                    rejected.append({"clip": r["path"], "identity": identity(cid), "reasons": reasons, "quality": stats})
                    continue
                source_id = r["path"].removesuffix(".mp3")
                dest = OUT / "decoded_16k" / (source_id + ".wav")
                dest.parent.mkdir(parents=True, exist_ok=True)
                sf.write(dest, y, RATE, subtype="FLOAT")
                source = {
                    "source_id": source_id, "identity": identity(cid), "split": role,
                    "usage": "probe" if role == "development" else "reserved_not_used_in_S4",
                    "dataset": "Common Voice", "release": RELEASE, "locale": r["locale"],
                    "upstream_split": r["upstream_split"], "source_binding": source_bind,
                    "native_decoded": {"sample_rate_hz": int(sr), "channels": x.shape[1], "samples": x.shape[0], "duration_sec": len(x) / sr, "float64_pcm_sha256": native_hash},
                    "decoded_16k_binding": bind(dest), "decoded_pcm_sha256": decoded_hash,
                    "sample_rate_hz": RATE, "samples": len(y), "duration_sec": len(y) / RATE,
                    "transcript": r["transcript"], "transcript_sha256": digest(r["transcript"].encode()),
                    "sentence_id": r["sentence_id"], "whole_clip": True,
                    "metadata_row_sha256": row_hash({k: v for k, v in r.items() if k != "client_id"}),
                    "metadata_identity_sha256": digest(cid.encode()),
                    "votes": {"up": int(r["up_votes"]), "down": int(r["down_votes"])},
                    "self_reported_accent": r["accents"] or None,
                    "self_reported_age_category": r["source_age_label"] or None,
                    "quality": stats, "source_gain_applied": 1.0,
                    "rights": "CC0; local supplied release datasheet, no speaker identity determination",
                    "quality_disposition": "NUMERICAL_SHORTLIST_ACCEPTED_WITH_SOURCE_DOMAIN_LIMITATIONS",
                }
                accepted.append(source)
                used_texts.add(norm)
                seen_bytes.add(source_bind["sha256"])
                seen_decoded.add(decoded_hash)
            minimum = 2 if role == "downstream_reserve" else 4
            if len(accepted) < minimum:
                rejected.append({"identity": identity(cid), "reasons": ["too_few_qualified_distinct_clips"], "qualified_count": len(accepted)})
                continue
            if role == "development":
                accepted[-1]["usage"] = "enrollment_candidate_not_S4_probe"
            people.append({"identity": identity(cid), "split": role, "source_ids": [s["source_id"] for s in accepted], "metadata_supported_not_biometric_identity": True})
            sources.extend(accepted)
            print(json.dumps({"identity": identity(cid), "role": role, "accepted": len(accepted), "decoded_count": decoded_count}), flush=True)
    c.close()
    materialization = json.loads((EN / "state/materialization_complete.json").read_text())
    readme_binding = bind(EN / "metadata/original/README.md")
    if readme_binding["sha256"].lower() != materialization["metadata_file_hashes"]["README.md"].lower():
        raise RuntimeError("Release license datasheet differs from materialization receipt")
    counts = dict(Counter(p["split"] for p in people))
    counts.update({"selected_clips": len(sources), "decoded_shortlist_clips": decoded_count,
                   "development_probe_clips": sum(s["usage"] == "probe" for s in sources),
                   "enrollment_candidate_clips": sum(s["usage"] == "enrollment_candidate_not_S4_probe" for s in sources),
                   "selected_seconds": sum(s["duration_sec"] for s in sources)})
    if counts.get("development") != 6 or counts.get("downstream_reserve") != 3:
        raise RuntimeError("Bounded source cohort incomplete; inspect shortlist before changing selection")
    manifest = {
        "schema": "s4_sources_v1", "created_utc": utc(), "dataset_root": str(DATA),
        "release": RELEASE, "locale": "en", "common_voice_root": str(EN),
        "license_binding": readme_binding, "materialization_binding": bind(EN / "state/materialization_complete.json"),
        "native_metadata_fields": {"identity": "client_id", "path": "path", "transcript": "sentence", "locale": "locale", "accent": "accents"},
        "adapter_index_mapping": {"transcript": "candidates.transcript copied from native sentence", "identity": "candidates.client_id", "upstream_split": "upstream.split", "duration": "durations.duration_ms"},
        "canonical_native_metadata_path": str(EN / "metadata/original/validated.tsv"),
        "canonical_native_metadata_sha256_from_existing_receipt": materialization["metadata_file_hashes"]["validated.tsv"].lower(),
        "index_binding_scope": "Read-only existing SQLite candidate/audio-validation index; no full index regeneration or whole-corpus hash. Selected source bytes rehashed and compared with indexed prior hashes.",
        "split_freeze_binding": bind(ledger_path), "historical_identities_excluded": len(old_ids),
        "counts": counts, "people": people, "sources": sources,
        "resampler": {"implementation": "scipy.signal.resample_poly", "scipy_version": scipy.__version__, "window": ["kaiser", 5.0], "padtype": "constant", "output_rate": RATE, "gain": 1.0},
        "source_preparation_proposal": {"frozen_by_this_adapter": False, "estimator": "frame_rms_20ms_p95_minus25dB_absolute_floor_minus50dBFS_v1", "target_active_rms_dbfs": -24, "maximum_boost_db": 12, "source_peak_cap": .5, "gain_formula": "min(10**(-24/20)/active_rms,0.5/peak); reject if uncapped RMS target requires boost >12dB; coordinator freezes on calibration sources", "single_preconvolution_gain_only": True},
        "limitations": [
            "This is locally materialized self-reported older-age English prompted/read speech, not population-balanced conversational speech.",
            "Metadata votes and waveform/activity checks do not independently certify exact transcript alignment, absence of other voices, or acoustic dryness; no listening/biometric classifier claim is made.",
            "Lossy MP3, source microphones, native reverberation and recording conditions are inherited and not independently calibrated. No denoising/EQ is applied.",
            "Contributor IDs are working metadata identities. Multiple accounts or cross-corpus humans may collide; no identity determination is attempted.",
            "New S4 reserve is disjoint from the consumed historical 413-identity CV protocol and S4 development; pretrained model exposure remains unknown.",
            "Only selected bytes and decoded PCM are deduplicated; no whole-corpus acoustic duplicate audit or corpus-wide release/locale inventory is claimed.",
        ],
    }
    save(OUT / "SHORTLIST_QUALITY.json", {"decoded_count": decoded_count, "rejected": rejected, "accepted_sources": [s["source_id"] for s in sources]})
    save(manifest_path, manifest)
    print(json.dumps({"status": "COMPLETE", "manifest": str(manifest_path), "counts": counts}))


def validate_structure(m):
    dev_ids = {s["identity"] for s in m["sources"] if s["split"] == "development"}
    reserve_ids = {s["identity"] for s in m["sources"] if s["split"] == "downstream_reserve"}
    assert not dev_ids & reserve_ids, "Contributor crossed development and reserve"
    for field in ("source_binding", "decoded_16k_binding"):
        hashes = [s[field]["sha256"] for s in m["sources"]]
        assert len(set(hashes)) == len(hashes), "Duplicate source or decoded bytes"
    for person in m["people"]:
        clips = [s for s in m["sources"] if s["identity"] == person["identity"]]
        assert len({s["transcript_sha256"] for s in clips}) == len(clips), "Repeated within-person transcript"
        if person["split"] == "development":
            assert sum(s["usage"] == "probe" for s in clips) >= 3
            assert sum(s["usage"] == "enrollment_candidate_not_S4_probe" for s in clips) == 1


def verify():
    """Cross-check only selected metadata rows; do not regenerate the corpus index."""
    m = json.loads((OUT / "SOURCE_AND_SPLIT_MANIFEST.json").read_text(encoding="utf-8"))
    wanted = {Path(s["source_binding"]["path"]).name: s for s in m["sources"]}
    remaining = set(wanted)
    checked = []
    metadata = EN / "metadata/original/validated.tsv"
    with metadata.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        actual_columns = reader.fieldnames
        assert {"client_id", "path", "sentence", "locale"} <= set(actual_columns)
        for r in reader:
            if r["path"] not in remaining:
                continue
            s = wanted[r["path"]]
            assert identity(r["client_id"]) == s["identity"]
            assert r["sentence"] == s["transcript"]
            assert r["sentence_id"] == s["sentence_id"]
            assert r["locale"] == s["locale"] == "en"
            assert int(r["up_votes"]) == s["votes"]["up"]
            assert int(r["down_votes"]) == s["votes"]["down"] == 0
            checked.append({"source_id": s["source_id"], "native_row_sha256": row_hash(r)})
            remaining.remove(r["path"])
            if not remaining:
                break
    assert not remaining, f"Selected rows absent in native validated.tsv: {remaining}"
    validate_structure(m)
    receipt = {"status": "PASS", "utc": utc(), "scope": "Selected native metadata rows, contributor/split uniqueness, transcript and source/decoded byte uniqueness, distinct enrollment candidates", "actual_native_columns": actual_columns, "native_metadata_path": str(metadata), "selected_rows_checked": len(checked), "rows": checked}
    save(OUT / "SOURCE_NATIVE_METADATA_VERIFICATION.json", receipt)
    print(json.dumps({"status": "PASS", "selected_rows_checked": len(checked), "receipt": str(OUT / "SOURCE_NATIVE_METADATA_VERIFICATION.json")}))


def calibration_qc():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    m = json.loads((OUT / "SOURCE_AND_SPLIT_MANIFEST.json").read_text())
    ids = [p["identity"] for p in m["people"] if p["split"] == "development"][:2]
    shortlist = []
    for cid in ids:
        shortlist.extend([s for s in m["sources"] if s["identity"] == cid and s["usage"] == "probe"][:2])
    fig, axes = plt.subplots(4, 1, figsize=(11, 9), constrained_layout=True)
    rows = []
    for ax, s in zip(axes, shortlist):
        y, sr = sf.read(s["decoded_16k_binding"]["path"], dtype="float64")
        q = s["quality"]
        frame = q["frame_samples"]
        rms = np.sqrt(np.mean(y[:len(y) // frame * frame].reshape(-1, frame) ** 2, axis=1))
        tail_n = min(len(y), int(.3 * sr))
        last_active = q["active_ranges_samples_estimated"][-1][1]
        row = {"source_id": s["source_id"], "duration_sec": s["duration_sec"],
               "peak": q["peak"], "active_rms_dbfs": q["active_rms_dbfs"],
               "last_300ms_rms_dbfs": float(20 * np.log10(max(float(np.sqrt(np.mean(y[-tail_n:] ** 2))), 1e-15))),
               "estimated_quiet_suffix_sec": (len(y) - last_active) / sr,
               "rails_ge_0_999": q["samples_abs_ge_0_999"],
               "scope": "Waveform and 20ms RMS envelope; suffix is source-file margin, not measured reverberation decay"}
        rows.append(row)
        ax.plot(np.arange(0, len(y), 20) / sr, y[::20], lw=.35, color="#688bc2", label="waveform")
        ax.plot((np.arange(len(rms)) + .5) * frame / sr, rms, lw=1.2, color="#922b21", label="20 ms RMS")
        ax.set_title(s["source_id"] + " — " + s["transcript"], fontsize=9)
        ax.set_ylim(-1, 1)
        ax.set_ylabel("Original amplitude")
        ax.grid(alpha=.2)
    axes[0].legend(loc="upper right", fontsize=8)
    axes[-1].set_xlabel("Seconds from source-file start")
    fig.savefig(OUT / "SOURCE_CALIBRATION_WAVEFORMS.png", dpi=140)
    plt.close(fig)
    receipt = {"created_utc": utc(), "scope": "First two whole probe utterances of each initial A/B contributor; no listening review", "rows": rows,
               "interpretation": "Numerical envelopes expose clipping and remaining end activity. End-of-file quiet margins cannot prove dry/anechoic speech or estimate RT60; source room/microphone conditions remain unknown. No source filtering based on S4 model or XVF results."}
    save(OUT / "SOURCE_CALIBRATION_QC.json", receipt)
    print(json.dumps(receipt))


def tests():
    sr = RATE
    x = np.r_[np.zeros(sr), .1 * np.sin(2 * np.pi * 440 * np.arange(2 * sr) / sr), np.zeros(sr)].astype("float32")
    s = active_stats(x)
    assert abs(s["active_seconds_estimated"] - 2.) < .021
    assert abs(s["active_rms"] - .1 / math.sqrt(2)) < 1e-5
    assert quality_reasons(s, 4) == []
    bad = x.copy(); bad[sr:sr + 10] = 1.
    assert "source_rail_or_overrange" in quality_reasons(active_stats(bad), 4)
    low = x * .01
    assert "would_require_excessive_amplification" in quality_reasons(active_stats(low), 4)
    assert identity("same-id") == identity("same-id")
    assert identity("same-id") != identity("another-id")
    for rate in (32000, 44100, 48000):
        g = math.gcd(rate, RATE)
        y = resample_poly(np.zeros(rate), RATE // g, rate // g)
        assert len(y) == RATE and np.isfinite(y).all()
    fixture = {"sources": [{"identity": "dev", "split": "development", "source_binding": {"sha256": str(i)}, "decoded_16k_binding": {"sha256": str(i)}, "transcript_sha256": str(i), "usage": "probe" if i < 3 else "enrollment_candidate_not_S4_probe"} for i in range(4)], "people": [{"identity": "dev", "split": "development"}]}
    validate_structure(fixture)
    import copy
    for mutation in ("identity_leak", "source_duplicate", "decoded_duplicate", "enrollment_as_probe"):
        bad_manifest = copy.deepcopy(fixture)
        if mutation == "identity_leak":
            bad_manifest["sources"][0]["split"] = "downstream_reserve"
        elif mutation == "source_duplicate":
            bad_manifest["sources"][0]["source_binding"]["sha256"] = "1"
        elif mutation == "decoded_duplicate":
            bad_manifest["sources"][0]["decoded_16k_binding"]["sha256"] = "1"
        else:
            bad_manifest["sources"][3]["usage"] = "probe"
        try:
            validate_structure(bad_manifest)
        except AssertionError:
            pass
        else:
            raise AssertionError("Leakage control failed: " + mutation)
    result = {"status": "PASS", "checks": ["estimated_activity_synthetic", "clipping_rejection", "excessive_gain_rejection", "stable_contributor_namespace", "rational_resampler_duration", "identity_leak_rejected", "source_duplicate_rejected", "decoded_duplicate_rejected", "enrollment_as_probe_rejected"], "utc": utc()}
    save(OUT / "SOURCE_ADAPTER_TESTS.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "test", "verify", "calibration-qc"))
    args = parser.parse_args()
    {"test": tests, "prepare": prepare, "verify": verify, "calibration-qc": calibration_qc}[args.action]()
