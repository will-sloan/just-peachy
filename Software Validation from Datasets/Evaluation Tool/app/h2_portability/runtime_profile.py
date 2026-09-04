"""Separately versioned H2 ONNX runtime profile for the common factory.

The native ``H2_REFERENCE`` construction remains the default.  This module is
imported only when the caller explicitly selects ``H2_PORTABLE_ONNX_FP32``.
ONNX Runtime itself stays inside the pinned ReDimNet2 worker environment; the
common coordinator continues to exchange the same backend-neutral values.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Mapping

from app.full_pipeline.cache import ContentAddressedCache
from app.full_pipeline.models import ComponentRuntimeIdentity
from app.full_pipeline.runtime_components import (
    WorkerEmbeddingAdapter,
    WorkerStreamingSegmenter,
)
from app.full_pipeline.segmentation import RollingSegmentationConfig
from app.full_pipeline.workers import PersistentWorker, WorkerSpec
from app.utils.paths import repository_root

from .contracts import FP32_ONLY, ONNX_OPSET
from .interpreters import resolve_worker_interpreter
from .onnx_tooling import canonical_sha256, sha256_file


H2_REFERENCE = "H2_REFERENCE"
H2_PORTABLE_ONNX_FP32 = "H2_PORTABLE_ONNX_FP32"
H2_PORTABLE_RUNTIME_PROFILE_VERSION = "h2-portable-onnx-runtime-profile.v1"
SUPPORTED_H2_RUNTIME_PROFILES = (H2_REFERENCE, H2_PORTABLE_ONNX_FP32)
REDIM_COMPONENT = "redimnet2_b2_speaker_embedding"
SEGMENTATION_COMPONENT = "pyannote_segmentation_3_0"


class H2RuntimeProfileError(RuntimeError):
    """The requested H2 runtime profile is absent or inconsistent."""


@dataclass(frozen=True)
class H2PortableRuntimeConfig:
    redimnet2_path: Path
    segmentation_path: Path
    expected_sha256: Mapping[str, str]
    threads: int = 1
    redim_execution_strategy: str = "R2_ONE_SHARED_MODEL"

    def __post_init__(self) -> None:
        redim = Path(self.redimnet2_path).resolve()
        segmentation = Path(self.segmentation_path).resolve()
        object.__setattr__(self, "redimnet2_path", redim)
        object.__setattr__(self, "segmentation_path", segmentation)
        expected = {str(key): str(value).lower() for key, value in self.expected_sha256.items()}
        if set(expected) != {REDIM_COMPONENT, SEGMENTATION_COMPONENT}:
            raise H2RuntimeProfileError("both exact H2 ONNX graph hashes are required")
        if self.threads < 1:
            raise H2RuntimeProfileError("ONNX worker threads must be at least one")
        if self.redim_execution_strategy not in {
            "R1_TWO_INDEPENDENT_MODELS",
            "R2_ONE_SHARED_MODEL",
            "R3_EXACT_WINDOW_EMBEDDING_REUSE",
            "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
        }:
            raise H2RuntimeProfileError("unsupported portable H2 ReDim strategy")
        for component_id, path in (
            (REDIM_COMPONENT, redim),
            (SEGMENTATION_COMPONENT, segmentation),
        ):
            if not path.is_file():
                raise FileNotFoundError(path)
            observed = sha256_file(path)
            if observed != expected[component_id]:
                raise H2RuntimeProfileError(
                    f"ONNX graph hash mismatch for {component_id}: "
                    f"expected {expected[component_id]}, observed {observed}"
                )
        object.__setattr__(self, "expected_sha256", expected)

    def to_jsonable(self) -> dict[str, object]:
        return {
            "runtime_profile_id": H2_PORTABLE_ONNX_FP32,
            "runtime_profile_version": H2_PORTABLE_RUNTIME_PROFILE_VERSION,
            "precision": FP32_ONLY,
            "opset": ONNX_OPSET,
            "redimnet2_path": str(self.redimnet2_path),
            "segmentation_path": str(self.segmentation_path),
            "graph_sha256": dict(sorted(self.expected_sha256.items())),
            "threads": self.threads,
            "redim_execution_strategy": self.redim_execution_strategy,
            "shared_redimnet2_session": self.redim_execution_strategy
            != "R1_TWO_INDEPENDENT_MODELS",
            "implicit_downloads_allowed": False,
            "scientific_policy_changed": False,
            "linux_arm64_hardware_qualified": False,
        }

    @property
    def identity_sha256(self) -> str:
        return canonical_sha256(self.to_jsonable())


@dataclass(frozen=True)
class H2PortableAdapterSet:
    segmenter: WorkerStreamingSegmenter
    diarization_embedder: WorkerEmbeddingAdapter
    identity_embedder: WorkerEmbeddingAdapter
    profile_config: H2PortableRuntimeConfig


class _ComponentWorkerFacade:
    """Expose one component identity while sharing one ONNX worker process."""

    def __init__(
        self,
        worker: PersistentWorker,
        *,
        component_id: str,
        role: str,
        component_identity: Mapping[str, object],
    ) -> None:
        self._worker = worker
        self.spec = SimpleNamespace(component_id=component_id)
        self._role = role
        self._identity = dict(component_identity)

    def start(self) -> dict[str, object]:
        portable = self._worker.start()
        self._validate_portable_identity(portable)
        return dict(self._identity)

    def call(self, operation: str, payload: Mapping[str, object], **kwargs) -> dict[str, object]:
        result = self._worker.call(operation, payload, **kwargs)
        portable = result.get("identity")
        if not isinstance(portable, Mapping):
            raise H2RuntimeProfileError("portable ONNX worker omitted its identity")
        self._validate_portable_identity(portable)
        return {
            **result,
            "portable_worker_identity": dict(portable),
            "identity": dict(self._identity),
        }

    def reset(self) -> dict[str, object]:
        return self._worker.reset()

    def shutdown(self) -> None:
        self._worker.shutdown()

    def status(self) -> dict[str, object]:
        value = self._worker.status()
        return {
            **value,
            "worker_id": f"{value.get('worker_id')}:{self._role}",
            "component_id": self.spec.component_id,
            "identity": dict(self._identity),
            "portable_worker_identity": value.get("identity"),
        }

    @staticmethod
    def _validate_portable_identity(value: Mapping[str, object]) -> None:
        if value.get("runtime_profile_id") != H2_PORTABLE_ONNX_FP32:
            raise H2RuntimeProfileError("worker is not the H2 ONNX runtime profile")
        if value.get("linux_arm64_hardware_qualified") is not False:
            raise H2RuntimeProfileError("worker made an unsupported ARM64 claim")


def _worker_spec(
    config: H2PortableRuntimeConfig,
    *,
    worker_id: str,
    warmup_audio_path: Path,
    warmup_audio_sha256: str,
) -> WorkerSpec:
    configured_python = os.environ.get("JP_H2_ONNX_WORKER_PYTHON")
    if configured_python:
        interpreter_path = Path(configured_python).expanduser().resolve()
        if not interpreter_path.is_file():
            raise H2RuntimeProfileError(
                "JP_H2_ONNX_WORKER_PYTHON is not an existing interpreter: "
                f"{interpreter_path}"
            )
    else:
        interpreter = resolve_worker_interpreter(
            "redimnet2", repository=repository_root().path
        )
        if interpreter.path is None:  # pragma: no cover - resolver fails first.
            raise H2RuntimeProfileError("redimnet2 worker interpreter is unavailable")
        interpreter_path = interpreter.path
    command = (
        str(interpreter_path),
        "-u",
        "-m",
        "app.full_pipeline.worker_main",
        "--worker-id",
        worker_id,
        "--kind",
        "h2_portable_onnx",
        "--component",
        "h2_portable_onnx_fp32",
        "--h2-redim-onnx",
        str(config.redimnet2_path),
        "--h2-segmentation-onnx",
        str(config.segmentation_path),
        "--h2-redim-sha256",
        str(config.expected_sha256[REDIM_COMPONENT]),
        "--h2-segmentation-sha256",
        str(config.expected_sha256[SEGMENTATION_COMPONENT]),
    )
    return WorkerSpec(
        worker_id=worker_id,
        kind="h2_portable_onnx",
        component_id="h2_portable_onnx_fp32",
        environment_profile="redimnet2",
        startup_timeout_sec=120.0,
        request_timeout_sec=180.0,
        command_override=command,
        warmup_request={
            "audio_path": str(Path(warmup_audio_path).resolve()),
            "audio_sha256": warmup_audio_sha256,
            "recording_id": f"{worker_id}-model-warmup",
            "chunk_id": "portable-model-warmup",
            "window_id": "portable-model-warmup",
            "role": "model_warmup",
            "start_sec": 0.0,
            "end_sec": 10.0,
            "source_timestamp_offset_sec": 0.0,
            "algorithmic_lookahead_sec": 5.0,
        },
    )


def _component_identity(
    *,
    component_id: str,
    profile: H2PortableRuntimeConfig,
    backend_config_sha256: str | None = None,
    segmentation_asset_files: Mapping[str, str] | None = None,
) -> dict[str, object]:
    core = {
        "kind": "h2_portable_onnx_component_facade",
        "component_id": component_id,
        "runtime_profile_id": H2_PORTABLE_ONNX_FP32,
        "runtime_profile_identity_sha256": profile.identity_sha256,
        "graph_sha256": dict(profile.expected_sha256),
        "declared_backend": (
            {"config_hash": backend_config_sha256}
            if backend_config_sha256 is not None
            else None
        ),
        "model_asset_files": dict(segmentation_asset_files or {}),
        "implicit_model_downloads_allowed": False,
        "linux_arm64_hardware_qualified": False,
    }
    return {**core, "declared_identity_sha256": canonical_sha256(core)}


def build_h2_portable_adapters(
    *,
    config: H2PortableRuntimeConfig,
    session_id: str,
    work_root: Path,
    warmup_audio_path: Path,
    warmup_audio_sha256: str,
    shared_cache: ContentAddressedCache,
    worker_for: Callable[[object], object],
    segmentation_config: RollingSegmentationConfig,
    segmentation_asset_files: Mapping[str, str],
    embedding_backend_id: str,
    embedding_config_sha256: str,
    embedding_model_id: str,
    embedding_model_sha256: str,
    lazy_worker_start: bool,
) -> H2PortableAdapterSet:
    if embedding_backend_id != REDIM_COMPONENT:
        raise H2RuntimeProfileError(
            "H2_PORTABLE_ONNX_FP32 supports only the frozen H2 ReDimNet2 backend"
        )
    spec = _worker_spec(
        config,
        worker_id=f"{session_id}-h2-portable-onnx",
        warmup_audio_path=warmup_audio_path,
        warmup_audio_sha256=warmup_audio_sha256,
    )
    raw_worker = worker_for(spec)
    if not isinstance(raw_worker, PersistentWorker):
        # Pools can return a compatible proxy; perform structural validation.
        if not all(hasattr(raw_worker, name) for name in ("start", "call", "reset", "shutdown", "status")):
            raise TypeError("portable worker pool result is incompatible")
    segment_facade = _ComponentWorkerFacade(
        raw_worker,  # type: ignore[arg-type]
        component_id=SEGMENTATION_COMPONENT,
        role="segmentation",
        component_identity=_component_identity(
            component_id=SEGMENTATION_COMPONENT,
            profile=config,
            segmentation_asset_files=segmentation_asset_files,
        ),
    )
    embedding_facade = _ComponentWorkerFacade(
        raw_worker,  # type: ignore[arg-type]
        component_id=embedding_backend_id,
        role=(
            "shared_embedding"
            if config.redim_execution_strategy != "R1_TWO_INDEPENDENT_MODELS"
            else "diarization_embedding"
        ),
        component_identity=_component_identity(
            component_id=embedding_backend_id,
            profile=config,
            backend_config_sha256=embedding_config_sha256,
        ),
    )
    profile_cache = ContentAddressedCache(
        shared_cache.root / "runtime_profiles" / config.identity_sha256
    )
    segmenter = WorkerStreamingSegmenter(
        segment_facade,  # type: ignore[arg-type]
        work_root,
        cache=profile_cache,
        expected_model_asset_files=segmentation_asset_files,
        lazy_worker_start=lazy_worker_start,
        config=segmentation_config,
    )
    embedder = WorkerEmbeddingAdapter(
        worker=embedding_facade,  # type: ignore[arg-type]
        work_root=work_root,
        backend_config_sha256=embedding_config_sha256,
        model_id=embedding_model_id,
        # Profiles remain bound to the exact native checkpoint identity.  The
        # additional ONNX graph identity is carried in runtime provenance.
        model_sha256=embedding_model_sha256,
        cache=profile_cache,
        lazy_worker_start=lazy_worker_start,
    )
    identity_embedder = embedder
    if config.redim_execution_strategy == "R1_TWO_INDEPENDENT_MODELS":
        identity_spec = _worker_spec(
            config,
            worker_id=f"{session_id}-h2-portable-onnx-identity",
            warmup_audio_path=warmup_audio_path,
            warmup_audio_sha256=warmup_audio_sha256,
        )
        identity_worker = worker_for(identity_spec)
        if not isinstance(identity_worker, PersistentWorker) and not all(
            hasattr(identity_worker, name)
            for name in ("start", "call", "reset", "shutdown", "status")
        ):
            raise TypeError("portable identity worker pool result is incompatible")
        identity_facade = _ComponentWorkerFacade(
            identity_worker,  # type: ignore[arg-type]
            component_id=embedding_backend_id,
            role="identity_embedding",
            component_identity=_component_identity(
                component_id=embedding_backend_id,
                profile=config,
                backend_config_sha256=embedding_config_sha256,
            ),
        )
        identity_embedder = WorkerEmbeddingAdapter(
            worker=identity_facade,  # type: ignore[arg-type]
            work_root=work_root,
            backend_config_sha256=embedding_config_sha256,
            model_id=embedding_model_id,
            model_sha256=embedding_model_sha256,
            cache=profile_cache,
            lazy_worker_start=lazy_worker_start,
        )
    return H2PortableAdapterSet(
        segmenter=segmenter,
        diarization_embedder=embedder,
        identity_embedder=identity_embedder,
        profile_config=config,
    )


def apply_portable_component_identities(
    identities: Mapping[str, ComponentRuntimeIdentity],
    *,
    profile: H2PortableRuntimeConfig,
    pipeline_config_sha256: str,
) -> dict[str, ComponentRuntimeIdentity]:
    """Add an explicit profile identity and replace only affected backends."""

    values = dict(identities)
    implementation = "app/h2_portability/runtime_profile.py"
    implementation_path = (
        repository_root().path
        / "Software Validation from Datasets"
        / "Evaluation Tool"
        / implementation
    )
    implementation_sha = (
        sha256_file(implementation_path) if implementation_path.is_file() else None
    )
    graph_hashes = tuple(profile.expected_sha256[key] for key in (SEGMENTATION_COMPONENT, REDIM_COMPONENT))

    def identity(family: str, backend: str, model: str | None, assets: tuple[str, ...]):
        return ComponentRuntimeIdentity(
            component_family=family,
            backend_id=backend,
            backend_config_id=H2_PORTABLE_RUNTIME_PROFILE_VERSION,
            backend_config_sha256=profile.identity_sha256,
            pipeline_config_sha256=pipeline_config_sha256,
            model_id=model,
            model_asset_sha256s=assets,
            environment_profile_id="redimnet2",
            environment_fingerprint_sha256=None,
            implementation_id=implementation,
            implementation_sha256=implementation_sha,
        )

    values["runtime_profile"] = identity(
        "runtime_profile",
        H2_PORTABLE_ONNX_FP32,
        None,
        graph_hashes,
    )
    values["segmentation"] = identity(
        "segmentation",
        "pyannote_segmentation_3_0_onnx_fp32",
        "pyannote/segmentation-3.0",
        (profile.expected_sha256[SEGMENTATION_COMPONENT],),
    )
    values["diarization"] = identity(
        "diarization",
        "modular_pyannote_redimnet2_onnx_fp32",
        "H2_DR_ONNX_FP32",
        graph_hashes,
    )
    values["speaker_embedding"] = identity(
        "speaker_embedding",
        "redimnet2_b2_speaker_embedding_onnx_fp32",
        "ReDimNet2-B2",
        (profile.expected_sha256[REDIM_COMPONENT],),
    )
    return values


__all__ = [
    "H2PortableAdapterSet",
    "H2PortableRuntimeConfig",
    "H2RuntimeProfileError",
    "H2_PORTABLE_ONNX_FP32",
    "H2_PORTABLE_RUNTIME_PROFILE_VERSION",
    "H2_REFERENCE",
    "SUPPORTED_H2_RUNTIME_PROFILES",
    "apply_portable_component_identities",
    "build_h2_portable_adapters",
]
