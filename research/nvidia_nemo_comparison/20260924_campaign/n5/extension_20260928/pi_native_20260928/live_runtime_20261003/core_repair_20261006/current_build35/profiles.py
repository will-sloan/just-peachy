"""Independent source/backend settings and source-validated geometry. See README_PIPELINES.md."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math

MODEL_SHA256 = "08456d9e22cd9a323c0364d98375f3746d6e68507ebb705cd46438c534c7a3a1"
RUNTIME_REVISION = "97a15afa5caa9bce5baaa86c1184103877af4101"
MODEL_CARD_URL = "https://huggingface.co/nvidia/Nemotron-3-Diarization/blob/main/README.md"
NOMINAL_FRAME_SECONDS = 0.08


def _integer(value, low, high=2**31 - 1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Exact bounded integer required")
    return value


@dataclass(frozen=True)
class ModelLimits:
    # Read from the existing pinned GGUF metadata; no model execution.
    speakers: int = 8
    silence_frames_per_speaker: int = 1
    position_frames: int = 5000


@dataclass(frozen=True)
class Geometry:
    chunk_frames: int
    right_context_frames: int
    left_context_frames: int = 0
    fifo_frames: int = 264
    spkcache_frames: int = 264
    update_period_frames: int = 222
    preset: str = "v3-streaming"
    gpu: int = -1

    @property
    def nominal_input_seconds(self):
        """Audio buffering only, excluding compute, scheduling and capture delays."""
        return (self.chunk_frames + self.right_context_frames) * NOMINAL_FRAME_SECONDS


_PRESETS = {
    "v3-streaming": Geometry(13, 1, 0, 80, 264, 40),
    "v3-offline": Geometry(264, 1, 1, 0, 264, 188, "v3-offline"),
}


def effective_c_abi_geometry(geometry):
    """Mirror c_api.cpp override rules, including its zero FIFO/right behavior."""
    if not isinstance(geometry, Geometry) or geometry.preset not in _PRESETS:
        raise ValueError("Explicit supported native preset required")
    base = asdict(_PRESETS[geometry.preset])
    for key in ("chunk_frames", "right_context_frames", "fifo_frames",
                "spkcache_frames", "update_period_frames"):
        value = getattr(geometry, key)
        if value > 0:
            base[key] = value
    if geometry.left_context_frames >= 0:
        base["left_context_frames"] = geometry.left_context_frames
    base.update(preset=geometry.preset, gpu=geometry.gpu)
    return Geometry(**base)


def validate_geometry(geometry, model_limits=ModelLimits()):
    """Source-equivalent checks; this is never a native ABI or quality pass."""
    if not isinstance(geometry, Geometry) or not isinstance(model_limits, ModelLimits):
        raise ValueError("Geometry and explicit model limits required")
    for key in ("chunk_frames", "update_period_frames", "spkcache_frames"):
        _integer(getattr(geometry, key), 1)
    for key in ("fifo_frames", "left_context_frames", "right_context_frames"):
        _integer(getattr(geometry, key), 0)
    if type(geometry.gpu) is not int or geometry.gpu != -1:
        raise ValueError("This release is CPU only")
    _integer(model_limits.speakers, 1, 8)
    _integer(model_limits.silence_frames_per_speaker, 0, 5000)
    _integer(model_limits.position_frames, 1, 2**31 - 1)
    minimum = (1 + model_limits.silence_frames_per_speaker) * model_limits.speakers
    if geometry.spkcache_frames < minimum:
        raise ValueError("Speaker cache below native silence/speaker minimum")
    total = sum(getattr(geometry, k) for k in ("spkcache_frames", "fifo_frames",
                "left_context_frames", "chunk_frames", "right_context_frames"))
    if total > model_limits.position_frames:
        raise ValueError("Geometry exceeds native positional encoding limit")
    if effective_c_abi_geometry(geometry) != geometry:
        raise ValueError("C ABI ignores zero FIFO/right override; choose a matching preset")
    return {"status": "SOURCE_PARAMETER_RULES_VALIDATED", "sequence_frames": total,
            "minimum_cache_frames": minimum, "native_execution": False,
            "model_sha256": MODEL_SHA256, "runtime_revision": RUNTIME_REVISION}


@dataclass(frozen=True)
class Profile:
    id: str
    label: str
    geometry: Geometry
    provenance: str
    experimental: bool
    retained_mode: str | None = None
    retained_unpaced_rtf: float | None = None
    retained_source_wait_seconds: float | None = None

    @property
    def native_name(self):
        return {"current_delayed": "native_v3_delayed", "streaming": "native_v3_streaming",
                "chunk52": "native_cm5_chunk52", "chunk52_threads2": "native_cm5_chunk52"}.get(self.id, "live_20261003_" + self.id)

    def descriptor(self):
        result = asdict(self)
        result.update(nominal_input_seconds=self.geometry.nominal_input_seconds,
                      native_name=self.native_name,
                      input_buffer_excludes_compute=True, native_pass_claimed=False,
                      realtime_qualified=False, speaker_accuracy_qualified=False,
                      parameter_validation=validate_geometry(self.geometry))
        if self.id == "chunk52_threads2":
            result.update(required_native_variant="chunk52-native-threads2",
                          configured_native_graph_threads=2,
                          measured_component_review_sha256="8ef69dd6333c2a1432cb08fd34a905c60c49044cce869b89b43fc7cb3a926ef6")
        return result


_PROFILES = (
    Profile("current_delayed", "CurrentDelayed", _PRESETS["v3-offline"],
            "retained:d1-geometry-delayed-lru1-v1", False, "delayed",
            0.40478771333206454, 21.3),
    Profile("chunk52", "Chunk52", Geometry(52, 1, 0, 80, 264, 40),
            "retained:d1-geometry-chunk52-a76-v1", True, "chunk52",
            1.0851342303786364, 4.3),
    Profile("chunk52_threads2", "Chunk52: two native graph threads (experimental)", Geometry(52, 1, 0, 80, 264, 40),
            "2026-10-03 chunk52-threads2-01: same-source component numerical pass; whole-pipeline and sustained unqualified", True),
    Profile("streaming", "Streaming", _PRESETS["v3-streaming"],
            "retained:d1-geometry-stream-lru8-a76-v1", True, "streaming",
            3.633745760425762, 1.2),
    Profile("official_low", "Official low latency", Geometry(9, 4),
            "NVIDIA Nemotron 3 model card, verified 2026-10-03", True),
    Profile("official_very_low", "Official very low latency", Geometry(6, 2),
            "NVIDIA Nemotron 3 model card, verified 2026-10-03", True),
    Profile("official_ultra_low", "Official ultra low latency", Geometry(3, 1),
            "NVIDIA Nemotron 3 model card, verified 2026-10-03", True),
    Profile("candidate_1_2", "Candidate 1.20 s input", Geometry(14, 1, 0, 80, 264, 40),
            "local intermediate candidate; native untested", True),
    Profile("candidate_2", "Candidate 2.00 s input", Geometry(24, 1, 0, 80, 264, 40),
            "2026-10-03 candidate2-01: complete short component RTF 2.1233; quality and sustained unqualified", True),
    Profile("candidate_3", "Candidate 3.04 s input", Geometry(37, 1, 0, 80, 264, 40),
            "local intermediate candidate; native untested", True),
    Profile("candidate_4_5", "Candidate 4.48 s input", Geometry(55, 1, 0, 80, 264, 40),
            "2026-10-03 candidate55-01: complete short component RTF 1.1091; quality and sustained unqualified", True),
    Profile("candidate_3_compact", "Candidate 3.04 s compact context", Geometry(37, 1, 0, 40, 128, 40),
            "2026-10-03 compact3-02: complete short component RTF 0.8568; reduced history, quality and sustained unqualified", True),
)


def get_profile(profile_id):
    for profile in _PROFILES:
        if profile.id == profile_id:
            return profile
    raise ValueError("Unknown profile; implicit fallback is forbidden")


def catalog():
    return [p.descriptor() for p in _PROFILES]


@dataclass(frozen=True)
class RuntimeSelection:
    diarizer: str = "pyannote"
    embedding: str = "redimnet"
    input_source: str = "live"
    nemotron_profile: str | None = None
    allow_experimental: bool = False
    provisional_correction: bool = False
    refinement_profile: str = "current_delayed"
    revision_window_seconds: int = 30
    refinement_period_seconds: int = 5
    embedding_schedule: str = "continuous"
    embedding_refresh_seconds: float = 2.0
    speaker_attribution: str = "retained"
    optional_d1_refiner: bool = False

    def validate(self):
        if self.diarizer not in ("pyannote", "nemotron"):
            raise ValueError("Choose Pyannote or Nemotron")
        if self.embedding not in ("redimnet", "titanet", "anonymous"):
            raise ValueError("Choose ReDimNet, TitaNet or anonymous")
        if self.input_source not in ("live", "saved"):
            raise ValueError("Choose live or saved input independently")
        if self.embedding_schedule not in ("continuous", "sparse_clean_turn"):
            raise ValueError("Unknown embedding schedule")
        if self.speaker_attribution not in ("retained", "single_d1_late_labels"):
            raise ValueError("Unknown speaker attribution mode")
        if self.speaker_attribution == "single_d1_late_labels" and (
                self.diarizer != "nemotron" or not self.allow_experimental):
            raise ValueError("ASR-first delayed attribution requires experimental Nemotron")
        if (type(self.embedding_refresh_seconds) not in (int, float) or
                not math.isfinite(self.embedding_refresh_seconds) or
                not .5 <= self.embedding_refresh_seconds <= 120):
            raise ValueError("Embedding refresh must be finite, from 0.5 to 120 seconds")
        if self.embedding_schedule == "sparse_clean_turn" and (
                self.diarizer != "nemotron" or self.embedding == "anonymous" or
                not self.allow_experimental):
            raise ValueError("Sparse clean-turn schedule requires experimental Nemotron with named embeddings")
        if any(type(v) is not bool for v in (self.allow_experimental, self.provisional_correction, self.optional_d1_refiner)):
            raise ValueError("Exact flags required")
        _integer(self.revision_window_seconds, 1, 300)
        _integer(self.refinement_period_seconds, 1, self.revision_window_seconds)
        get_profile(self.refinement_profile)
        if self.optional_d1_refiner and (
                self.diarizer != "pyannote" or not self.allow_experimental or
                self.provisional_correction or self.speaker_attribution != "retained" or
                self.refinement_profile != "current_delayed"):
            raise ValueError("Optional delayed-D1 refinement requires experimental Pyannote primary and retained attribution")
        if self.diarizer == "pyannote":
            if self.nemotron_profile is not None or self.provisional_correction:
                raise ValueError("Nemotron geometry/correction requires Nemotron")
        else:
            profile = get_profile(self.nemotron_profile)
            validate_geometry(profile.geometry)
            if (profile.experimental or self.provisional_correction) and not self.allow_experimental:
                raise ValueError("Explicit experimental opt-in required")
            if self.provisional_correction:
                validate_geometry(get_profile(self.refinement_profile).geometry)
        return asdict(self)


@dataclass(frozen=True)
class SessionPolicy:
    maximum_session_seconds: int = 300
    developer_soak: bool = False
    max_drain_seconds: int = 120
    max_backlog_seconds: int | None = 120
    model_load_seconds: int = 120
    cleanup_seconds: int = 60
    manual_stop: bool = False

    def validate(self):
        _integer(self.maximum_session_seconds, 1, 2**31-1 if self.manual_stop else 86400)
        if type(self.manual_stop) is not bool:
            raise ValueError('Explicit manual-stop policy flag required')
        if type(self.developer_soak) is not bool:
            raise ValueError("Explicit developer flag required")
        for value in (self.model_load_seconds, self.cleanup_seconds):
            _integer(value, 1, 86400)
        _integer(self.max_drain_seconds, 1, max(120, self.maximum_session_seconds) if self.manual_stop else 86400)
        if self.max_backlog_seconds is not None:
            _integer(self.max_backlog_seconds, 1, 86400)
        if self.developer_soak and self.maximum_session_seconds < 3600:
            raise ValueError("Developer soak must explicitly reserve at least 3600 seconds")
        if not self.developer_soak and not self.manual_stop and self.maximum_session_seconds > 300:
            raise ValueError("Long sessions need explicit developer soak policy")
        if not self.developer_soak and not self.manual_stop and self.max_drain_seconds > 120:
            raise ValueError("Extended processing drain needs explicit developer soak policy")
        return asdict(self)

    @property
    def total_deadline_seconds(self):
        self.validate()
        return (self.maximum_session_seconds + self.model_load_seconds +
                self.max_drain_seconds + self.cleanup_seconds)

    def maximum_samples(self, sample_rate=16000):
        self.validate()
        return _integer(sample_rate, 1, 192000) * self.maximum_session_seconds

    def expired(self, elapsed_seconds):
        self.validate()
        if type(elapsed_seconds) not in (int, float) or not math.isfinite(elapsed_seconds) or elapsed_seconds < 0:
            raise ValueError("Finite nonnegative elapsed time required")
        return elapsed_seconds >= self.maximum_session_seconds


def main():
    """Print configuration only; use the registered README launch commands."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("--diarizer", choices=("pyannote", "nemotron"), default="pyannote")
    parser.add_argument("--embedding", choices=("redimnet", "titanet", "anonymous"), default="redimnet")
    parser.add_argument("--source", choices=("live", "saved"), default="live")
    parser.add_argument("--profile")
    parser.add_argument("--experimental", action="store_true")
    parser.add_argument("--provisional", action="store_true")
    parser.add_argument("--refinement-profile", default="current_delayed")
    parser.add_argument("--revision-window", type=int, default=30)
    parser.add_argument("--refinement-period", type=int, default=5)
    parser.add_argument("--embedding-schedule", choices=("continuous", "sparse_clean_turn"), default="continuous")
    parser.add_argument("--embedding-refresh", type=float, default=2.0)
    parser.add_argument("--speaker-attribution", choices=("retained", "single_d1_late_labels"), default="retained")
    parser.add_argument("--optional-d1-refiner", action="store_true")
    parser.add_argument("--duration", type=int, default=300)
    parser.add_argument("--developer-soak", action="store_true")
    parser.add_argument("--drain", type=int, default=120)
    parser.add_argument("--backlog", type=int, default=120)
    args = parser.parse_args()
    selection = RuntimeSelection(args.diarizer, args.embedding, args.source, args.profile,
        args.experimental, args.provisional, args.refinement_profile,
        args.revision_window, args.refinement_period,
        args.embedding_schedule, args.embedding_refresh, args.speaker_attribution, args.optional_d1_refiner)
    policy = SessionPolicy(args.duration, args.developer_soak, args.drain, args.backlog)
    result = {"native_execution": False, "configuration_only": True}
    if args.catalog:
        result["catalog"] = catalog()
    else:
        result.update(selection=selection.validate(), policy=policy.validate(),
                      total_deadline_seconds=policy.total_deadline_seconds)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
