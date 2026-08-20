from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

import pytest
from app.benchmark_contracts.manifest_io import file_sha256
from app.speaker_breadth.commonvoice import (
    DEFAULT_CONFIG_PATH,
    CandidateClip,
    _breadth_leakage,
    _build_protocol_rows,
    _load_candidates,
    _load_config,
    _protocol_identity,
    _speaker_key,
    _write_protocol_manifests,
    select_cohort,
    selected_paths_exist,
)
from app.speaker_protocol.manifests import validate_protocol_manifest_set


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]


def test_actual_age_mapping_filters_to_observed_60plus_categories(tmp_path: Path) -> None:
    database = tmp_path / "commonvoice.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript(
        """
        CREATE TABLE candidates (
            path TEXT PRIMARY KEY, client_id TEXT, transcript TEXT, sentence_id TEXT,
            sentence_domain TEXT, source_age_label TEXT, normalized_age_bin TEXT,
            gender TEXT, accents TEXT, variant TEXT, locale TEXT, up_votes TEXT,
            down_votes TEXT
        );
        CREATE TABLE audio_validation (
            path TEXT PRIMARY KEY, audio_sha256 TEXT, size_bytes INTEGER,
            duration_seconds REAL, sample_rate_hz INTEGER, channels INTEGER,
            format TEXT, readable INTEGER, duration_delta_seconds REAL
        );
        """
    )
    for index, age in enumerate(("fifties", "sixties", "seventies", "eighties", "nineties")):
        path = f"clip-{index}.mp3"
        connection.execute(
            "INSERT INTO candidates VALUES (?, ?, ?, ?, '', ?, '', '', '', '', 'en', '2', '0')",
            (path, f"speaker-{index}", f"sentence {index}", f"sentence-{index}", age),
        )
        connection.execute(
            "INSERT INTO audio_validation VALUES (?, ?, 10, 1.0, 48000, 1, 'MP3', 1, 0.0)",
            (path, "A" * 64),
        )
    connection.commit()
    connection.close()

    rows = _load_candidates(database, _load_config(DEFAULT_CONFIG_PATH))

    assert {row.age_category for row in rows} == {
        "sixties",
        "seventies",
        "eighties",
        "nineties",
    }


def test_pseudonym_is_stable_and_separates_source_speakers() -> None:
    first = _speaker_key("client-a", "protocol-x")
    assert first == _speaker_key("client-a", "protocol-x")
    assert first != _speaker_key("client-b", "protocol-x")
    assert first.startswith("spk_cv60p_")
    assert "client-a" not in first


def test_selection_is_deterministic_capped_and_disjoint() -> None:
    config = _load_config(DEFAULT_CONFIG_PATH)
    candidates = _synthetic_candidates()
    first = select_cohort(candidates, config, "protocol-test")
    second = select_cohort(list(reversed(candidates)), config, "protocol-test")

    assert _selection_signature(first) == _selection_signature(second)
    assert len(first["known_speakers"]) == 4
    assert len(first["calibration_unknown_speakers"]) == 1
    assert len(first["evaluation_unknown_speakers"]) == 1
    assert not (first["known_speakers"] & first["calibration_unknown_speakers"])
    assert not (first["known_speakers"] & first["evaluation_unknown_speakers"])
    assert not (
        first["calibration_unknown_speakers"]
        & first["evaluation_unknown_speakers"]
    )
    for speaker, value in first["selected"].items():
        expected = 30 if value["speaker_role"] == "known" else 25
        assert len(value["clips"]) == expected
        transcripts = [row.transcript_sha256 for row in value["clips"]]
        assert len(transcripts) == len(set(transcripts))


def test_manifests_are_deterministic_stage10_compatible_and_leak_free(
    tmp_path: Path,
) -> None:
    config = _load_config(DEFAULT_CONFIG_PATH)
    candidates = _synthetic_candidates()
    identity = "commonvoice_60plus_v1_test"
    selection = select_cohort(candidates, config, identity)
    metadata = tmp_path / "validated.tsv"
    metadata.write_text("header\n", encoding="utf-8")
    paths = {"validated_metadata": metadata}
    rows, source, _speakers = _build_protocol_rows(selection, config, identity, paths)

    assert _breadth_leakage(rows, source, data_paths_exist=True)[
        "all_required_checks_passed"
    ]
    assert _breadth_leakage(rows, source, data_paths_exist=True)[
        "same_speaker_transcript_cross_split_count"
    ] == 0
    config_copy = tmp_path / "policy.yaml"
    config_copy.write_text(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    roots = [tmp_path / "one", tmp_path / "two"]
    for root in roots:
        root.mkdir()
        _write_protocol_manifests(root, rows, identity, config_copy, paths)
        validate_protocol_manifest_set(root)
    for filename in (
        "enrollment.parquet",
        "calibration.parquet",
        "known_evaluation.parquet",
        "unknown_evaluation.parquet",
        "clean_probes.parquet",
        "degraded_probes.parquet",
        "speaker_protocol_manifest.json",
    ):
        assert file_sha256(roots[0] / filename) == file_sha256(roots[1] / filename)


def test_logical_clip_paths_resolve_and_missing_paths_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    audio = tmp_path / "Raw Datasets (Not formatted)" / "Common Voice" / "clip.mp3"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"audio")
    (tmp_path / "Normalized Metadata").mkdir()
    monkeypatch.setenv("JP_DATA_ROOT", str(tmp_path))
    row = {"logical_audio_path": "Raw Datasets (Not formatted)/Common Voice/clip.mp3"}
    assert selected_paths_exist([row])
    audio.unlink()
    assert not selected_paths_exist([row])


def test_protocol_identity_is_bound_to_config_and_source_hashes(tmp_path: Path) -> None:
    config = _load_config(DEFAULT_CONFIG_PATH)
    metadata = tmp_path / "validated.tsv"
    metadata.write_text("metadata\n", encoding="utf-8")
    state = tmp_path / "materialization_complete.json"
    state.write_text(
        '{"candidate_membership_list_sha256":"' + "B" * 64 + '"}\n',
        encoding="utf-8",
    )
    paths = {"validated_metadata": metadata, "materialization_state": state}
    first = _protocol_identity(DEFAULT_CONFIG_PATH, paths, config)
    assert first == _protocol_identity(DEFAULT_CONFIG_PATH, paths, config)
    metadata.write_text("changed\n", encoding="utf-8")
    assert first != _protocol_identity(DEFAULT_CONFIG_PATH, paths, config)


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell is unavailable")
def test_powershell_plan_action_performs_no_inference() -> None:
    protocol = TOOL_ROOT / "benchmarks" / "speaker_breadth" / "commonvoice_60plus_v1"
    if not (protocol / "protocol_summary.json").is_file():
        pytest.skip("frozen Common Voice protocol package is absent")
    completed = subprocess.run(
        [
            shutil.which("powershell") or "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(TOOL_ROOT / "scripts" / "run_speaker_breadth_commonvoice.ps1"),
            "-Action",
            "Plan",
            "-Backends",
            "speechbrain_ecapa",
            "-ManagementPython",
            sys.executable,
        ],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Model inference performed: NO" in completed.stdout
    assert "speechbrain_ecapa" in completed.stdout


def _synthetic_candidates() -> list[CandidateClip]:
    rows = []
    for speaker_index in range(6):
        for clip_index in range(36):
            transcript_index = clip_index if clip_index < 35 else 0
            path = f"speaker-{speaker_index}-clip-{clip_index}.mp3"
            rows.append(
                CandidateClip(
                    path=path,
                    source_speaker_id=f"client-{speaker_index}",
                    transcript=f"speaker {speaker_index} transcript {transcript_index}",
                    sentence_id=f"sentence-{speaker_index}-{transcript_index}",
                    sentence_domain="general",
                    age_category="sixties",
                    gender="",
                    accent="",
                    variant="",
                    locale="en",
                    up_votes="2",
                    down_votes="0",
                    audio_sha256=hashlib.sha256(path.encode()).hexdigest().upper(),
                    size_bytes=100,
                    duration_sec=1.0 + clip_index / 100,
                    sample_rate_hz=48000,
                    channels=1,
                    audio_format="MP3",
                )
            )
    return rows


def _selection_signature(value: dict[str, object]) -> tuple[object, ...]:
    selected = value["selected"]
    return tuple(
        (
            speaker,
            row["speaker_role"],
            row["unknown_split"],
            tuple(clip.path for clip in row["clips"]),
        )
        for speaker, row in sorted(selected.items())
    )
