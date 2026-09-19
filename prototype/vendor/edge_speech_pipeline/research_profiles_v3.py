"""Strict opt-in S6C configuration. See README_RESEARCH_S6C.md."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace, fields
import hashlib
import json
from pathlib import Path
import math

from .research_profiles import (ASRSettings, SegmentationSettings, PunctuationSettings, RuntimeSettings,
    XVFSettingsV2, SchedulerSettingsV2, ResearchProfile, TrackerSettings, EmbeddingSettings,
    InputSettings, _section, _range)


@dataclass(frozen=True)
class InputSettingsV3:
    asr_tap: str = "O0"
    identity_tap: str = "O0"
    gain: float = 1.0
    already_gained: bool = True
    common_origin: str = "paired_capture_sample_zero"
    source_block_ms: int = 100


@dataclass(frozen=True)
class EvidenceSettingsV3:
    evidence_policy: str = "dual"
    window_sec: float = 1.5
    hop_sec: float = .25
    short_window_sec: float = .5
    short_hop_sec: float = .25
    mature_hop_sec: float = .5
    minimum_rms: float = .002
    rms_policy: str = "full_window"
    purity_policy: str = "fraction"
    minimum_clean_fraction: float = .8
    minimum_contiguous_clean_sec: float = .45
    clipping_fraction_max: float = 1.0
    cadence_policy: str = "fixed"
    sparse_hop_sec: float = 1.
    uncertainty_cosine: float = .5
    voice_observation_floor_sec: float = 1.
    debt_target_unique_sec: float = 2.
    debt_target_disjoint_count: int = 2
    cadence_cues_enabled: bool = False
    cadence_direction_deg: float = 35.


@dataclass(frozen=True)
class IdentitySettingsV3:
    mode: str = "none"
    score_threshold: float = .5128856897354127
    margin_threshold: float = .03
    minimum_unique_sec: float = 2.
    minimum_disjoint_count: int = 2
    query_policy: str = "mature"
    display_tentative: bool = True
    prototype_update_cosine: float = .45
    severe_query_cosine: float = .2
    max_gallery_profiles: int = 256
    max_track_states: int = 256
    max_intervals: int = 256
    max_prototypes: int = 8
    name_memory_sec: float = 30.


@dataclass(frozen=True)
class RuntimeSettingsV3(RuntimeSettings):
    lane_drain_timeout_sec: float = 600.


def _tracker():
    from .research_tracking_v3 import S6CTrackingConfig
    return S6CTrackingConfig.from_mapping({})


@dataclass(frozen=True)
class ResearchProfileV3:
    profile_id: str = "S6C_voice_empty"
    schema_version: str = "edge-research-profile.v3"
    input: InputSettingsV3 = field(default_factory=InputSettingsV3)
    asr: ASRSettings = field(default_factory=ASRSettings)
    segmentation: SegmentationSettings = field(default_factory=lambda: SegmentationSettings(hop_sec=.5, post_policy="posterior_hysteresis"))
    embedding: EvidenceSettingsV3 = field(default_factory=EvidenceSettingsV3)
    tracker: object = field(default_factory=_tracker)
    identity: IdentitySettingsV3 = field(default_factory=IdentitySettingsV3)
    xvf: XVFSettingsV2 = field(default_factory=XVFSettingsV2)
    scheduler: SchedulerSettingsV2 = field(default_factory=SchedulerSettingsV2)
    punctuation: PunctuationSettings = field(default_factory=PunctuationSettings)
    runtime: RuntimeSettingsV3 = field(default_factory=lambda: RuntimeSettingsV3(asr_threads=1, speaker_threads=1))

    @classmethod
    def from_dict(cls, value):
        from .research_tracking_v3 import S6CTrackingConfig
        sections = {"input": InputSettingsV3, "asr": ASRSettings, "segmentation": SegmentationSettings,
            "embedding": EvidenceSettingsV3, "identity": IdentitySettingsV3, "xvf": XVFSettingsV2,
            "scheduler": SchedulerSettingsV2, "punctuation": PunctuationSettings, "runtime": RuntimeSettingsV3}
        if not isinstance(value, dict) or set(value) - {"schema_version", "profile_id", "tracker", *sections}:
            raise ValueError("unsupported S6C profile fields")
        kwargs = {k: _section(sections[k], v) if k in sections else v for k, v in value.items() if k != "tracker"}
        kwargs["tracker"] = S6CTrackingConfig.from_mapping(value.get("tracker", {}))
        result = cls(**kwargs)
        result.validate()
        return result

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    def _base(self):
        return ResearchProfile(profile_id=self.profile_id, input=InputSettings(self.input.asr_tap, 1., True),
            asr=self.asr, segmentation=self.segmentation,
            embedding=EmbeddingSettings(self.embedding.window_sec, self.embedding.hop_sec, self.embedding.minimum_rms),
            tracker=TrackerSettings(), punctuation=self.punctuation,
            runtime=RuntimeSettings(**{f.name:getattr(self.runtime,f.name) for f in fields(RuntimeSettings)}))

    def validate(self):
        if self.schema_version != "edge-research-profile.v3":
            raise ValueError("S6C requires profile schema v3")
        self._base().validate()
        self.tracker.validated()
        if self.tracker.field_usage()["nondefault_inactive_fields"]:
            raise ValueError("changed inactive S6C tracker knobs")
        _section(RuntimeSettingsV3, asdict(self.runtime))
        _range(self.runtime.lane_drain_timeout_sec, .01, 3600., "native lane drain timeout")
        for name, typ in (("input", InputSettingsV3), ("embedding", EvidenceSettingsV3),
                          ("identity", IdentitySettingsV3), ("xvf", XVFSettingsV2), ("scheduler", SchedulerSettingsV2)):
            _section(typ, asdict(getattr(self, name)))
        if self.input.asr_tap not in {"O0", "O1"} or self.input.identity_tap not in {"O0", "O1"}:
            raise ValueError("S6C routes require explicit O0/O1 declarations")
        if self.input.gain != 1. or not self.input.already_gained or self.input.common_origin != "paired_capture_sample_zero":
            raise ValueError("S6C requires admitted once-gained paired-origin inputs consumed at unity")
        if self.input.source_block_ms not in {20, 50, 100, 200}:
            raise ValueError("invalid paired producer block")
        e = self.embedding
        if e.evidence_policy not in {"dual", "short_only", "mature_only"}:
            raise ValueError("unsupported short/mature evidence policy")
        if e.rms_policy not in {"dispatch", "full_window"} or e.purity_policy not in {"gate_only", "fraction", "contiguous"}:
            raise ValueError("unsupported evidence RMS/purity")
        _range(e.short_window_sec, .5, 3., "short window")
        if e.evidence_policy == "dual" and e.short_window_sec >= e.window_sec:
            raise ValueError("dual evidence requires distinct short and longer mature windows")
        for name in ("short_hop_sec", "mature_hop_sec", "sparse_hop_sec", "voice_observation_floor_sec"):
            _range(getattr(e, name), e.hop_sec, 3., name)
            if abs(getattr(e, name) / e.hop_sec - round(getattr(e, name) / e.hop_sec)) > 1e-8:
                raise ValueError(name + " must be an exact evidence dispatch multiple")
        _range(e.minimum_clean_fraction, 0., 1., "clean fraction")
        _range(e.minimum_contiguous_clean_sec, 0., 3., "contiguous clean")
        _range(e.clipping_fraction_max, 0., 1., "clipping fraction")
        _range(e.debt_target_unique_sec, .5, 30., "debt unique target")
        _range(e.debt_target_disjoint_count, 1, 64, "debt disjoint target")
        _range(e.uncertainty_cosine, -1., 1., "uncertainty cosine")
        _range(e.cadence_direction_deg, 1., 180., "cadence direction")
        if e.cadence_policy not in {"fixed", "frequent", "sparse", "uncertainty"}:
            raise ValueError("unsupported evidence cadence")
        if self.xvf.mode not in {"none", "tracking_only", "endpoint_only", "both"}:
            raise ValueError("unsupported cue route")
        if bool(getattr(self.tracker, "cues_enabled", False)) != (self.xvf.mode in {"tracking_only", "both"}):
            raise ValueError("tracker cues must match declared routing")
        if e.cadence_cues_enabled and (e.cadence_policy != "uncertainty" or self.xvf.mode not in {"tracking_only", "both"}):
            raise ValueError("cue cadence requires uncertainty cadence and tracking cue route")
        for name in ("direction_change_deg", "direction_match_deg"):
            _range(getattr(self.xvf, name), 1., 180., name)
        for name, lo, hi in (("minimum_reliability", 0., 1.), ("direction_persistence_sec", 0., 3.),
            ("advisory_silence_sec", .1, 1.), ("advisory_min_utterance_sec", .25, 5.),
            ("endpoint_min_interval_sec", .5, 60.), ("endpoint_max_per_minute", 1, 30),
            ("endpoint_circuit_breaker_sec", 1., 120.)):
            _range(getattr(self.xvf, name), lo, hi, name)
        i = self.identity
        if i.mode not in {"none", "post_association"} or i.query_policy not in {"any", "mature"}:
            raise ValueError("only empty or actual post-association gallery naming is supported")
        if i.mode == "post_association" and i.query_policy == "mature" and e.evidence_policy == "short_only":
            raise ValueError("short-only inference cannot execute a mature-only naming query; choose explicit any policy")
        for name in ("score_threshold", "prototype_update_cosine", "severe_query_cosine"):
            _range(getattr(i, name), -1., 1., name)
        _range(i.margin_threshold, 0., 2., "identity margin")
        _range(i.minimum_unique_sec, 0., 60., "identity unique duration")
        _range(i.name_memory_sec, 0., 120., "name memory")
        for name, low, high in (("minimum_disjoint_count", 1, 64), ("max_gallery_profiles", 1, 1024),
            ("max_track_states", 1, 1024), ("max_intervals", 8, 4096), ("max_prototypes", 1, 64)):
            _range(getattr(i, name), low, high, name)
        s = self.scheduler
        if s.mode != "causal_watermark":
            raise ValueError("only shared causal watermark scheduler supported")
        _range(s.revision_horizon_sec, 0., 5., "revision horizon")
        _range(s.evidence_expiry_sec, .01, 3., "evidence expiry")
        for name, high in (("max_pending_events", 100000), ("max_events", 2000000), ("max_utterances", 10000), ("max_revisions_per_utterance", 16)):
            _range(getattr(s, name), 1, high, name)
        inactive = self.field_usage()["nondefault_inactive_fields"]
        if inactive:
            raise ValueError("changed inactive S6C knobs: " + str(inactive))

    def field_usage(self):
        inactive = []
        e = self.embedding
        if e.cadence_policy != "uncertainty":
            inactive.extend(("embedding." + x) for x in ("uncertainty_cosine", "voice_observation_floor_sec", "cadence_cues_enabled", "debt_target_unique_sec", "debt_target_disjoint_count"))
        if e.cadence_policy in {"fixed", "frequent"}:
            inactive.append("embedding.sparse_hop_sec")
        if not e.cadence_cues_enabled:
            inactive.append("embedding.cadence_direction_deg")
        if e.purity_policy == "gate_only":
            inactive += ["embedding.minimum_clean_fraction", "embedding.minimum_contiguous_clean_sec"]
        elif e.purity_policy == "fraction":
            inactive.append("embedding.minimum_contiguous_clean_sec")
        if e.evidence_policy == "mature_only":
            inactive += ["embedding.short_window_sec", "embedding.short_hop_sec"]
        if self.identity.mode == "none":
            inactive.extend("identity." + f.name for f in fields(IdentitySettingsV3) if f.name != "mode")
        elif self.identity.query_policy == "any":
            inactive.append("identity.name_memory_sec")
        if self.xvf.mode not in {"endpoint_only", "both"}:
            inactive.extend("xvf." + f.name for f in fields(XVFSettingsV2) if f.name != "mode" and not (f.name == "minimum_reliability" and e.cadence_cues_enabled))
        inactive += ["runtime.capture_block_ms", "runtime.raw_capture_reserve_sec"]
        defaults = {"embedding": EvidenceSettingsV3(), "identity": IdentitySettingsV3(), "xvf": XVFSettingsV2(), "runtime": RuntimeSettingsV3()}
        changed = [p for p in inactive if getattr(getattr(self, p.split('.')[0]), p.split('.')[1]) != getattr(defaults[p.split('.')[0]], p.split('.')[1])]
        return {"inactive_fields": sorted(set(inactive)), "nondefault_inactive_fields": sorted(set(changed))}

    def apply(self, base=None):
        self.validate()
        return self._base().apply(base)

    def to_dict(self):
        result = asdict(self)
        result["tracker"] = self.tracker.to_dict()
        return result

    def digest(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def effective(self, config):
        return {"schema_version": "edge-effective-research.v3", "profile": self.to_dict(), "profile_sha256": self.digest(),
            "field_usage": self.field_usage(), "gallery_mode": self.identity.mode,
            "tracker_field_usage": self.tracker.field_usage(),
            "model_weights_changed": False, "input_gain": config.input_gain,
            "timing_policy": "serial measured upstream source-clock lanes; tracker/resolver cost separate; native release/wall separately observed",
            "identity_policy": "post-association names never feed anonymous association; no evaluator naming",
            "evidence_policy": "one ReDimNet instance; separate real contiguous short/mature calls; unique clean intervals unioned"}
