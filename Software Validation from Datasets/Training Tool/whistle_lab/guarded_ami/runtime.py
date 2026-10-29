"""Isolated paths, immutable identities and shared pause controls."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import time

SOURCE = Path(__file__).resolve().parent
LAB = SOURCE.parent
REPO = LAB.parents[2]
sys.path.append(str(LAB))
import common

BASE = REPO / "training/whistle_age_robust_v1"
FOLLOWUP = REPO / "training/whistle_followups_v1"
RUN = REPO / "training/whistle_transcription_guarded_v1"
atomic_json, atomic_bytes = common.atomic_json, common.atomic_bytes
read_json, sha256, replace_file = common.read_json, common.sha256, common.replace_file
COHORTS = ("ami", "chime6", "voices", "common_voice_age", "cmu_arctic_clean",
           "hifitts_clean", "hifitts_native", "librispeech_clean", "librispeech_native")


def paused():
    return any(read_json(p / "control.json").get("paused", False) for p in (RUN, BASE, FOLLOWUP))


def status(phase, **values):
    record = read_json(RUN / "status.json")
    record.update(phase=phase, updated_at=time.time(), **values)
    if phase != "failed":
        record.pop("traceback", None)
    atomic_json(RUN / "status.json", record)


def configure():
    config = read_json(RUN / "config.json")
    if config.get("run_name") != "whistle_transcription_guarded_v1":
        raise ValueError("Run configuration is missing or names another output directory")
    common.RUN, common.ASSETS, common.CONFIG = RUN, BASE / "assets", config
    common.CONFIG_DIGEST = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    return config


def verify():
    config = configure()
    snapshot = read_json(RUN / "split_snapshot.json")
    if not snapshot.get("complete") or not read_json(RUN / "execution_amendment.json").get("exploratory_authorized"):
        raise ValueError("Preparation and the exploratory amendment are required")
    if sha256(RUN / "split_snapshot.json") != config["split_snapshot_sha256"]:
        raise ValueError("Frozen split/exposure snapshot changed")
    for key in ("train", "dev", "confirmation"):
        if sha256(RUN / (key + ".parquet")) != snapshot["sha256"][key]:
            raise ValueError("Frozen manifest changed: " + key)
    if sha256(RUN / "execution_amendment.json") != config["amendment_sha256"]:
        raise ValueError("Execution amendment changed")
    parent = read_json(RUN / "proposal_snapshot.json")["proposal"]["initialization"]
    for name, expected in (("adapter.final.safetensors", parent["adapter_sha256"]),
                           ("whistle.final.cact", parent["reference_export_sha256"])):
        if sha256(BASE / name) != expected:
            raise ValueError("Parent model changed: " + name)
    return config


def export_paths(step):
    return RUN / f"adapter.step_{step:05d}.safetensors", RUN / f"whistle.step_{step:05d}.cact"


def scores_path(step, role="dev"):
    return RUN / "scores" / f"{role}_{step:05d}.json"
