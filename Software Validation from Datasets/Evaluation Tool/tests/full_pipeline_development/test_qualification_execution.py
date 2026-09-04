from __future__ import annotations

import copy
from dataclasses import dataclass
import gzip
import json
from pathlib import Path

import pytest

from app.full_pipeline_development.qualification_execution import (
    _compare_pipeline_results,
    _semantic_enrollment_profiles,
    _semantic_events,
    _semantic_transcript,
    qualify_component_restarts,
)


@dataclass(frozen=True)
class _Spec:
    component_id: str
    kind: str = "test"
    environment_profile: str = "test"


class _Worker:
    def __init__(self, spec: _Spec) -> None:
        self.spec = spec
        self.restart_count = 0
        self.running = False

    def start(self) -> dict[str, object]:
        self.running = True
        return {"component_id": self.spec.component_id, "identity": "stable"}

    def health(self) -> dict[str, object]:
        return {"status": "HEALTHY", "warmed_up": True}

    def restart(self) -> dict[str, object]:
        self.restart_count += 1
        return self.start()

    def shutdown(self) -> None:
        self.running = False

    def status(self) -> dict[str, object]:
        return {
            "running": self.running,
            "pid": None,
            "restart_count": self.restart_count,
        }


def test_restart_evidence_is_actual_idempotent_and_checksum_bound(
    tmp_path: Path,
) -> None:
    specs = tuple((f"evidence_{index}", _Spec(f"component_{index}")) for index in range(6))

    first = qualify_component_restarts(
        tmp_path, worker_factory=_Worker, specs=specs
    )
    second = qualify_component_restarts(
        tmp_path,
        worker_factory=lambda spec: (_ for _ in ()).throw(AssertionError(spec)),
        specs=specs,
    )

    assert first == second
    assert first["status"] == "PASS"
    assert first["component_count"] == 6
    for row in first["entries"]:
        assert row["status"] == "PASS"
        assert (tmp_path / row["logical_path"]).is_file()


def test_semantic_normalization_ignores_session_ids_and_wall_time_but_keeps_order(
    tmp_path: Path,
) -> None:
    transcript_a = tmp_path / "a_transcript.jsonl"
    transcript_b = tmp_path / "b_transcript.jsonl"
    transcript_a.write_text(
        '{"span_id":"span_a","source_event_ids":["evt_a"],"text":"hello","start_sec":0.0}\n',
        encoding="utf-8",
    )
    transcript_b.write_text(
        '{"span_id":"span_b","source_event_ids":["evt_b"],"text":"hello","start_sec":0.0}\n',
        encoding="utf-8",
    )
    events_a = tmp_path / "a_events.jsonl"
    events_b = tmp_path / "b_events.jsonl.gz"
    events_a.write_text(
        '\n'.join(
            (
                '{"event_id":"evt_a","event_sequence":7,"event_type":"speech_region","session_id":"a","start_sec":0.0}',
                '{"event_id":"telemetry_a","event_type":"resource_telemetry","elapsed_sec":1.0}',
                '{"event_id":"evt_b","event_sequence":9,"event_type":"anonymous_speaker","session_id":"a","anonymous_speaker_id":"anon_0001"}',
            )
        )
        + "\n",
        encoding="utf-8",
    )
    with gzip.open(events_b, "wt", encoding="utf-8") as handle:
        handle.write(
            '\n'.join(
                (
                    '{"event_id":"different_1","event_sequence":1,"event_type":"speech_region","session_id":"b","start_sec":0.0}',
                    '{"event_id":"different_2","event_sequence":2,"event_type":"anonymous_speaker","session_id":"b","anonymous_speaker_id":"anon_0001"}',
                )
            )
            + "\n"
        )

    assert _semantic_transcript(transcript_a) == _semantic_transcript(transcript_b)
    semantic_a, _ = _semantic_events(events_a)
    semantic_b, _ = _semantic_events(events_b)
    assert semantic_a == semantic_b
    assert [row["event_type"] for row in semantic_a] == [
        "speech_region",
        "anonymous_speaker",
    ]


def test_semantic_profiles_ignore_only_run_local_profile_hash() -> None:
    cold = [_profile("a" * 64)]
    shared = [_profile("b" * 64)]

    cold_rows, cold_runtime, cold_semantic = _semantic_enrollment_profiles(cold)
    shared_rows, shared_runtime, shared_semantic = _semantic_enrollment_profiles(shared)

    assert cold_rows == shared_rows
    assert cold_semantic == shared_semantic
    assert cold_runtime != shared_runtime
    for field, value in (
        ("template_sha256", "d" * 64),
        ("backend_id", "changed_backend"),
        ("aggregation_method", "changed_aggregation"),
        ("source_clips", [{"source_clip_id": "changed"}]),
    ):
        changed = copy.deepcopy(shared)
        changed[0][field] = value
        changed_rows, _, changed_semantic = _semantic_enrollment_profiles(changed)
        assert changed_rows != cold_rows
        assert changed_semantic != cold_semantic


def test_semantic_events_validate_and_rebind_runtime_gallery(tmp_path: Path) -> None:
    _, runtime_gallery, semantic_gallery = _semantic_enrollment_profiles(
        [_profile("a" * 64)]
    )
    path = tmp_path / "events.jsonl"
    rows = [
        {
            "event_type": "identity_evidence",
            "event_id": f"event_{index}",
            "enrollment_profile_sha256": runtime_gallery,
            "decision": "accepted_known",
        }
        for index in range(2)
    ]
    _write_jsonl(path, rows)

    semantic, _ = _semantic_events(
        path,
        runtime_gallery_sha256=runtime_gallery,
        semantic_gallery_sha256=semantic_gallery,
    )
    assert [row["enrollment_profile_sha256"] for row in semantic] == [
        semantic_gallery,
        semantic_gallery,
    ]

    rows[1]["enrollment_profile_sha256"] = "f" * 64
    _write_jsonl(path, rows)
    with pytest.raises(RuntimeError, match="gallery differs"):
        _semantic_events(
            path,
            runtime_gallery_sha256=runtime_gallery,
            semantic_gallery_sha256=semantic_gallery,
        )


def test_compare_pipeline_results_accepts_only_run_local_differences(
    tmp_path: Path,
) -> None:
    cold = tmp_path / "cold"
    shared = tmp_path / "shared"
    _write_result(cold, tag="cold", profile_sha256="a" * 64)
    _write_result(shared, tag="shared", profile_sha256="b" * 64, compressed=True)

    summary = _compare_pipeline_results("pipeline", cold, shared, _case())

    assert summary["status"] == "PASS"
    assert summary["semantically_equivalent"] is True
    assert summary["runtime_gallery_sha256s"]["cold"] != summary[
        "runtime_gallery_sha256s"
    ]["shared"]
    assert len(summary["enrollment_profile_semantic_sha256"]) == 64


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        (lambda rows: rows.__setitem__(1, rows[2]), "event sequence differs"),
        (lambda rows: rows[0]["capture_timestamps"].__setitem__("audio_end_sec", 9.0), "event sequence differs"),
        (lambda rows: rows[0]["capture_timestamps"].__setitem__("sample_end_index", 999), "event sequence differs"),
        (lambda rows: rows[3].__setitem__("decision", "rejected_unknown"), "event sequence differs"),
        (lambda rows: rows[3]["candidate_scores"][0].__setitem__("raw_score", 0.1), "event sequence differs"),
    ),
)
def test_compare_pipeline_results_rejects_scientific_event_mutations(
    tmp_path: Path,
    mutation: object,
    message: str,
) -> None:
    cold = tmp_path / "cold"
    shared = tmp_path / "shared"
    _write_result(cold, tag="cold", profile_sha256="a" * 64)
    rows = _events("shared", _runtime_gallery("b" * 64))
    mutation(rows)  # type: ignore[operator]
    _write_result(
        shared,
        tag="shared",
        profile_sha256="b" * 64,
        event_rows=rows,
    )

    with pytest.raises(RuntimeError, match=message):
        _compare_pipeline_results("pipeline", cold, shared, _case())


def test_compare_pipeline_results_rejects_stable_profile_mutation(
    tmp_path: Path,
) -> None:
    cold = tmp_path / "cold"
    shared = tmp_path / "shared"
    _write_result(cold, tag="cold", profile_sha256="a" * 64)
    changed_profile = _profile("b" * 64)
    changed_profile["template_sha256"] = "d" * 64
    _write_result(
        shared,
        tag="shared",
        profile_sha256="b" * 64,
        profile=changed_profile,
    )

    with pytest.raises(RuntimeError, match="enrollment profiles differ"):
        _compare_pipeline_results("pipeline", cold, shared, _case())


def _profile(profile_sha256: str) -> dict[str, object]:
    return {
        "schema_version": "selected-profile.v1",
        "profile_id": "profile_1",
        "profile_sha256": profile_sha256,
        "template_sha256": "c" * 64,
        "backend_id": "test_backend",
        "model_id": "test_model",
        "backend_config_sha256": "d" * 64,
        "aggregation_method": "multi_template_top2_mean",
        "within_enrollment_consistency": 0.9,
        "source_clips": [
            {"source_clip_id": "clip_1", "source_audio_sha256": "e" * 64}
        ],
    }


def _runtime_gallery(profile_sha256: str) -> str:
    return _semantic_enrollment_profiles([_profile(profile_sha256)])[1]


def _events(tag: str, runtime_gallery: str) -> list[dict[str, object]]:
    return [
        {
            "event_type": "audio_frame",
            "event_id": f"{tag}_audio",
            "event_sequence": 1,
            "session_id": tag,
            "capture_timestamps": {
                "audio_start_sec": 0.0,
                "audio_end_sec": 0.1,
                "sample_start_index": 0,
                "sample_end_index": 1600,
                "capture_start_monotonic_ns": 10 if tag == "cold" else 20,
                "capture_end_monotonic_ns": 11 if tag == "cold" else 21,
                "capture_start_utc": f"{tag}_start",
                "capture_end_utc": f"{tag}_end",
                "discontinuity_before": False,
                "dropped_sample_count_before": 0,
            },
        },
        {
            "event_type": "asr_partial",
            "event_id": f"{tag}_native",
            "event_sequence": 2,
            "session_id": tag,
            "adapter_event_type": "native_partial",
            "text": "hello",
        },
        {
            "event_type": "speaker_boundary",
            "event_id": f"{tag}_boundary",
            "event_sequence": 3,
            "session_id": tag,
            "boundary_id": f"{tag}_boundary_1",
            "boundary_time_sec": 0.5,
            "from_anonymous_speaker_id": "anon_1",
            "to_anonymous_speaker_id": "anon_2",
        },
        {
            "event_type": "identity_evidence",
            "event_id": f"{tag}_evidence",
            "event_sequence": 4,
            "session_id": tag,
            "enrollment_profile_id": "gallery:test",
            "enrollment_profile_sha256": runtime_gallery,
            "decision": "accepted_known",
            "top1_raw_score": 0.8,
            "candidate_scores": [
                {"candidate_speaker_id": "known_1", "raw_score": 0.8}
            ],
        },
        {
            "event_type": "identity_label",
            "event_id": f"{tag}_label",
            "event_sequence": 5,
            "session_id": tag,
            "evidence_event_ids": [f"{tag}_evidence"],
            "identity_state": "confirmed",
            "speaker_label": {
                "display_label": "known_1",
                "enrolled_speaker_id": "known_1",
                "label_kind": "known",
            },
        },
        {
            "event_type": "pipeline_status",
            "event_id": f"{tag}_complete",
            "event_sequence": 6,
            "session_id": tag,
            "pipeline_state": "completed",
            "pipeline_id": "pipeline",
            "recording_id": "recording",
            "errors": [],
            "warnings": [],
        },
    ]


def _write_result(
    root: Path,
    *,
    tag: str,
    profile_sha256: str,
    compressed: bool = False,
    event_rows: list[dict[str, object]] | None = None,
    profile: dict[str, object] | None = None,
) -> None:
    _write_json(root / "checksums.json", {})
    _write_json(root / "run.json", {"status": "complete", "errors": [], "run_id": tag})
    _write_json(
        root / "pipeline_identity.json",
        {
            "pipeline_config_sha256": "f" * 64,
            "environment_identities": ["test"],
        },
    )
    _write_json(root / "model_assets.json", {"run_id": tag, "assets": []})
    _write_jsonl(
        root / "predictions/labelled_transcript.jsonl",
        [
            {
                "span_id": f"{tag}_span",
                "source_event_ids": [f"{tag}_native"],
                "text": "hello",
                "start_sec": 0.0,
                "end_sec": 0.5,
            }
        ],
    )
    _write_jsonl(
        root / "references/selected_enrollment_profiles.jsonl",
        [profile or _profile(profile_sha256)],
    )
    rows = event_rows or _events(tag, _runtime_gallery(profile_sha256))
    event_path = root / ("events.jsonl.gz" if compressed else "events.jsonl")
    event_path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    if compressed:
        with gzip.open(event_path, "wt", encoding="utf-8") as handle:
            handle.write(text)
    else:
        event_path.write_text(text, encoding="utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _case() -> dict[str, object]:
    return {"case_id": "case", "audio_sha256": "a" * 64, "duration_sec": 1.0}
