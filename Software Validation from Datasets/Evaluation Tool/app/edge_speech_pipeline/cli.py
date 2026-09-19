"""Command-line entry points for GUI, live/file runs, enrollment, and export."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys
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
    gui = commands.add_parser("gui")
    for flag in ("research-profile", "research-gallery", "research-telemetry", "s6d-settings"):
        gui.add_argument("--" + flag, type=Path)
    commands.add_parser("validate")
    commands.add_parser("devices")
    live = commands.add_parser("live")
    live.add_argument("--device", type=int)
    wav = commands.add_parser("file")
    wav.add_argument("wav", type=Path)
    wav.add_argument("--accelerated", action="store_true")
    wav.add_argument("--research-profile", type=Path, help="Opt-in validated research JSON; GUI/default behavior is unchanged")
    wav.add_argument("--research-telemetry", type=Path, help="Sanitized source-clock telemetry JSONL for a cue-enabled profile")
    wav.add_argument("--identity-wav", type=Path, help="S6C v3 synchronized identity tap; positional WAV supplies ASR")
    wav.add_argument("--research-gallery", type=Path, help="S6C v3 explicit isolated gallery manifest")
    wav.add_argument("--s6d-settings", type=Path, help="Explicit S6D delivery/filter/direction JSON; default unchanged")
    captured=commands.add_parser('capture',help='Opt-in native analysis of an accepted same-pass S6D capture; no device access')
    captured.add_argument('admission',type=Path)
    for flag in ('beam-settings','research-profile','research-gallery','s6d-settings','asset-manifest','session-root'):
        captured.add_argument('--'+flag,type=Path,required=True)
    captured.add_argument('--check-only',action='store_true',help='Validate source/calibration/routes without models or session creation')
    captured.add_argument('--input-bindings',type=Path,required=True,help='Frozen per-job input receipt emitted by the beam planner')
    captured.add_argument('--input-bindings-sha256',required=True)
    enroll = commands.add_parser("enroll-wav")
    enroll.add_argument("name")
    enroll.add_argument("wavs", nargs="+", type=Path)
    enroll_mic = commands.add_parser("enroll-mic")
    enroll_mic.add_argument("name")
    enroll_mic.add_argument("--device", type=int)
    enroll_mic.add_argument("--seconds", type=float, default=6.0)
    commands.add_parser("profiles")
    research = commands.add_parser("research-profile", help="Validate and print an opt-in v1/v2 profile without loading models")
    research.add_argument("profile", type=Path)
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
    export_error = None
    try:
        engine.wait_for_completion()
    except (RuntimeError, TimeoutError) as exc:
        export_error = str(exc)
    while not engine.events.empty():
        print(json.dumps(engine.events.get().to_jsonable(), ensure_ascii=False), flush=True)
    if engine._s6d is not None:
        engine.record_s6d_consumer_closure("CLI")
    print(json.dumps(engine.telemetry(), indent=2))
    if export_error is not None:
        print(json.dumps({"session_export_error": export_error}), file=sys.stderr, flush=True)
        return 2
    return 0 if engine.state == "COMPLETED" else 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = PipelineConfig()
    if getattr(args, "s6d_settings", None):
        config = replace(config, s6d_settings_path=args.s6d_settings)
    if args.command == "research-profile":
        from .research_profiles import ResearchProfile
        profile = ResearchProfile.load(args.profile)
        print(json.dumps(profile.effective(profile.apply(config)), indent=2, default=str, allow_nan=False))
        return 0
    if args.command=='capture':
        from .config import AssetSpec
        from .research_profiles import ResearchProfile
        from .research_beams_s6d import BeamSettings,BeamPipelineEngine,CaptureAdmission,BeamSelector,verify_cli_inputs
        verify_cli_inputs({k:getattr(args,k) for k in ('admission','beam_settings','research_profile','research_gallery','s6d_settings','asset_manifest')},
            args.input_bindings,args.input_bindings_sha256)
        asset_rows=json.loads(args.asset_manifest.read_text(encoding='utf-8-sig'))
        assets=tuple(AssetSpec(r['component_id'],Path(r['path']),r['sha256'],r['deployment_relative_path']) for r in asset_rows)
        if len(assets)!=8 or {a.component_id for a in assets}!={a.component_id for a in config.assets}:
            raise ValueError('Explicit existing eight-asset recipe required')
        if {a.component_id:a.sha256 for a in assets}!={a.component_id:a.sha256 for a in config.assets}:
            raise ValueError('S6D capture reuses the fixed existing model weights only')
        config=replace(config,assets=assets,session_root=args.session_root,profile_root=args.session_root/'unused_private_profiles')
        engine=BeamPipelineEngine(config,research_profile=ResearchProfile.load(args.research_profile),
            research_gallery=args.research_gallery,beam_settings=BeamSettings.load(args.beam_settings))
        if args.check_only:
            capture=CaptureAdmission(args.admission,engine.beam_settings)
            selector=BeamSelector(engine.beam_settings,engine._research_gallery.receipt['manifest'],profile_digest=engine._research_profile.digest(),
                capture_profile=capture.capture_profile,capture_identity=(capture.data['capture_source_id'],capture.data['route_id']))
            print(json.dumps({'status':'INPUTS_VALIDATED_NO_MODELS','capture_admission':capture.binding,
                'source_streams':list(capture.names),'frames':capture.frames,'calibration_available':selector.calibration is not None,
                'native_tested':False,'physical_qualification_is_upstream_only':True},indent=2))
            return 0
        engine.start_capture(args.admission,realtime=True)
        return _print_events(engine)
    if args.command == "gui":
        from .gui import run_gui
        from .research_profiles import JsonSpatialProvider, ResearchProfile
        profile = ResearchProfile.load(args.research_profile) if args.research_profile else None
        provider = JsonSpatialProvider(args.research_telemetry) if args.research_telemetry else None
        engine = PipelineEngine(config, research_profile=profile, spatial_provider=provider, research_gallery=args.research_gallery)
        run_gui(config, engine=engine)
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
    research_profile = None
    spatial_provider = None
    if args.command == "file" and args.research_profile is not None:
        from .research_profiles import JsonSpatialProvider, ResearchProfile
        research_profile = ResearchProfile.load(args.research_profile)
        # Explicit research file runs require a prepared mono 16-kHz input. This
        # prevents the ordinary convenience downmix from silently selecting a tap.
        import soundfile as sf
        info = sf.info(args.wav)
        if info.channels != 1 or info.samplerate != 16000:
            raise ValueError("research file input must be prepared mono 16-kHz audio")
        if args.research_telemetry is not None:
            spatial_provider = JsonSpatialProvider(args.research_telemetry)
    elif args.command == "file" and args.research_telemetry is not None:
        raise ValueError("--research-telemetry requires --research-profile")
    if args.command == "file" and (args.identity_wav is not None or args.research_gallery is not None):
        if getattr(research_profile, "schema_version", None) != "edge-research-profile.v3":
            raise ValueError("paired identity audio/research gallery require an explicit S6C v3 profile")
    engine = PipelineEngine(config, research_profile=research_profile, spatial_provider=spatial_provider,
        research_gallery=args.research_gallery if args.command == "file" else None)
    if args.command == "live":
        engine.start_live(args.device)
    else:
        if args.identity_wav is not None:
            engine.start_paired_files(args.wav, args.identity_wav, realtime=not args.accelerated)
        else:
            engine.start_file(args.wav, realtime=not args.accelerated)
    return _print_events(engine)
