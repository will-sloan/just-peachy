from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(slots=True)
class RuntimeConfig:
    preferred_providers: list[str] = field(default_factory=lambda: ["CPUExecutionProvider"])
    intra_op_num_threads: int | None = None
    inter_op_num_threads: int | None = None


@dataclass(slots=True)
class VadConfig:
    enabled: bool = False
    backend: str = "silero_onnx"
    model_path: str | None = None
    sample_rate: int = 16000
    trim_only: bool = True


@dataclass(slots=True)
class AsrConfig:
    backend: str = "sherpa_whisper"
    model_dir: str | None = None
    sample_rate: int = 16000
    language: str | None = None
    task: str | None = None


@dataclass(slots=True)
class SpeakerConfig:
    enabled: bool = False
    backend: str = "wespeaker_campplus_onnx"
    model_path: str | None = None
    sample_rate: int = 16000


@dataclass(slots=True)
class PunctuationConfig:
    enabled: bool = False
    backend: str = "sherpa_punctuation"
    model_dir: str | None = None


@dataclass(slots=True)
class EnrollmentConfig:
    enabled: bool = False
    store_path: str = "data/enrollment_store.json"


@dataclass(slots=True)
class ThresholdConfig:
    accept_threshold: float = 0.72
    margin_threshold: float = 0.05
    unknown_label: str = "Unknown"


@dataclass(slots=True)
class PipelineConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    speaker: SpeakerConfig = field(default_factory=SpeakerConfig)
    punctuation: PunctuationConfig = field(default_factory=PunctuationConfig)
    enrollment: EnrollmentConfig = field(default_factory=EnrollmentConfig)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineConfig":
        return cls(
            runtime=RuntimeConfig(**data.get("runtime", {})),
            vad=VadConfig(**data.get("vad", {})),
            asr=AsrConfig(**data.get("asr", {})),
            speaker=SpeakerConfig(**data.get("speaker", {})),
            punctuation=PunctuationConfig(**data.get("punctuation", {})),
            enrollment=EnrollmentConfig(**data.get("enrollment", {})),
            thresholds=ThresholdConfig(**data.get("thresholds", {})),
        )


def load_pipeline_config(path: str | Path) -> PipelineConfig:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PipelineConfig.from_dict(data)
