"""Metric contracts and the frozen scientific catalog for full-pipeline V1.

The central rule in this module is that absence is data.  A metric whose
prerequisites are unavailable is emitted with ``status="unsupported"``; a
metric with valid inputs but a zero mathematical denominator is emitted with
``status="undefined"``.  Neither case is silently omitted or converted to
zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal, Mapping, Sequence


METRICS_SCHEMA_VERSION = "full-pipeline-metrics.v1"
MetricStatus = Literal["computed", "unsupported", "undefined"]


@dataclass(frozen=True)
class MetricDefinition:
    """One immutable metric definition and its scientific prerequisites."""

    metric_id: str
    category: str
    display_name: str
    definition: str
    unit: str
    higher_is_better: bool | None
    prerequisites: tuple[str, ...]

    def to_jsonable(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "category": self.category,
            "display_name": self.display_name,
            "definition": self.definition,
            "unit": self.unit,
            "higher_is_better": self.higher_is_better,
            "prerequisites": list(self.prerequisites),
        }


@dataclass(frozen=True)
class MetricValue:
    """A computed, unsupported, or mathematically undefined metric value."""

    definition: MetricDefinition
    status: MetricStatus
    value: int | float | None = None
    numerator: int | float | None = None
    denominator: int | float | None = None
    reason: str | None = None
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status == "computed" and self.value is None:
            raise ValueError("computed metrics require a value")
        if self.status != "computed" and self.value is not None:
            raise ValueError("non-computed metrics cannot carry a value")
        if self.status != "computed" and not self.reason:
            raise ValueError("unsupported/undefined metrics require a reason")

    @property
    def metric_id(self) -> str:
        return self.definition.metric_id

    def to_jsonable(self) -> dict[str, object]:
        return {
            **self.definition.to_jsonable(),
            "status": self.status,
            "value": self.value,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "reason": self.reason,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class MetricReport:
    """All catalog metrics for one evaluation view.

    ``build_metric_report`` fills any unprovided catalog entry with an explicit
    unsupported value, so result writers can never accidentally omit a metric.
    """

    category: str
    metrics: Mapping[str, MetricValue]
    warnings: tuple[str, ...] = ()
    schema_version: str = METRICS_SCHEMA_VERSION

    def __getitem__(self, metric_id: str) -> MetricValue:
        return self.metrics[metric_id]

    def to_jsonable(self) -> dict[str, object]:
        values = {key: value.to_jsonable() for key, value in self.metrics.items()}
        return {
            "schema_version": self.schema_version,
            "category": self.category,
            "metrics": values,
            "computed_metric_count": sum(
                value.status == "computed" for value in self.metrics.values()
            ),
            "unsupported_metric_count": sum(
                value.status == "unsupported" for value in self.metrics.values()
            ),
            "undefined_metric_count": sum(
                value.status == "undefined" for value in self.metrics.values()
            ),
            "warnings": list(self.warnings),
        }


def _d(
    metric_id: str,
    category: str,
    display_name: str,
    definition: str,
    unit: str,
    higher_is_better: bool | None,
    *prerequisites: str,
) -> MetricDefinition:
    return MetricDefinition(
        metric_id=metric_id,
        category=category,
        display_name=display_name,
        definition=definition,
        unit=unit,
        higher_is_better=higher_is_better,
        prerequisites=tuple(prerequisites),
    )


_DEFINITIONS = (
    # ASR-only view. WER/CER are micro-averaged over the scored corpus.
    _d(
        "wer",
        "asr",
        "Word error rate",
        "(substitutions + deletions + insertions) / reference word count after "
        "lowercase-and-whitespace normalization; failed outputs score as empty.",
        "ratio",
        False,
        "reference transcripts",
        "hypothesis or explicit output failure per utterance",
    ),
    _d(
        "substitutions",
        "asr",
        "Substitutions",
        "Levenshtein word substitutions summed over utterances.",
        "words",
        False,
        "reference and hypothesis transcripts",
    ),
    _d(
        "deletions",
        "asr",
        "Deletions",
        "Levenshtein word deletions summed over utterances.",
        "words",
        False,
        "reference and hypothesis transcripts",
    ),
    _d(
        "insertions",
        "asr",
        "Insertions",
        "Levenshtein word insertions summed over utterances.",
        "words",
        False,
        "reference and hypothesis transcripts",
    ),
    _d(
        "cer",
        "asr",
        "Character error rate",
        "Character Levenshtein errors / reference characters after lowercase, "
        "whitespace collapse, and removal of all spaces.",
        "ratio",
        False,
        "reference and hypothesis transcripts",
    ),
    _d(
        "output_failure_count",
        "asr",
        "Output failures",
        "Count of attempted utterances with an explicit failure or no hypothesis object.",
        "utterances",
        False,
        "attempt record for every utterance",
    ),
    _d(
        "output_failure_rate",
        "asr",
        "Output failure rate",
        "Utterances explicitly failed or missing a hypothesis / attempted utterances.",
        "ratio",
        False,
        "attempt record for every utterance",
    ),
    # Streaming ASR view.
    _d(
        "first_nonempty_partial_latency_sec",
        "streaming",
        "First non-empty partial latency",
        "Earliest elapsed emission time of a non-empty non-final ASR hypothesis, relative to stream start.",
        "seconds",
        False,
        "partial events",
        "stream-relative emission time",
    ),
    _d(
        "first_readable_partial_latency_sec",
        "streaming",
        "First readable partial latency",
        "Earliest stream-relative emission time of a non-final hypothesis containing at least the declared readable_min_words.",
        "seconds",
        False,
        "partial events",
        "stream-relative emission time",
        "readability rule",
    ),
    _d(
        "stable_prefix_latency_sec",
        "streaming",
        "Stable-prefix latency",
        "Earliest stream-relative emission time at which the backend reports at least one stable-prefix token under its frozen method.",
        "seconds",
        False,
        "stable-prefix telemetry",
        "stream-relative emission time",
    ),
    _d(
        "endpoint_to_final_latency_sec",
        "streaming",
        "Endpoint-to-final latency",
        "Mean measured time from endpoint/finalize request to corresponding final hypothesis emission; backend finalization latency is accepted only when provenance identifies that interval.",
        "seconds",
        False,
        "paired endpoint and final timestamps or backend finalization latency",
    ),
    _d(
        "partial_revision_rate_per_minute",
        "streaming",
        "Partial revision rate",
        "Changed non-final hypotheses after the first partial, divided by consumed audio minutes.",
        "revisions/minute",
        False,
        "ordered partial hypotheses",
        "consumed audio duration",
    ),
    _d(
        "token_churn_rate",
        "streaming",
        "Partial token churn",
        "Decoder-token edit operations between consecutive non-final hypotheses / decoder tokens in the earlier hypotheses; computed only from backend-emitted token arrays.",
        "ratio",
        False,
        "ordered partial hypotheses",
        "backend-emitted token arrays",
    ),
    _d(
        "word_churn_rate",
        "streaming",
        "Partial word churn",
        "Word edit operations between consecutive non-final hypotheses / words in the earlier hypotheses; empty-to-nonempty additions use one denominator unit.",
        "ratio",
        False,
        "ordered partial hypotheses",
    ),
    _d(
        "final_wer",
        "streaming",
        "Final streaming WER",
        "Corpus WER using only each hypothesis stream's final revision.",
        "ratio",
        False,
        "final hypotheses",
        "matching reference transcripts",
    ),
    _d(
        "long_stream_stability_rate",
        "streaming",
        "Long-stream stability",
        "Long streams completed without reset, stall, exception, or missing final / eligible long streams.",
        "ratio",
        True,
        "declared long-stream cases",
        "completion/failure evidence",
    ),
    # Anonymous diarization view. Rates use scored reference speaker-time.
    _d(
        "der",
        "diarization",
        "Diarization error rate",
        "(missed speaker-time + false-alarm speaker-time + mapped speaker-confusion time) / scored reference speaker-time, after the declared collar/overlap/UEM policy.",
        "ratio",
        False,
        "reference and hypothesis time segments",
        "scoring-region policy",
    ),
    _d(
        "jer",
        "diarization",
        "Jaccard error rate",
        "Mean over reference speakers of 1 - intersection/union with the one-to-one hypothesis speaker assignment that maximizes total Jaccard similarity.",
        "ratio",
        False,
        "reference and hypothesis time segments",
    ),
    _d(
        "miss_rate",
        "diarization",
        "Miss rate",
        "Missed reference speaker-time / scored reference speaker-time.",
        "ratio",
        False,
        "reference and hypothesis time segments",
    ),
    _d(
        "false_alarm_rate",
        "diarization",
        "False-alarm rate",
        "Excess hypothesis speaker-time / scored reference speaker-time.",
        "ratio",
        False,
        "reference and hypothesis time segments",
    ),
    _d(
        "speaker_confusion_rate",
        "diarization",
        "Speaker confusion rate",
        "Speaker-time assigned to the wrong optimally mapped speaker / scored reference speaker-time.",
        "ratio",
        False,
        "reference and hypothesis time segments",
    ),
    _d(
        "boundary_delay_sec",
        "diarization",
        "Boundary delay",
        "Mean max(0, absolute nearest mapped-speaker boundary error - collar) over reference turn boundaries inside the UEM whose speaker has scored time.",
        "seconds",
        False,
        "reference and hypothesis turn boundaries",
        "UEM/collar policy",
    ),
    _d(
        "speaker_count_error",
        "diarization",
        "Speaker-count error",
        "Number of distinct hypothesis speakers minus distinct reference speakers in the scored region.",
        "speakers",
        None,
        "reference and hypothesis time segments",
    ),
    _d(
        "fragmentation_per_reference_speaker",
        "diarization",
        "Fragmentation",
        "Mean max(0, overlapping hypothesis clusters - 1) per reference speaker.",
        "fragments/speaker",
        False,
        "reference and hypothesis time segments",
    ),
    _d(
        "merge_contamination_rate",
        "diarization",
        "Merge contamination",
        "For each hypothesis cluster, overlap with all non-dominant reference speakers, summed and divided by total hypothesis/reference overlap.",
        "ratio",
        False,
        "reference and hypothesis time segments",
    ),
    _d(
        "short_turn_der",
        "diarization",
        "Short-turn DER",
        "DER restricted to reference turn segments at or below a caller-supplied frozen maximum duration; no default threshold is invented.",
        "ratio",
        False,
        "reference segments are protocol turns",
        "frozen short-turn maximum duration",
    ),
    _d(
        "short_turn_der_lt_0_5_sec",
        "diarization",
        "Short-turn DER below 0.5 seconds",
        "DER restricted to protocol reference turns shorter than 0.5 seconds.",
        "ratio",
        False,
        "reference segments are protocol turns",
        "frozen [0.0, 0.5) second duration bin",
    ),
    _d(
        "short_turn_der_0_5_to_1_0_sec",
        "diarization",
        "Short-turn DER from 0.5 to 1.0 seconds",
        "DER restricted to protocol reference turns at least 0.5 seconds and shorter than 1.0 second.",
        "ratio",
        False,
        "reference segments are protocol turns",
        "frozen [0.5, 1.0) second duration bin",
    ),
    _d(
        "short_turn_der_1_0_to_2_0_sec",
        "diarization",
        "Short-turn DER from 1.0 to 2.0 seconds",
        "DER restricted to protocol reference turns at least 1.0 second and at most 2.0 seconds.",
        "ratio",
        False,
        "reference segments are protocol turns",
        "frozen [1.0, 2.0] second duration bin",
    ),
    _d(
        "reentry_accuracy",
        "diarization",
        "Speaker re-entry accuracy",
        "Episodes whose pre-gap and post-gap hypothesis speaker IDs are identical and optimally map to the annotated reference speaker / protocol-annotated re-entry episodes.",
        "ratio",
        True,
        "re-entry episode annotations",
        "pre-gap and post-gap hypothesis speaker IDs",
        "speaker mapping",
    ),
    # Known/unknown attribution view. Time metrics are duration weighted.
    _d(
        "correctly_named_known_time_sec",
        "identity",
        "Correctly named known time",
        "Known-reference time assigned its exact enrolled identity in confirmed-known state.",
        "seconds",
        True,
        "reference identity and decision intervals",
    ),
    _d(
        "correctly_named_known_rate",
        "identity",
        "Correctly named known rate",
        "Correctly named known time / known-reference time.",
        "ratio",
        True,
        "reference identity and decision intervals",
    ),
    _d(
        "wrong_known_time_sec",
        "identity",
        "Wrong-known time",
        "Known-reference time assigned a different enrolled identity.",
        "seconds",
        False,
        "reference identity and decision intervals",
    ),
    _d(
        "stranger_false_known_time_sec",
        "identity",
        "Stranger false-known time",
        "Unknown-reference time assigned any enrolled identity.",
        "seconds",
        False,
        "known/unknown reference and decision intervals",
    ),
    _d(
        "generic_known_time_sec",
        "identity",
        "Generic-known time",
        "Time labelled generically known without a specific confirmed identity.",
        "seconds",
        False,
        "decision intervals",
    ),
    _d(
        "uncovered_known_time_sec",
        "identity",
        "Uncovered known time",
        "Known-reference time left Unknown or uncovered.",
        "seconds",
        False,
        "reference identity and decision intervals",
    ),
    _d(
        "fpir",
        "identity",
        "False-positive identification rate",
        "Non-mated (unknown) search episodes whose final decision returns any enrolled identity / non-mated search episodes.",
        "ratio",
        False,
        "episode IDs",
        "known/unknown reference",
        "final decision per episode",
    ),
    _d(
        "fnir",
        "identity",
        "False-negative identification rate",
        "Mated (known) search episodes whose final decision is not the correct enrolled identity / mated search episodes; this includes rejection and wrong-known identification.",
        "ratio",
        False,
        "episode IDs",
        "known reference identity",
        "final decision per episode",
    ),
    _d(
        "unknown_n_consistency",
        "identity",
        "Session-anonymous label consistency",
        "For each recurring stranger, duration carrying its modal session-local Speaker_N/Unknown_N label / its total anonymous-labelled duration, micro-averaged.",
        "ratio",
        True,
        "persistent stranger reference IDs",
        "session-local Speaker_N/Unknown_N labels",
    ),
    _d(
        "identity_split_count",
        "identity",
        "Identity splits",
        "Sum over reference speakers of max(0, distinct output identities - 1).",
        "splits",
        False,
        "reference identities and output labels",
    ),
    _d(
        "identity_merge_count",
        "identity",
        "Identity merges",
        "Sum over output identities of max(0, distinct reference speakers - 1).",
        "merges",
        False,
        "reference identities and output labels",
    ),
    _d(
        "cold_identity_accuracy",
        "identity",
        "Cold identity accuracy",
        "Correct confirmed identity duration / known duration for protocol-marked cold-start intervals.",
        "ratio",
        True,
        "cold/warm annotation",
    ),
    _d(
        "warm_identity_accuracy",
        "identity",
        "Warm identity accuracy",
        "Correct confirmed identity duration / known duration for protocol-marked warm intervals.",
        "ratio",
        True,
        "cold/warm annotation",
    ),
    _d(
        "stable_name_latency_sec",
        "identity",
        "Stable-name latency",
        "Mean time from first reference speech to the first correct confirmed name that is never subsequently revised for that episode.",
        "seconds",
        False,
        "episode-level identity revision timeline",
    ),
    _d(
        "identity_revision_count",
        "identity",
        "Identity revisions",
        "Count of post-initial identity-label changes, excluding repeated identical state/label emissions.",
        "revisions",
        False,
        "ordered identity events",
    ),
    # Speaker-attributed transcription view.
    _d(
        "cpwer",
        "speaker_transcription",
        "Concatenated minimum-permutation WER",
        "Minimum total word edit errors after one-to-one assignment of complete per-speaker hypothesis streams to complete per-speaker reference streams, including dummy streams, divided by total reference words.",
        "ratio",
        False,
        "complete reference per-speaker word streams",
        "complete hypothesis per-speaker word streams",
        "frozen normalization ID",
        "declared permutation scope",
    ),
    _d(
        "speaker_attributed_wer",
        "speaker_transcription",
        "Speaker-attributed WER",
        "Word edit errors summed between same-identity reference and hypothesis streams (extra/missing streams use empty counterparts) / total reference words.",
        "ratio",
        False,
        "comparable reference/hypothesis speaker identities",
    ),
    _d(
        "word_speaker_label_accuracy",
        "speaker_transcription",
        "Word speaker-label accuracy",
        "Aligned reference words whose hypothesis speaker label equals the reference speaker / aligned reference words with a hypothesis word.",
        "ratio",
        True,
        "word alignment",
        "reference and hypothesis speaker labels",
    ),
    _d(
        "correct_transcribed_attributed_word_rate",
        "speaker_transcription",
        "Correctly transcribed and attributed words",
        "Reference words with an exact normalized aligned hypothesis word and correct speaker label / all reference words represented by the alignment.",
        "ratio",
        True,
        "word alignment",
        "speaker labels",
    ),
    _d(
        "wrong_speaker_word_count",
        "speaker_transcription",
        "Wrong-speaker words",
        "Aligned hypothesis words attached to a non-matching specific speaker label, regardless of lexical correctness.",
        "words",
        False,
        "word alignment",
        "speaker labels",
    ),
    _d(
        "wrong_speaker_word_time_sec",
        "speaker_transcription",
        "Wrong-speaker word time",
        "Reference-aligned duration of wrong-speaker words; unavailable when word timing is absent.",
        "seconds",
        False,
        "word alignment",
        "speaker labels",
        "reference word durations",
    ),
    _d(
        "unlabeled_generic_word_rate",
        "speaker_transcription",
        "Unlabelled/generic word rate",
        "Hypothesis words with no specific speaker label (None, empty, or generic_known) / hypothesis words in the alignment.",
        "ratio",
        False,
        "hypothesis word labels",
    ),
    _d(
        "retroactive_correction_count",
        "speaker_transcription",
        "Retroactive corrections",
        "Transcript revision operations that alter already emitted text or speaker attribution.",
        "corrections",
        False,
        "revision events",
    ),
    # User-experience view.
    _d(
        "time_to_first_text_sec",
        "ux",
        "Time to first text",
        "Stream-relative time of the first non-empty ASR partial/final or transcript text visible to the product.",
        "seconds",
        False,
        "ordered event timeline",
        "stream-relative time",
    ),
    _d(
        "time_to_stable_text_sec",
        "ux",
        "Time to stable text",
        "Earliest time the displayed normalized transcript equals the final transcript and never changes afterwards.",
        "seconds",
        False,
        "complete ordered transcript revision timeline",
    ),
    _d(
        "time_to_first_anonymous_label_sec",
        "ux",
        "Time to first anonymous label",
        "Stream-relative time of the first non-empty anonymous speaker label.",
        "seconds",
        False,
        "anonymous-speaker events",
        "stream-relative time",
    ),
    _d(
        "time_to_tentative_known_name_sec",
        "ux",
        "Time to tentative known name",
        "Stream-relative time of the first user-visible tentative-known identity label. Confirmed-only events are not treated as tentative evidence.",
        "seconds",
        False,
        "tentative-known identity events",
        "stream-relative time",
    ),
    _d(
        "time_to_confirmed_known_name_sec",
        "ux",
        "Time to confirmed known name",
        "Stream-relative time of the first confirmed-known identity label.",
        "seconds",
        False,
        "identity events",
        "stream-relative time",
    ),
    _d(
        "wrong_name_dwell_sec",
        "ux",
        "Wrong-name dwell",
        "Total wall-clock duration for which the UI displayed a specific enrolled name that disagreed with time-aligned reference identity.",
        "seconds",
        False,
        "UI label intervals",
        "time-aligned identity reference",
    ),
    _d(
        "transcript_revision_count",
        "ux",
        "Transcript revisions",
        "Post-initial changes to the normalized displayed transcript.",
        "revisions",
        False,
        "ordered displayed transcript states",
    ),
    _d(
        "ux_identity_revision_count",
        "ux",
        "Identity revisions",
        "Post-initial changes to displayed identity state or label.",
        "revisions",
        False,
        "ordered displayed identity states",
    ),
    _d(
        "ui_event_lag_sec",
        "ux",
        "UI/event lag",
        "Mean UI-render timestamp minus source event emission timestamp for paired events.",
        "seconds",
        False,
        "paired event-emission and UI-render timestamps",
    ),
    _d(
        "dropped_audio_sec",
        "ux",
        "Dropped audio",
        "Dropped input samples / source sample rate, summed without double-counting cumulative counters.",
        "seconds",
        False,
        "dropped-sample deltas",
        "sample rate",
    ),
    _d(
        "stall_time_sec",
        "ux",
        "Stall time",
        "Sum of protocol-defined non-overlapping intervals where no required output progressed while input remained available.",
        "seconds",
        False,
        "stall intervals",
    ),
    # Resource view.
    _d(
        "total_rtf",
        "resources",
        "Total real-time factor",
        "End-to-end wall time / evaluated audio duration.",
        "ratio",
        False,
        "end-to-end wall time",
        "audio duration",
    ),
    _d(
        "component_rtf",
        "resources",
        "Component real-time factors",
        "Per-component processing time / component audio duration; values are carried in metric details.",
        "mapping",
        False,
        "component processing and audio durations",
    ),
    _d(
        "process_cpu_mean_percent",
        "resources",
        "Mean process CPU",
        "Arithmetic mean of process-tree CPU-percent samples under the frozen sampling interval.",
        "percent",
        False,
        "resource samples",
    ),
    _d(
        "process_cpu_p95_percent",
        "resources",
        "P95 process CPU",
        "Linear-interpolated 95th percentile of process-tree CPU-percent samples.",
        "percent",
        False,
        "resource samples",
    ),
    _d(
        "gpu_peak_utilization_percent",
        "resources",
        "Peak GPU utilization",
        "Maximum observed GPU utilization sample; unsupported when GPU telemetry is unavailable.",
        "percent",
        False,
        "GPU resource samples",
    ),
    _d(
        "gpu_peak_memory_bytes",
        "resources",
        "Peak GPU memory",
        "Maximum observed process/device GPU memory bytes under the declared sampler.",
        "bytes",
        False,
        "GPU memory samples",
    ),
    _d(
        "peak_rss_bytes",
        "resources",
        "Peak RSS",
        "Maximum process-tree resident-set-size sample.",
        "bytes",
        False,
        "resource samples",
    ),
    _d(
        "model_startup_sec",
        "resources",
        "Model startup",
        "Measured duration from component load start to ready state.",
        "seconds",
        False,
        "model lifecycle timestamps",
    ),
    _d(
        "model_bytes",
        "resources",
        "Model bytes",
        "Checksum-bound bytes of model assets required by the pipeline.",
        "bytes",
        False,
        "model asset manifest",
    ),
    _d(
        "cache_bytes",
        "resources",
        "Cache bytes",
        "Bytes occupied by checksum-bound reusable stage-cache artifacts for this run.",
        "bytes",
        False,
        "cache manifest",
    ),
    _d(
        "maximum_queue_depth",
        "resources",
        "Maximum queue depth",
        "Maximum observed queued frame/item count.",
        "items",
        False,
        "queue telemetry",
    ),
    _d(
        "audio_throughput",
        "resources",
        "Audio throughput",
        "Evaluated audio seconds / end-to-end wall second.",
        "audio-seconds/second",
        True,
        "end-to-end wall time",
        "audio duration",
    ),
    _d(
        "failure_count",
        "resources",
        "Failures",
        "Count of failed pipeline/component attempts in scope.",
        "failures",
        False,
        "attempt states",
    ),
    _d(
        "retry_count",
        "resources",
        "Retries",
        "Count of additional attempts after each initial attempt.",
        "retries",
        False,
        "attempt identities",
    ),
)


METRIC_CATALOG: Mapping[str, MetricDefinition] = MappingProxyType(
    {definition.metric_id: definition for definition in _DEFINITIONS}
)


def metric_ids(category: str) -> tuple[str, ...]:
    """Return catalog IDs for a category in frozen declaration order."""

    return tuple(
        definition.metric_id
        for definition in _DEFINITIONS
        if definition.category == category
    )


def computed_metric(
    metric_id: str,
    value: int | float,
    *,
    numerator: int | float | None = None,
    denominator: int | float | None = None,
    details: Mapping[str, object] | None = None,
) -> MetricValue:
    return MetricValue(
        definition=METRIC_CATALOG[metric_id],
        status="computed",
        value=value,
        numerator=numerator,
        denominator=denominator,
        details=dict(details or {}),
    )


def unsupported_metric(metric_id: str, reason: str) -> MetricValue:
    return MetricValue(
        definition=METRIC_CATALOG[metric_id],
        status="unsupported",
        reason=reason,
    )


def undefined_metric(
    metric_id: str,
    reason: str,
    *,
    numerator: int | float | None = None,
    denominator: int | float | None = None,
    details: Mapping[str, object] | None = None,
) -> MetricValue:
    return MetricValue(
        definition=METRIC_CATALOG[metric_id],
        status="undefined",
        reason=reason,
        numerator=numerator,
        denominator=denominator,
        details=dict(details or {}),
    )


def build_metric_report(
    category: str,
    values: Sequence[MetricValue] | Mapping[str, MetricValue],
    *,
    missing_reason: str = "required scorer input was not provided",
    warnings: Sequence[str] = (),
) -> MetricReport:
    """Build a complete category report, explicitly filling missing metrics."""

    supplied = (
        dict(values)
        if isinstance(values, Mapping)
        else {value.metric_id: value for value in values}
    )
    expected = metric_ids(category)
    unknown = sorted(set(supplied) - set(expected))
    if unknown:
        raise ValueError(f"metrics do not belong to category {category!r}: {unknown}")
    complete = {
        metric_id: supplied.get(metric_id)
        or unsupported_metric(metric_id, missing_reason)
        for metric_id in expected
    }
    return MetricReport(
        category=category,
        metrics=MappingProxyType(complete),
        warnings=tuple(warnings),
    )
