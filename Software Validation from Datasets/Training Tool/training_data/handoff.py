"""Build and verify the additive portable-training successor and handoff assets.

This module never trains a model, runs an evaluation, or copies raw audio into
Git.  Its generated freeze lives under ``JP_TRAINING_ROOT`` and is reproduced
from the immutable Phase-3/Phase-4 parents.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from training_data.common_voice import sha256_file
from training_data.phase4 import common_voice_manifest, dataset_weights, manifest_summary
from training_data.portability import PortableRoots, portable_roots, resolve_logical_path
from training_data.registry import _frame_hash


PARENT_PHASE4_ID = "training_manifest_freeze_phase4_cc2909f344d0"
PARENT_PHASE4_SHA256 = "CC2909F344D01E9007EF648BA71277188DF26741CBEA5D1D2B0933116CE6DF92"
SUCCESSOR_FREEZE_NAME = "phase5a_portable_training_freeze_v1"
SUCCESSOR_RUNTIME_NAME = "phase5a_original_adapter_training_v1"
COMMON_VOICE_ARCHIVE_SHA256 = "6809228E6AB506D18F6A1EBC830056450F8266C8F513D6038BDB0FC88A49E6CB"
COMMON_VOICE_ARCHIVE_BYTES = 94_639_372_950
CHECKPOINT_REVISION = "37cb5606808f3d5e55a3fc73554bdf757d82465a"
CHECKPOINT_FILES = {
    "pretrained.pt": (
        "exp/pretrained.pt",
        "E44BB7C8D3985A7CF0089020D227AECD71E323DCAAABCAED90E4A792E1385342",
    ),
    "bpe.model": (
        "data/lang_bpe_500/bpe.model",
        "C53433DE083C4A6AD12D034550EF22DE68CEC62C4F58932A7B6B8B2F1E743FA5",
    ),
    "tokens.txt": (
        "data/lang_bpe_500/tokens.txt",
        "49E3C2646595FD907228B3C6787069658F67B17377C60AEB8619C4551B2316FB",
    ),
}
EXPERIMENTS = (
    ("O-AGE", "AGE", "strict"),
    ("O-AMI", "AMI", "strict"),
    ("O-CHIME", "CHIME", "strict"),
    ("O-VOICES", "VOICES", "strict"),
    ("O-ROBUST", "ROBUST", "strict"),
    ("O-AGE-ROBUST", "AGE_ROBUST", "strict"),
    ("O-CMU", "CMU_EXPLORATORY", "exploratory"),
    ("O-AGE-ROBUST-CMU", "AGE_ROBUST_CMU_EXPLORATORY", "exploratory"),
)


class HandoffError(RuntimeError):
    """Raised when a deterministic handoff invariant fails."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for attempt in range(20):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.1)


def _identity(payload: Mapping[str, Any], *, prefix: str, kind: str) -> dict[str, Any]:
    digest = canonical_sha256(payload)
    return {
        **payload,
        f"{kind}_id": f"{prefix}_{digest[:12].lower()}",
        f"{kind}_sha256": digest,
    }


def successor_root(roots: PortableRoots) -> Path:
    return roots.training / "successors" / SUCCESSOR_FREEZE_NAME


def runtime_root(roots: PortableRoots) -> Path:
    return roots.training / "successors" / SUCCESSOR_RUNTIME_NAME


def phase4_root(roots: PortableRoots) -> Path:
    return roots.training / "successors" / "phase4_training_manifests_v1"


def phase3_root(roots: PortableRoots) -> Path:
    return roots.training / "successors" / "common_voice_26_english_phase3"


def logical_training(path: Path, roots: PortableRoots) -> str:
    return "JP_TRAINING_ROOT:" + path.relative_to(roots.training).as_posix()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_parent_document(document: Mapping[str, Any]) -> None:
    canonical = {
        key: value
        for key, value in document.items()
        if key not in {"training_manifest_freeze_id", "training_manifest_freeze_sha256"}
    }
    if (
        document.get("training_manifest_freeze_id") != PARENT_PHASE4_ID
        or document.get("training_manifest_freeze_sha256") != PARENT_PHASE4_SHA256
        or canonical_sha256(canonical) != PARENT_PHASE4_SHA256
    ):
        raise HandoffError("Immutable Phase-4 parent identity changed")


def _write_age_train(roots: PortableRoots) -> dict[str, Any]:
    phase3 = phase3_root(roots)
    registry = pd.read_parquet(
        phase3 / "registries" / "common_voice_older_registry.parquet"
    )
    selected = registry.loc[
        registry["training_role"].astype(str).isin({"train", "heldout"})
    ].copy()
    parent = _read_json(phase3 / "registries" / "training_data_freeze_phase3.json")
    frame = common_voice_manifest(selected, role="train", parent=parent)
    destination = successor_root(roots) / "source_manifests" / "age_train.parquet"
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(destination, index=False)
    persisted = pd.read_parquet(destination)
    digest = _frame_hash(persisted)
    descriptor = {
        "manifest_name": "AGE_TRAIN",
        "manifest_id": f"age_train_manifest_{digest[:12].lower()}",
        "manifest_sha256": digest,
        "manifest_schema_version": "training-source-manifest-phase4.v1",
        "logical_path": logical_training(destination, roots),
        "phase3_parent_freeze_id": parent["training_data_freeze_id"],
        "phase3_parent_freeze_sha256": parent["training_data_freeze_sha256"],
        **manifest_summary(persisted),
        "former_common_voice_heldout_reclassified_to_train": True,
    }
    expected = (91_123, 1_217)
    if (descriptor["record_count"], descriptor["speaker_count"]) != expected:
        raise HandoffError(f"Successor AGE TRAIN arithmetic changed: {descriptor}")
    atomic_json(destination.with_suffix(".manifest.json"), descriptor)
    return descriptor


def _affected_bundle(
    roots: PortableRoots,
    *,
    name: str,
    old: Mapping[str, Any],
    age: Mapping[str, Any],
    phase4_sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    hours_by_dataset = {
        "common_voice": float(age["effective_unique_source_hours"]),
        "ami": float(phase4_sources["AMI_TRAIN"]["effective_unique_source_hours"]),
        "chime6": float(phase4_sources["CHIME_TRAIN"]["effective_unique_source_hours"]),
        "voices": float(phase4_sources["VOICES_TRAIN"]["effective_unique_source_hours"]),
        "cmu_arctic": float(
            phase4_sources["CMU_RELAXED_EXPLORATORY_TRAIN"]["effective_unique_source_hours"]
        ),
    }
    datasets = [str(item["dataset_id"]) for item in old["train_sources"]]
    weights = dataset_weights({key: hours_by_dataset[key] for key in datasets})
    sources = []
    for item in old["train_sources"]:
        dataset = str(item["dataset_id"])
        reference = dict(item)
        if dataset == "common_voice":
            reference.update(
                manifest_id=age["manifest_id"],
                manifest_sha256=age["manifest_sha256"],
                manifest_path=age["logical_path"],
            )
        reference["probability"] = weights[dataset]["final_probability"]
        sources.append(reference)
    payload = {
        key: value
        for key, value in old.items()
        if key not in {"bundle_id", "bundle_sha256"}
    }
    payload.update(
        schema_version="training-bundle-portable-successor.v1",
        phase4_parent_freeze_id=PARENT_PHASE4_ID,
        phase4_parent_freeze_sha256=PARENT_PHASE4_SHA256,
        train_sources=sources,
    )
    document = _identity(
        payload,
        prefix=f"{name.lower()}_bundle",
        kind="bundle",
    )
    destination = successor_root(roots) / "bundles" / f"{name.lower()}.json"
    atomic_json(destination, document)
    return {**document, "logical_path": logical_training(destination, roots)}


def build_successor(roots: PortableRoots) -> dict[str, Any]:
    """Materialize the additive successor without touching either parent freeze."""
    parent_path = phase4_root(roots) / "registries" / "training_manifest_freeze_phase4.json"
    parent = _read_json(parent_path)
    _verify_parent_document(parent)
    age = _write_age_train(roots)
    bundle_refs: dict[str, dict[str, Any]] = {
        key: dict(value) for key, value in parent["bundles"].items()
    }
    for name in ("AGE", "AGE_ROBUST", "AGE_ROBUST_CMU_EXPLORATORY"):
        old_path = resolve_logical_path(parent["bundles"][name]["logical_path"], roots)
        updated = _affected_bundle(
            roots,
            name=name,
            old=_read_json(old_path),
            age=age,
            phase4_sources=parent["source_manifests"],
        )
        bundle_refs[name] = {
            "id": updated["bundle_id"],
            "sha256": updated["bundle_sha256"],
            "logical_path": updated["logical_path"],
        }
    experiments = []
    for experiment_id, bundle_name, training_class in EXPERIMENTS:
        bundle = bundle_refs[bundle_name]
        experiments.append(
            {
                "experiment_id": experiment_id,
                "training_bundle_name": bundle_name,
                "training_bundle_id": bundle["id"],
                "training_bundle_sha256": bundle["sha256"],
                "training_class": training_class,
                "commercial_model_release_review_required": bundle_name
                in {"CHIME", "ROBUST", "AGE_ROBUST", "AGE_ROBUST_CMU_EXPLORATORY"},
                "initialization_family": "original",
                "training_started": False,
            }
        )
    plan_payload = {
        "schema_version": "original-adapter-experiment-plan-successor.v1",
        "phase4_parent_id": PARENT_PHASE4_ID,
        "experiments": experiments,
        "total_original_adapter_jobs": 8,
        "giga_adapter_jobs": 0,
    }
    plan = _identity(plan_payload, prefix="original_adapter_plan", kind="plan")
    plan_path = successor_root(roots) / "registries" / "original_adapter_plan.json"
    atomic_json(plan_path, plan)
    source_refs = {key: dict(value) for key, value in parent["source_manifests"].items()}
    source_refs["AGE_TRAIN"] = age
    freeze_payload = {
        "schema_version": "training-manifest-freeze-portable-successor.v1",
        "parent_phase4": {
            "id": PARENT_PHASE4_ID,
            "sha256": PARENT_PHASE4_SHA256,
            "logical_path": logical_training(parent_path, roots),
        },
        "successor_logical_root": "JP_TRAINING_ROOT",
        "successor_relative_path": f"successors/{SUCCESSOR_FREEZE_NAME}",
        "source_manifests": source_refs,
        "bundles": bundle_refs,
        "policies": parent["policies"],
        "initialization_reference": parent["initialization_references"]["original"],
        "model_plan": {
            "id": plan["plan_id"],
            "sha256": plan["plan_sha256"],
            "logical_path": logical_training(plan_path, roots),
            "total": 8,
            "giga": 0,
        },
        "declarations": {
            "common_voice_final_heldout_required": False,
            "former_common_voice_heldout_reclassified_to_train": True,
            "additional_final_holdout": False,
            "age_dev_used_for_gradients": False,
            "large_benchmark_is_independent_post_training_benchmark": True,
            "training_started": False,
            "large_evaluation_started": False,
            "onnx_export_started": False,
        },
    }
    freeze = _identity(
        freeze_payload,
        prefix="training_manifest_freeze_successor",
        kind="training_manifest_freeze",
    )
    freeze_path = successor_root(roots) / "registries" / "training_manifest_freeze_successor.json"
    atomic_json(freeze_path, freeze)
    verify = verify_successor(roots)
    if not verify["valid"]:
        raise HandoffError("Successor verification failed: " + "; ".join(verify["reasons"]))
    return freeze


def verify_successor(roots: PortableRoots) -> dict[str, Any]:
    path = successor_root(roots) / "registries" / "training_manifest_freeze_successor.json"
    reasons: list[str] = []
    if not path.is_file():
        return {"valid": False, "reasons": ["successor freeze is absent"]}
    freeze = _read_json(path)
    canonical = {
        key: value
        for key, value in freeze.items()
        if key not in {"training_manifest_freeze_id", "training_manifest_freeze_sha256"}
    }
    if canonical_sha256(canonical) != freeze.get("training_manifest_freeze_sha256"):
        reasons.append("successor self-hash mismatch")
    if freeze.get("parent_phase4", {}).get("id") != PARENT_PHASE4_ID:
        reasons.append("successor parent mismatch")
    age = freeze.get("source_manifests", {}).get("AGE_TRAIN", {})
    age_path = resolve_logical_path(str(age.get("logical_path", "invalid:")), roots)
    if not age_path.is_file() or _frame_hash(pd.read_parquet(age_path)) != age.get(
        "manifest_sha256"
    ):
        reasons.append("AGE TRAIN manifest mismatch")
    if (age.get("record_count"), age.get("speaker_count")) != (91_123, 1_217):
        reasons.append("AGE TRAIN arithmetic mismatch")
    for name, reference in freeze.get("bundles", {}).items():
        bundle_path = resolve_logical_path(reference["logical_path"], roots)
        if not bundle_path.is_file():
            reasons.append(f"missing bundle {name}")
            continue
        bundle = _read_json(bundle_path)
        canonical_bundle = {
            key: value
            for key, value in bundle.items()
            if key not in {"bundle_id", "bundle_sha256"}
        }
        if (
            canonical_sha256(canonical_bundle) != reference["sha256"]
            or bundle.get("bundle_id") != reference["id"]
        ):
            reasons.append(f"bundle identity mismatch {name}")
    if freeze.get("bundles", {}).get("ROBUST", {}).get("id") != "robust_bundle_204aa1c051dd":
        reasons.append("ROBUST identity changed")
    return {
        "valid": not reasons,
        "reasons": reasons,
        "freeze_id": freeze.get("training_manifest_freeze_id"),
        "freeze_sha256": freeze.get("training_manifest_freeze_sha256"),
        "path": str(path),
    }


def model_root(roots: PortableRoots) -> Path:
    return roots.models / "Original Trainable Checkpoint"


def verify_models(roots: PortableRoots) -> dict[str, Any]:
    observed: dict[str, Any] = {}
    for name, (_, expected) in CHECKPOINT_FILES.items():
        path = model_root(roots) / name
        if not path.is_file():
            raise HandoffError(f"Required model asset is absent: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise HandoffError(f"Model asset hash mismatch: {name}")
        observed[name] = {"bytes": path.stat().st_size, "sha256": actual}
    return observed


def acquire_models(roots: PortableRoots) -> dict[str, Any]:
    """Download the exact authoritative revision and stop on any hash mismatch."""
    destination = model_root(roots)
    destination.mkdir(parents=True, exist_ok=True)
    base = (
        "https://huggingface.co/Zengwei/"
        "icefall-asr-librispeech-streaming-zipformer-2023-05-17/resolve/"
        f"{CHECKPOINT_REVISION}/"
    )
    for name, (relative, expected) in CHECKPOINT_FILES.items():
        target = destination / name
        if target.is_file() and sha256_file(target) == expected:
            continue
        partial = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(base + relative, partial)
        if sha256_file(partial) != expected:
            partial.unlink(missing_ok=True)
            raise HandoffError(f"Downloaded model asset hash mismatch: {name}")
        partial.replace(target)
    return verify_models(roots)


def package_model_inventory(
    roots: PortableRoots, *, experiment_id: str, output: Path | None = None
) -> dict[str, Any]:
    queue_path = runtime_root(roots) / "registries" / "original_adapter_queue.json"
    queue = _read_json(queue_path)
    matches = [job for job in queue["jobs"] if job["experiment_id"] == experiment_id]
    if len(matches) != 1:
        raise HandoffError(f"Unknown experiment: {experiment_id}")
    job = matches[0]
    result_path = roots.runs / "adapters" / job["run_id"] / "result.json"
    result = _read_json(result_path)
    checkpoint = resolve_logical_path(result["BEST_CHECKPOINT_PATH"], roots)
    payload = {
        "schema_version": "trained-model-transfer-manifest.v1",
        "experiment_id": experiment_id,
        "checkpoint_id": result["BEST_CHECKPOINT_ID"],
        "checkpoint_sha256": sha256_file(checkpoint),
        "checkpoint_size": checkpoint.stat().st_size,
        "bundle_id": job["bundle_id"],
        "training_recipe_id": queue["training_recipe_id"],
        "model_lineage": "Original LibriSpeech streaming Zipformer2",
        "export_readiness": bool(result.get("EXPORT_READY")),
        "transport": "operator-selected; binary is not added to Git",
    }
    digest = canonical_sha256(payload)
    manifest = {**payload, "transfer_manifest_sha256": digest}
    destination = output or (
        roots.runs / "transfer_manifests" / f"{experiment_id.lower()}_{digest[:12]}.json"
    )
    atomic_json(destination, manifest)
    return {**manifest, "manifest_path": str(destination)}


def _default_roots() -> PortableRoots:
    return portable_roots(Path(__file__).resolve().parents[3])


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("build-successor", "verify-successor", "verify-models", "acquire-models", "package-model"),
    )
    parser.add_argument("--experiment-id")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(list(argv) if argv is not None else None)
    roots = _default_roots()
    try:
        if args.action == "build-successor":
            result = build_successor(roots)
        elif args.action == "verify-successor":
            result = verify_successor(roots)
        elif args.action == "verify-models":
            result = verify_models(roots)
        elif args.action == "acquire-models":
            result = acquire_models(roots)
        else:
            if not args.experiment_id:
                raise HandoffError("--experiment-id is required")
            result = package_model_inventory(
                roots, experiment_id=args.experiment_id, output=args.output
            )
    except (HandoffError, FileNotFoundError, KeyError, ValueError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2))
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
