"""Verify just-peachy dependencies, external tools, caches, and pipeline config."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_ROOT = PROJECT_ROOT / "Software Validation from Datasets" / "Evaluation Tool"
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "models" / "cache"
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))


@dataclass(frozen=True)
class CheckResult:
    label: str
    status: str
    detail: str
    required: bool = True


def import_check(module_name: str, *, required: bool = True) -> CheckResult:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return CheckResult(module_name, "FAIL" if required else "SKIP", str(exc), required)
    return CheckResult(module_name, "PASS", "importable", required)


def command_check(command: str, *, required: bool = True) -> CheckResult:
    path = shutil.which(command)
    if path:
        return CheckResult(command, "PASS", path, required)
    return CheckResult(command, "FAIL" if required else "SKIP", "not found on PATH", required)


def cuda_check(device: str) -> CheckResult:
    try:
        import torch
    except Exception as exc:
        return CheckResult("CUDA", "FAIL", f"PyTorch import failed: {exc}", device == "cuda")
    available = bool(torch.cuda.is_available())
    if device == "cuda" and not available:
        return CheckResult("CUDA", "FAIL", "requested but torch.cuda.is_available() is false")
    if available:
        name = torch.cuda.get_device_name(0)
        return CheckResult("CUDA", "PASS", name, device == "cuda")
    return CheckResult("CUDA", "SKIP", "not available; CPU execution is supported", False)


def whisper_cache_check(
    models: list[str],
    cache_root: Path,
    *,
    required: bool,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    aliases = {"turbo": "large-v3-turbo", "large": "large-v3"}
    for model_name in models:
        filename = f"{aliases.get(model_name, model_name)}.pt"
        path = cache_root / "whisper" / filename
        status = "PASS" if path.is_file() else "FAIL" if required else "SKIP"
        detail = str(path) if path.is_file() else f"missing: {path}"
        results.append(CheckResult(f"Whisper model {model_name}", status, detail, required))
    return results


def speechbrain_cache_check(cache_root: Path, *, required: bool) -> CheckResult:
    path = cache_root / "speechbrain" / "spkrec-ecapa-voxceleb"
    markers = [path / "hyperparams.yaml", *path.glob("*.ckpt")]
    available = any(marker.is_file() for marker in markers)
    status = "PASS" if available else "FAIL" if required else "SKIP"
    return CheckResult(
        "SpeechBrain ECAPA assets",
        status,
        str(path) if available else f"missing model markers under {path}",
        required,
    )


def pipeline_config_check() -> CheckResult:
    try:
        from app.inference_pipeline.config import PipelineConfig
        from app.inference_pipeline.registry import resolve_components

        config_path = (
            TOOL_ROOT
            / "configs"
            / "inference"
            / "live_mic_realtime_whisper_base_speaker_matching.yaml"
        )
        config = PipelineConfig.from_yaml_path(config_path)
        resolved = resolve_components(config)
        selected = ", ".join(
            f"{slot}={component.name}" for slot, component in resolved.items()
        )
    except Exception as exc:
        return CheckResult("Pipeline config", "FAIL", str(exc))
    return CheckResult("Pipeline config", "PASS", selected)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("core", "inference", "full", "dev"),
        default="inference",
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--whisper", default="base")
    parser.add_argument("--require-models", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    checks: list[CheckResult] = []
    core_modules = (
        "numpy",
        "pandas",
        "pyarrow",
        "yaml",
        "scipy",
        "soundfile",
        "tqdm",
        "matplotlib",
        "sklearn",
        "jiwer",
    )
    checks.extend(import_check(module) for module in core_modules)

    if args.profile != "core":
        inference_modules = (
            "torch",
            "torchaudio",
            "whisper",
            "speechbrain",
            "silero_vad",
            "sounddevice",
        )
        checks.extend(import_check(module) for module in inference_modules)
        checks.append(command_check("ffmpeg"))
        checks.append(cuda_check(args.device))
        models = [item.strip() for item in args.whisper.split(",") if item.strip()]
        checks.extend(
            whisper_cache_check(
                models,
                args.cache_root.resolve(),
                required=args.require_models,
            )
        )
        checks.append(
            speechbrain_cache_check(
                args.cache_root.resolve(),
                required=args.require_models,
            )
        )

    if args.profile == "full":
        checks.append(import_check("faster_whisper"))
        checks.append(import_check("pyannote.audio"))
    if args.profile == "dev":
        checks.extend(import_check(module) for module in ("pytest", "ruff", "mypy"))
    checks.append(pipeline_config_check())

    for check in checks:
        print(f"[{check.status}] {check.label}: {check.detail}")
    failures = [check for check in checks if check.status == "FAIL" and check.required]
    print(f"Verification complete: {len(checks) - len(failures)}/{len(checks)} checks non-failing")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
