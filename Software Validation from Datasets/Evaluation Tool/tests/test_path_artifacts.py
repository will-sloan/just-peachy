from __future__ import annotations

import os
from pathlib import Path

from app.utils.paths import metadata_path_to_project_relative, resolve_metadata_path
from app.utils.run_artifacts import relative_artifact_config, relative_artifact_record


def test_windows_raw_dataset_metadata_path_rebases_to_canonical_relative_path(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "Software Validation from Datasets"
    raw_path = (
        r"C:\Users\amiri\Documents\GitHub\just-peachy\Software Validation from Datasets"
        r"\Raw Datasets (Not formatted)\CMU Arctic\cmu_us_aew_arctic\wav\arctic_a0001.wav"
    )

    relative = metadata_path_to_project_relative(raw_path, project_root)
    resolved = resolve_metadata_path(raw_path, project_root)

    expected = Path("RawDatasets") / "CMU Arctic" / "cmu_us_aew_arctic" / "wav" / "arctic_a0001.wav"
    assert relative == expected
    assert resolved == project_root / expected


def test_artifact_record_uses_relative_paths_and_omits_resolved_runtime_fields(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "Software Validation from Datasets"
    run_dir = project_root / "Evaluation Tool" / "runs" / "run-001"
    source_audio = project_root / "RawDatasets" / "CMU Arctic" / "wav" / "a.wav"
    temp_audio = run_dir / "temp_audio" / "augmented.wav"
    record = {
        "recording_id": "rec-001",
        "audio_path": str(source_audio),
        "audio_path_project_relative": "RawDatasets/CMU Arctic/wav/a.wav",
        "audio_path_resolved": str(source_audio),
        "source_audio_path_resolved": str(source_audio),
        "source_audio_path_project_relative": "RawDatasets/CMU Arctic/wav/a.wav",
        "inference_audio_path": str(temp_audio),
        "reference_text": "hello",
    }

    artifact = relative_artifact_record(
        record,
        artifact_root=run_dir,
        project_root=project_root,
    )

    assert artifact["audio_path"] == "RawDatasets/CMU Arctic/wav/a.wav"
    assert artifact["inference_audio_path"] == "temp_audio/augmented.wav"
    assert artifact["source_audio_path_project_relative"] == "RawDatasets/CMU Arctic/wav/a.wav"
    assert "audio_path_resolved" not in artifact
    assert "source_audio_path_resolved" not in artifact


def test_artifact_config_writes_paths_relative_to_artifact_location(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "Software Validation from Datasets"
    run_dir = project_root / "Evaluation Tool" / "runs" / "run-001"
    config = {
        "project_root": str(project_root),
        "run_dir": str(run_dir),
        "dataset": {
            "normalized_metadata_dir": str(project_root / "Normalized Metadata" / "CMU Arctic"),
        },
        "prediction_contract": {
            "minimum_file": "predictions/utterances.jsonl",
        },
    }

    artifact = relative_artifact_config(
        config,
        artifact_root=run_dir,
        project_root=project_root,
    )

    assert artifact["project_root"] == Path(os.path.relpath(project_root, run_dir)).as_posix()
    assert artifact["run_dir"] == "."
    assert artifact["dataset"]["normalized_metadata_dir"] == "Normalized Metadata/CMU Arctic"
    assert artifact["prediction_contract"]["minimum_file"] == "predictions/utterances.jsonl"
