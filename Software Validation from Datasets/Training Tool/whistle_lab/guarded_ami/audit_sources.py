"""Check the proposed confirmation prerequisite without audio/model execution.

This audit intentionally fails closed. It is not a training launcher and does
not interpret previously scored sources as a new independent confirmation set.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import pandas as pd

LAB = Path(__file__).resolve().parent.parent
REPO = LAB.parents[2]
sys.path.append(str(LAB))
from common import atomic_json, read_json, sha256

BASE = REPO / "training/whistle_age_robust_v1"
FOLLOWUP = REPO / "training/whistle_followups_v1"
OUTPUT = REPO / "training/whistle_initial_ami_guarded_v1"
PROPOSAL = LAB / "proposals/initial_ami_guarded_v1/plan.json"
FRAMEWORK = REPO / "training/successors/phase5a_original_adapter_training_v1/framework_manifests"


def identities(values):
    """Missing identity is an audit error, never a new held-out source."""
    values = pd.Series(values, dtype="string")
    if values.isna().any() or values.str.strip().eq("").any():
        raise ValueError("Missing session identity; cannot establish disjointness")
    return set(values.str.strip())


def classify(available, trained, development, historical):
    available, trained, development, historical = map(
        identities, (available, trained, development, historical)
    )
    exposed = trained | development | historical
    return {
        "local_sessions": sorted(available),
        "parent_training_sessions": sorted(trained),
        "earlier_development_sessions": sorted(development),
        "historical_comparison_sessions": sorted(historical),
        "unexposed_local_sessions": sorted(available - exposed),
        "available_session_count": len(available),
        "unexposed_session_count": len(available - exposed),
        "sessions_not_in_parent_training": sorted(available - trained),
    }


def audit():
    paths = {
        "recordings": REPO / "Software Validation from Datasets/Normalized Metadata/CHiME_6/recordings.parquet",
        "parent_training": BASE / "train.parquet",
        "parent_source_metadata": FRAMEWORK / "train/chime_train.parquet",
        "earlier_development": FOLLOWUP / "quality/development.parquet",
        "historical_comparison": BASE / "evaluation.parquet",
    }
    local = pd.read_parquet(paths["recordings"], columns=["session_id"])
    # Match actual parent training rows, not just a proposed source manifest.
    trained = pd.read_parquet(paths["parent_training"],
        columns=["dataset_id", "source_registry_row_id"],
        filters=[("dataset_id", "==", "chime6")])
    meta = pd.read_parquet(paths["parent_source_metadata"],
        columns=["source_registry_row_id", "session_id"])
    joined = trained.merge(meta, on="source_registry_row_id", how="left", validate="one_to_one")
    dev = pd.read_parquet(paths["earlier_development"],
        columns=["dataset_id", "session_id"], filters=[("dataset_id", "==", "chime6")])
    history = pd.read_parquet(paths["historical_comparison"],
        columns=["dataset_id", "session_id"], filters=[("dataset_id", "==", "chime6")])
    result = classify(local.session_id, joined.session_id, dev.session_id, history.session_id)
    original = read_json(PROPOSAL)
    parent = original["initialization"]
    files = {
        "adapter": BASE / "adapter.final.safetensors",
        "reference_export": BASE / "whistle.final.cact",
    }
    digests = {name: sha256(path) for name, path in files.items()}
    if digests["adapter"] != parent["adapter_sha256"] or digests["reference_export"] != parent["reference_export_sha256"]:
        raise ValueError("Preserved initial model identity differs from the proposal")
    # Zero unseen CHiME sessions is sufficient to fail the proposed primary
    # confirmation requirement; do not needlessly inspect other raw datasets.
    blocked = not result["unexposed_local_sessions"]
    record = {
        "schema": "whistle-guarded-provenance-audit/v1",
        "checked_at": time.time(),
        "proposal_sha256": sha256(PROPOSAL),
        "model_sha256": digests,
        "metadata_only": True,
        "audio_decoded": 0,
        "optimizer_updates": 0,
        "chime6": result,
        "evidence": {name: {"path": str(path), "sha256": sha256(path)} for name, path in paths.items()},
        "complete_for_chime_session_gate": True,
        "all_cohort_preparation_complete": False,
        "fresh_confirmation_gate": "blocked" if blocked else "requires_remaining_cohort_audits",
        "training_ready": False,
        "reason": ("All local CHiME-6 sessions were used in parent training, earlier development, or the inspected historical comparison. New utterances or microphone views from these sessions are not a fresh session-disjoint confirmation set."
            if blocked else "CHiME has unexposed sessions; remaining preparation and cohort gates still require verification."),
        "independence_scope": "Local fine-tuning and evaluated-source history; pretrained-base corpus independence is not established.",
        "next_options": [
            "Obtain genuinely new independent recordings and retain the original confirmation gate.",
            "Explicitly amend this new run to exploratory evaluation with the independence limitation disclosed; retain the initial model as default.",
        ],
    }
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Save this audit and blocked preparation status in the separate proposed output directory")
    args = parser.parse_args()
    result = audit()
    if args.write:
        if (OUTPUT / "checkpoint.json").exists() or read_json(OUTPUT / "status.json").get("training_launched"):
            raise RuntimeError("Refusing to replace status for a launched run")
        snapshot = {"proposal": read_json(PROPOSAL), "sha256": sha256(PROPOSAL)}
        existing = read_json(OUTPUT / "proposal_snapshot.json")
        if existing and existing != snapshot:
            raise RuntimeError("Proposal snapshot is immutable; keep the existing evidence")
        atomic_json(OUTPUT / "proposal_snapshot.json", snapshot)
        atomic_json(OUTPUT / "provenance_audit.json", result)
        atomic_json(OUTPUT / "status.json", {
            "phase": "blocked_provenance", "updated_at": time.time(),
            "training_launched": False, "step": 0,
            "message": result["reason"], "audit_sha256": sha256(OUTPUT / "provenance_audit.json"),
            "waiting_for": "Independent recordings or an explicit exploratory protocol amendment",
        })
    print(json.dumps(result, indent=2))
    return 2 if result["fresh_confirmation_gate"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
