"""Compact, checksum-bound export of deployment study evidence."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import zipfile

from .contracts import SpeakerDeploymentError, file_sha256, load_config, write_json_atomic


def collect(result_root: Path, analysis_root: Path, destination: Path, config_path: Path, *, create_zip: bool = True) -> dict[str, object]:
    config = load_config(config_path)
    result_root, analysis_root, destination = result_root.resolve(), analysis_root.resolve(), destination.resolve()
    if destination.exists():
        manifest = destination / "collection_manifest.json"
        if manifest.is_file():
            return validate_collection(destination)
        raise SpeakerDeploymentError(f"refusing to overwrite incomplete collection: {destination}")
    staging = destination.with_name(f".{destination.name}.collecting")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    for name in (
        "analysis_summary.json", "model_comparison.csv", "enrollment_recommendations.csv",
        "gallery_scale_summary.csv", "enrollment_mode_summary.csv", "session_summary.csv", "session_trajectory_summary.csv",
        "hubness_summary.csv", "METRIC_GUIDE.md", "REPORT.md",
    ):
        shutil.copy2(analysis_root / name, staging / name)
    for backend in config["backends"]:
        target = staging / "backends" / str(backend)
        target.mkdir(parents=True)
        for name in ("summary.json", "gallery_operating_points.csv", "enrollment_operating_modes.csv", "hubness.csv", "subgroup_metrics.csv", "session_accumulation.csv", "session_trajectories.csv"):
            shutil.copy2(result_root / str(backend) / name, target / name)
    files = {
        str(path.relative_to(staging)).replace("\\", "/"): {"bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path in sorted(staging.rglob("*")) if path.is_file()
    }
    write_json_atomic(staging / "collection_manifest.json", {
        "schema_version": "speaker-embedding-deployment-collection.v1", "files": files,
        "raw_audio_included": False, "model_assets_included": False,
    })
    staging.rename(destination)
    if create_zip:
        zip_path = destination.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in sorted(destination.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(str(path.relative_to(destination.parent)).replace("\\", "/"), (1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    archive.writestr(info, path.read_bytes())
    return validate_collection(destination)


def validate_collection(root: Path) -> dict[str, object]:
    root = root.resolve()
    manifest = json.loads((root / "collection_manifest.json").read_text(encoding="utf-8"))
    for relative, expected in manifest["files"].items():
        path = root / relative
        if not path.is_file() or file_sha256(path) != expected["sha256"]:
            raise SpeakerDeploymentError(f"collection checksum mismatch: {relative}")
    prohibited = {".wav", ".mp3", ".flac", ".onnx", ".pt", ".pth", ".ckpt"}
    if any(path.suffix.lower() in prohibited for path in root.rglob("*") if path.is_file()):
        raise SpeakerDeploymentError("collection contains prohibited audio or model payloads")
    return {"status": "VALID", "collection_root": str(root), "files": len(manifest["files"]), "zip": str(root.with_suffix('.zip')) if root.with_suffix('.zip').is_file() else None}
