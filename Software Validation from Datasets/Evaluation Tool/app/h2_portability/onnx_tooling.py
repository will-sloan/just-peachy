"""Real, fail-closed FP32 ONNX export tooling for the two H2 components.

No model is downloaded here. Only checksum-pinned repository assets are
loaded. An explicitly selected exporter creates a graph, the graph is checked
and annotated, and a provenance manifest is written beside it. Numerical
parity lives in :mod:`app.h2_portability.parity`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
from importlib import metadata as importlib_metadata
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
from typing import Any, Mapping

from app.utils.paths import repository_root

from .contracts import (
    EXPORTER_DYNAMO,
    EXPORTER_LEGACY,
    FP32_ONLY,
    ONNX_EXPORT_CONTRACT_VERSION,
    ONNX_OPSET,
    ONNX_TOOLING_ID,
    ONNX_TOOLING_SCHEMA,
    PARITY_TOLERANCES,
    PINNED_ONNX_TOOLCHAIN,
    PYANNOTE_FIXED_SAMPLES,
    SAMPLE_RATE_HZ,
    SUPPORTED_EXPORTERS,
)


class OnnxExportError(RuntimeError):
    """The requested explicit export path could not make a valid graph."""


@dataclass(frozen=True)
class RequiredAsset:
    relative_path: str
    sha256: str


@dataclass(frozen=True)
class ComponentExportContract:
    component_id: str
    native_backend: str
    native_environment_profile: str
    required_assets: tuple[RequiredAsset, ...]
    input_name: str
    output_name: str
    input_contract: str
    output_contract: str
    example_samples: int
    dynamic_time: bool
    postprocessing: str


COMPONENTS: Mapping[str, ComponentExportContract] = {
    "redimnet2_b2_speaker_embedding": ComponentExportContract(
        component_id="redimnet2_b2_speaker_embedding",
        native_backend="official PalabraAI ReDimNet2-B2 native PyTorch",
        native_environment_profile="redimnet2",
        required_assets=(
            RequiredAsset(
                "models/cache/redimnet2/b2-vox2-lm.pt",
                "0545a29679a87fe1c662d2bbd05e3b3fe0d1b392832729abaa135e4079a2f77a",
            ),
            RequiredAsset(
                "models/cache/redimnet2/source-cdc875670034dd7068013ca2ab21ec083a040ff8/hubconf.py",
                "325d5dfa4db8377ca76d71ecf4b652a2ebf54e77179c7ce50f77759b32de6ddd",
            ),
            RequiredAsset(
                "models/cache/redimnet2/source-cdc875670034dd7068013ca2ab21ec083a040ff8/redimnet2/redimnet2.py",
                "3b6bb2b9e8a5766d1286ea18b76f94cfacdd6e895cf4b996efbaf5c5f146dc5b",
            ),
        ),
        input_name="waveform",
        output_name="embedding_raw",
        input_contract="float32 mono waveform [batch=1, samples] at 16 kHz",
        output_contract="float32 raw embedding [batch=1, 192]",
        example_samples=32_000,
        dynamic_time=True,
        postprocessing="L2 normalize on axis 1 before cosine scoring",
    ),
    "pyannote_segmentation_3_0": ComponentExportContract(
        component_id="pyannote_segmentation_3_0",
        native_backend="pyannote.audio 4.0.7 Segmentation 3.0 native PyTorch",
        native_environment_profile="credential-diarization",
        required_assets=(
            RequiredAsset(
                "models/cache/pyannote/segmentation-3.0/config.yaml",
                "fa65a47a751602f04cc570135007d76859b69e8f9f1bfdf5878a5145980d4263",
            ),
            RequiredAsset(
                "models/cache/pyannote/segmentation-3.0/pytorch_model.bin",
                "da85c29829d4002daedd676e012936488234d9255e65e86dfab9bec6b1729298",
            ),
        ),
        input_name="waveform",
        output_name="powerset_log_scores",
        input_contract="float32 mono waveform [batch=1, channel=1, samples=160000] at 16 kHz",
        output_contract="float32 log scores [batch=1, frames=589, powerset_classes=7]",
        example_samples=PYANNOTE_FIXED_SAMPLES,
        dynamic_time=False,
        postprocessing=(
            "hard argmax powerset-to-three-speaker mapping, then max/second-max "
            "speech-overlap channels and frozen hysteresis binarization"
        ),
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _asset_check(repository: Path, asset: RequiredAsset) -> dict[str, object]:
    path = repository / asset.relative_path
    if not path.is_file():
        return {
            "path": asset.relative_path,
            "expected_sha256": asset.sha256,
            "observed_sha256": None,
            "status": "MISSING",
        }
    observed = sha256_file(path)
    return {
        "path": asset.relative_path,
        "expected_sha256": asset.sha256,
        "observed_sha256": observed,
        "status": "MATCH" if observed == asset.sha256 else "HASH_MISMATCH",
    }


def _distribution_version(name: str) -> str | None:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return None


def environment_manifest(*, profile: str) -> dict[str, object]:
    """Capture interpreter/packages without reading environment secrets."""

    packages = {
        distribution.metadata["Name"]: distribution.version
        for distribution in importlib_metadata.distributions()
        if distribution.metadata.get("Name")
    }
    return {
        "schema_version": "h2-onnx-environment-manifest.v1",
        "environment_profile": profile,
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "packages": dict(sorted(packages.items(), key=lambda row: row[0].casefold())),
        "credentials_read": False,
    }


def tooling_status() -> dict[str, object]:
    observed = {
        "torch": _distribution_version("torch"),
        "onnx": _distribution_version("onnx"),
        "onnxruntime": _distribution_version("onnxruntime"),
        "onnxscript": _distribution_version("onnxscript"),
    }
    matches = {
        name: value is not None and value.split("+")[0] == expected
        for name, expected in PINNED_ONNX_TOOLCHAIN.items()
        for value in (observed[name],)
    }
    return {
        "expected": dict(PINNED_ONNX_TOOLCHAIN),
        "observed": observed,
        "matches": matches,
        "status": "MATCH" if all(matches.values()) else "MISMATCH_OR_MISSING",
    }


def inspect_component(
    component_id: str,
    *,
    repository: Path | None = None,
    proposed_onnx_path: Path | None = None,
) -> dict[str, object]:
    """Inspect exact assets, toolchain, and any existing graph."""

    try:
        contract = COMPONENTS[component_id]
    except KeyError as exc:
        raise ValueError(f"unsupported H2 ONNX component: {component_id}") from exc
    repo = Path(repository) if repository is not None else repository_root().path
    checks = [_asset_check(repo, asset) for asset in contract.required_assets]
    if any(check["status"] == "MISSING" for check in checks):
        readiness = "BLOCKED_ASSET_MISSING"
    elif any(check["status"] == "HASH_MISMATCH" for check in checks):
        readiness = "BLOCKED_ASSET_HASH_MISMATCH"
    elif tooling_status()["status"] != "MATCH":
        readiness = "BLOCKED_TOOLCHAIN_MISMATCH"
    else:
        readiness = "READY_FOR_EXPLICIT_EXPORT"

    existing_onnx = None
    if proposed_onnx_path is not None and proposed_onnx_path.is_file():
        existing_onnx = {
            "path": str(proposed_onnx_path.resolve()),
            "bytes": proposed_onnx_path.stat().st_size,
            "sha256": sha256_file(proposed_onnx_path),
            "status": "EXISTING_ONNX_REQUIRES_MANIFEST_AND_PARITY_VALIDATION",
        }

    return {
        "schema_version": ONNX_TOOLING_SCHEMA,
        "tooling_id": ONNX_TOOLING_ID,
        "export_contract_version": ONNX_EXPORT_CONTRACT_VERSION,
        "component": asdict(contract),
        "component_contract_sha256": canonical_sha256(asdict(contract)),
        "requested_precision": FP32_ONLY,
        "opset": ONNX_OPSET,
        "asset_checks": checks,
        "toolchain": tooling_status(),
        "readiness_status": readiness,
        "existing_onnx": existing_onnx,
        "export_adapter_implemented": True,
        "implicit_downloads_allowed": False,
        "parity_tolerance_contract": PARITY_TOLERANCES[component_id],
        "parity_tolerance_contract_sha256": canonical_sha256(
            PARITY_TOLERANCES[component_id]
        ),
        "status": readiness,
    }


def _assert_ready(component_id: str, repository: Path) -> dict[str, object]:
    status = inspect_component(component_id, repository=repository)
    if status["readiness_status"] != "READY_FOR_EXPLICIT_EXPORT":
        raise OnnxExportError(
            f"{component_id} export prerequisites failed: {status['readiness_status']}"
        )
    return status


def _load_redimnet2(repository: Path) -> Any:
    import importlib
    import torch

    source = repository / (
        "models/cache/redimnet2/"
        "source-cdc875670034dd7068013ca2ab21ec083a040ff8"
    )
    checkpoint = repository / "models/cache/redimnet2/b2-vox2-lm.pt"
    source_text = str(source)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    module = importlib.import_module("redimnet2.redimnet2")
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model = module.ReDimNet2Wrap(**dict(payload["model_config"]))
    result = model.load_state_dict(payload["state_dict"])
    if result.missing_keys or result.unexpected_keys:
        raise OnnxExportError(
            "ReDimNet2 state mismatch: "
            f"missing={result.missing_keys}, unexpected={result.unexpected_keys}"
        )
    model.to(device="cpu", dtype=torch.float32)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


def _load_pyannote(repository: Path) -> Any:
    import torch
    from pyannote.audio import Model

    source = repository / "models/cache/pyannote/segmentation-3.0"
    model = Model.from_pretrained(str(source), map_location=torch.device("cpu"))
    if model is None:
        raise OnnxExportError("pyannote loader returned no model")
    model.to(device="cpu", dtype=torch.float32)
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


def load_native_model(component_id: str, *, repository: Path | None = None) -> Any:
    """Load one exact native model after checksum validation."""

    repo = Path(repository) if repository is not None else repository_root().path
    _assert_ready(component_id, repo)
    if component_id == "redimnet2_b2_speaker_embedding":
        return _load_redimnet2(repo)
    if component_id == "pyannote_segmentation_3_0":
        return _load_pyannote(repo)
    raise ValueError(component_id)


def _example_input(component_id: str) -> Any:
    import torch

    contract = COMPONENTS[component_id]
    generator = torch.Generator(device="cpu").manual_seed(3_805_2026)
    if component_id == "redimnet2_b2_speaker_embedding":
        value = torch.randn(
            (1, contract.example_samples), generator=generator, dtype=torch.float32
        )
        return value.mul_(0.01)
    value = torch.randn(
        (1, 1, contract.example_samples), generator=generator, dtype=torch.float32
    )
    return value.mul_(0.01)


def _export_graph(
    model: Any,
    example: Any,
    destination: Path,
    *,
    component: ComponentExportContract,
    exporter: str,
    artifacts_dir: Path,
) -> dict[str, object]:
    import torch

    if exporter not in SUPPORTED_EXPORTERS:
        raise ValueError(f"unsupported exporter: {exporter}")
    started = time.perf_counter()
    common = {
        "model": model,
        "args": (example,),
        "f": destination,
        "input_names": [component.input_name],
        "output_names": [component.output_name],
        "opset_version": ONNX_OPSET,
        "external_data": False,
    }
    if exporter == EXPORTER_DYNAMO:
        dynamic_shapes = None
        if component.dynamic_time:
            sample_dim = torch.export.Dim("num_samples", min=8_000, max=320_000)
            dynamic_shapes = ({1: sample_dim},)
        torch.onnx.export(
            **common,
            dynamo=True,
            dynamic_shapes=dynamic_shapes,
            optimize=True,
            verify=False,
            report=True,
            artifacts_dir=artifacts_dir,
        )
    elif exporter == EXPORTER_LEGACY:
        dynamic_axes = None
        if component.dynamic_time:
            dynamic_axes = {
                component.input_name: {1: "num_samples"},
                component.output_name: {0: "batch"},
            }
        torch.onnx.export(
            **common,
            dynamo=False,
            dynamic_axes=dynamic_axes,
            do_constant_folding=True,
        )
    return {
        "exporter": exporter,
        "dynamic_time_requested": component.dynamic_time,
        "duration_sec": time.perf_counter() - started,
    }


def _validate_and_annotate(
    path: Path,
    *,
    component: ComponentExportContract,
    exporter: str,
    source_checks: list[dict[str, object]],
) -> dict[str, object]:
    import onnx
    from onnx import TensorProto

    graph = onnx.load(str(path), load_external_data=True)
    onnx.checker.check_model(graph, full_check=True)
    float_types = {
        initializer.data_type
        for initializer in graph.graph.initializer
        if initializer.data_type
        in {TensorProto.FLOAT, TensorProto.FLOAT16, TensorProto.DOUBLE, TensorProto.BFLOAT16}
    }
    non_fp32 = sorted(value for value in float_types if value != TensorProto.FLOAT)
    if non_fp32:
        raise OnnxExportError(f"graph contains non-FP32 floating initializers: {non_fp32}")

    metadata = {
        "just_peachy_contract": ONNX_EXPORT_CONTRACT_VERSION,
        "component_id": component.component_id,
        "precision": FP32_ONLY,
        "opset": str(ONNX_OPSET),
        "exporter": exporter,
        "sample_rate_hz": str(SAMPLE_RATE_HZ),
        "input_contract": component.input_contract,
        "output_contract": component.output_contract,
        "postprocessing": component.postprocessing,
        "component_contract_sha256": canonical_sha256(asdict(component)),
        "source_asset_set_sha256": canonical_sha256(source_checks),
        "implicit_downloads_allowed": "false",
    }
    del graph.metadata_props[:]
    for name, value in sorted(metadata.items()):
        prop = graph.metadata_props.add()
        prop.key = name
        prop.value = value
    onnx.save_model(graph, str(path), save_as_external_data=False)
    onnx.checker.check_model(onnx.load(str(path)), full_check=True)

    def shapes(values: Any) -> list[dict[str, object]]:
        return [
            {
                "name": value.name,
                "dimensions": [
                    dimension.dim_param
                    if dimension.dim_param
                    else int(dimension.dim_value)
                    for dimension in value.type.tensor_type.shape.dim
                ],
            }
            for value in values
        ]

    return {
        "onnx_ir_version": graph.ir_version,
        "producer_name": graph.producer_name,
        "producer_version": graph.producer_version,
        "opsets": [
            {"domain": item.domain or "ai.onnx", "version": item.version}
            for item in graph.opset_import
        ],
        "input_shapes": shapes(graph.graph.input),
        "output_shapes": shapes(graph.graph.output),
        "float_initializer_types": sorted(float_types),
        "non_fp32_float_initializer_types": non_fp32,
        "metadata": metadata,
    }


def atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(dict(value), stream, indent=2, sort_keys=True, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except Exception:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def export_component(
    component_id: str,
    *,
    onnx_path: Path,
    repository: Path | None = None,
    exporter: str = EXPORTER_DYNAMO,
    replace: bool = False,
) -> dict[str, object]:
    """Export one real graph with an explicitly named exporter.

    The function never switches exporters automatically. A Dynamo failure is
    retained as evidence; a caller must deliberately request the legacy path.
    """

    if exporter not in SUPPORTED_EXPORTERS:
        raise ValueError(f"exporter must be one of {SUPPORTED_EXPORTERS}")
    repo = Path(repository) if repository is not None else repository_root().path
    preflight = _assert_ready(component_id, repo)
    target = Path(onnx_path).resolve(strict=False)
    if target.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing ONNX graph: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    artifacts_dir = target.parent / f"{target.stem}.export_evidence"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    prior_failure_path = artifacts_dir / "export_failure.json"
    temporary = target.with_name(f".{target.stem}.{os.getpid()}.tmp.onnx")
    if temporary.exists():
        temporary.unlink()

    model = load_native_model(component_id, repository=repo)
    example = _example_input(component_id)
    contract = COMPONENTS[component_id]
    try:
        import torch

        with torch.inference_mode():
            export_execution = _export_graph(
                model,
                example,
                temporary,
                component=contract,
                exporter=exporter,
                artifacts_dir=artifacts_dir,
            )
        graph_validation = _validate_and_annotate(
            temporary,
            component=contract,
            exporter=exporter,
            source_checks=list(preflight["asset_checks"]),
        )
        os.replace(temporary, target)
    except Exception as exc:
        try:
            temporary.unlink()
        except OSError:
            pass
        failure = {
            "schema_version": ONNX_TOOLING_SCHEMA,
            "status": "EXPORT_FAILED",
            "component_id": component_id,
            "exporter": exporter,
            "fallback_attempted": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(prior_failure_path, failure)
        raise OnnxExportError(
            f"explicit {exporter} export failed for {component_id}: {exc}"
        ) from exc

    environment = environment_manifest(profile=contract.native_environment_profile)
    fallback_evidence = None
    if exporter == EXPORTER_LEGACY and prior_failure_path.is_file():
        prior_failure = json.loads(prior_failure_path.read_text(encoding="utf-8"))
        fallback_evidence = {
            "preferred_exporter": EXPORTER_DYNAMO,
            "preferred_exporter_status": prior_failure.get("status"),
            "preferred_exporter_error_type": prior_failure.get("error_type"),
            "failure_evidence_path": str(prior_failure_path),
            "failure_evidence_sha256": sha256_file(prior_failure_path),
        }
    manifest = {
        "schema_version": ONNX_TOOLING_SCHEMA,
        "tooling_id": ONNX_TOOLING_ID,
        "export_contract_version": ONNX_EXPORT_CONTRACT_VERSION,
        "status": "EXPORTED_GRAPH_VALIDATED_PARITY_PENDING",
        "component_id": component_id,
        "component_contract": asdict(contract),
        "component_contract_sha256": canonical_sha256(asdict(contract)),
        "precision": FP32_ONLY,
        "opset": ONNX_OPSET,
        "export_execution": export_execution,
        "fallback_attempted": exporter == EXPORTER_LEGACY,
        "fallback_evidence": fallback_evidence,
        "source_asset_checks": preflight["asset_checks"],
        "source_asset_set_sha256": canonical_sha256(preflight["asset_checks"]),
        "onnx_path": str(target),
        "onnx_bytes": target.stat().st_size,
        "onnx_sha256": sha256_file(target),
        "graph_validation": graph_validation,
        "environment": environment,
        "environment_sha256": canonical_sha256(environment),
        "parity_tolerance_contract": PARITY_TOLERANCES[component_id],
        "parity_tolerance_contract_sha256": canonical_sha256(
            PARITY_TOLERANCES[component_id]
        ),
        "implicit_downloads_allowed": False,
        "model_inference_performed": True,
        "parity_measured": False,
        "linux_arm64_measured": False,
        "production_usable": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = target.with_suffix(target.suffix + ".manifest.json")
    atomic_write_json(manifest_path, manifest)
    return {**manifest, "manifest_path": str(manifest_path)}


def build_export_plan(
    component_id: str,
    *,
    repository: Path | None = None,
    proposed_onnx_path: Path,
) -> dict[str, object]:
    report = inspect_component(
        component_id,
        repository=repository,
        proposed_onnx_path=proposed_onnx_path,
    )
    report.update(
        {
            "operation": "EXPLICIT_EXPORT_PLAN",
            "proposed_onnx_path": str(proposed_onnx_path.resolve(strict=False)),
            "default_exporter": EXPORTER_DYNAMO,
            "fallback_policy": (
                "never automatic; rerun with --exporter torch_onnx_legacy_v1 "
                "and retain Dynamo failure evidence"
            ),
            "forbidden": [
                "int8_export",
                "implicit_model_download",
                "threshold_retuning",
                "held_out_selection",
                "claiming_ARM64_readiness_without_hardware_measurement",
            ],
        }
    )
    return report


def build_parity_plan(
    component_id: str,
    *,
    native_artifact_sha256: str,
    onnx_artifact_sha256: str | None,
) -> dict[str, object]:
    if component_id not in COMPONENTS:
        raise ValueError(f"unsupported H2 ONNX component: {component_id}")
    if len(native_artifact_sha256) != 64:
        raise ValueError("native_artifact_sha256 must be a SHA-256 digest")
    if onnx_artifact_sha256 is not None and len(onnx_artifact_sha256) != 64:
        raise ValueError("onnx_artifact_sha256 must be a SHA-256 digest")
    return {
        "schema_version": ONNX_TOOLING_SCHEMA,
        "tooling_id": ONNX_TOOLING_ID,
        "component_id": component_id,
        "precision": FP32_ONLY,
        "native_artifact_sha256": native_artifact_sha256.lower(),
        "onnx_artifact_sha256": (
            onnx_artifact_sha256.lower() if onnx_artifact_sha256 else None
        ),
        "tolerances": PARITY_TOLERANCES[component_id],
        "tolerance_contract_sha256": canonical_sha256(
            PARITY_TOLERANCES[component_id]
        ),
        "measurement_status": "PENDING",
        "required_diagnostics": (
            [
                "absolute_and_relative_embedding_error",
                "cosine_and_pair_score_error",
                "identity_decision_equivalence",
                "clustering_coassignment_equivalence",
            ]
            if component_id == "redimnet2_b2_speaker_embedding"
            else [
                "raw_frame_output_error",
                "powerset_frame_agreement",
                "speech_overlap_activity_agreement",
                "onset_offset_boundary_delta",
                "downstream_region_equivalence",
            ]
        ),
        "parity_measured": False,
        "parity_passed": False,
        "production_usable": False,
        "status": "PARITY_PLAN_FROZEN_NOT_MEASURED",
    }


__all__ = [
    "COMPONENTS",
    "ComponentExportContract",
    "OnnxExportError",
    "atomic_write_json",
    "build_export_plan",
    "build_parity_plan",
    "canonical_sha256",
    "environment_manifest",
    "export_component",
    "inspect_component",
    "load_native_model",
    "sha256_file",
    "tooling_status",
]
