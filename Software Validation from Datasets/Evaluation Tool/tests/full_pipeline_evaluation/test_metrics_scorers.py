"""Tiny model-free perfect/failure cases for full-pipeline scientific scorers."""

from __future__ import annotations

import pytest

from app.full_pipeline_evaluation.metrics import METRIC_CATALOG, metric_ids
from app.full_pipeline_evaluation.scorers import (
    CPWER_NORMALIZATION_ID,
    CPWER_PERMUTATION_SCOPE_ID,
    AsrUtterance,
    AttributionInterval,
    DiarizationSegment,
    LongStreamCase,
    ReentryEpisode,
    SpeakerTranscriptPrerequisites,
    WordAlignment,
    attribution_intervals_from_prompt1_events,
    fold_reports_for_result_files,
    score_anonymous_diarization,
    score_asr,
    score_full_pipeline,
    score_known_unknown_attribution,
    score_resources,
    score_speaker_attributed_transcription,
    score_streaming,
    score_ux,
)


def _value(report, metric_id: str) -> float | int:
    metric = report[metric_id]
    assert metric.status == "computed", metric.to_jsonable()
    assert metric.value is not None
    return metric.value


def test_catalog_ids_are_unique_and_reports_never_omit_missing_metrics() -> None:
    assert len(METRIC_CATALOG) == len(set(METRIC_CATALOG))
    reports = score_full_pipeline()
    assert set(reports) == {
        "asr",
        "streaming",
        "diarization",
        "identity",
        "speaker_transcription",
        "ux",
        "resources",
    }
    for category, report in reports.items():
        assert tuple(report.metrics) == metric_ids(category)
        assert all(value.status == "unsupported" for value in report.metrics.values())
        assert all(value.reason for value in report.metrics.values())
        assert all(
            value.definition.category == category for value in report.metrics.values()
        )
    folded = fold_reports_for_result_files(reports)
    assert tuple(folded) == ("asr", "streaming", "diarization", "identity", "resources")
    assert tuple(folded["asr"]) == ("asr", "speaker_transcription")
    assert tuple(folded["streaming"]) == ("streaming", "ux")


def test_asr_perfect_and_total_output_failure_are_scored_in_accuracy_denominator() -> (
    None
):
    perfect = score_asr([AsrUtterance("Hello   world", "hello world")])
    assert _value(perfect, "wer") == 0.0
    assert _value(perfect, "cer") == 0.0
    assert _value(perfect, "output_failure_rate") == 0.0
    assert _value(perfect, "output_failure_count") == 0

    failed = score_asr([AsrUtterance("hello world", None, output_failed=True)])
    assert _value(failed, "wer") == 1.0
    assert _value(failed, "deletions") == 2
    assert _value(failed, "output_failure_rate") == 1.0
    assert _value(failed, "output_failure_count") == 1


def test_streaming_perfect_final_and_revision_telemetry() -> None:
    events = [
        {
            "adapter_event_type": "asr_partial",
            "hypothesis_id": "h1",
            "text": "hello",
            "emitted_elapsed_sec": 0.2,
            "audio_consumed_through_sec": 1.0,
            "stable_prefix_token_count": 0,
            "tokens": ["hello"],
            "event_sequence": 1,
        },
        {
            "adapter_event_type": "asr_partial",
            "hypothesis_id": "h1",
            "text": "hello world",
            "emitted_elapsed_sec": 0.4,
            "audio_consumed_through_sec": 2.0,
            "stable_prefix_token_count": 1,
            "tokens": ["hello", "world"],
            "event_sequence": 2,
        },
        {
            "adapter_event_type": "asr_final",
            "hypothesis_id": "h1",
            "text": "hello world",
            "emitted_elapsed_sec": 0.5,
            "audio_consumed_through_sec": 2.0,
            "finalization_latency_ms": 20.0,
            "event_sequence": 3,
        },
    ]
    report = score_streaming(
        events,
        reference_text_by_hypothesis={"h1": "hello world"},
    )
    assert _value(report, "first_nonempty_partial_latency_sec") == 0.2
    assert _value(report, "first_readable_partial_latency_sec") == 0.4
    assert _value(report, "stable_prefix_latency_sec") == 0.4
    assert _value(report, "endpoint_to_final_latency_sec") == pytest.approx(0.02)
    assert _value(report, "final_wer") == 0.0
    assert _value(report, "token_churn_rate") == 1.0
    assert report["long_stream_stability_rate"].status == "unsupported"

    empty = score_streaming([])
    assert empty["first_nonempty_partial_latency_sec"].status == "unsupported"
    assert empty["word_churn_rate"].status == "unsupported"


def test_word_churn_requires_a_within_stream_partial_transition() -> None:
    single = score_streaming(
        [
            {
                "adapter_event_type": "asr_partial",
                "hypothesis_id": "h1",
                "text": "hello",
                "emitted_elapsed_sec": 0.1,
                "audio_consumed_through_sec": 1.0,
            }
        ]
    )
    assert single["word_churn_rate"].status == "unsupported"

    unchanged = score_streaming(
        [
            {
                "adapter_event_type": "asr_partial",
                "hypothesis_id": "h1",
                "text": "hello",
                "emitted_elapsed_sec": 0.1,
                "audio_consumed_through_sec": 0.5,
            },
            {
                "adapter_event_type": "asr_partial",
                "hypothesis_id": "h1",
                "text": "hello",
                "emitted_elapsed_sec": 0.2,
                "audio_consumed_through_sec": 1.0,
            },
        ]
    )
    assert _value(unchanged, "word_churn_rate") == 0.0
    assert unchanged["word_churn_rate"].denominator == 1


def test_diarization_perfect_and_complete_miss_cases() -> None:
    reference = [DiarizationSegment(0.0, 1.0, "reference_a")]
    perfect = score_anonymous_diarization(
        reference,
        [DiarizationSegment(0.0, 1.0, "anonymous_1")],
    )
    assert _value(perfect, "der") == 0.0
    assert _value(perfect, "jer") == 0.0
    assert _value(perfect, "boundary_delay_sec") == 0.0
    assert _value(perfect, "speaker_count_error") == 0
    assert perfect["short_turn_der"].status == "unsupported"

    missed = score_anonymous_diarization(reference, [])
    assert _value(missed, "der") == 1.0
    assert _value(missed, "miss_rate") == 1.0
    assert _value(missed, "jer") == 1.0
    assert _value(missed, "speaker_count_error") == -1


def test_open_set_attribution_perfect_and_false_known_cases() -> None:
    perfect = score_known_unknown_attribution(
        [
            AttributionInterval(
                0.0,
                1.0,
                "known_a",
                True,
                predicted_speaker_id="known_a",
                decision_state="confirmed_known",
                episode_id="known_probe",
            ),
            AttributionInterval(
                1.0,
                2.0,
                "stranger_a",
                False,
                decision_state="unknown",
                predicted_unknown_label="Unknown_1",
                episode_id="unknown_probe",
            ),
        ]
    )
    assert _value(perfect, "correctly_named_known_rate") == 1.0
    assert _value(perfect, "fpir") == 0.0
    assert _value(perfect, "unknown_n_consistency") == 1.0

    failure = score_known_unknown_attribution(
        [
            AttributionInterval(
                0.0,
                1.0,
                "known_a",
                True,
                predicted_speaker_id="known_b",
                decision_state="confirmed_known",
                episode_id="known_probe",
            ),
            AttributionInterval(
                1.0,
                2.0,
                "stranger_a",
                False,
                predicted_speaker_id="known_b",
                decision_state="confirmed_known",
                episode_id="unknown_probe",
            ),
        ]
    )
    assert _value(failure, "correctly_named_known_rate") == 0.0
    assert _value(failure, "wrong_known_time_sec") == 1.0
    assert _value(failure, "fpir") == 1.0


def test_unknown_consistency_conditions_on_labelled_unknown_duration() -> None:
    report = score_known_unknown_attribution(
        [
            AttributionInterval(
                0.0,
                1.0,
                "stranger_a",
                False,
                decision_state="unknown",
                predicted_unknown_label=None,
                episode_id="unknown_probe_1",
            ),
            AttributionInterval(
                1.0,
                2.0,
                "stranger_a",
                False,
                decision_state="unknown",
                predicted_unknown_label="Speaker_1",
                episode_id="unknown_probe_1",
            ),
            AttributionInterval(
                2.0,
                3.0,
                "stranger_a",
                False,
                decision_state="unknown",
                predicted_unknown_label="Speaker_1",
                episode_id="unknown_probe_2",
            ),
        ]
    )

    consistency = report["unknown_n_consistency"]
    assert _value(report, "unknown_n_consistency") == 1.0
    assert consistency.denominator == 2.0
    assert consistency.details["unlabelled_unknown_duration_sec"] == 1.0


def test_cpwer_requires_attested_complete_streams_and_uses_global_permutation() -> None:
    references = {"speaker_a": "hello", "speaker_b": "world"}
    hypotheses = {"hyp_1": "world", "hyp_2": "hello"}
    unsupported = score_speaker_attributed_transcription(references, hypotheses)
    assert unsupported["cpwer"].status == "unsupported"
    assert "normalization_id" in str(unsupported["cpwer"].reason)

    prerequisites = SpeakerTranscriptPrerequisites(
        reference_streams_complete=True,
        hypothesis_streams_complete=True,
        normalization_id=CPWER_NORMALIZATION_ID,
        permutation_scope=CPWER_PERMUTATION_SCOPE_ID,
        identities_comparable=False,
    )
    permuted = score_speaker_attributed_transcription(
        references,
        hypotheses,
        prerequisites=prerequisites,
    )
    assert _value(permuted, "cpwer") == 0.0
    assert permuted["speaker_attributed_wer"].status == "unsupported"

    word_level = score_speaker_attributed_transcription(
        {"speaker_a": "hello"},
        {"speaker_a": "hello"},
        prerequisites=SpeakerTranscriptPrerequisites(
            True,
            True,
            CPWER_NORMALIZATION_ID,
            CPWER_PERMUTATION_SCOPE_ID,
            identities_comparable=True,
        ),
        word_alignments=[
            WordAlignment("hello", "hello", "speaker_a", "speaker_a", 0.5)
        ],
        revision_events=[],
    )
    assert _value(word_level, "speaker_attributed_wer") == 0.0
    assert _value(word_level, "word_speaker_label_accuracy") == 1.0
    assert _value(word_level, "correct_transcribed_attributed_word_rate") == 1.0


@pytest.mark.parametrize(
    ("normalization_id", "permutation_scope"),
    [
        ("not_the_implemented_normalizer", CPWER_PERMUTATION_SCOPE_ID),
        (CPWER_NORMALIZATION_ID, "global_corpus"),
    ],
)
def test_cpwer_rejects_unimplemented_normalization_or_scope(
    normalization_id: str,
    permutation_scope: str,
) -> None:
    report = score_speaker_attributed_transcription(
        {"speaker_a": "hello"},
        {"hypothesis_a": "hello"},
        prerequisites=SpeakerTranscriptPrerequisites(
            reference_streams_complete=True,
            hypothesis_streams_complete=True,
            normalization_id=normalization_id,
            permutation_scope=permutation_scope,
        ),
    )
    assert report["cpwer"].status == "unsupported"
    assert report["cpwer"].value is None


def test_word_speaker_metrics_require_reference_speaker_labels() -> None:
    report = score_speaker_attributed_transcription(
        None,
        None,
        word_alignments=[
            WordAlignment(
                "hello",
                "hello",
                None,
                "speaker_a",
                reference_duration_sec=0.5,
            )
        ],
    )
    for metric_id in (
        "word_speaker_label_accuracy",
        "correct_transcribed_attributed_word_rate",
        "wrong_speaker_word_count",
        "wrong_speaker_word_time_sec",
    ):
        assert report[metric_id].status == "unsupported"
        assert "reference" in str(report[metric_id].reason)
    assert _value(report, "unlabeled_generic_word_rate") == 0.0


def test_stable_name_latency_is_aggregated_once_per_episode() -> None:
    intervals = [
        AttributionInterval(
            start_sec=index / 10,
            end_sec=(index + 1) / 10,
            reference_speaker_id="known_a",
            reference_is_known=True,
            episode_id="episode_a",
            stable_name_latency_sec=1.0,
        )
        for index in range(5)
    ]
    intervals.append(
        AttributionInterval(
            start_sec=1.0,
            end_sec=2.0,
            reference_speaker_id="known_b",
            reference_is_known=True,
            episode_id="episode_b",
            stable_name_latency_sec=9.0,
        )
    )

    report = score_known_unknown_attribution(intervals)

    assert _value(report, "stable_name_latency_sec") == 5.0
    assert report["stable_name_latency_sec"].denominator == 2
    assert report["stable_name_latency_sec"].details["episode_count"] == 2


def test_stable_name_latency_rejects_inconsistent_episode_values() -> None:
    report = score_known_unknown_attribution(
        [
            AttributionInterval(
                0.0,
                1.0,
                "known_a",
                True,
                episode_id="episode_a",
                stable_name_latency_sec=1.0,
            ),
            AttributionInterval(
                1.0,
                2.0,
                "known_a",
                True,
                episode_id="episode_a",
                stable_name_latency_sec=2.0,
            ),
        ]
    )
    assert report["stable_name_latency_sec"].status == "unsupported"
    assert "inconsistent" in str(report["stable_name_latency_sec"].reason)


def test_ux_perfect_timeline_and_resources_make_absence_explicit() -> None:
    ux = score_ux(
        [
            {
                "event_type": "asr_partial",
                "text": "hello",
                "emitted_elapsed_sec": 0.1,
                "event_sequence": 1,
                "ui_identity_is_correct": True,
                "displayed_speaker_id": "known_a",
                "start_sec": 0.0,
                "end_sec": 1.0,
                "ui_lag_ms": 10.0,
                "dropped_sample_count_delta": 0,
                "sample_rate_hz": 16000,
                "stall_duration_sec": 0.0,
            },
            {
                "event_type": "anonymous_speaker",
                "anonymous_speaker_id": "anon_1",
                "emitted_elapsed_sec": 0.2,
                "event_sequence": 2,
            },
            {
                "event_type": "identity_label",
                "identity_state": "confirmed",
                "speaker_label": {"label_kind": "known", "display_label": "A"},
                "emitted_elapsed_sec": 0.3,
                "event_sequence": 3,
            },
            {
                "event_type": "asr_final",
                "text": "hello",
                "transcript_state": "final",
                "emitted_elapsed_sec": 0.5,
                "event_sequence": 4,
            },
        ]
    )
    assert _value(ux, "time_to_first_text_sec") == 0.1
    assert _value(ux, "time_to_stable_text_sec") == 0.1
    assert ux["time_to_tentative_known_name_sec"].status == "unsupported"
    assert _value(ux, "wrong_name_dwell_sec") == 0.0
    assert _value(ux, "dropped_audio_sec") == 0.0
    assert _value(ux, "stall_time_sec") == 0.0

    resources = score_resources(
        [
            {
                "elapsed_sec": 0.0,
                "process_cpu_percent": 10.0,
                "process_rss_bytes": 100,
                "component": "asr",
                "processing_sec": 0.5,
                "audio_duration_sec": 1.0,
            },
            {
                "elapsed_sec": 2.0,
                "process_cpu_percent": 30.0,
                "process_rss_bytes": 200,
            },
        ],
        audio_duration_sec=4.0,
        wall_time_sec=2.0,
        failure_count=0,
        retry_count=0,
    )
    assert _value(resources, "total_rtf") == 0.5
    assert _value(resources, "audio_throughput") == 2.0
    assert _value(resources, "process_cpu_mean_percent") == 20.0
    assert _value(resources, "peak_rss_bytes") == 200
    assert resources["gpu_peak_utilization_percent"].status == "unsupported"


def test_prompt1_nested_timing_drop_deltas_and_per_speaker_revisions() -> None:
    baseline = 1_000_000_000

    def envelope(
        event_type: str,
        sequence: int,
        elapsed_sec: float,
        **payload: object,
    ) -> dict[str, object]:
        return {
            "event_type": event_type,
            "event_sequence": sequence,
            "processing_timestamps": {
                "emitted_monotonic_ns": baseline + round(elapsed_sec * 1e9)
            },
            **payload,
        }

    events = [
        envelope(
            "audio_frame",
            1,
            0.01,
            sample_rate_hz=16000,
            capture_timestamps={
                "capture_start_monotonic_ns": baseline,
                "dropped_sample_count_before": 1600,
                "sample_start_index": 1600,
                "sample_end_index": 3200,
            },
        ),
        envelope(
            "asr_partial",
            2,
            0.2,
            text="hello",
            # The derived event repeats the frame's capture delta; it must not
            # be added a second time.
            capture_timestamps={"dropped_sample_count_before": 1600},
        ),
        envelope(
            "anonymous_speaker",
            3,
            0.3,
            anonymous_speaker_id="anon_a",
        ),
        envelope(
            "identity_label",
            4,
            0.35,
            anonymous_speaker_id="anon_a",
            identity_state="tentative",
            speaker_label={
                "label_kind": "known",
                "display_label": "A",
                "enrolled_speaker_id": "speaker_a",
            },
        ),
        envelope(
            "identity_label",
            5,
            0.4,
            anonymous_speaker_id="anon_a",
            identity_state="confirmed",
            speaker_label={
                "label_kind": "known",
                "display_label": "A",
                "enrolled_speaker_id": "speaker_a",
            },
        ),
        envelope(
            "identity_label",
            6,
            0.45,
            anonymous_speaker_id="anon_b",
            identity_state="confirmed",
            speaker_label={
                "label_kind": "known",
                "display_label": "B",
                "enrolled_speaker_id": "speaker_b",
            },
        ),
        envelope(
            "identity_label",
            7,
            0.5,
            anonymous_speaker_id="anon_a",
            identity_state="confirmed",
            speaker_label={
                "label_kind": "known",
                "display_label": "A",
                "enrolled_speaker_id": "speaker_a",
            },
        ),
        envelope(
            "identity_label",
            8,
            0.6,
            anonymous_speaker_id="anon_a",
            identity_state="unknown",
            speaker_label={
                "label_kind": "unknown",
                "display_label": "Unknown_1",
                "enrolled_speaker_id": None,
            },
        ),
        envelope("asr_final", 9, 0.7, text="hello", transcript_state="final"),
    ]
    report = score_ux(events)
    assert _value(report, "time_to_first_text_sec") == pytest.approx(0.2)
    assert _value(report, "time_to_first_anonymous_label_sec") == pytest.approx(0.3)
    assert _value(report, "time_to_tentative_known_name_sec") == pytest.approx(0.35)
    assert _value(report, "time_to_confirmed_known_name_sec") == pytest.approx(0.4)
    assert _value(report, "dropped_audio_sec") == pytest.approx(0.1)
    assert _value(report, "ux_identity_revision_count") == 2

    no_baseline = score_ux(
        [
            {
                "event_type": "asr_partial",
                "text": "not enough timing provenance",
                "processing_timestamps": {"emitted_monotonic_ns": baseline + 1},
            }
        ]
    )
    assert no_baseline["time_to_first_text_sec"].status == "unsupported"


def test_protocol_inputs_enable_short_turn_reentry_and_long_stream_metrics() -> None:
    diarization = score_anonymous_diarization(
        [
            DiarizationSegment(0.0, 0.5, "reference_short"),
            DiarizationSegment(0.5, 2.0, "reference_long"),
        ],
        [DiarizationSegment(0.5, 2.0, "hypothesis_long")],
        short_turn_max_duration_sec=0.5,
        reentry_episodes=[
            ReentryEpisode(
                "reentry_1", "reference_long", "hypothesis_long", "hypothesis_long"
            ),
            ReentryEpisode(
                "reentry_2", "reference_short", "hypothesis_a", "hypothesis_b"
            ),
        ],
    )
    assert _value(diarization, "short_turn_der") == 1.0
    assert _value(diarization, "reentry_accuracy") == 0.5

    streaming = score_streaming(
        [],
        long_stream_cases=[
            LongStreamCase("long_1", 600.0, True),
            LongStreamCase("long_2", 600.0, True, stall_count=1),
        ],
    )
    assert _value(streaming, "long_stream_stability_rate") == 0.5


def test_standard_short_turn_bins_use_the_frozen_exact_boundaries() -> None:
    report = score_anonymous_diarization(
        [
            DiarizationSegment(0.0, 0.4, "reference_lt_half"),
            DiarizationSegment(1.0, 1.5, "reference_exact_half"),
            DiarizationSegment(2.0, 3.0, "reference_exact_one"),
            DiarizationSegment(4.0, 6.0, "reference_exact_two"),
            DiarizationSegment(7.0, 9.1, "reference_over_two"),
        ],
        [DiarizationSegment(1.0, 1.5, "hypothesis_exact_half")],
        score_standard_short_turn_bins=True,
    )

    assert _value(report, "short_turn_der_lt_0_5_sec") == 1.0
    assert _value(report, "short_turn_der_0_5_to_1_0_sec") == 0.0
    assert _value(report, "short_turn_der_1_0_to_2_0_sec") == 1.0
    assert report["short_turn_der_lt_0_5_sec"].details["short_turn_region_count"] == 1
    assert (
        report["short_turn_der_0_5_to_1_0_sec"].details["short_turn_region_count"] == 1
    )
    assert (
        report["short_turn_der_1_0_to_2_0_sec"].details["short_turn_region_count"] == 2
    )
    assert (
        report["short_turn_der_1_0_to_2_0_sec"].details["duration_upper_inclusive"]
        is True
    )


def test_boundary_delay_applies_uem_and_collar_tolerance() -> None:
    report = score_anonymous_diarization(
        [DiarizationSegment(0.0, 2.0, "reference_a")],
        [DiarizationSegment(0.2, 2.2, "hypothesis_a")],
        uem=[(0.0, 1.0)],
        collar_sec=0.1,
    )
    assert _value(report, "boundary_delay_sec") == pytest.approx(0.1)
    assert report["boundary_delay_sec"].details["uem_provided"] is True


def test_prompt1_identity_reference_adapter_normalizes_nested_known_state() -> None:
    events = [
        {
            "event_type": "identity_label",
            "event_sequence": 1,
            "anonymous_speaker_id": "anon_1",
            "identity_state": "tentative",
            "speaker_label": {
                "label_kind": "known",
                "display_label": "Alice",
                "enrolled_speaker_id": "speaker_a",
            },
            "capture_timestamps": {"audio_end_sec": 0.5},
        },
        {
            "event_type": "identity_label",
            "event_sequence": 2,
            "anonymous_speaker_id": "anon_1",
            "identity_state": "confirmed",
            "speaker_label": {
                "label_kind": "known",
                "display_label": "Alice",
                "enrolled_speaker_id": "speaker_a",
            },
            "capture_timestamps": {"audio_end_sec": 1.0},
        },
    ]
    intervals = attribution_intervals_from_prompt1_events(
        events,
        [
            {
                "start_sec": 0.0,
                "end_sec": 2.0,
                "anonymous_speaker_id": "anon_1",
                "reference_speaker_id": "speaker_a",
                "reference_is_known": True,
                "episode_id": "probe_1",
            }
        ],
    )
    assert [row.decision_state for row in intervals] == [
        "unknown",
        "tentative_known",
        "confirmed_known",
    ]
    report = score_known_unknown_attribution(intervals, identity_events=events)
    assert _value(report, "correctly_named_known_rate") == 0.5
    assert _value(report, "fnir") == 0.0
    assert _value(report, "stable_name_latency_sec") == 1.0
    assert report["stable_name_latency_sec"].details["censored_episode_count"] == 0
    assert _value(report, "identity_revision_count") == 1


def test_stable_name_is_derived_after_last_correction_and_wrong_dwell_uses_alignment() -> (
    None
):
    intervals = [
        AttributionInterval(
            0.0,
            0.5,
            "speaker_a",
            True,
            decision_state="unknown",
            episode_id="episode_a",
        ),
        AttributionInterval(
            0.5,
            1.0,
            "speaker_a",
            True,
            predicted_speaker_id="speaker_b",
            decision_state="tentative_known",
            episode_id="episode_a",
        ),
        AttributionInterval(
            1.0,
            2.0,
            "speaker_a",
            True,
            predicted_speaker_id="speaker_a",
            decision_state="confirmed_known",
            episode_id="episode_a",
        ),
    ]

    identity = score_known_unknown_attribution(intervals)
    assert _value(identity, "stable_name_latency_sec") == 1.0
    ux = score_ux([], attribution_intervals=intervals)
    assert _value(ux, "wrong_name_dwell_sec") == 0.5
    assert (
        ux["wrong_name_dwell_sec"].details["source"]
        == "time_aligned_attribution_decision_intervals"
    )


def test_retroactive_correction_excludes_causal_append_events() -> None:
    report = score_speaker_attributed_transcription(
        None,
        None,
        revision_events=[
            {
                "event_type": "transcript_revision",
                "operation": "append",
                "revision": {"corrected_event_ids": ["causal_asr_event"]},
            },
            {"event_type": "transcript_revision", "operation": "replace"},
            {"event_type": "transcript_revision", "operation": "speaker_relabel"},
        ],
    )
    assert _value(report, "retroactive_correction_count") == 2
