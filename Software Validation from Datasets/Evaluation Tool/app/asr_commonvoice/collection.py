"""Compact, checksummed handoff package for the ASR generalization campaign."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import zipfile
import csv

from app.diarization_evaluation.artifacts import file_sha256, write_json_atomic, write_text_atomic

from .contracts import ASRCommonVoiceError, MODEL_COMPONENT_IDS
from .protocol import validate_protocol


def collect(
    result_root: Path,
    protocol_root: Path,
    collection_root: Path,
    *,
    create_zip: bool = True,
) -> dict[str, object]:
    """Collect analysis and compact provenance; never include audio or model weights."""

    result_root = result_root.resolve()
    protocol_root = protocol_root.resolve()
    destination = collection_root.resolve()
    protocol = validate_protocol(protocol_root)
    analysis_summary = _read_json(result_root / "analysis" / "analysis_manifest.json")
    if analysis_summary["protocol_id"] != protocol["protocol_id"]:
        raise ASRCommonVoiceError("analysis and protocol identities do not match")
    if destination.exists():
        manifest = destination / "collection_manifest.json"
        if manifest.is_file():
            validation = validate_collection(destination)
            return {**validation, "reused_collection": True}
        raise ASRCommonVoiceError(f"refusing to overwrite incomplete collection: {destination}")

    staging = destination.parent / f".{destination.name}.collecting"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        shutil.copytree(result_root / "analysis", staging / "analysis")
        shutil.copyfile(protocol_root / "protocol_summary.json", staging / "PROTOCOL_SUMMARY.json")
        shutil.copyfile(protocol_root / "protocol_files.json", staging / "protocol_files.json")
        shutil.copyfile(protocol_root / "manifest.parquet", staging / "protocol_manifest.parquet")
        shutil.copyfile(protocol_root / "campaign_config.yaml", staging / "campaign_config.yaml")
        for component in MODEL_COMPONENT_IDS:
            source = result_root / component
            target = staging / "backends" / component
            target.mkdir(parents=True)
            for name in ("backend_identity.json", "summary.json", "validation.json", "progress.json"):
                shutil.copyfile(source / name, target / name)
            shutil.copytree(source / "inference", target / "inference")
            shutil.copyfile(source / "predictions.jsonl", target / "predictions.jsonl")
        _write_collection_summaries(staging, analysis_summary)
        write_text_atomic(staging / "README.md", _readme(analysis_summary))
        _write_inventory(staging)
        _write_manifest(staging)
        os.replace(staging, destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    zip_path = None
    if create_zip:
        zip_path = destination.with_suffix(".zip")
        _write_deterministic_zip(destination, zip_path)
    validation = validate_collection(destination)
    return {
        **validation,
        "reused_collection": False,
        "zip_path": str(zip_path) if zip_path is not None else None,
        "zip_sha256": file_sha256(zip_path) if zip_path is not None else None,
    }


def validate_collection(root: Path) -> dict[str, object]:
    root = root.resolve()
    payload = _read_json(root / "collection_manifest.json")
    for relative, expected in dict(payload["files"]).items():
        path = root / relative
        if not path.is_file() or file_sha256(path) != expected:
            raise ASRCommonVoiceError(f"collection checksum mismatch: {relative}")
    prohibited = [path for path in root.rglob("*") if path.suffix.casefold() in {".wav", ".mp3", ".flac", ".onnx", ".pt", ".bin", ".tar", ".gz"}]
    if prohibited:
        raise ASRCommonVoiceError("collection contains prohibited audio/model/archive payloads")
    return {
        "valid": True,
        "collection_root": str(root),
        "campaign_id": payload["campaign_id"],
        "protocol_id": payload["protocol_id"],
        "file_count": len(payload["files"]),
        "bytes": sum((root / path).stat().st_size for path in payload["files"]),
    }


def _write_manifest(root: Path) -> None:
    summary = _read_json(root / "analysis" / "analysis_manifest.json")
    files = {
        path.relative_to(root).as_posix(): file_sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "collection_manifest.json"
    }
    write_json_atomic(root / "collection_manifest.json", {
        "schema_version": "asr-commonvoice-collection.v1",
        "campaign_id": summary["campaign_id"],
        "protocol_id": summary["protocol_id"],
        "mode": summary["mode"],
        "scientific_use_prohibited": summary["scientific_use_prohibited"],
        "contains_audio": False,
        "contains_model_weights": False,
        "files": files,
    })


def _write_deterministic_zip(root: Path, path: Path) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for source in sorted(item for item in root.rglob("*") if item.is_file()):
                relative = (Path(root.name) / source.relative_to(root)).as_posix()
                info = zipfile.ZipInfo(relative, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, source.read_bytes())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _readme(summary: dict[str, object]) -> str:
    return f"""# Common Voice 60+ ASR result handoff

Campaign: `{summary['campaign_id']}`

Protocol: `{summary['protocol_id']}`

Mode: `{summary['mode']}`

This compact package contains the complete analysis tables, frozen protocol
manifest, exact model/inference identities, summaries, and checksums. It does
not contain Common Voice audio, model weights, per-item restart checkpoints, or
credentials. Verify every file against `collection_manifest.json` before use.

The smoke mode is explicitly non-scientific. A full package may be uploaded as
one ZIP to the receiving machine; raw Common Voice assets must be acquired or
materialized separately under the same `JP_DATA_ROOT` logical layout and terms.
"""


def _write_collection_summaries(root: Path, summary: dict[str, object]) -> None:
    overall = list(summary["overall"])
    _write_csv(root / "RUN_SUMMARY.csv", overall)
    identities = _read_json(root / "analysis" / "model_identities.json")
    models = []
    for component_id, identity in identities.items():
        model = identity["model"]
        models.append({
            "human_name": model["human_name"],
            "component_id": component_id,
            "adapter": model["adapter"],
            "model_identity": json.dumps(model["model_identity"], sort_keys=True),
            "model_assets": json.dumps(model["model_assets"], sort_keys=True),
            "environment_profile": model["environment_profile"],
            "runtime": model["runtime"],
            "device": model["device"],
            "precision": model["precision"],
            "config_sha256": model["config_sha256"],
            "git_sha": identity["repository_git_sha"],
        })
    _write_csv(root / "MODEL_SUMMARY.csv", models)
    write_text_atomic(
        root / "RUN_PROVENANCE.txt",
        "\n".join([
            f"campaign_id={summary['campaign_id']}",
            f"protocol_id={summary['protocol_id']}",
            f"mode={summary['mode']}",
            f"scientific_use_prohibited={str(summary['scientific_use_prohibited']).lower()}",
            "augmentation=none",
            "bootstrap_unit=speaker",
            "bootstrap_repetitions=500",
            "bootstrap_seed=3800",
            "contains_audio=false",
            "contains_model_weights=false",
            "",
        ]),
    )


def _write_inventory(root: Path) -> None:
    rows = [
        {
            "relative_path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in {"RESULT_FILE_INVENTORY.csv", "collection_manifest.json"}
    ]
    _write_csv(root / "RESULT_FILE_INVENTORY.csv", rows)


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ASRCommonVoiceError(f"refusing to write empty summary: {path}")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ASRCommonVoiceError(f"expected JSON object: {path}")
    return value
