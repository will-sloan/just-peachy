"""Runtime helpers for pipeline-level diagnostics."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Mapping

from app.inference_pipeline.contracts import RuntimeStats
from app.inference_pipeline.typing import JsonObject


@dataclass
class RuntimeAccumulator:
    """Collect per-stage wall-clock timings for one prediction."""

    device: str = "cpu"
    started_at: float = field(default_factory=time.perf_counter)
    stages: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        stage_started_at = time.perf_counter()
        try:
            yield
        finally:
            self.stages[name] = self.stages.get(name, 0.0) + (
                time.perf_counter() - stage_started_at
            )

    @property
    def total_sec(self) -> float:
        return time.perf_counter() - self.started_at

    def stats(
        self,
        *,
        counters: Mapping[str, object] | None = None,
        model_versions: Mapping[str, object] | None = None,
    ) -> RuntimeStats:
        return RuntimeStats(
            total_sec=self.total_sec,
            audio_load_sec=self.stages.get("audio_load"),
            vad_sec=self.stages.get("vad"),
            diarization_sec=self.stages.get("diarization"),
            asr_sec=self.stages.get("asr"),
            speaker_sec=self.stages.get("speaker"),
            postprocess_sec=self.stages.get("postprocess"),
            device=self.device,
            model_versions=dict(model_versions or {}) or None,
            counters=dict(counters or {}) or None,
        )


def runtime_realtime_factor(
    runtime_sec: float | None,
    audio_duration_sec: float | None,
) -> float | None:
    """Return runtime / audio duration when duration is known."""

    if runtime_sec is None or audio_duration_sec is None or audio_duration_sec <= 0:
        return None
    return runtime_sec / audio_duration_sec


def runtime_diagnostics(
    runtime_stats: RuntimeStats,
    *,
    audio_duration_sec: float | None,
) -> JsonObject:
    """Return JSON-safe pipeline timing diagnostics."""

    stage_breakdown = {
        "audio_load_sec": runtime_stats.audio_load_sec,
        "vad_sec": runtime_stats.vad_sec,
        "diarization_sec": runtime_stats.diarization_sec,
        "asr_sec": runtime_stats.asr_sec,
        "speaker_sec": runtime_stats.speaker_sec,
        "postprocess_sec": runtime_stats.postprocess_sec,
    }
    return {
        "total_sec": runtime_stats.total_sec,
        "audio_duration_sec": audio_duration_sec,
        "realtime_factor": runtime_realtime_factor(
            runtime_stats.total_sec,
            audio_duration_sec,
        ),
        "stage_breakdown_sec": stage_breakdown,
        "device": runtime_stats.device,
        "model_versions": runtime_stats.model_versions,
        "counters": runtime_stats.counters,
    }
