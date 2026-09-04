"""Construct one of the locked 18 pipelines without importing model stacks."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping
import uuid
import wave

from .alignment import TranscriptSpeakerAligner
from .audio import (
    DurationLimitedAudioSource,
    FileAudioSource,
    MicrophoneAudioSource,
    PlaybackAudioSource,
    RecordingAudioSource,
    StreamingAudioNormalizer,
)
from .cache import ContentAddressedCache
from .clustering import OnlineClusterConfig, OnlineClusterManager
from .coordinator import CoordinatorConfig, StreamingPipelineCoordinator
from .enrollment import ProtectedEnrollmentStore
from .identity import (
    FROZEN_IDENTITY_POLICIES,
    SessionIdentityManager,
    challenger_policy,
)
from .matrix import FullPipelineMatrix
from .provenance import runtime_identities
from .product_modes import H2ProductMode, H2RuntimeTuning
from .runtime_components import (
    NativeASRWorkerAdapter,
    WorkerEmbeddingAdapter,
    WorkerStreamingSegmenter,
)
from .segmentation import RollingSegmentationConfig
from .telemetry import RuntimeResourceMonitor
from .workers import (
    PersistentWorker,
    asr_worker_spec,
    embedding_worker_spec,
    segmentation_worker_spec,
)


EVALUATION_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = EVALUATION_ROOT.parents[1]
MATRIX_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml"
)
RUNTIME_CONFIG_PATH = (
    EVALUATION_ROOT / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml"
)
DEFAULT_RESULTS_ROOT = (
    EVALUATION_ROOT / "JustPeachyResults/full_pipeline/runtime_sessions"
)
DEFAULT_ENROLLMENT_ROOT = (
    EVALUATION_ROOT / "JustPeachyResults/full_pipeline/enrollment_profiles"
)
DEFAULT_CACHE_ROOT = EVALUATION_ROOT / "JustPeachyResults/full_pipeline/_shared_cache"


def new_session_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"fullpipe_session_{timestamp}_{uuid.uuid4().hex[:10]}"


def _speaker_embedding_worker_partitions(
    share_runtime_model: bool,
) -> tuple[str, str]:
    """Return cache-independent pool roles for diarization and identity.

    Gallery preparation always owns the identity partition.  R2/R3/R4 must
    therefore put their one shared runtime model in that same partition;
    otherwise a gallery cache miss can leave a second model process resident.
    R1 keeps a separate diarization partition and joins its identity worker to
    the gallery partition, yielding exactly two processes in either cache
    regime.
    """

    identity = "speaker_embedding:identity"
    diarization = identity if share_runtime_model else "speaker_embedding:diarization"
    return diarization, identity


def build_file_runtime(
    *,
    pipeline_id: str,
    input_path: Path,
    output_root: Path | None = None,
    enrollment_root: Path | None = None,
    session_id: str | None = None,
    realtime: bool = False,
    pace: float | None = None,
    duration_sec: float | None = None,
    telemetry_enabled: bool = True,
    cache_root: Path | None = None,
    play_audio: bool = False,
    worker_pool: object | None = None,
    lazy_worker_start: bool = False,
    worker_warmup_audio_path: Path | None = None,
    asr_stream_trace_root: Path | None = None,
    asr_stream_trace_enabled: bool = False,
    evaluation_measurement_mode: str | None = None,
    decision_policy_registry_path: Path | None = None,
    gallery_requested_size: str | int | None = None,
    realized_gallery_size: int | None = None,
    product_mode: H2ProductMode | str | None = None,
    runtime_tuning: H2RuntimeTuning | Mapping[str, object] | None = None,
    runtime_profile: str = "H2_REFERENCE",
    h2_onnx_graphs: Mapping[str, Path] | None = None,
    h2_onnx_expected_sha256: Mapping[str, str] | None = None,
    emit_identity_score_diagnostics: bool = False,
) -> StreamingPipelineCoordinator:
    if asr_stream_trace_enabled and evaluation_measurement_mode != "accuracy":
        raise ValueError(
            "ASR stream trace replay is accuracy-only and is forbidden for "
            "resource measurement"
        )
    replay_pace = (1.0 if realtime else 0.0) if pace is None else float(pace)
    if replay_pace < 0:
        raise ValueError("pace must be non-negative")
    source: Any = FileAudioSource(
        Path(input_path),
        frame_duration_ms=100,
        pace=0.0 if play_audio else replay_pace,
    )
    if duration_sec is not None:
        source = DurationLimitedAudioSource(source, duration_sec)
    if play_audio:
        source = PlaybackAudioSource(source)
    return _build(
        pipeline_id=pipeline_id,
        source=source,
        recording_id=Path(input_path).stem,
        output_root=output_root,
        enrollment_root=enrollment_root,
        session_id=session_id,
        queue_policy="block",
        telemetry_enabled=telemetry_enabled,
        cache_root=cache_root,
        worker_pool=worker_pool,
        lazy_worker_start=lazy_worker_start,
        worker_warmup_audio_path=worker_warmup_audio_path,
        asr_stream_trace_root=asr_stream_trace_root,
        asr_stream_trace_enabled=asr_stream_trace_enabled,
        evaluation_measurement_mode=evaluation_measurement_mode,
        asr_trace_source_path=Path(input_path),
        asr_trace_duration_sec=duration_sec,
        decision_policy_registry_path=decision_policy_registry_path,
        gallery_requested_size=gallery_requested_size,
        realized_gallery_size=realized_gallery_size,
        product_mode=product_mode,
        runtime_tuning=runtime_tuning,
        runtime_profile=runtime_profile,
        h2_onnx_graphs=h2_onnx_graphs,
        h2_onnx_expected_sha256=h2_onnx_expected_sha256,
        emit_identity_score_diagnostics=emit_identity_score_diagnostics,
    )


def build_microphone_runtime(
    *,
    pipeline_id: str,
    duration_sec: float,
    output_root: Path | None = None,
    enrollment_root: Path | None = None,
    session_id: str | None = None,
    device: int | str | None = None,
    source_sample_rate_hz: int | None = None,
    source_channels: int | None = None,
    telemetry_enabled: bool = True,
    cache_root: Path | None = None,
    record_audio_path: Path | None = None,
    product_mode: H2ProductMode | str | None = None,
    runtime_tuning: H2RuntimeTuning | Mapping[str, object] | None = None,
    runtime_profile: str = "H2_REFERENCE",
    h2_onnx_graphs: Mapping[str, Path] | None = None,
    h2_onnx_expected_sha256: Mapping[str, str] | None = None,
) -> StreamingPipelineCoordinator:
    source = DurationLimitedAudioSource(
        MicrophoneAudioSource(
            device=device,
            source_sample_rate_hz=source_sample_rate_hz,
            source_channels=source_channels,
            frame_duration_ms=100,
        ),
        duration_sec,
    )
    if record_audio_path is not None:
        source = RecordingAudioSource(source, Path(record_audio_path))
    return _build(
        pipeline_id=pipeline_id,
        source=source,
        recording_id="live_microphone",
        output_root=output_root,
        enrollment_root=enrollment_root,
        session_id=session_id,
        queue_policy="drop_oldest",
        telemetry_enabled=telemetry_enabled,
        cache_root=cache_root,
        worker_pool=None,
        lazy_worker_start=False,
        worker_warmup_audio_path=None,
        asr_stream_trace_root=None,
        asr_stream_trace_enabled=False,
        evaluation_measurement_mode=None,
        asr_trace_source_path=None,
        asr_trace_duration_sec=duration_sec,
        decision_policy_registry_path=None,
        gallery_requested_size=None,
        realized_gallery_size=None,
        product_mode=product_mode,
        runtime_tuning=runtime_tuning,
        runtime_profile=runtime_profile,
        h2_onnx_graphs=h2_onnx_graphs,
        h2_onnx_expected_sha256=h2_onnx_expected_sha256,
        emit_identity_score_diagnostics=False,
    )


def _build(
    *,
    pipeline_id: str,
    source: Any,
    recording_id: str,
    output_root: Path | None,
    enrollment_root: Path | None,
    session_id: str | None,
    queue_policy: str,
    telemetry_enabled: bool,
    cache_root: Path | None,
    worker_pool: object | None,
    lazy_worker_start: bool,
    worker_warmup_audio_path: Path | None,
    asr_stream_trace_root: Path | None,
    asr_stream_trace_enabled: bool,
    evaluation_measurement_mode: str | None,
    asr_trace_source_path: Path | None,
    asr_trace_duration_sec: float | None,
    decision_policy_registry_path: Path | None,
    gallery_requested_size: str | int | None,
    realized_gallery_size: int | None,
    product_mode: H2ProductMode | str | None,
    runtime_tuning: H2RuntimeTuning | Mapping[str, object] | None,
    runtime_profile: str = "H2_REFERENCE",
    h2_onnx_graphs: Mapping[str, Path] | None = None,
    h2_onnx_expected_sha256: Mapping[str, str] | None = None,
    emit_identity_score_diagnostics: bool = False,
) -> StreamingPipelineCoordinator:
    session_id = session_id or new_session_id()
    run_root = (
        Path(output_root).resolve()
        if output_root
        else (DEFAULT_RESULTS_ROOT / session_id)
    )
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    selection = matrix.resolve(pipeline_id)
    tuning = H2RuntimeTuning.coerce(runtime_tuning, product_mode=product_mode)
    runtime_profile_id = str(runtime_profile or "H2_REFERENCE").strip().upper()
    if tuning is not None and selection.hybrid_label != "H2":
        raise ValueError(
            "H2 product modes/tuning may only be used with an H2 pipeline"
        )
    work_root = run_root / "runtime_work"
    warmup_audio = _resolve_worker_warmup_audio(
        work_root=work_root,
        worker_warmup_audio_path=worker_warmup_audio_path,
    )
    warmup_sha256 = hashlib.sha256(warmup_audio.read_bytes()).hexdigest()
    shared_cache = ContentAddressedCache(
        Path(cache_root).resolve() if cache_root is not None else DEFAULT_CACHE_ROOT
    )

    def worker_for(spec: object) -> object:
        if worker_pool is None:
            return PersistentWorker(spec)  # type: ignore[arg-type]
        acquire = getattr(worker_pool, "acquire", None)
        if not callable(acquire):
            raise TypeError("worker_pool must provide acquire(WorkerSpec)")
        return acquire(spec)

    asr_component_id = str(selection.asr["component_id"])
    asr_worker_overrides: dict[str, object] = {}
    portable_asr_python = os.environ.get("JP_H2_ASR_WORKER_PYTHON")
    if runtime_profile_id == "H2_PORTABLE_ONNX_FP32" and portable_asr_python:
        portable_asr_interpreter = Path(portable_asr_python).expanduser().resolve()
        if not portable_asr_interpreter.is_file():
            raise ValueError(
                "JP_H2_ASR_WORKER_PYTHON is not an existing interpreter: "
                f"{portable_asr_interpreter}"
            )
        asr_worker_overrides["command_override"] = (
            str(portable_asr_interpreter),
            "-u",
            "-m",
            "app.full_pipeline.worker_main",
            "--worker-id",
            f"{session_id}-asr",
            "--kind",
            "native_sherpa_asr",
            "--component",
            asr_component_id,
        )
    asr_worker = worker_for(
        asr_worker_spec(
            asr_component_id,
            worker_id=f"{session_id}-asr",
            pool_partition_id="asr",
            warmup_request={
                "session_id": f"{session_id}-model-warmup",
                "source_start_sec": 0.0,
            },
            **asr_worker_overrides,
        )
    )
    diar_backend = str(selection.diarization["embedding_backend_id"])
    identity_backend = str(selection.identity["backend_id"])
    share_redim_worker = (
        identity_backend == diar_backend
        and (
            tuning is None
            or tuning.redim_execution_strategy
            in {
                "R2_ONE_SHARED_MODEL",
                "R3_EXACT_WINDOW_EMBEDDING_REUSE",
                "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
            }
        )
    )
    diar_worker_partition, identity_worker_partition = (
        _speaker_embedding_worker_partitions(share_redim_worker)
    )
    diar_axis_identity = _embedding_axis(matrix, diar_backend)
    identity_axis = selection.identity
    segmentation_config = (
        RollingSegmentationConfig(
            hop_duration_sec=tuning.segmentation_hop_sec,
            onset=tuning.segmentation_onset,
            offset=tuning.segmentation_offset,
            minimum_speech_duration_sec=tuning.segmentation_min_speech_sec,
            minimum_silence_duration_sec=tuning.segmentation_min_silence_sec,
        )
        if tuning is not None
        else RollingSegmentationConfig()
    )
    portable_profile_config: object | None = None
    if runtime_profile_id == "H2_REFERENCE":
        if h2_onnx_graphs is not None or h2_onnx_expected_sha256 is not None:
            raise ValueError(
                "H2_REFERENCE must not receive ONNX graph overrides; select "
                "H2_PORTABLE_ONNX_FP32 explicitly"
            )
        segmentation_worker = worker_for(
            segmentation_worker_spec(
                worker_id=f"{session_id}-segmentation",
                pool_partition_id="segmentation",
                warmup_request={
                    "audio_path": str(warmup_audio),
                    "audio_sha256": warmup_sha256,
                    "recording_id": f"{session_id}-model-warmup",
                    "chunk_id": "segmentation-model-warmup",
                    "start_sec": 0.0,
                    "end_sec": 10.0,
                    "source_timestamp_offset_sec": 0.0,
                    "algorithmic_lookahead_sec": 5.0,
                },
            )
        )
        diar_worker = worker_for(
            embedding_worker_spec(
                diar_backend,
                worker_id=f"{session_id}-diar-{diar_backend}",
                pool_partition_id=diar_worker_partition,
                warmup_request=_embedding_warmup_request(
                    warmup_audio, warmup_sha256, session_id
                ),
            )
        )
        identity_worker = (
            diar_worker
            if share_redim_worker
            else worker_for(
                embedding_worker_spec(
                    identity_backend,
                    worker_id=f"{session_id}-identity-{identity_backend}",
                    pool_partition_id=identity_worker_partition,
                    warmup_request=_embedding_warmup_request(
                        warmup_audio, warmup_sha256, session_id
                    ),
                )
            )
        )
        segmenter = WorkerStreamingSegmenter(
            segmentation_worker,  # type: ignore[arg-type]
            work_root=work_root,
            cache=shared_cache,
            expected_model_asset_files=dict(
                matrix.matrix["shared_segmentation_asset"]["result_affecting_files"]
            ),
            lazy_worker_start=lazy_worker_start,
            config=segmentation_config,
        )
        diar_embedder = WorkerEmbeddingAdapter(
            worker=diar_worker,  # type: ignore[arg-type]
            work_root=work_root,
            backend_config_sha256=str(diar_axis_identity["config_sha256"]),
            model_id=str(diar_axis_identity["model_id"]),
            model_sha256=str(diar_axis_identity["model_identity_sha256"]),
            cache=shared_cache,
            lazy_worker_start=lazy_worker_start,
        )
        identity_embedder = (
            diar_embedder
            if identity_worker is diar_worker
            else WorkerEmbeddingAdapter(
                worker=identity_worker,  # type: ignore[arg-type]
                work_root=work_root,
                backend_config_sha256=str(identity_axis["config_sha256"]),
                model_id=str(identity_axis["model_id"]),
                model_sha256=str(identity_axis["model_identity_sha256"]),
                cache=shared_cache,
                lazy_worker_start=lazy_worker_start,
            )
        )
    elif runtime_profile_id == "H2_PORTABLE_ONNX_FP32":
        if selection.hybrid_label != "H2":
            raise ValueError("H2_PORTABLE_ONNX_FP32 is valid only for H2 pipelines")
        graphs = dict(h2_onnx_graphs or {})
        hashes = dict(h2_onnx_expected_sha256 or {})
        try:
            redim_graph = Path(graphs["redimnet2_b2_speaker_embedding"])
            segmentation_graph = Path(graphs["pyannote_segmentation_3_0"])
        except KeyError as exc:
            raise ValueError(
                "H2_PORTABLE_ONNX_FP32 requires both explicit graph paths"
            ) from exc
        from app.h2_portability.runtime_profile import (
            H2PortableRuntimeConfig,
            build_h2_portable_adapters,
        )

        portable_profile_config = H2PortableRuntimeConfig(
            redimnet2_path=redim_graph,
            segmentation_path=segmentation_graph,
            expected_sha256=hashes,
            redim_execution_strategy=(
                tuning.redim_execution_strategy
                if tuning is not None
                else "R2_ONE_SHARED_MODEL"
            ),
        )
        portable = build_h2_portable_adapters(
            config=portable_profile_config,
            session_id=session_id,
            work_root=work_root,
            warmup_audio_path=warmup_audio,
            warmup_audio_sha256=warmup_sha256,
            shared_cache=shared_cache,
            worker_for=worker_for,
            segmentation_config=segmentation_config,
            segmentation_asset_files=dict(
                matrix.matrix["shared_segmentation_asset"]["result_affecting_files"]
            ),
            embedding_backend_id=diar_backend,
            embedding_config_sha256=str(diar_axis_identity["config_sha256"]),
            embedding_model_id=str(diar_axis_identity["model_id"]),
            embedding_model_sha256=str(
                diar_axis_identity["model_identity_sha256"]
            ),
            lazy_worker_start=lazy_worker_start,
        )
        segmenter = portable.segmenter
        diar_embedder = portable.diarization_embedder
        identity_embedder = portable.identity_embedder
    else:
        raise ValueError(
            "runtime_profile must be H2_REFERENCE or H2_PORTABLE_ONNX_FP32"
        )
    decision_policy_contract: dict[str, object] | None = None
    if selection.hybrid_label in FROZEN_IDENTITY_POLICIES:
        policy = FROZEN_IDENTITY_POLICIES[selection.hybrid_label]
        if realized_gallery_size is not None:
            from app.full_pipeline_development.policies import (
                resolve_decision_policy_contract,
            )

            decision_policy_contract = resolve_decision_policy_contract(
                pipeline_id,
                realized_gallery_size=int(realized_gallery_size),
                gallery_requested_size=gallery_requested_size,
            )
    elif decision_policy_registry_path is not None:
        if realized_gallery_size is None:
            raise ValueError(
                "a challenger decision registry requires realized_gallery_size"
            )
        registry_path = Path(decision_policy_registry_path).resolve()
        if not registry_path.is_file():
            raise FileNotFoundError(registry_path)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        if not isinstance(registry, dict):
            raise ValueError(f"decision policy registry is not an object: {registry_path}")
        from app.full_pipeline_development.policies import (
            resolve_decision_policy_contract,
        )

        decision_policy_contract = resolve_decision_policy_contract(
            pipeline_id,
            realized_gallery_size=int(realized_gallery_size),
            gallery_requested_size=gallery_requested_size,
            registry=registry,
        )
        policy = challenger_policy(
            selection.hybrid_label,
            score_threshold=float(decision_policy_contract["score_threshold"]),
            margin_threshold=float(decision_policy_contract["margin_threshold"]),
            calibration_identity=(
                "development_policy:"
                + str(decision_policy_contract["decision_policy_sha256"])
            ),
            decision_policy_sha256=str(
                decision_policy_contract["decision_policy_sha256"]
            ),
            calibration_protocol_id=str(
                decision_policy_contract["calibration_protocol_id"]
            ),
            calibration_result_sha256=str(
                decision_policy_contract["calibration_result_sha256"]
            ),
            target_fpir=float(decision_policy_contract["target_fpir"]),
        )
    else:
        policy = challenger_policy(selection.hybrid_label)
    if tuning is not None:
        policy = tuning.apply_identity_policy(policy)
        decision_policy_contract = {
            **dict(decision_policy_contract or {}),
            "decision_policy_sha256": policy.decision_policy_sha256,
            "calibration_protocol_id": policy.calibration_protocol_id,
            "calibration_result_sha256": policy.calibration_result_sha256,
            "target_fpir": policy.target_fpir,
            "operating_mode": "H2_PRODUCT_DEVELOPMENT_TUNING",
            "threshold_scope": "explicit_h2_runtime_tuning",
            "runtime_tuning_sha256": tuning.identity_sha256,
        }
    identities = runtime_identities(
        selection,
        evaluation_root=EVALUATION_ROOT,
        decision_policy_sha256=policy.decision_policy_sha256,
    )
    if portable_profile_config is not None:
        from app.h2_portability.runtime_profile import (
            H2PortableRuntimeConfig,
            apply_portable_component_identities,
        )

        if not isinstance(portable_profile_config, H2PortableRuntimeConfig):
            raise TypeError("invalid H2 portable runtime profile configuration")
        identities = apply_portable_component_identities(
            identities,
            profile=portable_profile_config,
            pipeline_config_sha256=selection.pipeline_config_sha256,
        )
    if decision_policy_contract is None and policy.decision_policy_sha256 is not None:
        decision_policy_contract = {
            "decision_policy_sha256": policy.decision_policy_sha256,
            "calibration_protocol_id": policy.calibration_protocol_id,
            "calibration_result_sha256": policy.calibration_result_sha256,
            "target_fpir": policy.target_fpir,
        }
    monitor = RuntimeResourceMonitor(
        session_id=session_id,
        output_root=run_root,
        interval_sec=1.0,
    )
    asr_adapter: object = NativeASRWorkerAdapter(
        asr_worker,  # type: ignore[arg-type]
        work_root,
        expected_config_sha256=str(selection.asr["config_sha256"]),
    )
    if asr_stream_trace_enabled:
        if evaluation_measurement_mode != "accuracy":
            raise ValueError(
                "ASR stream trace replay is accuracy-only and is forbidden for "
                "resource measurement"
            )
        if asr_trace_source_path is None:
            raise ValueError("ASR stream traces require an immutable file source")
        from app.full_pipeline_development.shared_execution import (
            ASRStreamTraceAdapter,
            ASRStreamTraceStore,
            build_asr_stream_trace_identity,
        )

        trace_root = (
            Path(asr_stream_trace_root).resolve()
            if asr_stream_trace_root is not None
            else shared_cache.root / "asr_stream_traces"
        )
        asr_adapter = ASRStreamTraceAdapter(
            asr_adapter,
            store=ASRStreamTraceStore(trace_root),
            identity=build_asr_stream_trace_identity(
                source_audio_path=asr_trace_source_path,
                selection=selection,
                duration_sec=asr_trace_duration_sec,
            ),
            usage_mode=evaluation_measurement_mode,
        )

    return StreamingPipelineCoordinator(
        config=CoordinatorConfig(
            session_id=session_id,
            recording_id=recording_id,
            output_root=run_root,
            maximum_queue_frames=16,
            queue_policy=queue_policy,  # type: ignore[arg-type]
            telemetry_enabled=telemetry_enabled,
            maximum_audio_history_sec=max(
                30.0,
                tuning.retroactive_correction_sec + tuning.embedding_window_sec
                if tuning is not None
                else 30.0,
            ),
        ),
        selection=selection,
        source=source,
        normalizer=StreamingAudioNormalizer(
            cache=shared_cache if queue_policy == "block" else None
        ),
        asr=asr_adapter,  # type: ignore[arg-type]
        segmenter=segmenter,
        diarization_embedder=diar_embedder,
        cluster_manager=OnlineClusterManager(
            OnlineClusterConfig(
                minimum_embedding_duration_sec=float(
                    tuning.minimum_embedding_sec
                    if tuning is not None
                    else selection.diarization["minimum_embedding_window_sec"]
                ),
                threshold=(
                    tuning.clustering_threshold
                    if tuning is not None
                    else float(selection.diarization["clustering_threshold"])
                ),
                short_turn_attach_gap_sec=(
                    tuning.short_turn_attach_gap_sec if tuning is not None else 0.50
                ),
                maximum_clusters=(
                    tuning.maximum_session_speakers if tuning is not None else 128
                ),
                maximum_embeddings_per_cluster=(
                    tuning.maximum_cluster_embeddings if tuning is not None else 256
                ),
                policy_id=(
                    "full_pipeline_online_centroid_cosine_reconciliation.v2"
                    if tuning is not None
                    and tuning.memory_level == "M5_CLUSTER_RECONCILIATION"
                    else "full_pipeline_online_centroid_cosine.v1"
                ),
                reconciliation_enabled=bool(
                    tuning is not None
                    and tuning.memory_level == "M5_CLUSTER_RECONCILIATION"
                ),
                reconciliation_threshold=(
                    tuning.cluster_reconciliation_threshold
                    if tuning is not None
                    and tuning.memory_level == "M5_CLUSTER_RECONCILIATION"
                    else None
                ),
                reconciliation_max_gap_sec=(
                    tuning.cluster_reconciliation_max_gap_sec
                    if tuning is not None
                    else 120.0
                ),
                reconciliation_min_embeddings=(
                    tuning.cluster_reconciliation_min_embeddings
                    if tuning is not None
                    else 2
                ),
            )
        ),
        identity_embedder=identity_embedder,
        enrollment_store=ProtectedEnrollmentStore(
            Path(enrollment_root).resolve()
            if enrollment_root
            else DEFAULT_ENROLLMENT_ROOT
        ),
        identity_manager=SessionIdentityManager(
            policy,
            maximum_clusters=(
                tuning.maximum_session_speakers if tuning is not None else 128
            ),
            maximum_evidence_history_per_cluster=(
                tuning.maximum_identity_history_per_cluster
                if tuning is not None
                else 64
            ),
        ),
        transcript_aligner=TranscriptSpeakerAligner(
            transcript_id=f"transcript:{session_id}"
        ),
        identities=identities,
        decision_policy_contract=decision_policy_contract,
        resource_monitor=monitor,
        cache=shared_cache,
        runtime_tuning=tuning,
        emit_identity_score_diagnostics=emit_identity_score_diagnostics,
    )


def _embedding_axis(matrix: FullPipelineMatrix, backend_id: str) -> dict[str, object]:
    identities = matrix.matrix["axes"]["identity"]
    for row in identities.values():
        if row["backend_id"] == backend_id:
            return dict(row)
    raise KeyError(f"no locked identity axis for embedding backend {backend_id}")


def _ensure_warmup_audio(work_root: Path) -> Path:
    """Create deterministic local silence used only to initialize model kernels."""

    path = Path(work_root).resolve() / "warmup/mono16k_10s.wav"
    if path.is_file():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    with wave.open(str(temporary), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(b"\x00\x00" * 160_000)
    temporary.replace(path)
    return path


def _resolve_worker_warmup_audio(
    *, work_root: Path, worker_warmup_audio_path: Path | None
) -> Path:
    """Resolve an optional owner-stable warmup WAV for lazy pooled workers."""

    if worker_warmup_audio_path is None:
        return _ensure_warmup_audio(work_root)
    path = Path(worker_warmup_audio_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"worker warmup audio is missing: {path}")
    return path


def _embedding_warmup_request(
    audio_path: Path, audio_sha256: str, session_id: str
) -> dict[str, object]:
    return {
        "audio_path": str(audio_path),
        "audio_sha256": audio_sha256,
        "recording_id": f"{session_id}-model-warmup",
        "window_id": "embedding-model-warmup",
        "role": "model_warmup",
        "start_sec": 0.0,
        "end_sec": 2.0,
        "segment_index": 0,
        "device": "cpu",
    }
