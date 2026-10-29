"""Isolated full-training rerun, immutable identities and inherited user pauses."""
from __future__ import annotations
import hashlib
import importlib.util
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
PREVIOUS = REPO / "training/whistle_transcription_guarded_v1"
RUN = REPO / "training/whistle_full_rerun_v1"
atomic_json, atomic_bytes = common.atomic_json, common.atomic_bytes
read_json, sha256, replace_file = common.read_json, common.sha256, common.replace_file
COHORTS = ("ami", "chime6", "voices", "common_voice_age", "cmu_arctic_clean",
           "hifitts_clean", "hifitts_native", "librispeech_clean", "librispeech_native")


def shared(name):
    """Reuse the tested decoder/uncertainty helpers with this isolated runtime."""
    key = "_full_rerun_shared_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, LAB / "guarded_ami" / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def paused():
    return any(read_json(p / "control.json").get("paused", False) for p in (RUN, BASE, FOLLOWUP, PREVIOUS))


def status(phase, **values):
    record = read_json(RUN / "status.json")
    record.update(phase=phase, updated_at=time.time(), **values)
    if phase != "failed":
        record.pop("traceback", None)
    atomic_json(RUN / "status.json", record)


def configure():
    config = read_json(RUN / "config.json")
    if config.get("run_name") != RUN.name or config.get("method") != "full":
        raise ValueError("Missing or incompatible full-training configuration")
    common.RUN, common.ASSETS, common.CONFIG = RUN, BASE / "assets", config
    common.CONFIG_DIGEST = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    return config


def verify():
    config = configure()
    frozen = read_json(RUN / "execution_snapshot.json")
    if not frozen.get("complete") or not frozen.get("authorized_full_rerun"):
        raise ValueError("Frozen preparation is required")
    for name, digest in frozen["files"].items():
        if sha256(RUN / name) != digest:
            raise ValueError("Frozen input changed: " + name)
    for name, digest in frozen["source_sha256"].items():
        if sha256(LAB / name) != digest:
            raise ValueError("Pinned execution source changed: " + name)
    for name, digest in frozen["base_sha256"].items():
        if sha256(BASE / name) != digest:
            raise ValueError("Preserved base/reference changed: " + name)
    return config


def export_paths(step):
    if step == 0:
        # Scoring ID zero is explicitly the INITIAL comparison model, not the
        # zero-update parameter state of this fresh-base full-training run.
        return BASE / "adapter.final.safetensors", BASE / "whistle.final.cact"
    return RUN / f"weights.step_{step:07d}.msgpack", RUN / f"whistle.step_{step:07d}.cact"


def scores_path(step, role="dev"):
    return RUN / "scores" / f"{role}_{step:07d}.json"


def validation_steps(batches_per_epoch, epochs=3):
    if batches_per_epoch < 2 or epochs != 3:
        raise ValueError("Three complete passes and at least two batches are required")
    return [e * batches_per_epoch + point
            for e in range(epochs) for point in ((batches_per_epoch + 1)//2, batches_per_epoch)]


def next_target(step, boundaries):
    return next((n for n in boundaries if n > step), None)
