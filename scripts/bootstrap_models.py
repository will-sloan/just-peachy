"""Download optional inference model assets into the project cache."""

from __future__ import annotations

import argparse
import gc
import os
import sys
from pathlib import Path
from typing import Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "models" / "cache"


def download_whisper(models: list[str], cache_root: Path) -> None:
    import whisper

    destination = cache_root / "whisper"
    destination.mkdir(parents=True, exist_ok=True)
    available = set(whisper.available_models())
    for model_name in models:
        if model_name not in available:
            known = ", ".join(sorted(available))
            raise ValueError(f"unknown Whisper model {model_name!r}; available: {known}")
        print(f"Downloading Whisper {model_name} to {destination}")
        model_urls = getattr(whisper, "_MODELS", {})
        downloader: Callable[..., object] | None = getattr(whisper, "_download", None)
        if model_name in model_urls and callable(downloader):
            downloader(model_urls[model_name], str(destination), False)
        else:
            model = whisper.load_model(model_name, device="cpu", download_root=str(destination))
            del model
            gc.collect()


def download_speechbrain(cache_root: Path, device: str) -> None:
    try:
        from speechbrain.inference.speaker import EncoderClassifier
    except Exception:
        from speechbrain.pretrained import EncoderClassifier
    from speechbrain.utils.fetching import LocalStrategy

    destination = cache_root / "speechbrain" / "spkrec-ecapa-voxceleb"
    destination.mkdir(parents=True, exist_ok=True)
    print(f"Downloading SpeechBrain ECAPA to {destination}")
    model = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(destination),
        run_opts={"device": device},
        local_strategy=LocalStrategy.COPY,
    )
    del model
    gc.collect()


def download_silero() -> None:
    from silero_vad import load_silero_vad

    print("Loading packaged Silero VAD assets")
    model = load_silero_vad()
    del model
    gc.collect()


def download_pyannote(cache_root: Path, token_env: str) -> None:
    from pyannote.audio import Pipeline

    token = os.environ.get(token_env)
    if not token:
        raise RuntimeError(
            f"{token_env} is not set; pyannote community model access requires a Hugging Face token"
        )
    destination = cache_root / "pyannote"
    destination.mkdir(parents=True, exist_ok=True)
    source = "pyannote/speaker-diarization-community-1"
    print(f"Downloading {source} to {destination}")
    try:
        pipeline = Pipeline.from_pretrained(
            source,
            token=token,
            cache_dir=str(destination),
        )
    except TypeError:
        pipeline = Pipeline.from_pretrained(
            source,
            use_auth_token=token,
            cache_dir=str(destination),
        )
    del pipeline
    gc.collect()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cache-root",
        type=Path,
        default=DEFAULT_CACHE_ROOT,
        help="Shared model cache root.",
    )
    parser.add_argument(
        "--whisper",
        default="",
        help="Comma-separated OpenAI Whisper model names.",
    )
    parser.add_argument("--speechbrain-ecapa", action="store_true")
    parser.add_argument("--silero", action="store_true")
    parser.add_argument("--pyannote", action="store_true")
    parser.add_argument("--hf-token-env", default="HF_TOKEN")
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda"),
        default="cpu",
        help="Device used while initializing models that must be loaded after download.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cache_root = args.cache_root.expanduser().resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    tasks: list[tuple[str, Callable[[], None]]] = []
    whisper_models = [item.strip() for item in args.whisper.split(",") if item.strip()]
    if whisper_models:
        tasks.append(("Whisper", lambda: download_whisper(whisper_models, cache_root)))
    if args.speechbrain_ecapa:
        tasks.append(
            ("SpeechBrain ECAPA", lambda: download_speechbrain(cache_root, args.device))
        )
    if args.silero:
        tasks.append(("Silero VAD", download_silero))
    if args.pyannote:
        tasks.append(("pyannote", lambda: download_pyannote(cache_root, args.hf_token_env)))
    if not tasks:
        print("No models selected. Use --whisper, --speechbrain-ecapa, --silero, or --pyannote.")
        return 0

    failures: list[str] = []
    for label, task in tasks:
        try:
            task()
            print(f"[PASS] {label}")
        except Exception as exc:
            failures.append(f"{label}: {exc}")
            print(f"[FAIL] {label}: {exc}", file=sys.stderr)
    if failures:
        print("Model bootstrap completed with failures:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Model bootstrap complete: {cache_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
