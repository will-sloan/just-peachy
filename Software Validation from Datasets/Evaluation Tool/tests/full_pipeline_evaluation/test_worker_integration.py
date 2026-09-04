from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import threading
import time
from types import SimpleNamespace
import wave

import numpy as np
import pytest
import soundfile as sf

from app.full_pipeline.factory import (
    _ensure_warmup_audio,
    _resolve_worker_warmup_audio,
)
from app.full_pipeline.models import EmbeddingResult, EmbeddingWindow
from app.full_pipeline_development import shared_execution
from app.full_pipeline_development.shared_execution import SharedWorkerPool
from app.full_pipeline_evaluation.metrics import (
    build_metric_report,
    computed_metric,
    unsupported_metric,
)
from app.full_pipeline_evaluation.planning import matrix
from app.full_pipeline_evaluation.schema import normalize_reuse_identity
from app.full_pipeline_evaluation.store import EvaluationJobSpec
from app.full_pipeline_evaluation.worker import (
    _FrozenGalleryPreparer,
    PreparedGallery,
    _aggregate_recording_reports,
    _enrich_event,
    _hydrate_case,
    _identity_intervals,
    _load_protocol_context,
    _maximum_queue_depth,
    _queue_backpressure_evidence,
    _prepare_runtime_audio,
    _reference_reentry_episodes,
    _require_declared_prerequisites,
    _run_runtime_with_stop,
    _score_isolated_case_views,
    _speaker_transcription_scoring_inputs,
    _selected_protocol_reference_artifacts,
    execute_evaluation_job,
)


def _jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _controlled_context(tmp_path: Path) -> tuple[dict[str, object], object]:
    split_root = tmp_path / "development"
    reference = {
        "source_reference_id": "source:case",
        "partition": "development",
        "speaker_attributed_transcript_status": "supported",
        "segments": [
            {
                "start_sec": 0.0,
                "end_sec": 1.0,
                "reference_speaker": "SPK00",
                "global_speaker_id": "global-a",
                "scorable_transcript": "hello there",
            }
        ],
    }
    overlay = {
        "identity_overlay_ref": "source:case:known",
        "partition": "development",
        "enrollment_database": [{"enrolled_id": "enrolled-a"}],
        "speaker_states": {
            "global-a": {
                "identity_state": "KNOWN",
                "enrolled_id": "enrolled-a",
                "unknown_reference_id": None,
            }
        },
    }
    enrollment = {
        "enrolled_id": "enrolled-a",
        "partition": "development",
        "global_speaker_id": "global-a",
        "reserved_enrollment_clips": [],
    }
    _jsonl(split_root / "references/speaker_attributed_transcript.jsonl", [reference])
    _jsonl(split_root / "identity/identity_overlays.jsonl", [overlay])
    _jsonl(split_root / "enrollment/enrollment_registry.jsonl", [enrollment])
    rttm = tmp_path / "case.rttm"
    rttm.write_text(
        "SPEAKER source-case 1 0.000000 1.000000 <NA> <NA> SPK00 <NA> <NA>\n",
        encoding="utf-8",
    )
    uem = tmp_path / "case.uem"
    uem.write_text("source-case 1 0.000000 1.000000\n", encoding="utf-8")
    case = {
        "protocol_case_id": "protocol-case",
        "source_case_id": "source-case",
        "partition": "development",
        "source_reference_id": "source:case",
        "identity_overlay_ref": "source:case:known",
        "gallery_enrolled_ids": ["enrolled-a"],
        "duration_sec": 1.0,
        "local_to_global_speaker": {"SPK00": "global-a"},
        "reference_rttm_logical_path": str(rttm),
        "reference_rttm_sha256": _sha(rttm),
        "reference_uem_logical_path": str(uem),
        "reference_uem_sha256": _sha(uem),
        "supported_views": [
            "asr",
            "diarization",
            "identity",
            "speaker_attributed_transcript",
        ],
    }
    context = _load_protocol_context("development", [case], protocol_root=tmp_path)
    return case, context


def test_controlled_case_hydrates_exact_split_registries_rttm_and_uem(
    tmp_path: Path,
) -> None:
    case, context = _controlled_context(tmp_path)

    science = _hydrate_case(case, context)
    _require_declared_prerequisites(case, science)

    assert science["reference_text"] == "hello there"
    assert science["diarization_segments"] == [
        {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "SPK00"}
    ]
    assert science["uem"] == [(0.0, 1.0)]
    assert science["speaker_texts"] == {"global-a": "hello there"}
    artifacts = _selected_protocol_reference_artifacts([case], context)
    assert set(artifacts) == {
        "references/selected_speaker_attributed_transcripts.jsonl",
        "references/selected_identity_overlays.jsonl",
        "references/selected_enrollment_registry.jsonl",
    }
    assert b"enrolled-a" in artifacts["references/selected_enrollment_registry.jsonl"]


def test_h2_speaker_transcription_adapter_scores_visible_labels_without_oracle_text_mapping() -> (
    None
):
    case = {
        "events": [],
        "reference_segments": [
            {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "SPK00"},
            {"start_sec": 1.0, "end_sec": 2.0, "speaker_id": "SPK01"},
        ],
        "hypothesis_segments": [
            {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "anon-a"},
            {"start_sec": 1.0, "end_sec": 2.0, "speaker_id": "anon-b"},
        ],
        "uem": [(0.0, 2.0)],
        "attribution_intervals": [],
        "reference_speaker_texts": {
            "global-a": "hello",
            "global-b": "world",
        },
        "hypothesis_speaker_texts": {
            "anon-a": "hello",
            "anon-b": "world",
        },
        "reference_transcript_segments": [
            {
                "start_sec": 0.0,
                "end_sec": 1.0,
                "reference_speaker": "SPK00",
                "global_speaker_id": "global-a",
                "scorable_transcript": "hello",
            },
            {
                "start_sec": 1.0,
                "end_sec": 2.0,
                "reference_speaker": "SPK01",
                "global_speaker_id": "global-b",
                "scorable_transcript": "world",
            },
        ],
        "hypothesis_transcript_spans": [
            {
                "span_id": "span-a",
                "start_sec": 0.0,
                "end_sec": 1.0,
                "text": "hello",
                "anonymous_speaker_id": "anon-a",
                "speaker_label": "Speaker_1",
            },
            {
                "span_id": "span-b",
                "start_sec": 1.0,
                "end_sec": 2.0,
                "text": "world",
                "anonymous_speaker_id": "anon-b",
                "speaker_label": "enrolled-b",
            },
        ],
        "local_to_global_speaker": {
            "SPK00": "global-a",
            "SPK01": "global-b",
        },
        "identity_overlay": {
            "speaker_states": {
                "global-a": {
                    "identity_state": "UNKNOWN",
                    "unknown_reference_id": "unknown-a",
                },
                "global-b": {
                    "identity_state": "KNOWN",
                    "enrolled_id": "enrolled-b",
                },
            }
        },
        "speaker_transcript_supported": True,
    }

    report = _score_isolated_case_views([case], all_cases_complete=True)[
        "speaker_transcription"
    ]

    assert report["cpwer"].value == 0.0
    assert report["speaker_attributed_wer"].value == 0.0
    assert report["word_speaker_label_accuracy"].value == 1.0
    assert report["correct_transcribed_attributed_word_rate"].value == 1.0
    assert report["wrong_speaker_word_count"].value == 0
    assert report["wrong_speaker_word_time_sec"].status == "unsupported"
    assert report["retroactive_correction_count"].value == 0


def test_word_alignment_is_withheld_for_cross_speaker_overlap() -> None:
    inputs = _speaker_transcription_scoring_inputs(
        {
            "reference_transcript_segments": [
                {
                    "start_sec": 0.0,
                    "end_sec": 1.0,
                    "global_speaker_id": "global-a",
                    "scorable_transcript": "hello",
                },
                {
                    "start_sec": 0.5,
                    "end_sec": 1.5,
                    "global_speaker_id": "global-b",
                    "scorable_transcript": "world",
                },
            ],
            "hypothesis_transcript_spans": [
                {
                    "start_sec": 0.0,
                    "end_sec": 1.5,
                    "text": "hello world",
                    "speaker_label": None,
                }
            ],
            "local_to_global_speaker": {},
            "identity_overlay": None,
        },
        {},
    )

    assert inputs["word_alignments"] is None
    assert inputs["word_alignment_id"] is None


def test_controlled_gallery_must_belong_to_selected_overlay(tmp_path: Path) -> None:
    case, _ = _controlled_context(tmp_path)
    overlay_path = tmp_path / "development/identity/identity_overlays.jsonl"
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    overlay["enrollment_database"] = []
    _jsonl(overlay_path, [overlay])

    with pytest.raises(KeyError, match="gallery is absent from overlay"):
        _load_protocol_context("development", [case], protocol_root=tmp_path)


def test_native_references_translate_absolute_offsets_to_excerpt_time(
    tmp_path: Path,
) -> None:
    split_root = tmp_path / "evaluation"
    _jsonl(split_root / "references/speaker_attributed_transcript.jsonl", [])
    _jsonl(split_root / "identity/identity_overlays.jsonl", [])
    _jsonl(split_root / "enrollment/enrollment_registry.jsonl", [])
    transcript = tmp_path / "transcript.jsonl"
    _jsonl(
        transcript,
        [
            {
                "evaluation_unit_id": "native-1",
                "start_sec": 100.25,
                "end_sec": 101.25,
                "speaker_label": "ref-a",
                "text": "native words",
                "full_reference_segment": True,
            }
        ],
    )
    rttm = tmp_path / "native.rttm"
    rttm.write_text(
        "SPEAKER native-1 1 100.250000 1.000000 <NA> <NA> ref-a <NA> <NA>\n",
        encoding="utf-8",
    )
    uem = tmp_path / "native.uem"
    uem.write_text("native-1 1 100.000000 102.000000\n", encoding="utf-8")
    case = {
        "protocol_case_id": "diag-native-1",
        "source_case_id": "native-1",
        "partition": "evaluation",
        "source_reference_id": None,
        "identity_overlay_ref": None,
        "source_start_sec": 100.0,
        "source_end_sec": 102.0,
        "duration_sec": 2.0,
        "reference_transcripts_logical_path": str(transcript),
        "reference_rttm_logical_path": str(rttm),
        "reference_uem_logical_path": str(uem),
        "supported_views": ["asr", "diarization", "speaker_attributed_transcript"],
    }
    context = _load_protocol_context("evaluation", [case], protocol_root=tmp_path)

    science = _hydrate_case(case, context)

    assert science["reference_text"] == "native words"
    assert science["diarization_segments"] == [
        {"start_sec": 0.25, "end_sec": 1.25, "speaker_id": "ref-a"}
    ]
    assert science["uem"] == [(0.0, 2.0)]


def test_native_runtime_input_is_exact_declared_excerpt(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    with wave.open(str(source), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(b"\x01\x00" * 48_000)

    excerpt = _prepare_runtime_audio(
        source,
        {
            "protocol_case_id": "native",
            "source_start_sec": 1.0,
            "source_end_sec": 2.25,
        },
        tmp_path / "runtime",
    )

    assert excerpt != source
    assert sf.info(excerpt).frames == 20_000


def test_native_runtime_input_crops_excerpt_starting_at_zero(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    with wave.open(str(source), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(b"\x01\x00" * 48_000)

    excerpt = _prepare_runtime_audio(
        source,
        {
            "protocol_case_id": "native-zero-origin",
            "source_start_sec": 0.0,
            "source_end_sec": 1.25,
        },
        tmp_path / "runtime",
    )

    assert excerpt != source
    assert sf.info(excerpt).frames == 20_000


def test_multi_recording_scoring_never_flattens_restarted_time_or_labels() -> None:
    cases = []
    for case_id, reference_speaker, word in (
        ("case-a", "ref-a", "hello"),
        ("case-b", "ref-b", "world"),
    ):
        cases.append(
            {
                "case_id": case_id,
                "events": [],
                "streaming_references": {},
                "reference_segments": [
                    {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": reference_speaker}
                ],
                "hypothesis_segments": [
                    {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "anon-1"}
                ],
                "uem": [(0.0, 1.0)],
                "attribution_intervals": [
                    {
                        "start_sec": 0.0,
                        "end_sec": 1.0,
                        "reference_speaker_id": f"enrolled-{case_id}",
                        "reference_is_known": True,
                        "predicted_speaker_id": f"enrolled-{case_id}",
                        "decision_state": "confirmed_known",
                        "episode_id": f"{case_id}:episode",
                    }
                ],
                "reference_speaker_texts": {reference_speaker: word},
                "hypothesis_speaker_texts": {"anon-1": word},
                "speaker_transcript_supported": True,
            }
        )

    reports = _score_isolated_case_views(cases, all_cases_complete=True)

    assert reports["diarization"]["der"].value == 0.0
    assert reports["identity"]["correctly_named_known_rate"].value == 1.0
    assert reports["speaker_transcription"]["cpwer"].value == 0.0
    assert reports["diarization"]["der"].details["aggregation"] == (
        "per_recording_sufficient_statistics.v1"
    )


def test_worker_derives_cold_warm_and_reentry_without_reference_leakage() -> None:
    references = [
        {"start_sec": 0.0, "end_sec": 1.0, "speaker_id": "SPK00"},
        {"start_sec": 1.0, "end_sec": 1.5, "speaker_id": "SPK00"},
        {"start_sec": 2.0, "end_sec": 3.0, "speaker_id": "SPK00"},
    ]
    hypotheses = [
        {"start_sec": 0.0, "end_sec": 1.5, "speaker_id": "anon-a"},
        {"start_sec": 2.0, "end_sec": 3.0, "speaker_id": "anon-b"},
    ]
    events = [
        {
            "event_type": "identity_label",
            "event_sequence": 1,
            "anonymous_speaker_id": "anon-a",
            "identity_state": "confirmed",
            "speaker_label": {
                "label_kind": "known",
                "enrolled_speaker_id": "enrolled-a",
            },
            "capture_timestamps": {"audio_end_sec": 0.0},
        },
        {
            "event_type": "identity_label",
            "event_sequence": 2,
            "anonymous_speaker_id": "anon-b",
            "identity_state": "confirmed",
            "speaker_label": {
                "label_kind": "known",
                "enrolled_speaker_id": "enrolled-a",
            },
            "capture_timestamps": {"audio_end_sec": 2.0},
        },
    ]
    case = {
        "protocol_case_id": "case-a",
        "local_to_global_speaker": {"SPK00": "global-a"},
    }
    science = {
        "diarization_segments": references,
        "overlay": {
            "speaker_states": {
                "global-a": {
                    "identity_state": "KNOWN",
                    "enrolled_id": "enrolled-a",
                }
            }
        },
    }

    intervals = _identity_intervals(case, science, hypotheses, events)
    reentries = _reference_reentry_episodes(references, hypotheses, case_id="case-a")

    assert [row["temperature"] for row in intervals] == ["cold", "cold", "warm"]
    assert [row["predicted_speaker_id"] for row in intervals] == [
        "enrolled-a",
        "enrolled-a",
        "enrolled-a",
    ]
    assert reentries == [
        {
            "episode_id": "case-a:SPK00:reentry:000000",
            "reference_speaker_id": "SPK00",
            "before_hypothesis_speaker_id": "anon-a",
            "after_hypothesis_speaker_id": "anon-b",
        }
    ]


def test_isolated_scoring_populates_short_turn_reentry_and_warm_identity() -> None:
    case = {
        "case_id": "case-a",
        "events": [],
        "streaming_references": {},
        "reference_segments": [
            {"start_sec": 0.0, "end_sec": 0.4, "speaker_id": "ref-a"},
            {"start_sec": 0.8, "end_sec": 1.2, "speaker_id": "ref-b"},
            {"start_sec": 2.0, "end_sec": 2.4, "speaker_id": "ref-a"},
        ],
        "hypothesis_segments": [
            {"start_sec": 0.0, "end_sec": 0.4, "speaker_id": "anon-a"},
            {"start_sec": 0.8, "end_sec": 1.2, "speaker_id": "anon-b"},
            {"start_sec": 2.0, "end_sec": 2.4, "speaker_id": "anon-a"},
        ],
        "uem": [(0.0, 2.4)],
        "short_turn_max_duration_sec": 0.5,
        "reentry_episodes": [
            {
                "episode_id": "case-a:ref-a:reentry:000000",
                "reference_speaker_id": "ref-a",
                "before_hypothesis_speaker_id": "anon-a",
                "after_hypothesis_speaker_id": "anon-a",
            }
        ],
        "attribution_intervals": [
            {
                "start_sec": 0.0,
                "end_sec": 0.4,
                "reference_speaker_id": "enrolled-a",
                "reference_is_known": True,
                "predicted_speaker_id": "enrolled-a",
                "decision_state": "confirmed_known",
                "episode_id": "case-a:cold",
                "temperature": "cold",
            },
            {
                "start_sec": 2.0,
                "end_sec": 2.4,
                "reference_speaker_id": "enrolled-a",
                "reference_is_known": True,
                "predicted_speaker_id": "enrolled-a",
                "decision_state": "confirmed_known",
                "episode_id": "case-a:warm",
                "temperature": "warm",
            },
        ],
        "speaker_transcript_supported": False,
    }

    reports = _score_isolated_case_views([case], all_cases_complete=True)

    assert reports["diarization"]["short_turn_der"].value == 0.0
    assert reports["diarization"]["short_turn_der_lt_0_5_sec"].value == 0.0
    assert reports["diarization"]["short_turn_der_0_5_to_1_0_sec"].status == (
        "undefined"
    )
    assert reports["diarization"]["short_turn_der_1_0_to_2_0_sec"].status == (
        "undefined"
    )
    assert reports["diarization"]["reentry_accuracy"].value == 1.0
    assert reports["identity"]["cold_identity_accuracy"].value == 1.0
    assert reports["identity"]["warm_identity_accuracy"].value == 1.0


def test_recording_scalar_latency_is_mean_while_counts_remain_additive() -> None:
    latency_reports = [
        build_metric_report(
            "ux",
            [computed_metric("time_to_first_text_sec", value)],
            missing_reason="fixture",
        )
        for value in (1.0, 2.0)
    ]
    count_reports = [
        build_metric_report(
            "ux",
            [computed_metric("transcript_revision_count", value)],
            missing_reason="fixture",
        )
        for value in (1.0, 2.0)
    ]

    latency = _aggregate_recording_reports("ux", latency_reports)
    counts = _aggregate_recording_reports("ux", count_reports)

    assert latency["time_to_first_text_sec"].value == 1.5
    assert latency["time_to_first_text_sec"].denominator == 2.0
    assert counts["transcript_revision_count"].value == 3.0
    assert counts["transcript_revision_count"].denominator is None


def test_conditional_metric_uses_applicable_recordings_and_reports_coverage() -> None:
    reports = [
        build_metric_report(
            "speaker_transcription",
            [computed_metric("cpwer", 0.25, numerator=1, denominator=4)],
            missing_reason="fixture",
        ),
        build_metric_report(
            "speaker_transcription",
            [unsupported_metric("cpwer", "reference scope is not applicable")],
            missing_reason="fixture",
        ),
    ]

    aggregate = _aggregate_recording_reports("speaker_transcription", reports)

    assert aggregate["cpwer"].status == "computed"
    assert aggregate["cpwer"].value == 0.25
    assert aggregate["cpwer"].details["recording_count"] == 2
    assert aggregate["cpwer"].details["applicable_recording_count"] == 1
    assert aggregate["cpwer"].details["unsupported_recording_count"] == 1


def test_missing_queue_telemetry_is_explicit_none() -> None:
    assert _maximum_queue_depth([], {}) is None


def test_nested_runtime_queue_telemetry_preserves_high_water_and_waiting() -> None:
    runtime_metrics = {
        "queue": {
            "policy": "block",
            "maximum_frames": 16,
            "maximum_observed_depth": 16,
            "dropped_frames": 0,
            "blocked_total_sec": 12.5,
            "blocked_max_sec": 0.75,
        }
    }

    assert _maximum_queue_depth([], runtime_metrics) == 16
    assert _queue_backpressure_evidence([], runtime_metrics) == {
        "policy": "block",
        "maximum_frames": 16,
        "maximum_observed_depth": 16,
        "dropped_frames": 0,
        "blocked_total_sec": 12.5,
        "blocked_max_sec": 0.75,
    }


def test_queue_high_water_accepts_nested_event_payload() -> None:
    events = [
        {
            "payload": {
                "queue_depth": 3,
                "queue_backpressure": {"maximum_depth": 7},
            }
        }
    ]

    assert _maximum_queue_depth(events, {}) == 7


def test_stop_watcher_requests_in_case_shutdown() -> None:
    stop = threading.Event()

    class Runtime:
        def __init__(self) -> None:
            self.stop_called = threading.Event()

        def request_stop(self) -> None:
            self.stop_called.set()

        def run(self) -> dict[str, object]:
            assert self.stop_called.wait(2.0)
            return {"completion_state": "stopped"}

    runtime = Runtime()
    timer = threading.Timer(0.05, stop.set)
    timer.start()
    started = time.monotonic()
    try:
        result = _run_runtime_with_stop(runtime, stop.is_set)
    finally:
        timer.cancel()

    assert result["completion_state"] == "stopped"
    assert runtime.stop_called.is_set()
    assert time.monotonic() - started < 1.0


def test_case_shards_resume_without_rerunning_valid_cases_and_only_repair_corrupt(
    tmp_path: Path,
) -> None:
    pipeline_id = "fullpipe_v1_ag_dr_ir"
    selection = matrix().resolve(pipeline_id)
    audio = tmp_path / "fixture.wav"
    sf.write(audio, np.zeros(1600, dtype=np.float32), 16000)
    cases = tuple(
        {
            "case_id": f"case-{index}",
            "partition": "development",
            "source_key": "fixture",
            "duration_sec": 0.1,
            "audio_path": str(audio),
            "audio_sha256": _sha(audio),
            "reference_text": f"word{index}",
            "supported_views": ["asr"],
        }
        for index in range(1, 4)
    )
    reuse = normalize_reuse_identity(
        {
            "program_id": "just_peachy_full_pipeline_program_v1",
            "evaluation_protocol_id": "case_shard_test_v1",
            "evaluation_protocol_sha256": "1" * 64,
            "pipeline_id": pipeline_id,
            "pipeline_config_sha256": selection.pipeline_config_sha256,
            "case_manifest_id": "case_shard_fixture",
            "case_manifest_sha256": "2" * 64,
            "runtime_config_sha256": selection.runtime_config_sha256,
            "partition": "development",
            "seed": 3800,
        }
    )
    job = EvaluationJobSpec(
        job_id="fpjob_case_shard_fixture",
        pipeline_id=pipeline_id,
        protocol_id="case_shard_test_v1",
        split="development",
        source_key="fixture",
        measurement_mode="accuracy",
        seed=3800,
        case_count=3,
        audio_duration_sec=0.3,
        protocol_identity="1" * 64,
        pipeline_identity=selection.pipeline_config_sha256,
        reuse_identity=reuse,
        case_ids=tuple(str(row["case_id"]) for row in cases),
        result_relative_path="jobs/fixture/result",
    )
    calls: list[str] = []
    stop = threading.Event()
    stop_after_first = {"enabled": True}

    class Runtime:
        def __init__(self, *, output_root: Path, session_id: str) -> None:
            self.output_root = output_root
            self.case_id = output_root.name

        def run(self) -> dict[str, object]:
            del self.case_id
            case_id = self.output_root.name
            source = next(row for row in cases if row["case_id"] == case_id)
            calls.append(case_id)
            word = str(source["reference_text"])
            _jsonl(self.output_root / "events/events.jsonl", [])
            self.output_root.joinpath("transcript").mkdir(parents=True, exist_ok=True)
            self.output_root.joinpath("transcript/final_transcript.json").write_text(
                json.dumps(
                    {
                        "spans": [
                            {
                                "start_sec": 0.0,
                                "end_sec": 0.1,
                                "text": word,
                                "anonymous_speaker_id": "Speaker_1",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            _jsonl(self.output_root / "speakers/anonymous.jsonl", [])
            _jsonl(
                self.output_root / "diagnostics/short_turn_decisions.jsonl",
                [
                    {
                        "schema_version": "h2-short-turn-diagnostic.fixture.v1",
                        "decision_id": f"short-{case_id}",
                        "inherited": False,
                    }
                ],
            )
            if stop_after_first["enabled"] and len(calls) == 1:
                stop.set()
            return {"completion_state": "complete", "result_sha256": "a" * 64}

    def runtime_builder(**kwargs: object) -> Runtime:
        return Runtime(
            output_root=Path(str(kwargs["output_root"])),
            session_id=str(kwargs["session_id"]),
        )

    class Gallery:
        def prepare(self, _case: object, _context: object) -> PreparedGallery:
            root = tmp_path / "gallery"
            root.mkdir(exist_ok=True)
            return PreparedGallery(root=root)

        def close(self) -> None:
            pass

    def run_attempt(number: int) -> dict[str, object]:
        return dict(
            execute_evaluation_job(
                job,
                cases,
                tmp_path / f"attempts/{job.job_id}/attempt_{number:03d}/result",
                lambda **_values: None,
                stop.is_set,
                runtime_builder=runtime_builder,
                enrollment_preparer=Gallery(),
                stop_at_case_boundary=True,
            )
        )

    first = run_attempt(1)
    assert first["state"] == "stopped"
    assert calls == ["case-1"]
    first_case_root = (
        tmp_path / f"attempts/{job.job_id}/attempt_001/runtime_cases/case-1"
    )
    assert not first_case_root.exists()
    # Simulate a process exit after the shard was durable but before cleanup.
    # The next attempt must remove this old completed tree without rerunning it.
    first_case_root.mkdir(parents=True)
    first_case_root.joinpath("probe-cache.bin").write_bytes(b"regenerable")

    stop.clear()
    stop_after_first["enabled"] = False
    calls.clear()
    second = run_attempt(2)
    assert second["state"] == "complete"
    assert calls == ["case-2", "case-3"]
    assert not first_case_root.exists()
    for case_id in ("case-1", "case-2", "case-3"):
        assert not (
            tmp_path / f"attempts/{job.job_id}/attempt_002/runtime_cases/{case_id}"
        ).exists()
    aggregate_before = _sha(
        tmp_path
        / f"attempts/{job.job_id}/attempt_002/result/diagnostics/per_case_metrics.jsonl"
    )
    short_turn_aggregate = (
        tmp_path
        / f"attempts/{job.job_id}/attempt_002/result/diagnostics/short_turn_decisions.jsonl"
    )
    short_turn_before = _sha(short_turn_aggregate)
    assert {
        row["decision_id"]
        for row in (
            json.loads(line)
            for line in short_turn_aggregate.read_text(encoding="utf-8").splitlines()
        )
    } == {"short-case-1", "short-case-2", "short-case-3"}

    shard = tmp_path / f"attempts/{job.job_id}/case_shards_v1/case-1/case_shard.json"
    value = json.loads(shard.read_text(encoding="utf-8"))
    value["payload"]["cache_hits"] = 999
    shard.write_text(json.dumps(value), encoding="utf-8")
    calls.clear()
    third = run_attempt(3)

    assert third["state"] == "complete"
    assert calls == ["case-1"]
    assert aggregate_before == _sha(
        tmp_path
        / f"attempts/{job.job_id}/attempt_003/result/diagnostics/per_case_metrics.jsonl"
    )
    assert short_turn_before == _sha(
        tmp_path
        / f"attempts/{job.job_id}/attempt_003/result/diagnostics/short_turn_decisions.jsonl"
    )


def test_case_storage_reserve_blocks_before_next_missing_case(
    tmp_path: Path,
) -> None:
    # The shard validator/storage callback interaction is covered by the full
    # three-case restart test above. This focused callback assertion proves a
    # reserve failure happens before constructing a runtime for a missing case.
    blocked = RuntimeError("35 GiB reserve violated")
    constructions = 0

    def reserve() -> None:
        raise blocked

    class NeverConstructed:
        pass

    def builder(**_kwargs: object) -> NeverConstructed:
        nonlocal constructions
        constructions += 1
        return NeverConstructed()

    pipeline_id = "fullpipe_v1_ag_dr_ir"
    selection = matrix().resolve(pipeline_id)
    audio = tmp_path / "storage.wav"
    sf.write(audio, np.zeros(1600, dtype=np.float32), 16000)
    case = {
        "case_id": "storage-case",
        "partition": "development",
        "source_key": "fixture",
        "duration_sec": 0.1,
        "audio_path": str(audio),
        "audio_sha256": _sha(audio),
        "reference_text": "word",
        "supported_views": ["asr"],
    }
    reuse = normalize_reuse_identity(
        {
            "program_id": "just_peachy_full_pipeline_program_v1",
            "evaluation_protocol_id": "storage_test_v1",
            "evaluation_protocol_sha256": "1" * 64,
            "pipeline_id": pipeline_id,
            "pipeline_config_sha256": selection.pipeline_config_sha256,
            "case_manifest_id": "storage_fixture",
            "case_manifest_sha256": "2" * 64,
            "runtime_config_sha256": selection.runtime_config_sha256,
            "partition": "development",
            "seed": 3800,
        }
    )
    job = EvaluationJobSpec(
        job_id="fpjob_storage_fixture",
        pipeline_id=pipeline_id,
        protocol_id="storage_test_v1",
        split="development",
        source_key="fixture",
        measurement_mode="accuracy",
        seed=3800,
        case_count=1,
        audio_duration_sec=0.1,
        protocol_identity="1" * 64,
        pipeline_identity=selection.pipeline_config_sha256,
        reuse_identity=reuse,
        case_ids=("storage-case",),
        result_relative_path="jobs/storage/result",
    )

    result = execute_evaluation_job(
        job,
        (case,),
        tmp_path / "attempts/fpjob_storage_fixture/attempt_001/result",
        lambda **_values: None,
        lambda: False,
        runtime_builder=builder,
        stop_at_case_boundary=True,
        storage_reserve_callback=reserve,
    )

    assert result["state"] == "stopped"
    assert result["completed_cases"] == 0
    assert constructions == 0


def test_retry_lazy_worker_warmup_survives_first_case_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempt_root = tmp_path / "attempts/fpjob-fixture/attempt_002"
    stable_audio = _ensure_warmup_audio(attempt_root / "shared_runtime_work")
    starts: list[Path] = []

    class Worker:
        def __init__(self, spec: object) -> None:
            self.spec = spec

        def start(self) -> dict[str, object]:
            request = dict(self.spec.warmup_request or {})
            path = Path(str(request["audio_path"])).resolve()
            assert path == stable_audio
            assert path.is_file()
            assert (
                hashlib.sha256(path.read_bytes()).hexdigest() == request["audio_sha256"]
            )
            starts.append(path)
            return {
                "component_id": self.spec.component_id,
                "config_sha256": "b" * 64,
            }

        def call(
            self, operation: str, _payload: object, **_kwargs: object
        ) -> dict[str, object]:
            assert operation == "embed"
            identity = {
                "component_id": self.spec.component_id,
                "config_sha256": "b" * 64,
            }
            return {
                "identity": identity,
                "embedding": {
                    "vector": [0.0, 1.0],
                    "status": "ok",
                    "dimension": 2,
                },
                "worker_wall_sec": 0.0,
            }

        def status(self) -> dict[str, object]:
            return {"component_id": self.spec.component_id}

        def shutdown(self) -> None:
            pass

    class FirstHitThenMissCache:
        def __init__(self) -> None:
            self.loads = 0
            self.published = 0

        def load(self, _key: object) -> dict[str, object] | None:
            self.loads += 1
            if self.loads == 1:
                return {
                    "vector": [1.0, 0.0],
                    "status": "ok",
                    "dimension": 2,
                    "worker_wall_sec": 0.0,
                }
            return None

        def publish(self, _key: object, _payload: object) -> None:
            self.published += 1

    monkeypatch.setattr(shared_execution, "PersistentWorker", Worker)
    pool = SharedWorkerPool("retry-fixture")
    selection = SimpleNamespace(
        identity={
            "backend_id": "wespeaker",
            "config_sha256": "b" * 64,
            "model_id": "fixture-wespeaker",
            "model_identity_sha256": "c" * 64,
        }
    )
    preparer = _FrozenGalleryPreparer(
        selection=selection,
        attempt_root=attempt_root,
        worker_pool=pool,
        lazy_worker_start=True,
        worker_warmup_audio_path=stable_audio,
    )
    adapter = preparer._embedding_adapter()
    cache = FirstHitThenMissCache()
    adapter.cache = cache

    first = EmbeddingWindow(
        window_id="first-case-cache-hit",
        start_sec=0.0,
        end_sec=1.0,
        assignment_start_sec=0.0,
        assignment_end_sec=1.0,
        samples=np.zeros(16_000, dtype=np.float32),
        role="enrollment",
    )
    assert adapter.embed(first).vector.tolist() == [1.0, 0.0]
    assert starts == []

    first_case_root = attempt_root / "runtime_cases/fspcase-first"
    (first_case_root / "runtime_work").mkdir(parents=True)
    shutil.rmtree(first_case_root)
    assert not first_case_root.exists()
    assert stable_audio.is_file()
    assert (
        _resolve_worker_warmup_audio(
            work_root=attempt_root / "runtime_cases/fspcase-second/runtime_work",
            worker_warmup_audio_path=stable_audio,
        )
        == stable_audio
    )

    second = EmbeddingWindow(
        window_id="later-case-cache-miss",
        start_sec=0.0,
        end_sec=1.0,
        assignment_start_sec=0.0,
        assignment_end_sec=1.0,
        samples=np.ones(16_000, dtype=np.float32),
        role="enrollment",
    )
    assert adapter.embed(second).vector.tolist() == [0.0, 1.0]
    assert starts == [stable_audio]
    assert cache.published == 1
    preparer.close()
    pool.close()


def test_frozen_gallery_profiles_reopen_with_identical_identity_on_restart(
    tmp_path: Path,
) -> None:
    audio = tmp_path / "enrollment.wav"
    sf.write(audio, np.ones(16_000, dtype=np.float32) * 0.05, 16_000)
    audio_sha = _sha(audio)
    selection = SimpleNamespace(
        identity={
            "backend_id": "redimnet2_b2_speaker_embedding",
            "config_sha256": "b" * 64,
            "model_id": "ReDimNet2-B2",
            "model_identity_sha256": "c" * 64,
        },
        enrollment_policy={
            "policy_id": "fixture-enrollment",
            "sha256": "d" * 64,
            "utterance_count": 1,
            "aggregation": "normalized_mean",
        },
    )
    context = SimpleNamespace(
        enrollments={
            "enrolled-a": {
                "enrolled_id": "enrolled-a",
                "global_speaker_id": "speaker-a",
                "reserved_enrollment_clips": [
                    {
                        "source_clip_id": "clip-a",
                        "logical_audio_path": str(audio),
                        "source_audio_sha256": audio_sha,
                    }
                ],
            }
        }
    )
    case = {"gallery_enrolled_ids": ["enrolled-a"]}

    class Adapter:
        def __init__(self, *, fail: bool = False) -> None:
            self.fail = fail
            self.calls = 0

        def embed(self, window: EmbeddingWindow) -> EmbeddingResult:
            if self.fail:
                raise AssertionError("restart attempted to re-embed enrollment")
            self.calls += 1
            return EmbeddingResult(
                window_id=window.window_id,
                backend_id="redimnet2_b2_speaker_embedding",
                model_id="ReDimNet2-B2",
                model_sha256="c" * 64,
                vector=np.asarray([1.0, 0.0], dtype=np.float32),
                duration_sec=1.0,
                role=window.role,
                quality={"status": "accepted"},
            )

        def close(self) -> None:
            pass

    root = tmp_path / "shared-gallery"
    first = _FrozenGalleryPreparer(selection=selection, attempt_root=root)
    first_adapter = Adapter()
    first._adapter = first_adapter
    prepared_first = first.prepare(case, context)
    first.close()
    assert first_adapter.calls == 1

    restarted = _FrozenGalleryPreparer(selection=selection, attempt_root=root)
    restarted_adapter = Adapter(fail=True)
    restarted._adapter = restarted_adapter
    prepared_restarted = restarted.prepare(case, context)
    restarted.close()

    assert restarted_adapter.calls == 0
    assert prepared_first.profiles == prepared_restarted.profiles
    assert prepared_first.profiles[0]["profile_sha256"]


def test_capture_time_is_not_overwritten_as_emission_elapsed_time() -> None:
    event = _enrich_event(
        {
            "event_type": "asr_final",
            "event_id": "evt-1",
            "hypothesis_id": "hyp-1",
            "capture_timestamps": {"audio_end_sec": 2.0},
            "processing_timestamps": {"emitted_monotonic_ns": 5_000_000_000},
        },
        "case-a",
    )

    assert "stream_elapsed_sec" not in event
    assert event["capture_timestamps"] == {"audio_end_sec": 2.0}
    assert event["hypothesis_id"] == "case-a:hyp-1"


def test_declared_supported_view_cannot_complete_without_reference() -> None:
    try:
        _require_declared_prerequisites(
            {"protocol_case_id": "missing", "supported_views": ["asr"]},
            {"reference_text": ""},
        )
    except ValueError as exc:
        assert "ASR transcript" in str(exc)
    else:  # pragma: no cover - assertion guard
        raise AssertionError("missing declared prerequisite was accepted")
