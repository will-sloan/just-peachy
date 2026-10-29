"""Paths, run isolation and controls for the sequential follow-up campaign."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import sys
import time

LAB = Path(__file__).resolve().parent.parent
if str(LAB) not in sys.path:
    sys.path.append(str(LAB))
import common

REPO = common.REPO
BASE = REPO / "training/whistle_age_robust_v1"
HOME = REPO / "training/whistle_followups_v1"
SOURCE = Path(__file__).resolve().parent
atomic_json, read_json, sha256 = common.atomic_json, common.read_json, common.sha256
DATASETS = ("common_voice", "ami", "chime6", "voices")


def run_dir(name):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        raise ValueError("Invalid experiment name")
    return HOME / "runs" / name


def configure(name):
    """Override imported constants only inside this isolated worker process."""
    folder = run_dir(name)
    config = read_json(folder / "config.json")
    if not config or config["run_name"] != f"whistle_followups_v1/runs/{name}":
        raise ValueError("Missing or mismatched experiment configuration")
    common.CONFIG = config
    common.CONFIG_DIGEST = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    common.RUN = folder
    common.ASSETS = BASE / "assets"
    return config, folder


def paused():
    return (read_json(HOME / "control.json").get("paused", False)
            or read_json(BASE / "control.json").get("paused", False))


def initial_complete():
    return (read_json(BASE / "status.json").get("phase") == "complete"
            and read_json(BASE / "evaluation_summary.json").get("complete") is True
            and (BASE / "whistle.final.cact").is_file()
            and (BASE / "whistle.best.cact").is_file())


def update_status(phase, **values):
    record = read_json(HOME / "status.json")
    record.update(phase=phase, updated_at=time.time(), **values)
    try:
        atomic_json(HOME / "status.json", record)
    except PermissionError:
        # The next update retries; a locked display file must not stop a worker.
        pass


def policy():
    return read_json(SOURCE / "plan.json")


def qualified(split):
    """Only audited manifests can reach a new training/evaluation worker."""
    record = read_json(HOME / "audio_quality.json")
    path = HOME / "quality" / f"{split}.parquet"
    if not record.get("complete") or sha256(path) != record["sha256"][split]:
        raise ValueError("Complete, unchanged audio-quality audit required")
    return path


def freeze_policy():
    target = HOME / "policy_snapshot.json"
    current = {"plan": policy(), "sha256": sha256(SOURCE / "plan.json")}
    if target.exists() and read_json(target) != current:
        raise ValueError("Campaign policy changed; refusing to extend or alter an active campaign")
    if not target.exists():
        atomic_json(target, current)
    return current["sha256"]
