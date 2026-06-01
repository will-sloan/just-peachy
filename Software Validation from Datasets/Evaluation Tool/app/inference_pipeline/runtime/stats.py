"""Small runtime timing helpers for pipeline diagnostics."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, Mapping

from app.inference_pipeline.contracts import RuntimeStats
from app.inference_pipeline.typing import JsonObject


@dataclass
class StageRuntimeTracker:
    """Collect per-stage runtime without binding the pipeline to one backend."""

    device: str = "cpu"
    started_at: float = field(default_factory=time.perf_counter)
    stage_seconds: dict[str, float] = field(default_factory=dict)

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started_at = time.perf_counter()
        try:
            yield
        finally:
            elapsed = time.perf_counter() - started_at
            self.stage_seconds[name] = self.stage_seconds.get(name, 0.0) + elapsed

    @property
    def total_sec(self) -> float:
        return time.perf_counter() - self.started_at

    def to_runtime_stats(
        self,
        *,
        counters: Mapping[str, object] | None = None,
        model_versions: Mapping[str, object] | None = None,
    ) -> RuntimeStats:
        speaker_sec = self.stage_seconds.get("speaker_embedding")
        speaker_sec = (speaker_sec or 0.0) + (self.stage_seconds.get("speaker_matching") or 0.0)
        speaker_sec = speaker_sec + (self.stage_seconds.get("speaker_labeling") or 0.0)
        return RuntimeStats(
            total_sec=self.total_sec,
            audio_load_sec=self.stage_seconds.get("audio_load"),
            vad_sec=self.stage_seconds.get("vad"),
            asr_sec=self.stage_seconds.get("asr"),
            speaker_sec=speaker_sec or None,
            postprocess_sec=self.stage_seconds.get("postprocess"),
            device=self.device,
            model_versions=dict(model_versions or {}),
            counters=dict(counters) if counters is not None else None,
        )

    def to_diagnostics(self, *, audio_duration_sec: float | None = None) -> JsonObject:
        total = self.total_sec
        realtime_factor = (
            total / audio_duration_sec
            if audio_duration_sec is not None and audio_duration_sec > 0
            else None
        )
        return {
            "total_sec": total,
            "audio_duration_sec": audio_duration_sec,
            "pipeline_realtime_factor": realtime_factor,
            "stage_seconds": dict(sorted(self.stage_seconds.items())),
            "stage_realtime_factors": _stage_realtime_factors(
                self.stage_seconds,
                audio_duration_sec,
            ),
        }


def _stage_realtime_factors(
    stage_seconds: Mapping[str, float],
    audio_duration_sec: float | None,
) -> JsonObject:
    if audio_duration_sec is None or audio_duration_sec <= 0:
        return {}
    return {
        stage: seconds / audio_duration_sec
        for stage, seconds in sorted(stage_seconds.items())
    }
