"""Injectable CPU, memory, disk, process-tree, and NVML telemetry providers."""

from __future__ import annotations

from dataclasses import dataclass, fields
import importlib
from pathlib import Path
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True)
class SystemSnapshot:
    process_tree_pids: tuple[int, ...] = ()
    process_cpu_percent: float | None = None
    system_cpu_percent: float | None = None
    process_rss_bytes: int | None = None
    process_vms_bytes: int | None = None
    system_ram_total_bytes: int | None = None
    system_ram_available_bytes: int | None = None
    system_ram_used_bytes: int | None = None
    system_ram_percent: float | None = None
    process_disk_read_bytes: int | None = None
    process_disk_write_bytes: int | None = None
    system_disk_read_bytes: int | None = None
    system_disk_write_bytes: int | None = None
    disk_free_bytes: int | None = None
    availability_reason: str | None = None


@dataclass(frozen=True)
class GpuSnapshot:
    gpu_index: str | None = None
    gpu_uuid: str | None = None
    gpu_utilization_percent: float | None = None
    gpu_memory_utilization_percent: float | None = None
    gpu_vram_bytes: int | None = None
    gpu_total_vram_bytes: int | None = None
    gpu_temperature_c: float | None = None
    gpu_power_w: float | None = None
    gpu_power_limit_w: float | None = None
    gpu_graphics_clock_mhz: float | None = None
    gpu_memory_clock_mhz: float | None = None
    gpu_throttling_reasons: str | None = None
    availability_reason: str | None = None


class SystemTelemetryProvider(Protocol):
    def snapshot(self, root_pid: int, disk_path: Path) -> SystemSnapshot:
        """Return one process-tree and host resource snapshot."""

    def availability(self) -> Mapping[str, Mapping[str, object]]:
        """Describe field support and unavailability reasons."""


class GpuTelemetryProvider(Protocol):
    def snapshot(self, gpu_index: str | None, process_tree_pids: Sequence[int]) -> GpuSnapshot:
        """Return one GPU snapshot for the scenario process tree."""

    def availability(self) -> Mapping[str, Mapping[str, object]]:
        """Describe field support and unavailability reasons."""


class PsutilSystemProvider:
    """Process-tree telemetry backed by psutil, with explicit optionality."""

    _FIELD_NAMES = tuple(
        field.name
        for field in fields(SystemSnapshot)
        if field.name not in {"process_tree_pids", "availability_reason"}
    )

    def __init__(self, module: object | None = None) -> None:
        self._reason: str | None = None
        if module is not None:
            self.psutil = module
        else:
            try:
                self.psutil = importlib.import_module("psutil")
            except (ImportError, OSError) as exc:
                self.psutil = None
                self._reason = f"psutil unavailable: {type(exc).__name__}"

    def snapshot(self, root_pid: int, disk_path: Path) -> SystemSnapshot:
        if self.psutil is None:
            return SystemSnapshot(availability_reason=self._reason or "psutil unavailable")
        psutil = self.psutil
        try:
            root = psutil.Process(int(root_pid))
            processes = [root, *root.children(recursive=True)]
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            return SystemSnapshot(availability_reason="scenario process exited")
        except (psutil.AccessDenied, OSError) as exc:
            return SystemSnapshot(availability_reason=f"process tree unavailable: {type(exc).__name__}")

        live = []
        for process in processes:
            try:
                if process.is_running():
                    live.append(process)
            except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
                continue
        pids = tuple(sorted({int(process.pid) for process in live}))
        process_cpu = 0.0
        rss = vms = read_bytes = write_bytes = 0
        process_values = 0
        io_values = 0
        for process in live:
            try:
                process_cpu += float(process.cpu_percent(interval=None))
                memory = process.memory_info()
                rss += int(memory.rss)
                vms += int(memory.vms)
                process_values += 1
            except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError):
                continue
            try:
                io = process.io_counters()
                read_bytes += int(io.read_bytes)
                write_bytes += int(io.write_bytes)
                io_values += 1
            except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError, AttributeError):
                continue
        memory = psutil.virtual_memory()
        disk_io = psutil.disk_io_counters()
        disk = psutil.disk_usage(str(disk_path))
        return SystemSnapshot(
            process_tree_pids=pids,
            process_cpu_percent=process_cpu if process_values else None,
            system_cpu_percent=float(psutil.cpu_percent(interval=None)),
            process_rss_bytes=rss if process_values else None,
            process_vms_bytes=vms if process_values else None,
            system_ram_total_bytes=int(memory.total),
            system_ram_available_bytes=int(memory.available),
            system_ram_used_bytes=int(memory.used),
            system_ram_percent=float(memory.percent),
            process_disk_read_bytes=read_bytes if io_values else None,
            process_disk_write_bytes=write_bytes if io_values else None,
            system_disk_read_bytes=(int(disk_io.read_bytes) if disk_io is not None else None),
            system_disk_write_bytes=(int(disk_io.write_bytes) if disk_io is not None else None),
            disk_free_bytes=int(disk.free),
            availability_reason=None,
        )

    def availability(self) -> Mapping[str, Mapping[str, object]]:
        available = self.psutil is not None
        return {
            name: {
                "available": available,
                "source": "psutil" if available else None,
                "reason": None if available else self._reason or "psutil unavailable",
            }
            for name in self._FIELD_NAMES
        }


class NvmlGpuProvider:
    """Best-effort NVML provider; every unsupported field remains explicit."""

    _FIELD_NAMES = tuple(
        field.name
        for field in fields(GpuSnapshot)
        if field.name != "availability_reason"
    )

    def __init__(self, module: object | None = None) -> None:
        self.nvml = module
        self._reason: str | None = None
        self._initialized = False
        if self.nvml is None:
            try:
                self.nvml = importlib.import_module("pynvml")
            except (ImportError, OSError) as exc:
                self._reason = f"NVML unavailable: {type(exc).__name__}"
                return
        try:
            self.nvml.nvmlInit()
            self._initialized = True
        except Exception as exc:  # pragma: no cover - host-driver boundary
            self._reason = f"NVML initialization failed: {type(exc).__name__}"

    def snapshot(self, gpu_index: str | None, process_tree_pids: Sequence[int]) -> GpuSnapshot:
        if not self._initialized or self.nvml is None:
            return GpuSnapshot(availability_reason=self._reason or "NVML unavailable")
        nvml = self.nvml
        try:
            index = int(gpu_index or 0)
            handle = nvml.nvmlDeviceGetHandleByIndex(index)
            uuid = _decode(nvml.nvmlDeviceGetUUID(handle))
            utilization = nvml.nvmlDeviceGetUtilizationRates(handle)
            memory = nvml.nvmlDeviceGetMemoryInfo(handle)
            process_vram = _process_vram(nvml, handle, process_tree_pids)
            return GpuSnapshot(
                gpu_index=str(index),
                gpu_uuid=uuid,
                gpu_utilization_percent=_float_attr(utilization, "gpu"),
                gpu_memory_utilization_percent=_float_attr(utilization, "memory"),
                gpu_vram_bytes=process_vram,
                gpu_total_vram_bytes=_int_attr(memory, "total"),
                gpu_temperature_c=_nvml_call(
                    nvml,
                    "nvmlDeviceGetTemperature",
                    handle,
                    getattr(nvml, "NVML_TEMPERATURE_GPU", 0),
                    transform=float,
                ),
                gpu_power_w=_scaled_nvml_call(nvml, "nvmlDeviceGetPowerUsage", handle),
                gpu_power_limit_w=_scaled_nvml_call(
                    nvml, "nvmlDeviceGetEnforcedPowerLimit", handle
                ),
                gpu_graphics_clock_mhz=_clock(nvml, handle, "NVML_CLOCK_GRAPHICS"),
                gpu_memory_clock_mhz=_clock(nvml, handle, "NVML_CLOCK_MEM"),
                gpu_throttling_reasons=_throttle_reasons(nvml, handle),
                availability_reason=None,
            )
        except Exception as exc:  # pragma: no cover - host-driver boundary
            return GpuSnapshot(availability_reason=f"NVML sample failed: {type(exc).__name__}")

    def availability(self) -> Mapping[str, Mapping[str, object]]:
        available = self._initialized
        return {
            name: {
                "available": available,
                "source": "NVML" if available else None,
                "reason": None if available else self._reason or "NVML unavailable",
            }
            for name in self._FIELD_NAMES
        }


def _process_vram(module: object, handle: object, pids: Sequence[int]) -> int | None:
    allowed = {int(pid) for pid in pids}
    if not allowed:
        return 0
    processes = []
    for method_name in (
        "nvmlDeviceGetComputeRunningProcesses_v3",
        "nvmlDeviceGetComputeRunningProcesses_v2",
        "nvmlDeviceGetComputeRunningProcesses",
    ):
        method = getattr(module, method_name, None)
        if method is None:
            continue
        try:
            processes = method(handle)
            break
        except Exception:
            continue
    if not processes:
        return 0
    values = []
    unavailable = getattr(module, "NVML_VALUE_NOT_AVAILABLE", None)
    for process in processes:
        if int(getattr(process, "pid", -1)) not in allowed:
            continue
        value = getattr(process, "usedGpuMemory", None)
        if value is not None and value != unavailable:
            values.append(int(value))
    return sum(values) if values else 0


def _nvml_call(module: object, name: str, *args: object, transform: object = None) -> object | None:
    method = getattr(module, name, None)
    if method is None:
        return None
    try:
        value = method(*args)
        return transform(value) if callable(transform) else value
    except Exception:
        return None


def _scaled_nvml_call(module: object, name: str, handle: object) -> float | None:
    value = _nvml_call(module, name, handle)
    return None if value is None else float(value) / 1000.0


def _clock(module: object, handle: object, clock_name: str) -> float | None:
    clock_type = getattr(module, clock_name, None)
    if clock_type is None:
        return None
    value = _nvml_call(module, "nvmlDeviceGetClockInfo", handle, clock_type)
    return None if value is None else float(value)


def _throttle_reasons(module: object, handle: object) -> str | None:
    value = _nvml_call(module, "nvmlDeviceGetCurrentClocksThrottleReasons", handle)
    if value is None:
        return None
    numeric = int(value)
    if numeric == 0:
        return "none"
    labels = []
    for name in dir(module):
        if not name.startswith("nvmlClocksThrottleReason") or name.endswith("All"):
            continue
        mask = getattr(module, name, None)
        if isinstance(mask, int) and mask and numeric & mask:
            labels.append(name.removeprefix("nvmlClocksThrottleReason"))
    return ",".join(sorted(set(labels))) or f"mask:{numeric}"


def _decode(value: object) -> str:
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def _float_attr(value: object, name: str) -> float | None:
    raw = getattr(value, name, None)
    return None if raw is None else float(raw)


def _int_attr(value: object, name: str) -> int | None:
    raw = getattr(value, name, None)
    return None if raw is None else int(raw)
