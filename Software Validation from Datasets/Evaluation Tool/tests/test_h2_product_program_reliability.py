from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import threading
import time

import pytest

from app.full_pipeline.product_modes import H2ProductMode, H2RuntimeTuning
from app.full_pipeline_extended_evaluation import execution as shared_execution
from app.h2_product_program import reliability as reliability_module
from app.h2_product_program.contracts import H2Job, H2ProgramError
from app.h2_product_program.io import read_json, write_json_atomic, write_jsonl_atomic
from app.h2_product_program.planning import (
    build_job_manifest,
    build_protocol_manifest,
    default_paths,
)
from app.h2_product_program.reliability import (
    LONG_SESSION_DURATIONS_SEC,
    _execute_long_sessions,
    _bounded_state_evidence,
    _publish_subresult,
    _runtime_evidence,
    _subresult_reusable,
    build_long_session_source_plan,
    validate_reliability_tuning,
)


def _planned_job(kind: str) -> tuple[H2Job, dict[str, object]]:
    paths = default_paths()
    protocol = build_protocol_manifest(paths)
    manifest = build_job_manifest(protocol)
    job = next(
        H2Job.from_jsonable(row)
        for row in manifest["jobs"]
        if row["job_kind"] == kind
    )
    return job, protocol


def test_long_source_plan_uses_declared_recordings_and_30_60_minutes() -> None:
    job, protocol = _planned_job("long_session")

    plan = build_long_session_source_plan(
        default_paths(),
        job,
        protocol=protocol,
    )

    assert plan["source_count"] == 4
    assert len(plan["streams"]) == 8
    assert tuple(plan["target_durations_sec"]) == LONG_SESSION_DURATIONS_SEC
    assert {row["target_duration_sec"] for row in plan["streams"]} == {
        1800.0,
        3600.0,
    }
    assert all(row["scenario"]["long_session"] is True for row in plan["sources"])
    assert plan["ordinary_dev_core_cases_treated_as_long_streams"] is False
    assert plan["evaluation_material_inspected"] is False


def test_heldout_long_source_plan_is_presealed_8_sources_16_streams_12_hours() -> None:
    job, protocol = _planned_job("long_session_evaluation")

    plan = build_long_session_source_plan(default_paths(), job, protocol=protocol)

    assert plan["split"] == "evaluation"
    assert plan["development_only"] is False
    assert plan["source_count"] == 8
    assert plan["stream_count"] == 16
    assert plan["target_source_hours"] == 12.0
    assert len(plan["presealed_case_ids"]) == 24
    assert plan["no_recalibration"] is True
    assert plan["identity_scoring_scope"] == "RESOURCE_STATE_ONLY_EMPTY_GALLERY"
    assert plan["known_identity_or_reentry_metrics_scored"] is False


def test_final_tuning_must_match_controller_product_mode() -> None:
    job, _protocol = _planned_job("reliability")
    selected = H2RuntimeTuning(
        product_mode=H2ProductMode.SESSION_MEMORY_ENHANCED,
        score_threshold=0.61,
    )

    assert validate_reliability_tuning(job, selected) is selected
    with pytest.raises(Exception, match="product mode conflicts"):
        validate_reliability_tuning(
            job,
            H2RuntimeTuning(product_mode=H2ProductMode.KNOWN_ONLY),
        )


def test_bounded_state_is_measured_against_source_clock() -> None:
    tuning = H2RuntimeTuning(maximum_roster_entries=2, maximum_session_event_history=3)
    observations = [
        {
            "source_time_sec": 1.0,
            "bounded_session_state": {
                "identity_observation_count": 2,
                "identity_cluster_count": 1,
                "identity_history_count": 2,
            },
            "session_memory": {
                "roster_count": 1,
                "history_count": 2,
            },
        },
        {
            "source_time_sec": 2.0,
            "bounded_session_state": {
                "identity_observation_count": 3,
                "identity_cluster_count": 2,
                "identity_history_count": 3,
            },
            "session_memory": {
                "roster_count": 2,
                "history_count": 3,
            },
        },
    ]

    evidence = _bounded_state_evidence(observations, tuning)
    assert evidence["status"] == "PASS"
    assert evidence["measurement_clock"] == "normalized_audio_source_time_sec"
    assert evidence["maximum_observed_cardinalities"]["session_memory_roster_count"] == 2

    observations[0]["session_id"] = "session-one"
    observations[1]["session_id"] = "session-two"
    observations[1]["source_time_sec"] = 0.5
    restarted = _bounded_state_evidence(observations, tuning)
    assert restarted["status"] == "PASS"

    observations[-1]["session_memory"]["roster_count"] = 3
    failed = _bounded_state_evidence(observations, tuning)
    assert failed["status"] == "FAIL"
    assert failed["violations"][0]["bound"] == "session_memory_roster_count"


def test_runtime_evidence_reports_events_revisions_queue_rtf_ram_and_deadlines(
    tmp_path: Path,
) -> None:
    root = tmp_path / "runtime"
    write_jsonl_atomic(
        root / "events/events.jsonl",
        [
            {
                "session_id": "session-a",
                "event_type": "transcript_revision",
                "capture_timestamps": {"audio_end_sec": 1.0},
            },
            {
                "session_id": "session-a",
                "event_type": "identity_revision",
                "capture_timestamps": {"audio_end_sec": 2.0},
            },
        ],
    )
    write_json_atomic(
        root / "metrics/runtime_metrics.json",
        {
            "counts": {"transcript_revisions": 2, "deadline_miss_count": 1},
            "queue": {"maximum_observed_depth": 4, "dropped_frames": 3},
            "asr": {"partial_revision_count": 5},
        },
    )
    write_jsonl_atomic(
        root / "telemetry/resource_samples.jsonl",
        [{"process_rss_bytes": 100}, {"process_rss_bytes": 250}],
    )
    tuning = H2RuntimeTuning()
    observations = [
        {
            "source_time_sec": 2.0,
            "bounded_session_state": {
                "identity_observation_count": 1,
                "identity_cluster_count": 1,
                "identity_history_count": 1,
            },
            "session_memory": {"roster_count": 1, "history_count": 1},
        }
    ]

    evidence = _runtime_evidence(
        root,
        completions=["complete"],
        wall_sec=4.0,
        observations=observations,
        tuning=tuning,
    )

    assert evidence["event_count"] == 2
    assert evidence["transcript_revision_count"] == 2
    assert evidence["asr_partial_revision_count"] == 5
    assert evidence["identity_revision_event_count"] == 1
    assert evidence["maximum_queue_depth"] == 4
    assert evidence["dropped_frame_count"] == 3
    assert evidence["deadline_counters"] == {"deadline_miss_count": 1}
    assert evidence["real_time_factor"] == pytest.approx(2.0)
    assert evidence["peak_process_rss_bytes"] == 250
    assert evidence["bounded_state_evidence"]["status"] == "PASS"


def test_uninjectable_device_behavior_is_explicitly_unsupported(tmp_path: Path) -> None:
    value = shared_execution.run_reliability_fault(
        {"fault_id": "device_reconnect", "target_duration_sec": 30.0},
        spec=SimpleNamespace(pipeline_id="fullpipe_v1_ag_dr_ir", job_id="device"),
        input_path=tmp_path / "not-opened.wav",
        output_root=tmp_path / "output",
        stop_requested=lambda: False,
        decision_policy_registry_path=None,
        runtime_tuning=H2RuntimeTuning(),
        product_mode="H2_SESSION_MEMORY_ENHANCED",
    )

    assert value["harness_status"] == "UNSUPPORTED"
    assert value["fault_injected"] is False
    assert value["physical_human_microphone_claimed"] is False
    assert "no deterministic hardware" in value["unsupported_reason"]


def test_subresult_reuse_requires_exact_checksum_tree(tmp_path: Path) -> None:
    binding = {"execution_binding_sha256": "a" * 64}
    root = tmp_path / "subresult"
    write_json_atomic(root / "evidence.json", {"value": 1})
    _publish_subresult(
        root,
        {
            "schema_version": "test.v1",
            "harness_status": "PASS",
            "execution_binding_sha256": binding["execution_binding_sha256"],
        },
        binding,
    )
    assert _subresult_reusable(root, binding)

    write_json_atomic(root / "evidence.json", {"value": 2})
    assert not _subresult_reusable(root, binding)


def test_long_stream_stop_resume_progress_and_corruption_repair_are_atomic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, _protocol = _planned_job("long_session")
    job = replace(
        job,
        case_ids=("sealed-a", "sealed-b", "sealed-c"),
        audio_duration_sec=0.003,
    )
    tuning = H2RuntimeTuning(product_mode=H2ProductMode.SESSION_MEMORY_ENHANCED)
    sources = [
        {
            "source_recording_id": f"source-{index}",
            "source_case_id": f"sealed-{index}",
            "source_audio_identity": str(index) * 64,
        }
        for index in range(1, 4)
    ]
    streams = [
        {
            "stream_id": f"stream-{index}",
            "source_recording_id": f"source-{index}",
            "target_duration_sec": 0.001,
        }
        for index in range(1, 4)
    ]
    plan = {"sources": sources, "streams": streams}
    binding = {"execution_binding_sha256": "a" * 64}
    calls: list[str] = []
    stop = threading.Event()
    stop_after_first = {"enabled": True}

    def materialize(
        _source: object, stream: dict[str, object], *, destination_root: Path
    ) -> tuple[Path, dict[str, object]]:
        destination_root.mkdir(parents=True, exist_ok=True)
        path = destination_root / f"{stream['stream_id']}.wav"
        path.write_bytes(b"generated-loopback")
        write_json_atomic(path.with_suffix(".materialization.json"), {"fixture": True})
        return path, {
            "duration_sec": stream["target_duration_sec"],
            "output_path": str(path),
        }

    def run_session(spec: object, **kwargs: object) -> dict[str, object]:
        calls.append(str(spec.job_id))
        assert kwargs["stop_requested"]() is False  # atomic item is not interrupted
        time.sleep(0.02)
        if stop_after_first["enabled"] and len(calls) == 1:
            stop.set()
        return {"completion_state": "complete"}

    monkeypatch.setattr(reliability_module, "_materialize_long_stream", materialize)
    monkeypatch.setattr(
        reliability_module.shared_execution,
        "run_controlled_file_session",
        run_session,
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_evidence",
        lambda *_args, **_kwargs: {
            "bounded_state_evidence": {"status": "PASS"}
        },
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_tuning_evidence",
        lambda *_args, **_kwargs: {"status": "PASS"},
    )
    progress: list[dict[str, object]] = []
    result_root = tmp_path / "long"

    first = _execute_long_sessions(
        default_paths(),
        job,
        binding=binding,
        tuning=tuning,
        source_plan=plan,
        result_root=result_root,
        stop_event=stop,
        runtime_builder=None,
        progress=lambda **values: progress.append(values),
        storage_reserve_callback=lambda: None,
    )
    assert first["status"] == "STOPPED"
    assert calls == ["stream-1"]
    first_checksum = (
        result_root / "long_sessions/stream-1/checksums.json"
    ).read_bytes()
    assert progress[-1]["completed_items"] == 1

    stop.clear()
    stop_after_first["enabled"] = False
    calls.clear()
    second = _execute_long_sessions(
        default_paths(),
        job,
        binding=binding,
        tuning=tuning,
        source_plan=plan,
        result_root=result_root,
        stop_event=stop,
        runtime_builder=None,
        progress=lambda **values: progress.append(values),
        storage_reserve_callback=lambda: None,
    )
    assert second["status"] == "COMPLETE", second
    assert calls == ["stream-2", "stream-3"]
    assert (
        result_root / "long_sessions/stream-1/checksums.json"
    ).read_bytes() == first_checksum
    assert not list((result_root / "inputs").glob("*.wav"))
    assert second["cleanup"]["path_refusal_count"] == 0
    assert second["cleanup"]["successful_runtime_compactions"] == 3

    corrupt = result_root / "long_sessions/stream-1/result.json"
    value = corrupt.read_text(encoding="utf-8").replace(
        '"harness_status": "PASS"', '"harness_status": "FAIL"'
    )
    corrupt.write_text(value, encoding="utf-8")
    calls.clear()
    repaired = _execute_long_sessions(
        default_paths(),
        job,
        binding=binding,
        tuning=tuning,
        source_plan=plan,
        result_root=result_root,
        stop_event=stop,
        runtime_builder=None,
        progress=None,
        storage_reserve_callback=lambda: None,
    )
    assert repaired["status"] == "COMPLETE"
    assert calls == ["stream-1"]


def test_long_stream_storage_reserve_stops_before_next_atomic_item(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, _protocol = _planned_job("long_session")
    tuning = H2RuntimeTuning(product_mode=H2ProductMode.SESSION_MEMORY_ENHANCED)
    plan = {
        "sources": [
            {
                "source_recording_id": "source",
                "source_case_id": "sealed",
                "source_audio_identity": "1" * 64,
            }
        ],
        "streams": [
            {
                "stream_id": f"stream-{index}",
                "source_recording_id": "source",
                "target_duration_sec": 0.001,
            }
            for index in (1, 2)
        ],
    }
    calls: list[str] = []
    reserve_calls = 0

    def materialize(
        _source: object, stream: dict[str, object], *, destination_root: Path
    ) -> tuple[Path, dict[str, object]]:
        destination_root.mkdir(parents=True, exist_ok=True)
        path = destination_root / f"{stream['stream_id']}.wav"
        path.write_bytes(b"generated-loopback")
        write_json_atomic(path.with_suffix(".materialization.json"), {"fixture": True})
        return path, {
            "duration_sec": stream["target_duration_sec"],
            "output_path": str(path),
        }

    monkeypatch.setattr(
        reliability_module,
        "_materialize_long_stream",
        materialize,
    )

    def run_session(spec: object, **_kwargs: object) -> dict[str, object]:
        calls.append(str(spec.job_id))
        time.sleep(0.02)
        return {"completion_state": "complete"}

    monkeypatch.setattr(
        reliability_module.shared_execution,
        "run_controlled_file_session",
        run_session,
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_evidence",
        lambda *_args, **_kwargs: {
            "bounded_state_evidence": {"status": "PASS"}
        },
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_tuning_evidence",
        lambda *_args, **_kwargs: {"status": "PASS"},
    )

    def reserve() -> None:
        nonlocal reserve_calls
        reserve_calls += 1
        if reserve_calls == 2:
            raise RuntimeError("35 GiB reserve violated")

    stop = threading.Event()
    root = tmp_path / "storage"
    outcome = _execute_long_sessions(
        default_paths(),
        job,
        binding={"execution_binding_sha256": "b" * 64},
        tuning=tuning,
        source_plan=plan,
        result_root=root,
        stop_event=stop,
        runtime_builder=None,
        progress=None,
        storage_reserve_callback=reserve,
    )

    assert outcome["status"] == "STOPPED"
    assert calls == ["stream-1"]
    assert stop.is_set()
    assert (root / "long_sessions/stream-1/checksums.json").is_file()
    assert not (root / "long_sessions/stream-2/result.json").exists()


def test_runtime_cleanup_refuses_path_escape_and_preserves_diagnostics(
    tmp_path: Path,
) -> None:
    subroot = tmp_path / "subresult"
    escaped_attempt = tmp_path / "outside" / "attempt_001"
    escaped_runtime = escaped_attempt / "runtime"
    escaped_runtime.mkdir(parents=True)
    diagnostic = escaped_runtime / "diagnostic.bin"
    diagnostic.write_bytes(b"must-not-be-deleted")

    with pytest.raises(H2ProgramError, match="escaped"):
        reliability_module._cleanup_runtime_before_seal(
            subroot=subroot,
            attempt_root=escaped_attempt,
            runtime_root=escaped_runtime,
            item_kind="long_session",
            item_id="escape-test",
            harness_status="PASS",
        )

    assert diagnostic.read_bytes() == b"must-not-be-deleted"
    receipts = list((subroot / "cleanup_receipts").glob("*.json"))
    assert len(receipts) == 1
    assert read_json(receipts[0])["status"] == "REFUSED"


def test_failed_long_stream_retains_runtime_and_generated_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job, _protocol = _planned_job("long_session")
    job = replace(job, case_ids=("sealed",), audio_duration_sec=0.001)
    tuning = H2RuntimeTuning(product_mode=H2ProductMode.SESSION_MEMORY_ENHANCED)
    plan = {
        "sources": [
            {
                "source_recording_id": "source",
                "source_case_id": "sealed",
                "source_audio_identity": "1" * 64,
            }
        ],
        "streams": [
            {
                "stream_id": "stream-fail",
                "source_recording_id": "source",
                "target_duration_sec": 0.001,
            }
        ],
    }

    def materialize(
        _source: object, stream: dict[str, object], *, destination_root: Path
    ) -> tuple[Path, dict[str, object]]:
        destination_root.mkdir(parents=True, exist_ok=True)
        path = destination_root / f"{stream['stream_id']}.wav"
        path.write_bytes(b"generated-loopback")
        write_json_atomic(path.with_suffix(".materialization.json"), {"fixture": True})
        return path, {
            "duration_sec": stream["target_duration_sec"],
            "output_path": str(path),
        }

    def run_failed(_spec: object, **kwargs: object) -> dict[str, object]:
        runtime = Path(str(kwargs["output_root"]))
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "diagnostic.bin").write_bytes(b"retain-failure")
        return {"completion_state": "failed", "errors": ["fixture failure"]}

    monkeypatch.setattr(reliability_module, "_materialize_long_stream", materialize)
    monkeypatch.setattr(
        reliability_module.shared_execution,
        "run_controlled_file_session",
        run_failed,
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_evidence",
        lambda *_args, **_kwargs: {
            "bounded_state_evidence": {"status": "PASS"}
        },
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_tuning_evidence",
        lambda *_args, **_kwargs: {"status": "PASS"},
    )
    binding = {"execution_binding_sha256": "c" * 64}
    root = tmp_path / "failed-long"

    outcome = _execute_long_sessions(
        default_paths(),
        job,
        binding=binding,
        tuning=tuning,
        source_plan=plan,
        result_root=root,
        stop_event=threading.Event(),
        runtime_builder=None,
        progress=None,
        storage_reserve_callback=lambda: None,
    )

    subroot = root / "long_sessions/stream-fail"
    runtime = subroot / "attempts/attempt_001/runtime/diagnostic.bin"
    generated = root / "inputs/stream-fail.wav"
    expected_binding = reliability_module._subbinding(
        binding, "long_session", "stream-fail"
    )
    payload = read_json(subroot / "result.json")
    assert outcome["status"] == "FAILED"
    assert runtime.read_bytes() == b"retain-failure"
    assert generated.is_file()
    assert generated.with_suffix(".materialization.json").is_file()
    assert payload["cleanup"]["runtime"]["status"] == "RETAINED_FOR_DIAGNOSIS"
    assert reliability_module._subresult_checksum_valid(subroot, expected_binding)
    assert not _subresult_reusable(subroot, expected_binding)
    assert outcome["cleanup"]["retained_bytes"] > 0


@pytest.mark.parametrize("harness_status", ["PASS", "FAIL"])
def test_reliability_cleanup_reuses_success_and_retains_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness_status: str,
) -> None:
    job, _protocol = _planned_job("reliability")
    tuning = H2RuntimeTuning(product_mode=H2ProductMode.SESSION_MEMORY_ENHANCED)
    source_audio = tmp_path / "source.wav"
    source_audio.write_bytes(b"fixture")
    plan = {
        "sources": [
            {
                "source_recording_id": "source",
                "source_case_id": "sealed",
                "source_audio_identity": "2" * 64,
            }
        ]
    }
    calls: list[str] = []

    monkeypatch.setattr(reliability_module, "H2_RELIABILITY_FAULTS", ("fault",))
    monkeypatch.setattr(reliability_module, "_resolve_source", lambda _row: source_audio)

    def run_fault(_fault: object, **kwargs: object) -> dict[str, object]:
        calls.append("fault")
        runtime = Path(str(kwargs["output_root"]))
        runtime.mkdir(parents=True, exist_ok=True)
        (runtime / "diagnostic.bin").write_bytes(b"runtime-evidence")
        return {
            "harness_status": harness_status,
            "fault_injected": True,
            "unsupported_reason": None,
            "error": None if harness_status == "PASS" else "fixture failure",
            "injection": {},
            "device_inventory": [],
            "observed_completion_states": [
                "complete" if harness_status == "PASS" else "failed"
            ],
            "assertions": [
                {
                    "assertion_id": "fixture",
                    "status": harness_status,
                    "expected": "PASS",
                    "observed": harness_status,
                }
            ],
        }

    monkeypatch.setattr(
        reliability_module.shared_execution,
        "run_reliability_fault",
        run_fault,
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_evidence",
        lambda *_args, **_kwargs: {"fixture": True},
    )
    monkeypatch.setattr(
        reliability_module,
        "_runtime_tuning_evidence",
        lambda *_args, **_kwargs: {"status": "PASS"},
    )
    binding = {"execution_binding_sha256": "d" * 64}
    root = tmp_path / f"reliability-{harness_status.casefold()}"

    outcome = reliability_module._execute_reliability_matrix(
        default_paths(),
        job,
        binding=binding,
        tuning=tuning,
        source_plan=plan,
        result_root=root,
        stop_event=threading.Event(),
        runtime_builder=None,
        progress=None,
        storage_reserve_callback=lambda: None,
    )

    subroot = root / "reliability/fault"
    runtime = subroot / "attempts/attempt_001/runtime/diagnostic.bin"
    expected_binding = reliability_module._subbinding(
        binding, "reliability", "fault"
    )
    assert reliability_module._subresult_checksum_valid(subroot, expected_binding)
    if harness_status == "PASS":
        assert outcome["status"] == "COMPLETE"
        assert not runtime.exists()
        second = reliability_module._execute_reliability_matrix(
            default_paths(),
            job,
            binding=binding,
            tuning=tuning,
            source_plan=plan,
            result_root=root,
            stop_event=threading.Event(),
            runtime_builder=None,
            progress=None,
            storage_reserve_callback=lambda: None,
        )
        assert second["status"] == "COMPLETE"
        assert calls == ["fault"]
        assert _subresult_reusable(subroot, expected_binding)
    else:
        assert outcome["status"] == "FAILED"
        assert runtime.read_bytes() == b"runtime-evidence"
        assert not _subresult_reusable(subroot, expected_binding)
