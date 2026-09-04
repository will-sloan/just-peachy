from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import yaml

from app.full_pipeline_evaluation.io import installed_tool_path_candidates
from app.full_pipeline_evaluation.protocol import (
    ProtocolError,
    audit_sources,
    load_cases,
    plan_protocol,
    preflight_case_contracts,
    prepare_protocol,
    validate_protocol,
)


def test_stage11_generated_audio_keeps_frozen_logical_path(tmp_path: Path) -> None:
    logical = Path("benchmarks/stage11/example_protocol/development/audio/case.wav")
    expected = (
        tmp_path
        / "JustPeachyGeneratedData/example_protocol/development/audio/case.wav"
    )
    expected.parent.mkdir(parents=True)
    expected.write_bytes(b"installed audio")

    candidates = installed_tool_path_candidates(logical, evaluation_root=tmp_path)

    assert candidates[0] == (tmp_path / logical).resolve()
    assert candidates[1] == expected.resolve()
    assert next(path for path in candidates if path.is_file()) == expected.resolve()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _fixture(
    tmp_path: Path,
    *,
    enrollment_overlap: bool = False,
    shared_gallery_impostor: bool = False,
) -> Path:
    source_root = tmp_path / "source"
    overlay_root = tmp_path / "overlay"
    transcript_path = tmp_path / "validated.tsv"
    transcript_path.write_text(
        "path\tsentence\nmixture.wav\tExact source sentence.\nenrollment.wav\tEnrollment only.\n",
        encoding="utf-8",
    )
    enrollment_audio = tmp_path / "enrollment.wav"
    enrollment_audio.write_bytes(b"fixture enrollment audio")
    enrollment_audio_sha = _sha(enrollment_audio)
    normalized = "exact source sentence."
    transcript_sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest().upper()
    inventory_path = source_root / "source_clip_inventory.csv"
    inventory_path.parent.mkdir(parents=True, exist_ok=True)
    with inventory_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["source_clip_id", "transcript_sha256", "logical_audio_path"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "source_clip_id": "clip_mix",
                "transcript_sha256": transcript_sha,
                "logical_audio_path": "mixture.wav",
            }
        )

    manifest_paths: list[Path] = [inventory_path]
    source_checksum_entries: dict[str, dict[str, object]] = {}
    for split, speaker, cropped in (
        ("development", "speaker_dev", False),
        ("evaluation", "speaker_eval", True),
    ):
        case_id = f"case_{split}"
        placement = {
            "global_start_sample": 0,
            "global_end_sample": 16000,
            "global_start_sec": 0.0,
            "global_end_sec": 1.0,
            "global_speaker_id": speaker,
            "reference_speaker": "SPK00",
            "logical_audio_path": "mixture.wav",
            "source_audio_sha256": "A" * 64,
            "source_clip_id": "clip_mix",
            "source_crop_start_sample": 0,
            "source_crop_end_sample": 16000,
            "turn_index": 0,
            "overlap_indicator": False,
            "product_short_turn_crop": cropped,
        }
        recipe_path = source_root / split / "recipes" / f"{case_id}.json"
        recipe_identity = "E" * 64
        _write_json(
            recipe_path,
            {"placements": [placement], "recipe_sha256": recipe_identity},
        )
        audio_path = source_root / split / "audio" / f"{case_id}.wav"
        audio_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path.write_bytes(f"fixture audio {split}".encode("utf-8"))
        rttm_path = source_root / split / "references" / f"{case_id}.rttm"
        uem_path = source_root / split / "references" / f"{case_id}.uem"
        rttm_path.parent.mkdir(parents=True, exist_ok=True)
        rttm_path.write_text(
            f"SPEAKER {case_id} 1 0.000000 1.000000 <NA> <NA> SPK00 <NA> <NA>\n",
            encoding="utf-8",
        )
        uem_path.write_text(f"{case_id} 1 0.000000 1.000000\n", encoding="utf-8")
        for relative, path in (
            (f"{split}/recipes/{case_id}.json", recipe_path),
            (f"{split}/references/{case_id}.rttm", rttm_path),
            (f"{split}/references/{case_id}.uem", uem_path),
        ):
            source_checksum_entries[relative] = {
                "sha256": _sha(path),
                "bytes": path.stat().st_size,
            }
        case = {
            "case_id": case_id,
            "recipe_path": f"{split}/recipes/{case_id}.json",
            "recipe_sha256": recipe_identity,
            "audio_logical_path": f"{split}/audio/{case_id}.wav",
            "audio_sha256": _sha(audio_path),
            "pcm_sha256": "C" * 64,
            "sample_rate_hz": 16000,
            "channels": 1,
            "duration_sec": 1.0,
            "global_speaker_ids": [speaker],
            "local_to_global_speaker": {"SPK00": speaker},
            "reference_rttm_path": f"{split}/references/{case_id}.rttm",
            "reference_uem_path": f"{split}/references/{case_id}.uem",
            "speaker_count": 1,
            "scenario_profile": "short_response_rare_reentry",
            "overlap_profile": "none",
            "reference_statistics": {"overlap_ratio": 0.0},
            "turn_cadence": "standard",
            "turn_pattern": "synthetic",
        }
        manifest_path = source_root / split / "case_manifest.jsonl"
        _write_jsonl(manifest_path, [case])
        manifest_paths.append(manifest_path)

        reserved_id = "clip_mix" if enrollment_overlap else f"clip_enroll_{split}"
        enrolled_id = f"enrolled_{split}"
        enrollment_database = [
            {
                "database_role": "live_known",
                "enrolled_id": enrolled_id,
                "global_speaker_id": speaker,
                "reserved_enrollment_clips": [
                    {
                        "source_clip_id": reserved_id,
                        "logical_audio_path": str(enrollment_audio),
                        "source_audio_sha256": enrollment_audio_sha,
                        "duration_sec": 2.0,
                    }
                ],
            }
        ]
        if shared_gallery_impostor:
            enrollment_database.append(
                {
                    "database_role": "background_impostor",
                    "enrolled_id": f"shared_impostor_{split}",
                    "global_speaker_id": "shared_gallery_speaker",
                    "reserved_enrollment_clips": [
                        {
                            "source_clip_id": f"shared_clip_{split}",
                            "logical_audio_path": str(enrollment_audio),
                            "source_audio_sha256": enrollment_audio_sha,
                            "duration_sec": 2.0,
                        }
                    ],
                }
            )
        overlay = {
            "case_id": case_id,
            "overlay_id": "ALL_KNOWN",
            "waveform_identity_unchanged": True,
            "speaker_states": {
                speaker: {
                    "identity_state": "KNOWN",
                    "enrolled_id": enrolled_id,
                    "unknown_reference_id": None,
                }
            },
            "enrollment_database": enrollment_database,
            "gallery_subsets": [
                {
                    "status": "VALID",
                    "requested_size": 1,
                    "realized_size": 1,
                    "enrolled_ids": [enrolled_id],
                    "primary": True,
                }
            ],
        }
        overlay_path = overlay_root / split / "identity_overlays.jsonl"
        _write_jsonl(overlay_path, [overlay])
        manifest_paths.append(overlay_path)

    checksums_path = source_root / "checksums.json"
    _write_json(checksums_path, {"entries": source_checksum_entries})
    manifest_paths.append(checksums_path)

    config = {
        "schema_version": "full-speech-pipeline-config.v1",
        "protocol_name": "full_speech_pipeline_v1",
        "protocol_version": 1,
        "selection_seed": 3800,
        "dataset_policy": {
            "installed_only": True,
            "downloads_allowed": False,
            "training_eligible": False,
        },
        "transcript_source": {
            "physical_path": str(transcript_path),
            "sha256": _sha(transcript_path),
            "path_column": "path",
            "text_column": "sentence",
            "normalization": "unicode_casefold_then_collapse_whitespace",
        },
        "sources": [
            {
                "source_key": "fixture_controlled",
                "kind": "controlled_primary",
                "source_root": str(source_root),
                "source_protocol_id": "fixture_controlled_v1",
                "identity_overlay_protocol_id": "fixture_overlay_v1",
                "identity_overlay_root": str(overlay_root),
                "partitions": ["development", "evaluation"],
                "case_manifests": {
                    "development": "development/case_manifest.jsonl",
                    "evaluation": "evaluation/case_manifest.jsonl",
                },
                "identity_overlays": {
                    "development": "development/identity_overlays.jsonl",
                    "evaluation": "evaluation/identity_overlays.jsonl",
                },
                "source_inventory": "source_clip_inventory.csv",
                "identity_files": [
                    {"path": str(path), "sha256": _sha(path)} for path in manifest_paths
                ],
                "supported_views": [
                    "asr",
                    "diarization",
                    "identity",
                    "streaming",
                    "resources",
                    "speaker_attributed_transcript",
                ],
                "unsupported_views": [],
            }
        ],
    }
    config_path = tmp_path / "protocol.yaml"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    return config_path


def test_prepare_is_deterministic_and_preserves_exact_reference_semantics(tmp_path: Path) -> None:
    config = _fixture(tmp_path)
    first_root = tmp_path / "prepared_a"
    second_root = tmp_path / "prepared_b"

    first = prepare_protocol(config, first_root)
    second = prepare_protocol(config, second_root)

    assert first["protocol_id"] == second["protocol_id"]
    assert first["files"] == second["files"]
    validation = validate_protocol(first_root, config_path=config)
    assert validation["valid"], validation["errors"]
    assert validation["checks"]["primary_development_evaluation_speaker_disjoint"]
    assert validation["checks"]["enrollment_mixture_disjoint"]
    assert validation["checks"]["development_evaluation_enrollment_gallery_speaker_disjoint"]
    assert validation["checks"]["supported_view_contracts_hydrate"]
    assert preflight_case_contracts(first_root)["valid"]

    development = load_cases(first_root, split="development")
    assert len(development) == 1
    assert development[0]["gallery_size"] == 1
    assert development[0]["overlay_id"] == "ALL_KNOWN"
    plan = plan_protocol(first_root)
    assert plan["case_counts"] == {"development": 1, "evaluation": 1}
    assert plan["inference_started"] is False

    evaluation_reference = json.loads(
        (first_root / "evaluation/references/speaker_attributed_transcript.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    segment = evaluation_reference["segments"][0]
    assert segment["source_transcript"] == "Exact source sentence."
    assert segment["source_transcript_sha256"]
    assert segment["scorable_transcript"] is None
    assert segment["speaker_attributed_transcript_status"] == "unsupported"
    assert segment["start_sample"] == 0 and segment["end_sample"] == 16000


def test_prepare_rejects_enrollment_mixture_overlap(tmp_path: Path) -> None:
    config = _fixture(tmp_path, enrollment_overlap=True)
    try:
        prepare_protocol(config, tmp_path / "prepared")
    except ProtocolError as error:
        assert "enrollment/mixture overlap" in str(error)
    else:  # pragma: no cover - makes the scientific guard explicit
        raise AssertionError("overlapping enrollment clip was accepted")


def test_source_audit_reports_frozen_identity_failure(tmp_path: Path) -> None:
    config = _fixture(tmp_path)
    document = yaml.safe_load(config.read_text(encoding="utf-8"))
    identity_path = Path(document["sources"][0]["identity_files"][0]["path"])
    identity_path.write_text(identity_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    audit = audit_sources(config)

    assert audit["status"] == "FAIL"
    assert any("frozen identity mismatch" in error for error in audit["errors"])
    assert audit["downloads_attempted"] is False
    assert audit["inference_started"] is False


def test_prepare_rejects_cross_partition_enrollment_speaker_reuse(tmp_path: Path) -> None:
    config = _fixture(tmp_path, shared_gallery_impostor=True)
    try:
        prepare_protocol(config, tmp_path / "prepared")
    except ProtocolError as error:
        assert "enrollment-gallery speakers overlap" in str(error)
    else:  # pragma: no cover
        raise AssertionError("cross-partition gallery speaker reuse was accepted")


def test_verify_audio_hashes_reserved_enrollment_clips(tmp_path: Path) -> None:
    config = _fixture(tmp_path)
    root = tmp_path / "prepared"
    prepare_protocol(config, root)
    (tmp_path / "enrollment.wav").write_bytes(b"tampered")

    validation = validate_protocol(root, config_path=config, verify_audio=True)

    assert not validation["valid"]
    assert any(
        "reserved enrollment audio SHA-256 differs" in error
        for error in validation["errors"]
    )
