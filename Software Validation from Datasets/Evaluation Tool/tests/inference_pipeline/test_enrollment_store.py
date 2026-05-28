from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.inference_pipeline.enrollment import (
    DuplicateSpeakerNameError,
    EnrollmentAudioNotFoundError,
    EnrollmentDatabase,
    add_enrollment_exemplar,
    add_speaker,
    load_enrollment_db,
    save_enrollment_db,
    validate_enrollment_database,
)
from app.inference_pipeline.errors import ContractValidationError


TOOL_ROOT = Path(__file__).resolve().parents[2]


def test_enrollment_db_save_load_multiple_speakers_and_centroids(tmp_path: Path) -> None:
    alice_1 = existing_audio(tmp_path / "alice_1.wav")
    alice_2 = existing_audio(tmp_path / "alice_2.wav")
    bob_1 = existing_audio(tmp_path / "bob_1.wav")
    db = EnrollmentDatabase.empty(created_at="2026-05-27T00:00:00Z")

    db, _ = add_enrollment_exemplar(
        db,
        display_name="Alice",
        prompt_id="clean_enrollment_v1",
        audio_path=alice_1,
        embedding=(1.0, 0.0),
        model_id="speaker-embedder@1",
        created_at="2026-05-27T00:00:01Z",
        duration_sec=1.25,
    )
    db, _ = add_enrollment_exemplar(
        db,
        display_name="Alice",
        prompt_id="clean_enrollment_v1",
        audio_path=alice_2,
        embedding=(0.0, 1.0),
        model_id="speaker-embedder@1",
        created_at="2026-05-27T00:00:02Z",
        duration_sec=1.75,
    )
    db, _ = add_enrollment_exemplar(
        db,
        display_name="Bob",
        prompt_id="clean_enrollment_v1",
        audio_path=bob_1,
        embedding=(0.0, -1.0),
        model_id="speaker-embedder@1",
        created_at="2026-05-27T00:00:03Z",
        duration_sec=2.0,
    )

    db_path = tmp_path / "enrollment_db.json"
    save_enrollment_db(db, db_path)
    loaded = load_enrollment_db(db_path)

    assert len(loaded.speakers) == 2
    assert loaded.exemplar_count == 3
    assert loaded.embedding_model_ids == ("speaker-embedder@1",)
    alice = loaded.speakers[0]
    assert alice.display_name == "Alice"
    assert len(alice.exemplars) == 2
    assert alice.duration_sec == pytest.approx(3.0)
    assert alice.centroid_embedding == pytest.approx((0.70710678, 0.70710678))
    assert loaded.to_jsonable()["speakers"][0]["centroid_embedding"] == pytest.approx(
        [0.70710678, 0.70710678]
    )


def test_duplicate_display_names_are_rejected() -> None:
    db = EnrollmentDatabase.empty(created_at="2026-05-27T00:00:00Z")
    db, _speaker = add_speaker(db, "Alice Smith")

    with pytest.raises(DuplicateSpeakerNameError):
        add_speaker(db, " alice   smith ")


def test_duplicate_display_names_are_rejected_when_loading() -> None:
    mapping = {
        "schema_version": "m10.enrollment_db.v1",
        "speakers": [
            {
                "speaker_id": "spk_1",
                "display_name": "Alice",
                "exemplars": [],
            },
            {
                "speaker_id": "spk_2",
                "display_name": " alice ",
                "exemplars": [],
            },
        ],
    }

    with pytest.raises(ContractValidationError):
        EnrollmentDatabase.from_mapping(mapping)


def test_missing_audio_file_is_rejected(tmp_path: Path) -> None:
    db = EnrollmentDatabase.empty(created_at="2026-05-27T00:00:00Z")

    with pytest.raises(EnrollmentAudioNotFoundError):
        add_enrollment_exemplar(
            db,
            display_name="Alice",
            prompt_id="clean_enrollment_v1",
            audio_path=tmp_path / "missing.wav",
            embedding=(1.0, 0.0),
            model_id="speaker-embedder@1",
            created_at="2026-05-27T00:00:01Z",
        )


def test_model_version_mismatch_emits_warning(tmp_path: Path) -> None:
    db = db_with_one_exemplar(tmp_path, model_id="speaker-embedder@1")

    with pytest.warns(UserWarning, match="model_id mismatch"):
        report = validate_enrollment_database(
            db,
            runtime_model_id="speaker-embedder@2",
            min_exemplars_per_speaker=1,
            emit_warnings=True,
        )

    assert report.ok is True
    assert report.warnings == (
        "model_id mismatch for Alice: stored 'speaker-embedder@1' != runtime 'speaker-embedder@2'",
    )


def test_completeness_checks_exemplar_count_and_duration(tmp_path: Path) -> None:
    db = db_with_one_exemplar(tmp_path, duration_sec=0.5)

    report = validate_enrollment_database(
        db,
        runtime_model_id="speaker-embedder@1",
        min_exemplars_per_speaker=2,
        min_duration_sec_per_speaker=1.0,
    )

    assert report.ok is False
    assert report.speaker_summaries[0].valid_embedding_count == 1
    assert report.speaker_summaries[0].duration_sec == pytest.approx(0.5)
    assert any("requires 2" in error for error in report.errors)
    assert any("requires 1.000s" in error for error in report.errors)


def test_enrollment_db_loads_in_separate_process(tmp_path: Path) -> None:
    db = db_with_one_exemplar(tmp_path)
    db_path = tmp_path / "enrollment_db.json"
    save_enrollment_db(db, db_path)
    script = (
        "import sys; "
        "from pathlib import Path; "
        "from app.inference_pipeline.enrollment import load_enrollment_db; "
        "db = load_enrollment_db(Path(sys.argv[1])); "
        "print(f'{len(db.speakers)}:{db.exemplar_count}:{db.embedding_model_ids[0]}')"
    )

    result = subprocess.run(
        [sys.executable, "-c", script, str(db_path)],
        cwd=TOOL_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "1:1:speaker-embedder@1"


def db_with_one_exemplar(
    tmp_path: Path,
    *,
    model_id: str = "speaker-embedder@1",
    duration_sec: float = 1.5,
) -> EnrollmentDatabase:
    db = EnrollmentDatabase.empty(created_at="2026-05-27T00:00:00Z")
    db, _ = add_enrollment_exemplar(
        db,
        display_name="Alice",
        prompt_id="clean_enrollment_v1",
        audio_path=existing_audio(tmp_path / "alice.wav"),
        embedding=(1.0, 0.0, 0.0),
        model_id=model_id,
        created_at="2026-05-27T00:00:01Z",
        duration_sec=duration_sec,
    )
    return db


def existing_audio(path: Path) -> Path:
    path.write_bytes(b"synthetic wav placeholder")
    return path
