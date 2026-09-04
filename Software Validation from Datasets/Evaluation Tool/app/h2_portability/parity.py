"""Deterministic native-PyTorch versus ONNX Runtime parity measurements.

The built-in panel is an engineering smoke, not an accuracy dataset. Callers
may additionally provide local audio paths; the exact post-resample samples are
hashed before either runtime sees them. No tolerance is accepted from the CLI.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from app.inference_pipeline.diarization.clustering import (
    agglomerative_cosine_labels,
)
from app.utils.paths import repository_root

from .contracts import (
    E2E_PARITY_HOOK_VERSION,
    H2_DECISION_DIAGNOSTIC,
    ONNX_PARITY_CONTRACT_VERSION,
    ONNX_TOOLING_SCHEMA,
    PARITY_TOLERANCES,
    PYANNOTE_FIXED_SAMPLES,
    SAMPLE_RATE_HZ,
)
from .onnx_tooling import (
    COMPONENTS,
    atomic_write_json,
    canonical_sha256,
    environment_manifest,
    load_native_model,
    sha256_file,
)


POWERSET_TO_MULTILABEL = np.asarray(
    [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
        [1.0, 1.0, 0.0],
        [1.0, 0.0, 1.0],
        [0.0, 1.0, 1.0],
    ],
    dtype=np.float32,
)


class ParityError(RuntimeError):
    """A graph or case violates the frozen parity contract."""


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    header = f"{array.dtype.str}|{array.shape}".encode("ascii")
    return hashlib.sha256(header + array.tobytes()).hexdigest()


def _signal(case_id: str, samples: int, seed: int) -> np.ndarray:
    """Create one deterministic, bounded, non-dataset engineering signal."""

    time_axis = np.arange(samples, dtype=np.float64) / SAMPLE_RATE_HZ
    generator = np.random.default_rng(seed)
    if "noise" in case_id:
        value = generator.normal(0.0, 0.025, samples)
        value = np.convolve(value, np.asarray([0.2, 0.6, 0.2]), mode="same")
    elif "bursts" in case_id:
        carrier = 0.025 * np.sin(2.0 * np.pi * 173.0 * time_axis)
        carrier += 0.012 * np.sin(2.0 * np.pi * 337.0 * time_axis + 0.4)
        gate = (
            ((time_axis >= 0.6) & (time_axis < 2.8))
            | ((time_axis >= 4.1) & (time_axis < 6.2))
            | ((time_axis >= 7.0) & (time_axis < 9.4))
        )
        value = carrier * gate
        value += generator.normal(0.0, 0.001, samples)
    elif "overlap" in case_id:
        first = 0.025 * np.sin(2.0 * np.pi * 211.0 * time_axis)
        second = 0.020 * np.sin(2.0 * np.pi * 421.0 * time_axis + 0.7)
        gate_first = (time_axis >= 0.4) & (time_axis < 7.2)
        gate_second = (time_axis >= 3.0) & (time_axis < 9.5)
        value = first * gate_first + second * gate_second
        value += generator.normal(0.0, 0.001, samples)
    else:
        value = 0.028 * np.sin(2.0 * np.pi * 197.0 * time_axis)
        value += 0.014 * np.sin(2.0 * np.pi * 389.0 * time_axis + 0.3)
        value += generator.normal(0.0, 0.002, samples)
    return np.ascontiguousarray(np.clip(value, -1.0, 1.0), dtype=np.float32)


def _built_in_cases(component_id: str) -> list[dict[str, object]]:
    if component_id == "redimnet2_b2_speaker_embedding":
        definitions = (
            ("tone_0p5s", 8_000, 10_101),
            ("noise_1s", 16_000, 10_102),
            ("tone_2s", 32_000, 10_103),
            ("noise_5s", 80_000, 10_104),
            ("tone_10s", 160_000, 10_105),
        )
    elif component_id == "pyannote_segmentation_3_0":
        definitions = (
            ("segmentation_bursts_10s", PYANNOTE_FIXED_SAMPLES, 20_101),
            ("segmentation_noise_10s", PYANNOTE_FIXED_SAMPLES, 20_102),
            ("segmentation_overlap_10s", PYANNOTE_FIXED_SAMPLES, 20_103),
        )
    else:
        raise ValueError(component_id)
    rows = []
    for case_id, samples, seed in definitions:
        waveform = _signal(case_id, samples, seed)
        rows.append(
            {
                "case_id": case_id,
                "source": "deterministic_engineering_generator.v1",
                "seed": seed,
                "sample_rate_hz": SAMPLE_RATE_HZ,
                "sample_count": samples,
                "duration_sec": samples / SAMPLE_RATE_HZ,
                "input_sha256": _array_sha256(waveform),
                "waveform": waveform,
            }
        )
    return rows


def _load_audio_case(
    path: Path, *, component_id: str, index: int
) -> dict[str, object]:
    import soundfile as sf
    from scipy.signal import resample_poly

    source = path.expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    samples, source_rate = sf.read(source, dtype="float32", always_2d=True)
    waveform = np.mean(samples, axis=1, dtype=np.float32)
    if int(source_rate) != SAMPLE_RATE_HZ:
        divisor = math.gcd(int(source_rate), SAMPLE_RATE_HZ)
        waveform = resample_poly(
            waveform,
            SAMPLE_RATE_HZ // divisor,
            int(source_rate) // divisor,
        ).astype(np.float32)
    preprocessing: list[str] = ["mean_channels", "resample_poly_if_needed"]
    if component_id == "pyannote_segmentation_3_0":
        if waveform.size < PYANNOTE_FIXED_SAMPLES:
            waveform = np.pad(
                waveform, (0, PYANNOTE_FIXED_SAMPLES - waveform.size)
            )
            preprocessing.append("right_zero_pad_to_10s")
        elif waveform.size > PYANNOTE_FIXED_SAMPLES:
            waveform = waveform[:PYANNOTE_FIXED_SAMPLES]
            preprocessing.append("first_10s_only")
    elif waveform.size < 8_000:
        raise ParityError(f"ReDimNet2 parity audio is shorter than 0.5 s: {source}")
    waveform = np.ascontiguousarray(np.clip(waveform, -1.0, 1.0), dtype=np.float32)
    return {
        "case_id": f"local_audio_{index:03d}_{source.stem}",
        "source": "local_audio",
        "source_path": str(source),
        "source_file_sha256": sha256_file(source),
        "source_sample_rate_hz": int(source_rate),
        "preprocessing": preprocessing,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "sample_count": int(waveform.size),
        "duration_sec": waveform.size / SAMPLE_RATE_HZ,
        "input_sha256": _array_sha256(waveform),
        "waveform": waveform,
    }


def build_case_panel(
    component_id: str, *, audio_paths: Sequence[Path] = ()
) -> tuple[list[dict[str, object]], dict[str, object]]:
    cases = _built_in_cases(component_id)
    cases.extend(
        _load_audio_case(path, component_id=component_id, index=index)
        for index, path in enumerate(audio_paths, 1)
    )
    public_rows = [
        {name: value for name, value in row.items() if name != "waveform"}
        for row in cases
    ]
    manifest = {
        "schema_version": "h2-onnx-parity-case-manifest.v1",
        "component_id": component_id,
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "case_count": len(public_rows),
        "cases": public_rows,
        "accuracy_dataset": False,
        "purpose": "bounded numerical and decision-contract parity only",
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    return cases, manifest


def _absolute_relative(native: np.ndarray, onnx: np.ndarray) -> dict[str, float]:
    if native.shape != onnx.shape:
        raise ParityError(f"output shape mismatch: native={native.shape}, onnx={onnx.shape}")
    difference = np.abs(native.astype(np.float64) - onnx.astype(np.float64))
    denominator = np.maximum(np.abs(native.astype(np.float64)), 1.0e-8)
    relative = difference / denominator
    return {
        "maximum_absolute": float(np.max(difference)),
        "mean_absolute": float(np.mean(difference)),
        "maximum_relative": float(np.max(relative)),
        "mean_relative": float(np.mean(relative)),
    }


def _l2_normalize(value: np.ndarray) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    norm = np.linalg.norm(matrix, axis=-1, keepdims=True)
    if np.any(~np.isfinite(norm)) or np.any(norm <= 0.0):
        raise ParityError("embedding output is zero or non-finite")
    return matrix / norm


def _coassignment(labels: Sequence[int]) -> np.ndarray:
    values = np.asarray(labels, dtype=np.int64)
    return values[:, None] == values[None, :]


def _redim_decisions(embeddings: np.ndarray) -> list[dict[str, object]]:
    if len(embeddings) < 3:
        return []
    enrollment = embeddings[:2]
    rows = []
    for index, probe in enumerate(embeddings[2:], 2):
        scores = enrollment @ probe
        order = np.argsort(-scores, kind="stable")
        top1 = int(order[0])
        top2 = int(order[1])
        margin = float(scores[top1] - scores[top2])
        accepted = bool(
            scores[top1] >= H2_DECISION_DIAGNOSTIC["identity_score_threshold"]
            and margin >= H2_DECISION_DIAGNOSTIC["top1_top2_margin"]
        )
        rows.append(
            {
                "probe_case_index": index,
                "top1_index": top1,
                "top1_score": float(scores[top1]),
                "top2_score": float(scores[top2]),
                "margin": margin,
                "accepted": accepted,
                "label": f"known_{top1}" if accepted else "Unknown",
            }
        )
    return rows


def _run_redim_parity(
    model: Any, session: Any, cases: Sequence[dict[str, object]]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    import torch

    native_embeddings: list[np.ndarray] = []
    onnx_embeddings: list[np.ndarray] = []
    rows: list[dict[str, object]] = []
    for row in cases:
        waveform = np.asarray(row["waveform"], dtype=np.float32)[None, :]
        started = time.perf_counter()
        with torch.inference_mode():
            native_raw = model(torch.from_numpy(waveform)).detach().cpu().numpy()
        native_sec = time.perf_counter() - started
        started = time.perf_counter()
        onnx_raw = session.run(None, {"waveform": waveform})[0]
        onnx_sec = time.perf_counter() - started
        native = _l2_normalize(native_raw)[0]
        onnx = _l2_normalize(onnx_raw)[0]
        absolute = _absolute_relative(native, onnx)
        cosine = float(np.clip(native @ onnx, -1.0, 1.0))
        native_embeddings.append(native)
        onnx_embeddings.append(onnx)
        rows.append(
            {
                "case_id": row["case_id"],
                "sample_count": row["sample_count"],
                "input_sha256": row["input_sha256"],
                "native_output_sha256": _array_sha256(native_raw),
                "onnx_output_sha256": _array_sha256(onnx_raw),
                "raw_error": _absolute_relative(native_raw, onnx_raw),
                "normalized_error": absolute,
                "cosine_similarity": cosine,
                "cosine_distance": 1.0 - cosine,
                "native_wall_sec": native_sec,
                "onnx_wall_sec": onnx_sec,
            }
        )

    native_matrix = np.stack(native_embeddings)
    onnx_matrix = np.stack(onnx_embeddings)
    native_scores = native_matrix @ native_matrix.T
    onnx_scores = onnx_matrix @ onnx_matrix.T
    native_labels = agglomerative_cosine_labels(
        native_matrix.tolist(),
        threshold=float(H2_DECISION_DIAGNOSTIC["clustering_cosine_threshold"]),
    )
    onnx_labels = agglomerative_cosine_labels(
        onnx_matrix.tolist(),
        threshold=float(H2_DECISION_DIAGNOSTIC["clustering_cosine_threshold"]),
    )
    native_decisions = _redim_decisions(native_matrix)
    onnx_decisions = _redim_decisions(onnx_matrix)
    decision_keys = ("top1_index", "accepted", "label")
    decisions_match = all(
        all(native[name] == onnx[name] for name in decision_keys)
        for native, onnx in zip(native_decisions, onnx_decisions, strict=True)
    )
    summary = {
        "case_count": len(rows),
        "normalized_embedding_max_abs": max(
            float(row["normalized_error"]["maximum_absolute"]) for row in rows
        ),
        "normalized_embedding_mean_abs": float(
            np.mean([row["normalized_error"]["mean_absolute"] for row in rows])
        ),
        "cosine_distance_max": max(float(row["cosine_distance"]) for row in rows),
        "pair_score_max_abs": float(np.max(np.abs(native_scores - onnx_scores))),
        "identity_decisions_match": decisions_match,
        "native_identity_decisions": native_decisions,
        "onnx_identity_decisions": onnx_decisions,
        "native_cluster_labels": native_labels,
        "onnx_cluster_labels": onnx_labels,
        "clustering_coassignment_match": bool(
            np.array_equal(_coassignment(native_labels), _coassignment(onnx_labels))
        ),
    }
    tolerance = PARITY_TOLERANCES["redimnet2_b2_speaker_embedding"]
    gates = {
        "normalized_embedding_max_abs": summary["normalized_embedding_max_abs"]
        <= tolerance["normalized_embedding_max_abs"],
        "normalized_embedding_mean_abs": summary["normalized_embedding_mean_abs"]
        <= tolerance["normalized_embedding_mean_abs"],
        "cosine_distance_max": summary["cosine_distance_max"]
        <= tolerance["cosine_distance_max"],
        "pair_score_max_abs": summary["pair_score_max_abs"]
        <= tolerance["pair_score_max_abs"],
        "identity_decisions_match": decisions_match,
        "clustering_coassignment_match": summary["clustering_coassignment_match"],
    }
    summary["gates"] = gates
    summary["passed"] = all(gates.values())
    return rows, summary


def _powerset_views(raw: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    class_ids = np.argmax(raw, axis=-1)
    multilabel = POWERSET_TO_MULTILABEL[class_ids]
    ordered = np.sort(multilabel, axis=-1)
    speech = ordered[..., -1].astype(np.int8)
    overlap = ordered[..., -2].astype(np.int8)
    return class_ids, speech, overlap


def _regions(activity: np.ndarray) -> list[tuple[int, int]]:
    values = np.asarray(activity, dtype=np.int8).reshape(-1)
    padded = np.pad(values, (1, 1))
    difference = np.diff(padded)
    starts = np.flatnonzero(difference == 1)
    ends = np.flatnonzero(difference == -1)
    return [(int(start), int(end)) for start, end in zip(starts, ends, strict=True)]


def _boundary_diagnostics(
    native: np.ndarray, onnx: np.ndarray, *, frame_step_sec: float
) -> dict[str, object]:
    native_regions = _regions(native)
    onnx_regions = _regions(onnx)
    native_boundaries = [item for region in native_regions for item in region]
    onnx_boundaries = [item for region in onnx_regions for item in region]
    if len(native_boundaries) == len(onnx_boundaries):
        deltas = [
            abs(native_value - onnx_value)
            for native_value, onnx_value in zip(
                native_boundaries, onnx_boundaries, strict=True
            )
        ]
        maximum = max(deltas, default=0)
    else:
        deltas = []
        maximum = None
    return {
        "native_regions_frames": native_regions,
        "onnx_regions_frames": onnx_regions,
        "native_boundary_count": len(native_boundaries),
        "onnx_boundary_count": len(onnx_boundaries),
        "boundary_frame_deltas": deltas,
        "maximum_boundary_frame_delta": maximum,
        "maximum_boundary_sec_delta": (
            maximum * frame_step_sec if maximum is not None else None
        ),
        "regions_match": native_regions == onnx_regions,
    }


def _run_pyannote_parity(
    model: Any, session: Any, cases: Sequence[dict[str, object]]
) -> tuple[list[dict[str, object]], dict[str, object]]:
    import torch

    receptive = model.receptive_field
    frame_step_sec = float(receptive.step)
    frame_duration_sec = float(receptive.duration)
    rows: list[dict[str, object]] = []
    for row in cases:
        waveform = np.asarray(row["waveform"], dtype=np.float32)[None, None, :]
        if waveform.shape[-1] != PYANNOTE_FIXED_SAMPLES:
            raise ParityError("Pyannote graph requires exactly 160000 samples")
        started = time.perf_counter()
        with torch.inference_mode():
            native = model(torch.from_numpy(waveform)).detach().cpu().numpy()
        native_sec = time.perf_counter() - started
        started = time.perf_counter()
        onnx = session.run(None, {"waveform": waveform})[0]
        onnx_sec = time.perf_counter() - started
        native_ids, native_speech, native_overlap = _powerset_views(native)
        onnx_ids, onnx_speech, onnx_overlap = _powerset_views(onnx)
        speech_boundaries = _boundary_diagnostics(
            native_speech, onnx_speech, frame_step_sec=frame_step_sec
        )
        overlap_boundaries = _boundary_diagnostics(
            native_overlap, onnx_overlap, frame_step_sec=frame_step_sec
        )
        rows.append(
            {
                "case_id": row["case_id"],
                "input_sha256": row["input_sha256"],
                "native_output_sha256": _array_sha256(native),
                "onnx_output_sha256": _array_sha256(onnx),
                "raw_error": _absolute_relative(native, onnx),
                "powerset_frame_agreement": float(np.mean(native_ids == onnx_ids)),
                "speech_activity_agreement": float(
                    np.mean(native_speech == onnx_speech)
                ),
                "overlap_activity_agreement": float(
                    np.mean(native_overlap == onnx_overlap)
                ),
                "speech_boundary_diagnostics": speech_boundaries,
                "overlap_boundary_diagnostics": overlap_boundaries,
                "downstream_regions_match": bool(
                    speech_boundaries["regions_match"]
                    and overlap_boundaries["regions_match"]
                ),
                "native_wall_sec": native_sec,
                "onnx_wall_sec": onnx_sec,
            }
        )

    boundary_values = [
        diagnostic["maximum_boundary_frame_delta"]
        for row in rows
        for diagnostic in (
            row["speech_boundary_diagnostics"],
            row["overlap_boundary_diagnostics"],
        )
    ]
    finite_boundaries = all(value is not None for value in boundary_values)
    boundary_max = max((int(value) for value in boundary_values if value is not None), default=0)
    summary = {
        "case_count": len(rows),
        "frame_step_sec": frame_step_sec,
        "frame_duration_sec": frame_duration_sec,
        "raw_output_max_abs": max(
            float(row["raw_error"]["maximum_absolute"]) for row in rows
        ),
        "raw_output_mean_abs": float(
            np.mean([row["raw_error"]["mean_absolute"] for row in rows])
        ),
        "powerset_frame_agreement_min": min(
            float(row["powerset_frame_agreement"]) for row in rows
        ),
        "speech_activity_agreement_min": min(
            float(row["speech_activity_agreement"]) for row in rows
        ),
        "overlap_activity_agreement_min": min(
            float(row["overlap_activity_agreement"]) for row in rows
        ),
        "maximum_boundary_frame_delta": boundary_max if finite_boundaries else None,
        "all_downstream_regions_match": all(
            bool(row["downstream_regions_match"]) for row in rows
        ),
    }
    tolerance = PARITY_TOLERANCES["pyannote_segmentation_3_0"]
    gates = {
        "raw_output_max_abs": summary["raw_output_max_abs"]
        <= tolerance["raw_output_max_abs"],
        "raw_output_mean_abs": summary["raw_output_mean_abs"]
        <= tolerance["raw_output_mean_abs"],
        "powerset_frame_agreement": summary["powerset_frame_agreement_min"]
        >= tolerance["powerset_frame_agreement_min"],
        "speech_activity_agreement": summary["speech_activity_agreement_min"]
        >= tolerance["speech_activity_agreement_min"],
        "overlap_activity_agreement": summary["overlap_activity_agreement_min"]
        >= tolerance["overlap_activity_agreement_min"],
        "boundary_frame_delta": finite_boundaries
        and boundary_max <= tolerance["maximum_boundary_frame_delta"],
        "downstream_regions_match": summary["all_downstream_regions_match"],
    }
    summary["gates"] = gates
    summary["passed"] = all(gates.values())
    return rows, summary


def run_component_parity(
    component_id: str,
    *,
    onnx_path: Path,
    output_dir: Path,
    repository: Path | None = None,
    audio_paths: Sequence[Path] = (),
) -> dict[str, object]:
    """Measure one component against the frozen tolerance contract."""

    import onnxruntime as ort
    import torch

    if component_id not in COMPONENTS:
        raise ValueError(component_id)
    graph = Path(onnx_path).resolve()
    if not graph.is_file():
        raise FileNotFoundError(graph)
    repo = Path(repository) if repository is not None else repository_root().path
    cases, case_manifest = build_case_panel(component_id, audio_paths=audio_paths)
    output = Path(output_dir).resolve(strict=False)
    output.mkdir(parents=True, exist_ok=True)
    case_manifest_path = output / f"{component_id}.case_manifest.json"
    atomic_write_json(case_manifest_path, case_manifest)

    torch.set_num_threads(1)
    torch.manual_seed(3_805_2026)
    model = load_native_model(component_id, repository=repo)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(
        str(graph), sess_options=options, providers=["CPUExecutionProvider"]
    )

    expected_input = COMPONENTS[component_id].input_name
    if len(session.get_inputs()) != 1 or session.get_inputs()[0].name != expected_input:
        raise ParityError("ONNX input contract mismatch")
    if component_id == "redimnet2_b2_speaker_embedding":
        case_rows, summary = _run_redim_parity(model, session, cases)
    else:
        case_rows, summary = _run_pyannote_parity(model, session, cases)

    tolerance = PARITY_TOLERANCES[component_id]
    environment = environment_manifest(
        profile=COMPONENTS[component_id].native_environment_profile
    )
    report = {
        "schema_version": ONNX_TOOLING_SCHEMA,
        "parity_contract_version": ONNX_PARITY_CONTRACT_VERSION,
        "status": "PARITY_PASS" if summary["passed"] else "PARITY_FAIL",
        "component_id": component_id,
        "onnx_path": str(graph),
        "onnx_sha256": sha256_file(graph),
        "onnx_bytes": graph.stat().st_size,
        "case_manifest_path": str(case_manifest_path),
        "case_manifest_sha256": case_manifest["manifest_sha256"],
        "tolerances": tolerance,
        "tolerance_contract_sha256": canonical_sha256(tolerance),
        "case_results": case_rows,
        "summary": summary,
        "runtime": {
            "native": "torch",
            "onnx": "onnxruntime",
            "onnxruntime_version": ort.__version__,
            "onnxruntime_providers": session.get_providers(),
            "threads": 1,
            "execution_mode": "ORT_SEQUENTIAL",
        },
        "environment": environment,
        "environment_sha256": canonical_sha256(environment),
        "parity_measured": True,
        "parity_passed": bool(summary["passed"]),
        "accuracy_evaluation_performed": False,
        "thresholds_retuned": False,
        "linux_arm64_measured": False,
        "production_usable": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    report_path = output / f"{component_id}.parity.json"
    atomic_write_json(report_path, report)
    return {**report, "report_path": str(report_path)}


def build_e2e_parity_hook(
    reports: Sequence[Mapping[str, object]], *, output_path: Path | None = None
) -> dict[str, object]:
    """Bind both component reports into a controller-consumable H2 gate."""

    by_component = {str(report.get("component_id")): report for report in reports}
    required = set(COMPONENTS)
    missing = sorted(required - set(by_component))
    component_rows = {}
    all_pass = not missing
    for component_id in sorted(required):
        report = by_component.get(component_id)
        if report is None:
            continue
        passed = bool(report.get("parity_passed")) and report.get("status") == "PARITY_PASS"
        all_pass = all_pass and passed
        component_rows[component_id] = {
            "status": report.get("status"),
            "parity_passed": passed,
            "onnx_sha256": report.get("onnx_sha256"),
            "case_manifest_sha256": report.get("case_manifest_sha256"),
            "tolerance_contract_sha256": report.get("tolerance_contract_sha256"),
            "report_sha256": canonical_sha256(report),
        }
    value = {
        "schema_version": E2E_PARITY_HOOK_VERSION,
        "status": "E2E_CONTRACT_PARITY_PASS" if all_pass else "E2E_CONTRACT_PARITY_BLOCKED",
        "required_components": sorted(required),
        "missing_components": missing,
        "components": component_rows,
        "component_parity_passed": all_pass,
        "full_live_pipeline_parity_measured": False,
        "h2_controller_may_schedule_onnx_e2e_smoke": all_pass,
        "h2_controller_may_claim_arm64_ready": False,
        "scientific_policy_changed": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    value["contract_binding_sha256"] = canonical_sha256(value)
    if output_path is not None:
        atomic_write_json(output_path, value)
        value["output_path"] = str(Path(output_path).resolve())
    return value


def load_reports(paths: Iterable[Path]) -> list[dict[str, object]]:
    rows = []
    for path in paths:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ParityError(f"parity report must be an object: {path}")
        rows.append(value)
    return rows


__all__ = [
    "ParityError",
    "build_case_panel",
    "build_e2e_parity_hook",
    "load_reports",
    "run_component_parity",
]
