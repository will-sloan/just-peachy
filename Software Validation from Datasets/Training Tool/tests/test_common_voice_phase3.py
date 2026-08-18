"""Bounded synthetic-archive tests for selective Common Voice Phase 3."""
from __future__ import annotations

import hashlib
import io
import sys
import tarfile
from pathlib import Path

import pandas as pd
import pytest
import soundfile as sf


TRAINING_TOOL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TRAINING_TOOL))

from training_data.common_voice_phase3 import (  # noqa: E402
    Phase3Error,
    Phase3Paths,
    _accent_inventory,
    _accent_tokens,
    _apply_common_voice_eligibility,
    _evaluation_content_hash_index,
    _validate_audio_file,
    build_metadata_state,
    detect_archive_format,
    deterministic_speaker_split,
    discover_archive,
    materialize_selected_audio,
    safe_member_name,
    source_audit,
)


PREFIX = "fixture-release/en"


def _tsv(columns: list[str], rows: list[list[object]]) -> bytes:
    lines = ["\t".join(columns)] + ["\t".join(str(value) for value in row) for row in rows]
    return ("\n".join(lines) + "\n").encode()


def _metadata() -> dict[str, bytes]:
    columns = [
        "client_id", "path", "sentence_id", "sentence", "sentence_domain",
        "up_votes", "down_votes", "age", "gender", "accents", "variant", "locale",
    ]
    validated = [
        ["older-a", "a.mp3", "s1", "One sentence", "general", 2, 0, "sixties", "", "us|canada", "", "en"],
        ["older-b", "b.mp3", "s2", "Another sentence", "general", 2, 0, "seventies", "", "", "", "en"],
        ["young", "young.mp3", "s3", "Young sentence", "general", 2, 0, "thirties", "", "england", "", "en"],
        ["missing-age", "missing.mp3", "s4", "Missing age", "general", 2, 0, "", "", "us", "", "en"],
    ]
    invalidated = [["older-invalid", "invalid.mp3", "s5", "Invalid", "", 0, 2, "sixties", "", "us", "", "en"]]
    other = [["older-other", "other.mp3", "s6", "Other", "", 0, 0, "eighties", "", "us", "", "en"]]
    return {
        "README.md": b"fixture\n",
        "validated.tsv": _tsv(columns, validated),
        "invalidated.tsv": _tsv(columns, invalidated),
        "other.tsv": _tsv(columns, other),
        "train.tsv": _tsv(columns, [validated[0]]),
        "dev.tsv": _tsv(columns, [validated[1]]),
        "test.tsv": _tsv(columns, []),
        "reported.tsv": _tsv(["sentence_id", "reason"], [["s1", "offensive-language"]]),
        "clip_durations.tsv": _tsv(
            ["clip", "duration[ms]"],
            [["a.mp3", 1000], ["b.mp3", 2000], ["young.mp3", 1000], ["missing.mp3", 1000], ["invalid.mp3", 1000], ["other.mp3", 1000]],
        ),
        "validated_sentences.tsv": _tsv(["sentence_id", "sentence"], [["s1", "One sentence"]]),
        "unvalidated_sentences.tsv": _tsv(["sentence_id", "sentence"], []),
    }


def _archive(path: Path, *, unsafe: bool = False) -> tuple[dict, dict[str, bytes]]:
    metadata = _metadata()
    clips = {
        "a.mp3": b"fixture-mp3-a",
        "b.mp3": b"fixture-mp3-b",
        "young.mp3": b"fixture-young",
        "missing.mp3": b"fixture-missing",
        "invalid.mp3": b"fixture-invalid",
        "other.mp3": b"fixture-other",
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, payload in [*metadata.items(), *[(f"clips/{name}", value) for name, value in clips.items()]]:
            member_name = f"{PREFIX}/{name}"
            info = tarfile.TarInfo(member_name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
        if unsafe:
            payload = b"unsafe"
            info = tarfile.TarInfo(f"{PREFIX}/../escape.txt")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    release = {
        "release_id": "fixture-release",
        "archive_size_bytes": path.stat().st_size,
        "archive_sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper(),
    }
    return release, clips


def _paths(tmp_path: Path, archive: Path) -> Phase3Paths:
    data = tmp_path
    training = tmp_path / "training"
    training.mkdir(exist_ok=True)
    return Phase3Paths(data, training, archive, "fixture-release")


def test_discovery_accepts_renamed_gzip_by_content_and_size(tmp_path: Path) -> None:
    raw = tmp_path / "Raw Datasets (Not formatted)"
    raw.mkdir()
    archive = raw / "Common Voice.gz"
    release, _ = _archive(archive)
    assert discover_archive(tmp_path, release) == archive
    assert detect_archive_format(archive) == "gzip-compressed tar"


def test_discovery_rejects_partial_download(tmp_path: Path) -> None:
    raw = tmp_path / "Raw Datasets (Not formatted)"
    raw.mkdir()
    (raw / "Common Voice.part").write_bytes(b"partial")
    with pytest.raises(Phase3Error, match="partial download"):
        discover_archive(tmp_path, {"archive_size_bytes": 7})


def test_member_path_safety() -> None:
    assert safe_member_name(f"{PREFIX}/clips/a.mp3", PREFIX)
    assert not safe_member_name(f"{PREFIX}/../escape", PREFIX)
    assert not safe_member_name("/absolute/path", PREFIX)


def test_source_audit_verifies_hash_and_extracts_only_metadata(tmp_path: Path) -> None:
    archive = tmp_path / "Common Voice"
    release, _ = _archive(archive)
    paths = _paths(tmp_path, archive)
    audit = source_audit(paths, release)
    assert audit["expected_sha256_match"] is True
    assert (paths.original_metadata / "validated.tsv").is_file()
    assert not any(paths.clips.iterdir())
    assert audit["archive_full_sequential_passes"] == 1


def test_source_audit_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "Common Voice"
    release, _ = _archive(archive, unsafe=True)
    with pytest.raises(Phase3Error, match="Unsafe or unexpected"):
        source_audit(_paths(tmp_path, archive), release)


def test_source_audit_rejects_content_hash_mismatch(tmp_path: Path) -> None:
    archive = tmp_path / "Common Voice"
    release, _ = _archive(archive)
    release["archive_sha256"] = "0" * 64
    with pytest.raises(Phase3Error, match="sha256"):
        source_audit(_paths(tmp_path, archive), release)


def test_validated_only_age_selection_and_member_list_are_deterministic(tmp_path: Path) -> None:
    archive = tmp_path / "Common Voice"
    release, _ = _archive(archive)
    paths = _paths(tmp_path, archive)
    source_audit(paths, release)
    first = build_metadata_state(paths, release)
    second = build_metadata_state(paths, release)
    assert first["older_metadata_candidate_clips"] == 2
    assert first["older_metadata_candidate_speakers"] == 2
    assert first["selected_older_age_labels"] == ["eighties", "seventies", "sixties"]
    assert first["accent_filter_policy"] == "none"
    assert first["selected_archive_member_list_sha256"] == second["selected_archive_member_list_sha256"]
    members = (paths.manifests / "common_voice_older_candidate_archive_members.v1.txt").read_text().splitlines()
    assert members == [f"{PREFIX}/clips/a.mp3", f"{PREFIX}/clips/b.mp3"]
    assert first["buckets"]["invalidated"]["clips"] == 1
    assert first["buckets"]["other"]["clips"] == 1


def test_selective_materialization_is_resumable_and_preserves_accents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "Common Voice"
    release, clips = _archive(archive)
    paths = _paths(tmp_path, archive)
    source_audit(paths, release)
    metadata = build_metadata_state(paths, release)

    def fake_validate(path: Path, expected_duration_ms: int | None) -> tuple:
        return (
            path.name,
            hashlib.sha256(path.read_bytes()).hexdigest().upper(),
            path.stat().st_size,
            (expected_duration_ms or 0) / 1000,
            48_000,
            1,
            "MP3",
            1,
            0.0,
        )

    monkeypatch.setattr("training_data.common_voice_phase3._validate_audio_file", fake_validate)
    first = materialize_selected_audio(paths, release, metadata)
    second = materialize_selected_audio(paths, release, metadata)
    assert first["selected_audio_materialized_files"] == 2
    assert first["archive_full_sequential_passes_this_run"] == 1
    assert second["archive_full_sequential_passes_this_run"] == 0
    assert (paths.clips / "a.mp3").read_bytes() == clips["a.mp3"]
    assert not (paths.clips / "young.mp3").exists()
    database = __import__("sqlite3").connect(paths.state / "common_voice_phase3.sqlite3")
    accents = dict(database.execute("SELECT path, accents FROM candidates"))
    database.close()
    assert accents["a.mp3"] == "us|canada"


def test_audio_validation_accepts_mp3_and_rejects_corruption(tmp_path: Path) -> None:
    audio = tmp_path / "readable.mp3"
    sf.write(audio, [0.0] * 8_000, 8_000, format="MP3")
    readable = _validate_audio_file(audio, 1_000)
    assert readable[6:8] == ("MP3", 1)
    assert readable[3] == pytest.approx(1.0)

    corrupt = tmp_path / "corrupt.mp3"
    corrupt.write_bytes(b"not audio")
    rejected = _validate_audio_file(corrupt, None)
    assert rejected[6:8] == ("unreadable", 0)


def test_evaluation_content_hash_firewall_and_cache(tmp_path: Path) -> None:
    archive = tmp_path / "Common Voice"
    archive.write_bytes(b"archive")
    paths = _paths(tmp_path, archive)
    evaluation_audio = tmp_path / "frozen" / "evaluation.wav"
    evaluation_audio.parent.mkdir()
    evaluation_audio.write_bytes(b"evaluation audio bytes")
    exclusion = pd.DataFrame(
        {
            "source_audio_logical_path": ["frozen/evaluation.wav"],
            "source_original_audio_logical_path": [None],
        }
    )

    hashes, first = _evaluation_content_hash_index(paths, exclusion)
    reused_hashes, second = _evaluation_content_hash_index(paths, exclusion)
    assert hashes == {hashlib.sha256(evaluation_audio.read_bytes()).hexdigest().upper()}
    assert reused_hashes == hashes
    assert first["hashes_computed_this_run"] == 1
    assert second["hashes_reused_from_cache"] == 1


def test_heldout_lock_applies_to_strict_and_relaxed_training() -> None:
    frame = pd.DataFrame({"training_role": ["train", "dev", "heldout", "train"]})
    initially_eligible = pd.Series([True, True, True, False])
    _apply_common_voice_eligibility(frame, initially_eligible)
    assert frame["strict_training_eligible"].tolist() == [True, True, False, False]
    assert frame["relaxed_training_eligible"].tolist() == [True, True, False, False]
    assert frame["commercial_training_eligible"].tolist() == [True, True, True, False]


def test_accent_separator_preserves_commas_inside_labels() -> None:
    regional = "Southern African (South Africa, Zimbabwe, Namibia)"
    assert _accent_tokens(regional) == [regional]
    assert _accent_tokens(f"United States English|{regional}") == [regional, "United States English"]


def test_accent_inventory_is_scoped_to_the_supplied_pool() -> None:
    frame = pd.DataFrame(
        [
            {"speaker_id": "train-a", "accents": "Canadian English", "duration_seconds": 2.0},
            {"speaker_id": "train-b", "accents": "", "duration_seconds": 3.0},
        ]
    )
    inventory, unspecified, multiple = _accent_inventory(frame.iloc[:1])
    assert inventory == {
        "Canadian English": {"speaker_incidence": 1, "clip_incidence": 1, "hours": 2 / 3600}
    }
    assert unspecified == 0
    assert multiple == 0


def test_speaker_split_is_deterministic_disjoint_and_age_stratified() -> None:
    rows = []
    for age in ("60s", "70s", "80s", "90s"):
        for index in range(12):
            rows.append({"speaker_id": f"{age}-{index}", "normalized_age_bin": age, "duration_seconds": index + 1})
    frame = pd.DataFrame(rows)
    first, underpowered = deterministic_speaker_split(frame)
    second, _ = deterministic_speaker_split(frame.sample(frac=1, random_state=1))
    assert first == second
    assert set(first.values()) == {"train", "dev", "heldout"}
    assert not any(underpowered.values())
    for age in ("60s", "70s", "80s", "90s"):
        assert {first[f"{age}-{index}"] for index in range(12)} == {"train", "dev", "heldout"}


def test_small_age_bin_preserves_speaker_independence() -> None:
    frame = pd.DataFrame(
        [
            {"speaker_id": "a", "normalized_age_bin": "90s", "duration_seconds": 1.0},
            {"speaker_id": "b", "normalized_age_bin": "90s", "duration_seconds": 2.0},
        ]
    )
    assignments, underpowered = deterministic_speaker_split(frame)
    assert len(assignments) == 2
    assert underpowered["90s"] is True
