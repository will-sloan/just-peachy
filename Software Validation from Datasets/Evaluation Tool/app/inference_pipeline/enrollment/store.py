"""Load, save, validate, and report on speaker enrollment databases."""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Mapping, Sequence

from app.inference_pipeline.enrollment.schema import (
    ENROLLMENT_SCHEMA_VERSION,
    EnrollmentDatabase,
    EnrollmentExemplar,
    EnrollmentSpeaker,
)
from app.inference_pipeline.errors import ContractValidationError, InferencePipelineError
from app.inference_pipeline.typing import JsonObject
from app.utils.json_utils import read_json, write_json


TOOL_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENROLLMENT_DB_PATH = TOOL_ROOT / "artifacts" / "enrollment" / "enrollment_db.json"


class EnrollmentStoreError(InferencePipelineError):
    """Base error for enrollment store operations."""


class DuplicateSpeakerNameError(EnrollmentStoreError, ValueError):
    """Raised when two speakers use the same normalized display name."""


class EnrollmentAudioNotFoundError(EnrollmentStoreError, FileNotFoundError):
    """Raised when an enrollment audio file does not exist."""


@dataclass(frozen=True)
class SpeakerEnrollmentSummary:
    """Completeness summary for one enrolled speaker."""

    speaker_id: str
    display_name: str
    exemplar_count: int
    valid_embedding_count: int
    duration_sec: float
    model_ids: tuple[str, ...]
    complete: bool

    def to_jsonable(self) -> JsonObject:
        return {
            "speaker_id": self.speaker_id,
            "display_name": self.display_name,
            "exemplar_count": self.exemplar_count,
            "valid_embedding_count": self.valid_embedding_count,
            "duration_sec": self.duration_sec,
            "model_ids": list(self.model_ids),
            "complete": self.complete,
        }


@dataclass(frozen=True)
class EnrollmentValidationReport:
    """Validation result for completeness, duration, and model consistency."""

    runtime_model_id: str | None
    min_exemplars_per_speaker: int
    min_duration_sec_per_speaker: float
    speaker_summaries: tuple[SpeakerEnrollmentSummary, ...]
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_jsonable(self) -> JsonObject:
        return {
            "runtime_model_id": self.runtime_model_id,
            "min_exemplars_per_speaker": self.min_exemplars_per_speaker,
            "min_duration_sec_per_speaker": self.min_duration_sec_per_speaker,
            "speaker_summaries": [
                summary.to_jsonable()
                for summary in self.speaker_summaries
            ],
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "ok": self.ok,
        }


def load_enrollment_db(path: Path | str = DEFAULT_ENROLLMENT_DB_PATH) -> EnrollmentDatabase:
    """Load an enrollment DB, returning an empty DB when no file exists yet."""

    db_path = Path(path)
    if not db_path.exists():
        return EnrollmentDatabase.empty(
            created_at=_utc_now(),
            notes="Empty M10 enrollment database.",
        )
    data = read_json(db_path)
    if not isinstance(data, Mapping):
        raise ContractValidationError("enrollment DB root must be a JSON object")
    return EnrollmentDatabase.from_mapping(data)


def save_enrollment_db(
    db: EnrollmentDatabase,
    path: Path | str = DEFAULT_ENROLLMENT_DB_PATH,
) -> Path:
    """Save an enrollment DB as deterministic, human-inspectable JSON."""

    db_path = Path(path)
    write_json(db_path, db.to_jsonable())
    return db_path


def add_speaker(
    db: EnrollmentDatabase,
    display_name: str,
    *,
    speaker_id: str | None = None,
    notes: str | None = None,
) -> tuple[EnrollmentDatabase, EnrollmentSpeaker]:
    """Add a new speaker without exemplars."""

    _ensure_unique_display_name(db, display_name)
    resolved_speaker_id = speaker_id or stable_speaker_id(display_name)
    if any(speaker.speaker_id == resolved_speaker_id for speaker in db.speakers):
        raise DuplicateSpeakerNameError(f"speaker_id already exists: {resolved_speaker_id}")
    speaker = EnrollmentSpeaker(
        speaker_id=resolved_speaker_id,
        display_name=display_name,
        exemplars=(),
        notes=notes,
    )
    updated = _with_speakers(db, (*db.speakers, speaker))
    return updated, speaker


def find_speaker_by_display_name(
    db: EnrollmentDatabase,
    display_name: str,
) -> EnrollmentSpeaker | None:
    """Return the existing speaker with the same normalized display name."""

    target = normalized_display_name(display_name)
    for speaker in db.speakers:
        if normalized_display_name(speaker.display_name) == target:
            return speaker
    return None


def add_enrollment_exemplar(
    db: EnrollmentDatabase,
    *,
    display_name: str,
    prompt_id: str,
    audio_path: Path | str,
    embedding: Sequence[float],
    model_id: str,
    created_at: str | None = None,
    notes: str | None = None,
    speaker_notes: str | None = None,
    duration_sec: float | None = None,
    metadata: Mapping[str, object] | None = None,
    validate_audio_path: bool = True,
    tool_root: Path = TOOL_ROOT,
) -> tuple[EnrollmentDatabase, EnrollmentExemplar]:
    """Create and append one exemplar, reusing an existing speaker by name."""

    speaker = find_speaker_by_display_name(db, display_name)
    working_db = db
    if speaker is None:
        working_db, speaker = add_speaker(
            working_db,
            display_name,
            notes=speaker_notes,
        )
    exemplar = create_enrollment_exemplar(
        speaker_id=speaker.speaker_id,
        display_name=speaker.display_name,
        prompt_id=prompt_id,
        audio_path=audio_path,
        embedding=embedding,
        model_id=model_id,
        created_at=created_at,
        notes=notes,
        duration_sec=duration_sec,
        metadata=metadata,
        validate_audio_path=validate_audio_path,
        tool_root=tool_root,
    )
    updated_speaker = EnrollmentSpeaker(
        speaker_id=speaker.speaker_id,
        display_name=speaker.display_name,
        exemplars=(*speaker.exemplars, exemplar),
        notes=speaker.notes,
    )
    updated_speakers = tuple(
        updated_speaker if item.speaker_id == speaker.speaker_id else item
        for item in working_db.speakers
    )
    return _with_speakers(working_db, updated_speakers), exemplar


def create_enrollment_exemplar(
    *,
    speaker_id: str,
    display_name: str,
    prompt_id: str,
    audio_path: Path | str,
    embedding: Sequence[float],
    model_id: str,
    created_at: str | None = None,
    notes: str | None = None,
    duration_sec: float | None = None,
    metadata: Mapping[str, object] | None = None,
    validate_audio_path: bool = True,
    tool_root: Path = TOOL_ROOT,
) -> EnrollmentExemplar:
    """Build a validated exemplar from an existing WAV and embedding vector."""

    source_path = Path(audio_path).expanduser()
    if validate_audio_path and not source_path.is_file():
        raise EnrollmentAudioNotFoundError(f"enrollment audio file does not exist: {source_path}")
    stored_path = portable_audio_path(source_path, tool_root=tool_root)
    vector = tuple(float(value) for value in embedding)
    resolved_created_at = created_at or _utc_now()
    return EnrollmentExemplar(
        speaker_id=speaker_id,
        display_name=display_name,
        prompt_id=prompt_id,
        audio_path=stored_path,
        embedding=vector,
        model_id=model_id,
        created_at=resolved_created_at,
        notes=notes,
        duration_sec=duration_sec,
        embedding_id=stable_embedding_id(
            speaker_id=speaker_id,
            prompt_id=prompt_id,
            audio_path=stored_path,
            model_id=model_id,
            embedding=vector,
        ),
        metadata=dict(metadata or {}),
    )


def validate_enrollment_database(
    db: EnrollmentDatabase,
    *,
    runtime_model_id: str | None = None,
    min_exemplars_per_speaker: int = 1,
    min_duration_sec_per_speaker: float = 0.0,
    emit_warnings: bool = False,
) -> EnrollmentValidationReport:
    """Check completeness, duration coverage, and model-version consistency."""

    if min_exemplars_per_speaker < 1:
        raise ContractValidationError("min_exemplars_per_speaker must be >= 1")
    if min_duration_sec_per_speaker < 0:
        raise ContractValidationError("min_duration_sec_per_speaker must be >= 0")

    errors: list[str] = []
    warning_messages: list[str] = []
    summaries: list[SpeakerEnrollmentSummary] = []
    if not db.speakers:
        errors.append("enrollment DB has no speakers")

    for speaker in db.speakers:
        valid_embeddings = [exemplar for exemplar in speaker.exemplars if exemplar.embedding]
        duration_sec = speaker.duration_sec
        model_ids = speaker.model_ids
        complete = (
            len(valid_embeddings) >= min_exemplars_per_speaker
            and duration_sec >= min_duration_sec_per_speaker
        )
        summaries.append(
            SpeakerEnrollmentSummary(
                speaker_id=speaker.speaker_id,
                display_name=speaker.display_name,
                exemplar_count=len(speaker.exemplars),
                valid_embedding_count=len(valid_embeddings),
                duration_sec=duration_sec,
                model_ids=model_ids,
                complete=complete,
            )
        )
        if len(valid_embeddings) < min_exemplars_per_speaker:
            errors.append(
                f"{speaker.display_name} has {len(valid_embeddings)} valid embedding(s), "
                f"requires {min_exemplars_per_speaker}"
            )
        if duration_sec < min_duration_sec_per_speaker:
            errors.append(
                f"{speaker.display_name} has {duration_sec:.3f}s enrollment duration, "
                f"requires {min_duration_sec_per_speaker:.3f}s"
            )
        if len(model_ids) > 1:
            warning_messages.append(
                f"{speaker.display_name} has mixed enrollment model_ids: {', '.join(model_ids)}"
            )
        if runtime_model_id is not None:
            mismatches = sorted(model_id for model_id in model_ids if model_id != runtime_model_id)
            for model_id in mismatches:
                warning_messages.append(
                    f"model_id mismatch for {speaker.display_name}: "
                    f"stored {model_id!r} != runtime {runtime_model_id!r}"
                )

    unique_warnings = tuple(dict.fromkeys(warning_messages))
    if emit_warnings:
        for message in unique_warnings:
            warnings.warn(message, UserWarning, stacklevel=2)
    return EnrollmentValidationReport(
        runtime_model_id=runtime_model_id,
        min_exemplars_per_speaker=min_exemplars_per_speaker,
        min_duration_sec_per_speaker=float(min_duration_sec_per_speaker),
        speaker_summaries=tuple(summaries),
        warnings=unique_warnings,
        errors=tuple(errors),
    )


def stable_speaker_id(display_name: str) -> str:
    """Return a deterministic speaker id from the normalized display name."""

    key = normalized_display_name(display_name)
    if not key:
        raise ContractValidationError("display_name must be a non-empty string")
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]
    return f"spk_{digest}"


def stable_embedding_id(
    *,
    speaker_id: str,
    prompt_id: str,
    audio_path: str,
    model_id: str,
    embedding: Sequence[float],
) -> str:
    payload = "|".join(
        [
            speaker_id,
            prompt_id,
            audio_path,
            model_id,
            ",".join(f"{float(value):.9g}" for value in embedding),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"emb_{digest}"


def normalized_display_name(display_name: str) -> str:
    return " ".join(str(display_name).casefold().split())


def portable_audio_path(audio_path: Path, *, tool_root: Path = TOOL_ROOT) -> str:
    """Store paths relative to the Evaluation Tool when possible."""

    path = audio_path.expanduser()
    try:
        resolved_path = path.resolve(strict=False)
        resolved_root = tool_root.resolve(strict=False)
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return path.as_posix()


def enrollment_report_path(reports_root: Path, run_id: str) -> Path:
    """Return the M10 enrollment component report path for a run id."""

    return (
        reports_root
        / "component_reports"
        / "enrollment"
        / f"enrollment_db_report_{run_id}.md"
    )


def write_enrollment_db_report(
    path: Path,
    *,
    run_id: str,
    db: EnrollmentDatabase,
    validation_report: EnrollmentValidationReport,
    files_changed: Sequence[str],
    test_commands: Sequence[str],
    smoke_commands: Sequence[str],
    runner_contract: str,
    blockers: Sequence[str] = (),
    incomplete: Sequence[str] = (),
) -> Path:
    """Write the required M10 enrollment component report."""

    lines = [
        "# Enrollment DB Component Report",
        "",
        "## Milestone",
        "",
        "M10 - Enrollment Store and Enrollment CLI",
        "",
        f"- Run id: `{run_id}`",
        f"- Schema version: `{db.schema_version}`",
        f"- Speakers: `{len(db.speakers)}`",
        f"- Exemplars: `{db.exemplar_count}`",
        f"- Model ids: `{', '.join(db.embedding_model_ids) or 'none'}`",
        "",
        "## Files Changed",
        "",
        *[f"- `{file_path}`" for file_path in files_changed],
        "",
        "## Summary",
        "",
        "M10 adds a versioned enrollment database, store helpers, validation checks,",
        "and a standalone CLI for enrolling one speaker from existing WAV files.",
        "The store keeps per-exemplar vectors for future exemplar-by-exemplar matching",
        "and computes per-speaker centroid embeddings for future centroid matching.",
        "",
        "## Schema",
        "",
        "Each exemplar records `speaker_id`, `display_name`, `prompt_id`, `audio_path`,",
        "`embedding`, `model_id`, `created_at`, and `notes`; the DB also records",
        "schema version and top-level model-id metadata.",
        "",
        "## CLI",
        "",
        "`scripts/enroll_speaker.py` enrolls from existing WAV files. The default",
        "`speechbrain` backend uses the existing lazy SpeechBrain ECAPA adapter and",
        "fails clearly when dependencies or local model assets are unavailable. The",
        "`fake` backend is explicit smoke/test plumbing only.",
        "",
        "## Runner Contract Preservation",
        "",
        runner_contract,
        "",
        "## Commands",
        "",
        *[f"- `{command}`" for command in test_commands],
        *[f"- `{command}`" for command in smoke_commands],
        "",
        "## Validation",
        "",
        f"- Validation ok: `{validation_report.ok}`",
        f"- Minimum exemplars per speaker: `{validation_report.min_exemplars_per_speaker}`",
        (
            "- Minimum duration coverage per speaker: "
            f"`{validation_report.min_duration_sec_per_speaker:.3f}s`"
        ),
    ]
    if validation_report.speaker_summaries:
        lines.extend(
            [
                "",
                "## Speaker Summaries",
                "",
                *[
                    (
                        f"- `{summary.display_name}`: exemplars={summary.exemplar_count}, "
                        f"valid={summary.valid_embedding_count}, "
                        f"duration_sec={summary.duration_sec:.3f}, "
                        f"model_ids={list(summary.model_ids)}, complete={summary.complete}"
                    )
                    for summary in validation_report.speaker_summaries
                ],
            ]
        )
    lines.extend(["", "## Warnings", ""])
    if validation_report.warnings:
        lines.extend(f"- {message}" for message in validation_report.warnings)
    else:
        lines.append("- None.")
    lines.extend(["", "## Errors", ""])
    if validation_report.errors:
        lines.extend(f"- {message}" for message in validation_report.errors)
    else:
        lines.append("- None.")
    lines.extend(["", "## Blockers", ""])
    if blockers:
        lines.extend(f"- {blocker}" for blocker in blockers)
    else:
        lines.append("- None known.")
    lines.extend(["", "## Incomplete", ""])
    if incomplete:
        lines.extend(f"- {item}" for item in incomplete)
    else:
        lines.append("- None known.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _ensure_unique_display_name(db: EnrollmentDatabase, display_name: str) -> None:
    if find_speaker_by_display_name(db, display_name) is not None:
        raise DuplicateSpeakerNameError(f"display_name already exists: {display_name}")


def _with_speakers(
    db: EnrollmentDatabase,
    speakers: Sequence[EnrollmentSpeaker],
) -> EnrollmentDatabase:
    now = _utc_now()
    return EnrollmentDatabase(
        schema_version=ENROLLMENT_SCHEMA_VERSION,
        speakers=tuple(speakers),
        created_at=db.created_at or now,
        updated_at=now,
        notes=db.notes,
    )


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
