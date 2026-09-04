from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pytest

from app.full_pipeline.factory import build_file_runtime
from app.h2_portability.runtime_profile import (
    H2PortableRuntimeConfig,
    H2RuntimeProfileError,
    REDIM_COMPONENT,
    SEGMENTATION_COMPONENT,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
SMOKE_AUDIO = (
    TOOL_ROOT / "artifacts/realtime_test_audio/aew_rxr_eey_arctic_a0301_concat.wav"
)


def _graph_pair(tmp_path: Path) -> tuple[dict[str, Path], dict[str, str]]:
    paths = {
        REDIM_COMPONENT: tmp_path / "redim.onnx",
        SEGMENTATION_COMPONENT: tmp_path / "segmentation.onnx",
    }
    paths[REDIM_COMPONENT].write_bytes(b"bounded-redim-graph")
    paths[SEGMENTATION_COMPONENT].write_bytes(b"bounded-segmentation-graph")
    hashes = {
        key: hashlib.sha256(path.read_bytes()).hexdigest()
        for key, path in paths.items()
    }
    return paths, hashes


def test_config_requires_both_exact_graph_hashes(tmp_path: Path) -> None:
    paths, hashes = _graph_pair(tmp_path)
    config = H2PortableRuntimeConfig(
        redimnet2_path=paths[REDIM_COMPONENT],
        segmentation_path=paths[SEGMENTATION_COMPONENT],
        expected_sha256=hashes,
    )
    assert config.to_jsonable()["implicit_downloads_allowed"] is False
    bad = dict(hashes)
    bad[REDIM_COMPONENT] = "0" * 64
    with pytest.raises(H2RuntimeProfileError, match="graph hash mismatch"):
        H2PortableRuntimeConfig(
            redimnet2_path=paths[REDIM_COMPONENT],
            segmentation_path=paths[SEGMENTATION_COMPONENT],
            expected_sha256=bad,
        )


def test_common_factory_keeps_reference_default_and_builds_explicit_profile(
    tmp_path: Path, monkeypatch
) -> None:
    reference = build_file_runtime(
        pipeline_id="fullpipe_v1_ag_dr_ir",
        input_path=SMOKE_AUDIO,
        output_root=tmp_path / "reference",
        enrollment_root=tmp_path / "reference-enrollment",
        duration_sec=1.0,
        telemetry_enabled=False,
    )
    assert "runtime_profile" not in reference.identities

    paths, hashes = _graph_pair(tmp_path)
    monkeypatch.setenv("JP_H2_ONNX_WORKER_PYTHON", sys.executable)
    monkeypatch.setenv("JP_H2_ASR_WORKER_PYTHON", sys.executable)
    portable = build_file_runtime(
        pipeline_id="fullpipe_v1_ag_dr_ir",
        input_path=SMOKE_AUDIO,
        output_root=tmp_path / "portable",
        enrollment_root=tmp_path / "portable-enrollment",
        duration_sec=1.0,
        telemetry_enabled=False,
        runtime_profile="H2_PORTABLE_ONNX_FP32",
        h2_onnx_graphs=paths,
        h2_onnx_expected_sha256=hashes,
    )
    identity = portable.identities["runtime_profile"].to_contract()
    assert identity["backend_id"] == "H2_PORTABLE_ONNX_FP32"
    assert set(identity["model_asset_sha256s"]) == set(hashes.values())
    assert identity["environment_profile_id"] == "redimnet2"

    portable_r1 = build_file_runtime(
        pipeline_id="fullpipe_v1_ag_dr_ir",
        input_path=SMOKE_AUDIO,
        output_root=tmp_path / "portable-r1",
        enrollment_root=tmp_path / "portable-r1-enrollment",
        duration_sec=1.0,
        telemetry_enabled=False,
        runtime_tuning={"redim_execution_strategy": "R1_TWO_INDEPENDENT_MODELS"},
        runtime_profile="H2_PORTABLE_ONNX_FP32",
        h2_onnx_graphs=paths,
        h2_onnx_expected_sha256=hashes,
    )
    assert portable_r1.diarization_embedder is not portable_r1.identity_embedder
