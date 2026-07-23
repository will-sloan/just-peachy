from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy.signal import resample_poly


FLOAT_RE = re.compile(r"(?i)(?<![A-Za-z_])(?:nan|[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)(?![A-Za-z_])")
PROJECT_ROOT = Path(__file__).resolve().parent
PACKED_OUTPUT_LABELS = [
    "far_end_reference",
    "processed_auto_selected",
    "amplified_mic0",
    "amplified_mic1",
    "amplified_mic2",
    "amplified_mic3",
]
ASR_PACKED_OUTPUT_LABELS = [
    "far_end_reference",
    "asr_processed_auto_selected",
    "amplified_mic0",
    "amplified_mic1",
    "amplified_mic2",
    "amplified_mic3",
]
PACKED_DEFAULT_COMMAND = "12 0  3 0  3 2  6 3  3 1  3 3"
# AUDIO_MGR_OP_ALL arguments are ordered as L_PK0, L_PK1, L_PK2,
# R_PK0, R_PK1, R_PK2. The unpacker emits L_PK0, R_PK0, L_PK1,
# R_PK1, L_PK2, R_PK2. Put ASR in R_PK0 so it becomes output channel 2.
ASR_PACKED_DEFAULT_COMMAND = "12 0  3 0  3 2  7 3  3 1  3 3"
TRACKED_PARAMETERS = [
    "VERSION",
    "AEC_NUM_MICS",
    "AEC_MIC_ARRAY_TYPE",
    "AEC_MIC_ARRAY_GEO",
    "AUDIO_MGR_OP_PACKED",
    "AUDIO_MGR_OP_ALL",
    "AUDIO_MGR_OP_UPSAMPLE",
    "AUDIO_MGR_OP_L_PK0",
    "AUDIO_MGR_OP_L_PK1",
    "AUDIO_MGR_OP_L_PK2",
    "AUDIO_MGR_OP_R_PK0",
    "AUDIO_MGR_OP_R_PK1",
    "AUDIO_MGR_OP_R_PK2",
    "USB_BIT_DEPTH",
    "I2S_INPUT_PACKED",
    "AUDIO_MGR_MIC_GAIN",
    "AUDIO_MGR_REF_GAIN",
    "AUDIO_MGR_SYS_DELAY",
    "AEC_ASROUTONOFF",
    "AEC_ASROUTGAIN",
]
CATEGORY_TO_NUMBER = {
    "MUX_RAW_MICS": 1,
    "MUX_PROCESSED_MICS": 6,
    "MUX_AEC_RESIDUALS": 7,
    "MUX_FAR_END": 12,
}
ACTIVE_RUN_CONTEXT: tuple[Config, Path, dict[str, dict[str, Any]]] | None = None


@dataclass(frozen=True)
class Config:
    workspace_root: Path
    xvf_host_path: Path
    xvf_tools_path: Path
    python_executable: str
    protocol: str
    audio_input_device_contains: str
    audio_output_device_contains: str
    sample_rate_hz: int
    record_channels: int
    record_subtype: str
    telemetry_poll_hz: float
    command_timeout_sec: float
    reset_before_digital_test: bool
    packed_bit_depth: int
    xmos_source_root: Path
    xmos_pythonpath: Path
    audio_api_preference: tuple[str, ...]
    packed_output_command: str
    asr_packed_output_command: str


def resolve_config_path(value: Any, config_path: Path, default: Path) -> Path:
    """Resolve a config path relative to config.json, while accepting old absolute paths."""
    candidate = default if value is None else Path(str(value))
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


def load_config(path: Path) -> Config:
    config_path = path.resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    tools_path = resolve_config_path(data.get("xvf_tools_path"), config_path, PROJECT_ROOT.parent)
    source_root = resolve_config_path(
        data.get("xmos_source_root"),
        config_path,
        tools_path.parent,
    )
    pythonpath = resolve_config_path(
        data.get("xmos_pythonpath"),
        config_path,
        source_root / "modules" / "fwk_xvf" / "modules" / "tuning",
    )
    return Config(
        workspace_root=resolve_config_path(data.get("workspace_root"), config_path, PROJECT_ROOT.parent),
        xvf_host_path=resolve_config_path(data.get("xvf_host_path"), config_path, PROJECT_ROOT.parent),
        xvf_tools_path=tools_path,
        python_executable=str(
            resolve_config_path(
                data.get("python_executable"),
                config_path,
                PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
            )
        ),
        protocol=str(data.get("protocol", "usb")),
        audio_input_device_contains=str(data.get("audio_input_device_contains", "XVF3800 Voice Processor")),
        audio_output_device_contains=str(data.get("audio_output_device_contains", "XVF3800 Voice Processor")),
        sample_rate_hz=int(data.get("sample_rate_hz", 48000)),
        record_channels=int(data.get("record_channels", 2)),
        record_subtype=str(data.get("record_subtype", "PCM_24")),
        telemetry_poll_hz=float(data.get("telemetry_poll_hz", 5.0)),
        command_timeout_sec=float(data.get("command_timeout_sec", 5.0)),
        reset_before_digital_test=bool(data.get("reset_before_digital_test", True)),
        packed_bit_depth=int(data.get("packed_bit_depth", 24)),
        xmos_source_root=source_root.resolve(),
        xmos_pythonpath=pythonpath.resolve(),
        audio_api_preference=tuple(str(x) for x in data.get("audio_api_preference", ["WDM-KS", "WASAPI", "DirectSound", "MME"])),
        packed_output_command=str(data.get("packed_output_command", PACKED_DEFAULT_COMMAND)),
        asr_packed_output_command=str(data.get("asr_packed_output_command", ASR_PACKED_DEFAULT_COMMAND)),
    )


def verify_paths(cfg: Config, require_tools: bool = False) -> None:
    if not cfg.workspace_root.is_dir():
        raise FileNotFoundError(f"workspace_root not found: {cfg.workspace_root}")
    if not cfg.xvf_host_path.is_file():
        raise FileNotFoundError(f"xvf_host.exe not found: {cfg.xvf_host_path}")
    if require_tools and not cfg.xvf_tools_path.is_file():
        raise FileNotFoundError(f"xvf_tools.py not found: {cfg.xvf_tools_path}")
    if require_tools and not cfg.xmos_pythonpath.is_dir():
        raise FileNotFoundError(f"XMOS Python module directory not found: {cfg.xmos_pythonpath}")
    python_path = Path(cfg.python_executable)
    if not python_path.is_file():
        raise FileNotFoundError(f"Configured Python executable not found: {python_path}")
    if PROJECT_ROOT / ".venv" not in python_path.parents:
        raise RuntimeError(f"Configured Python executable must be inside this project .venv: {python_path}")


def format_command(args: Iterable[str]) -> str:
    return subprocess.list2cmdline([str(arg) for arg in args])


def append_text(path: Path, text: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text)


def run_process(
    args: list[str],
    timeout: float | None = None,
    check: bool = True,
    log_dir: Path | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            shell=False,
            cwd=str(cwd) if cwd else None,
            env=env,
        )
    except Exception as exc:
        if log_dir:
            append_text(log_dir / "commands.txt", f"$ {format_command(args)}\nexit_code=EXCEPTION\n{exc!r}\n{'-' * 80}\n")
            append_text(log_dir / "stderr.log", f"$ {format_command(args)}\n{exc!r}\n{'-' * 80}\n")
        raise
    if log_dir:
        append_text(log_dir / "commands.txt", f"$ {format_command(args)}\nexit_code={result.returncode}\n{'-' * 80}\n")
        if result.stdout:
            append_text(log_dir / "stdout.log", f"$ {format_command(args)}\n{result.stdout}\n{'-' * 80}\n")
        if result.stderr:
            append_text(log_dir / "stderr.log", f"$ {format_command(args)}\n{result.stderr}\n{'-' * 80}\n")
    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def host_command(
    cfg: Config,
    command: str,
    *params: str,
    check: bool = True,
    log_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [str(cfg.xvf_host_path), "--use", cfg.protocol, command, *map(str, params)]
    return run_process(args, timeout=cfg.command_timeout_sec, check=check, log_dir=log_dir)


def parse_numeric_values(text: str) -> list[float]:
    values: list[float] = []
    for token in FLOAT_RE.findall(text):
        if token.lower() == "nan":
            values.append(float("nan"))
        else:
            values.append(float(token))
    return values


def last_values(result: subprocess.CompletedProcess[str], expected: int) -> list[float]:
    values = parse_numeric_values(result.stdout + "\n" + result.stderr)
    if len(values) < expected:
        return [float("nan")] * expected
    return values[-expected:]


def parse_angle_radians(result: subprocess.CompletedProcess[str], expected: int) -> list[float]:
    """Extract angle values in radians from xvf_host output.

    Some release builds print only radians, while others may print radians and
    human-readable degrees. This handles contiguous and interleaved rad/degree
    layouts before falling back to the final plausible radian block.
    """
    values = parse_numeric_values(result.stdout + "\n" + result.stderr)
    if len(values) < expected:
        return [float("nan")] * expected

    def finite_or_nan(v: float) -> bool:
        return math.isnan(v) or abs(v) <= (2.0 * math.pi + 0.25)

    def degree_match(rad: float, deg: float) -> bool:
        if math.isnan(rad) and math.isnan(deg):
            return True
        if not (math.isfinite(rad) and math.isfinite(deg)):
            return False
        return abs(math.degrees(rad) - deg) <= max(1.0, abs(deg) * 0.02)

    # Search from the end because xvf_host may prepend labels or command IDs.
    for start in range(len(values) - 2 * expected, -1, -1):
        block = values[start:start + 2 * expected]
        first = block[:expected]
        second = block[expected:]
        if all(finite_or_nan(v) for v in first) and all(degree_match(r, d) for r, d in zip(first, second)):
            return first
        interleaved_rad = block[0::2]
        interleaved_deg = block[1::2]
        if all(finite_or_nan(v) for v in interleaved_rad) and all(
            degree_match(r, d) for r, d in zip(interleaved_rad, interleaved_deg)
        ):
            return interleaved_rad

    for start in range(len(values) - expected, -1, -1):
        block = values[start:start + expected]
        if all(finite_or_nan(v) for v in block):
            return block
    return [float("nan")] * expected


def _audio_candidates(contains: str, kind: str) -> list[dict[str, Any]]:
    devices = sd.query_devices()
    key = contains.lower()
    candidates: list[dict[str, Any]] = []
    for idx, device in enumerate(devices):
        name = str(device["name"])
        if key not in name.lower():
            continue
        if kind == "input" and int(device["max_input_channels"]) > 0:
            candidates.append({"index": idx, "device": dict(device), "api": sd.query_hostapis(int(device["hostapi"]))["name"]})
        elif kind == "output" and int(device["max_output_channels"]) > 0:
            candidates.append({"index": idx, "device": dict(device), "api": sd.query_hostapis(int(device["hostapi"]))["name"]})
    return candidates


def select_audio_devices(cfg: Config) -> dict[str, Any]:
    inputs = _audio_candidates(cfg.audio_input_device_contains, "input")
    outputs = _audio_candidates(cfg.audio_output_device_contains, "output")
    if not inputs:
        raise RuntimeError(f"No input device contains '{cfg.audio_input_device_contains}'. Refusing to use the default PC microphone.")
    if not outputs:
        raise RuntimeError(f"No output device contains '{cfg.audio_output_device_contains}'. Refusing to use default PC speakers.")

    preference = [item.lower() for item in cfg.audio_api_preference]
    pairs: list[tuple[int, int, int, dict[str, Any], dict[str, Any]]] = []
    for input_item in inputs:
        for output_item in outputs:
            if input_item["api"] != output_item["api"]:
                continue
            api_lower = str(input_item["api"]).lower()
            rank = next((i for i, name in enumerate(preference) if name in api_lower), len(preference))
            pairs.append((rank, input_item["index"], output_item["index"], input_item, output_item))
    if not pairs:
        raise RuntimeError("No XVF3800 input/output pair shares a Windows audio API.")
    pairs.sort(key=lambda item: (item[0], item[1], item[2]))
    best_rank = pairs[0][0]
    best = [item for item in pairs if item[0] == best_rank]
    if len(best) > 1 and {(item[1], item[2]) for item in best}.__len__() > 1:
        choices = "; ".join(f"input {item[1]} / output {item[2]} / {item[3]['api']}" for item in best)
        raise RuntimeError(f"Ambiguous XVF3800 audio selection: {choices}. Narrow the configured device text or API preference.")
    _, input_id, output_id, input_item, output_item = best[0]
    return {
        "input_id": input_id,
        "output_id": output_id,
        "api": input_item["api"],
        "input": input_item["device"],
        "output": output_item["device"],
    }


def find_audio_device(cfg: Config, kind: str) -> int:
    selected = select_audio_devices(cfg)
    return int(selected["input_id"] if kind == "input" else selected["output_id"])


def timestamp_name(label: str) -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S") + "_" + sanitize(label)


def sanitize(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")


def make_run_dir(cfg: Config, label: str) -> Path:
    runs_root = cfg.workspace_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)
    base_name = timestamp_name(label)
    run_dir = runs_root / base_name
    suffix = 2
    while run_dir.exists():
        run_dir = runs_root / f"{base_name}_{suffix}"
        suffix += 1
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "input").mkdir()
    (run_dir / "output").mkdir()
    (run_dir / "logs").mkdir()
    for log_name in ["commands.txt", "stdout.log", "stderr.log", "xvf_host_commands.log"]:
        (run_dir / "logs" / log_name).touch()
    return run_dir


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot_run_environment(cfg: Config, run_dir: Path) -> None:
    write_json(run_dir / "config_snapshot.json", config_to_dict(cfg))
    env_lines = [
        f"project_root={PROJECT_ROOT}",
        f"python_executable={sys.executable}",
        f"python_version={sys.version}",
        f"xvf_host_path={cfg.xvf_host_path}",
        f"xvf_tools_path={cfg.xvf_tools_path}",
        f"xmos_pythonpath={cfg.xmos_pythonpath}",
    ]
    (run_dir / "logs" / "environment.txt").write_text("\n".join(env_lines) + "\n", encoding="utf-8")
    freeze = run_process([str(cfg.python_executable), "-m", "pip", "freeze"], timeout=60, check=False)
    (run_dir / "logs" / "pip_freeze.txt").write_text(freeze.stdout + ("\n[stderr]\n" + freeze.stderr if freeze.stderr else ""), encoding="utf-8")


def run_start(cfg: Config, label: str) -> tuple[Path, float]:
    run_dir = make_run_dir(cfg, label)
    snapshot_run_environment(cfg, run_dir)
    return run_dir, time.monotonic()


def run_and_log_host(cfg: Config, log_file: Path, command: str, *params: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    log_dir = log_file.parent
    result = host_command(cfg, command, *params, check=check, log_dir=log_dir)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"$ {format_command([str(cfg.xvf_host_path), '--use', cfg.protocol, command, *map(str, params)])}\n")
        handle.write(f"exit_code={result.returncode}\n")
        handle.write(result.stdout)
        if result.stderr:
            handle.write("\n[stderr]\n" + result.stderr)
        handle.write("\n" + "-" * 80 + "\n")
    return result


def dump_parameters(cfg: Config, output_path: Path) -> None:
    result = run_process(
        [str(cfg.xvf_host_path), "--use", cfg.protocol, "--dump-params"],
        timeout=max(cfg.command_timeout_sec, 30.0),
        check=False,
    )
    output_path.write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")


def capture_parameter_state(cfg: Config, run_dir: Path, filename: str) -> dict[str, dict[str, Any]]:
    state: dict[str, dict[str, Any]] = {}
    log = run_dir / "logs" / "xvf_host_commands.log"
    for command in TRACKED_PARAMETERS:
        result = run_and_log_host(cfg, log, command, check=False)
        state[command] = {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    write_json(run_dir / filename, state)
    return state


def numeric_tail(text: str, count: int) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    tokens = lines[-1].split()
    values: list[str] = []
    for token in reversed(tokens):
        if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", token):
            values.append(token)
            if len(values) == count:
                return list(reversed(values))
    return []


def parse_output_pair(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return []
    tokens = lines[-1].split()
    if len(tokens) >= 3 and tokens[-2].lstrip("+-").isdigit() and tokens[-1].lstrip("+-").isdigit():
        return [tokens[-2], tokens[-1]]
    if len(tokens) >= 3:
        match = re.search(r"([A-Za-z0-9_]+)\[(\d+)\]\s+([-+]?\d+)", lines[-1])
        if match:
            return [str(CATEGORY_TO_NUMBER.get(match.group(1), match.group(2))), match.group(3)]
    return []


def restore_parameter_state(cfg: Config, run_dir: Path, state: dict[str, dict[str, Any]]) -> list[str]:
    log = run_dir / "logs" / "xvf_host_commands.log"
    warnings: list[str] = []
    def get_text(name: str) -> str:
        return str(state.get(name, {}).get("stdout", ""))

    # USB_BIT_DEPTH reboots the device, so restore it first and then restore routing.
    bits = numeric_tail(get_text("USB_BIT_DEPTH"), 2)
    current_bits_result = host_command(cfg, "USB_BIT_DEPTH", check=False, log_dir=log.parent)
    current_bits = numeric_tail(current_bits_result.stdout, 2)
    if not bits:
        warnings.append("Could not parse USB_BIT_DEPTH for restoration")
    elif current_bits != bits:
        run_and_log_host(cfg, log, "USB_BIT_DEPTH", *bits, check=False)
        time.sleep(3.0)

    for command in ["AUDIO_MGR_OP_PACKED", "AUDIO_MGR_OP_UPSAMPLE", "I2S_INPUT_PACKED", "AUDIO_MGR_MIC_GAIN", "AUDIO_MGR_REF_GAIN", "AUDIO_MGR_SYS_DELAY", "AEC_ASROUTONOFF", "AEC_ASROUTGAIN"]:
        values = numeric_tail(get_text(command), 2 if command in {"AUDIO_MGR_OP_PACKED", "AUDIO_MGR_OP_UPSAMPLE"} else 1)
        if values:
            run_and_log_host(cfg, log, command, *values, check=False)
        else:
            warnings.append(f"Could not parse {command} for restoration")

    for command in ["AUDIO_MGR_OP_L_PK0", "AUDIO_MGR_OP_L_PK1", "AUDIO_MGR_OP_L_PK2", "AUDIO_MGR_OP_R_PK0", "AUDIO_MGR_OP_R_PK1", "AUDIO_MGR_OP_R_PK2"]:
        values = parse_output_pair(get_text(command))
        if values:
            run_and_log_host(cfg, log, command, *values, check=False)
        else:
            warnings.append(f"Could not parse {command} for restoration")
    write_json(run_dir / "restore_warnings.json", warnings)
    return warnings


def baseline(cfg: Config) -> Path:
    verify_paths(cfg)
    run_dir, start = run_start(cfg, "windows_baseline")
    log = run_dir / "logs" / "xvf_host_commands.log"
    summary: dict[str, Any] = {
        "created_local": datetime.now().isoformat(),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "config": config_to_dict(cfg),
        "checks": {},
    }
    checks = [
        ("VERSION", 3),
        ("AEC_NUM_MICS", 1),
        ("AEC_MIC_ARRAY_TYPE", 1),
        ("AEC_MIC_ARRAY_GEO", 12),
        ("AUDIO_MGR_OP_L", 2),
        ("AUDIO_MGR_OP_R", 2),
        ("USB_BIT_DEPTH", 2),
        ("AEC_ASROUTONOFF", 1),
        ("AEC_ASROUTGAIN", 1),
        ("I2S_INPUT_PACKED", 1),
        ("AUDIO_MGR_OP_PACKED", 2),
        ("AUDIO_MGR_OP_ALL", 12),
    ]
    for command, expected in checks:
        result = run_and_log_host(cfg, log, command, check=False)
        summary["checks"][command] = {
            "returncode": result.returncode,
            "values": last_values(result, expected),
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    dump_parameters(cfg, run_dir / "parameters_full.txt")
    capture_parameter_state(cfg, run_dir, "parameters_after.txt")
    device_selection = select_audio_devices(cfg)
    summary["audio_devices"] = device_selection
    summary["firmware_version"] = summary["checks"].get("VERSION", {}).get("values", [])
    summary["microphone_geometry"] = summary["checks"].get("AEC_MIC_ARRAY_GEO", {}).get("values", [])
    summary["duration_sec"] = time.monotonic() - start
    summary["end_time_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(run_dir / "baseline_summary.json", summary)
    write_json(run_dir / "metadata.json", {
        "test_name": "windows_baseline",
        "start_time_utc": summary["created_utc"],
        "end_time_utc": summary["end_time_utc"],
        "duration_sec": summary["duration_sec"],
        "python_executable": sys.executable,
        "python_version": sys.version,
        "project_path": str(PROJECT_ROOT),
        "xvf_host_path": str(cfg.xvf_host_path),
        "xvf_tools_path": str(cfg.xvf_tools_path),
        "firmware_version": summary["firmware_version"],
        "microphone_geometry": summary["microphone_geometry"],
        "audio_device_selection": device_selection,
        "commands_executed": list(summary["checks"]),
        "exit_status": max((int(item["returncode"]) for item in summary["checks"].values()), default=0),
    })
    return run_dir


def apply_profile(cfg: Config, profile: dict[str, Any], log_file: Path) -> None:
    for item in profile.get("commands", []):
        if not item:
            continue
        run_and_log_host(cfg, log_file, str(item[0]), *map(str, item[1:]))


def telemetry_worker(
    cfg: Config,
    output_csv: Path,
    stop_event: threading.Event,
    start_monotonic: float,
    sample_queue: queue.Queue[dict[str, Any]],
) -> None:
    fieldnames = [
        "elapsed_sec",
        "timestamp_local",
        "beam1_rad", "beam2_rad", "scan_rad", "auto_rad",
        "beam1_deg", "beam2_deg", "scan_deg", "auto_deg",
        "energy_beam1", "energy_beam2", "energy_scan", "energy_auto",
        "selected_processed_rad", "selected_auto_rad",
        "selected_processed_deg", "selected_auto_deg",
        "aec_converged", "aec_path_change",
        "poll_error",
    ]
    interval = 1.0 / max(cfg.telemetry_poll_hz, 0.2)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        while not stop_event.is_set():
            cycle_start = time.monotonic()
            row: dict[str, Any] = {
                "elapsed_sec": cycle_start - start_monotonic,
                "timestamp_local": datetime.now().isoformat(timespec="milliseconds"),
                "poll_error": "",
            }
            try:
                az = parse_angle_radians(host_command(cfg, "AEC_AZIMUTH_VALUES", check=False), 4)
                en = last_values(host_command(cfg, "AEC_SPENERGY_VALUES", check=False), 4)
                sel = parse_angle_radians(host_command(cfg, "AUDIO_MGR_SELECTED_AZIMUTHS", check=False), 2)
                conv = last_values(host_command(cfg, "AEC_AECCONVERGED", check=False), 1)
                path = last_values(host_command(cfg, "AEC_AECPATHCHANGE", check=False), 1)
                names = ["beam1", "beam2", "scan", "auto"]
                for name, value in zip(names, az):
                    row[f"{name}_rad"] = value
                    row[f"{name}_deg"] = math.degrees(value) if math.isfinite(value) else float("nan")
                for name, value in zip(names, en):
                    row[f"energy_{name}"] = value
                row["selected_processed_rad"] = sel[0]
                row["selected_auto_rad"] = sel[1]
                row["selected_processed_deg"] = math.degrees(sel[0]) if math.isfinite(sel[0]) else float("nan")
                row["selected_auto_deg"] = math.degrees(sel[1]) if math.isfinite(sel[1]) else float("nan")
                row["aec_converged"] = conv[0]
                row["aec_path_change"] = path[0]
            except Exception as exc:  # Keep audio recording alive even if one control poll fails.
                row["poll_error"] = repr(exc)
            writer.writerow(row)
            handle.flush()
            try:
                sample_queue.put_nowait(row)
            except queue.Full:
                pass
            remaining = interval - (time.monotonic() - cycle_start)
            if remaining > 0:
                stop_event.wait(remaining)


def record_audio(
    cfg: Config,
    duration: float,
    output_wav: Path,
    stop_event: threading.Event,
) -> tuple[np.ndarray, int]:
    selected = select_audio_devices(cfg)
    print(
        f"Selected XVF3800 audio pair: input index {selected['input_id']} '{selected['input']['name']}', "
        f"output index {selected['output_id']} '{selected['output']['name']}', API {selected['api']}"
    )
    device_id = int(selected["input_id"])
    frames = int(round(duration * cfg.sample_rate_hz))
    recording = sd.rec(
        frames,
        samplerate=cfg.sample_rate_hz,
        channels=cfg.record_channels,
        dtype="float32",
        device=device_id,
        blocking=False,
    )
    sd.wait()
    stop_event.set()
    sf.write(output_wav, recording, cfg.sample_rate_hz, subtype=cfg.record_subtype)
    return np.asarray(recording), device_id


def save_split_channels(data: np.ndarray, sample_rate: int, run_dir: Path, labels: list[str], subtype: str) -> None:
    if data.ndim == 1:
        data = data[:, None]
    for index in range(data.shape[1]):
        label = labels[index] if index < len(labels) else f"channel_{index + 1}"
        sf.write(run_dir / "output" / f"{index + 1:02d}_{sanitize(label)}.wav", data[:, index], sample_rate, subtype=subtype)


def audio_statistics(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Audio output is missing or empty: {path}")
    info = sf.info(str(path))
    data, sample_rate = sf.read(str(path), always_2d=True, dtype="float32")
    if data.size == 0:
        raise RuntimeError(f"Audio output contains no samples: {path}")
    absolute = np.abs(data)
    return {
        "file": str(path),
        "sha256": sha256_file(path),
        "sample_rate_hz": int(sample_rate),
        "channels": int(info.channels),
        "frames": int(info.frames),
        "duration_sec": float(info.frames / info.samplerate),
        "peak_absolute": float(np.max(absolute)),
        "rms": float(np.sqrt(np.mean(np.square(data)))),
        "exact_zero_percent": float(np.mean(data == 0.0) * 100.0),
        "clipping_count": int(np.count_nonzero(absolute >= 0.999999)),
    }


def write_audio_statistics(run_dir: Path, paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows = [audio_statistics(path) for path in paths if path.exists()]
    if not rows:
        raise RuntimeError(f"No audio files were available for statistics in {run_dir}")
    fieldnames = list(rows[0])
    with (run_dir / "output" / "audio_statistics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def plot_telemetry(csv_path: Path, run_dir: Path) -> None:
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return

    elapsed = np.array([safe_float(row.get("elapsed_sec")) for row in rows])
    selected = np.array([safe_float(row.get("selected_processed_deg")) for row in rows])
    auto = np.array([safe_float(row.get("auto_deg")) for row in rows])
    energy = np.array([safe_float(row.get("energy_auto")) for row in rows])

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(elapsed, selected, label="Processed selected DoA")
    ax.plot(elapsed, auto, label="Auto-selected beam")
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Angle (degrees)")
    ax.set_title("XVF3800 Direction of Arrival")
    ax.grid(True)
    ax.legend()
    fig.tight_layout()
    fig.savefig(run_dir / "output" / "doa_timeline.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(elapsed, energy)
    ax.set_xlabel("Elapsed time (s)")
    ax.set_ylabel("Auto-beam speech energy (relative)")
    ax.set_title("XVF3800 Speech Energy")
    ax.grid(True)
    fig.tight_layout()
    fig.savefig(run_dir / "output" / "speech_energy_timeline.png", dpi=160)
    plt.close(fig)


def live_plot_loop(sample_queue: queue.Queue[dict[str, Any]], stop_event: threading.Event) -> None:
    plt.ion()
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="polar")
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(-1)
    ax.set_title("XVF3800 selected Direction of Arrival")
    point, = ax.plot([0], [1], marker="o")
    text = ax.text(0.5, -0.10, "Waiting for telemetry", transform=ax.transAxes, ha="center")
    while not stop_event.is_set() or not sample_queue.empty():
        try:
            row = sample_queue.get(timeout=0.1)
        except queue.Empty:
            plt.pause(0.05)
            continue
        angle = safe_float(row.get("selected_processed_rad"))
        energy = safe_float(row.get("energy_auto"))
        if math.isfinite(angle):
            point.set_data([angle], [1])
            text.set_text(f"Selected DoA: {math.degrees(angle):.1f} deg | Speech energy: {energy:.5g}")
        else:
            text.set_text(f"No selected speech direction | Speech energy: {energy:.5g}")
        fig.canvas.draw_idle()
        plt.pause(0.01)
    plt.ioff()
    plt.close(fig)


def safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def record_test(cfg: Config, profile_path: Path, duration: float, live_plot: bool) -> Path:
    verify_paths(cfg)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    run_dir, start = run_start(cfg, profile["name"])
    start_utc = datetime.now(timezone.utc)
    shutil.copy2(profile_path, run_dir / "input" / profile_path.name)
    log = run_dir / "logs" / "xvf_host_commands.log"
    before_state = capture_parameter_state(cfg, run_dir, "parameters_before.json")
    global ACTIVE_RUN_CONTEXT
    ACTIVE_RUN_CONTEXT = (cfg, run_dir, before_state)
    dump_parameters(cfg, run_dir / "parameters_before.txt")
    stop_event = threading.Event()
    sample_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
    telemetry_csv = run_dir / "output" / "telemetry.csv"
    telemetry_thread = threading.Thread(target=telemetry_worker, args=(cfg, telemetry_csv, stop_event, start, sample_queue), daemon=True)
    audio_result: dict[str, Any] = {}
    selected = select_audio_devices(cfg)
    try:
        apply_profile(cfg, profile, log)
        dump_parameters(cfg, run_dir / "parameters_after_profile.txt")
        telemetry_thread.start()
        stereo_path = run_dir / "output" / "recording_stereo.wav"

        def audio_target() -> None:
            try:
                audio_result["value"] = record_audio(cfg, duration, stereo_path, stop_event)
            except Exception as exc:
                audio_result["error"] = exc
                stop_event.set()

        audio_thread = threading.Thread(target=audio_target, daemon=True)
        audio_thread.start()
        if live_plot:
            live_plot_loop(sample_queue, stop_event)
        audio_thread.join(timeout=duration + 15.0)
        stop_event.set()
        telemetry_thread.join(timeout=10)
        if "error" in audio_result:
            raise RuntimeError(f"Audio recording failed: {audio_result['error']}")
        if "value" not in audio_result:
            raise RuntimeError("Audio recording did not complete within the expected time.")
        audio_data, input_device_id = audio_result["value"]
        labels = [profile.get("left_label", "left"), profile.get("right_label", "right")]
        save_split_channels(audio_data, cfg.sample_rate_hz, run_dir, labels, cfg.record_subtype)
        plot_telemetry(telemetry_csv, run_dir)
        stats = write_audio_statistics(run_dir, [stereo_path, *(run_dir / "output").glob("0[12]_*.wav")])
        metadata = {
            "test_name": profile["name"],
            "test_type": "casual_recording",
            "profile": profile,
            "duration_sec": duration,
            "sample_rate_hz": cfg.sample_rate_hz,
            "channels": cfg.record_channels,
            "input_device_id": input_device_id,
            "audio_device_selection": selected,
            "audio_statistics": stats,
            "start_time_utc": start_utc.isoformat(),
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
            "important_note": "AEC_SPENERGY_VALUES is a relative internal speech-energy value, not calibrated sound pressure level or acoustic power.",
        }
        write_json(run_dir / "metadata.json", metadata)
    finally:
        if telemetry_thread.is_alive():
            stop_event.set()
            telemetry_thread.join(timeout=10)
        restore_parameter_state(cfg, run_dir, before_state)
        dump_parameters(cfg, run_dir / "parameters_after.txt")
        ACTIVE_RUN_CONTEXT = None
    return run_dir


def read_audio_mono(path: Path) -> tuple[np.ndarray, int]:
    if not path.is_file():
        raise FileNotFoundError(f"Input WAV not found: {path}")
    data, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    if data.size == 0:
        raise RuntimeError(f"Input WAV contains no samples: {path}")
    mono = np.mean(data, axis=1)
    return mono, int(sample_rate)


def resample_to_16k(data: np.ndarray, sample_rate: int) -> np.ndarray:
    if sample_rate == 16000:
        return data.astype(np.float32, copy=False)
    gcd = math.gcd(sample_rate, 16000)
    return resample_poly(data, 16000 // gcd, sample_rate // gcd).astype(np.float32)


def make_six_channel_vector(
    mono_path: Path,
    output_path: Path,
    mode: str = "DuplicateMics",
    mic_index: int | None = None,
    normalize_peak: float | None = 0.8,
) -> dict[str, Any]:
    mono, original_rate = read_audio_mono(mono_path)
    mono16 = resample_to_16k(mono, original_rate)
    if normalize_peak is not None:
        peak = float(np.max(np.abs(mono16))) if mono16.size else 0.0
        if peak > 0:
            mono16 = mono16 * (float(normalize_peak) / peak)
    mono16 = np.clip(mono16, -1.0, 1.0).astype(np.float32, copy=False)
    # The XMOS unpacker trims leading zero frames independently per USB
    # channel. A common zero frame keeps the two packed channels aligned even
    # when the source begins with a non-zero sample.
    mono16 = np.concatenate([np.zeros(1, dtype=np.float32), mono16])
    zero = np.zeros_like(mono16)
    normalized_mode = mode.lower()
    if normalized_mode in {"farendreference", "far_end_reference", "far-end-reference"}:
        normalized_mode = "far_end_reference"
        reference = mono16
        microphones = [zero, zero, zero, zero]
    elif normalized_mode in {"duplicatemics", "duplicate_mics", "duplicate-mics"}:
        normalized_mode = "duplicate_mics"
        reference = zero
        microphones = [mono16, mono16, mono16, mono16]
    elif normalized_mode in {"singlemic", "single_mic", "single-mic"}:
        normalized_mode = "single_mic"
        if mic_index is None or mic_index not in range(4):
            raise ValueError("SingleMic mode requires -MicIndex/-\u200b\u200b--mic-index 0, 1, 2, or 3")
        reference = zero
        microphones = [mono16 if index == mic_index else zero for index in range(4)]
    else:
        raise ValueError(f"Unsupported digital mono mode: {mode}. Use FarEndReference, DuplicateMics, or SingleMic.")
    six = np.column_stack([reference, zero, *microphones])
    sf.write(output_path, six, 16000, subtype="PCM_16")
    channel_map = {
        "channel_0": "far_end_reference" if normalized_mode == "far_end_reference" else "silence",
        "channel_1": "packing_convention_unused_silence",
        "channel_2": "mic0" if np.any(microphones[0]) else "silence",
        "channel_3": "mic1" if np.any(microphones[1]) else "silence",
        "channel_4": "mic2" if np.any(microphones[2]) else "silence",
        "channel_5": "mic3" if np.any(microphones[3]) else "silence",
    }
    write_json(output_path.parent / "channel_map.json", {
        "ordering": ["far_end_reference", "packing_convention_unused", "mic0", "mic1", "mic2", "mic3"],
        "mode": normalized_mode,
        "mic_index": mic_index,
        "channels": channel_map,
        "warning": (
            "DuplicateMics is deterministic routing data, not genuine four-microphone far-field data and is invalid for beamforming, DoA, dereverberation, or spatial-rejection evaluation."
            if normalized_mode == "duplicate_mics"
            else "FarEndReference injects only channel 0; substitute microphone channels are silence."
            if normalized_mode == "far_end_reference"
            else "SingleMic injects only the selected substitute microphone channel; it is not spatially valid four-microphone data."
        ),
    })
    return {
        "input_file": str(mono_path),
        "input_sha256": sha256_file(mono_path),
        "input_sample_rate_hz": original_rate,
        "output_file": str(output_path),
        "output_sample_rate_hz": 16000,
        "channels": ["far_end_reference", "packing_convention_unused", "mic0", "mic1", "mic2", "mic3"],
        "mode": normalized_mode,
        "mic_index": mic_index,
        "warning": "Duplicating one mono waveform into all four microphone channels contains no realistic spatial delays. It is unsuitable for evaluating beamforming or Direction of Arrival.",
    }


def split_unpacked_capture(
    unpacked_out: Path,
    run_dir: Path,
    subtype: str,
    labels: list[str] | None = None,
) -> dict[str, Any]:
    if not unpacked_out.exists():
        raise FileNotFoundError(f"Unpacked capture was not created: {unpacked_out}")
    unpacked, sample_rate = sf.read(unpacked_out, always_2d=True, dtype="float32")
    labels = labels or PACKED_OUTPUT_LABELS
    if int(sample_rate) != 16000 or unpacked.shape[1] != 6:
        raise RuntimeError(f"Expected unpacked capture at 16 kHz with 6 channels, got {sample_rate} Hz and {unpacked.shape[1]} channels")
    save_split_channels(unpacked, int(sample_rate), run_dir, labels, subtype)
    return {
        "unpacked_output_found": True,
        "sample_rate_hz": int(sample_rate),
        "channels": int(unpacked.shape[1]),
        "frames": int(unpacked.shape[0]),
        "labels": labels,
    }


def xmos_environment(cfg: Config) -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(cfg.xmos_pythonpath) + (os.pathsep + existing if existing else "")
    return env


def run_xmos_tool(cfg: Config, run_dir: Path, command: str, *args: str, timeout: float = 120.0) -> subprocess.CompletedProcess[str]:
    command_args = [str(cfg.python_executable), str(cfg.xvf_tools_path), command, *map(str, args)]
    return run_process(command_args, timeout=timeout, check=True, log_dir=run_dir / "logs", cwd=cfg.xmos_source_root, env=xmos_environment(cfg))


def run_packing_command(cfg: Config, run_dir: Path, command: str, input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    packing_script = cfg.xmos_pythonpath / "tuning" / "packing.py"
    command_args = [str(cfg.python_executable), str(packing_script), command, str(input_path), str(output_path), "-b", str(cfg.packed_bit_depth)]
    if command == "unpack":
        command_args.append("-s")
    result = run_process(command_args, timeout=120.0, check=True, log_dir=run_dir / "logs", cwd=cfg.xmos_source_root, env=xmos_environment(cfg))
    (run_dir / "logs" / f"packing_{command}.txt").write_text(
        f"$ {format_command(command_args)}\nexit_code={result.returncode}\n{result.stdout}\n{result.stderr}", encoding="utf-8"
    )
    return result


def verify_packed_prerequisites(cfg: Config, run_dir: Path) -> dict[str, Any]:
    selected = select_audio_devices(cfg)
    if "wdm" not in str(selected["api"]).lower():
        raise RuntimeError(f"Packed recorder requires the common WDM-KS XVF3800 pair; selected API was {selected['api']}")
    log = run_dir / "logs" / "xvf_host_commands.log"
    usb = run_and_log_host(cfg, log, "USB_BIT_DEPTH", check=False)
    bits = numeric_tail(usb.stdout, 2)
    expected = [str(cfg.packed_bit_depth), str(cfg.packed_bit_depth)]
    if usb.returncode != 0 or bits != expected:
        raise RuntimeError(f"USB_BIT_DEPTH must be {expected} before packed testing; returned {bits or usb.stdout.strip()}")
    firmware = run_and_log_host(cfg, log, "VERSION", check=False)
    if firmware.returncode != 0:
        raise RuntimeError(f"XVF3800 VERSION command failed: {firmware.stderr.strip()}")
    return {"audio_device_selection": selected, "usb_bit_depth": bits, "firmware": firmware.stdout.strip()}


def packed_capture_test(cfg: Config, duration: float, label: str, asr_output: bool = False) -> Path:
    verify_paths(cfg, require_tools=True)
    run_dir, start = run_start(cfg, label)
    start_utc = datetime.now(timezone.utc)
    before_state = capture_parameter_state(cfg, run_dir, "parameters_before.json")
    global ACTIVE_RUN_CONTEXT
    ACTIVE_RUN_CONTEXT = (cfg, run_dir, before_state)
    dump_parameters(cfg, run_dir / "parameters_before.txt")
    prerequisite_meta = verify_packed_prerequisites(cfg, run_dir)

    packed_out = run_dir / "output" / "raw_capture_48k_stereo.wav"
    tool_unpacked_out = run_dir / "output" / "unpacked_capture_tool_32bit.wav"
    unpacked_out = run_dir / "output" / "unpacked_capture_16k_6ch.wav"
    packed_command = cfg.asr_packed_output_command if asr_output else cfg.packed_output_command
    output_labels = ASR_PACKED_OUTPUT_LABELS if asr_output else PACKED_OUTPUT_LABELS
    recorder_cmd = [
        str(cfg.python_executable),
        str(cfg.xvf_tools_path),
        "packed_recorder",
        str(cfg.xvf_host_path),
        "--protocol",
        cfg.protocol,
        "--recording_length",
        str(duration),
        "--bit_depth",
        str(cfg.packed_bit_depth),
        "--packed_output",
        "--packed_output_file",
        str(packed_out),
        "--unpacked_output_file",
        str(tool_unpacked_out),
        "--op_all",
        packed_command,
    ]
    if asr_output:
        recorder_cmd.append("--asr_output")

    stop_event = threading.Event()
    sample_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
    start = time.monotonic()
    telemetry_csv = run_dir / "output" / "telemetry.csv"
    telemetry_thread = threading.Thread(
        target=telemetry_worker,
        args=(cfg, telemetry_csv, stop_event, start, sample_queue),
        daemon=True,
    )
    telemetry_thread.start()
    try:
        recorder_result = run_process(
            recorder_cmd,
            timeout=max(120.0, duration + 60.0),
            check=True,
            log_dir=run_dir / "logs",
            cwd=cfg.xmos_source_root,
            env=xmos_environment(cfg),
        )
        (run_dir / "logs" / "packed_recorder.txt").write_text(
            f"$ {format_command(recorder_cmd)}\nexit_code={recorder_result.returncode}\n" + recorder_result.stdout + "\n" + recorder_result.stderr, encoding="utf-8"
        )
        run_packing_command(cfg, run_dir, "unpack", packed_out, unpacked_out)
    finally:
        stop_event.set()
        telemetry_thread.join(timeout=10)

    capture_meta = split_unpacked_capture(unpacked_out, run_dir, cfg.record_subtype, output_labels)
    plot_telemetry(telemetry_csv, run_dir)
    output_files = [packed_out, unpacked_out, *(run_dir / "output").glob("0[1-6]_*.wav")]
    stats = write_audio_statistics(run_dir, output_files)
    restore_warnings = restore_parameter_state(cfg, run_dir, before_state)
    dump_parameters(cfg, run_dir / "parameters_after.txt")
    ACTIVE_RUN_CONTEXT = None
    write_json(
        run_dir / "metadata.json",
        {
            "test_name": label,
            "test_type": "packed_asr_physical_capture" if asr_output else "packed_six_channel_physical_capture",
            "start_time_utc": start_utc.isoformat(),
            "end_time_utc": datetime.now(timezone.utc).isoformat(),
            "duration_sec": duration,
            "python_executable": sys.executable,
            "python_version": sys.version,
            "project_path": str(PROJECT_ROOT),
            "xvf_host_path": str(cfg.xvf_host_path),
            "xvf_tools_path": str(cfg.xvf_tools_path),
            "firmware_version": prerequisite_meta["firmware"],
            "audio_device_selection": prerequisite_meta["audio_device_selection"],
            "usb_sample_rate_hz": cfg.sample_rate_hz,
            "usb_bit_depth": cfg.packed_bit_depth,
            "packed_bit_depth": cfg.packed_bit_depth,
            "packed_output_command": packed_command,
            "packed_output_order": output_labels,
            "asr_output_enabled": asr_output,
            "asr_output_route": (
                {
                    "AEC_ASROUTONOFF": 1,
                    "mux_category": 7,
                    "mux_source": 3,
                    "label": "asr_processed_auto_selected",
                }
                if asr_output
                else None
            ),
            "capture": capture_meta,
            "audio_statistics": stats,
            "command": recorder_cmd,
            "restore_warnings": restore_warnings,
            "exit_status": 0,
            "important_note": (
                "ASR output was enabled with AEC_ASROUTONOFF=1. AUDIO_MGR_OP_ALL uses category 7 source 3 for the automatic speech-recognition auto-selected beam."
                if asr_output
                else "The release default AUDIO_MGR_OP_ALL is unpacked as (L_PK0, R_PK0, L_PK1, R_PK1, L_PK2, R_PK2): far-end reference, processed auto-selected beam, amplified MIC0, amplified MIC1, amplified MIC2, amplified MIC3."
            ),
        },
    )
    return run_dir


def digital_mono_test(
    cfg: Config,
    mono_path: Path,
    label: str,
    mode: str,
    mic_index: int | None,
    normalize_peak: float | None,
    asr_output: bool = False,
) -> Path:
    verify_paths(cfg, require_tools=True)
    run_dir, start = run_start(cfg, label)
    start_utc = datetime.now(timezone.utc)
    log = run_dir / "logs" / "xvf_host_commands.log"
    before_state = capture_parameter_state(cfg, run_dir, "parameters_before.json")
    global ACTIVE_RUN_CONTEXT
    ACTIVE_RUN_CONTEXT = (cfg, run_dir, before_state)
    prerequisite_meta = verify_packed_prerequisites(cfg, run_dir)
    copied_input = run_dir / "input" / mono_path.name
    if not mono_path.is_file():
        raise FileNotFoundError(f"Input WAV not found: {mono_path}")
    shutil.copy2(mono_path, copied_input)

    six_path = run_dir / "input" / "injection_vector_16k_6ch.wav"
    vector_meta = make_six_channel_vector(copied_input, six_path, mode, mic_index, normalize_peak)
    packed_path = run_dir / "input" / "packed_input_48k_stereo.wav"
    run_packing_command(cfg, run_dir, "pack", six_path, packed_path)

    if cfg.reset_before_digital_test:
        run_and_log_host(cfg, log, "TEST_CORE_BURN", "0", check=False)
        time.sleep(3.0)

    dump_parameters(cfg, run_dir / "parameters_before.txt")

    packed_out = run_dir / "output" / "raw_capture_48k_stereo.wav"
    tool_unpacked_out = run_dir / "output" / "unpacked_capture_tool_32bit.wav"
    unpacked_out = run_dir / "output" / "unpacked_capture_16k_6ch.wav"
    packed_command = cfg.asr_packed_output_command if asr_output else cfg.packed_output_command
    output_labels = ASR_PACKED_OUTPUT_LABELS if asr_output else PACKED_OUTPUT_LABELS
    recorder_cmd = [
        str(cfg.python_executable),
        str(cfg.xvf_tools_path),
        "packed_recorder",
        str(cfg.xvf_host_path),
        "--protocol",
        cfg.protocol,
        "--playback_file",
        str(packed_path),
        "--packed_input",
        "--packed_output",
        "--bit_depth",
        str(cfg.packed_bit_depth),
        "--packed_output_file",
        str(packed_out),
        "--unpacked_output_file",
        str(tool_unpacked_out),
        "--op_all",
        packed_command,
    ]
    if asr_output:
        recorder_cmd.append("--asr_output")

    stop_event = threading.Event()
    sample_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=100)
    start = time.monotonic()
    telemetry_csv = run_dir / "output" / "telemetry.csv"
    telemetry_thread = threading.Thread(
        target=telemetry_worker,
        args=(cfg, telemetry_csv, stop_event, start, sample_queue),
        daemon=True,
    )
    telemetry_thread.start()
    try:
        recorder_result = run_process(
            recorder_cmd,
            timeout=600,
            check=True,
            log_dir=run_dir / "logs",
            cwd=cfg.xmos_source_root,
            env=xmos_environment(cfg),
        )
        (run_dir / "logs" / "packed_recorder.txt").write_text(
            f"$ {format_command(recorder_cmd)}\nexit_code={recorder_result.returncode}\n" + recorder_result.stdout + "\n" + recorder_result.stderr,
            encoding="utf-8",
        )
        run_packing_command(cfg, run_dir, "unpack", packed_out, unpacked_out)
    finally:
        stop_event.set()
        telemetry_thread.join(timeout=10)

    capture_meta = split_unpacked_capture(unpacked_out, run_dir, cfg.record_subtype, output_labels)
    plot_telemetry(telemetry_csv, run_dir)
    stats = write_audio_statistics(run_dir, [copied_input, six_path, packed_path, packed_out, unpacked_out, *(run_dir / "output").glob("0[1-6]_*.wav")])
    restore_warnings = restore_parameter_state(cfg, run_dir, before_state)
    dump_parameters(cfg, run_dir / "parameters_after.txt")
    ACTIVE_RUN_CONTEXT = None

    unpacked_info = sf.info(str(unpacked_out))
    metadata = {
        "test_name": label,
        "test_type": "digital_mono_asr_hardware_in_loop" if asr_output else "digital_mono_processed_hardware_in_loop",
        "start_time_utc": start_utc.isoformat(),
        "end_time_utc": datetime.now(timezone.utc).isoformat(),
        "duration_sec": float(unpacked_info.frames / unpacked_info.samplerate),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "project_path": str(PROJECT_ROOT),
        "xvf_host_path": str(cfg.xvf_host_path),
        "xvf_tools_path": str(cfg.xvf_tools_path),
        "firmware_version": prerequisite_meta["firmware"],
        "audio_device_selection": prerequisite_meta["audio_device_selection"],
        "usb_sample_rate_hz": cfg.sample_rate_hz,
        "usb_bit_depth": cfg.packed_bit_depth,
        "vector": vector_meta,
        "packed_bit_depth": cfg.packed_bit_depth,
        "packed_output_command": packed_command,
        "packed_output_order": output_labels,
        "asr_output_enabled": asr_output,
        "asr_output_route": (
            {
                "AEC_ASROUTONOFF": 1,
                "mux_category": 7,
                "mux_source": 3,
                "label": "asr_processed_auto_selected",
            }
            if asr_output
            else None
        ),
        "capture": capture_meta,
        "audio_statistics": stats,
        "restore_warnings": restore_warnings,
        "commands": {
            "pack": [str(cfg.python_executable), str(cfg.xmos_pythonpath / "tuning" / "packing.py"), "pack", str(six_path), str(packed_path), "-b", str(cfg.packed_bit_depth)],
            "packed_recorder": recorder_cmd,
        },
        "exit_status": 0,
        "interpretation": {
            "valid_for": [
                "USB packed transport verification",
                "repeatable gain and signal-routing tests",
                "ASR-output regression testing" if asr_output else "normal processed-output regression testing",
                "firmware regression testing that does not depend on spatial processing",
            ],
            "not_valid_for": [
                "beamforming gain",
                "Direction of Arrival accuracy",
                "spatial noise rejection",
                "microphone geometry performance",
            ],
        },
    }
    write_json(run_dir / "metadata.json", metadata)
    return run_dir


def compare_runs(run_a: Path, run_b: Path) -> Path:
    run_a = run_a.resolve()
    run_b = run_b.resolve()
    files = ["unpacked_capture_16k_6ch.wav", "02_processed_auto_selected.wav", "03_amplified_mic0.wav"]
    comparison: dict[str, Any] = {
        "run_a": str(run_a),
        "run_b": str(run_b),
        "files": {},
        "bit_identical_all": True,
    }
    for name in files:
        path_a = run_a / "output" / name
        path_b = run_b / "output" / name
        if not path_a.exists() or not path_b.exists():
            comparison["files"][name] = {"status": "missing", "path_a": str(path_a), "path_b": str(path_b)}
            comparison["bit_identical_all"] = False
            continue
        data_a, rate_a = sf.read(path_a, always_2d=True, dtype="float64")
        data_b, rate_b = sf.read(path_b, always_2d=True, dtype="float64")
        sample_count_equal = data_a.shape == data_b.shape
        overlap_frames = min(data_a.shape[0], data_b.shape[0])
        same_channels = data_a.shape[1] == data_b.shape[1]
        max_difference = float("nan")
        if same_channels and overlap_frames:
            max_difference = float(np.max(np.abs(data_a[:overlap_frames] - data_b[:overlap_frames])))
        bit_identical = sha256_file(path_a) == sha256_file(path_b)
        comparison["files"][name] = {
            "sample_rate_a": int(rate_a),
            "sample_rate_b": int(rate_b),
            "shape_a": list(data_a.shape),
            "shape_b": list(data_b.shape),
            "duration_a_sec": float(data_a.shape[0] / rate_a),
            "duration_b_sec": float(data_b.shape[0] / rate_b),
            "peak_a": float(np.max(np.abs(data_a))),
            "peak_b": float(np.max(np.abs(data_b))),
            "rms_a": float(np.sqrt(np.mean(np.square(data_a)))),
            "rms_b": float(np.sqrt(np.mean(np.square(data_b)))),
            "sha256_a": sha256_file(path_a),
            "sha256_b": sha256_file(path_b),
            "bit_identical": bit_identical,
            "sample_count_equal": sample_count_equal,
            "overlap_frames": overlap_frames,
            "unmatched_frames": abs(data_a.shape[0] - data_b.shape[0]),
            "max_abs_sample_difference": max_difference,
        }
        comparison["bit_identical_all"] = comparison["bit_identical_all"] and bit_identical
    output = run_b / "repeatability_comparison.json"
    write_json(output, comparison)
    print(json.dumps(comparison, indent=2))
    print(f"Saved repeatability comparison: {output}")
    return output


def config_to_dict(cfg: Config) -> dict[str, Any]:
    return {
        "workspace_root": str(cfg.workspace_root),
        "xvf_host_path": str(cfg.xvf_host_path),
        "xvf_tools_path": str(cfg.xvf_tools_path),
        "python_executable": cfg.python_executable,
        "protocol": cfg.protocol,
        "audio_input_device_contains": cfg.audio_input_device_contains,
        "audio_output_device_contains": cfg.audio_output_device_contains,
        "sample_rate_hz": cfg.sample_rate_hz,
        "record_channels": cfg.record_channels,
        "record_subtype": cfg.record_subtype,
        "telemetry_poll_hz": cfg.telemetry_poll_hz,
        "command_timeout_sec": cfg.command_timeout_sec,
        "reset_before_digital_test": cfg.reset_before_digital_test,
        "packed_bit_depth": cfg.packed_bit_depth,
        "xmos_source_root": str(cfg.xmos_source_root),
        "xmos_pythonpath": str(cfg.xmos_pythonpath),
        "audio_api_preference": list(cfg.audio_api_preference),
        "packed_output_command": cfg.packed_output_command,
        "asr_packed_output_command": cfg.asr_packed_output_command,
    }


def project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description="XVF3800 Windows testing and logging harness")
    sub = parser.add_subparsers(dest="command", required=True)

    devices_parser = sub.add_parser("devices", help="List Windows audio devices visible to PortAudio")
    devices_parser.add_argument("--config", type=Path, default=Path("config.json"))

    baseline_parser = sub.add_parser("baseline", help="Capture firmware, geometry, routing, and parameter baseline")
    baseline_parser.add_argument("--config", type=Path, default=Path("config.json"))

    record_parser = sub.add_parser("record", help="Apply a routing profile, record stereo audio, and log live DoA/energy")
    record_parser.add_argument("--config", type=Path, default=Path("config.json"))
    record_parser.add_argument("--profile", type=Path, required=True)
    record_parser.add_argument("--duration", type=float, default=30.0)
    record_parser.add_argument("--live-plot", action="store_true")

    vector_parser = sub.add_parser("make-vector", help="Convert mono audio to a 16 kHz, six-channel XVF3800 injection vector")
    vector_parser.add_argument("mono_file", type=Path)
    vector_parser.add_argument("output_file", type=Path)
    vector_parser.add_argument("--mode", choices=["FarEndReference", "DuplicateMics", "SingleMic"], default="DuplicateMics")
    vector_parser.add_argument("--mic-index", type=int, default=None)
    vector_parser.add_argument("--far-end-reference", action="store_true", help="Compatibility alias for --mode FarEndReference")
    vector_parser.add_argument("--normalize-peak", type=float, default=0.8)

    packed_parser = sub.add_parser("packed-capture", help="Capture the default six internal signals using packed USB output")
    packed_parser.add_argument("--config", type=Path, default=Path("config.json"))
    packed_parser.add_argument("--duration", type=float, default=15.0)
    packed_parser.add_argument("--label", default="packed_six_channel_capture")

    asr_parser = sub.add_parser("asr-capture", help="Capture the packed automatic speech-recognition output")
    asr_parser.add_argument("--config", type=Path, default=Path("config.json"))
    asr_parser.add_argument("--duration", type=float, default=15.0)
    asr_parser.add_argument("--label", default="packed_asr_capture")

    digital_parser = sub.add_parser("digital-mono", help="Run packed digital injection/capture using a mono source")
    digital_parser.add_argument("--config", type=Path, default=Path("config.json"))
    digital_parser.add_argument("mono_file", type=Path)
    digital_parser.add_argument("--label", default="digital_mono_processed_duplicate_4mic")
    digital_parser.add_argument("--mode", choices=["FarEndReference", "DuplicateMics", "SingleMic"], default="DuplicateMics")
    digital_parser.add_argument("--mic-index", type=int, default=None)
    digital_parser.add_argument("--far-end-reference", action="store_true", help="Compatibility alias for --mode FarEndReference")
    digital_parser.add_argument("--normalize-peak", type=float, default=0.8)
    digital_parser.add_argument("--asr-output", action="store_true", help="Enable ASR-processed output; default is normal processed auto-selected output")

    compare_parser = sub.add_parser("compare-runs", help="Compare deterministic digital-test outputs from two run folders")
    compare_parser.add_argument("run_a", type=Path)
    compare_parser.add_argument("run_b", type=Path)

    args = parser.parse_args()
    if hasattr(args, "config"):
        args.config = project_path(args.config)
    if hasattr(args, "profile"):
        args.profile = project_path(args.profile)
    if hasattr(args, "mono_file"):
        args.mono_file = project_path(args.mono_file)

    if args.command == "devices":
        cfg = load_config(args.config)
        print(sd.query_devices())
        selected = select_audio_devices(cfg)
        print(json.dumps({"selected": selected}, indent=2, default=str))
        return 0

    if args.command == "make-vector":
        args.mono_file = project_path(args.mono_file)
        args.output_file = project_path(args.output_file)
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        mode = "FarEndReference" if args.far_end_reference else args.mode
        meta = make_six_channel_vector(args.mono_file, args.output_file, mode, args.mic_index, args.normalize_peak)
        print(json.dumps(meta, indent=2))
        return 0

    if args.command == "compare-runs":
        compare_runs(project_path(args.run_a), project_path(args.run_b))
        return 0

    cfg = load_config(args.config)

    if args.command == "baseline":
        run_dir = baseline(cfg)
    elif args.command == "record":
        run_dir = record_test(cfg, args.profile, args.duration, args.live_plot)
    elif args.command == "packed-capture":
        run_dir = packed_capture_test(cfg, args.duration, args.label)
    elif args.command == "asr-capture":
        run_dir = packed_capture_test(cfg, args.duration, args.label, asr_output=True)
    elif args.command == "digital-mono":
        mode = "FarEndReference" if args.far_end_reference else args.mode
        run_dir = digital_mono_test(cfg, args.mono_file, args.label, mode, args.mic_index, args.normalize_peak, args.asr_output)
    else:
        parser.error("Unsupported command")
        return 2

    print(f"Completed. Results: {run_dir}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as exc:
        if ACTIVE_RUN_CONTEXT is not None:
            active_cfg, active_run_dir, active_state = ACTIVE_RUN_CONTEXT
            try:
                write_json(active_run_dir / "failure.json", {"error": repr(exc), "exit_status": 1})
                restore_parameter_state(active_cfg, active_run_dir, active_state)
                dump_parameters(active_cfg, active_run_dir / "parameters_after.txt")
            except Exception as restore_exc:
                print(f"WARNING: temporary parameter restoration also failed: {restore_exc}", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
