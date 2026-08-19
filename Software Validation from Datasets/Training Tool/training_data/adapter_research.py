"""Plan, control, and validate the Original-only Phase-5 adapter queue.

This module is the Windows-side control plane.  Model execution is delegated to
``adapter_runtime.py`` in the pinned WSL environment so routine operators never
need to activate Linux manually.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import sentencepiece as spm

from training_data.common_voice import sha256_file
from training_data.handoff import (
    SUCCESSOR_FREEZE_NAME,
    SUCCESSOR_RUNTIME_NAME,
    build_successor,
    verify_successor,
)
from training_data.phase4 import default_paths as phase4_default_paths
from training_data.phase4 import verify_phase4_freeze
from training_data.portability import (
    PortabilityError,
    PortableRoots,
    discover_wsl_distro,
    portable_roots,
    resolve_logical_path,
    wsl_home,
)
from training_data.registry import _frame_hash


PHASE4_ID = "training_manifest_freeze_phase4_cc2909f344d0"
PHASE4_SHA256 = "CC2909F344D01E9007EF648BA71277188DF26741CBEA5D1D2B0933116CE6DF92"
CHECKPOINT_ID = "zengwei_librispeech_streaming_zipformer_2023_05_17_37cb5606808f"
CHECKPOINT_SHA256 = "E44BB7C8D3985A7CF0089020D227AECD71E323DCAAABCAED90E4A792E1385342"
TOKENIZER_ID = "sentencepiece_bpe500_c53433de083c"
TOKENIZER_SHA256 = "C53433DE083C4A6AD12D034550EF22DE68CEC62C4F58932A7B6B8B2F1E743FA5"
TOKENS_SHA256 = "49E3C2646595FD907228B3C6787069658F67B17377C60AEB8619C4551B2316FB"
ICEFALL_COMMIT = "3f848bb6d0acc970c9b294a30ca0a04a7c9c78d1"
SAMPLER_VERSION = "dataset_group_source_rotating_view.v1"
SAMPLER_SEED = "just-peachy-phase4-training-sampler-v1"
SUCCESSOR_NAME = SUCCESSOR_RUNTIME_NAME
TEXT_NORMALIZATION_ID = "english_bpe500_training_text_nfkd_ascii_upper_v1"


EXPERIMENTS: tuple[tuple[str, str, str, bool], ...] = (
    ("O-AGE", "AGE", "strict", False),
    ("O-AMI", "AMI", "strict", False),
    ("O-CHIME", "CHIME", "strict", True),
    ("O-VOICES", "VOICES", "strict", False),
    ("O-ROBUST", "ROBUST", "strict", True),
    ("O-AGE-ROBUST", "AGE_ROBUST", "strict", True),
    ("O-CMU", "CMU_EXPLORATORY", "exploratory", False),
    (
        "O-AGE-ROBUST-CMU",
        "AGE_ROBUST_CMU_EXPLORATORY",
        "exploratory",
        True,
    ),
)

BUNDLE_FILES = {
    "AGE": "age.json",
    "AMI": "ami.json",
    "CHIME": "chime.json",
    "VOICES": "voices.json",
    "ROBUST": "robust.json",
    "AGE_ROBUST": "age_robust.json",
    "CMU_EXPLORATORY": "cmu_exploratory.json",
    "AGE_ROBUST_CMU_EXPLORATORY": "age_robust_cmu_exploratory.json",
}

SOURCE_FILES = {
    "common_voice": "age_train.parquet",
    "ami": "ami_train.parquet",
    "chime6": "chime_train.parquet",
    "voices": "voices_train.parquet",
    "cmu_arctic": "cmu_relaxed_exploratory_train.parquet",
}

DEV_FILES = {
    "common_voice": "age_dev.parquet",
    "ami": "ami_dev.parquet",
    "chime6": "chime_dev.parquet",
    "voices": "voices_dev.parquet",
    "cmu_arctic": "cmu_relaxed_exploratory_dev.parquet",
}


class AdapterResearchError(RuntimeError):
    """Raised when a Phase-5 stop condition is encountered."""


@dataclass(frozen=True)
class AdapterPaths:
    repository_root: Path
    data_root: Path
    training_root: Path
    model_root: Path | None = None
    run_root: Path | None = None

    @property
    def roots(self) -> PortableRoots:
        return PortableRoots(
            self.repository_root,
            self.data_root,
            self.training_root,
            self.model_root or self.repository_root / "models",
            self.run_root or self.training_root / "runs",
        )

    @property
    def tool_root(self) -> Path:
        return (
            self.repository_root / "Software Validation from Datasets" / "Training Tool"
        )

    @property
    def phase4_root(self) -> Path:
        return self.training_root / "successors" / "phase4_training_manifests_v1"

    @property
    def successor_freeze_root(self) -> Path:
        return self.training_root / "successors" / SUCCESSOR_FREEZE_NAME

    @property
    def successor_freeze_path(self) -> Path:
        return (
            self.successor_freeze_root
            / "registries"
            / "training_manifest_freeze_successor.json"
        )

    @property
    def root(self) -> Path:
        return self.training_root / "successors" / SUCCESSOR_NAME

    @property
    def configs(self) -> Path:
        return self.tool_root / "configs"

    @property
    def framework_manifests(self) -> Path:
        return self.root / "framework_manifests"

    @property
    def registries(self) -> Path:
        return self.root / "registries"

    @property
    def audits(self) -> Path:
        return self.root / "audits"

    @property
    def runs(self) -> Path:
        return (self.run_root or self.training_root / "runs") / "adapters"

    @property
    def qualification(self) -> Path:
        return self.root / "qualification"

    @property
    def queue_path(self) -> Path:
        return self.registries / "original_adapter_queue.json"

    @property
    def status_path(self) -> Path:
        override = os.environ.get("JP_ADAPTER_STATUS_ROOT")
        return (Path(override).resolve() if override else self.root) / "queue_status.json"

    @property
    def stop_path(self) -> Path:
        return self.root / "STOP_REQUESTED.json"


def default_paths() -> AdapterPaths:
    roots = portable_roots(Path(__file__).resolve().parents[3])
    return AdapterPaths(
        roots.repository, roots.data, roots.training, roots.models, roots.runs
    )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest().upper()


def stable_u64(*parts: object) -> int:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest()[:8], "big")


def deterministic_view_index(
    bundle_id: str, epoch_index: int, source_group_id: str, available: int
) -> int:
    if epoch_index < 0 or available < 1:
        raise ValueError("Invalid deterministic view bounds")
    return (
        stable_u64(
            SAMPLER_VERSION,
            SAMPLER_SEED,
            bundle_id,
            epoch_index,
            source_group_id,
        )
        % available
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if path.is_file() and path.read_bytes() == temporary.read_bytes():
                temporary.unlink()
                return
            if attempt == 4:
                raise
            time.sleep(0.2 * (attempt + 1))


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _verify_identity(
    path: Path, *, id_key: str, sha_key: str, prefix: str
) -> dict[str, Any]:
    document = read_json(path)
    canonical = {k: v for k, v in document.items() if k not in {id_key, sha_key}}
    observed = canonical_sha256(canonical)
    expected_id = f"{prefix}_{observed[:12].lower()}"
    if document.get(sha_key) != observed or document.get(id_key) != expected_id:
        raise AdapterResearchError(f"Identity verification failed: {path}")
    return document


def load_frozen_configs(paths: AdapterPaths) -> dict[str, dict[str, Any]]:
    return {
        "recipe": _verify_identity(
            paths.configs / "original_adapter_recipe.v1.json",
            id_key="recipe_id",
            sha_key="recipe_sha256",
            prefix="original_adapter_recipe",
        ),
        "budget": _verify_identity(
            paths.configs / "original_adapter_budget_policy.v1.json",
            id_key="policy_id",
            sha_key="policy_sha256",
            prefix="original_adapter_budget_policy",
        ),
        "environment": _verify_identity(
            paths.configs / "original_adapter_environment_lock.v1.json",
            id_key="environment_id",
            sha_key="environment_sha256",
            prefix="original_adapter_environment",
        ),
        "provenance": _verify_identity(
            paths.configs / "original_adapter_provenance.v1.json",
            id_key="provenance_id",
            sha_key="provenance_sha256",
            prefix="original_adapter_provenance",
        ),
    }


def verify_parent(paths: AdapterPaths) -> dict[str, Any]:
    freeze = paths.phase4_root / "registries" / "training_manifest_freeze_phase4.json"
    result = verify_phase4_freeze(freeze, paths=phase4_default_paths())
    if not result["valid"]:
        raise AdapterResearchError(
            "Phase-4 parent verification failed: " + "; ".join(result["reasons"])
        )
    if result["freeze_id"] != PHASE4_ID or result["freeze_sha256"] != PHASE4_SHA256:
        raise AdapterResearchError("Phase-4 parent identity is not the required freeze")
    return result


def active_freeze(paths: AdapterPaths) -> dict[str, Any]:
    result = verify_successor(paths.roots)
    if not result["valid"]:
        raise AdapterResearchError(
            "Portable successor verification failed: " + "; ".join(result["reasons"])
        )
    return read_json(paths.successor_freeze_path)


def active_bundle_path(paths: AdapterPaths, bundle_name: str) -> Path:
    freeze = active_freeze(paths)
    try:
        logical = freeze["bundles"][bundle_name]["logical_path"]
    except KeyError as exc:
        raise AdapterResearchError(f"Successor bundle is absent: {bundle_name}") from exc
    try:
        return resolve_logical_path(logical, paths.roots)
    except PortabilityError as exc:
        raise AdapterResearchError(str(exc)) from exc


def verify_initialization(paths: AdapterPaths) -> dict[str, Any]:
    root = paths.roots.models / "Original Trainable Checkpoint"
    expected = {
        "pretrained.pt": CHECKPOINT_SHA256,
        "bpe.model": TOKENIZER_SHA256,
        "tokens.txt": TOKENS_SHA256,
    }
    observed = {}
    for name, digest in expected.items():
        path = root / name
        if not path.is_file():
            raise AdapterResearchError(
                f"Required Original initialization is absent: {path}"
            )
        actual = sha256_file(path)
        if actual != digest:
            raise AdapterResearchError(f"Original initialization hash mismatch: {name}")
        observed[name] = {"bytes": path.stat().st_size, "sha256": actual}
    return observed


def normalize_training_text(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").upper()
    text = text.replace("_", " ").replace("’", "'")
    normalized = []
    for char in text:
        normalized.append(char if char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ' " else " ")
    return " ".join("".join(normalized).split())


def recipe_source_text(value: object, dataset_id: object) -> tuple[str, str | None]:
    text = str(value or "")
    if str(dataset_id) == "common_voice" and any(char in text for char in "\t\r\n"):
        head = text.splitlines()[0].split("\t", 1)[0].strip()
        if head:
            return head, "common_voice_embedded_tsv_tail_removed"
    return text, None


def text_normalization_sha256() -> str:
    payload = {
        "id": TEXT_NORMALIZATION_ID,
        "unicode": "NFKD then ASCII transliteration by dropping non-ASCII marks",
        "case": "uppercase",
        "underscore": "space",
        "allowed": "A-Z apostrophe and space",
        "whitespace": "collapsed",
        "common_voice_embedded_tsv_tail": "retain the Phase-4 row and raw transcript, but derive the recipe target from the non-empty first TSV field and record the correction",
        "empty_rows": "punctuation-only or source-empty rows are preserved and reported as explicit blank transducer targets; lexical rows normalizing empty are blocking",
    }
    return canonical_sha256(payload)


def _logical_source(path: Path, paths: AdapterPaths) -> str:
    return "JP_TRAINING_ROOT:" + path.relative_to(paths.training_root).as_posix()


def _audio_paths(frame: pd.DataFrame, paths: AdapterPaths) -> pd.Series:
    result = []
    for root_id, relative in zip(
        frame["audio_root_id"], frame["audio_relative_path"], strict=True
    ):
        try:
            result.append(
                str(
                    resolve_logical_path(
                        f"{root_id}:{relative}", paths.roots, use_asset_aliases=True
                    )
                )
            )
        except PortabilityError as exc:
            raise AdapterResearchError(str(exc)) from exc
    return pd.Series(result, index=frame.index, dtype="string")


def _segment_indexes(paths: AdapterPaths) -> tuple[pd.DataFrame, pd.DataFrame]:
    normalized = paths.data_root / "Normalized Metadata"
    ami = pd.read_parquet(
        normalized / "AMI" / "segments.parquet",
        columns=["segment_ref_id", "recording_id", "start_sec", "end_sec"],
    ).drop_duplicates(["segment_ref_id", "recording_id"])
    chime = pd.read_parquet(
        normalized / "CHiME_6" / "utterances.parquet",
        columns=["utterance_key", "start_sec", "end_sec"],
    ).drop_duplicates("utterance_key")
    return ami, chime


def derive_framework_manifest(
    source: Path,
    destination: Path,
    *,
    paths: AdapterPaths,
    ami_index: pd.DataFrame,
    chime_index: pd.DataFrame,
    tokenizer: spm.SentencePieceProcessor,
    bundle_bindings: list[dict[str, str]],
) -> dict[str, Any]:
    frame = pd.read_parquet(source)
    source_descriptor = read_json(source.with_suffix(".manifest.json"))
    source_manifest_sha256 = _frame_hash(frame)
    if source_descriptor["manifest_sha256"] != source_manifest_sha256:
        raise AdapterResearchError(f"Phase-4 source descriptor mismatch: {source}")
    original_rows = len(frame)
    datasets = set(frame["dataset_id"].astype(str))
    if datasets == {"ami"}:
        frame = frame.merge(
            ami_index,
            how="left",
            left_on=["source_utterance_id", "source_recording_id"],
            right_on=["segment_ref_id", "recording_id"],
            validate="many_to_one",
        ).drop(columns=["segment_ref_id", "recording_id"])
    elif datasets == {"chime6"}:
        frame = frame.merge(
            chime_index,
            how="left",
            left_on="acoustic_view_id",
            right_on="utterance_key",
            validate="many_to_one",
        ).drop(columns=["utterance_key"])
    else:
        frame["start_sec"] = 0.0
        frame["end_sec"] = frame["duration_seconds"].astype(float)
    if len(frame) != original_rows:
        raise AdapterResearchError(f"Derived manifest changed membership: {source}")
    frame["source_duration_seconds"] = frame["duration_seconds"]
    frame["segment_correction"] = None
    reversed_endpoints = frame["end_sec"] < frame["start_sec"]
    reversed_count = int(reversed_endpoints.sum())
    if reversed_count:
        original_start = frame.loc[reversed_endpoints, "start_sec"].copy()
        frame.loc[reversed_endpoints, "start_sec"] = frame.loc[
            reversed_endpoints, "end_sec"
        ]
        frame.loc[reversed_endpoints, "end_sec"] = original_start
        frame.loc[reversed_endpoints, "duration_seconds"] = (
            frame.loc[reversed_endpoints, "end_sec"]
            - frame.loc[reversed_endpoints, "start_sec"]
        )
        frame.loc[reversed_endpoints, "segment_correction"] = (
            "reversed_source_endpoints_swapped"
        )
    recipe_sources = [
        recipe_source_text(raw, dataset)
        for raw, dataset in zip(
            frame["raw_transcript"], frame["dataset_id"], strict=True
        )
    ]
    frame["transcript_correction"] = [item[1] for item in recipe_sources]
    frame["training_text"] = [
        normalize_training_text(item[0]) for item in recipe_sources
    ]
    frame["training_text_sha256"] = frame["training_text"].map(
        lambda text: hashlib.sha256(text.encode("utf-8")).hexdigest().upper()
    )
    resolved_audio_paths = _audio_paths(frame, paths)
    missing_segments = int(frame[["start_sec", "end_sec"]].isna().any(axis=1).sum())
    invalid_segments = int(
        (
            (frame["start_sec"].fillna(-1) < 0)
            | (frame["end_sec"].fillna(-1) <= frame["start_sec"].fillna(0))
        ).sum()
    )
    empty_mask = frame["training_text"].eq("")
    nonlexical_blank = int(empty_mask.sum())
    invalid_text = int(
        (
            empty_mask
            & pd.Series([item[0] for item in recipe_sources], index=frame.index)
            .fillna("")
            .astype(str)
            .str.contains(r"[A-Za-z0-9]", regex=True)
        ).sum()
    )
    unique_audio = resolved_audio_paths.drop_duplicates()
    missing_audio_paths = [value for value in unique_audio if not Path(value).is_file()]
    if missing_segments or invalid_segments or invalid_text or missing_audio_paths:
        raise AdapterResearchError(
            f"Derived manifest audit failed for {source.name}: "
            f"missing_segments={missing_segments}, invalid_segments={invalid_segments}, "
            f"invalid_text={invalid_text}, missing_audio={len(missing_audio_paths)}"
        )
    unknown_id = tokenizer.unk_id()
    unknown_occurrences = 0
    tokenization_failures = 0
    max_token_count = 0
    token_counts: dict[str, int] = {}
    unique_texts = frame["training_text"].drop_duplicates().tolist()
    for start in range(0, len(unique_texts), 10_000):
        try:
            encoded = tokenizer.encode(
                unique_texts[start : start + 10_000], out_type=int
            )
        except Exception:
            tokenization_failures += len(unique_texts[start : start + 10_000])
            continue
        for text, token_ids in zip(
            unique_texts[start : start + 10_000], encoded, strict=True
        ):
            unknown_occurrences += token_ids.count(unknown_id)
            max_token_count = max(max_token_count, len(token_ids))
            token_counts[text] = len(token_ids)
    if tokenization_failures or unknown_occurrences:
        raise AdapterResearchError(
            f"Tokenizer audit failed for {source.name}: "
            f"failures={tokenization_failures}, unknown_tokens={unknown_occurrences}"
        )
    frame["bpe_token_count"] = frame["training_text"].map(token_counts).astype("int64")
    frame["model_input_duration_seconds"] = pd.concat(
        [
            frame["duration_seconds"].astype(float),
            pd.Series(1.0, index=frame.index),
            frame["bpe_token_count"].astype(float) * 0.05,
        ],
        axis=1,
    ).max(axis=1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    frame.to_parquet(temporary, index=False)
    temporary.replace(destination)
    derived_hash = _frame_hash(frame)
    sidecar = {
        "schema_version": "icefall-derived-manifest-phase5.v1",
        "phase4_parent_id": PHASE4_ID,
        "phase4_parent_sha256": PHASE4_SHA256,
        "bundle_bindings": bundle_bindings,
        "sampler_policy_id": SAMPLER_VERSION,
        "sampler_seed": SAMPLER_SEED,
        "source_manifest_id": source_descriptor["manifest_id"],
        "source_manifest_path": _logical_source(source, paths),
        "source_manifest_sha256": source_manifest_sha256,
        "derived_manifest_path": _logical_source(destination, paths),
        "derived_manifest_sha256": derived_hash,
        "rows": original_rows,
        "unique_source_groups": int(frame["source_group_id"].nunique()),
        "unique_audio_files": int(len(unique_audio)),
        "effective_unique_audio_hours": float(
            frame.groupby("source_group_id", sort=False)["duration_seconds"]
            .first()
            .sum()
            / 3600
        ),
        "text_normalization_id": TEXT_NORMALIZATION_ID,
        "text_normalization_sha256": text_normalization_sha256(),
        "missing_audio": 0,
        "invalid_segments": 0,
        "reversed_segment_endpoints_corrected": reversed_count,
        "transcript_repairs": int(frame["transcript_correction"].notna().sum()),
        "invalid_training_text": 0,
        "blank_nonlexical_training_rows": nonlexical_blank,
        "blank_nonlexical_policy": "preserved as an empty transducer target; never dropped or replaced with invented lexical content",
        "tokenization_failures": 0,
        "unknown_token_occurrences": 0,
        "maximum_bpe_tokens": max_token_count,
        "maximum_model_input_duration_seconds": float(
            frame["model_input_duration_seconds"].max()
        ),
        "membership_preserved": True,
    }
    sidecar_hash = canonical_sha256(sidecar)
    sidecar["manifest_id"] = f"icefall_derived_manifest_{sidecar_hash[:12].lower()}"
    sidecar["manifest_sha256"] = sidecar_hash
    atomic_json(destination.with_suffix(".manifest.json"), sidecar)
    return sidecar


def materialize_framework_manifests(paths: AdapterPaths) -> dict[str, Any]:
    ami_index, chime_index = _segment_indexes(paths)
    tokenizer = spm.SentencePieceProcessor(
        model_file=str(
            paths.roots.models / "Original Trainable Checkpoint" / "bpe.model"
        )
    )
    bundles = [
        read_json(active_bundle_path(paths, bundle_name))
        for bundle_name in BUNDLE_FILES
    ]
    bundle_bindings = [
        {"bundle_id": item["bundle_id"], "bundle_sha256": item["bundle_sha256"]}
        for item in bundles
    ]
    dataset_bundle_bindings = {
        dataset: [
            binding
            for item, binding in zip(bundles, bundle_bindings, strict=True)
            if dataset
            in {str(source["dataset_id"]) for source in item["train_sources"]}
        ]
        for dataset in SOURCE_FILES
    }
    references: dict[str, Any] = {}
    train_sources: dict[str, Path] = {}
    for bundle in bundles:
        for source in bundle["train_sources"]:
            dataset = str(source["dataset_id"])
            source_path = resolve_logical_path(source["manifest_path"], paths.roots)
            previous = train_sources.setdefault(dataset, source_path)
            if previous != source_path:
                raise AdapterResearchError(
                    f"Conflicting successor TRAIN manifest for {dataset}"
                )
    for dataset, name in SOURCE_FILES.items():
        destination = paths.framework_manifests / "train" / name
        references[f"train:{dataset}"] = derive_framework_manifest(
            train_sources[dataset],
            destination,
            paths=paths,
            ami_index=ami_index,
            chime_index=chime_index,
            tokenizer=tokenizer,
            bundle_bindings=dataset_bundle_bindings[dataset],
        )
    dev_sources: dict[str, Path] = {}
    for bundle in bundles:
        for reference in bundle["dev_manifests"]:
            source_path = resolve_logical_path(reference["manifest_path"], paths.roots)
            dev_sources.setdefault(source_path.name, source_path)
    for dataset, name in DEV_FILES.items():
        destination = paths.framework_manifests / "dev" / name
        references[f"dev:{dataset}"] = derive_framework_manifest(
            dev_sources[name],
            destination,
            paths=paths,
            ami_index=ami_index,
            chime_index=chime_index,
            tokenizer=tokenizer,
            bundle_bindings=dataset_bundle_bindings[dataset],
        )
    monitor_source = (
        paths.phase4_root / "monitoring" / "clean_regression_monitor.parquet"
    )
    references["monitor:librispeech"] = derive_framework_manifest(
        monitor_source,
        paths.framework_manifests / "monitor" / monitor_source.name,
        paths=paths,
        ami_index=ami_index,
        chime_index=chime_index,
        tokenizer=tokenizer,
        bundle_bindings=bundle_bindings,
    )
    audit = {
        "schema_version": "phase5a-framework-manifest-audit.v1",
        "phase4_parent_id": PHASE4_ID,
        "phase4_parent_sha256": PHASE4_SHA256,
        "successor_freeze_id": active_freeze(paths)["training_manifest_freeze_id"],
        "successor_freeze_sha256": active_freeze(paths)[
            "training_manifest_freeze_sha256"
        ],
        "text_normalization_id": TEXT_NORMALIZATION_ID,
        "text_normalization_sha256": text_normalization_sha256(),
        "manifests": references,
        "all_memberships_preserved": all(
            item["membership_preserved"] for item in references.values()
        ),
        "total_missing_audio": sum(
            item["missing_audio"] for item in references.values()
        ),
        "total_invalid_segments": sum(
            item["invalid_segments"] for item in references.values()
        ),
        "total_reversed_segment_endpoints_corrected": sum(
            item["reversed_segment_endpoints_corrected"] for item in references.values()
        ),
        "total_transcript_repairs": sum(
            item["transcript_repairs"] for item in references.values()
        ),
        "total_invalid_training_text": sum(
            item["invalid_training_text"] for item in references.values()
        ),
        "total_tokenization_failures": sum(
            item["tokenization_failures"] for item in references.values()
        ),
        "total_unknown_token_occurrences": sum(
            item["unknown_token_occurrences"] for item in references.values()
        ),
        "common_voice_heldout_included": True,
        "former_common_voice_heldout_reclassified_to_train": True,
        "common_voice_dev_used_for_gradients": False,
        "large_accessed": False,
    }
    atomic_json(paths.audits / "framework_manifest_audit.json", audit)
    return audit


def derive_budget(
    bundle: Mapping[str, Any],
    source_sidecars: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> tuple[int, float, dict[str, float]]:
    contributions: dict[str, float] = {}
    for source in bundle["train_sources"]:
        dataset = str(source["dataset_id"])
        hours = float(
            source_sidecars[f"train:{dataset}"]["effective_unique_audio_hours"]
        )
        contributions[dataset] = float(Decimal(source["probability"])) * hours
    weighted_hours = sum(contributions.values())
    raw = (
        float(policy["source_passes"])
        * weighted_hours
        * 3600
        / float(policy["effective_audio_seconds_per_optimizer_step"])
    )
    steps = math.ceil(
        min(
            float(policy["maximum_optimizer_steps"]),
            max(float(policy["minimum_optimizer_steps"]), raw),
        )
    )
    return steps, weighted_hours, contributions


def _scientific_run_identity(
    experiment_id: str,
    bundle: Mapping[str, Any],
    training_class: str,
    max_steps: int,
    configs: Mapping[str, Mapping[str, Any]],
    successor: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "original-adapter-training-run-identity.v1",
        "experiment_id": experiment_id,
        "training_class": training_class,
        "phase4_freeze_id": PHASE4_ID,
        "phase4_freeze_sha256": PHASE4_SHA256,
        "successor_freeze_id": successor["training_manifest_freeze_id"],
        "successor_freeze_sha256": successor["training_manifest_freeze_sha256"],
        "bundle_id": bundle["bundle_id"],
        "bundle_sha256": bundle["bundle_sha256"],
        "initialization_checkpoint_id": CHECKPOINT_ID,
        "initialization_checkpoint_sha256": CHECKPOINT_SHA256,
        "tokenizer_id": TOKENIZER_ID,
        "tokenizer_sha256": TOKENIZER_SHA256,
        "adapter_implementation_id": configs["recipe"]["implementation"]["id"],
        "adapter_implementation_commit": ICEFALL_COMMIT,
        "training_recipe_id": configs["recipe"]["recipe_id"],
        "training_recipe_sha256": configs["recipe"]["recipe_sha256"],
        "training_budget_policy_id": configs["budget"]["policy_id"],
        "training_budget_policy_sha256": configs["budget"]["policy_sha256"],
        "max_optimizer_steps": max_steps,
        "sampler_algorithm_version": SAMPLER_VERSION,
        "sampler_seed": SAMPLER_SEED,
        "training_seed": configs["recipe"]["control"]["training_seed"],
        "environment_id": configs["environment"]["environment_id"],
        "environment_sha256": configs["environment"]["environment_sha256"],
        "checkpoint_selection_policy_id": bundle["policies"]["checkpoint_selection"][
            "id"
        ],
        "checkpoint_selection_policy_sha256": bundle["policies"][
            "checkpoint_selection"
        ]["sha256"],
    }


def materialize_queue(paths: AdapterPaths, audit: Mapping[str, Any]) -> dict[str, Any]:
    configs = load_frozen_configs(paths)
    successor = active_freeze(paths)
    jobs = []
    for order, (experiment_id, bundle_name, training_class, chime_review) in enumerate(
        EXPERIMENTS, start=1
    ):
        bundle_path = active_bundle_path(paths, bundle_name)
        bundle = read_json(bundle_path)
        max_steps, weighted_hours, contributions = derive_budget(
            bundle, audit["manifests"], configs["budget"]
        )
        identity = _scientific_run_identity(
            experiment_id, bundle, training_class, max_steps, configs, successor
        )
        digest = canonical_sha256(identity)
        jobs.append(
            {
                "queue_order": order,
                "experiment_id": experiment_id,
                "training_class": training_class,
                "bundle_name": bundle_name,
                "bundle_id": bundle["bundle_id"],
                "bundle_sha256": bundle["bundle_sha256"],
                "bundle_path": _logical_source(bundle_path, paths),
                "derived_training_budget_optimizer_steps": max_steps,
                "weighted_unique_source_hours": weighted_hours,
                "weighted_hour_contributions": contributions,
                "run_id": f"original_adapter_run_{digest[:12].lower()}",
                "run_sha256": digest,
                "run_identity": identity,
                "chime_used_in_training": bool(
                    bundle["license"]["chime_used_in_training"]
                ),
                "commercial_model_release_review_required": chime_review,
                "cmu_experiment_class": training_class,
            }
        )
    if [item["experiment_id"] for item in jobs] != [item[0] for item in EXPERIMENTS]:
        raise AdapterResearchError("Queue order changed")
    if any(not item["experiment_id"].startswith("O-") for item in jobs):
        raise AdapterResearchError("Non-Original job entered the queue")
    canonical = {
        "schema_version": "original-adapter-queue-phase5a.v1",
        "phase4_parent_id": PHASE4_ID,
        "phase4_parent_sha256": PHASE4_SHA256,
        "successor_freeze_id": successor["training_manifest_freeze_id"],
        "successor_freeze_sha256": successor["training_manifest_freeze_sha256"],
        "training_recipe_id": configs["recipe"]["recipe_id"],
        "training_recipe_sha256": configs["recipe"]["recipe_sha256"],
        "training_budget_policy_id": configs["budget"]["policy_id"],
        "training_budget_policy_sha256": configs["budget"]["policy_sha256"],
        "environment_id": configs["environment"]["environment_id"],
        "environment_sha256": configs["environment"]["environment_sha256"],
        "jobs": jobs,
        "total_jobs": 8,
        "giga_jobs": 0,
    }
    digest = canonical_sha256(canonical)
    queue = {
        **canonical,
        "queue_id": f"adapter_queue_{digest[:12].lower()}",
        "queue_sha256": digest,
    }
    atomic_json(paths.queue_path, queue)
    if not paths.status_path.exists():
        atomic_json(paths.status_path, initial_status(queue))
    return queue


def initial_status(queue: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "QUEUE_ID": queue["queue_id"],
        "QUEUE_STATE": "planned",
        "COMPLETED_EXPERIMENTS": 0,
        "TOTAL_EXPERIMENTS": 8,
        "CURRENT_EXPERIMENT_ID": None,
        "CURRENT_STEP": 0,
        "MAX_STEP_OR_EQUIVALENT": None,
        "PROGRESS_PERCENT": 0.0,
        "MODEL_ELAPSED_SECONDS": 0.0,
        "EMA_SECONDS_PER_STEP": None,
        "MODEL_ETA_SECONDS": None,
        "QUEUE_ELAPSED_SECONDS": 0.0,
        "QUEUE_ETA_SECONDS": None,
        "LATEST_TRAIN_LOSS": None,
        "LATEST_DEV_OBJECTIVE": None,
        "LATEST_PER_DOMAIN_DEV_METRICS": {},
        "LATEST_CLEAN_MONITOR_METRIC": None,
        "PEAK_VRAM_GIB": None,
        "CURRENT_CHECKPOINT": None,
        "BEST_CHECKPOINT": None,
        "LAST_HEARTBEAT_UTC": utc_now(),
        "FAILURE_REASON": None,
    }


def plan(paths: AdapterPaths, *, rebuild_manifests: bool = False) -> dict[str, Any]:
    parent = verify_parent(paths)
    successor = build_successor(paths.roots)
    initialization = verify_initialization(paths)
    load_frozen_configs(paths)
    audit_path = paths.audits / "framework_manifest_audit.json"
    if rebuild_manifests or not audit_path.is_file():
        audit = materialize_framework_manifests(paths)
    else:
        audit = read_json(audit_path)
        if not _framework_manifests_valid(paths, audit):
            audit = materialize_framework_manifests(paths)
    queue = materialize_queue(paths, audit)
    return {
        "status": "planned",
        "phase4_parent": parent,
        "successor_freeze": {
            "id": successor["training_manifest_freeze_id"],
            "sha256": successor["training_manifest_freeze_sha256"],
            "path": str(paths.successor_freeze_path),
        },
        "initialization": initialization,
        "framework_manifest_audit": audit,
        "queue": queue,
    }


def _qualification(paths: AdapterPaths) -> dict[str, Any] | None:
    path = paths.qualification / "canary_summary.json"
    return read_json(path) if path.is_file() else None


def estimate(paths: AdapterPaths) -> dict[str, Any]:
    queue = (
        read_json(paths.queue_path)
        if paths.queue_path.is_file()
        else plan(paths)["queue"]
    )
    qualification = _qualification(paths)
    measured = []
    if qualification and qualification.get("ready_to_run_original_adapter_queue"):
        measured = [
            float(item["seconds_per_optimizer_step"])
            for item in qualification.get("canaries", [])
            if item.get("passed") and item.get("seconds_per_optimizer_step")
        ]
    seconds_per_step = sum(measured) / len(measured) if measured else None
    jobs = []
    for item in queue["jobs"]:
        if seconds_per_step is None:
            expected = low = high = None
        else:
            expected = (
                item["derived_training_budget_optimizer_steps"] * seconds_per_step
            )
            low, high = expected * 0.8, expected * 1.35
        jobs.append(
            {
                "EXPERIMENT_ID": item["experiment_id"],
                "DERIVED_TRAINING_BUDGET": item[
                    "derived_training_budget_optimizer_steps"
                ],
                "ESTIMATED_TIME_SECONDS": expected,
                "ESTIMATED_TIME_LOW_SECONDS": low,
                "ESTIMATED_TIME_HIGH_SECONDS": high,
            }
        )
    return {
        "QUEUE_ID": queue["queue_id"],
        "CALIBRATED": seconds_per_step is not None,
        "MEASURED_SECONDS_PER_STEP": seconds_per_step,
        "EXPERIMENTS": jobs,
        "ESTIMATED_TOTAL_QUEUE_TIME_SECONDS": (
            sum(x["ESTIMATED_TIME_SECONDS"] for x in jobs) if seconds_per_step else None
        ),
        "ESTIMATED_TOTAL_QUEUE_TIME_LOW_SECONDS": (
            sum(x["ESTIMATED_TIME_LOW_SECONDS"] for x in jobs)
            if seconds_per_step
            else None
        ),
        "ESTIMATED_TOTAL_QUEUE_TIME_HIGH_SECONDS": (
            sum(x["ESTIMATED_TIME_HIGH_SECONDS"] for x in jobs)
            if seconds_per_step
            else None
        ),
        "NOTE": None
        if seconds_per_step
        else "ETA unavailable until both measured canaries pass; no ETA was fabricated.",
    }


def _wsl_path(path: Path, *, distro: str | None = None) -> str:
    windows_path = str(path).replace("\\", "/")
    try:
        selected = discover_wsl_distro(configured=distro)
        completed = subprocess.run(
            [
                "wsl.exe",
                "-d",
                selected,
                "--",
                "wslpath",
                "-u",
                "-a",
                windows_path,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (PortabilityError, OSError, subprocess.CalledProcessError) as exc:
        if isinstance(exc, PortabilityError):
            raise AdapterResearchError(str(exc)) from exc
        detail = (
            getattr(exc, "stderr", None)
            or getattr(exc, "stdout", None)
            or str(exc)
            or "unknown wslpath error"
        ).strip()
        raise AdapterResearchError(f"Windows-to-WSL path conversion failed: {detail}") from exc
    converted = completed.stdout.strip()
    if not converted.startswith("/"):
        raise AdapterResearchError(
            f"Windows-to-WSL path conversion returned an invalid path: {converted!r}"
        )
    return converted


def _run_runtime(paths: AdapterPaths, command: str, experiment_id: str) -> int:
    environment = load_frozen_configs(paths)["environment"]
    distro = discover_wsl_distro()
    runtime = _wsl_path(Path(__file__).with_name("adapter_runtime.py"), distro=distro)
    queue = _wsl_path(paths.queue_path, distro=distro)
    linux_home = wsl_home(distro)
    wsl_python = os.environ.get("JP_WSL_PYTHON") or (
        linux_home
        + "/"
        + environment[
            "wsl_python_relative_to_home"
        ].lstrip("/")
    )
    wsl_icefall = os.environ.get("JP_ICEFALL_ROOT") or (
        linux_home
        + "/"
        + environment["wsl_icefall_relative_to_home"].lstrip("/")
    )
    root_environment = [
        f"{root_id}={_wsl_path(root, distro=distro)}"
        for root_id, root in paths.roots.as_mapping().items()
    ]
    if os.environ.get("JP_ADAPTER_STATUS_ROOT"):
        root_environment.append(
            "JP_ADAPTER_STATUS_ROOT="
            + _wsl_path(Path(os.environ["JP_ADAPTER_STATUS_ROOT"]), distro=distro)
        )
    args = [
        "wsl.exe",
        "-d",
        distro,
        "--",
        "env",
        *root_environment,
        f"JP_WSL_DISTRO={distro}",
        f"JP_ICEFALL_ROOT={wsl_icefall}",
        wsl_python,
        runtime,
        command,
        "--queue",
        queue,
        "--experiment-id",
        experiment_id,
    ]
    return subprocess.run(args, check=False).returncode


def _completed_run(paths: AdapterPaths, job: Mapping[str, Any]) -> bool:
    result = paths.runs / job["run_id"] / "result.json"
    if not result.is_file():
        return False
    data = read_json(result)
    declared_complete = bool(
        data.get("STATE") in {"completed", "early_stopped"} and data.get("EXPORT_READY")
    )
    if not declared_complete or "run_identity" not in job:
        return declared_complete
    return not _result_blockers(paths, job, data, canary=False)


def run_one(paths: AdapterPaths, experiment_id: str) -> int:
    if not paths.queue_path.is_file():
        plan(paths)
    if not validate(paths)["READY_TO_RUN_ORIGINAL_ADAPTER_QUEUE"]:
        raise AdapterResearchError(
            "All Phase-5 readiness gates, including both canaries, must pass before full training"
        )
    queue = read_json(paths.queue_path)
    matches = [x for x in queue["jobs"] if x["experiment_id"] == experiment_id]
    if len(matches) != 1:
        raise AdapterResearchError(f"Unknown experiment ID: {experiment_id}")
    if _completed_run(paths, matches[0]):
        return 0
    return _run_runtime(paths, "train", experiment_id)


def run_queue(paths: AdapterPaths) -> int:
    if not paths.queue_path.is_file():
        plan(paths)
    queue = read_json(paths.queue_path)
    for job in queue["jobs"]:
        if paths.stop_path.is_file():
            return 2
        if _completed_run(paths, job):
            continue
        code = run_one(paths, job["experiment_id"])
        if code != 0:
            return code
    return 0


def qualify(paths: AdapterPaths) -> int:
    """Run the two bounded receiver canaries; never called by Plan/Estimate."""
    if not paths.queue_path.is_file():
        plan(paths)
    for experiment_id in ("O-AGE", "O-AGE-ROBUST"):
        code = _run_runtime(paths, "canary", experiment_id)
        if code != 0:
            return code
    return 0


def request_stop(paths: AdapterPaths, reason: str) -> dict[str, Any]:
    payload = {"requested_utc": utc_now(), "reason": reason or "operator request"}
    atomic_json(paths.stop_path, payload)
    return payload


def resume(paths: AdapterPaths) -> int:
    if paths.stop_path.is_file():
        paths.stop_path.unlink()
    return run_queue(paths)


REQUIRED_STATUS_FIELDS = frozenset(initial_status({"queue_id": "fixture"}))


def status(paths: AdapterPaths) -> dict[str, Any]:
    if not paths.status_path.is_file():
        if not paths.queue_path.is_file():
            plan(paths)
        atomic_json(paths.status_path, initial_status(read_json(paths.queue_path)))
    value = read_json(paths.status_path)
    missing = REQUIRED_STATUS_FIELDS - set(value)
    if missing:
        raise AdapterResearchError(f"Status schema missing: {sorted(missing)}")
    qualification = _qualification(paths)
    if (
        qualification
        and qualification.get("ready_to_run_original_adapter_queue")
        and value["QUEUE_STATE"] == "canary_complete"
    ):
        estimate_value = estimate(paths)
        value.update(
            {
                "QUEUE_STATE": "ready",
                "CURRENT_EXPERIMENT_ID": None,
                "CURRENT_STEP": 0,
                "MAX_STEP_OR_EQUIVALENT": None,
                "PROGRESS_PERCENT": 0.0,
                "MODEL_ELAPSED_SECONDS": 0.0,
                "EMA_SECONDS_PER_STEP": None,
                "MODEL_ETA_SECONDS": None,
                "QUEUE_ELAPSED_SECONDS": 0.0,
                "QUEUE_ETA_SECONDS": estimate_value[
                    "ESTIMATED_TOTAL_QUEUE_TIME_SECONDS"
                ],
                "LATEST_TRAIN_LOSS": None,
                "LATEST_DEV_OBJECTIVE": None,
                "LATEST_PER_DOMAIN_DEV_METRICS": {},
                "LATEST_CLEAN_MONITOR_METRIC": None,
                "CURRENT_CHECKPOINT": None,
                "BEST_CHECKPOINT": None,
                "LAST_HEARTBEAT_UTC": utc_now(),
                "FAILURE_REASON": None,
            }
        )
        atomic_json(paths.status_path, value)
    return value


def compact_status(paths: AdapterPaths) -> str:
    value = status(paths)
    fields = (
        ("Queue", "QUEUE_ID"),
        ("State", "QUEUE_STATE"),
        ("Completed", "COMPLETED_EXPERIMENTS"),
        ("Current", "CURRENT_EXPERIMENT_ID"),
        ("Step", "CURRENT_STEP"),
        ("Budget", "MAX_STEP_OR_EQUIVALENT"),
        ("Progress", "PROGRESS_PERCENT"),
        ("Elapsed", "MODEL_ELAPSED_SECONDS"),
        ("Current ETA", "MODEL_ETA_SECONDS"),
        ("Queue elapsed", "QUEUE_ELAPSED_SECONDS"),
        ("Queue ETA", "QUEUE_ETA_SECONDS"),
        ("Train loss", "LATEST_TRAIN_LOSS"),
        ("DEV objective", "LATEST_DEV_OBJECTIVE"),
        ("Clean monitor", "LATEST_CLEAN_MONITOR_METRIC"),
        ("Peak VRAM GiB", "PEAK_VRAM_GIB"),
        ("Best checkpoint", "BEST_CHECKPOINT"),
        ("Last heartbeat", "LAST_HEARTBEAT_UTC"),
        ("Failure", "FAILURE_REASON"),
    )
    lines = ["JUST-PEACHY ORIGINAL ADAPTER QUEUE", ""]
    for label, key in fields:
        shown = value[key]
        if key == "COMPLETED_EXPERIMENTS":
            shown = f"{shown} / {value['TOTAL_EXPERIMENTS']}"
        elif key == "PROGRESS_PERCENT" and shown is not None:
            shown = f"{shown:.2f}%"
        lines.extend([f"{label}:", str(shown), ""])
    return "\n".join(lines).rstrip()


def _result_blockers(
    paths: AdapterPaths,
    job: Mapping[str, Any],
    result: Mapping[str, Any],
    *,
    canary: bool,
) -> list[str]:
    blockers: list[str] = []

    def require(condition: bool, reason: str) -> None:
        if not condition:
            blockers.append(reason)

    require(result.get("EXPERIMENT_ID") == job["experiment_id"], "experiment identity")
    require(result.get("TRAINING_RUN_ID") == job["run_id"], "run identity")
    require(result.get("TRAINING_RUN_SHA256") == job["run_sha256"], "run hash")
    require(result.get("BUNDLE_ID") == job["bundle_id"], "bundle identity")
    require(
        result.get("INITIALIZATION_CHECKPOINT_ID") == CHECKPOINT_ID,
        "initialization identity",
    )
    require(
        result.get("INITIALIZATION_CHECKPOINT_SHA256") == CHECKPOINT_SHA256,
        "initialization hash",
    )
    require(
        result.get("TRAINING_RECIPE_ID") == job["run_identity"]["training_recipe_id"],
        "training recipe identity",
    )
    expected_budget = 250 if canary else job["derived_training_budget_optimizer_steps"]
    require(result.get("TRAINING_BUDGET") == expected_budget, "training budget")
    require(result.get("STATE") in {"completed", "early_stopped"}, "terminal state")
    final_step = int(result.get("FINAL_STEP") or 0)
    require(0 < final_step <= expected_budget, "final step")
    if canary:
        require(final_step == 250, "complete 250-step canary")
        require(bool(result.get("CANARY_PASSED")), "canary pass declaration")
    for field in (
        "FINITE_LOSS_CHECK",
        "BACKBONE_FROZEN_CHECK",
        "ADAPTER_CHANGED_CHECK",
        "BEST_CHECKPOINT_RELOAD_CHECK",
        "RESUME_CHECK",
        "OPTIMIZER_ADAPTER_ONLY_CHECK",
        "DEV_COMPLETE",
        "MONITOR_COMPLETE",
        "PHASE4_WEIGHTS_RESPECTED",
    ):
        require(bool(result.get(field)), field)
    require(not result.get("HELDOUT_USED"), "heldout exclusion")
    require(not result.get("MONITOR_USED_FOR_GRADIENTS"), "monitor gradient exclusion")
    require(not result.get("LARGE_ACCESSED"), "Large exclusion")
    require(bool(result.get("PER_DOMAIN_DEV_METRICS")), "per-domain DEV metrics")
    require(
        result.get("BEST_DEV_OBJECTIVE") is not None,
        "best DEV objective",
    )
    require(
        result.get("INITIAL_CLEAN_MONITOR_METRIC") is not None
        and result.get("BEST_CLEAN_MONITOR_METRIC") is not None,
        "clean monitor metrics",
    )
    peak = float(result.get("PEAK_GPU_VRAM_GIB") or 0.0)
    total = float(result.get("GPU_TOTAL_GIB") or 0.0)
    require(bool(result.get("GPU_NAME")) and peak > 0.0, "GPU evidence")
    require(total > 0.0 and peak <= total * 0.92, "VRAM safety")
    require(
        result.get("CHIME_USED_IN_TRAINING") == job["chime_used_in_training"],
        "CHiME provenance",
    )
    require(
        result.get("COMMERCIAL_MODEL_RELEASE_REVIEW_REQUIRED")
        == job["commercial_model_release_review_required"],
        "commercial review provenance",
    )
    require(
        result.get("CMU_EXPERIMENT_CLASS") == job["cmu_experiment_class"],
        "experiment class",
    )
    checkpoint_value = result.get("BEST_CHECKPOINT_PATH")
    checkpoint_hash = result.get("BEST_CHECKPOINT_SHA256")
    best_step = int(result.get("BEST_CHECKPOINT_STEP") or 0)
    expected_checkpoint_id = f"{job['run_id']}_best_step_{best_step}"
    require(0 < best_step <= final_step, "best checkpoint step")
    require(
        result.get("BEST_CHECKPOINT_ID") == expected_checkpoint_id,
        "best checkpoint identity",
    )
    require(bool(checkpoint_value and checkpoint_hash), "best checkpoint reference")
    if checkpoint_value and checkpoint_hash:
        run_dir = (
            paths.qualification / "canaries" / job["experiment_id"]
            if canary
            else paths.runs / job["run_id"]
        )
        checkpoint = run_dir / Path(str(checkpoint_value)).name
        require(
            checkpoint.name == f"checkpoint-step-{best_step:06d}.pt",
            "best checkpoint filename",
        )
        require(checkpoint.is_file(), "best checkpoint exists")
        if checkpoint.is_file():
            require(sha256_file(checkpoint) == checkpoint_hash, "best checkpoint hash")
    return blockers


def _framework_manifests_valid(paths: AdapterPaths, audit: Mapping[str, Any]) -> bool:
    try:
        normalization_sha256 = text_normalization_sha256()
        if (
            audit["text_normalization_id"] != TEXT_NORMALIZATION_ID
            or audit["text_normalization_sha256"] != normalization_sha256
        ):
            return False
        bundles = [
            read_json(active_bundle_path(paths, bundle_name))
            for bundle_name in BUNDLE_FILES
        ]
        all_bindings = [
            {"bundle_id": item["bundle_id"], "bundle_sha256": item["bundle_sha256"]}
            for item in bundles
        ]
        for reference, item in audit["manifests"].items():
            canonical = {
                key: value
                for key, value in item.items()
                if key not in {"manifest_id", "manifest_sha256"}
            }
            if canonical_sha256(canonical) != item["manifest_sha256"]:
                return False
            if (
                item["text_normalization_id"] != TEXT_NORMALIZATION_ID
                or item["text_normalization_sha256"] != normalization_sha256
            ):
                return False
            if item["sampler_policy_id"] != SAMPLER_VERSION:
                return False
            if item["sampler_seed"] != SAMPLER_SEED:
                return False
            dataset = reference.split(":", 1)[1]
            expected_bindings = (
                all_bindings
                if reference.startswith("monitor:")
                else [
                    binding
                    for bundle, binding in zip(bundles, all_bindings, strict=True)
                    if dataset
                    in {str(source["dataset_id"]) for source in bundle["train_sources"]}
                ]
            )
            if (
                not item["source_manifest_id"]
                or item["bundle_bindings"] != expected_bindings
            ):
                return False
            derived = item["derived_manifest_path"]
            source = item["source_manifest_path"]
            if not derived.startswith("JP_TRAINING_ROOT:") or not source.startswith(
                "JP_TRAINING_ROOT:"
            ):
                return False
            derived_path = resolve_logical_path(derived, paths.roots)
            source_path = resolve_logical_path(source, paths.roots)
            source_descriptor = read_json(source_path.with_suffix(".manifest.json"))
            if (
                source_descriptor["manifest_id"] != item["source_manifest_id"]
                or source_descriptor["manifest_sha256"]
                != item["source_manifest_sha256"]
            ):
                return False
            if (
                _frame_hash(pd.read_parquet(derived_path))
                != item["derived_manifest_sha256"]
            ):
                return False
            if (
                _frame_hash(pd.read_parquet(source_path))
                != item["source_manifest_sha256"]
            ):
                return False
    except (FileNotFoundError, KeyError, ValueError):
        return False
    return True


def validate(paths: AdapterPaths) -> dict[str, Any]:
    parent = verify_parent(paths)
    initialization = verify_initialization(paths)
    configs = load_frozen_configs(paths)
    queue = (
        read_json(paths.queue_path)
        if paths.queue_path.is_file()
        else plan(paths)["queue"]
    )
    queue_canonical = {
        k: v for k, v in queue.items() if k not in {"queue_id", "queue_sha256"}
    }
    queue_hash_valid = canonical_sha256(queue_canonical) == queue["queue_sha256"]
    exact_ids = [x[0] for x in EXPERIMENTS]
    jobs_valid = [x["experiment_id"] for x in queue["jobs"]] == exact_ids
    no_giga = queue["giga_jobs"] == 0 and all(
        job["experiment_id"].startswith("O-") for job in queue["jobs"]
    )
    audit = read_json(paths.audits / "framework_manifest_audit.json")
    qualification = _qualification(paths)
    canaries_valid = False
    if qualification and qualification.get("ready_to_run_original_adapter_queue"):
        summary = {item["experiment_id"]: item for item in qualification["canaries"]}
        canaries_valid = set(summary) == {"O-AGE", "O-AGE-ROBUST"}
        jobs = {item["experiment_id"]: item for item in queue["jobs"]}
        for experiment_id in ("O-AGE", "O-AGE-ROBUST"):
            result_path = (
                paths.qualification / "canaries" / experiment_id / "result.json"
            )
            if not result_path.is_file():
                canaries_valid = False
                continue
            canary_result = read_json(result_path)
            if not summary.get(experiment_id, {}).get("passed") or _result_blockers(
                paths, jobs[experiment_id], canary_result, canary=True
            ):
                canaries_valid = False
    result = {
        "PHASE4_PARENT_VALID": parent["valid"],
        "INITIALIZATION_VALID": bool(initialization),
        "CONFIG_IDENTITIES_VALID": bool(configs),
        "FRAMEWORK_MANIFESTS_VALID": bool(
            audit["all_memberships_preserved"]
            and audit["total_missing_audio"] == 0
            and audit["total_invalid_segments"] == 0
            and audit["total_invalid_training_text"] == 0
            and audit["total_tokenization_failures"] == 0
            and audit["total_unknown_token_occurrences"] == 0
            and _framework_manifests_valid(paths, audit)
        ),
        "QUEUE_HASH_VALID": queue_hash_valid,
        "QUEUE_EXACTLY_EIGHT": len(queue["jobs"]) == 8 and jobs_valid,
        "NO_GIGA_JOBS": no_giga,
        "NO_LARGE_ACCESS": not audit["large_accessed"],
        "COMMON_VOICE_RECLASSIFICATION_VALID": bool(
            audit["common_voice_heldout_included"]
            and audit["former_common_voice_heldout_reclassified_to_train"]
            and not audit["common_voice_dev_used_for_gradients"]
        ),
        "TRANSCRIPT_REPAIRS_AUDITED": isinstance(
            audit["total_transcript_repairs"], int
        )
        and audit["total_transcript_repairs"] >= 0,
        "CANARIES_PASSED": canaries_valid,
    }
    result["READY_TO_RUN_ORIGINAL_ADAPTER_QUEUE"] = all(result.values())
    full_result_paths = [
        paths.runs / job["run_id"] / "result.json" for job in queue["jobs"]
    ]
    full_results_present = any(path.is_file() for path in full_result_paths)
    validated_successes = sum(_completed_run(paths, job) for job in queue["jobs"])
    result["FULL_RUN_RESULTS_PRESENT"] = full_results_present
    result["VALIDATED_SUCCESSFUL_EXPERIMENTS"] = validated_successes
    result["ALL_FULL_RUNS_SUCCESSFUL"] = (
        validated_successes == 8 if full_results_present else None
    )
    result["VALID"] = bool(
        result["READY_TO_RUN_ORIGINAL_ADAPTER_QUEUE"]
        and (not full_results_present or validated_successes == 8)
    )
    return result


def phase6_input_block(completion: Mapping[str, Any]) -> str:
    def shown(value: Any) -> str:
        if isinstance(value, bool):
            return "YES" if value else "NO"
        if value is None:
            return "NONE"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) if value else "NONE"
        return str(value)

    top_level_fields = (
        "PARENT_PHASE4_FREEZE_ID",
        "PARENT_PHASE4_FREEZE_SHA256",
        "PHASE5_TRAINING_SYSTEM_COMMIT",
        "ORIGINAL_BASELINE_CONTINUITY",
        "RECONSTRUCTED_ORIGINAL_BASELINE_EXPORT_REQUIRED",
        "ORIGINAL_TRAINABLE_CHECKPOINT_ID",
        "ORIGINAL_TRAINABLE_CHECKPOINT_PATH",
        "ORIGINAL_TRAINABLE_CHECKPOINT_SHA256",
        "TOKENIZER_ID",
        "TOKENIZER_PATH",
        "TOKENIZER_SHA256",
        "ICEFALL_COMMIT",
        "ADAPTER_IMPLEMENTATION_ID",
        "ADAPTER_TRAINING_RECIPE_ID",
        "ORIGINAL_ADAPTER_QUEUE_ID",
        "ORIGINAL_ADAPTER_QUEUE_SHA256",
        "SUCCESSFUL_EXPERIMENT_IDS",
    )
    lines = [f"{key} = {shown(completion.get(key))}" for key in top_level_fields]
    for item in completion["experiments"]:
        if not item.get("EXPORT_READY"):
            continue
        lines.append("")
        for key in (
            "EXPERIMENT_ID",
            "BEST_CHECKPOINT_ID",
            "BEST_CHECKPOINT_PATH",
            "BEST_CHECKPOINT_SHA256",
            "BEST_CHECKPOINT_STEP",
            "BUNDLE_ID",
            "CMU_EXPERIMENT_CLASS",
            "COMMERCIAL_MODEL_RELEASE_REVIEW_REQUIRED",
            "EXPORT_READY",
        ):
            lines.append(f"{key} = {shown(item.get(key))}")
    lines.append("")
    for key in (
        "FAILED_OR_INCOMPLETE_EXPERIMENTS",
        "GIGA_ADAPTATION_ATTEMPTED",
        "GIGA_FUTURE_OPTION",
        "ONNX_EXPORTED",
        "LARGE_CAMPAIGN_CREATED",
        "COMMON_VOICE_HELDOUT_EVALUATED",
        "CURRENT_GIT_COMMIT",
        "CURRENT_BRANCH",
    ):
        lines.append(f"{key} = {shown(completion.get(key))}")
    return "\n".join(lines)


def results(paths: AdapterPaths) -> dict[str, Any]:
    readiness = validate(paths)
    if not readiness["READY_TO_RUN_ORIGINAL_ADAPTER_QUEUE"]:
        raise AdapterResearchError("Phase-5 training system validation failed")
    queue = read_json(paths.queue_path)
    git_commit = subprocess.run(
        ["git", "-C", str(paths.repository_root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    git_branch = subprocess.run(
        ["git", "-C", str(paths.repository_root), "branch", "--show-current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    system_lock_path = paths.configs / "original_adapter_system_commit.v1.json"
    phase5_system_commit = (
        read_json(system_lock_path)["phase5_training_system_commit"]
        if system_lock_path.is_file()
        else git_commit
    )
    experiments = []
    successful = []
    for job in queue["jobs"]:
        result_path = paths.runs / job["run_id"] / "result.json"
        if result_path.is_file():
            item = read_json(result_path)
            blockers = _result_blockers(paths, job, item, canary=False)
            if blockers:
                item = dict(item)
                item["EXPORT_READY"] = False
                item["EXPORT_BLOCKERS"] = sorted(
                    set(item.get("EXPORT_BLOCKERS", [])) | set(blockers)
                )
        else:
            item = {
                "EXPERIMENT_ID": job["experiment_id"],
                "STATE": "not_started",
                "TRAINING_RUN_ID": job["run_id"],
                "TRAINING_RUN_SHA256": job["run_sha256"],
                "BUNDLE_ID": job["bundle_id"],
                "INITIALIZATION_CHECKPOINT_ID": CHECKPOINT_ID,
                "INITIALIZATION_CHECKPOINT_SHA256": CHECKPOINT_SHA256,
                "TRAINING_RECIPE_ID": queue["training_recipe_id"],
                "TRAINING_BUDGET": job["derived_training_budget_optimizer_steps"],
                "BEST_CHECKPOINT_ID": None,
                "BEST_CHECKPOINT_PATH": None,
                "BEST_CHECKPOINT_SHA256": None,
                "BEST_CHECKPOINT_STEP": None,
                "FINAL_STEP": 0,
                "EARLY_STOPPED": False,
                "BEST_DEV_OBJECTIVE": None,
                "PER_DOMAIN_DEV_METRICS": {},
                "INITIAL_CLEAN_MONITOR_METRIC": None,
                "BEST_CLEAN_MONITOR_METRIC": None,
                "CLEAN_MONITOR_RELATIVE_CHANGE": None,
                "TRAINING_ELAPSED_SECONDS": 0.0,
                "PEAK_GPU_VRAM_GIB": None,
                "FINITE_LOSS_CHECK": False,
                "BACKBONE_FROZEN_CHECK": False,
                "ADAPTER_CHANGED_CHECK": False,
                "BEST_CHECKPOINT_RELOAD_CHECK": False,
                "DEV_COMPLETE": False,
                "MONITOR_COMPLETE": False,
                "CHIME_USED_IN_TRAINING": job["chime_used_in_training"],
                "COMMERCIAL_MODEL_RELEASE_REVIEW_REQUIRED": job[
                    "commercial_model_release_review_required"
                ],
                "CMU_EXPERIMENT_CLASS": job["cmu_experiment_class"],
                "EXPORT_READY": False,
                "EXPORT_BLOCKERS": ["training not complete"],
            }
        experiments.append(item)
        if item.get("EXPORT_READY"):
            successful.append(item["EXPERIMENT_ID"])
    completion = {
        "schema_version": "phase5-original-adapter-training-completion.v1",
        "PARENT_PHASE4_FREEZE_ID": PHASE4_ID,
        "PARENT_PHASE4_FREEZE_SHA256": PHASE4_SHA256,
        "PHASE5_TRAINING_SYSTEM_COMMIT": phase5_system_commit,
        "ORIGINAL_BASELINE_CONTINUITY": "strong_lineage_requires_reconstructed_baseline",
        "RECONSTRUCTED_ORIGINAL_BASELINE_EXPORT_REQUIRED": True,
        "ORIGINAL_TRAINABLE_CHECKPOINT_ID": CHECKPOINT_ID,
        "ORIGINAL_TRAINABLE_CHECKPOINT_PATH": "JP_MODEL_ROOT:Original Trainable Checkpoint/pretrained.pt",
        "ORIGINAL_TRAINABLE_CHECKPOINT_SHA256": CHECKPOINT_SHA256,
        "TOKENIZER_ID": TOKENIZER_ID,
        "TOKENIZER_PATH": "JP_MODEL_ROOT:Original Trainable Checkpoint/bpe.model",
        "TOKENIZER_SHA256": TOKENIZER_SHA256,
        "ICEFALL_COMMIT": ICEFALL_COMMIT,
        "ADAPTER_IMPLEMENTATION_ID": load_frozen_configs(paths)["recipe"][
            "implementation"
        ]["id"],
        "ADAPTER_TRAINING_RECIPE_ID": queue["training_recipe_id"],
        "ORIGINAL_ADAPTER_QUEUE_ID": queue["queue_id"],
        "ORIGINAL_ADAPTER_QUEUE_SHA256": queue["queue_sha256"],
        "SUCCESSFUL_EXPERIMENT_IDS": successful,
        "FAILED_OR_INCOMPLETE_EXPERIMENTS": [
            x["EXPERIMENT_ID"] for x in experiments if not x.get("EXPORT_READY")
        ],
        "GIGA_ADAPTATION_ATTEMPTED": False,
        "GIGA_FUTURE_OPTION": "native full fine-tuning after adapter evaluation if Phase-8 decision gate justifies it",
        "ONNX_EXPORTED": False,
        "LARGE_CAMPAIGN_CREATED": False,
        "COMMON_VOICE_HELDOUT_EVALUATED": False,
        "CURRENT_GIT_COMMIT": git_commit,
        "CURRENT_BRANCH": git_branch,
        "experiments": experiments,
    }
    json_path = paths.root / "phase5_original_adapter_training_completion.json"
    atomic_json(json_path, completion)
    lines = [
        "# Phase 5 Original adapter training completion",
        "",
        f"Successful experiments: {len(successful)} / 8",
        "",
    ]
    lines.extend(
        [
            "## Phase-6 input block",
            "",
            "```text",
            phase6_input_block(completion),
            "```",
            "",
        ]
    )
    experiment_fields = (
        "EXPERIMENT_ID",
        "STATE",
        "TRAINING_RUN_ID",
        "TRAINING_RUN_SHA256",
        "BUNDLE_ID",
        "INITIALIZATION_CHECKPOINT_ID",
        "INITIALIZATION_CHECKPOINT_SHA256",
        "TRAINING_RECIPE_ID",
        "TRAINING_BUDGET",
        "BEST_CHECKPOINT_ID",
        "BEST_CHECKPOINT_PATH",
        "BEST_CHECKPOINT_SHA256",
        "BEST_CHECKPOINT_STEP",
        "FINAL_STEP",
        "EARLY_STOPPED",
        "BEST_DEV_OBJECTIVE",
        "PER_DOMAIN_DEV_METRICS",
        "INITIAL_CLEAN_MONITOR_METRIC",
        "BEST_CLEAN_MONITOR_METRIC",
        "CLEAN_MONITOR_RELATIVE_CHANGE",
        "TRAINING_ELAPSED_SECONDS",
        "PEAK_GPU_VRAM_GIB",
        "FINITE_LOSS_CHECK",
        "BACKBONE_FROZEN_CHECK",
        "ADAPTER_CHANGED_CHECK",
        "BEST_CHECKPOINT_RELOAD_CHECK",
        "DEV_COMPLETE",
        "MONITOR_COMPLETE",
        "CHIME_USED_IN_TRAINING",
        "COMMERCIAL_MODEL_RELEASE_REVIEW_REQUIRED",
        "CMU_EXPERIMENT_CLASS",
        "EXPORT_READY",
        "EXPORT_BLOCKERS",
    )
    for item in experiments:
        lines.extend(
            [
                f"## {item['EXPERIMENT_ID']}",
                "",
            ]
        )
        for key in experiment_fields:
            lines.append(f"{key} = {json.dumps(item.get(key), sort_keys=True)}")
        lines.append("")
    atomic_text(
        paths.root / "phase5_original_adapter_training_completion.md",
        "\n".join(lines) + "\n",
    )
    return completion


def _print(value: Any) -> None:
    if isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=(
            "plan",
            "estimate",
            "run",
            "run-one",
            "qualify",
            "status",
            "status-compact",
            "stop",
            "resume",
            "validate",
            "results",
        ),
    )
    parser.add_argument("--experiment-id")
    parser.add_argument("--reason", default="operator request")
    parser.add_argument("--rebuild-manifests", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    paths = default_paths()
    try:
        if args.action == "plan":
            value = plan(paths, rebuild_manifests=args.rebuild_manifests)
            code = 0
        elif args.action == "estimate":
            value, code = estimate(paths), 0
        elif args.action == "run":
            return run_queue(paths)
        elif args.action == "run-one":
            if not args.experiment_id:
                raise AdapterResearchError("--experiment-id is required")
            return run_one(paths, args.experiment_id)
        elif args.action == "qualify":
            return qualify(paths)
        elif args.action == "status":
            value, code = status(paths), 0
        elif args.action == "status-compact":
            value, code = compact_status(paths), 0
        elif args.action == "stop":
            value, code = request_stop(paths, args.reason), 0
        elif args.action == "resume":
            return resume(paths)
        elif args.action == "validate":
            value = validate(paths)
            code = 0 if value["VALID"] else 1
        else:
            value = results(paths)
            _print(value)
            print()
            print(phase6_input_block(value))
            return 0
    except (AdapterResearchError, FileNotFoundError, KeyError, ValueError) as exc:
        _print({"status": "blocked", "reason": str(exc)})
        return 1
    _print(value)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
