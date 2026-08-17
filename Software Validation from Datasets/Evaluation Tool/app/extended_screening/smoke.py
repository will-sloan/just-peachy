"""Real one-item Stage 9 smoke matrix over every Stage 8-qualified backend."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping

import soundfile as sf

from app.core_screening.metrics import analyze_asr_items, analyze_vad_segments
from app.extended_backends.contracts import validate_qualification_payload
from app.extended_screening.contracts import (
    eligible_backend_rows,
    load_qualification_registry,
)
from app.utils.paths import data_root, repository_root


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = repository_root().path
DEFAULT_OUTPUT_ROOT = TOOL_ROOT / "runs" / "extended_screening"
DEFAULT_AUDIO = (
    data_root().path
    / "Raw Datasets (Not formatted)"
    / "CMU Arctic"
    / "cmu_us_aew_arctic"
    / "wav"
    / "arctic_b0476.wav"
)
DEFAULT_REFERENCE = "The reorganization of these countries took the form of revolution."


def build_real_smoke_matrix(
    *,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    audio_path: Path = DEFAULT_AUDIO,
    rerun: bool = False,
) -> dict[str, object]:
    """Rerun or validate real profile evidence and produce comparable smoke rows."""

    registry = load_qualification_registry()
    eligible = eligible_backend_rows(registry)
    expected_ids = {str(row["backend_id"]) for row in eligible}
    profiles: dict[str, list[str]] = defaultdict(list)
    for row in eligible:
        profiles[str(row["profile"])].append(str(row["backend_id"]))
    destination = output_root.resolve()
    evidence_root = destination / "profile_evidence"
    evidence_root.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, dict[str, object]] = {}
    commands = []
    for profile in sorted(profiles):
        output_path = evidence_root / f"{profile}.json"
        if rerun:
            interpreter = _profile_interpreter(profile)
            command = [
                str(interpreter),
                str(TOOL_ROOT / "scripts" / "qualify_extended_backends.py"),
                "--profile",
                profile,
                "--audio",
                str(audio_path.resolve()),
                "--output",
                str(output_path),
            ]
            completed = subprocess.run(
                command,
                cwd=TOOL_ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=900,
            )
            commands.append(
                {
                    "profile": profile,
                    "command": _portable_command(command),
                    "exit_code": completed.returncode,
                }
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"Stage 9 real smoke failed for {profile}: "
                    + (completed.stderr.strip() or completed.stdout.strip())
                )
        elif not output_path.is_file():
            source = (
                TOOL_ROOT
                / "runs"
                / "extended_backend_qualification"
                / f"{profile}.json"
            )
            if not source.is_file():
                raise FileNotFoundError(f"missing qualification evidence for {profile}")
            output_path.write_bytes(source.read_bytes())
            commands.append(
                {
                    "profile": profile,
                    "command": "validated existing Stage 8 real evidence",
                    "exit_code": 0,
                }
            )
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        validate_qualification_payload(payload)
        evidence[profile] = payload

    result_rows = {
        str(row["backend_id"]): row
        for payload in evidence.values()
        for row in payload["results"]
        if isinstance(row, Mapping) and str(row.get("backend_id")) in expected_ids
    }
    if set(result_rows) != expected_ids:
        raise ValueError(
            f"real smoke coverage mismatch: missing={sorted(expected_ids - set(result_rows))}"
        )
    duration = float(sf.info(audio_path).frames) / float(sf.info(audio_path).samplerate)
    records = [
        _smoke_record(result_rows[str(row["backend_id"])], row, duration)
        for row in eligible
    ]
    payload: dict[str, object] = {
        "schema_version": "extended-screening-smoke.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "one_identical_real_item_contract_and_metric_smoke",
        "scientific_screening_complete": False,
        "comparison_item": {
            "recording_id": "arctic_b0476",
            "audio_sha256": _sha256(audio_path),
            "reference_text_sha256": hashlib.sha256(
                DEFAULT_REFERENCE.encode("utf-8")
            ).hexdigest(),
            "duration_sec": duration,
        },
        "commands": commands,
        "summary": {
            "expected_backends": len(expected_ids),
            "real_smoke_passed": sum(row["status"] == "passed" for row in records),
            "failed": sum(row["status"] != "passed" for row in records),
            "identical_item_for_every_backend": True,
        },
        "results": sorted(records, key=lambda row: str(row["backend_id"])),
        "secret_audit": {
            "values_serialized": False,
            "credential_presence_only": True,
        },
    }
    matrix_path = destination / "real_smoke_matrix.json"
    _atomic_write_json(matrix_path, payload)
    _atomic_write_text(
        matrix_path.with_suffix(".json.sha256"),
        f"{_sha256(matrix_path)}  {matrix_path.name}\n",
    )
    _write_smoke_handoffs(destination, payload)
    return payload


def _write_smoke_handoffs(
    destination: Path, payload: Mapping[str, object]
) -> None:
    records = [dict(row) for row in payload["results"]]
    _atomic_write_json(
        destination / "extended_component_comparison_tables.json",
        {
            "schema_version": "extended-component-comparison-tables.v1",
            "scope": "one-item real smoke; not the full small benchmark",
            "comparison_item": payload["comparison_item"],
            "rows": records,
            "runtime_values_comparable_only_within_environment_profile": True,
        },
    )
    _atomic_write_json(
        destination / "advancement_and_exclusion_report.json",
        {
            "schema_version": "extended-advancement-exclusion.v1",
            "scope": "smoke gate",
            "decisions": [
                {
                    "backend_id": row["backend_id"],
                    "action": (
                        "composition_passed_science_deferred_to_stage11"
                        if row["catalog_family"] == "diarization"
                        else "smoke_passed_full_small_screen_pending"
                    ),
                    "reason": (
                        "one-item output contract passed; advancement requires the declared full screening metrics"
                    ),
                }
                for row in records
            ],
            "opaque_score_used": False,
        },
    )
    profiles = sorted({str(row["environment_profile"]) for row in records})
    _atomic_write_json(
        destination / "environment_compatibility_matrix.json",
        {
            "schema_version": "extended-environment-compatibility-matrix.v1",
            "profiles": profiles,
            "profile_pairs": [
                {
                    "left": left,
                    "right": right,
                    "single_process_composable": left == right,
                }
                for left in profiles
                for right in profiles
            ],
        },
    )
    _atomic_write_json(
        destination / "benchmark_coverage_report.json",
        {
            "schema_version": "extended-benchmark-coverage.v1",
            "scope": "real smoke",
            "item_count": 1,
            "backend_count": len(records),
            "identical_item_for_every_backend": True,
            "full_small_screen_pending": True,
        },
    )
    _atomic_write_json(
        destination / "shortlist_manifest.json",
        {
            "schema_version": "extended-shortlist-manifest.v1",
            "plan_id": "pending-full-small-screen",
            "asr": [],
            "vad_segmentation": [],
            "speaker_embedding": [],
            "targeted_combinations": [],
            "status": "smoke_passed_scientific_shortlist_pending",
            "selection_policy": "the one-item smoke cannot advance candidates",
        },
    )


def _smoke_record(
    result: Mapping[str, object],
    registry_row: Mapping[str, object],
    duration_sec: float,
) -> dict[str, object]:
    status = str(result["status"])
    if status not in {"qualified", "qualified_with_warnings"}:
        raise ValueError(f"eligible backend lost qualification: {result['backend_id']}")
    family = str(result["family"])
    details = result.get("details")
    if not isinstance(details, Mapping):
        raise ValueError(f"real smoke details missing for {result['backend_id']}")
    metrics: dict[str, object]
    if family == "asr":
        transcripts = details.get("transcripts")
        if not isinstance(transcripts, list) or not transcripts:
            raise ValueError("ASR smoke has no transcript")
        metrics = analyze_asr_items(
            [
                {
                    "recording_id": "arctic_b0476",
                    "utt_id": "arctic_b0476",
                    "reference_text": DEFAULT_REFERENCE,
                    "duration_sec": duration_sec,
                }
            ],
            [
                {
                    "recording_id": "arctic_b0476",
                    "utt_id": "arctic_b0476",
                    "text": str(transcripts[0]),
                }
            ],
            component_spans=[],
        )
    elif family == "vad":
        metrics = analyze_vad_segments(
            [
                {
                    "duration_sec": duration_sec,
                    "predicted_regions": details.get("regions", []),
                    "segments": details.get("regions", []),
                }
            ]
        )
    elif family == "speaker_embedding":
        metrics = {
            "successful_extractions": details.get("valid_real_outputs"),
            "dimension": details.get("dimension"),
            "l2_norms": details.get("l2_norms"),
            "finite": details.get("finite"),
            "repeatability_l2_drift": details.get("repeatability_l2_drift"),
            "minimum_duration_status": details.get("minimum_duration_status"),
            "clean_to_degraded_drift": None,
            "unsupported_metrics": [
                {
                    "metric": "clean_to_degraded_drift",
                    "reason": "the one-item contract smoke has no degraded pair",
                }
            ],
        }
    elif family == "diarization":
        metrics = {
            "turn_count": details.get("turn_count"),
            "anonymous_label_consistency": details.get(
                "anonymous_label_consistency"
            ),
            "bounded": details.get("bounded"),
            "rttm_conversion": details.get("rttm_conversion"),
            "reference_label_fallback": details.get("reference_label_fallback"),
            "scientific_metrics_emitted": False,
        }
    else:
        raise ValueError(f"unsupported smoke family: {family}")
    return {
        "backend_id": result["backend_id"],
        "catalog_family": registry_row["catalog_family"],
        "catalog_name": registry_row["catalog_name"],
        "environment_profile": result["profile"],
        "status": "passed",
        "stage8_status": status,
        "output_contract_valid": bool(result["schema_validation"]),
        "repetitions": result["repetitions"],
        "timing": result["timing"],
        "metrics": metrics,
        "warnings": result["warnings"],
        "component_identity": result["component_identity"],
        "asset_identities": result["asset_identities"],
        "implicit_downloads_allowed": False,
        "scientific_scope": registry_row["disposition"],
    }


def _profile_interpreter(profile: str) -> Path:
    candidate = (
        REPOSITORY_ROOT / ".stage8-envs" / profile / "Scripts" / "python.exe"
    )
    if not candidate.is_file():
        raise FileNotFoundError(f"isolated Stage 8 interpreter is missing: {candidate}")
    return candidate


def _portable_command(command: list[str]) -> list[str]:
    values = []
    for item in command:
        path = Path(item)
        try:
            values.append(path.resolve().relative_to(REPOSITORY_ROOT).as_posix())
        except (ValueError, OSError):
            values.append(item)
    return values


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    try:
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
