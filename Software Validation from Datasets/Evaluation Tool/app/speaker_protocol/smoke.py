"""Real ECAPA and extended-backend Stage 10 smoke qualification."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Mapping

from app.speaker_protocol.contracts import TOOL_ROOT, eligible_embedding_backends
from app.speaker_protocol.evaluation import (
    evaluate_protocol_rows,
    observations_from_npz,
)
from app.speaker_protocol.extraction import load_backend_identity
from app.speaker_protocol.manifests import (
    build_protocol_manifests,
    read_protocol_rows,
)


REPOSITORY_ROOT = TOOL_ROOT.parent.parent
DEFAULT_MANIFEST_ROOT = TOOL_ROOT / "benchmarks" / "stage10" / "small"
DEFAULT_OUTPUT_ROOT = TOOL_ROOT / "runs" / "speaker_protocol_smoke"


def build_real_speaker_smoke(
    *,
    manifest_root: Path = DEFAULT_MANIFEST_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    rerun: bool = False,
) -> dict[str, object]:
    if not (manifest_root / "speaker_protocol_manifest.json").is_file():
        build_protocol_manifests(manifest_root, tier="small")
    rows = _smoke_rows(manifest_root)
    selected_ids = sorted(
        str(row["item_id"]) for values in rows.values() for row in values
    )
    backends = eligible_embedding_backends()
    results = []
    for backend_id, backend in sorted(backends.items()):
        extraction_root = output_root / "extractions" / backend_id
        result_root = output_root / "results" / backend_id
        evidence = extraction_root / "observations.npz"
        identity_path = extraction_root / "backend_identity.json"
        try:
            if rerun or not evidence.is_file() or not identity_path.is_file():
                command = [
                    str(_interpreter(str(backend["environment_profile"]))),
                    "-m",
                    "app.speaker_protocol.worker",
                    "--manifest-root",
                    str(manifest_root),
                    "--component",
                    backend_id,
                    "--output-root",
                    str(extraction_root),
                ]
                for item_id in selected_ids:
                    command.extend(("--item-id", item_id))
                completed = subprocess.run(
                    command,
                    cwd=TOOL_ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                if completed.returncode != 0:
                    raise RuntimeError(
                        completed.stderr.strip() or completed.stdout.strip() or "extraction failed"
                    )
            identity = load_backend_identity(identity_path)
            observations = observations_from_npz(evidence, identity)
            metrics = evaluate_protocol_rows(
                rows,
                observations,
                identity,
                result_root,
                scope="real_one-item-per-role-smoke",
                allow_overwrite=True,
            )
            results.append(
                {
                    "backend_id": backend_id,
                    "environment_profile": backend["environment_profile"],
                    "status": "passed",
                    "backend_identity_hash": identity.identity_hash,
                    "embedding_dimension": identity.embedding_dimension,
                    "expected_items": len(selected_ids),
                    "successful_items": metrics["extraction"]["successful_items"],
                    "calibration_evaluation_separate": metrics[
                        "calibration_evaluation_separate"
                    ],
                    "unknown_label": metrics["open_set_identification"]["unknown_label"],
                    "result_path": result_root.relative_to(TOOL_ROOT).as_posix(),
                }
            )
        except Exception as exc:  # backend failure isolation
            results.append(
                {
                    "backend_id": backend_id,
                    "environment_profile": backend["environment_profile"],
                    "status": "failed",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    payload = {
        "schema_version": "speaker-protocol-real-smoke.v1",
        "scope": "contract smoke; not full scientific speaker evaluation",
        "manifest_root": manifest_root.relative_to(TOOL_ROOT).as_posix(),
        "expected_backends": len(backends),
        "passed": sum(1 for row in results if row["status"] == "passed"),
        "failed": sum(1 for row in results if row["status"] != "passed"),
        "identical_item_ids_for_every_backend": True,
        "item_count_per_backend": len(selected_ids),
        "clean_source_only": True,
        "degraded_results_claimed": False,
        "implicit_model_downloads_allowed": False,
        "private_identity_mapping_included": False,
        "results": results,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    target = output_root / "real_smoke_matrix.json"
    _write_json(target, payload)
    _write_text(
        output_root / "real_smoke_matrix.json.sha256",
        _sha256(target).lower() + "  real_smoke_matrix.json\n",
    )
    return payload


def _smoke_rows(root: Path) -> dict[str, list[dict[str, object]]]:
    enrollment = read_protocol_rows(root / "enrollment.parquet", expected_kind="enrollment")
    calibration = read_protocol_rows(root / "calibration.parquet", expected_kind="calibration")
    known_eval = read_protocol_rows(
        root / "known_evaluation.parquet", expected_kind="known_evaluation"
    )
    unknown_eval = read_protocol_rows(
        root / "unknown_evaluation.parquet", expected_kind="unknown_evaluation"
    )
    known_speakers = sorted({str(row["speaker_key"]) for row in enrollment})[:2]
    selected_enrollment = []
    selected_calibration = []
    selected_known_eval = []
    for speaker in known_speakers:
        selected_enrollment.append(
            _first(enrollment, speaker=speaker, role="enrollment", condition="clean")
        )
        selected_calibration.append(
            _first(calibration, speaker=speaker, role="known_probe", condition="clean")
        )
        selected_known_eval.append(
            _first(known_eval, speaker=speaker, role="known_probe", condition="clean")
        )
    selected_calibration.append(
        _first(calibration, speaker=None, role="unknown_probe", condition="clean")
    )
    selected_unknown_eval = [
        _first(unknown_eval, speaker=None, role="unknown_probe", condition="clean")
    ]
    return {
        "enrollment": selected_enrollment,
        "calibration": selected_calibration,
        "known_evaluation": selected_known_eval,
        "unknown_evaluation": selected_unknown_eval,
    }


def _first(
    rows: list[dict[str, object]],
    *,
    speaker: str | None,
    role: str,
    condition: str,
) -> dict[str, object]:
    values = [
        row
        for row in rows
        if row["trial_role"] == role
        and row["protocol_condition"] == condition
        and (speaker is None or row["speaker_key"] == speaker)
    ]
    if not values:
        raise ValueError(f"smoke selection has no {role}/{condition}/{speaker}")
    return sorted(values, key=lambda row: str(row["item_id"]))[0]


def _interpreter(profile: str) -> Path:
    values = {
        "core-cpu": REPOSITORY_ROOT / ".venv" / "Scripts" / "python.exe",
        "extended-local": REPOSITORY_ROOT
        / ".stage8-envs"
        / "extended-local"
        / "Scripts"
        / "python.exe",
        "onnx": REPOSITORY_ROOT / ".stage8-envs" / "onnx" / "Scripts" / "python.exe",
        "wespeaker": REPOSITORY_ROOT
        / ".stage8-envs"
        / "wespeaker"
        / "Scripts"
        / "python.exe",
    }
    path = values.get(profile)
    if path is None or not path.is_file():
        raise FileNotFoundError(f"Stage 10 environment interpreter is unavailable: {profile}")
    return path


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    _write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8", newline="\n")
        for attempt in range(5):
            try:
                os.replace(temporary, path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.1 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
