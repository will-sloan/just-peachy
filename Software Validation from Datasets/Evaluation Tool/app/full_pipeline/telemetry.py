"""Live adapter over the repository's existing resource telemetry sampler."""

from __future__ import annotations

import os
from pathlib import Path
import socket
import threading
from typing import Callable, Mapping

from app.resource_telemetry.sampler import ResourceSampler


class RuntimeResourceMonitor:
    """Poll existing providers and forward each row to the runtime event layer."""

    def __init__(
        self,
        *,
        session_id: str,
        output_root: Path,
        interval_sec: float = 1.0,
        on_sample: Callable[[Mapping[str, object]], None] | None = None,
        sampler: ResourceSampler | None = None,
    ) -> None:
        self.interval_sec = float(interval_sec)
        self.on_sample = on_sample
        self._sampler = sampler or ResourceSampler(
            campaign_id="full_pipeline_runtime",
            scenario_id=session_id,
            attempt=1,
            worker_id="pipeline_coordinator",
            host=socket.gethostname(),
            root_pid=os.getpid(),
            disk_path=Path(output_root),
            interval_sec=interval_sec,
        )
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("resource monitor is already started")
        self._publish(self._sampler.sample_once())
        self._thread = threading.Thread(
            target=self._loop, name="full-pipeline-telemetry", daemon=True
        )
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop.wait(self.interval_sec):
            self._publish(self._sampler.sample_once())

    def _publish(self, row: Mapping[str, object]) -> None:
        if self.on_sample is not None:
            self.on_sample(dict(row))

    def sample_now(self) -> Mapping[str, object]:
        row = self._sampler.sample_once()
        self._publish(row)
        return row

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_sec * 3))
            if self._thread.is_alive():
                raise RuntimeError("resource monitor did not stop cleanly")
            self._thread = None
        self._publish(self._sampler.sample_once())

    def samples(self) -> tuple[Mapping[str, object], ...]:
        return self._sampler.samples

    @property
    def warnings(self) -> tuple[str, ...]:
        return self._sampler.warnings
