from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path

import pytest

from app.full_pipeline.product_modes import H2ProductMode, H2RuntimeTuning
from app.full_pipeline_demo.exports import export_session
from app.full_pipeline_demo.runtime_config import (
    DemoRuntimeConfigError,
    build_h2_demo_runtime_binding_payload,
    load_h2_demo_runtime_binding,
)
from app.full_pipeline_demo.session import DemoSessionManager


AG_H2 = "fullpipe_v1_ag_dr_ir"
AO_H2 = "fullpipe_v1_ao_dr_ir"


class _ImmediateRuntime:
    def run(self) -> dict[str, object]:
        return {"completion_state": "complete", "errors": []}


def _selected_tuning(mode: str) -> H2RuntimeTuning:
    return H2RuntimeTuning(
        product_mode=H2ProductMode(mode),
        segmentation_hop_sec=0.5,
        segmentation_onset=0.61,
        segmentation_offset=0.43,
        segmentation_min_speech_sec=0.1,
        segmentation_min_silence_sec=0.2,
        embedding_window_sec=2.0,
        embedding_hop_sec=0.5,
        minimum_embedding_sec=1.0,
        clustering_threshold=0.41,
        short_turn_attach_gap_sec=0.25,
        overlap_policy="INCLUDE_PREDICTED_OVERLAP",
        identity_accumulation="recent_window",
        boundary_correction_ms=500,
        paragraph_policy="T4_SPEAKER_CHANGE_DOMINANT",
        paragraph_pause_sec=1.1,
        paragraph_max_words=42,
        score_threshold=0.73,
        margin_threshold=0.08,
        minimum_evidence_sec=2.5,
        minimum_embedding_consistency=0.32,
        consecutive_passes_to_confirm=3,
        consecutive_failures_to_release=2,
        hysteresis=0.04,
        identity_expiry_sec=60.0,
        hysteresis_policy="H3_THREE_CONFIRM_SAFE",
        memory_level=(
            "M2_CONFIRMED_NAME"
            if mode == "H2_SESSION_MEMORY_ENHANCED"
            else None
        ),
        maximum_identity_observations_per_cluster=17,
        maximum_cluster_embeddings=55,
        maximum_session_speakers=11,
        maximum_identity_history_per_cluster=19,
        maximum_roster_entries=13,
        maximum_session_event_history=99,
    )


def _entry(pipeline_id: str, tuning: H2RuntimeTuning) -> dict[str, object]:
    return {
        "pipeline_id": pipeline_id,
        "mode": tuning.product_mode.value,
        "runtime_tuning": tuning.to_jsonable(),
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
    }


def _write_binding(
    path: Path,
    *,
    entries: list[dict[str, object]],
    default_mode: str,
    lifecycle: str = "FROZEN",
) -> tuple[dict[str, object], str]:
    payload = build_h2_demo_runtime_binding_payload(
        lifecycle=lifecycle,
        default_product_mode=default_mode,
        configurations=entries,
        provenance={"selection_split": "development"},
    )
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload, hashlib.sha256(path.read_bytes()).hexdigest()


def _validator(pipeline_id: str) -> dict[str, object]:
    return {
        "pipeline_id": pipeline_id,
        "pipeline_config_sha256": "a" * 64,
    }


def test_file_and_live_builders_receive_exact_bound_tuning_and_identity(
    tmp_path: Path,
) -> None:
    anonymous = _selected_tuning("H2_SESSION_ANONYMOUS")
    memory = replace(
        anonymous,
        product_mode=H2ProductMode.SESSION_MEMORY_ENHANCED,
        memory_level="M2_CONFIRMED_NAME",
    )
    config_path = tmp_path / "selected-demo-binding.json"
    _payload, file_sha = _write_binding(
        config_path,
        entries=[_entry(AG_H2, anonymous), _entry(AG_H2, memory)],
        default_mode="H2_SESSION_ANONYMOUS",
    )
    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF-fixture")
    file_calls: list[dict[str, object]] = []
    live_calls: list[dict[str, object]] = []

    def file_builder(**kwargs: object) -> _ImmediateRuntime:
        file_calls.append(dict(kwargs))
        return _ImmediateRuntime()

    def live_builder(**kwargs: object) -> _ImmediateRuntime:
        live_calls.append(dict(kwargs))
        return _ImmediateRuntime()

    file_manager = DemoSessionManager(
        tmp_path / "file-runs",
        file_builder=file_builder,
        pipeline_validator=_validator,
        runtime_config_path=config_path,
        runtime_config_expected_sha256=file_sha,
    )
    assert file_manager.default_product_mode == "H2_SESSION_ANONYMOUS"
    file_started = file_manager.start_file(
        pipeline_id=AG_H2,
        input_path=source,
        pace=0.0,
    )
    file_status = file_manager.join(str(file_started["session_id"]), timeout=2)
    assert file_status["state"] == "completed"
    assert file_calls[0]["product_mode"] == "H2_SESSION_ANONYMOUS"
    file_tuning_payload = file_calls[0]["runtime_tuning"]
    assert isinstance(file_tuning_payload, dict)
    assert set(file_tuning_payload) == {
        *anonymous.to_jsonable(),
        "identity_sha256",
    }
    assert (
        H2RuntimeTuning.from_mapping(file_tuning_payload).identity_sha256
        == anonymous.identity_sha256
    )
    assert file_status["scientific_config_status"] == (
        "FROZEN_SCIENTIFIC_CONFIGURATION"
    )
    assert file_status["scientific_config_path"] == str(config_path.resolve())
    assert file_status["scientific_config_sha256"] == file_sha
    assert file_status["runtime_tuning_identity_sha256"] == (
        anonymous.identity_sha256
    )
    durable = json.loads(
        (
            Path(str(file_status["output_root"]))
            / "manifests/demo_runtime_configuration.json"
        ).read_text(encoding="utf-8")
    )
    assert durable == file_status["scientific_runtime_configuration"]

    export_root = tmp_path / "file-export"
    exported = export_session(
        Path(str(file_status["output_root"])),
        export_root,
        manager_status=file_status,
    )
    assert exported["scientific_config_status"] == (
        "FROZEN_SCIENTIFIC_CONFIGURATION"
    )
    exported_config = json.loads(
        (
            export_root / "manifests/scientific_runtime_configuration.json"
        ).read_text(encoding="utf-8")
    )
    assert exported_config == durable

    live_manager = DemoSessionManager(
        tmp_path / "live-runs",
        microphone_builder=live_builder,
        pipeline_validator=_validator,
        runtime_config_path=config_path,
        runtime_config_expected_sha256=file_sha,
    )
    live_started = live_manager.start_microphone(
        pipeline_id=AG_H2,
        product_mode="H2_SESSION_MEMORY_ENHANCED",
        duration_sec=1.0,
    )
    live_status = live_manager.join(str(live_started["session_id"]), timeout=2)
    assert live_status["state"] == "completed"
    assert live_calls[0]["product_mode"] == "H2_SESSION_MEMORY_ENHANCED"
    live_tuning_payload = live_calls[0]["runtime_tuning"]
    assert isinstance(live_tuning_payload, dict)
    loaded_live_tuning = H2RuntimeTuning.from_mapping(live_tuning_payload)
    assert loaded_live_tuning.identity_sha256 == memory.identity_sha256
    anonymous_axes = anonymous.to_jsonable()
    memory_axes = memory.to_jsonable()
    anonymous_axes.pop("product_mode")
    memory_axes.pop("product_mode")
    anonymous_axes.pop("memory_level")
    memory_axes.pop("memory_level")
    assert anonymous_axes == memory_axes


def test_corrupt_mismatched_and_stale_bindings_fail_closed(tmp_path: Path) -> None:
    tuning = _selected_tuning("H2_SESSION_ANONYMOUS")
    path = tmp_path / "binding.json"
    payload, file_sha = _write_binding(
        path,
        entries=[_entry(AG_H2, tuning)],
        default_mode="H2_SESSION_ANONYMOUS",
    )

    with pytest.raises(DemoRuntimeConfigError, match="file SHA-256 mismatch"):
        load_h2_demo_runtime_binding(path, expected_sha256="0" * 64)

    stale = json.loads(json.dumps(payload))
    stale["configurations"][0]["runtime_tuning_identity_sha256"] = "1" * 64
    stale.pop("binding_identity_sha256")
    stale = {
        **stale,
        "binding_identity_sha256": build_h2_demo_runtime_binding_payload(
            lifecycle=str(stale["lifecycle"]),
            default_product_mode=str(stale["default_product_mode"]),
            configurations=stale["configurations"],
            provenance=stale["provenance"],
        )["binding_identity_sha256"],
    }
    stale_path = tmp_path / "stale.json"
    stale_path.write_text(json.dumps(stale), encoding="utf-8")
    with pytest.raises(
        DemoRuntimeConfigError, match="runtime_tuning_identity_sha256 mismatch"
    ):
        load_h2_demo_runtime_binding(stale_path)

    corrupt_identity = dict(payload)
    corrupt_identity["binding_identity_sha256"] = "2" * 64
    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text(json.dumps(corrupt_identity), encoding="utf-8")
    with pytest.raises(DemoRuntimeConfigError, match="binding_identity_sha256"):
        load_h2_demo_runtime_binding(corrupt_path)

    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF")
    manager = DemoSessionManager(
        tmp_path / "runs",
        file_builder=lambda **_kwargs: _ImmediateRuntime(),
        pipeline_validator=_validator,
        runtime_config_path=path,
        runtime_config_expected_sha256=file_sha,
    )
    with pytest.raises(DemoRuntimeConfigError, match="no exact entry"):
        manager.start_file(pipeline_id=AO_H2, input_path=source)
    with pytest.raises(DemoRuntimeConfigError, match="no exact entry"):
        manager.start_file(
            pipeline_id=AG_H2,
            product_mode="H2_SESSION_MEMORY_ENHANCED",
            input_path=source,
        )

    incompatible_builder = DemoSessionManager(
        tmp_path / "incompatible-builder-runs",
        file_builder=lambda output_root: _ImmediateRuntime(),
        pipeline_validator=_validator,
        runtime_config_path=path,
        runtime_config_expected_sha256=file_sha,
    )
    started = incompatible_builder.start_file(
        pipeline_id=AG_H2,
        input_path=source,
    )
    failed = incompatible_builder.join(str(started["session_id"]), timeout=2)
    assert failed["state"] == "failed"
    assert "does not accept exact keyword" in failed["failures"][0]["message"]

    path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(DemoRuntimeConfigError, match="changed after it was loaded"):
        manager.start_file(pipeline_id=AG_H2, input_path=source)


def test_frozen_per_mode_config_and_engineering_baseline_are_explicit(
    tmp_path: Path,
) -> None:
    tuning = _selected_tuning("H2_KNOWN_ONLY")
    frozen_path = tmp_path / "H2_KNOWN_ONLY.json"
    frozen = {
        "schema_version": "h2-frozen-product-configuration.v1",
        "mode": "H2_KNOWN_ONLY",
        "pipeline_id": AG_H2,
        "freeze_identity_sha256": "f" * 64,
        "runtime_tuning": tuning.to_jsonable(),
        "runtime_tuning_identity_sha256": tuning.identity_sha256,
    }
    frozen_path.write_text(json.dumps(frozen), encoding="utf-8")
    binding = load_h2_demo_runtime_binding(frozen_path)
    selection = binding.select(AG_H2)
    assert selection.status == "FROZEN_SCIENTIFIC_CONFIGURATION"
    assert selection.product_mode == "H2_KNOWN_ONLY"
    assert selection.final_scientific_validation is False

    calls: list[dict[str, object]] = []
    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF")
    baseline = DemoSessionManager(
        tmp_path / "baseline-runs",
        file_builder=lambda **kwargs: (
            calls.append(dict(kwargs)) or _ImmediateRuntime()
        ),
        pipeline_validator=_validator,
    )
    started = baseline.start_file(pipeline_id=AG_H2, input_path=source, pace=0.0)
    status = baseline.join(str(started["session_id"]), timeout=2)
    assert status["scientific_config_status"] == "ENGINEERING_BASELINE_NOT_FINAL"
    assert status["final_scientific_validation"] is False
    assert status["runtime_tuning_identity_sha256"]
    assert "runtime_tuning" in calls[0]


def test_binding_rejects_unknown_schema_and_expected_hash_without_path(
    tmp_path: Path,
) -> None:
    path = tmp_path / "unknown.json"
    path.write_text(json.dumps({"schema_version": "future.v9"}), encoding="utf-8")
    with pytest.raises(DemoRuntimeConfigError, match="unsupported"):
        load_h2_demo_runtime_binding(path)
    with pytest.raises(ValueError, match="requires runtime_config_path"):
        DemoSessionManager(
            tmp_path / "runs",
            runtime_config_expected_sha256="a" * 64,
        )
