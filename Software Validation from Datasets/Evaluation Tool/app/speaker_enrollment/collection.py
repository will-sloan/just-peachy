"""Compact collection package for external scientific interpretation."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
from typing import Mapping, Sequence

from app.speaker_enrollment.protocol import SpeakerEnrollmentError, validate_protocol


ANALYSIS_FILES = (
    "analysis_manifest.json",
    "configuration_results.csv",
    "speaker_results.csv",
    "duration_curve.csv",
    "enrollment_curve.csv",
    "aggregation_comparison.csv",
    "joint_frontier.csv",
    "reliability_summary.csv",
    "quality_loss_vs_reference.csv",
    "marginal_gain.csv",
    "speaker_diagnostics.csv",
    "enrollment_selection_variance.csv",
    "subgroup_results.csv",
    "report.md",
)


def collect_results(
    protocol_root: Path,
    source_protocol_root: Path,
    result_base: Path,
    analysis_root: Path,
    output_root: Path,
    backends: Sequence[str],
) -> dict[str, object]:
    validation = validate_protocol(protocol_root, source_protocol_root=source_protocol_root)
    output = output_root.resolve()
    if output.exists() and any(output.iterdir()):
        raise SpeakerEnrollmentError(f"collection output already exists: {output}")
    output.mkdir(parents=True, exist_ok=True)
    protocol_destination = output / "protocol"
    shutil.copytree(protocol_root, protocol_destination, dirs_exist_ok=False)
    shutil.copy2(protocol_root / "feasibility_audit.json", output / "feasibility_audit.json")
    (output / "validation_report.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    analysis_destination = output / "analysis"
    analysis_destination.mkdir()
    copied_analysis = []
    for name in ANALYSIS_FILES:
        source = analysis_root / name
        if source.is_file():
            shutil.copy2(source, analysis_destination / name)
            copied_analysis.append(name)
    if (analysis_root / "plots").is_dir():
        shutil.copytree(analysis_root / "plots", analysis_destination / "plots")
    backend_destination = output / "backend_evidence"
    summary_rows = []
    external_rows = []
    for backend in backends:
        root = result_base.resolve() / backend
        destination = backend_destination / backend
        destination.mkdir(parents=True, exist_ok=True)
        cache_root = root / "embeddings"
        for name in ("backend_identity.json", "cache_summary.json"):
            source = cache_root / name
            if source.is_file():
                shutil.copy2(source, destination / name)
        results = sorted(root.glob("phase_*/*/configuration_result.json"))
        summary_rows.append(
            {
                "backend": backend,
                "completed_configurations": len(results),
                "analysis_included": (analysis_destination / "configuration_results.csv").is_file(),
                "embedding_cache_copied": False,
                "embedding_cache_path": str(cache_root),
            }
        )
        if cache_root.exists():
            external_rows.append(
                {
                    "artifact_type": "biometric_embedding_cache_external_reference",
                    "backend": backend,
                    "path": str(cache_root),
                    "copied": False,
                    "reason": "large biometric-sensitive embedding bundles are referenced, not duplicated",
                }
            )
    _write_csv(output / "RUN_SUMMARY.csv", summary_rows)
    provenance = [
        "SCHEMA_VERSION=speaker-enrollment-collection-provenance.v1",
        f"PROTOCOL_ID={validation['protocol_id']}",
        f"SOURCE_PROTOCOL_ID={validation['source_protocol_id']}",
        f"GIT_HEAD={_git_sha()}",
        f"BACKENDS={','.join(backends)}",
        f"RESULT_BASE={result_base.resolve()}",
        f"ANALYSIS_ROOT={analysis_root.resolve()}",
        "RAW_AUDIO_COPIED=NO",
        "EMBEDDING_BUNDLES_COPIED=NO",
        "AUTOMATIC_PRODUCT_DECISION=NO",
    ]
    (output / "RUN_PROVENANCE.txt").write_text("\n".join(provenance) + "\n", encoding="utf-8", newline="\n")
    inventory = []
    for path in sorted(value for value in output.rglob("*") if value.is_file() and value.name != "RESULT_FILE_INVENTORY.csv"):
        inventory.append(
            {
                "artifact_type": "collected_file",
                "backend": "",
                "path": path.relative_to(output).as_posix(),
                "copied": True,
                "reason": "",
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    for row in external_rows:
        inventory.append({**row, "size_bytes": "", "sha256": ""})
    _write_csv(output / "RESULT_FILE_INVENTORY.csv", inventory)
    return {
        "schema_version": "speaker-enrollment-collection.v1",
        "protocol_id": validation["protocol_id"],
        "backends": list(backends),
        "analysis_files_copied": copied_analysis,
        "embedding_bundles_copied": False,
        "output_root": str(output),
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields = list(rows[0]) if rows else ["empty"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[4],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except Exception:
        return "UNKNOWN"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()
