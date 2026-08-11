"""Verify just-peachy dependencies, external tools, caches, and pipeline config."""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TOOL_ROOT = PROJECT_ROOT / "Software Validation from Datasets" / "Evaluation Tool"
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "models" / "cache"
ALLOWED_WHISPER_MODELS = frozenset(
    {"tiny", "tiny.en", "base", "base.en", "small", "small.en"}
)
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))


@dataclass(frozen=True)
class CheckResult:
    label: str
    status: str
    detail: str
    required: bool = True
    category: str = "RUNTIME"


def _distribution_version(module_name: str) -> str | None:
    distribution_names = {
        "yaml": "PyYAML",
        "sklearn": "scikit-learn",
        "soundfile": "soundfile",
        "whisper": "openai-whisper",
        "silero_vad": "silero-vad",
        "pyannote.audio": "pyannote.audio",
        "sherpa_onnx": "sherpa-onnx",
        "webrtcvad": "webrtcvad-wheels",
    }
    try:
        return metadata.version(distribution_names.get(module_name, module_name))
    except Exception:
        return None


def import_check(module_name: str, *, required: bool = True) -> CheckResult:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return CheckResult(
            module_name,
            "MISSING" if required else "OPTIONAL",
            f"import failed: {exc}",
            required,
            "PACKAGE",
        )
    version = _distribution_version(module_name)
    detail = "importable" if version is None else f"importable (version {version})"
    return CheckResult(module_name, "PRESENT", detail, required, "PACKAGE")


def wenet_import_check() -> CheckResult:
    """Verify WeNet through the compatibility shim used by its pipeline adapter."""

    try:
        from app.inference_pipeline.asr.wenet_adapter import (
            _prepare_wenet_torch_compatibility,
        )

        _prepare_wenet_torch_compatibility()
    except Exception as exc:
        return CheckResult(
            "wenet",
            "MISSING",
            f"adapter compatibility setup failed: {exc}",
            True,
            "PACKAGE",
        )
    result = import_check("wenet")
    return CheckResult(
        result.label,
        result.status,
        f"{result.detail}; loaded through adapter compatibility setup",
        result.required,
        result.category,
    )


def command_check(command: str, *, required: bool = True) -> CheckResult:
    path = shutil.which(command)
    if path:
        return CheckResult(command, "PRESENT", path, required, "SYSTEM")
    return CheckResult(
        command,
        "MISSING" if required else "OPTIONAL",
        "not found on PATH",
        required,
        "SYSTEM",
    )


def cuda_check(device: str) -> CheckResult:
    try:
        import torch
    except Exception as exc:
        return CheckResult(
            "CUDA",
            "MISSING" if device == "cuda" else "OPTIONAL",
            f"PyTorch import failed: {exc}",
            device == "cuda",
            "DEVICE",
        )
    available = bool(torch.cuda.is_available())
    if device == "cuda" and not available:
        return CheckResult(
            "CUDA",
            "MISSING",
            "requested but torch.cuda.is_available() is false",
            True,
            "DEVICE",
        )
    if available:
        if torch.version.cuda is None or "+cpu" in str(torch.__version__).lower():
            return CheckResult(
                "CUDA",
                "MISSING" if device == "cuda" else "OPTIONAL",
                f"CPU-only PyTorch build detected: torch={torch.__version__}",
                device == "cuda",
                "DEVICE",
            )
        try:
            name = torch.cuda.get_device_name(0)
            probe = torch.empty(1, device="cuda:0")
            torch.cuda.synchronize(0)
            del probe
        except Exception as exc:
            return CheckResult(
                "CUDA",
                "MISSING" if device == "cuda" else "OPTIONAL",
                f"CUDA device 0 could not be opened: {type(exc).__name__}: {exc}",
                device == "cuda",
                "DEVICE",
            )
        cudnn = torch.backends.cudnn.version()
        return CheckResult(
            "CUDA",
            "PRESENT",
            (
                f"{name}; torch={torch.__version__}; "
                f"torch CUDA runtime={torch.version.cuda}; cuDNN={cudnn}"
            ),
            device == "cuda",
            "DEVICE",
        )
    return CheckResult(
        "CUDA",
        "OPTIONAL",
        "not available; CPU execution is supported",
        False,
        "DEVICE",
    )


def whisper_cache_check(
    models: list[str],
    cache_root: Path,
    *,
    required: bool,
) -> list[CheckResult]:
    results: list[CheckResult] = []
    for model_name in models:
        filename = f"{model_name}.pt"
        path = cache_root / "whisper" / filename
        available = path.is_file() and path.stat().st_size > 0
        status = "PRESENT" if available else "MISSING" if required else "OPTIONAL"
        detail = str(path) if available else f"missing or empty: {path}"
        results.append(
            CheckResult(
                f"Whisper model {model_name}",
                status,
                detail,
                required,
                "ASSET",
            )
        )
    return results


def speechbrain_cache_check(cache_root: Path, *, required: bool) -> CheckResult:
    path = cache_root / "speechbrain" / "spkrec-ecapa-voxceleb"
    markers = [path / "hyperparams.yaml", path / "embedding_model.ckpt"]
    available = all(
        marker.is_file() and marker.stat().st_size > 0 for marker in markers
    )
    status = "PRESENT" if available else "MISSING" if required else "OPTIONAL"
    return CheckResult(
        "SpeechBrain ECAPA assets",
        status,
        str(path) if available else f"missing model markers under {path}",
        required,
        "ASSET",
    )


def model_asset_check(
    label: str,
    path: Path,
    *,
    required: bool,
) -> CheckResult:
    available = path.is_file() and path.stat().st_size > 0
    status = "PRESENT" if available else "MISSING" if required else "OPTIONAL"
    return CheckResult(
        label,
        status,
        str(path) if available else f"missing: {path}",
        required,
        "ASSET",
    )


def model_assets_check(
    label: str,
    root: Path,
    markers: tuple[str, ...],
    *,
    required: bool,
) -> CheckResult:
    missing = [
        marker
        for marker in markers
        if not (root / marker).is_file() or (root / marker).stat().st_size == 0
    ]
    status = "PRESENT" if not missing else "MISSING" if required else "OPTIONAL"
    detail = str(root) if not missing else f"missing under {root}: {', '.join(missing)}"
    return CheckResult(label, status, detail, required, "ASSET")


def environment_check(variable: str, *, backend: str) -> CheckResult:
    configured = bool(os.environ.get(variable))
    return CheckResult(
        f"{backend} credential ({variable})",
        "PRESENT" if configured else "GATED",
        "configured" if configured else "not set; backend cannot be qualified",
        False,
        "CREDENTIAL",
    )


def pyannote_asset_check(cache_root: Path, *, required: bool) -> CheckResult:
    root = cache_root / "pyannote"
    markers = tuple(root.rglob("config.yaml")) if root.is_dir() else ()
    available = any(
        "speaker-diarization-community-1" in str(path.parent) for path in markers
    )
    token_present = bool(os.environ.get("PYANNOTE_AUTH_TOKEN"))
    if available:
        status = "PRESENT"
        detail = str(root)
    elif not token_present:
        status = "GATED"
        detail = "model absent and PYANNOTE_AUTH_TOKEN is not set"
    else:
        status = "MISSING" if required else "OPTIONAL"
        detail = f"model snapshot missing under {root}"
    return CheckResult(
        "pyannote Community-1 assets",
        status,
        detail,
        required and token_present,
        "ASSET",
    )


def platform_check(
    label: str,
    *,
    supported: bool,
    detail: str,
    required: bool = False,
) -> CheckResult:
    return CheckResult(
        label,
        "SUPPORTED" if supported else "UNSUPPORTED",
        detail,
        required,
        "PLATFORM",
    )


def qualification_check(label: str, detail: str) -> CheckResult:
    return CheckResult(label, "NOT_RUN", detail, False, "QUALIFICATION")


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
        return CheckResult("Pipeline config", "MISSING", str(exc), True, "CONFIG")
    return CheckResult("Pipeline config", "PRESENT", selected, True, "CONFIG")


def parse_whisper_models(value: str) -> list[str]:
    models = [item.strip() for item in value.split(",") if item.strip()]
    rejected = [model for model in models if model not in ALLOWED_WHISPER_MODELS]
    if rejected:
        allowed = ", ".join(sorted(ALLOWED_WHISPER_MODELS))
        raise ValueError(
            "Whisper model(s) are prohibited or unsupported: "
            f"{', '.join(rejected)}. Allowed models: {allowed}"
        )
    return models


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        choices=("core", "inference", "full", "dev", "nemo"),
        default="inference",
    )
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument(
        "--whisper",
        default="base",
        help="Approved models only: tiny, tiny.en, base, base.en, small, small.en.",
    )
    parser.add_argument("--require-models", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        whisper_models = parse_whisper_models(args.whisper)
    except ValueError as exc:
        print(f"[MISSING] POLICY Whisper: {exc}", file=sys.stderr)
        return 2
    print(f"Python: {sys.version.split()[0]} ({sys.executable})")
    cache_root = args.cache_root.expanduser().resolve()
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

    if args.profile in {"inference", "full", "dev"}:
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
        checks.extend(
            whisper_cache_check(
                whisper_models,
                cache_root,
                required=args.require_models,
            )
        )
        checks.append(
            speechbrain_cache_check(
                cache_root,
                required=args.require_models,
            )
        )

    if args.profile == "full":
        checks.append(import_check("faster_whisper"))
        checks.append(import_check("pyannote.audio"))
        checks.append(import_check("sherpa_onnx"))
        checks.append(import_check("webrtcvad"))
        checks.append(import_check("resemblyzer"))
        checks.append(import_check("wespeaker"))
        checks.append(import_check("pvfalcon"))
        checks.append(import_check("vosk"))
        checks.append(wenet_import_check())
        checks.append(
            model_assets_check(
                "Faster-Whisper Tiny ASR model",
                cache_root / "faster_whisper" / "tiny",
                ("config.json", "model.bin", "tokenizer.json", "vocabulary.txt"),
                required=args.require_models,
            )
        )
        checks.append(
            model_assets_check(
                "Sherpa-ONNX ASR model",
                cache_root
                / "sherpa_onnx"
                / "asr"
                / "sherpa-onnx-streaming-zipformer-en-2023-06-26",
                (
                    "tokens.txt",
                    "encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                    "decoder-epoch-99-avg-1-chunk-16-left-128.onnx",
                    "joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx",
                ),
                required=args.require_models,
            )
        )
        checks.append(
            model_assets_check(
                "Vosk ASR model",
                cache_root / "vosk" / "asr" / "vosk-model-small-en-us-0.15",
                ("am/final.mdl", "conf/model.conf", "graph/HCLr.fst"),
                required=args.require_models,
            )
        )
        checks.append(
            model_assets_check(
                "WeNet ASR model",
                cache_root / "wenet" / "asr" / "librispeech_u2pp_conformer_exp",
                (
                    "final.pt",
                    "global_cmvn",
                    "train.yaml",
                    "train_960_unigram5000.model",
                    "units.txt",
                ),
                required=args.require_models,
            )
        )
        checks.append(
            model_asset_check(
                "Sherpa-ONNX VAD model",
                cache_root / "sherpa_onnx" / "vad" / "silero_vad.onnx",
                required=args.require_models,
            )
        )
        checks.append(
            model_asset_check(
                "Sherpa-ONNX speaker embedding model",
                cache_root
                / "sherpa_onnx"
                / "speaker_embedding"
                / "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx",
                required=args.require_models,
            )
        )
        checks.append(
            model_asset_check(
                "Sherpa-ONNX diarization segmentation model",
                cache_root
                / "sherpa_onnx"
                / "diarization"
                / "sherpa-onnx-pyannote-segmentation-3-0"
                / "model.onnx",
                required=args.require_models,
            )
        )
        checks.append(
            model_assets_check(
                "WeSpeaker English model",
                cache_root / "wespeaker" / "english",
                ("avg_model.pt", "config.yaml"),
                required=args.require_models,
            )
        )
        checks.append(pyannote_asset_check(cache_root, required=args.require_models))
        checks.append(
            environment_check("PYANNOTE_AUTH_TOKEN", backend="pyannote Community-1")
        )
        checks.append(
            environment_check("PICOVOICE_ACCESS_KEY", backend="Picovoice Falcon")
        )
        checks.append(
            platform_check(
                "NeMo diarization runtime",
                supported=platform.system() == "Linux",
                detail=(
                    "supported Linux platform"
                    if platform.system() == "Linux"
                    else (
                        "NeMo is isolated in requirements/nemo.txt and is "
                        "unsupported by the Windows full profile"
                    )
                ),
            )
        )
        checks.append(
            model_asset_check(
                "NeMo meeting diarization example configuration (not model weights)",
                cache_root / "nemo" / "diarization" / "config.yaml",
                required=False,
            )
        )
        checks.append(
            qualification_check(
                "Model-backed full-profile components",
                "not qualified here; package imports and model files are "
                "prerequisites, not inference tests",
            )
        )
    if args.profile == "dev":
        checks.extend(import_check(module) for module in ("pytest", "ruff", "mypy"))
    if args.profile == "nemo":
        linux = platform.system() == "Linux"
        checks.append(
            platform_check(
                "NeMo diarization runtime",
                supported=linux,
                detail=(
                    "supported Linux platform"
                    if linux
                    else f"unsupported operating system: {platform.system()}"
                ),
                required=True,
            )
        )
        if linux:
            checks.append(import_check("nemo.collections.asr"))
            checks.append(import_check("omegaconf"))
        else:
            checks.append(
                CheckResult(
                    "nemo.collections.asr",
                    "UNSUPPORTED",
                    "package import intentionally skipped on this platform",
                    False,
                    "PACKAGE",
                )
            )
        checks.append(
            model_asset_check(
                "NeMo meeting diarization example configuration (not model weights)",
                cache_root / "nemo" / "diarization" / "config.yaml",
                required=True,
            )
        )
        checks.append(
            qualification_check(
                "NeMo diarization inference",
                "not qualified here; a real Linux smoke is required, and MSDD "
                "additionally requires a config with a real msdd_model",
            )
        )
    checks.append(pipeline_config_check())

    for check in checks:
        print(f"[{check.status}] {check.category} {check.label}: {check.detail}")
    failures = [
        check
        for check in checks
        if check.required and check.status in {"MISSING", "UNSUPPORTED"}
    ]
    print(
        f"Readiness verification complete: {len(checks) - len(failures)}/"
        f"{len(checks)} checks non-failing; no model is marked qualified by "
        "this script."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
