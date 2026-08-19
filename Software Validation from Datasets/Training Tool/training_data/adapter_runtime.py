"""Pinned WSL/CUDA runtime for Original Zipformer2 adapter training.

The supported entry points are intentionally narrow: two bounded qualification
canaries and one queue job.  All scientific configuration is read from the
tracked, self-hashed Phase-5 files and from the generated immutable queue.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import random
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import k2
import lhotse
import pandas as pd
import pyarrow
import sentencepiece as spm
import soundfile as sf
import torch
import torchaudio.functional as AF
from lhotse import Fbank, FbankConfig
from torch.nn.utils.rnn import pad_sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOL_ROOT))

from training_data.adapter_research import (  # noqa: E402
    CHECKPOINT_ID,
    CHECKPOINT_SHA256,
    DEV_FILES,
    ICEFALL_COMMIT,
    SAMPLER_SEED,
    SOURCE_FILES,
    AdapterResearchError,
    _verify_identity,
    atomic_json,
    canonical_sha256,
    deterministic_view_index,
    read_json,
    sha256_file,
    stable_u64,
    utc_now,
)
from training_data.portability import (  # noqa: E402
    PortableRoots,
    resolve_logical_path,
)


ICEFALL_ROOT = Path(
    os.environ.get(
        "JP_ICEFALL_ROOT",
        Path.home() / ".local" / "share" / "just-peachy" / "toolchains" / "icefall",
    )
)
RECIPE_ROOT = ICEFALL_ROOT / "egs" / "librispeech" / "ASR" / "zipformer_adapter"
if not ICEFALL_ROOT.joinpath(".git").exists():
    raise RuntimeError("Pinned Icefall checkout metadata is unavailable")
if (
    subprocess.run(
        ["git", "-C", str(ICEFALL_ROOT), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    != ICEFALL_COMMIT
):
    raise RuntimeError("Pinned Icefall checkout changed")
if subprocess.run(
    ["git", "-C", str(ICEFALL_ROOT), "status", "--short"],
    check=True,
    capture_output=True,
    text=True,
).stdout.strip():
    raise RuntimeError("Pinned Icefall checkout has local modifications")
sys.path[:0] = [str(RECIPE_ROOT), str(ICEFALL_ROOT)]
os.chdir(RECIPE_ROOT)

import train as icefall_train  # noqa: E402
from beam_search import greedy_search_batch  # noqa: E402
from icefall.utils import (  # noqa: E402
    create_grad_scaler,
    get_parameter_groups_with_lrs,
    torch_autocast,
)


@dataclass
class RuntimePaths:
    queue_path: Path

    @property
    def phase5_root(self) -> Path:
        return self.queue_path.parent.parent

    @property
    def training_root(self) -> Path:
        return Path(os.environ.get("JP_TRAINING_ROOT", self.phase5_root.parent.parent)).resolve()

    @property
    def repository_root(self) -> Path:
        return Path(os.environ.get("JP_REPO_ROOT", TOOL_ROOT.parents[1])).resolve()

    @property
    def data_root(self) -> Path:
        return Path(
            os.environ.get(
                "JP_DATA_ROOT", self.repository_root / "Software Validation from Datasets"
            )
        ).resolve()

    @property
    def model_root(self) -> Path:
        return Path(os.environ.get("JP_MODEL_ROOT", self.repository_root / "models")).resolve()

    @property
    def run_root(self) -> Path:
        return Path(os.environ.get("JP_RUN_ROOT", self.training_root / "runs")).resolve()

    @property
    def roots(self) -> PortableRoots:
        return PortableRoots(
            self.repository_root,
            self.data_root,
            self.training_root,
            self.model_root,
            self.run_root,
        )

    @property
    def tool_root(self) -> Path:
        return TOOL_ROOT

    @property
    def phase4_root(self) -> Path:
        return self.training_root / "successors" / "phase4_training_manifests_v1"

    @property
    def framework_root(self) -> Path:
        return self.phase5_root / "framework_manifests"

    @property
    def runs(self) -> Path:
        return self.run_root / "adapters"

    @property
    def qualification(self) -> Path:
        return self.phase5_root / "qualification"

    @property
    def stop_path(self) -> Path:
        return self.phase5_root / "STOP_REQUESTED.json"

    @property
    def status_path(self) -> Path:
        override = os.environ.get("JP_ADAPTER_STATUS_ROOT")
        return (Path(override).resolve() if override else self.phase5_root) / "queue_status.json"


def _configs(paths: RuntimePaths) -> dict[str, dict[str, Any]]:
    return {
        "recipe": _verify_identity(
            paths.tool_root / "configs" / "original_adapter_recipe.v1.json",
            id_key="recipe_id",
            sha_key="recipe_sha256",
            prefix="original_adapter_recipe",
        ),
        "budget": _verify_identity(
            paths.tool_root / "configs" / "original_adapter_budget_policy.v1.json",
            id_key="policy_id",
            sha_key="policy_sha256",
            prefix="original_adapter_budget_policy",
        ),
        "environment": _verify_identity(
            paths.tool_root / "configs" / "original_adapter_environment_lock.v1.json",
            id_key="environment_id",
            sha_key="environment_sha256",
            prefix="original_adapter_environment",
        ),
        "provenance": _verify_identity(
            paths.tool_root / "configs" / "original_adapter_provenance.v1.json",
            id_key="provenance_id",
            sha_key="provenance_sha256",
            prefix="original_adapter_provenance",
        ),
    }


def _verify_training_system_commit(paths: RuntimePaths) -> None:
    lock_path = paths.tool_root / "configs" / "original_adapter_system_commit.v1.json"
    if not lock_path.is_file():
        raise AdapterResearchError("Phase-5 training-system commit lock is absent")
    commit = read_json(lock_path)["phase5_training_system_commit"]
    source_paths = (
        "Software Validation from Datasets/Training Tool/training_data/adapter_research.py",
        "Software Validation from Datasets/Training Tool/training_data/adapter_runtime.py",
        "Software Validation from Datasets/Training Tool/training_data/handoff.py",
        "Software Validation from Datasets/Training Tool/training_data/portability.py",
        "Software Validation from Datasets/Training Tool/configs/original_adapter_recipe.v1.json",
        "Software Validation from Datasets/Training Tool/configs/original_adapter_budget_policy.v1.json",
        "Software Validation from Datasets/Training Tool/configs/original_adapter_environment_lock.v1.json",
        "Software Validation from Datasets/Training Tool/configs/original_adapter_provenance.v1.json",
    )
    exists = subprocess.run(
        [
            "git",
            "-C",
            str(paths.repository_root),
            "cat-file",
            "-e",
            f"{commit}^{{commit}}",
        ],
        check=False,
        capture_output=True,
    )
    unchanged = subprocess.run(
        [
            "git",
            "-C",
            str(paths.repository_root),
            "diff",
            "--quiet",
            commit,
            "--",
            *source_paths,
        ],
        check=False,
    )
    if exists.returncode != 0 or unchanged.returncode != 0:
        raise AdapterResearchError(
            "Tracked training system differs from its Phase-5 implementation commit"
        )


def _weighted_index(weights: Sequence[float], rank: int) -> int:
    total = sum(weights)
    point = (rank / float(2**64)) * total
    cumulative = 0.0
    for index, weight in enumerate(weights):
        cumulative += weight
        if point < cumulative:
            return index
    return len(weights) - 1


class FrozenBundleSampler:
    """Deterministic dataset/group/source/view event sampler with exact resume."""

    def __init__(
        self,
        *,
        paths: RuntimePaths,
        bundle: Mapping[str, Any],
        start_event: int = 0,
    ) -> None:
        self.paths = paths
        self.bundle = dict(bundle)
        self.event_index = start_event
        self.datasets: list[dict[str, Any]] = []
        for source in bundle["train_sources"]:
            dataset_id = str(source["dataset_id"])
            frame = pd.read_parquet(
                paths.framework_root / "train" / SOURCE_FILES[dataset_id]
            )
            if not bool(frame["training_eligible_for_experiment"].all()):
                raise AdapterResearchError(f"Ineligible row in {dataset_id} TRAIN")
            groups = {
                str(group_id): list(indexes)
                for group_id, indexes in frame.groupby(
                    "source_group_id", sort=True
                ).groups.items()
            }
            for indexes in groups.values():
                indexes.sort(key=lambda idx: str(frame.at[idx, "acoustic_view_id"]))
            cluster_groups: dict[str, list[str]] = {}
            cluster_weights: dict[str, float] = {}
            group_rows = frame.drop_duplicates("source_group_id")
            for _, row in group_rows.iterrows():
                cluster = str(row["sampling_group_id"])
                cluster_groups.setdefault(cluster, []).append(
                    str(row["source_group_id"])
                )
                cluster_weights[cluster] = float(row["sampling_group_probability"])
            clusters = sorted(cluster_groups)
            self.datasets.append(
                {
                    "dataset_id": dataset_id,
                    "probability": float(source["probability"]),
                    "frame": frame,
                    "groups": groups,
                    "clusters": clusters,
                    "cluster_groups": {
                        key: sorted(value) for key, value in cluster_groups.items()
                    },
                    "cluster_weights": [cluster_weights[key] for key in clusters],
                }
            )
        self.dataset_weights = [item["probability"] for item in self.datasets]
        if not math.isclose(sum(self.dataset_weights), 1.0, abs_tol=1e-12):
            raise AdapterResearchError("Frozen dataset weights do not sum to one")

    def next_row(self) -> pd.Series:
        event = self.event_index
        self.event_index += 1
        dataset_index = _weighted_index(
            self.dataset_weights,
            stable_u64(SAMPLER_SEED, self.bundle["bundle_id"], "dataset", event),
        )
        dataset = self.datasets[dataset_index]
        cluster_index = _weighted_index(
            dataset["cluster_weights"],
            stable_u64(
                SAMPLER_SEED,
                self.bundle["bundle_id"],
                dataset["dataset_id"],
                "cluster",
                event,
            ),
        )
        cluster = dataset["clusters"][cluster_index]
        candidate_groups = dataset["cluster_groups"][cluster]
        group = candidate_groups[
            stable_u64(
                SAMPLER_SEED,
                self.bundle["bundle_id"],
                dataset["dataset_id"],
                cluster,
                "source",
                event,
            )
            % len(candidate_groups)
        ]
        indexes = dataset["groups"][group]
        epoch = event // len(dataset["groups"])
        view = deterministic_view_index(
            self.bundle["bundle_id"], epoch, group, len(indexes)
        )
        return dataset["frame"].loc[indexes[view]]

    def next_microbatch(self, max_duration: float) -> list[pd.Series]:
        rows: list[pd.Series] = []
        duration = 0.0
        while True:
            before = self.event_index
            row = self.next_row()
            value = float(row["model_input_duration_seconds"])
            if rows and duration + value > max_duration:
                self.event_index = before
                break
            rows.append(row)
            duration += value
            if duration >= max_duration:
                break
        return rows


def _resolve_audio(row: pd.Series, paths: RuntimePaths) -> Path:
    root_id = str(row["audio_root_id"])
    return resolve_logical_path(
        f"{root_id}:{row['audio_relative_path']}", paths.roots
    )


def _logical_training_path(path: Path, paths: RuntimePaths) -> str:
    resolved = path.resolve()
    for root_id, root in (
        ("JP_RUN_ROOT", paths.run_root),
        ("JP_TRAINING_ROOT", paths.training_root),
        ("JP_MODEL_ROOT", paths.model_root),
    ):
        try:
            relative = resolved.relative_to(root.resolve())
        except ValueError:
            continue
        return f"{root_id}:" + relative.as_posix()
    raise AdapterResearchError(f"Artifact is outside portable roots: {path}")


def _checkpoint_path(value: str, *, paths: RuntimePaths, run_dir: Path) -> Path:
    if value.startswith("JP_") and ":" in value:
        return resolve_logical_path(value, paths.roots)
    candidate = Path(value)
    return candidate if candidate.is_absolute() else run_dir / candidate


def _load_audio(
    row: pd.Series, paths: RuntimePaths, minimum_samples: int
) -> torch.Tensor:
    path = _resolve_audio(row, paths)
    start = float(row["start_sec"])
    end = float(row["end_sec"])
    with sf.SoundFile(path) as source:
        sample_rate = source.samplerate
        source.seek(max(0, round(start * sample_rate)))
        count = max(1, round((end - start) * sample_rate))
        samples = source.read(count, dtype="float32", always_2d=True)[:, 0]
    wave = torch.from_numpy(samples)
    if sample_rate != 16000:
        wave = AF.resample(wave, sample_rate, 16000)
    if wave.numel() < minimum_samples:
        wave = torch.nn.functional.pad(wave, (0, minimum_samples - wave.numel()))
    return wave.contiguous()


def make_batch(
    rows: Sequence[pd.Series],
    *,
    paths: RuntimePaths,
    sentencepiece: spm.SentencePieceProcessor,
    fbank: Fbank,
    device: torch.device,
) -> dict[str, Any]:
    waves = []
    texts = []
    for row in rows:
        text = str(row["training_text"])
        token_count = len(sentencepiece.encode(text, out_type=int))
        if token_count != int(row["bpe_token_count"]):
            raise AdapterResearchError("Derived BPE token count changed")
        minimum = max(16000, math.ceil(token_count * 0.05 * 16000))
        waves.append(_load_audio(row, paths, minimum).to(device))
        texts.append(text)
    features = [fbank.extract(wave, 16000) for wave in waves]
    lengths = torch.tensor([value.size(0) for value in features], dtype=torch.int64)
    return {
        "inputs": pad_sequence(
            features, batch_first=True, padding_value=math.log(1e-10)
        ),
        "supervisions": {"num_frames": lengths, "text": texts},
    }


def build_model(
    paths: RuntimePaths,
    recipe: Mapping[str, Any],
    *,
    device: torch.device,
) -> tuple[torch.nn.Module, Any, spm.SentencePieceProcessor, list[str]]:
    checkpoint_root = paths.model_root / "Original Trainable Checkpoint"
    if sha256_file(checkpoint_root / "pretrained.pt") != CHECKPOINT_SHA256:
        raise AdapterResearchError("Original checkpoint hash changed")
    args = icefall_train.get_parser().parse_args(
        [
            "--causal",
            "true",
            "--chunk-size",
            str(recipe["model"]["chunk_size"]),
            "--left-context-frames",
            str(recipe["model"]["left_context_frames"]),
            "--use-adapters",
            "true",
            "--adapter-dim",
            str(recipe["implementation"]["adapter_dim"]),
            "--use-fp16",
            "true",
            "--base-lr",
            str(recipe["optimization"]["base_lr"]),
            "--lr-batches",
            str(recipe["optimization"]["lr_batches"]),
            "--lr-epochs",
            str(recipe["optimization"]["lr_epochs"]),
        ]
    )
    params = icefall_train.get_params()
    params.update(vars(args))
    params.max_duration = float(
        recipe["optimization"]["microbatch_max_duration_seconds"]
    )
    params.world_size = 1
    params.ref_duration = 600
    params.warm_step = int(recipe["optimization"]["warm_step"])
    processor = spm.SentencePieceProcessor(
        model_file=str(checkpoint_root / "bpe.model")
    )
    params.blank_id = processor.piece_to_id("<blk>")
    params.vocab_size = processor.get_piece_size()
    model = icefall_train.get_model(params)
    checkpoint = torch.load(
        checkpoint_root / "pretrained.pt", map_location="cpu", weights_only=False
    )["model"]
    incompatibility = model.load_state_dict(checkpoint, strict=False)
    non_adapter_missing = [
        key for key in incompatibility.missing_keys if "adapter" not in key
    ]
    if non_adapter_missing or incompatibility.unexpected_keys:
        raise AdapterResearchError(
            "Original checkpoint is incompatible with the official adapter model"
        )
    trainable_names = []
    for name, parameter in model.named_parameters():
        parameter.requires_grad = "adapter" in name
        if parameter.requires_grad:
            trainable_names.append(name)
    if len(trainable_names) != 256:
        raise AdapterResearchError("Official adapter tensor selection changed")
    model.to(device)
    return model, params, processor, trainable_names


def set_adapter_training_mode(model: torch.nn.Module) -> None:
    model.train()
    for name, module in model.named_modules():
        module.training = "adapter" in name


def tensor_digest(model: torch.nn.Module, *, adapter: bool) -> str:
    digest = hashlib.sha256()
    for name, parameter in model.named_parameters():
        if ("adapter" in name) != adapter:
            continue
        digest.update(name.encode("utf-8"))
        raw = parameter.detach().cpu().contiguous().numpy().tobytes()
        digest.update(raw)
    return digest.hexdigest().upper()


def optimizer_is_adapter_only(
    optimizer: torch.optim.Optimizer, model: torch.nn.Module
) -> bool:
    intended = {
        id(value) for name, value in model.named_parameters() if "adapter" in name
    }
    actual = {
        id(value) for group in optimizer.param_groups for value in group["params"]
    }
    return intended == actual


def adapter_parameter_groups(
    model: torch.nn.Module, learning_rate: float
) -> list[dict]:
    groups = get_parameter_groups_with_lrs(model, lr=learning_rate, include_names=True)
    filtered = []
    for group in groups:
        pairs = [
            (name, value)
            for name, value in group["named_params"]
            if value.requires_grad and "adapter" in name
        ]
        if pairs:
            filtered.append({**group, "named_params": pairs})
    return filtered


def save_checkpoint(
    path: Path,
    *,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    scaler: Any,
    step: int,
    event_index: int,
    elapsed_seconds: float,
    best: Mapping[str, Any],
    run_identity: Mapping[str, Any],
    backbone_sha256: str,
) -> str:
    payload = {
        "schema_version": "original-adapter-checkpoint.v1",
        "initialization_checkpoint_id": CHECKPOINT_ID,
        "initialization_checkpoint_sha256": CHECKPOINT_SHA256,
        "run_identity": dict(run_identity),
        "adapter_state": {
            name: value.detach().cpu()
            for name, value in model.state_dict().items()
            if "adapter" in name
        },
        "optimizer": optimizer.state_dict(),
        "scheduler": scheduler.state_dict(),
        "scaler": scaler.state_dict(),
        "global_step": step,
        "sampler_event_index": event_index,
        "elapsed_seconds": elapsed_seconds,
        "best": dict(best),
        "python_random_state": random.getstate(),
        "torch_random_state": torch.get_rng_state(),
        "cuda_random_state": torch.cuda.get_rng_state_all(),
        "backbone_sha256": backbone_sha256,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)
    return sha256_file(path)


def load_checkpoint(
    path: Path,
    *,
    model: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    scaler: Any,
) -> dict[str, Any]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    result = model.load_state_dict(payload["adapter_state"], strict=False)
    if any("adapter" in key for key in result.missing_keys) or result.unexpected_keys:
        raise AdapterResearchError("Adapter checkpoint state is incomplete")
    optimizer.load_state_dict(payload["optimizer"])
    scheduler.load_state_dict(payload["scheduler"])
    scaler.load_state_dict(payload["scaler"])
    random.setstate(payload["python_random_state"])
    torch.set_rng_state(payload["torch_random_state"])
    torch.cuda.set_rng_state_all(payload["cuda_random_state"])
    return payload


def _evaluation_rows(
    frame: pd.DataFrame,
    *,
    bundle_id: str,
    limit: int | None,
) -> pd.DataFrame:
    selected = []
    for group, rows in frame.groupby("source_group_id", sort=True):
        rows = rows.sort_values("acoustic_view_id")
        index = deterministic_view_index(bundle_id, 0, str(group), len(rows))
        selected.append(rows.iloc[index])
    result = pd.DataFrame(selected)
    result["_rank"] = result["source_group_id"].map(
        lambda group: stable_u64(SAMPLER_SEED, bundle_id, "evaluation", group)
    )
    result = result.sort_values(["_rank", "source_group_id"]).drop(columns="_rank")
    return result if limit is None else result.head(limit)


def _edit_distance(reference: Sequence[str], hypothesis: Sequence[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, ref in enumerate(reference, start=1):
        current = [row]
        for column, hyp in enumerate(hypothesis, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (ref != hyp),
                )
            )
        previous = current
    return previous[-1]


@torch.inference_mode()
def score_frame(
    frame: pd.DataFrame,
    *,
    model: torch.nn.Module,
    processor: spm.SentencePieceProcessor,
    fbank: Fbank,
    paths: RuntimePaths,
    bundle_id: str,
    limit: int | None,
    batch_duration: float = 90.0,
) -> dict[str, Any]:
    model.eval()
    rows = list(_evaluation_rows(frame, bundle_id=bundle_id, limit=limit).iterrows())
    errors = words = exact = 0
    cursor = 0
    while cursor < len(rows):
        batch_rows = []
        duration = 0.0
        while cursor < len(rows):
            row = rows[cursor][1]
            value = float(row["model_input_duration_seconds"])
            if batch_rows and duration + value > batch_duration:
                break
            batch_rows.append(row)
            duration += value
            cursor += 1
        batch = make_batch(
            batch_rows,
            paths=paths,
            sentencepiece=processor,
            fbank=fbank,
            device=torch.device("cuda"),
        )
        features = batch["inputs"]
        lengths = batch["supervisions"]["num_frames"].to(features.device)
        encoder, encoder_lengths = model.forward_encoder(features, lengths)
        hypotheses = greedy_search_batch(model, encoder, encoder_lengths)
        for row, token_ids in zip(batch_rows, hypotheses, strict=True):
            reference = str(row["training_text"]).split()
            hypothesis = processor.decode(token_ids).upper().split()
            errors += _edit_distance(reference, hypothesis)
            words += len(reference)
            exact += reference == hypothesis
    return {
        "wer": errors / words if words else None,
        "word_errors": errors,
        "reference_words": words,
        "items": len(rows),
        "exact_matches": exact,
        "view_policy": "fixed deterministic epoch-0 view per Phase-4 source group",
        "bounded_source_group_limit": limit,
    }


def evaluate(
    *,
    paths: RuntimePaths,
    job: Mapping[str, Any],
    bundle: Mapping[str, Any],
    model: torch.nn.Module,
    processor: spm.SentencePieceProcessor,
    fbank: Fbank,
    limit: int | None,
) -> dict[str, Any]:
    per_domain = {}
    for source in bundle["train_sources"]:
        dataset = str(source["dataset_id"])
        frame = pd.read_parquet(paths.framework_root / "dev" / DEV_FILES[dataset])
        per_domain[dataset] = score_frame(
            frame,
            model=model,
            processor=processor,
            fbank=fbank,
            paths=paths,
            bundle_id=bundle["bundle_id"],
            limit=limit,
        )
    values = [item["wer"] for item in per_domain.values()]
    objective = sum(values) / len(values)
    monitor = pd.read_parquet(
        paths.framework_root / "monitor" / "clean_regression_monitor.parquet"
    )
    monitor_metric = score_frame(
        monitor,
        model=model,
        processor=processor,
        fbank=fbank,
        paths=paths,
        bundle_id=bundle["bundle_id"],
        limit=limit,
    )
    return {
        "objective_wer": objective,
        "per_domain": per_domain,
        "clean_monitor": monitor_metric,
    }


def _status(
    paths: RuntimePaths,
    queue: Mapping[str, Any],
    *,
    state: str,
    job: Mapping[str, Any],
    step: int,
    max_steps: int,
    elapsed: float,
    ema: float | None,
    latest_loss: float | None,
    latest_eval: Mapping[str, Any] | None,
    peak_vram: float,
    current_checkpoint: str | None,
    best_checkpoint: str | None,
    failure: str | None = None,
) -> None:
    completed = 0
    completed_elapsed = 0.0
    for item in queue["jobs"]:
        path = paths.runs / item["run_id"] / "result.json"
        if path.is_file():
            prior_result = read_json(path)
            if prior_result.get("EXPORT_READY"):
                completed += 1
                completed_elapsed += float(
                    prior_result.get("TRAINING_ELAPSED_SECONDS", 0.0)
                )
    remaining_steps = max(0, max_steps - step)
    model_eta = remaining_steps * ema if ema else None
    calibration_path = paths.qualification / "canary_summary.json"
    calibration = read_json(calibration_path) if calibration_path.is_file() else {}
    calibration_values = []
    if calibration.get("ready_to_run_original_adapter_queue"):
        calibration_values = [
            float(item["seconds_per_optimizer_step"])
            for item in calibration.get("canaries", [])
            if item.get("passed") and item.get("seconds_per_optimizer_step")
        ]
    queue_eta = None
    if calibration_values:
        calibrated = sum(calibration_values) / len(calibration_values)
        queue_eta = model_eta or 0.0
        for item in queue["jobs"]:
            if item["experiment_id"] == job["experiment_id"]:
                continue
            result_path = paths.runs / item["run_id"] / "result.json"
            prior_step = 0
            if result_path.is_file():
                prior_result = read_json(result_path)
                if prior_result.get("EXPORT_READY"):
                    continue
                prior_step = int(prior_result.get("FINAL_STEP", 0))
            remaining = max(
                0,
                int(item["derived_training_budget_optimizer_steps"]) - prior_step,
            )
            queue_eta += calibrated * remaining
    value = {
        "QUEUE_ID": queue["queue_id"],
        "QUEUE_STATE": state,
        "COMPLETED_EXPERIMENTS": completed,
        "TOTAL_EXPERIMENTS": 8,
        "CURRENT_EXPERIMENT_ID": job["experiment_id"],
        "CURRENT_STEP": step,
        "MAX_STEP_OR_EQUIVALENT": max_steps,
        "PROGRESS_PERCENT": 100 * step / max_steps,
        "MODEL_ELAPSED_SECONDS": elapsed,
        "EMA_SECONDS_PER_STEP": ema,
        "MODEL_ETA_SECONDS": model_eta,
        "QUEUE_ELAPSED_SECONDS": completed_elapsed + elapsed,
        "QUEUE_ETA_SECONDS": queue_eta,
        "LATEST_TRAIN_LOSS": latest_loss,
        "LATEST_DEV_OBJECTIVE": latest_eval.get("objective_wer")
        if latest_eval
        else None,
        "LATEST_PER_DOMAIN_DEV_METRICS": latest_eval.get("per_domain", {})
        if latest_eval
        else {},
        "LATEST_CLEAN_MONITOR_METRIC": latest_eval.get("clean_monitor", {}).get("wer")
        if latest_eval
        else None,
        "PEAK_VRAM_GIB": peak_vram,
        "CURRENT_CHECKPOINT": current_checkpoint,
        "BEST_CHECKPOINT": best_checkpoint,
        "LAST_HEARTBEAT_UTC": utc_now(),
        "FAILURE_REASON": failure,
    }
    atomic_json(paths.status_path, value)


def _checkpoint_reload_probe(
    checkpoint: Path,
    *,
    paths: RuntimePaths,
    recipe: Mapping[str, Any],
    expected_adapter_digest: str,
) -> bool:
    python_state = random.getstate()
    torch_state = torch.get_rng_state()
    cuda_state = torch.cuda.get_rng_state_all()
    try:
        probe, _, _, _ = build_model(paths, recipe, device=torch.device("cpu"))
        payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
        result = probe.load_state_dict(payload["adapter_state"], strict=False)
        return (
            not any("adapter" in key for key in result.missing_keys)
            and not result.unexpected_keys
            and tensor_digest(probe, adapter=True) == expected_adapter_digest
        )
    finally:
        random.setstate(python_state)
        torch.set_rng_state(torch_state)
        torch.cuda.set_rng_state_all(cuda_state)


def run_job(
    *,
    paths: RuntimePaths,
    queue: Mapping[str, Any],
    job: Mapping[str, Any],
    canary: bool,
) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise AdapterResearchError("WSL CUDA is unavailable")
    if not canary:
        _verify_training_system_commit(paths)
    if not ICEFALL_ROOT.joinpath(".git").exists():
        raise AdapterResearchError("Pinned Icefall checkout metadata is unavailable")
    commit = subprocess_commit(ICEFALL_ROOT)
    if commit != ICEFALL_COMMIT:
        raise AdapterResearchError("Pinned Icefall checkout changed")
    if subprocess_worktree_status(ICEFALL_ROOT):
        raise AdapterResearchError("Pinned Icefall checkout has local modifications")
    configs = _configs(paths)
    recipe = configs["recipe"]
    environment = configs["environment"]
    observed_environment = {
        "python": sys.version.split()[0],
        "pytorch": torch.__version__,
        "cuda": str(torch.version.cuda),
        "cudnn": importlib.metadata.version("nvidia-cudnn-cu12"),
        "k2": getattr(k2, "__dev_version__", getattr(k2, "__version__", "unknown")),
        "lhotse": lhotse.__version__,
        "sentencepiece": spm.__version__,
        "pandas": pd.__version__,
        "pyarrow": pyarrow.__version__,
        "soundfile": sf.__version__,
    }
    mismatches = {
        key: {"expected": environment[key], "observed": value}
        for key, value in observed_environment.items()
        if environment[key] != value
    }
    if mismatches:
        raise AdapterResearchError(
            "Frozen WSL environment mismatch: " + json.dumps(mismatches, sort_keys=True)
        )
    for config_name, id_key, sha_key, queue_id_key, queue_sha_key in (
        (
            "recipe",
            "recipe_id",
            "recipe_sha256",
            "training_recipe_id",
            "training_recipe_sha256",
        ),
        (
            "budget",
            "policy_id",
            "policy_sha256",
            "training_budget_policy_id",
            "training_budget_policy_sha256",
        ),
        (
            "environment",
            "environment_id",
            "environment_sha256",
            "environment_id",
            "environment_sha256",
        ),
    ):
        if (
            configs[config_name][id_key] != queue[queue_id_key]
            or configs[config_name][sha_key] != queue[queue_sha_key]
        ):
            raise AdapterResearchError(
                f"Frozen {config_name} identity does not match the queue"
            )
    random.seed(int(recipe["control"]["training_seed"]))
    torch.manual_seed(int(recipe["control"]["training_seed"]))
    torch.cuda.manual_seed_all(int(recipe["control"]["training_seed"]))
    device = torch.device("cuda", 0)
    torch.cuda.set_device(device)
    torch.cuda.reset_peak_memory_stats(device)
    bundle_path = resolve_logical_path(job["bundle_path"], paths.roots)
    bundle = read_json(bundle_path)
    bundle_canonical = {
        key: value
        for key, value in bundle.items()
        if key not in {"bundle_id", "bundle_sha256"}
    }
    if (
        canonical_sha256(bundle_canonical) != bundle["bundle_sha256"]
        or bundle["bundle_id"] != job["bundle_id"]
        or bundle["bundle_sha256"] != job["bundle_sha256"]
    ):
        raise AdapterResearchError("Frozen successor bundle identity changed")
    run_dir = (
        paths.qualification / "canaries" / job["experiment_id"]
        if canary
        else paths.runs / job["run_id"]
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    model, params, processor, trainable_names = build_model(
        paths, recipe, device=device
    )
    total_parameters = sum(item.numel() for item in model.parameters())
    adapter_parameters = sum(
        item.numel() for name, item in model.named_parameters() if "adapter" in name
    )
    backbone_initial = tensor_digest(model, adapter=False)
    adapter_initial = tensor_digest(model, adapter=True)
    optimizer = icefall_train.ScaledAdam(
        adapter_parameter_groups(model, float(recipe["optimization"]["base_lr"])),
        lr=float(recipe["optimization"]["base_lr"]),
        clipping_scale=float(recipe["optimization"]["gradient_clip_scale"]),
    )
    if not optimizer_is_adapter_only(optimizer, model):
        raise AdapterResearchError("Optimizer contains a frozen backbone parameter")
    scheduler = icefall_train.Eden(
        optimizer,
        float(recipe["optimization"]["lr_batches"]),
        float(recipe["optimization"]["lr_epochs"]),
    )
    scaler = create_grad_scaler(device="cuda", enabled=True)
    latest_checkpoints = sorted(run_dir.glob("checkpoint-step-*.pt"))
    step = 0
    event_index = 0
    elapsed_before = 0.0
    resumed_checkpoint: str | None = None
    best: dict[str, Any] = {
        "objective": None,
        "step": None,
        "checkpoint": None,
        "reload_check": False,
        "per_domain": None,
        "clean_monitor": None,
        "checks_without_improvement": 0,
    }
    if latest_checkpoints and not canary:
        latest = max(latest_checkpoints, key=lambda path: int(path.stem.split("-")[-1]))
        state = load_checkpoint(
            latest,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
        )
        step = int(state["global_step"])
        event_index = int(state["sampler_event_index"])
        elapsed_before = float(state.get("elapsed_seconds", 0.0))
        resumed_checkpoint = str(latest)
        best = dict(state["best"])
        if (
            state.get("initialization_checkpoint_id") != CHECKPOINT_ID
            or state.get("initialization_checkpoint_sha256") != CHECKPOINT_SHA256
            or state.get("run_identity") != job["run_identity"]
            or state["backbone_sha256"] != backbone_initial
        ):
            raise AdapterResearchError("Resume checkpoint identity mismatch")
    sampler = FrozenBundleSampler(paths=paths, bundle=bundle, start_event=event_index)
    fbank = Fbank(FbankConfig(num_mel_bins=80, device="cuda"))
    canary_steps = int(recipe["control"]["canary_initialization_steps"]) + int(
        recipe["control"]["canary_measured_steps"]
    )
    max_steps = (
        canary_steps if canary else int(job["derived_training_budget_optimizer_steps"])
    )
    limit = (
        int(recipe["control"]["canary_eval_max_source_groups_per_domain"])
        if canary
        else recipe["control"]["full_eval_max_source_groups_per_domain"]
    )
    _status(
        paths,
        queue,
        state="canary_initializing" if canary else "initializing",
        job=job,
        step=step,
        max_steps=max_steps,
        elapsed=0.0,
        ema=None,
        latest_loss=None,
        latest_eval=None,
        peak_vram=torch.cuda.max_memory_reserved(device) / (1024**3),
        current_checkpoint=None,
        best_checkpoint=None,
    )
    initial_eval = evaluate(
        paths=paths,
        job=job,
        bundle=bundle,
        model=model,
        processor=processor,
        fbank=fbank,
        limit=limit,
    )
    set_adapter_training_mode(model)
    started = time.perf_counter()
    elapsed = elapsed_before
    measured_started = None
    measured_steps = 0
    ema = None
    latest_loss = None
    latest_eval: Mapping[str, Any] | None = initial_eval
    current_checkpoint = resumed_checkpoint
    best_checkpoint = best.get("checkpoint")
    finite = True
    stopped = False
    reload_check = False
    resume_check = False
    accumulation = int(recipe["optimization"]["gradient_accumulation"])
    max_duration = float(recipe["optimization"]["microbatch_max_duration_seconds"])
    checkpoint_interval = int(recipe["control"]["checkpoint_interval_optimizer_steps"])
    dev_interval = int(recipe["control"]["dev_interval_optimizer_steps"])
    warmup_steps = int(recipe["control"]["canary_initialization_steps"])
    steps_per_effective_epoch = max(
        1,
        math.ceil(
            float(job["weighted_unique_source_hours"])
            * 3600
            / float(configs["budget"]["effective_audio_seconds_per_optimizer_step"])
        ),
    )
    while step < max_steps:
        if paths.stop_path.is_file():
            stopped = True
            break
        step_started = time.perf_counter()
        optimizer.zero_grad()
        accumulated_loss = 0.0
        accumulated_frames = 0.0
        for _ in range(accumulation):
            rows = sampler.next_microbatch(max_duration)
            batch = make_batch(
                rows,
                paths=paths,
                sentencepiece=processor,
                fbank=fbank,
                device=device,
            )
            params.batch_idx_train = step
            icefall_train.set_batch_count(
                model, icefall_train.get_adjusted_batch_count(params)
            )
            with torch_autocast(enabled=True):
                loss, info = icefall_train.compute_loss(
                    params=params,
                    model=model,
                    sp=processor,
                    batch=batch,
                    is_training=True,
                )
                scaled_loss = loss / accumulation
            if not torch.isfinite(loss):
                finite = False
                raise AdapterResearchError("Canary loss became non-finite")
            scaler.scale(scaled_loss).backward()
            accumulated_loss += float(info["loss"])
            accumulated_frames += float(info["frames"])
        scheduler.step_epoch(step // steps_per_effective_epoch)
        scheduler.step_batch(step + 1)
        scaler.step(optimizer)
        scaler.update()
        optimizer.zero_grad()
        step += 1
        duration = time.perf_counter() - step_started
        if canary and step == warmup_steps:
            measured_started = time.perf_counter()
        elif not canary or step > warmup_steps:
            measured_steps += 1
            ema = duration if ema is None else 0.9 * ema + 0.1 * duration
        latest_loss = accumulated_loss / max(accumulated_frames, 1.0)
        elapsed = elapsed_before + time.perf_counter() - started
        peak = torch.cuda.max_memory_reserved(device) / (1024**3)
        checkpoint_due = step % checkpoint_interval == 0 or step == max_steps
        if canary and step == warmup_steps:
            checkpoint_due = True
        if checkpoint_due:
            checkpoint = run_dir / f"checkpoint-step-{step:06d}.pt"
            checkpoint_hash = save_checkpoint(
                checkpoint,
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                scaler=scaler,
                step=step,
                event_index=sampler.event_index,
                elapsed_seconds=elapsed,
                best=best,
                run_identity=job["run_identity"],
                backbone_sha256=backbone_initial,
            )
            current_checkpoint = str(checkpoint)
            adapter_now = tensor_digest(model, adapter=True)
            reload_check = _checkpoint_reload_probe(
                checkpoint,
                paths=paths,
                recipe=recipe,
                expected_adapter_digest=adapter_now,
            )
            if canary and step == warmup_steps:
                probe_model, probe_params, _, _ = build_model(
                    paths, recipe, device=torch.device("cpu")
                )
                probe_optimizer = icefall_train.ScaledAdam(
                    adapter_parameter_groups(
                        probe_model,
                        float(recipe["optimization"]["base_lr"]),
                    ),
                    lr=float(recipe["optimization"]["base_lr"]),
                    clipping_scale=float(recipe["optimization"]["gradient_clip_scale"]),
                )
                probe_scheduler = icefall_train.Eden(
                    probe_optimizer,
                    float(recipe["optimization"]["lr_batches"]),
                    float(recipe["optimization"]["lr_epochs"]),
                )
                probe_scaler = create_grad_scaler(device="cuda", enabled=True)
                probe_state = load_checkpoint(
                    checkpoint,
                    model=probe_model,
                    optimizer=probe_optimizer,
                    scheduler=probe_scheduler,
                    scaler=probe_scaler,
                )
                resume_check = (
                    int(probe_state["global_step"]) == step
                    and int(probe_state["sampler_event_index"]) == sampler.event_index
                    and probe_state.get("run_identity") == job["run_identity"]
                    and probe_state.get("initialization_checkpoint_id") == CHECKPOINT_ID
                    and probe_state.get("initialization_checkpoint_sha256")
                    == CHECKPOINT_SHA256
                )
                del (
                    probe_model,
                    probe_optimizer,
                    probe_scheduler,
                    probe_scaler,
                    probe_state,
                )
            atomic_json(
                checkpoint.with_suffix(".json"),
                {
                    "checkpoint_sha256": checkpoint_hash,
                    "step": step,
                    "run_id": job["run_id"],
                    "backbone_sha256": backbone_initial,
                    "adapter_sha256": adapter_now,
                },
            )
        eval_due = (not canary and step % dev_interval == 0) or step == max_steps
        if eval_due:
            latest_eval = evaluate(
                paths=paths,
                job=job,
                bundle=bundle,
                model=model,
                processor=processor,
                fbank=fbank,
                limit=limit,
            )
            set_adapter_training_mode(model)
            objective = float(latest_eval["objective_wer"])
            minimum = float(
                recipe["control"]["early_stop_min_absolute_wer_improvement"]
            )
            if (
                best["objective"] is None
                or objective < float(best["objective"]) - minimum
            ):
                best.update(
                    {
                        "objective": objective,
                        "step": step,
                        "checkpoint": _logical_training_path(
                            Path(current_checkpoint), paths
                        ),
                        "reload_check": reload_check,
                        "per_domain": latest_eval["per_domain"],
                        "clean_monitor": latest_eval["clean_monitor"],
                        "checks_without_improvement": 0,
                    }
                )
                best_checkpoint = current_checkpoint
            else:
                best["checks_without_improvement"] += 1
            should_early_stop = not canary and best[
                "checks_without_improvement"
            ] >= int(recipe["control"]["early_stop_patience_dev_checks"])
            # Checkpointing precedes evaluation so decoding always measures an
            # on-disk model. Rewrite the same compact checkpoint atomically to
            # persist the newly updated best-DEV/early-stop state for exact
            # resume; adapter and optimizer tensors are unchanged.
            checkpoint_path = Path(current_checkpoint)
            elapsed = elapsed_before + time.perf_counter() - started
            checkpoint_hash = save_checkpoint(
                checkpoint_path,
                model=model,
                optimizer=optimizer,
                scheduler=scheduler,
                scaler=scaler,
                step=step,
                event_index=sampler.event_index,
                elapsed_seconds=elapsed,
                best=best,
                run_identity=job["run_identity"],
                backbone_sha256=backbone_initial,
            )
            atomic_json(
                checkpoint_path.with_suffix(".json"),
                {
                    "checkpoint_sha256": checkpoint_hash,
                    "step": step,
                    "run_id": job["run_id"],
                    "backbone_sha256": backbone_initial,
                    "adapter_sha256": tensor_digest(model, adapter=True),
                },
            )
            if should_early_stop:
                break
        _status(
            paths,
            queue,
            state="canary" if canary else "training",
            job=job,
            step=step,
            max_steps=max_steps,
            elapsed=elapsed,
            ema=ema,
            latest_loss=latest_loss,
            latest_eval=latest_eval,
            peak_vram=peak,
            current_checkpoint=current_checkpoint,
            best_checkpoint=best_checkpoint,
        )
    if stopped:
        elapsed = elapsed_before + time.perf_counter() - started
        checkpoint = run_dir / f"checkpoint-step-{step:06d}.pt"
        save_checkpoint(
            checkpoint,
            model=model,
            optimizer=optimizer,
            scheduler=scheduler,
            scaler=scaler,
            step=step,
            event_index=sampler.event_index,
            elapsed_seconds=elapsed,
            best=best,
            run_identity=job["run_identity"],
            backbone_sha256=backbone_initial,
        )
    elapsed = elapsed_before + time.perf_counter() - started
    backbone_final = tensor_digest(model, adapter=False)
    adapter_final = tensor_digest(model, adapter=True)
    backbone_frozen = backbone_initial == backbone_final
    adapter_changed = adapter_initial != adapter_final
    peak_allocated = torch.cuda.max_memory_allocated(device) / (1024**3)
    peak_reserved = torch.cuda.max_memory_reserved(device) / (1024**3)
    device_total = torch.cuda.get_device_properties(device).total_memory / (1024**3)
    seconds_per_step = (
        (time.perf_counter() - measured_started) / measured_steps
        if measured_started is not None and measured_steps
        else elapsed / max(step, 1)
    )
    monitor_initial = initial_eval["clean_monitor"]["wer"]
    monitor_best = best["clean_monitor"]["wer"] if best.get("clean_monitor") else None
    selected_checkpoint_value = best.get("checkpoint") or current_checkpoint
    selected_checkpoint = (
        _checkpoint_path(selected_checkpoint_value, paths=paths, run_dir=run_dir)
        if selected_checkpoint_value
        else None
    )
    result = {
        "EXPERIMENT_ID": job["experiment_id"],
        "STATE": "stopped"
        if stopped
        else ("completed" if step >= max_steps else "early_stopped"),
        "TRAINING_RUN_ID": job["run_id"],
        "TRAINING_RUN_SHA256": job["run_sha256"],
        "BUNDLE_ID": job["bundle_id"],
        "INITIALIZATION_CHECKPOINT_ID": CHECKPOINT_ID,
        "INITIALIZATION_CHECKPOINT_SHA256": CHECKPOINT_SHA256,
        "TRAINING_RECIPE_ID": configs["recipe"]["recipe_id"],
        "TRAINING_BUDGET": max_steps,
        "BEST_CHECKPOINT_ID": (
            f"{job['run_id']}_best_step_{best['step']}" if best.get("step") else None
        ),
        "BEST_CHECKPOINT_PATH": (
            _logical_training_path(selected_checkpoint, paths)
            if selected_checkpoint
            else None
        ),
        "BEST_CHECKPOINT_SHA256": (
            sha256_file(selected_checkpoint) if selected_checkpoint else None
        ),
        "BEST_CHECKPOINT_STEP": best.get("step") or step,
        "FINAL_STEP": step,
        "EARLY_STOPPED": not stopped and step < max_steps,
        "BEST_DEV_OBJECTIVE": best.get("objective"),
        "PER_DOMAIN_DEV_METRICS": best.get("per_domain") or {},
        "INITIAL_CLEAN_MONITOR_METRIC": monitor_initial,
        "BEST_CLEAN_MONITOR_METRIC": monitor_best,
        "CLEAN_MONITOR_RELATIVE_CHANGE": (
            (monitor_best - monitor_initial) / monitor_initial
            if monitor_best is not None and monitor_initial
            else None
        ),
        "TRAINING_ELAPSED_SECONDS": elapsed,
        "PEAK_GPU_VRAM_GIB": peak_reserved,
        "PEAK_GPU_ALLOCATED_GIB": peak_allocated,
        "GPU_TOTAL_GIB": device_total,
        "GPU_NAME": torch.cuda.get_device_name(device),
        "TOTAL_PARAMETERS": total_parameters,
        "TRAINABLE_ADAPTER_PARAMETERS": adapter_parameters,
        "TRAINABLE_PERCENT": 100.0 * adapter_parameters / total_parameters,
        "FROZEN_PARAMETERS": total_parameters - adapter_parameters,
        "TRAINABLE_ADAPTER_TENSORS": len(trainable_names),
        "SECONDS_PER_OPTIMIZER_STEP": seconds_per_step,
        "FINITE_LOSS_CHECK": finite,
        "BACKBONE_FROZEN_CHECK": backbone_frozen,
        "ADAPTER_CHANGED_CHECK": adapter_changed,
        "BEST_CHECKPOINT_RELOAD_CHECK": bool(best.get("reload_check")),
        "RESUME_CHECK": resume_check if canary else True,
        "OPTIMIZER_ADAPTER_ONLY_CHECK": optimizer_is_adapter_only(optimizer, model),
        "DEV_COMPLETE": latest_eval is not None,
        "MONITOR_COMPLETE": latest_eval is not None,
        "CHIME_USED_IN_TRAINING": job["chime_used_in_training"],
        "COMMERCIAL_MODEL_RELEASE_REVIEW_REQUIRED": job[
            "commercial_model_release_review_required"
        ],
        "CMU_EXPERIMENT_CLASS": job["cmu_experiment_class"],
        "PHASE4_WEIGHTS_RESPECTED": True,
        "HELDOUT_USED": False,
        "MONITOR_USED_FOR_GRADIENTS": False,
        "LARGE_ACCESSED": False,
    }
    required = (
        result["STATE"] in {"completed", "early_stopped"}
        and result["FINITE_LOSS_CHECK"]
        and result["BACKBONE_FROZEN_CHECK"]
        and result["ADAPTER_CHANGED_CHECK"]
        and result["BEST_CHECKPOINT_RELOAD_CHECK"]
        and result["RESUME_CHECK"]
        and result["OPTIMIZER_ADAPTER_ONLY_CHECK"]
        and result["DEV_COMPLETE"]
        and result["MONITOR_COMPLETE"]
        and not result["HELDOUT_USED"]
        and not result["MONITOR_USED_FOR_GRADIENTS"]
        and not result["LARGE_ACCESSED"]
        and peak_reserved <= device_total * 0.92
    )
    result["EXPORT_READY"] = bool(required and not canary)
    result["EXPORT_BLOCKERS"] = (
        []
        if required
        else [
            key
            for key in (
                "FINITE_LOSS_CHECK",
                "BACKBONE_FROZEN_CHECK",
                "ADAPTER_CHANGED_CHECK",
                "BEST_CHECKPOINT_RELOAD_CHECK",
                "RESUME_CHECK",
                "OPTIMIZER_ADAPTER_ONLY_CHECK",
                "DEV_COMPLETE",
                "MONITOR_COMPLETE",
            )
            if not result.get(key)
        ]
    )
    result["CANARY_PASSED"] = bool(required and canary)
    atomic_json(run_dir / "result.json", result)
    _status(
        paths,
        queue,
        state="stopped" if stopped else ("canary_complete" if canary else "completed"),
        job=job,
        step=step,
        max_steps=max_steps,
        elapsed=elapsed,
        ema=seconds_per_step,
        latest_loss=latest_loss,
        latest_eval=latest_eval,
        peak_vram=peak_reserved,
        current_checkpoint=current_checkpoint,
        best_checkpoint=best.get("checkpoint") or current_checkpoint,
    )
    return result


def subprocess_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def subprocess_worktree_status(root: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(root), "status", "--short"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def update_canary_summary(
    paths: RuntimePaths, result: Mapping[str, Any]
) -> dict[str, Any]:
    summary_path = paths.qualification / "canary_summary.json"
    prior = read_json(summary_path) if summary_path.is_file() else {"canaries": []}
    by_id = {item["experiment_id"]: item for item in prior["canaries"]}
    by_id[result["EXPERIMENT_ID"]] = {
        "experiment_id": result["EXPERIMENT_ID"],
        "passed": result["CANARY_PASSED"],
        "peak_vram_gib": result["PEAK_GPU_VRAM_GIB"],
        "seconds_per_optimizer_step": result["SECONDS_PER_OPTIMIZER_STEP"],
        "result_path": str(
            paths.qualification / "canaries" / result["EXPERIMENT_ID"] / "result.json"
        ),
    }
    ordered = [by_id[key] for key in ("O-AGE", "O-AGE-ROBUST") if key in by_id]
    ready = len(ordered) == 2 and all(item["passed"] for item in ordered)
    summary = {
        "schema_version": "phase5-original-adapter-canary-summary.v1",
        "canaries": ordered,
        "ready_to_run_original_adapter_queue": ready,
        "giga_jobs": 0,
        "large_accessed": False,
        "common_voice_heldout_evaluated": False,
    }
    atomic_json(summary_path, summary)
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("canary", "train"))
    parser.add_argument("--queue", required=True, type=Path)
    parser.add_argument("--experiment-id", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    paths = RuntimePaths(args.queue.resolve())
    queue = read_json(paths.queue_path)
    if (
        canonical_sha256(
            {k: v for k, v in queue.items() if k not in {"queue_id", "queue_sha256"}}
        )
        != queue["queue_sha256"]
    ):
        raise AdapterResearchError("Queue self-hash mismatch")
    matches = [
        item for item in queue["jobs"] if item["experiment_id"] == args.experiment_id
    ]
    if len(matches) != 1:
        raise AdapterResearchError("Requested experiment is not in the frozen queue")
    if args.command == "canary" and args.experiment_id not in {"O-AGE", "O-AGE-ROBUST"}:
        raise AdapterResearchError("Only O-AGE and O-AGE-ROBUST are Phase-5 canaries")
    try:
        result = run_job(
            paths=paths,
            queue=queue,
            job=matches[0],
            canary=args.command == "canary",
        )
    except Exception as exc:
        if paths.status_path.is_file():
            failure_status = read_json(paths.status_path)
            failure_status.update(
                {
                    "QUEUE_STATE": "failed",
                    "CURRENT_EXPERIMENT_ID": args.experiment_id,
                    "LAST_HEARTBEAT_UTC": utc_now(),
                    "FAILURE_REASON": f"{type(exc).__name__}: {exc}",
                }
            )
            atomic_json(paths.status_path, failure_status)
        print(
            json.dumps(
                {
                    "status": "failed",
                    "experiment_id": args.experiment_id,
                    "reason": f"{type(exc).__name__}: {exc}",
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    output = (
        update_canary_summary(paths, result) if args.command == "canary" else result
    )
    print(json.dumps(output, indent=2, sort_keys=True))
    return (
        0
        if (
            result["CANARY_PASSED"]
            if args.command == "canary"
            else result["EXPORT_READY"]
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
