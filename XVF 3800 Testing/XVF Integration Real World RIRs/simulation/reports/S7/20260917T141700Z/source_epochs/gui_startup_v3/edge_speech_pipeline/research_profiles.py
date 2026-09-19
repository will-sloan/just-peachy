"""Validated opt-in research settings for the actual edge application.

No profile is loaded by the GUI or ordinary CLI. All fields are explicit, and
unknown fields fail instead of silently becoming ineffective experiment knobs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from .config import PipelineConfig


@dataclass(frozen=True)
class InputSettings:
    tap: str = "mono"
    gain: float = 1.0
    already_gained: bool = False


@dataclass(frozen=True)
class ASRSettings:
    endpoint_rule1_silence_sec: float = 2.4
    endpoint_rule2_silence_sec: float = 1.2
    endpoint_rule3_utterance_sec: float = 20.0
    decoding_method: str = "greedy_search"
    max_active_paths: int = 4
    blank_penalty: float = 0.0
    journal_read_ms: int = 100


@dataclass(frozen=True)
class SegmentationSettings:
    window_sec: float = 10.0
    hop_sec: float = 0.75
    post_policy: str = "hard_argmax_fraction"
    onset: float = 0.46
    offset: float = 0.45
    speech_fraction_threshold: float = 0.20
    overlap_fraction_threshold: float = 0.20


@dataclass(frozen=True)
class EmbeddingSettings:
    window_sec: float = 0.5
    hop_sec: float = 0.25
    minimum_rms: float = 0.002


@dataclass(frozen=True)
class TrackerSettings:
    mode: str = "baseline"
    cosine_threshold: float = 0.35
    ambiguity_margin: float = 0.03
    commit_evidence_sec: float = 1.0
    prototype_update_threshold: float = 0.45
    max_tracks: int = 16
    direction_match_deg: float = 25.0
    direction_change_deg: float = 35.0
    direction_persistence_sec: float = 0.75
    direction_max_age_sec: float = 0.25
    position_decay_sec: float = 12.0
    spatial_weight: float = 0.12
    conflict_cosine_floor: float = 0.20
    reconciliation_enabled: bool = True
    revision_horizon_sec: float = 2.0
    reconciliation_cosine: float = 0.65
    identity_score_threshold: float = 0.5128856897354127
    identity_margin_threshold: float = 0.03
    identity_minimum_evidence_sec: float = 2.0


@dataclass(frozen=True)
class XVFSettings:
    mode: str = "none"
    speech_assist_delta: float = 0.05
    minimum_reliability: float = 0.5
    advisory_silence_sec: float = 0.30
    advisory_min_utterance_sec: float = 0.5


@dataclass(frozen=True)
class PunctuationSettings:
    mode: str = "final_only"
    partial_display_min_interval_sec: float = 0.0


@dataclass(frozen=True)
class RuntimeSettings:
    asr_threads: int = 2
    speaker_threads: int = 2
    punctuation_threads: int = 1
    capture_block_ms: int = 20
    raw_capture_reserve_sec: int = 120


_SECTIONS = {
    "input": InputSettings, "asr": ASRSettings, "segmentation": SegmentationSettings,
    "embedding": EmbeddingSettings, "tracker": TrackerSettings, "xvf": XVFSettings,
    "punctuation": PunctuationSettings, "runtime": RuntimeSettings,
}


def _section(cls: type, value: Any):
    if not isinstance(value, dict):
        raise ValueError(f"{cls.__name__} must be an object")
    allowed = {item.name for item in fields(cls)}
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"unsupported {cls.__name__} fields: {sorted(unknown)}")
    result = cls(**value)
    defaults = cls()
    for item in fields(cls):
        supplied = getattr(result, item.name)
        expected = getattr(defaults, item.name)
        if isinstance(expected, bool):
            valid = isinstance(supplied, bool)
        elif isinstance(expected, int):
            valid = isinstance(supplied, int) and not isinstance(supplied, bool)
        elif isinstance(expected, float):
            valid = isinstance(supplied, (int, float)) and not isinstance(supplied, bool) and math.isfinite(supplied)
        else:
            valid = isinstance(supplied, type(expected))
        if not valid:
            raise ValueError(f"invalid type/value for {cls.__name__}.{item.name}")
    return result


def _range(value: float, low: float, high: float, name: str) -> None:
    if not low <= value <= high:
        raise ValueError(f"{name} must be in [{low}, {high}]")


@dataclass(frozen=True)
class ResearchProfile:
    profile_id: str = "B0_explicit"
    schema_version: str = "edge-research-profile.v1"
    input: InputSettings = field(default_factory=InputSettings)
    asr: ASRSettings = field(default_factory=ASRSettings)
    segmentation: SegmentationSettings = field(default_factory=SegmentationSettings)
    embedding: EmbeddingSettings = field(default_factory=EmbeddingSettings)
    tracker: TrackerSettings = field(default_factory=TrackerSettings)
    xvf: XVFSettings = field(default_factory=XVFSettings)
    punctuation: PunctuationSettings = field(default_factory=PunctuationSettings)
    runtime: RuntimeSettings = field(default_factory=RuntimeSettings)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ResearchProfile":
        if not isinstance(value, dict):
            raise ValueError("profile must be an object")
        if value.get("schema_version") == "edge-research-profile.v3":
            from .research_profiles_v3 import ResearchProfileV3
            return ResearchProfileV3.from_dict(value)
        if value.get("schema_version") == "edge-research-profile.v2":
            return ResearchProfileV2.from_dict(value)
        if set(value) - {"profile_id", "schema_version", *_SECTIONS}:
            raise ValueError("unsupported profile fields")
        profile = cls(**{key: _section(_SECTIONS[key], item) if key in _SECTIONS else item for key, item in value.items()})
        profile.validate()
        return profile

    @classmethod
    def load(cls, path: Path) -> "ResearchProfile":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    def validate(self) -> None:
        # Revalidate direct dataclass construction, not only JSON input.
        for key, cls in _SECTIONS.items():
            _section(cls, asdict(getattr(self, key)))
        if self.schema_version != "edge-research-profile.v1":
            raise ValueError("unsupported research profile schema")
        if not isinstance(self.profile_id, str) or not self.profile_id or len(self.profile_id) > 120:
            raise ValueError("profile_id must be a nonempty string <=120 characters")
        if self.input.tap not in {"mono", "O0", "O1"}:
            raise ValueError("tap declares the supplied mono file; supported mono/O0/O1")
        _range(self.input.gain, 0.25, 4.0, "input.gain")
        if self.input.already_gained and self.input.gain != 1.0:
            raise ValueError("already-gained input must use unity to prevent double gain")
        if self.asr.decoding_method not in {"greedy_search", "modified_beam_search"}:
            raise ValueError("unsupported installed Sherpa decoder")
        if self.asr.max_active_paths not in {1, 2, 4, 8}:
            raise ValueError("max_active_paths must be 1/2/4/8")
        if self.asr.decoding_method == "greedy_search" and self.asr.max_active_paths != 4:
            raise ValueError("max_active_paths has no supported effect under greedy_search")
        _range(self.asr.blank_penalty, -2.0, 2.0, "blank_penalty")
        for name in ("endpoint_rule1_silence_sec", "endpoint_rule2_silence_sec"):
            _range(getattr(self.asr, name), 0.1, 5.0, name)
        _range(self.asr.endpoint_rule3_utterance_sec, 5.0, 60.0, "max utterance")
        if self.asr.journal_read_ms not in {20, 50, 100, 200}:
            raise ValueError("journal_read_ms must be 20/50/100/200")
        if self.segmentation.window_sec != 10.0:
            raise ValueError("fixed Pyannote graph requires exactly 10 seconds")
        _range(self.segmentation.hop_sec, 0.25, 1.5, "segmentation.hop_sec")
        if self.segmentation.post_policy not in {"hard_argmax_fraction", "posterior_hysteresis"}:
            raise ValueError("unsupported segmentation post policy")
        for name in ("onset", "offset", "speech_fraction_threshold", "overlap_fraction_threshold"):
            _range(getattr(self.segmentation, name), 0.0, 1.0, name)
        if self.segmentation.offset > self.segmentation.onset:
            raise ValueError("hysteresis offset cannot exceed onset")
        if self.segmentation.post_policy == "hard_argmax_fraction" and (self.segmentation.onset != 0.46 or self.segmentation.offset != 0.45):
            raise ValueError("onset/offset are inactive in baseline hard-argmax policy; choose posterior_hysteresis")
        if self.segmentation.post_policy == "posterior_hysteresis" and self.segmentation.speech_fraction_threshold != .20:
            raise ValueError("hard speech fraction threshold is inactive under posterior_hysteresis")
        _range(self.embedding.window_sec, 0.5, 3.0, "embedding.window_sec")
        _range(self.embedding.hop_sec, 0.25, 1.0, "embedding.hop_sec")
        if self.embedding.hop_sec > self.segmentation.hop_sec:
            raise ValueError("embedding dispatch cannot exceed segmentation hop")
        ratio = self.segmentation.hop_sec / self.embedding.hop_sec
        if abs(ratio - round(ratio)) > 1e-8:
            raise ValueError("segmentation hop must be a multiple of embedding hop; no silent cadence rounding")
        _range(self.embedding.minimum_rms, 0.0, 0.02, "minimum_rms")
        modes = {"baseline", "voice_time", "angle_diagnostic", "sustained_angle", "decaying_memory", "reliability_adaptive"}
        if self.tracker.mode not in modes:
            raise ValueError("unsupported tracker mode")
        for name in ("cosine_threshold", "prototype_update_threshold", "conflict_cosine_floor", "identity_score_threshold", "reconciliation_cosine"):
            _range(getattr(self.tracker, name), -1.0, 1.0, name)
        for name in ("ambiguity_margin", "identity_margin_threshold"):
            _range(getattr(self.tracker, name), 0.0, 2.0, name)
        for name in ("commit_evidence_sec", "identity_minimum_evidence_sec"):
            _range(getattr(self.tracker, name), 0.0, 10.0, name)
        _range(self.tracker.max_tracks, 1, 64, "max_tracks")
        for name in ("direction_match_deg", "direction_change_deg"):
            _range(getattr(self.tracker, name), 1.0, 180.0, name)
        _range(self.tracker.direction_persistence_sec, 0.0, 3.0, "direction persistence")
        _range(self.tracker.direction_max_age_sec, 0.01, 1.0, "direction maximum age")
        _range(self.tracker.position_decay_sec, 0.1, 120.0, "position decay")
        _range(self.tracker.spatial_weight, 0.0, 0.5, "spatial weight")
        _range(self.tracker.revision_horizon_sec, 0.01, 10.0, "revision horizon")
        tracker_defaults = TrackerSettings()
        if self.tracker.mode != "baseline":
            for name in ("identity_score_threshold", "identity_margin_threshold", "identity_minimum_evidence_sec"):
                if getattr(self.tracker, name) != getattr(tracker_defaults, name):
                    raise ValueError("named identity gates are unsupported by anonymous research trackers")
        else:
            for item in fields(TrackerSettings):
                if item.name not in {"mode", "cosine_threshold", "identity_score_threshold", "identity_margin_threshold", "identity_minimum_evidence_sec"} and getattr(self.tracker, item.name) != getattr(tracker_defaults, item.name):
                    raise ValueError(f"{item.name} is unsupported by the unchanged baseline tracker")
        if self.xvf.mode not in {"none", "tracking_only", "soft_energy", "advisory", "soft_energy_advisory"}:
            raise ValueError("unsupported XVF mode")
        if self.xvf.mode == "tracking_only" and self.tracker.mode in {"baseline", "voice_time"}:
            raise ValueError("tracking_only requires a spatial research tracker; baseline/voice_time ignores it")
        _range(self.xvf.speech_assist_delta, 0.0, 0.15, "speech assist delta")
        _range(self.xvf.minimum_reliability, 0.0, 1.0, "minimum reliability")
        _range(self.xvf.advisory_silence_sec, 0.1, 1.0, "advisory silence")
        _range(self.xvf.advisory_min_utterance_sec, 0.25, 5.0, "advisory minimum utterance")
        if "soft_energy" in self.xvf.mode and self.segmentation.post_policy != "posterior_hysteresis":
            raise ValueError("soft energy assistance requires posterior_hysteresis")
        if self.punctuation.mode != "final_only":
            raise ValueError("punctuation remains final only")
        _range(self.punctuation.partial_display_min_interval_sec, 0.0, 1.0, "partial interval")
        for name in ("asr_threads", "speaker_threads", "punctuation_threads"):
            if getattr(self.runtime, name) not in {1, 2, 4}:
                raise ValueError(f"{name} must be 1/2/4")
        if self.runtime.capture_block_ms not in {10, 20, 50, 100}:
            raise ValueError("capture block must be 10/20/50/100 ms")
        _range(self.runtime.raw_capture_reserve_sec, 10, 120, "capture reserve")

    def apply(self, base: PipelineConfig | None = None) -> PipelineConfig:
        self.validate()
        config = base or PipelineConfig()
        if config.sample_rate != 16000:
            raise ValueError("the fixed model set requires 16 kHz")
        return replace(config,
            input_gain=float(self.input.gain),
            journal_read_ms=self.asr.journal_read_ms,
            endpoint_rule1_silence_sec=self.asr.endpoint_rule1_silence_sec,
            endpoint_rule2_silence_sec=self.asr.endpoint_rule2_silence_sec,
            endpoint_rule3_utterance_sec=self.asr.endpoint_rule3_utterance_sec,
            asr_decoding_method=self.asr.decoding_method,
            asr_max_active_paths=self.asr.max_active_paths,
            asr_blank_penalty=self.asr.blank_penalty,
            segmentation_window_sec=self.segmentation.window_sec,
            segmentation_hop_sec=self.segmentation.hop_sec,
            segmentation_post_policy=self.segmentation.post_policy,
            segmentation_onset=self.segmentation.onset, segmentation_offset=self.segmentation.offset,
            segmentation_speech_fraction_threshold=self.segmentation.speech_fraction_threshold,
            segmentation_overlap_fraction_threshold=self.segmentation.overlap_fraction_threshold,
            embedding_window_sec=self.embedding.window_sec, embedding_hop_sec=self.embedding.hop_sec,
            minimum_rms=self.embedding.minimum_rms,
            clustering_threshold=self.tracker.cosine_threshold,
            identity_score_threshold=self.tracker.identity_score_threshold,
            identity_margin_threshold=self.tracker.identity_margin_threshold,
            identity_minimum_evidence_sec=self.tracker.identity_minimum_evidence_sec,
            partial_display_min_interval_sec=self.punctuation.partial_display_min_interval_sec,
            **asdict(self.runtime))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def effective(self, config: PipelineConfig) -> dict[str, Any]:
        original = PipelineConfig(session_root=config.session_root, profile_root=config.profile_root, assets=config.assets)
        values = asdict(config)
        clean = json.loads(json.dumps(values, default=str, allow_nan=False))
        original_values = asdict(original)
        delta = {key: clean[key] for key, value in values.items() if value != original_values[key]}
        return {"schema_version": "edge-effective-research.v1", "profile": self.to_dict(),
                "profile_sha256": self.digest(), "effective_config": clean, "component_delta_from_B0": delta,
                "input_contract": "supplied mono WAV tap; gain is applied once after native PCM16 journal, no automatic tap switch",
                "clock_contract": "source start after model loading; warm-resident serial availability excludes separately measured loading. Source seconds and measured session elapsed remain separate; no calibrated historical wall join",
                "gallery_mode": "existing baseline enrollment only for baseline tracker; research anonymous trackers have no gallery"}


@dataclass(frozen=True)
class DeliveredSpatialObservation:
    angle_deg: float | None
    available_at_sec: float
    energy: float | None = None
    reliability: float = 1.0
    valid: bool = True
    sequence: int | None = None
    source_start_sec: float | None = None
    source_end_sec: float | None = None


def spatial_is_fresh(observation, now: float, profile: ResearchProfile) -> bool:
    """Require fresh delivery and, when supplied, fresh observed sample support."""
    if observation is None or not observation.valid:
        return False
    source_end = getattr(observation, "source_end_sec", None)
    stamp = observation.available_at_sec if source_end is None else source_end
    return (math.isfinite(stamp) and math.isfinite(observation.available_at_sec)
            and 0 <= now - stamp <= profile.tracker.direction_max_age_sec
            and 0 <= now - observation.available_at_sec <= profile.tracker.direction_max_age_sec
            and math.isfinite(observation.reliability)
            and observation.reliability >= profile.xvf.minimum_reliability)


class JsonSpatialProvider:
    """Causal replay of sanitized telemetry with explicit source-clock availability."""

    allowed = {"angle_deg", "available_at_sec", "energy", "reliability", "valid", "sequence", "source_start_sec", "source_end_sec"}

    def __init__(self, path: Path) -> None:
        rows = [json.loads(line) for line in Path(path).read_text(encoding="utf-8-sig").splitlines() if line.strip()]
        self.rows = []
        for row in rows:
            if set(row) - self.allowed:
                raise ValueError("telemetry must be sanitized; unknown/truth fields are forbidden")
            available = float(row["available_at_sec"])
            end = float(row.get("source_end_sec", available))
            start = float(row.get("source_start_sec", end))
            if not all(math.isfinite(x) for x in (available, start, end)) or start > end or end > available:
                raise ValueError("invalid telemetry source/availability span")
            observation = DeliveredSpatialObservation(**row)
            if observation.angle_deg is not None and (not isinstance(observation.angle_deg, (int, float)) or not math.isfinite(observation.angle_deg) or not 0 <= observation.angle_deg <= 180):
                raise ValueError("native XVF angle must be finite in [0,180] or null")
            if observation.energy is not None and (not isinstance(observation.energy, (int, float)) or not math.isfinite(observation.energy)):
                raise ValueError("energy must be finite or null")
            if not isinstance(observation.reliability, (int, float)) or not math.isfinite(observation.reliability) or not 0 <= observation.reliability <= 1:
                raise ValueError("reliability must be finite in [0,1]")
            if not isinstance(observation.valid, bool):
                raise ValueError("valid must be boolean")
            if observation.sequence is not None and (not isinstance(observation.sequence, int) or isinstance(observation.sequence, bool)):
                raise ValueError("sequence must be integer or null")
            self.rows.append((available, observation))
        # Reordered input is retained in input order for equal-time observations.
        self.rows.sort(key=lambda item: item[0])
        self.path = str(Path(path).resolve())
        self.sha256 = hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def evidence(self, source_start_sec: float, source_end_sec: float):
        # Binary search avoids scanning complete future traces. Only delivery
        # timestamps <= the current sample cursor can be observed.
        import bisect
        index = bisect.bisect_right(self._times, source_end_sec) - 1
        return self.rows[index][1] if index >= 0 else None

    @property
    def _times(self):
        if not hasattr(self, "_cached_times"):
            self._cached_times = [item[0] for item in self.rows]
        return self._cached_times


def segmentation_gate(views: dict[str, Any], config: PipelineConfig, previous_speech: bool,
                      *, speech_assist_delta: float = 0.0) -> dict[str, Any]:
    """Pure actual wrapper used by runtime and dependency-correct replay."""
    import numpy as np
    tail_frames = max(1, round(config.segmentation_hop_sec / 0.016875))
    speech_fraction = float(np.mean(views["speech"][-tail_frames:]))
    overlap_fraction = float(np.mean(views["overlap"][-tail_frames:]))
    speech_threshold = config.segmentation_speech_fraction_threshold
    if config.segmentation_post_policy == "hard_argmax_fraction":
        speech = speech_fraction >= speech_threshold
        overlap = overlap_fraction >= config.segmentation_overlap_fraction_threshold
        posterior = overlap_posterior = None
    elif config.segmentation_post_policy == "posterior_hysteresis":
        posterior = float(np.mean(views["speech_probability"][-tail_frames:]))
        overlap_posterior = float(np.mean(views["overlap_probability"][-tail_frames:]))
        speech_threshold = (config.segmentation_offset if previous_speech else config.segmentation_onset) - speech_assist_delta
        speech = posterior >= max(0.0, speech_threshold)
        overlap = overlap_posterior >= config.segmentation_overlap_fraction_threshold
    else:
        raise ValueError("unsupported segmentation policy")
    return {"speech": bool(speech), "overlap": bool(overlap),
            "speech_fraction": speech_fraction, "overlap_fraction": overlap_fraction,
            "speech_probability": posterior, "overlap_probability": overlap_posterior,
            "speech_threshold_applied": speech_threshold, "speech_assist_delta": speech_assist_delta,
            "post_policy": config.segmentation_post_policy, "tail_frames": tail_frames}


class EndpointAdvisor:
    """A direction proposal can request a reset only after actual audio silence.

    It is an optional wrapper, not a claim that Sherpa exposes direction input.
    Repeated stale telemetry cannot satisfy persistence.
    """
    def __init__(self, profile: ResearchProfile) -> None:
        self.profile = profile
        self.anchor = None
        self.candidate = None
        self.candidate_since = None
        self.pending_until = -1.0
        self.last_delivery = -1.0
        self.last_sequence = None
        self.silence_sec = 0.0

    def observe(self, observation, source_sec: float, block_rms: float, block_sec: float,
                utterance_start_sec: float) -> bool:
        p = self.profile
        self.silence_sec = self.silence_sec + block_sec if block_rms < p.embedding.minimum_rms else 0.0
        qualified = spatial_is_fresh(observation, source_sec, p) and observation.angle_deg is not None and math.isfinite(observation.angle_deg) and 0 <= observation.angle_deg <= 180
        if qualified and observation.sequence is not None and self.last_sequence is not None:
            if observation.sequence < self.last_sequence or (observation.sequence == self.last_sequence and observation.available_at_sec > self.last_delivery):
                qualified = False
        if qualified and observation.available_at_sec > self.last_delivery:
            self.last_delivery = observation.available_at_sec
            if observation.sequence is not None:
                self.last_sequence = observation.sequence
            angle = float(observation.angle_deg)
            # Native XVF bearing is folded to [0,180], so never wrap it.
            distance = lambda a, b: abs(a - b)
            if self.anchor is None:
                self.anchor = angle
            elif distance(angle, self.anchor) >= p.tracker.direction_change_deg:
                if self.candidate is None or distance(angle, self.candidate) > p.tracker.direction_match_deg:
                    self.candidate, self.candidate_since = angle, observation.available_at_sec
                elif observation.available_at_sec - self.candidate_since >= p.tracker.direction_persistence_sec:
                    self.anchor = angle
                    self.candidate = self.candidate_since = None
                    self.pending_until = source_sec + 1.0
            else:
                self.candidate = self.candidate_since = None
        elif not qualified:
            self.candidate = self.candidate_since = None
            self.pending_until = -1.0
        eligible = source_sec <= self.pending_until and self.silence_sec >= p.xvf.advisory_silence_sec
        eligible = eligible and source_sec - utterance_start_sec >= p.xvf.advisory_min_utterance_sec
        if eligible:
            self.pending_until = -1.0
        return bool(eligible)


@dataclass(frozen=True)
class EmbeddingSettingsV2(EmbeddingSettings):
    rms_policy: str = "full_window"
    purity_policy: str = "fraction"
    minimum_clean_fraction: float = 0.8
    minimum_contiguous_clean_sec: float = 0.5
    evidence_policy: str = "fixed"
    early_window_sec: float = 0.5
    cadence_policy: str = "fixed"
    frequent_hop_sec: float = 0.25
    sparse_hop_sec: float = 1.0
    evidence_debt_enabled: bool = False
    voice_observation_floor_sec: float = 1.0
    event_cosine_threshold: float = 0.5
    cadence_cues_enabled: bool = False
    cadence_direction_deg: float = 35.0


@dataclass(frozen=True)
class XVFSettingsV2:
    mode: str = "none"
    minimum_reliability: float = 0.5
    direction_change_deg: float = 35.0
    direction_match_deg: float = 25.0
    direction_persistence_sec: float = 0.75
    advisory_silence_sec: float = 0.30
    advisory_min_utterance_sec: float = 0.5
    endpoint_min_interval_sec: float = 3.0
    endpoint_max_per_minute: int = 6
    endpoint_circuit_breaker_sec: float = 15.0


@dataclass(frozen=True)
class SchedulerSettingsV2:
    mode: str = "causal_watermark"
    revision_horizon_sec: float = 2.0
    max_pending_events: int = 20000
    evidence_expiry_sec: float = 0.75
    max_events: int = 1000000
    max_utterances: int = 4096
    max_revisions_per_utterance: int = 4


def _s6b_default_tracker():
    from .research_tracking_v2 import S6BTrackingConfig
    return S6BTrackingConfig()


@dataclass(frozen=True)
class ResearchProfileV2:
    """Explicit S6B contract; all original profile/v1 semantics stay unchanged."""
    profile_id: str = "S6B_voice"
    schema_version: str = "edge-research-profile.v2"
    input: InputSettings = field(default_factory=InputSettings)
    asr: ASRSettings = field(default_factory=ASRSettings)
    segmentation: SegmentationSettings = field(default_factory=SegmentationSettings)
    embedding: EmbeddingSettingsV2 = field(default_factory=EmbeddingSettingsV2)
    tracker: Any = field(default_factory=_s6b_default_tracker)
    xvf: XVFSettingsV2 = field(default_factory=XVFSettingsV2)
    punctuation: PunctuationSettings = field(default_factory=PunctuationSettings)
    runtime: RuntimeSettings = field(default_factory=lambda: RuntimeSettings(asr_threads=1, speaker_threads=1))
    scheduler: SchedulerSettingsV2 = field(default_factory=SchedulerSettingsV2)

    @classmethod
    def from_dict(cls, value):
        from .research_tracking_v2 import S6BTrackingConfig
        sections = {**_SECTIONS, "embedding": EmbeddingSettingsV2, "tracker": S6BTrackingConfig,
                    "xvf": XVFSettingsV2, "scheduler": SchedulerSettingsV2}
        if not isinstance(value, dict) or set(value) - {"profile_id", "schema_version", *sections}:
            raise ValueError("unsupported v2 profile fields")
        values = {key: _section(sections[key], item) if key in sections else item for key, item in value.items()}
        values.setdefault("tracker", S6BTrackingConfig())
        result = cls(**values)
        result.validate()
        return result

    def _base_profile(self):
        return ResearchProfile(profile_id=self.profile_id, input=self.input, asr=self.asr,
            segmentation=self.segmentation,
            embedding=EmbeddingSettings(self.embedding.window_sec, self.embedding.hop_sec, self.embedding.minimum_rms),
            tracker=TrackerSettings(cosine_threshold=self.tracker.cosine_threshold),
            punctuation=self.punctuation, runtime=self.runtime)

    def validate(self):
        from .research_tracking_v2 import S6BTrackingConfig
        if self.schema_version != "edge-research-profile.v2" or not isinstance(self.tracker, S6BTrackingConfig):
            raise ValueError("v2 profile requires S6BTrackingConfig")
        self._base_profile().validate()
        _section(S6BTrackingConfig, asdict(self.tracker))
        if hasattr(self.tracker, "validate"):
            self.tracker.validate()
        if hasattr(self.tracker, "field_usage") and self.tracker.field_usage()["nondefault_inactive_fields"]:
            raise ValueError("changed inactive tracker knobs: " + str(self.tracker.field_usage()["nondefault_inactive_fields"]))
        for cls, item in ((EmbeddingSettingsV2, self.embedding), (XVFSettingsV2, self.xvf), (SchedulerSettingsV2, self.scheduler)):
            _section(cls, asdict(item))
        e = self.embedding
        if e.rms_policy not in {"dispatch", "full_window"} or e.purity_policy not in {"gate_only", "fraction", "contiguous"}:
            raise ValueError("unsupported RMS/purity policy")
        if e.evidence_policy not in {"fixed", "early_short_long"} or e.cadence_policy not in {"fixed", "sparse", "frequent", "event_driven"}:
            raise ValueError("unsupported evidence/cadence policy")
        _range(e.minimum_clean_fraction, 0.0, 1.0, "clean fraction")
        _range(e.minimum_contiguous_clean_sec, 0.25, 3.0, "contiguous clean duration")
        _range(e.early_window_sec, 0.5, e.window_sec, "early window")
        if e.evidence_policy == "early_short_long" and e.early_window_sec >= e.window_sec:
            raise ValueError("early-short+long requires distinct supported lengths")
        active_hops = ({"frequent_hop_sec", "sparse_hop_sec"} if e.cadence_policy == "event_driven" else
                       {"frequent_hop_sec"} if e.cadence_policy == "frequent" else
                       {"sparse_hop_sec"} if e.cadence_policy == "sparse" else set())
        if e.evidence_debt_enabled:
            active_hops.add("voice_observation_floor_sec")
        for name in active_hops:
            _range(getattr(e, name), e.hop_sec, 3.0, name)
            if abs(getattr(e, name) / e.hop_sec - round(getattr(e, name) / e.hop_sec)) > 1e-8:
                raise ValueError(f"{name} must be an exact dispatch multiple")
        if e.cadence_policy == "event_driven" and e.frequent_hop_sec > e.sparse_hop_sec:
            raise ValueError("frequent cadence cannot be slower than sparse cadence")
        _range(e.event_cosine_threshold, -1.0, 1.0, "event cosine")
        if e.evidence_debt_enabled and e.cadence_policy != "event_driven":
            raise ValueError("evidence debt requires event-driven cadence")
        if e.cadence_cues_enabled and (e.cadence_policy != "event_driven" or self.xvf.mode not in {"tracking_only", "both"}):
            raise ValueError("cue scheduling requires event-driven cadence and an explicit tracking cue route")
        _range(e.cadence_direction_deg, 1.0, 180.0, "cadence direction change")
        defaults = EmbeddingSettingsV2()
        inactive = []
        if e.purity_policy == "gate_only":
            inactive += ["minimum_clean_fraction", "minimum_contiguous_clean_sec"]
        elif e.purity_policy == "fraction":
            inactive += ["minimum_contiguous_clean_sec"]
        if e.evidence_policy == "fixed":
            inactive += ["early_window_sec"]
        if e.cadence_policy == "fixed":
            inactive += ["frequent_hop_sec", "sparse_hop_sec", "event_cosine_threshold"]
        elif e.cadence_policy == "sparse":
            inactive += ["frequent_hop_sec", "event_cosine_threshold"]
        elif e.cadence_policy == "frequent":
            inactive += ["sparse_hop_sec", "event_cosine_threshold"]
        if not e.evidence_debt_enabled:
            inactive += ["voice_observation_floor_sec"]
        if not e.cadence_cues_enabled:
            inactive += ["cadence_direction_deg"]
        for name in inactive:
            if getattr(e, name) != getattr(defaults, name):
                raise ValueError(f"embedding.{name} is inactive under the selected policies")
        if self.xvf.mode not in {"none", "tracking_only", "endpoint_only", "both"}:
            raise ValueError("v2 cue routing must be none/tracking_only/endpoint_only/both")
        if self.tracker.cues_enabled != (self.xvf.mode in {"tracking_only", "both"}):
            raise ValueError("tracker.cues_enabled must exactly match declared XVF routing")
        for name in ("direction_match_deg", "direction_change_deg"):
            _range(getattr(self.xvf, name), 1.0, 180.0, name)
        _range(self.xvf.minimum_reliability, 0.0, 1.0, "XVF reliability")
        _range(self.xvf.direction_persistence_sec, 0.0, 3.0, "endpoint direction persistence")
        _range(self.xvf.advisory_silence_sec, 0.1, 1.0, "endpoint silence")
        _range(self.xvf.advisory_min_utterance_sec, 0.25, 5.0, "endpoint utterance minimum")
        _range(self.xvf.endpoint_min_interval_sec, 0.5, 60.0, "endpoint rate interval")
        _range(self.xvf.endpoint_max_per_minute, 1, 30, "endpoint count limit")
        _range(self.xvf.endpoint_circuit_breaker_sec, 1.0, 120.0, "endpoint breaker duration")
        if self.xvf.mode not in {"endpoint_only", "both"}:
            xvf_defaults = XVFSettingsV2()
            for item in fields(XVFSettingsV2):
                if item.name in {"mode"} or item.name == "minimum_reliability" and e.cadence_cues_enabled:
                    continue
                if getattr(self.xvf, item.name) != getattr(xvf_defaults, item.name):
                    raise ValueError(f"xvf.{item.name} is inactive without endpoint routing")
        if self.scheduler.mode != "causal_watermark":
            raise ValueError("unsupported scheduler")
        _range(self.scheduler.revision_horizon_sec, 0.01, 10.0, "transcript revision horizon")
        _range(self.scheduler.max_pending_events, 100, 100000, "scheduler queue limit")
        _range(self.scheduler.evidence_expiry_sec, 0.01, 3.0, "speaker evidence expiry")
        _range(self.scheduler.max_events, 1000, 2000000, "scheduler total event limit")
        _range(self.scheduler.max_utterances, 10, 10000, "scheduler utterance limit")
        _range(self.scheduler.max_revisions_per_utterance, 1, 16, "per-utterance revision limit")

    def apply(self, base=None):
        self.validate()
        return self._base_profile().apply(base)

    def to_dict(self):
        return asdict(self)

    def digest(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def effective(self, config):
        result = self._base_profile().effective(config)
        result.update(schema_version="edge-effective-research.v2", profile=self.to_dict(), profile_sha256=self.digest(),
            scheduler_contract="incremental sealed lane watermarks; shared upstream modeled clock, policy cost measured separately; actual session elapsed is distinct",
            revision_contract="immutable first display/final labels; bounded forward latest-label corrections; no GUI rewriting",
            gallery_mode="anonymous S6B tracker; original_common is a separate common-scheduler control")
        return result


class EndpointAdvisorV2:
    """N04: endpoint-only causal proposal, reset interval and burst breaker."""
    def __init__(self, profile):
        from types import SimpleNamespace
        # Reuse the established causal/folded observation guard; endpoint
        # thresholds are independent of the identity-tracker's own policy.
        proxy = SimpleNamespace(embedding=profile.embedding, xvf=profile.xvf,
            tracker=SimpleNamespace(direction_max_age_sec=profile.tracker.direction_max_age_sec,
                direction_change_deg=profile.xvf.direction_change_deg,
                direction_match_deg=profile.xvf.direction_match_deg,
                direction_persistence_sec=profile.xvf.direction_persistence_sec))
        self.base = EndpointAdvisor(proxy)
        self.profile = profile
        self.resets = []
        self.last_reset = float("-inf")
        self.disabled_until = 0.0
        self.last_status = {}

    def observe(self, observation, source_sec, block_rms, block_sec, utterance_start_sec):
        proposal = self.base.observe(observation, source_sec, block_rms, block_sec, utterance_start_sec)
        self.resets = [x for x in self.resets if source_sec - x < 60.0]
        reason = "no_proposal"
        accept = False
        if proposal:
            if source_sec < self.disabled_until:
                reason = "circuit_open"
            elif source_sec - self.last_reset < self.profile.xvf.endpoint_min_interval_sec:
                reason = "rate_limited"
            elif len(self.resets) >= self.profile.xvf.endpoint_max_per_minute:
                self.disabled_until = source_sec + self.profile.xvf.endpoint_circuit_breaker_sec
                reason = "circuit_opened"
            else:
                self.resets.append(source_sec)
                self.last_reset = source_sec
                accept, reason = True, "accepted"
        self.last_status = {"proposal": proposal, "accepted": accept, "reason": reason,
                            "advisory_resets_last_minute": len(self.resets), "disabled_until_sec": self.disabled_until}
        return accept
