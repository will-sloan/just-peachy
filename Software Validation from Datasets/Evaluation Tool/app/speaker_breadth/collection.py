"""Compact, analysis-ready collection for Common Voice breadth runs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
from typing import Mapping, Sequence

from app.benchmark_contracts.manifest_io import file_sha256
from app.speaker_breadth.commonvoice import (
    SpeakerBreadthError,
    _read_json,
    _read_tsv,
    _write_json,
    _write_text,
)
from app.speaker_protocol.evaluation import validate_protocol_results


SMALL_RESULT_FILES = (
    "backend_identity.json",
    "protocol_run.json",
    "calibration_results.json",
    "metrics/summary.json",
    "metrics/grouped_metrics.parquet",
    "verification_decisions.parquet",
    "identification_rankings.parquet",
    "unknown_rejection_decisions.parquet",
    "failures.parquet",
    "checksums.json",
)


def collect_results(
    protocol_root: Path,
    result_base: Path,
    output_root: Path,
    backends: Sequence[str],
) -> dict[str, object]:
    """Collect compact evidence while referencing large observation bundles in place."""

    if not backends:
        raise SpeakerBreadthError("Collect requires at least one backend")
    protocol = protocol_root.resolve()
    result_base = result_base.resolve()
    destination = output_root.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    summary = _read_json(protocol / "protocol_summary.json")
    protocol_id = str(summary["protocol_id"])
    run_rows = []
    inventory = []
    for backend in backends:
        backend_root = result_base / protocol_id / backend
        extraction_root = backend_root / "extraction"
        result_root = backend_root / "result"
        status = "NOT_RUN"
        metrics: Mapping[str, object] = {}
        try:
            validate_protocol_results(result_root)
            metrics = _read_json(result_root / "metrics" / "summary.json")
            status = "VALID"
        except Exception:
            if result_root.exists() or extraction_root.exists():
                status = "PARTIAL"
        extraction = (
            _read_json(extraction_root / "extraction_summary.json")
            if (extraction_root / "extraction_summary.json").is_file()
            else {}
        )
        expected = _integer(extraction.get("expected_items"))
        successful = _integer(extraction.get("successful_items"))
        run_rows.append(
            {
                "backend": backend,
                "status": status,
                "expected_items": expected,
                "successful_items": successful,
                "failed_items": _integer(extraction.get("failed_items")),
                "failure_rate": ("" if not expected else f"{(expected - successful) / expected:.8f}"),
                "verification_eer": _nested(metrics, "verification", "evaluation_eer", "eer"),
                "known_identification_top1": _nested(metrics, "closed_set_identification", "top_k", "1", "value"),
                "unknown_rejection_rate": _nested(metrics, "open_set_identification", "unknown_rejection_rate", "value"),
                "result_root": str(result_root),
                "observation_bundle": str(extraction_root / "observations.npz"),
            }
        )
        target = destination / "backends" / backend
        for relative in SMALL_RESULT_FILES:
            source = result_root / relative
            if source.is_file():
                output = target / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, output)
        for name in ("backend_identity.json", "extraction_summary.json"):
            source = extraction_root / name
            if source.is_file():
                target.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target / name)
        for source_root, label in ((extraction_root, "extraction"), (result_root, "result")):
            if not source_root.exists():
                continue
            for path in sorted(source_root.rglob("*"), key=lambda value: value.as_posix()):
                if path.is_file():
                    inventory.append(
                        {
                            "backend": backend,
                            "area": label,
                            "relative_path": path.relative_to(source_root).as_posix(),
                            "absolute_path": str(path),
                            "bytes": path.stat().st_size,
                            "sha256": file_sha256(path).upper(),
                            "copied_to_package": (target / path.relative_to(source_root)).is_file(),
                        }
                    )
    _write_csv(destination / "RUN_SUMMARY.csv", run_rows)
    _write_csv(destination / "RESULT_FILE_INVENTORY.csv", inventory)
    _write_json(destination / "PROTOCOL_SUMMARY.json", summary)
    _write_csv(destination / "SPEAKER_COHORT_SUMMARY.csv", _read_tsv(protocol / "speaker_inventory.tsv"))
    _write_csv(destination / "METADATA_COVERAGE.csv", _read_tsv(protocol / "metadata_coverage.tsv"))
    protocol_target = destination / "protocol"
    protocol_target.mkdir(parents=True, exist_ok=True)
    for path in sorted(protocol.iterdir(), key=lambda value: value.name):
        if path.is_file():
            shutil.copy2(path, protocol_target / path.name)
    _write_text(
        destination / "RUN_PROVENANCE.txt",
        "\n".join(
            [
                "Common Voice 60+ speaker breadth v1",
                f"Protocol ID: {protocol_id}",
                f"Protocol root: {protocol}",
                f"Result base: {result_base}",
                f"Selected backends: {', '.join(backends)}",
                "Large observations.npz bundles are referenced in RESULT_FILE_INVENTORY.csv and are not copied.",
                "This package contains no raw Common Voice audio or model assets.",
                "",
            ]
        ),
    )
    return {
        "output_root": str(destination),
        "protocol_id": protocol_id,
        "backends": len(backends),
        "valid_results": sum(row["status"] == "VALID" for row in run_rows),
        "inventory_files": len(inventory),
    }


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _integer(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _nested(value: Mapping[str, object], *keys: str) -> object:
    current: object = value
    for key in keys:
        if not isinstance(current, Mapping) or key not in current:
            return ""
        current = current[key]
    if isinstance(current, (dict, list)):
        return json.dumps(current, sort_keys=True, separators=(",", ":"))
    return current if current is not None else ""
