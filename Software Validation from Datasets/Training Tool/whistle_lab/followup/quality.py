"""One resumable CPU pass over multi-microphone audio, shared by every trial.

The measured levels are not SNR or intelligibility. No gain, denoising, new
transcripts, or fabricated silence labels are applied to dataset audio.
"""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import sqlite3
import time
import zlib
import numpy as np
import pandas as pd
import soundfile as sf
from shared import HOME, atomic_json, read_json, sha256, policy, paused, freeze_policy, update_status
from common import audio_path


def classify(rms, peak, speech, config=None):
    p = config or policy()["audio_quality"]
    silent = (rms < p["near_silent_rms_dbfs"]) & (peak < p["near_silent_peak_dbfs"])
    quiet = (rms < p["quiet_rms_dbfs"]) | (peak < p["quiet_peak_dbfs"])
    excluded = silent & speech
    confidence = np.where(quiet & speech, p["quiet_relative_view_weight"], 1.)
    return excluded, confidence


def measure_file(path, segments):
    """Decode once; use 20 ms energy/peak frames for all aligned segments/channels.

    At most 20 ms of boundary context is included, conservatively retaining a
    near-silent segment if a boundary contains sound. PCM is never saved.
    """
    powers, peaks, clips = [], [], []
    with sf.SoundFile(path) as handle:
        rate, channels = handle.samplerate, handle.channels
        width = max(1, round(rate * .02))
        while True:
            if paused():
                raise InterruptedError("Audio audit paused; completed files retained")
            wave = handle.read(width * 1500, dtype="float32", always_2d=True)
            if not len(wave): break
            if not np.isfinite(wave).all(): raise ValueError(f"Nonfinite PCM: {path}")
            if len(wave) % width:
                wave = np.pad(wave, ((0, width - len(wave) % width), (0, 0)))
            blocks = wave.reshape(-1, width, channels)
            powers.append(np.mean(np.square(blocks, dtype=np.float64), axis=1))
            peaks.append(np.max(np.abs(blocks), axis=1))
            clips.append(np.mean(np.abs(blocks) >= .999, axis=1))
    if not powers: raise ValueError(f"Empty PCM: {path}")
    energy = np.concatenate(powers)
    peak = np.concatenate(peaks)
    clipped = np.concatenate(clips)
    prefix = np.vstack([np.zeros(channels), np.cumsum(energy, axis=0)])
    clip_prefix = np.vstack([np.zeros(channels), np.cumsum(clipped, axis=0)])
    output = np.zeros((len(segments), 3), np.float32)
    for number, (start, end, channel) in enumerate(segments):
        a, b = int(np.floor(start * rate / width)), min(len(energy), int(np.ceil(end * rate / width)))
        channel = int(channel)
        if not 0 <= a < b or channel >= channels: raise ValueError(f"Bad audit bounds/channel: {path}")
        output[number] = (10*np.log10(max((prefix[b, channel]-prefix[a, channel])/(b-a), 1e-20)),
                          20*np.log10(max(float(peak[a:b, channel].max()), 1e-10)),
                          (clip_prefix[b, channel]-clip_prefix[a, channel])/(b-a))
    return output


def audit_pool():
    import os
    import ctypes
    if os.name == "nt": ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        return _audit_pool()
    finally:
        if os.name == "nt": ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def _audit_pool():
    from prepare import development_panel
    freeze_policy()
    if read_json(HOME / "audio_quality.json").get("complete"):
        from shared import qualified
        for split in ("train", "dev", "development"): qualified(split)
        return True
    quality = HOME / "quality"
    quality.mkdir(exist_ok=True)
    original = read_json(HOME / "pool.json")
    for split in ("train", "dev"):
        if sha256(HOME / f"{split}.parquet") != original["sha256"][split]:
            raise ValueError("Expanded source manifest changed before the level audit")
    frame = pd.concat([pd.read_parquet(HOME / f"{s}.parquet").assign(audit_split=s) for s in ("train", "dev")], ignore_index=True)
    metrics = np.full((len(frame), 3), np.nan, dtype=np.float32)
    # Actual dataframe indexes (not positions in the filtered table).
    groups = frame[frame.dataset_id.ne("common_voice")].groupby(["audio_root_id", "audio_relative_path"], sort=True).groups
    conn = sqlite3.connect(quality / "file_cache.sqlite3")
    conn.execute("CREATE TABLE IF NOT EXISTS files (key TEXT PRIMARY KEY, signature TEXT NOT NULL, metrics BLOB NOT NULL)")
    started, completed, reused = time.time(), 0, 0
    existing = dict((key, (signature, blob)) for key, signature, blob in conn.execute("SELECT key,signature,metrics FROM files"))
    def work(item):
        (root, relative), indexes = item
        path = audio_path(root, relative)
        segments = frame.loc[indexes, ["start_sec", "end_sec", "channel_index"]].to_numpy(dtype=np.float64)
        stat = path.stat()
        signature = hashlib.sha256(f"v1:{stat.st_size}:{stat.st_mtime_ns}:".encode() + segments.tobytes()).hexdigest()
        key = root + ":" + relative
        saved = existing.get(key)
        if saved and saved[0] == signature:
            values = np.frombuffer(zlib.decompress(saved[1]), np.float32).reshape(-1, 3)
            return key, signature, indexes, values, saved[1], True
        values = measure_file(path, segments)
        return key, signature, indexes, values, zlib.compress(values.tobytes()), False
    try:
        with ThreadPoolExecutor(max_workers=policy()["audio_quality"]["workers"]) as pool:
            # Bounded submission: avoid 20k queued dataframe copies or open handles.
            iterator = iter(groups.items())
            pending = [pool.submit(work, item) for _, item in zip(range(2), iterator)]
            while pending:
                future = pending.pop(0)
                key, signature, indexes, values, blob, cached = future.result()
                metrics[indexes] = values
                reused += int(cached)
                conn.execute("INSERT OR REPLACE INTO files VALUES (?,?,?)", (key, signature, blob))
                completed += 1
                if completed % 25 == 0 or completed == len(groups):
                    conn.commit()
                    progress = {"completed_files":completed, "total_files":len(groups), "percent":100*completed/len(groups), "elapsed_seconds":time.time()-started, "cached_files":reused}
                    atomic_json(HOME / "quality_status.json", progress)
                    update_status("auditing_audio", message="Checking recording levels before admitting microphone views", progress=progress)
                if paused(): raise InterruptedError("Audio audit paused")
                item = next(iterator, None)
                if item is not None: pending.append(pool.submit(work, item))
    except InterruptedError:
        conn.commit()
        return False
    finally:
        conn.commit(); conn.close()
    frame[["rms_dbfs", "peak_dbfs", "clipped_fraction"]] = metrics
    speech = frame.text.fillna("").astype(str).str.strip().ne("").to_numpy()
    excluded, confidence = classify(metrics[:,0], metrics[:,1], speech)
    opening_beep = frame.dataset_id.eq("chime6").to_numpy() & frame.start_sec.lt(1).to_numpy() & speech
    excluded |= opening_beep
    frame["view_confidence"] = confidence
    frame["audio_level"] = np.where(np.isnan(metrics[:,0]), "not_audited_single_mic", np.where(confidence < 1, "quiet", "ordinary"))
    quarantine = frame.loc[excluded].drop(columns=["tokens"])
    quarantine = quarantine.assign(reason=np.where(opening_beep[excluded],"Speech annotation overlaps user-reported CHiME opening beep; full segment reserved", "Labelled speech paired with near-silent PCM; no replacement transcript"))
    quarantine.to_parquet(quality / "quarantine.parquet", index=False)
    per_dataset = {}
    for ds, part in frame.groupby("dataset_id"):
        idx = part.index
        per_dataset[ds] = {"views":len(part), "measured_views":int(part.rms_dbfs.notna().sum()), "quarantined":int(excluded[idx].sum()), "quiet_retained":int(((confidence[idx]<1)&~excluded[idx]).sum()), "rms_dbfs_quantiles":{str(q):float(part.rms_dbfs.quantile(q)) for q in (.01,.1,.5,.9)} if part.rms_dbfs.notna().any() else {}}
    kept = frame.loc[~excluded].copy()
    counts = {}
    for split, part in kept.groupby("audit_split"):
        part.drop(columns="audit_split").to_parquet(quality / f"{split}.parquet", index=False)
        counts[split] = len(part)
    panel = development_panel(kept[kept.audit_split.eq("dev")])
    panel.to_parquet(quality / "development.parquet", index=False)
    from eta import write_profile
    write_profile(kept[kept.audit_split.eq("train")],kept[kept.audit_split.eq("dev")],panel)
    atomic_json(HOME / "audio_quality.json", {"complete":True, "finished_at":time.time(), "policy":policy()["audio_quality"], "rows":counts, "development_rows":len(panel), "datasets":per_dataset, "quarantined_views":int(excluded.sum()), "opening_beep_views":int(opening_beep.sum()), "quarantined_source_groups":int(frame.loc[excluded].source_group_id.nunique()), "source_groups_lost":int(frame.source_group_id.nunique()-kept.source_group_id.nunique()), "sha256":{s:sha256(quality/f"{s}.parquet") for s in ("train","dev","development")}, "source_pool_sha256":read_json(HOME/"pool.json")["sha256"], "common_voice":"Age-filtered single-microphone selection retained; no multi-mic level audit", "limitation":"Level measurements cannot certify speech intelligibility, estimate SNR, or detect every wrong-speaker/inaudible transcript"})
    return True


if __name__ == "__main__":
    from shared import initial_complete
    if not initial_complete(): raise SystemExit("Wait for the initial training and comparison")
    raise SystemExit(0 if audit_pool() else 75)
