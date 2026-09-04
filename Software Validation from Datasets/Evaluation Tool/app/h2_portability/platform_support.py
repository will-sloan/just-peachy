"""Linux ARM64 dependency, audio, headless, and two-GiB diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import importlib.util
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from typing import Mapping, Sequence

from app.utils.paths import repository_root

from .contracts import ARM64_PACKAGE_CONTRACT_VERSION
from .onnx_tooling import COMPONENTS, sha256_file


LINUX_ARM64_READY = "LINUX_ARM64_READY"
LIKELY_PORTABLE = "LIKELY_PORTABLE"
PORT_REQUIRES_WORK = "PORT_REQUIRES_WORK"
PLATFORM_BLOCKER = "PLATFORM_BLOCKER"


@dataclass(frozen=True)
class DependencySupport:
    dependency: str
    purpose: str
    classification: str
    evidence: str
    remaining_validation: str


DEPENDENCY_SUPPORT = (
    DependencySupport(
        "onnxruntime==1.29.0",
        "FP32 ReDimNet2 and Pyannote execution",
        LIKELY_PORTABLE,
        "https://onnxruntime.ai/getting-started (Linux + Python + ARM64 are listed)",
        "resolve the exact CPython ARM64 wheel and run graph parity on the target",
    ),
    DependencySupport(
        "sherpa-onnx==1.13.4",
        "native streaming Giga/Original Sherpa ASR",
        PORT_REQUIRES_WORK,
        "https://k2-fsa.github.io/sherpa/onnx/install/aarch64-embedded-linux.html",
        "resolve a matching wheel or use the documented ARM64 build; then test ALSA",
    ),
    DependencySupport(
        "numpy/scipy",
        "audio arrays, resampling, deterministic clustering",
        LIKELY_PORTABLE,
        "manylinux ARM64 wheel resolution is checked by install_linux_arm64.sh",
        "install and run numerical smoke on the exact Raspberry Pi OS image",
    ),
    DependencySupport(
        "soundfile/libsndfile",
        "local WAV decode and session export",
        LIKELY_PORTABLE,
        "Debian ARM64 provides libsndfile1",
        "verify decode/encode and filesystem permissions on target",
    ),
    DependencySupport(
        "sounddevice/PortAudio",
        "microphone and optional playback callbacks",
        LIKELY_PORTABLE,
        "Debian ARM64 provides libportaudio2 and portaudio19-dev",
        "verify ALSA/PipeWire device selection, disconnect, and callback pressure",
    ),
    DependencySupport(
        "tkinter/python3-tk",
        "local demonstration GUI",
        LIKELY_PORTABLE,
        "Raspberry Pi OS/Debian packages Tk separately as python3-tk",
        "verify X11/Wayland display, scaling, and non-blocking UI on target",
    ),
    DependencySupport(
        "systemd",
        "headless startup and restart policy",
        LIKELY_PORTABLE,
        "Raspberry Pi OS uses systemd",
        "install the unit, verify permissions, recovery, and clean shutdown",
    ),
    DependencySupport(
        "torch/pyannote native reference",
        "export/parity reference only; excluded from lean product service",
        PORT_REQUIRES_WORK,
        "https://pytorch.org/ publishes Linux aarch64 wheels",
        "use only in a separate reference environment; do not load beside lean service on 2 GiB",
    ),
)


TWO_GIB_BUDGET_MIB = {
    "raspberry_pi_os_and_background_services": 384,
    "sherpa_giga_asr_graph_and_working_memory": 620,
    "pyannote_segmentation_onnx_and_working_memory": 160,
    "shared_redimnet2_onnx_and_working_memory": 240,
    "python_control_gui_and_telemetry": 180,
    "bounded_audio_queues_and_session_cache": 128,
    "safety_headroom": 336,
}


def two_gib_budget() -> dict[str, object]:
    total = sum(TWO_GIB_BUDGET_MIB.values())
    return {
        "schema_version": "h2-two-gib-resource-budget.v1",
        "target_installed_ram_mib": 2048,
        "allocations_mib": dict(TWO_GIB_BUDGET_MIB),
        "allocation_total_mib": total,
        "within_nominal_2gib": total <= 2048,
        "design_rules": [
            "one process owns all production ONNX Runtime sessions",
            "one ReDimNet2 session is shared by diarization and identity roles",
            "native Torch and pyannote reference environments are never loaded by the lean service",
            "accuracy caches remain on disk and live audio queues are hard bounded",
            "resource qualification is serial and must measure RSS on real hardware",
        ],
        "qualification_status": "DESIGN_BUDGET_ONLY_NOT_HARDWARE_MEASURED",
    }


def _command_probe(command: Sequence[str], *, timeout_sec: float = 5.0) -> dict[str, object]:
    executable = shutil.which(command[0])
    if executable is None:
        return {"command": list(command), "available": False, "status": "NOT_INSTALLED"}
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
        return {
            "command": list(command),
            "available": True,
            "exit_code": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
            "status": "PROBED",
        }
    except subprocess.TimeoutExpired:
        return {
            "command": list(command),
            "available": True,
            "status": "PROBE_TIMEOUT",
        }


def _memory() -> dict[str, object]:
    try:
        import psutil

        value = psutil.virtual_memory()
        return {
            "available": True,
            "total_mib": round(value.total / 1024**2, 1),
            "available_mib": round(value.available / 1024**2, 1),
        }
    except Exception as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}


def _graph_rows(graph_paths: Mapping[str, Path] | None) -> list[dict[str, object]]:
    paths = dict(graph_paths or {})
    rows = []
    for component_id in COMPONENTS:
        path = paths.get(component_id)
        exists = path is not None and Path(path).is_file()
        rows.append(
            {
                "component_id": component_id,
                "path": str(Path(path).resolve(strict=False)) if path is not None else None,
                "exists": exists,
                "bytes": Path(path).stat().st_size if exists else None,
                "sha256": sha256_file(Path(path)) if exists else None,
            }
        )
    return rows


def arm64_diagnostic(
    *,
    repository: Path | None = None,
    graph_paths: Mapping[str, Path] | None = None,
    require_linux_arm64: bool = False,
    require_graphs: bool = False,
    probe_audio: bool = False,
) -> dict[str, object]:
    """Run non-destructive target diagnostics; never claim hardware readiness."""

    repo = Path(repository) if repository is not None else repository_root().path
    system = platform.system()
    machine = platform.machine()
    target = system.casefold() == "linux" and machine.casefold() in {"aarch64", "arm64"}
    imports = {
        name: importlib.util.find_spec(name) is not None
        for name in (
            "numpy",
            "onnxruntime",
            "sherpa_onnx",
            "soundfile",
            "sounddevice",
            "tkinter",
            "psutil",
            "yaml",
        )
    }
    commands = {
        name: shutil.which(name)
        for name in ("arecord", "aplay", "pactl", "pw-cli", "systemctl")
    }
    audio_probes = []
    if probe_audio:
        if commands["arecord"]:
            audio_probes.append(_command_probe(("arecord", "-l")))
        if commands["pactl"]:
            audio_probes.append(_command_probe(("pactl", "list", "short", "sources")))
    graphs = _graph_rows(graph_paths)
    graph_gate = all(row["exists"] for row in graphs) if require_graphs else True
    platform_gate = target if require_linux_arm64 else True
    status = "DIAGNOSTIC_PASS" if platform_gate and graph_gate else "DIAGNOSTIC_BLOCKED"
    return {
        "schema_version": "h2-linux-arm64-diagnostic.v1",
        "package_contract_version": ARM64_PACKAGE_CONTRACT_VERSION,
        "status": status,
        "repository": str(repo.resolve()),
        "platform": {
            "system": system,
            "machine": machine,
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "is_linux_arm64": target,
        },
        "requirements": {
            "require_linux_arm64": require_linux_arm64,
            "require_graphs": require_graphs,
            "platform_gate": platform_gate,
            "graph_gate": graph_gate,
        },
        "memory": _memory(),
        "imports": imports,
        "commands": commands,
        "audio_probes": audio_probes,
        "display": {
            "DISPLAY_present": bool(os.environ.get("DISPLAY")),
            "WAYLAND_DISPLAY_present": bool(os.environ.get("WAYLAND_DISPLAY")),
            "headless_capable": True,
            "gui_tested": False,
        },
        "graphs": graphs,
        "dependency_support": [asdict(row) for row in DEPENDENCY_SUPPORT],
        "resource_budget": two_gib_budget(),
        "candidate_classification": PORT_REQUIRES_WORK,
        "candidate_classification_reason": (
            "component graphs pass x86 parity, but the H2 ONNX runtime adapter, "
            "ARM64 wheel resolution, audio stack, serial resources, and sustained "
            "streaming still require real Raspberry Pi validation"
        ),
        "linux_arm64_ready_claimed": False,
    }


__all__ = [
    "DEPENDENCY_SUPPORT",
    "LIKELY_PORTABLE",
    "LINUX_ARM64_READY",
    "PLATFORM_BLOCKER",
    "PORT_REQUIRES_WORK",
    "arm64_diagnostic",
    "two_gib_budget",
]
