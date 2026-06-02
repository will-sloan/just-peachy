"""GPU discovery and telemetry helpers for parallel runtime scheduling."""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class GpuDevice:
    """Static GPU metadata discovered from the runtime environment."""

    index: str
    name: str | None
    total_vram_mb: float | None
    uuid: str | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "index": self.index,
            "name": self.name,
            "total_vram_mb": self.total_vram_mb,
            "uuid": self.uuid,
        }


@dataclass(frozen=True)
class GpuSample:
    """One sampled GPU telemetry row."""

    index: str
    timestamp_sec: float
    name: str | None = None
    total_vram_mb: float | None = None
    used_vram_mb: float | None = None
    utilization_percent: float | None = None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "index": self.index,
            "timestamp_sec": self.timestamp_sec,
            "name": self.name,
            "total_vram_mb": self.total_vram_mb,
            "used_vram_mb": self.used_vram_mb,
            "utilization_percent": self.utilization_percent,
        }


@dataclass(frozen=True)
class GpuJobSummary:
    """GPU telemetry summary for one scheduled job."""

    assigned_cuda_device: str | None
    gpu_name: str | None
    total_vram_mb: float | None
    peak_memory_mb: float | None
    average_utilization_percent: float | None
    memory_headroom_percent: float | None
    sample_count: int
    telemetry_available: bool

    def to_jsonable(self) -> dict[str, object]:
        return {
            "assigned_cuda_device": self.assigned_cuda_device,
            "gpu_name": self.gpu_name,
            "total_vram_mb": self.total_vram_mb,
            "peak_memory_mb": self.peak_memory_mb,
            "average_utilization_percent": self.average_utilization_percent,
            "memory_headroom_percent": self.memory_headroom_percent,
            "sample_count": self.sample_count,
            "telemetry_available": self.telemetry_available,
        }


class GpuTelemetryProvider(Protocol):
    """Protocol for injectable GPU telemetry providers."""

    def devices(self) -> tuple[GpuDevice, ...]:
        """Return available GPU devices."""

    def snapshot(self) -> tuple[GpuSample, ...]:
        """Return a telemetry snapshot for available GPUs."""


class NvidiaSmiTelemetryProvider:
    """Best-effort telemetry provider backed by ``nvidia-smi``."""

    def __init__(self, command: str = "nvidia-smi") -> None:
        self.command = command

    def devices(self) -> tuple[GpuDevice, ...]:
        output = self._query(
            "index,name,memory.total,uuid",
        )
        devices: list[GpuDevice] = []
        for row in output:
            if len(row) < 4:
                continue
            index, name, total_vram, uuid = row[:4]
            devices.append(
                GpuDevice(
                    index=index,
                    name=name or None,
                    total_vram_mb=_optional_float(total_vram),
                    uuid=uuid or None,
                )
            )
        return tuple(devices)

    def snapshot(self) -> tuple[GpuSample, ...]:
        output = self._query(
            "index,name,memory.total,memory.used,utilization.gpu",
        )
        timestamp = time.time()
        samples: list[GpuSample] = []
        for row in output:
            if len(row) < 5:
                continue
            index, name, total_vram, used_vram, utilization = row[:5]
            samples.append(
                GpuSample(
                    index=index,
                    timestamp_sec=timestamp,
                    name=name or None,
                    total_vram_mb=_optional_float(total_vram),
                    used_vram_mb=_optional_float(used_vram),
                    utilization_percent=_optional_float(utilization),
                )
            )
        return tuple(samples)

    def _query(self, fields: str) -> list[list[str]]:
        try:
            result = subprocess.run(
                [
                    self.command,
                    f"--query-gpu={fields}",
                    "--format=csv,noheader,nounits",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return []
        rows: list[list[str]] = []
        for line in result.stdout.splitlines():
            text = line.strip()
            if text:
                rows.append([part.strip() for part in text.split(",")])
        return rows


class GpuTelemetryMonitor:
    """Poll GPU telemetry while one subprocess is running."""

    def __init__(
        self,
        provider: GpuTelemetryProvider,
        *,
        gpu_indices: Sequence[str] = (),
        poll_interval_sec: float = 1.0,
    ) -> None:
        self.provider = provider
        self.gpu_indices = tuple(str(index) for index in gpu_indices)
        self.poll_interval_sec = max(0.01, float(poll_interval_sec))
        self._samples: list[GpuSample] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._samples.extend(self._filtered_snapshot())
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(0.1, self.poll_interval_sec * 2))
        self._samples.extend(self._filtered_snapshot())

    def summary(self, assigned_cuda_device: str | None) -> GpuJobSummary:
        selected = [
            sample
            for sample in self._samples
            if assigned_cuda_device is None or sample.index == assigned_cuda_device
        ]
        devices = {
            device.index: device
            for device in self.provider.devices()
        }
        device = devices.get(str(assigned_cuda_device)) if assigned_cuda_device is not None else None
        names = [sample.name for sample in selected if sample.name]
        totals = [sample.total_vram_mb for sample in selected if sample.total_vram_mb is not None]
        used_values = [sample.used_vram_mb for sample in selected if sample.used_vram_mb is not None]
        utilization_values = [
            sample.utilization_percent
            for sample in selected
            if sample.utilization_percent is not None
        ]
        total_vram = totals[0] if totals else (device.total_vram_mb if device else None)
        peak_memory = max(used_values) if used_values else None
        return GpuJobSummary(
            assigned_cuda_device=assigned_cuda_device,
            gpu_name=names[0] if names else (device.name if device else None),
            total_vram_mb=total_vram,
            peak_memory_mb=peak_memory,
            average_utilization_percent=(
                sum(utilization_values) / len(utilization_values)
                if utilization_values
                else None
            ),
            memory_headroom_percent=memory_headroom_percent(total_vram, peak_memory),
            sample_count=len(selected),
            telemetry_available=bool(selected),
        )

    def _poll(self) -> None:
        while not self._stop.wait(self.poll_interval_sec):
            self._samples.extend(self._filtered_snapshot())

    def _filtered_snapshot(self) -> tuple[GpuSample, ...]:
        samples = self.provider.snapshot()
        if not self.gpu_indices:
            return samples
        allowed = set(self.gpu_indices)
        return tuple(sample for sample in samples if sample.index in allowed)


def memory_headroom_percent(
    total_vram_mb: float | None,
    peak_memory_mb: float | None,
) -> float | None:
    """Return remaining VRAM as a percentage of total memory."""

    if total_vram_mb is None or peak_memory_mb is None or total_vram_mb <= 0:
        return None
    return max(0.0, (total_vram_mb - peak_memory_mb) / total_vram_mb * 100.0)


def available_gpu_indices(provider: GpuTelemetryProvider | None = None) -> tuple[str, ...]:
    """Return discoverable GPU indices, or an empty tuple when unavailable."""

    active_provider = provider or NvidiaSmiTelemetryProvider()
    return tuple(device.index for device in active_provider.devices())


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None
