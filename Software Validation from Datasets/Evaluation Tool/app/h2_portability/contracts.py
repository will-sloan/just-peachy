"""Frozen contracts for H2 ONNX export, parity, and ARM64 preparation.

The tolerance values in this module are deliberately code constants. A parity
run records a hash of this contract so results cannot be reclassified by
quietly changing a command-line threshold after measurement.
"""

from __future__ import annotations

H2_PORTABILITY_PROTOCOL = "h2-portability.v2"
H2_PORTABILITY_CODE_IDENTITY = "h2-portability-code-identity.v2"
WORKER_INTERPRETER_RESOLUTION_SCHEMA = "h2-worker-interpreter-resolution.v1"
SPATIAL_EVIDENCE_INTERFACE_VERSION = "spatial-evidence-interface.v2"
XVF_NO_EFFECT_PLACEHOLDER_ID = "xvf3800-spatial-evidence.no-effect.v2"
ONNX_TOOLING_SCHEMA = "h2-onnx-export-parity-status.v2"
ONNX_TOOLING_ID = "h2-onnx-export-parity-tooling.v2"
ONNX_EXPORT_CONTRACT_VERSION = "h2-onnx-fp32-export.v1"
ONNX_PARITY_CONTRACT_VERSION = "h2-onnx-numerical-parity.v1"
E2E_PARITY_HOOK_VERSION = "h2-onnx-e2e-contract-hook.v1"
H2_E2E_ONNX_PARITY_CONTRACT_VERSION = "h2-e2e-onnx-parity.v1"
ARM64_PACKAGE_CONTRACT_VERSION = "h2-linux-arm64-package.v1"

H2_PIPELINE_IDS = (
    "fullpipe_v1_ao_dr_ir",
    "fullpipe_v1_ag_dr_ir",
)

SUPPORTED_ENVIRONMENT_PROFILES = (
    "core-cpu",
    "onnx",
    "wespeaker",
    "credential-diarization",
    "redimnet2",
    "extended-local",
    "core-cuda",
)

FP32_ONLY = "FP32"
ONNX_OPSET = 18
SAMPLE_RATE_HZ = 16_000
REDIMNET2_EMBEDDING_DIM = 192
PYANNOTE_FIXED_SAMPLES = 160_000

EXPORTER_DYNAMO = "torch_onnx_dynamo_v2"
EXPORTER_LEGACY = "torch_onnx_legacy_v1"
SUPPORTED_EXPORTERS = (EXPORTER_DYNAMO, EXPORTER_LEGACY)

# These values predate the bounded parity run. Raw/relative diagnostics are
# reported even when scientific gates use cosine, label, and boundary parity.
PARITY_TOLERANCES: dict[str, dict[str, float | int | bool]] = {
    "redimnet2_b2_speaker_embedding": {
        "normalized_embedding_max_abs": 5.0e-4,
        "normalized_embedding_mean_abs": 5.0e-5,
        "cosine_distance_max": 1.0e-5,
        "pair_score_max_abs": 2.0e-4,
        "identity_decisions_must_match": True,
        "clustering_coassignment_must_match": True,
    },
    "pyannote_segmentation_3_0": {
        "raw_output_max_abs": 5.0e-4,
        "raw_output_mean_abs": 5.0e-5,
        "powerset_frame_agreement_min": 1.0,
        "speech_activity_agreement_min": 1.0,
        "overlap_activity_agreement_min": 1.0,
        "maximum_boundary_frame_delta": 0,
        "downstream_regions_must_match": True,
    },
}

# Frozen before inspecting native-vs-ONNX full-pipeline artifacts. Only
# non-semantic run identifiers, filesystem paths, wall/monotonic clocks,
# compute/resource telemetry, and component provenance are normalized away.
# Source-media timestamps remain result-affecting and receive only a numerical
# serialization tolerance, not a segmentation allowance.
H2_E2E_ONNX_PARITY_TOLERANCES: dict[str, object] = {
    "source_timestamp_max_abs_sec": 1.0e-9,
    "speech_boundary_max_abs_sec": 1.0e-9,
    "transcript_span_boundary_max_abs_sec": 1.0e-9,
    # Identity scores are derived from the normalized FP32 speaker embeddings.
    # These limits were frozen before running or reading an enrolled-speaker
    # native-vs-ONNX full-pipeline case.
    "identity_score_max_abs": 2.0e-4,
    "identity_margin_max_abs": 4.0e-4,
    "identity_consistency_max_abs": 2.0e-4,
    "segmentation_raw_score_max_abs": 5.0e-4,
    "speaker_boundary_raw_score_max_abs": 5.0e-4,
    "event_type_sequence_exact": True,
    "event_semantic_payload_exact": True,
    "transcript_text_and_words_exact": True,
    "rttm_speaker_time_exact_after_cluster_permutation": True,
    "cluster_coassignment_exact": True,
    "identity_state_and_label_exact": True,
    "normalization_allowlist": [
        "session/run/event identifiers derived only from session UUID",
        "filesystem and artifact paths",
        "UTC and monotonic wall-clock timestamps",
        "compute latency, queue wait, process/resource telemetry",
        "backend implementation provenance expected to differ by profile",
    ],
    "normalization_forbidden": [
        "source-media timestamps",
        "recognized words or transcript text",
        "speech/turn boundaries",
        "cluster coassignment structure",
        "identity state or public label",
        "event order or contract type",
    ],
}

# Frozen H2 diagnostics only; parity never calibrates or retunes them.
H2_DECISION_DIAGNOSTIC = {
    "identity_score_threshold": 0.5265351286789879,
    "top1_top2_margin": 0.03,
    "clustering_cosine_threshold": 0.50,
}

PINNED_ONNX_TOOLCHAIN = {
    "torch": "2.11.0",
    "onnx": "1.22.0",
    "onnxruntime": "1.29.0",
    "onnxscript": "0.7.1",
}
