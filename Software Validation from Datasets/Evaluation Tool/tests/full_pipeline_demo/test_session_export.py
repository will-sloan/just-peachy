from __future__ import annotations

import hashlib
import json
from pathlib import Path
import threading

import pytest

from app.full_pipeline_demo.exports import ExportSafetyError, export_session
from app.full_pipeline_demo.session import (
    CoalescingUpdateBuffer,
    DemoSessionManager,
    JsonlEventCursor,
)


def _json_line(sequence: int, contract: str = "AsrPartialEvent") -> bytes:
    return (
        json.dumps(
            {
                "event_sequence": sequence,
                "contract_type": contract,
                "hypothesis_id": "hypothesis-1",
                "text": f"text-{sequence}",
            },
            separators=(",", ":"),
        ).encode("utf-8")
        + b"\n"
    )


def test_jsonl_cursor_preserves_partial_line_and_reconnects(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    second = _json_line(2)
    path.write_bytes(_json_line(1) + second[:8])
    cursor = JsonlEventCursor(path)

    assert [value["event_sequence"] for value in cursor.read_available()] == [1]
    with path.open("ab") as stream:
        stream.write(second[8:])
    assert [value["event_sequence"] for value in cursor.read_available()] == [2]

    reconnect = JsonlEventCursor.from_token(path, cursor.token())
    assert reconnect.read_available() == []
    with path.open("ab") as stream:
        stream.write(_json_line(3))
    assert [value["event_sequence"] for value in reconnect.read_available()] == [3]
    replay = JsonlEventCursor(path, after_sequence=2)
    assert [value["event_sequence"] for value in replay.read_available()] == [3]


class _FakeRuntime:
    def __init__(self, output_root: Path) -> None:
        self.output_root = Path(output_root)
        self.started = threading.Event()
        self.done = threading.Event()
        self.paused = False
        self.stop_requested = False
        self.control_calls: list[tuple[str, bool]] = []

    def run(self) -> dict[str, object]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        events = self.output_root / "events/events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        events.write_bytes(_json_line(1))
        self.started.set()
        self.done.wait(timeout=5)
        completion = "stopped" if self.stop_requested else "complete"
        result = {
            "completion_state": completion,
            "session_id": self.output_root.name,
            "errors": [],
        }
        (self.output_root / "result.json").write_text(json.dumps(result), encoding="utf-8")
        return result

    def request_pause(self) -> None:
        self.paused = True

    def request_resume(self) -> None:
        self.paused = False

    def request_stop(self) -> None:
        self.stop_requested = True
        self.done.set()

    def reset_session(self, *, preserve_transcript: bool = True) -> dict[str, object]:
        self.control_calls.append(("reset_session", preserve_transcript))
        return {"reset": True, "preserve_transcript": preserve_transcript}

    def clear_anonymous_memory(
        self, *, preserve_transcript: bool = True
    ) -> dict[str, object]:
        self.control_calls.append(("clear_anonymous_memory", preserve_transcript))
        return {"cleared": True, "preserve_transcript": preserve_transcript}


def test_session_manager_is_nonblocking_and_switches_immutably(tmp_path: Path) -> None:
    runtimes: list[_FakeRuntime] = []
    calls: list[dict[str, object]] = []
    first_built = threading.Event()
    second_built = threading.Event()

    def builder(**kwargs: object) -> _FakeRuntime:
        calls.append(dict(kwargs))
        runtime = _FakeRuntime(Path(kwargs["output_root"]))
        runtimes.append(runtime)
        if len(runtimes) == 1:
            first_built.set()
        if len(runtimes) == 2:
            second_built.set()
        return runtime

    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF-fake")
    manager = DemoSessionManager(
        tmp_path / "runs",
        file_builder=builder,
        microphone_builder=builder,
        pipeline_validator=lambda pipeline_id: {
            "pipeline_id": pipeline_id,
            "pipeline_config_sha256": "a" * 64,
        },
        maximum_ui_updates=8,
    )
    first = manager.start_file(
        pipeline_id="fullpipe_v1_ao_dr_ir",
        input_path=source,
        pace=1.0,
        play_audio=False,
    )
    assert first["state"] in {"queued", "building", "starting"}
    assert manager.active
    assert manager.session_id == first["session_id"]
    assert manager.output_root == Path(str(first["output_root"]))
    assert first_built.wait(timeout=2)
    assert runtimes[0].started.wait(timeout=2)
    manager.pause(str(first["session_id"]))
    assert runtimes[0].paused
    manager.resume(str(first["session_id"]))
    assert not runtimes[0].paused

    second = manager.switch_file(
        pipeline_id="fullpipe_v1_ag_dw_iw",
        input_path=source,
        pace=0.0,
        play_audio=False,
        duration_sec=None,
        telemetry_enabled=False,
        session_id=None,
        output_root=None,
    )
    assert second["session_id"] != first["session_id"]
    assert second["predecessor_session_id"] == first["session_id"]
    manager.join(str(first["session_id"]), timeout=2)
    assert runtimes[0].stop_requested
    assert second_built.wait(timeout=2)
    assert len(runtimes) == 2
    assert runtimes[1].started.wait(timeout=2)
    manager.stop(str(second["session_id"]))
    final = manager.join(str(second["session_id"]), timeout=2)
    assert final["state"] == "stopped"
    assert calls[0]["pipeline_id"] == "fullpipe_v1_ao_dr_ir"
    assert calls[1]["pipeline_id"] == "fullpipe_v1_ag_dw_iw"
    assert calls[0]["output_root"] != calls[1]["output_root"]
    assert manager.poll_events(limit=4)["events"][0]["event_sequence"] == 1


def test_h2_product_mode_and_privacy_controls_reach_exact_runtime(
    tmp_path: Path,
) -> None:
    runtimes: list[_FakeRuntime] = []

    def builder(**kwargs: object) -> _FakeRuntime:
        runtime = _FakeRuntime(Path(kwargs["output_root"]))
        runtimes.append(runtime)
        return runtime

    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF-fake")
    manager = DemoSessionManager(
        tmp_path / "runs",
        file_builder=builder,
        pipeline_validator=lambda pipeline_id: {"pipeline_id": pipeline_id},
    )
    status = manager.start_file(
        pipeline_id="fullpipe_v1_ag_dr_ir",
        product_mode="H2_SESSION_MEMORY_ENHANCED",
        input_path=source,
        pace=0.0,
    )
    assert status["product_mode"] == "H2_SESSION_MEMORY_ENHANCED"
    assert runtimes[0].started.wait(timeout=2)

    cleared = manager.clear_anonymous_memory(str(status["session_id"]))
    assert cleared["session_control"]["permanent_enrollment_profiles_touched"] is False
    assert cleared["session_control"]["automatically_resumed"] is True
    reset = manager.reset_session(
        str(status["session_id"]), preserve_transcript=False
    )
    assert reset["session_control"]["preserve_transcript"] is False
    assert reset["session_control"]["automatically_resumed"] is True
    assert runtimes[0].paused is False
    assert runtimes[0].control_calls == [
        ("clear_anonymous_memory", True),
        ("reset_session", False),
    ]
    manager.stop(str(status["session_id"]))
    manager.join(str(status["session_id"]), timeout=2)

    with pytest.raises(ValueError, match="H2 product demo accepts only"):
        manager.start_file(
            pipeline_id="fullpipe_v1_ag_dr_ie",
            product_mode="H2_SESSION_MEMORY_ENHANCED",
            input_path=source,
        )


def test_switch_after_completed_session_retains_predecessor_without_stopping(
    tmp_path: Path,
) -> None:
    runtimes: list[_FakeRuntime] = []
    built = threading.Event()
    second_built = threading.Event()

    def builder(**kwargs: object) -> _FakeRuntime:
        runtime = _FakeRuntime(Path(kwargs["output_root"]))
        runtimes.append(runtime)
        built.set()
        if len(runtimes) == 2:
            second_built.set()
        return runtime

    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF-fake")
    manager = DemoSessionManager(
        tmp_path / "runs",
        file_builder=builder,
        pipeline_validator=lambda pipeline_id: {"pipeline_id": pipeline_id},
    )
    first = manager.start_file(
        pipeline_id="fullpipe_v1_ag_dr_ie",
        input_path=source,
        pace=0.0,
    )
    assert built.wait(timeout=2)
    assert runtimes[0].started.wait(timeout=2)
    runtimes[0].done.set()
    first_final = manager.join(str(first["session_id"]), timeout=2)
    assert first_final["state"] == "completed"

    second = manager.switch_file(
        pipeline_id="fullpipe_v1_ag_dr_ir",
        input_path=source,
        pace=0.0,
        play_audio=False,
        duration_sec=None,
        telemetry_enabled=False,
        session_id=None,
        output_root=None,
    )

    assert second["predecessor_session_id"] == first["session_id"]
    assert second["pipeline_id"] != first["pipeline_id"]
    assert second["output_root"] != first["output_root"]
    assert runtimes[0].stop_requested is False
    assert second_built.wait(timeout=2)
    assert len(runtimes) == 2
    assert runtimes[1].started.wait(timeout=2)
    manager.stop(str(second["session_id"]))
    manager.join(str(second["session_id"]), timeout=2)


def test_ui_update_buffer_is_bounded_and_reports_resync() -> None:
    buffer = CoalescingUpdateBuffer(maximum_items=4)
    buffer.push({"kind": "status", "status": {"state": "starting"}})
    buffer.push({"kind": "status", "status": {"state": "running"}})
    for sequence in range(1, 6):
        buffer.push(
            {
                "kind": "event",
                "event": {
                    "event_sequence": sequence,
                    "contract_type": "AnonymousSpeakerEvent",
                },
            }
        )
    result = buffer.drain()
    assert len(result["updates"]) == 4
    assert result["dropped_ui_updates"] == 2
    assert result["requires_event_resync"] is True


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path, root: Path) -> dict[str, object]:
    return {
        "logical_path": path.relative_to(root).as_posix(),
        "sha256": _sha(path),
    }


def _make_finished_run(root: Path) -> Path:
    transcript_path = root / "transcript/final_transcript.json"
    events_path = root / "events/events.jsonl"
    identity_evidence_path = root / "speakers/identity_evidence.jsonl"
    telemetry_path = root / "telemetry/resource_samples.jsonl"
    provenance_path = root / "manifests/provenance.json"
    for path in (
        transcript_path,
        events_path,
        identity_evidence_path,
        telemetry_path,
        provenance_path,
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
    transcript = {
        "schema_version": "full-pipeline-final-transcript.v1",
        "spans": [
            {
                "span_id": "span-1",
                "start_sec": 0.0,
                "end_sec": 1.25,
                "speaker_label": "Alice",
                "anonymous_speaker_id": "anon-1",
                "text": "hello there",
                "state": "final",
                "alignment_status": "aligned",
                "timing_provenance": "word",
                "source_event_ids": ["event-1"],
            }
        ],
    }
    transcript_path.write_text(json.dumps(transcript), encoding="utf-8")
    events_path.write_bytes(_json_line(1, "AsrFinalEvent"))
    identity_evidence_path.write_text(
        json.dumps(
            {
                "contract_type": "IdentityEvidenceEvent",
                "anonymous_speaker_id": "anon-1",
                "raw_score": 0.62,
                "score_type": "cosine_similarity",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    telemetry_path.write_text(
        json.dumps({"event_sequence": 2, "contract_type": "ResourceTelemetryEvent"})
        + "\n",
        encoding="utf-8",
    )
    provenance_path.write_text(
        json.dumps({"worker_reported_identities": [{"worker_id": "asr-1"}]}),
        encoding="utf-8",
    )
    session_state = {
        "session_id": "session-1",
        "pipeline_id": "fullpipe_v1_ao_dr_ir",
        "enrollment_profiles": [
            {"profile_id": "profile-1", "profile_sha256": "b" * 64}
        ],
    }
    (root / "session_state.json").write_text(
        json.dumps(session_state), encoding="utf-8"
    )
    result = {
        "session_id": "session-1",
        "pipeline_id": "fullpipe_v1_ao_dr_ir",
        "protocol_version": "full_pipeline_protocol.v1",
        "pipeline_config_sha256": "a" * 64,
        "completion_state": "complete",
        "result_sha256": "c" * 64,
        "component_identities": [
            {"component_family": "asr", "backend_id": "sherpa_onnx"}
        ],
        "warnings": [],
        "errors": [],
        "final_transcript_artifact": _artifact(transcript_path, root),
        "event_log_artifact": _artifact(events_path, root),
        "identity_evidence_artifact": _artifact(identity_evidence_path, root),
        "resource_telemetry_artifact": _artifact(telemetry_path, root),
    }
    (root / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return events_path


def test_export_is_checksum_bound_local_and_audio_requires_authorization(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    original_events = _make_finished_run(run).read_bytes()
    audio = tmp_path / "private.wav"
    audio.write_bytes(b"RIFF-private")

    with pytest.raises(PermissionError):
        export_session(run, tmp_path / "denied", input_audio_path=audio)

    output = tmp_path / "export"
    result = export_session(
        run,
        output,
        input_audio_path=audio,
        authorize_input_audio=True,
    )
    assert result["status"] == "COMPLETE"
    assert (output / "events/events.jsonl").read_bytes() == original_events
    assert (output / "evidence/identity_evidence.jsonl").is_file()
    assert "Alice: hello there" in (
        output / "transcript/labelled_transcript.txt"
    ).read_text("utf-8")
    assert (output / "audio/input.wav").read_bytes() == audio.read_bytes()
    checksums = json.loads((output / "checksums.json").read_text("utf-8"))
    for row in checksums["artifacts"]:
        path = output / row["logical_path"]
        assert path.stat().st_size == row["byte_count"]
        assert _sha(path) == row["sha256"]
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    assert manifest["contains_biometric_vectors"] is False
    assert manifest["protected_enrollment_store_copied"] is False
    assert manifest["input_audio_included_with_user_authorization"] is True
    privacy = {
        row["logical_path"]: row["privacy_classification"]
        for row in manifest["artifacts"]
    }
    assert privacy["transcript/labelled_transcript.jsonl"] == "private"
    assert privacy["events/events.jsonl"] == "biometric_sensitive"
    assert privacy["evidence/identity_evidence.jsonl"] == "biometric_sensitive"
    assert privacy["source/session_state.json"] == "biometric_sensitive"
    assert privacy["manifests/enrollment_profiles.json"] == "biometric_sensitive"
    assert privacy["manifests/pipeline_identity.json"] == "internal"
    assert privacy["manifests/component_identities.json"] == "internal"
    assert privacy["diagnostics/failures.json"] == "private"
    pipeline = json.loads(
        (output / "manifests/pipeline_identity.json").read_text("utf-8")
    )
    components = json.loads(
        (output / "manifests/component_identities.json").read_text("utf-8")
    )
    profiles = json.loads(
        (output / "manifests/enrollment_profiles.json").read_text("utf-8")
    )
    assert pipeline["pipeline_id"] == "fullpipe_v1_ao_dr_ir"
    assert components["component_identities"][0]["backend_id"] == "sherpa_onnx"
    assert profiles["enrollment_profiles"] == [
        {"profile_id": "profile-1", "profile_sha256": "b" * 64}
    ]
    assert profiles["biometric_vectors_inline"] is False


def test_export_rejects_biometric_vectors_in_full_event_log(tmp_path: Path) -> None:
    run = tmp_path / "run"
    events = _make_finished_run(run)
    events.write_text(
        json.dumps(
            {
                "event_sequence": 1,
                "contract_type": "IdentityEvidenceEvent",
                "embedding_vector": [0.1, 0.2],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result_path = run / "result.json"
    result = json.loads(result_path.read_text("utf-8"))
    result["event_log_artifact"] = _artifact(events, run)
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ExportSafetyError, match="biometric vector"):
        export_session(run, tmp_path / "export")


def test_export_rejects_biometric_vectors_in_identity_evidence(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    _make_finished_run(run)
    evidence = run / "speakers/identity_evidence.jsonl"
    evidence.write_text(
        json.dumps(
            {
                "contract_type": "IdentityEvidenceEvent",
                "template_vector": [0.1, 0.2],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    result_path = run / "result.json"
    result = json.loads(result_path.read_text("utf-8"))
    result["identity_evidence_artifact"] = _artifact(evidence, run)
    result_path.write_text(json.dumps(result), encoding="utf-8")

    with pytest.raises(ExportSafetyError, match="biometric vector"):
        export_session(run, tmp_path / "export")


def test_failed_builder_can_export_failure_bundle_without_run_root(
    tmp_path: Path,
) -> None:
    missing_run = tmp_path / "missing-run"
    output = tmp_path / "failed-export"
    result = export_session(
        missing_run,
        output,
        manager_status={
            "state": "failed",
            "session_id": "failed-session",
            "pipeline_id": "fullpipe_v1_ao_dr_ir",
            "pipeline_identity": {
                "pipeline_config_sha256": "a" * 64,
                "protocol_version": "full_pipeline_protocol.v1",
            },
            "failures": [{"stage": "building", "message": "fixture failure"}],
        },
    )
    assert result["status"] == "COMPLETE"
    failure = json.loads(
        (output / "diagnostics/failures.json").read_text("utf-8")
    )
    assert failure["manager_failures"][0]["message"] == "fixture failure"
    manifest = json.loads((output / "manifest.json").read_text("utf-8"))
    assert manifest["session_id"] == "failed-session"
