"""Enroll one speaker from existing WAV files into the enrollment DB."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Sequence

import soundfile as sf


TOOL_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = TOOL_ROOT.parent
REPO_ROOT = PROJECT_ROOT.parent
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.inference_pipeline.contracts import AudioSegment
from app.inference_pipeline.enrollment import (
    DEFAULT_ENROLLMENT_DB_PATH,
    DEFAULT_PROMPT_ID,
    add_enrollment_exemplar,
    enrollment_report_path,
    load_enrollment_db,
    save_enrollment_db,
    validate_enrollment_database,
    write_enrollment_db_report,
)
from app.inference_pipeline.errors import InferencePipelineError
from app.inference_pipeline.speaker_embedding import (
    DEFAULT_MIN_DURATION_SEC,
    DeterministicFakeSpeakerEmbedding,
    SpeakerEmbeddingBase,
    SpeakerEmbeddingContext,
)
from app.inference_pipeline.speaker_embedding.speechbrain_adapter import (
    SpeechBrainECAPAAdapter,
    SpeechBrainUnavailableError,
)


AUDIO_SUFFIXES = {".wav"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return enroll_speaker(args)
    except (FileNotFoundError, InferencePipelineError, ValueError) as exc:
        print(f"Enrollment failed: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Enroll one speaker from existing WAV files.",
    )
    parser.add_argument(
        "--display-name",
        required=True,
        help="Human-readable speaker name to create or append to.",
    )
    parser.add_argument(
        "--audio",
        type=Path,
        nargs="+",
        required=True,
        help="One or more existing WAV files for this speaker.",
    )
    parser.add_argument(
        "--model-id",
        required=True,
        help="Embedding model/version id to persist with every exemplar.",
    )
    parser.add_argument(
        "--prompt-id",
        default=DEFAULT_PROMPT_ID,
        help="Enrollment prompt id associated with these files.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_ENROLLMENT_DB_PATH,
        help="Enrollment DB JSON path.",
    )
    parser.add_argument("--notes", default=None, help="Per-exemplar notes.")
    parser.add_argument("--speaker-notes", default=None, help="Speaker-level notes for new speakers.")
    parser.add_argument("--run-id", default=None, help="Run id for the component report.")
    parser.add_argument("--report", type=Path, default=None, help="Optional report output path.")
    parser.add_argument(
        "--backend",
        choices=["speechbrain", "fake"],
        default="speechbrain",
        help="Embedding backend. Use fake only for isolated smoke checks.",
    )
    parser.add_argument("--device", default="cpu", help="Torch device for embedding.")
    parser.add_argument("--dimension", type=int, default=16, help="Fake backend dimension.")
    parser.add_argument(
        "--min-duration-sec",
        type=float,
        default=DEFAULT_MIN_DURATION_SEC,
        help="Minimum usable enrollment sample duration.",
    )
    parser.add_argument(
        "--allow-model-downloads",
        action="store_true",
        help="Allow SpeechBrain to download model assets.",
    )
    parser.add_argument(
        "--model-source",
        default="speechbrain/spkrec-ecapa-voxceleb",
        help="SpeechBrain source name or local model directory.",
    )
    parser.add_argument(
        "--savedir",
        type=Path,
        default=Path("models/cache/speechbrain/spkrec-ecapa-voxceleb"),
        help="SpeechBrain local asset/cache directory.",
    )
    return parser


def enroll_speaker(args: argparse.Namespace) -> int:
    audio_paths = validate_audio_paths(args.audio)
    adapter = build_adapter(args)
    run_id = args.run_id or time.strftime("m10_enrollment_%Y%m%d_%H%M%S")
    report_path = args.report or enrollment_report_path(TOOL_ROOT / "reports", run_id)
    db = load_enrollment_db(args.db)

    for index, audio_path in enumerate(audio_paths):
        info = sf.info(audio_path)
        duration_sec = int(info.frames) / int(info.samplerate)
        segment = AudioSegment(
            audio_path=audio_path,
            sample_rate_hz=int(info.samplerate),
            channel_count=int(info.channels),
            duration_sec=duration_sec,
        )
        context = SpeakerEmbeddingContext(
            recording_id=audio_path.stem,
            utt_id=audio_path.stem,
            source_audio_path=audio_path,
            segment_index=index,
            device=args.device,
            run_config={"run_id": run_id, "enrollment": True},
        )
        try:
            embedding = adapter.embed(segment, context)
        except SpeechBrainUnavailableError:
            raise
        except Exception as exc:
            raise InferencePipelineError(f"embedding failed for {audio_path}: {exc}") from exc
        if embedding.status != "ok" or not embedding.vector:
            raise InferencePipelineError(
                f"embedding for {audio_path} is not enrollable: status={embedding.status!r}"
            )
        db, _exemplar = add_enrollment_exemplar(
            db,
            display_name=args.display_name,
            prompt_id=args.prompt_id,
            audio_path=audio_path,
            embedding=embedding.vector,
            model_id=args.model_id,
            notes=args.notes,
            speaker_notes=args.speaker_notes,
            duration_sec=embedding.segment_duration_sec or duration_sec,
            metadata={
                "backend": args.backend,
                "embedding_id": embedding.embedding_id,
                "sample_rate_hz": embedding.sample_rate_hz,
                "source_model_name": embedding.model_name,
            },
        )

    save_enrollment_db(db, args.db)
    validation_report = validate_enrollment_database(
        db,
        runtime_model_id=args.model_id,
        min_exemplars_per_speaker=1,
        min_duration_sec_per_speaker=args.min_duration_sec,
        emit_warnings=True,
    )
    write_enrollment_db_report(
        report_path,
        run_id=run_id,
        db=db,
        validation_report=validation_report,
        files_changed=[
            "app/inference_pipeline/enrollment/__init__.py",
            "app/inference_pipeline/enrollment/store.py",
            "app/inference_pipeline/enrollment/schema.py",
            "app/inference_pipeline/enrollment/prompts.py",
            "scripts/enroll_speaker.py",
        ],
        test_commands=[],
        smoke_commands=[command_summary(args)],
        runner_contract=(
            "Enrollment is a standalone artifact workflow. It does not change "
            "app/model_runner/external_stub.py, record['inference_audio_path'], "
            "predictions/utterances.jsonl, or scoring identity fields."
        ),
        blockers=blockers_summary(args.backend),
        incomplete=incomplete_summary(args.backend),
    )
    print(f"Enrollment DB: {args.db}")
    print(f"Report: {report_path}")
    return 0 if validation_report.ok else 1


def validate_audio_paths(paths: Sequence[Path]) -> list[Path]:
    resolved: list[Path] = []
    for path in paths:
        candidate = path.expanduser()
        if candidate.suffix.lower() not in AUDIO_SUFFIXES:
            raise ValueError(f"enrollment audio must be WAV: {candidate}")
        if not candidate.is_file():
            raise FileNotFoundError(f"enrollment audio file does not exist: {candidate}")
        resolved.append(candidate)
    return resolved


def build_adapter(args: argparse.Namespace) -> SpeakerEmbeddingBase:
    if args.backend == "fake":
        return DeterministicFakeSpeakerEmbedding(
            dimension=args.dimension,
            min_duration_sec=args.min_duration_sec,
            device=args.device,
        )
    savedir = args.savedir
    if not savedir.is_absolute():
        savedir = TOOL_ROOT / savedir
    return SpeechBrainECAPAAdapter(
        {
            "model_source": args.model_source,
            "savedir": str(savedir),
            "sample_rate_hz": 16000,
            "embedding_dim": 192,
            "min_duration_sec": args.min_duration_sec,
            "device": args.device,
            "allow_model_downloads": args.allow_model_downloads,
        }
    )


def blockers_summary(backend: str) -> list[str]:
    if backend == "speechbrain":
        return []
    return [
        "The fake backend is deterministic smoke-test plumbing only; it is not a production enrollment model."
    ]


def incomplete_summary(backend: str) -> list[str]:
    items = ["Live microphone enrollment is intentionally deferred beyond M10."]
    if backend != "speechbrain":
        items.append("Real speaker embedding quality was not validated by the fake backend.")
    return items


def command_summary(args: argparse.Namespace) -> str:
    parts = [
        "python",
        "scripts/enroll_speaker.py",
        "--display-name",
        repr(args.display_name),
        "--model-id",
        args.model_id,
        "--backend",
        args.backend,
        "--audio",
        *[str(path) for path in args.audio],
        "--db",
        str(args.db),
    ]
    if args.run_id is not None:
        parts.extend(["--run-id", args.run_id])
    if args.report is not None:
        parts.extend(["--report", str(args.report)])
    if args.prompt_id != DEFAULT_PROMPT_ID:
        parts.extend(["--prompt-id", args.prompt_id])
    return " ".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())
