"""Command-line entry points for GUI, live/file runs, enrollment, and export."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from .assets import export_pi_bundle, validate_assets
from .audio import input_devices
from .config import PipelineConfig
from .enrollment import enroll_wavs, record_microphone_wav
from .models import SpeakerModels
from .runtime import PipelineEngine
from .speakers import ProfileStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean Sherpa Giga + H2 edge speech pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("gui")
    commands.add_parser("validate")
    commands.add_parser("devices")
    live = commands.add_parser("live")
    live.add_argument("--device", type=int)
    wav = commands.add_parser("file")
    wav.add_argument("wav", type=Path)
    wav.add_argument("--accelerated", action="store_true")
    enroll = commands.add_parser("enroll-wav")
    enroll.add_argument("name")
    enroll.add_argument("wavs", nargs="+", type=Path)
    enroll_mic = commands.add_parser("enroll-mic")
    enroll_mic.add_argument("name")
    enroll_mic.add_argument("--device", type=int)
    enroll_mic.add_argument("--seconds", type=float, default=6.0)
    commands.add_parser("profiles")
    export = commands.add_parser("export-pi")
    export.add_argument("output", type=Path)
    return parser


def _print_events(engine: PipelineEngine) -> int:
    try:
        while engine.state not in {"COMPLETED", "FAILED"}:
            while not engine.events.empty():
                print(json.dumps(engine.events.get().to_jsonable(), ensure_ascii=False), flush=True)
            time.sleep(0.05)
    except KeyboardInterrupt:
        engine.stop()
    while not engine.events.empty():
        print(json.dumps(engine.events.get().to_jsonable(), ensure_ascii=False), flush=True)
    print(json.dumps(engine.telemetry(), indent=2))
    return 0 if engine.state == "COMPLETED" else 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = PipelineConfig()
    if args.command == "gui":
        from .gui import run_gui

        run_gui(config)
        return 0
    if args.command == "validate":
        print(json.dumps(validate_assets(config.assets), indent=2))
        return 0
    if args.command == "devices":
        print(json.dumps(input_devices(), indent=2))
        return 0
    if args.command == "profiles":
        print(json.dumps(ProfileStore(config.profile_root).list_metadata(), indent=2))
        return 0
    if args.command == "export-pi":
        print(json.dumps(export_pi_bundle(config, args.output), indent=2))
        return 0
    if args.command == "enroll-wav":
        print(json.dumps(enroll_wavs(args.name, args.wavs, models=SpeakerModels(config), config=config), indent=2))
        return 0
    if args.command == "enroll-mic":
        temp = config.profile_root / "recordings" / f"{args.name}_latest.wav"
        record_microphone_wav(temp, device=args.device, duration_sec=args.seconds)
        print(json.dumps(enroll_wavs(args.name, [temp], models=SpeakerModels(config), config=config), indent=2))
        return 0
    engine = PipelineEngine(config)
    if args.command == "live":
        engine.start_live(args.device)
    else:
        engine.start_file(args.wav, realtime=not args.accelerated)
    return _print_events(engine)

