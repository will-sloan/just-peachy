"""High-resolution, injectable scenario resource sampler."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from typing import Callable, Mapping

from app.resource_telemetry.providers import (
    GpuTelemetryProvider,
    NvmlGpuProvider,
    PsutilSystemProvider,
    SystemTelemetryProvider,
)


class SystemClock:
    """Default wall and monotonic clock boundary."""

    def utc_now(self) -> datetime:
        return datetime.now(timezone.utc)

    def monotonic_ns(self) -> int:
        return time.perf_counter_ns()


class ResourceSampler:
    """Poll process-tree, host, disk, and GPU resources for one scenario."""

    def __init__(
        self,
        *,
        campaign_id: str,
        scenario_id: str,
        attempt: int,
        worker_id: str,
        host: str,
        root_pid: int,
        disk_path: Path,
        active_state_path: Path | None = None,
        gpu_index: str | None = None,
        interval_sec: float = 1.0,
        system_provider: SystemTelemetryProvider | None = None,
        gpu_provider: GpuTelemetryProvider | None = None,
        clock: object | None = None,
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        if interval_sec <= 0:
            raise ValueError("telemetry sampling interval must be positive")
        self.campaign_id = campaign_id
        self.scenario_id = scenario_id
        self.attempt = int(attempt)
        self.worker_id = worker_id
        self.host = host
        self.root_pid = int(root_pid)
        self.disk_path = disk_path.resolve()
        self.active_state_path = active_state_path
        self.gpu_index = gpu_index
        self.interval_sec = float(interval_sec)
        self.system_provider = system_provider or PsutilSystemProvider()
        self.gpu_provider = gpu_provider or NvmlGpuProvider()
        self.clock = clock or SystemClock()
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self._thread: threading.Thread | None = None
        self._rows: list[dict[str, object]] = []
        self._warnings: list[str] = []
        self._lock = threading.Lock()
        self._started_monotonic_ns: int | None = None
        self._last_monotonic_ns: int | None = None
        self._peak_vram_bytes: int | None = None

    @property
    def samples(self) -> tuple[dict[str, object], ...]:
        with self._lock:
            return tuple(dict(row) for row in self._rows)

    @property
    def warnings(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._warnings)

    def availability(self) -> dict[str, Mapping[str, object]]:
        values = {
            **dict(self.system_provider.availability()),
            **dict(self.gpu_provider.availability()),
        }
        vram = dict(values.get("gpu_vram_bytes") or {})
        values["gpu_peak_vram_bytes"] = {
            "available": bool(vram.get("available")),
            "source": "derived_running_peak" if vram.get("available") else None,
            "reason": vram.get("reason"),
        }
        values["active_component"] = {
            "available": self.active_state_path is not None,
            "source": "component_span_channel" if self.active_state_path is not None else None,
            "reason": (
                None
                if self.active_state_path is not None
                else "component span channel was not configured"
            ),
        }
        return values

    def start(self) -> None:
        if self._thread is not None:
            raise RuntimeError("resource sampler has already started")
        self.sample_once()
        self._thread = threading.Thread(
            target=self._sample_loop,
            name=f"telemetry-{self.scenario_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(1.0, self.interval_sec * 3.0))
            if self._thread.is_alive():
                with self._lock:
                    self._warnings.append("telemetry sampler did not stop within its join timeout")
        self.sample_once()

    def sample_once(self) -> dict[str, object]:
        now_ns = int(self.clock.monotonic_ns())
        wall = self.clock.utc_now()
        if wall.tzinfo is None or wall.utcoffset() is None:
            wall = wall.replace(tzinfo=timezone.utc)
        started = self._started_monotonic_ns
        if started is None:
            started = now_ns
            self._started_monotonic_ns = now_ns
        previous = self._last_monotonic_ns
        gap = previous is not None and (now_ns - previous) / 1_000_000_000 > self.interval_sec * 1.5
        if gap:
            with self._lock:
                self._warnings.append(
                    f"sampling gap exceeded 1.5x interval at elapsed {(now_ns - started) / 1e9:.6f}s"
                )
        self._last_monotonic_ns = now_ns
        system = self.system_provider.snapshot(self.root_pid, self.disk_path)
        gpu = self.gpu_provider.snapshot(self.gpu_index, system.process_tree_pids)
        current_vram = gpu.gpu_vram_bytes
        if current_vram is not None:
            self._peak_vram_bytes = max(self._peak_vram_bytes or 0, int(current_vram))
        row: dict[str, object] = {
            "timestamp_utc": wall.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
            "monotonic_ns": now_ns,
            "elapsed_sec": (now_ns - started) / 1_000_000_000,
            "campaign_id": self.campaign_id,
            "scenario_id": self.scenario_id,
            "attempt": self.attempt,
            "worker_id": self.worker_id,
            "host": self.host,
            "root_pid": self.root_pid,
            "process_tree_pids": list(system.process_tree_pids),
            "active_component": _active_component(self.active_state_path),
            **{
                key: value
                for key, value in asdict(system).items()
                if key not in {"process_tree_pids", "availability_reason"}
            },
            **{
                key: value
                for key, value in asdict(gpu).items()
                if key != "availability_reason"
            },
            "gpu_peak_vram_bytes": self._peak_vram_bytes,
            "process_availability_reason": system.availability_reason,
            "gpu_availability_reason": gpu.availability_reason,
            "sampling_gap": bool(gap),
        }
        with self._lock:
            self._rows.append(row)
        return dict(row)

    def _sample_loop(self) -> None:
        while not self._wait(self.interval_sec):
            try:
                self.sample_once()
            except Exception as exc:  # pragma: no cover - defensive sampler isolation
                with self._lock:
                    self._warnings.append(
                        f"telemetry sample failed: {type(exc).__name__}"
                    )


def _active_component(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, Mapping):
        return None
    component = value.get("active_component")
    return str(component) if component else None
