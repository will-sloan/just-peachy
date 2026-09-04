"""Audit and sign the H2 development/evaluation enrollment firewall.

The audit is metadata-only. It reads frozen manifests and enrollment registries,
proves that development and evaluation identities/audio references are disjoint,
and records that the held-out execution queue had not opened. It never reads or
copies audio, embeddings, model weights, predictions, or evaluation references.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
from typing import Iterable, Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = TOOL_ROOT / "automated_runs/h2_complete_product_pipeline_v17"
DEFAULT_OUTPUT = (
    DEFAULT_WORKSPACE
    / "engineering_validation/enrollment_firewall_audit_receipt.json"
)
SCHEMA_VERSION = "h2-enrollment-firewall-audit.v1"
AUDIT_ID = "H2_PREOPEN_ENROLLMENT_AND_SOURCE_FIREWALL_V1"
RETRYABLE_WINERRORS = {5, 32, 33}
RETRY_DELAYS_SEC = (0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 2.0, 2.0)
CASE_ISOLATION_FIELDS = (
    "protocol_case_id",
    "audio_sha256",
    "pcm_sha256",
    "source_reference_id",
    "source_case_id",
    "global_speaker_ids",
    "gallery_enrolled_ids",
)
REGISTRY_ISOLATION_FIELDS = (
    "enrolled_id",
    "global_speaker_id",
    "source_clip_id",
    "source_audio_sha256",
    "logical_audio_path",
)


class EnrollmentFirewallAuditError(RuntimeError):
    """The split firewall could not be proven from frozen metadata."""


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _read_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EnrollmentFirewallAuditError(f"JSON object required: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise EnrollmentFirewallAuditError(
                    f"JSONL object required: {path}:{line_number}"
                )
            rows.append(value)
    if not rows:
        raise EnrollmentFirewallAuditError(f"JSONL file is empty: {path}")
    return rows


def _strings(values: Iterable[object]) -> set[str]:
    output = {str(value) for value in values if value is not None and str(value)}
    if not output:
        raise EnrollmentFirewallAuditError("required identity set is empty")
    return output


def _flatten(rows: Sequence[Mapping[str, object]], field: str) -> set[str]:
    values: list[object] = []
    for row in rows:
        value = row.get(field)
        if isinstance(value, list):
            values.extend(value)
        else:
            values.append(value)
    return _strings(values)


def _registry_sets(
    rows: Sequence[Mapping[str, object]], *, expected_partition: str
) -> tuple[dict[str, set[str]], int]:
    if any(row.get("partition") != expected_partition for row in rows):
        raise EnrollmentFirewallAuditError(
            f"{expected_partition} enrollment registry has partition mismatch"
        )
    sets = {
        "enrolled_id": _flatten(rows, "enrolled_id"),
        "global_speaker_id": _flatten(rows, "global_speaker_id"),
    }
    if len(sets["enrolled_id"]) != len(rows) or len(
        sets["global_speaker_id"]
    ) != len(rows):
        raise EnrollmentFirewallAuditError(
            f"{expected_partition} enrollment identities are duplicated"
        )
    clip_rows: list[Mapping[str, object]] = []
    for row in rows:
        clips = row.get("reserved_enrollment_clips")
        if not isinstance(clips, list) or not clips:
            raise EnrollmentFirewallAuditError(
                f"{expected_partition} enrollment row lacks reserved clips"
            )
        if not all(isinstance(clip, Mapping) for clip in clips):
            raise EnrollmentFirewallAuditError("invalid enrollment clip metadata")
        clip_rows.extend(clip for clip in clips if isinstance(clip, Mapping))
    for field in ("source_clip_id", "source_audio_sha256", "logical_audio_path"):
        sets[field] = _flatten(clip_rows, field)
        if len(sets[field]) != len(clip_rows):
            raise EnrollmentFirewallAuditError(
                f"{expected_partition} enrollment clip field is duplicated: {field}"
            )
    if any(len(value) != 64 for value in sets["source_audio_sha256"]):
        raise EnrollmentFirewallAuditError("enrollment audio SHA-256 is malformed")
    return sets, len(clip_rows)


def _case_sets(
    rows: Sequence[Mapping[str, object]], *, expected_partition: str
) -> dict[str, set[str]]:
    if any(row.get("partition") != expected_partition for row in rows):
        raise EnrollmentFirewallAuditError(
            f"{expected_partition} case manifest has partition mismatch"
        )
    result = {field: _flatten(rows, field) for field in CASE_ISOLATION_FIELDS}
    if len(result["protocol_case_id"]) != len(rows):
        raise EnrollmentFirewallAuditError(
            f"{expected_partition} protocol case IDs are duplicated"
        )
    for field in ("audio_sha256", "pcm_sha256"):
        if any(len(value) != 64 for value in result[field]):
            raise EnrollmentFirewallAuditError(f"case SHA-256 is malformed: {field}")
    return result


def _set_sha256(values: set[str]) -> str:
    return _sha256_bytes(_canonical_bytes(sorted(values)))


def _source_row(path: Path, *, protocol_root: Path) -> dict[str, object]:
    resolved = path.resolve(strict=True)
    try:
        logical = resolved.relative_to(protocol_root).as_posix()
    except ValueError as exc:
        raise EnrollmentFirewallAuditError(
            f"protocol input escaped prepared root: {resolved}"
        ) from exc
    return {
        "logical_path": logical,
        "sha256": _sha256_file(resolved),
        "bytes": resolved.stat().st_size,
    }


def _heldout_preopen_audit(
    workspace: Path, job_manifest: Mapping[str, object]
) -> dict[str, object]:
    raw_jobs = job_manifest.get("jobs")
    if not isinstance(raw_jobs, list):
        raise EnrollmentFirewallAuditError("job manifest lacks jobs")
    evaluation_ids = sorted(
        str(row.get("job_id"))
        for row in raw_jobs
        if isinstance(row, Mapping) and row.get("split") == "evaluation"
    )
    if not evaluation_ids or any(not value for value in evaluation_ids):
        raise EnrollmentFirewallAuditError("frozen evaluation jobs are unavailable")
    if len(evaluation_ids) != len(set(evaluation_ids)):
        raise EnrollmentFirewallAuditError("evaluation job IDs are duplicated")

    program_state = _read_object(workspace / "program_state.json")
    program_jobs = program_state.get("jobs")
    if not isinstance(program_jobs, Mapping):
        raise EnrollmentFirewallAuditError("program state lacks frozen job states")
    program_rows = {
        job_id: program_jobs.get(job_id) for job_id in evaluation_ids
    }
    if any(
        not isinstance(row, Mapping)
        or str(row.get("state") or "").casefold() != "pending"
        or int(row.get("attempt_count") or 0) != 0
        or bool(row.get("result_path"))
        or bool(row.get("result_sha256"))
        for row in program_rows.values()
    ):
        raise EnrollmentFirewallAuditError(
            "held-out program state had opened before firewall audit"
        )

    database = workspace / "campaign.sqlite3"
    if not database.is_file():
        raise EnrollmentFirewallAuditError("campaign queue database is missing")
    uri = f"file:{database.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=30.0) as connection:
        placeholders = ",".join("?" for _ in evaluation_ids)
        state_rows = connection.execute(
            f"SELECT job_id, state, attempt_count FROM jobs WHERE job_id IN ({placeholders})",
            evaluation_ids,
        ).fetchall()
        attempt_count = int(
            connection.execute(
                f"SELECT COUNT(*) FROM attempts WHERE job_id IN ({placeholders})",
                evaluation_ids,
            ).fetchone()[0]
        )
    states = {
        str(job_id): (str(state), int(attempts))
        for job_id, state, attempts in state_rows
    }
    if not set(states).issubset(evaluation_ids) or any(
        state.casefold() != "pending" or attempts != 0
        for state, attempts in states.values()
    ):
        raise EnrollmentFirewallAuditError(
            "held-out queue had opened before firewall audit"
        )
    attempt_paths = [
        workspace / "attempts" / job_id
        for job_id in evaluation_ids
        if (workspace / "attempts" / job_id).exists()
    ]
    results_root = Path(str(program_state.get("results_root") or "")).resolve(
        strict=True
    )
    result_paths = [
        results_root / "jobs" / job_id
        for job_id in evaluation_ids
        if (results_root / "jobs" / job_id).exists()
    ]
    premature_receipts = [
        path.name
        for path in (
            workspace / "heldout_execution_manifest.json",
            workspace / "freeze_receipt.json",
        )
        if path.exists()
    ]
    if attempt_count or attempt_paths or result_paths or premature_receipts:
        raise EnrollmentFirewallAuditError(
            "held-out attempt/result/freeze artifact existed before audit"
        )
    return {
        "evaluation_job_count": len(evaluation_ids),
        "evaluation_jobs_materialized_in_queue": len(states),
        "evaluation_jobs_not_yet_materialized": len(evaluation_ids) - len(states),
        "evaluation_job_ids_sha256": _sha256_bytes(_canonical_bytes(evaluation_ids)),
        "all_evaluation_jobs_pending": True,
        "evaluation_attempt_count": 0,
        "evaluation_attempt_directories_present": 0,
        "evaluation_result_directories_present": 0,
        "heldout_execution_manifest_present": False,
        "freeze_receipt_present": False,
        "evaluation_predictions_or_metrics_inspected": False,
    }


def build_receipt(*, workspace: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve(strict=True)
    protocol_manifest_path = workspace / "protocol_manifest.json"
    job_manifest_path = workspace / "job_manifest.json"
    runtime_path = workspace / "runtime_implementation_identity.json"
    for path in (protocol_manifest_path, job_manifest_path, runtime_path):
        if not path.is_file():
            raise EnrollmentFirewallAuditError(f"required frozen input is missing: {path}")
    protocol_manifest = _read_object(protocol_manifest_path)
    job_manifest = _read_object(job_manifest_path)
    runtime_identity = _read_object(runtime_path)
    protocol_root = Path(str(protocol_manifest.get("prepared_protocol_root") or "")).resolve(
        strict=True
    )
    allowed_root = (TOOL_ROOT / "benchmarks/full_pipeline").resolve(strict=True)
    if protocol_root != allowed_root and allowed_root not in protocol_root.parents:
        raise EnrollmentFirewallAuditError("prepared protocol root escaped benchmark root")

    summary_path = protocol_root / "protocol_summary.json"
    summary = _read_object(summary_path)
    summary_sha = _sha256_file(summary_path)
    if summary_sha != protocol_manifest.get("prepared_protocol_summary_sha256"):
        raise EnrollmentFirewallAuditError("prepared protocol summary checksum differs")
    if (
        summary.get("development_evaluation_enrollment_gallery_speaker_disjoint")
        is not True
        or summary.get("primary_development_evaluation_speaker_disjoint") is not True
        or summary.get("evaluation_only") is not True
        or summary.get("training_eligible") is not False
        or summary.get("downloads_attempted") is not False
        or summary.get("audio_copied_or_modified") is not False
    ):
        raise EnrollmentFirewallAuditError("prepared protocol firewall contract differs")

    paths = {
        "protocol_summary.json": summary_path,
        "development/enrollment/enrollment_registry.jsonl": protocol_root
        / "development/enrollment/enrollment_registry.jsonl",
        "evaluation/enrollment/enrollment_registry.jsonl": protocol_root
        / "evaluation/enrollment/enrollment_registry.jsonl",
        "development/case_manifest.jsonl": protocol_root
        / "development/case_manifest.jsonl",
        "evaluation/case_manifest.jsonl": protocol_root
        / "evaluation/case_manifest.jsonl",
    }
    dev_registry = _read_jsonl(paths["development/enrollment/enrollment_registry.jsonl"])
    eval_registry = _read_jsonl(paths["evaluation/enrollment/enrollment_registry.jsonl"])
    dev_cases = _read_jsonl(paths["development/case_manifest.jsonl"])
    eval_cases = _read_jsonl(paths["evaluation/case_manifest.jsonl"])
    dev_registry_sets, dev_clip_count = _registry_sets(
        dev_registry, expected_partition="development"
    )
    eval_registry_sets, eval_clip_count = _registry_sets(
        eval_registry, expected_partition="evaluation"
    )
    dev_case_sets = _case_sets(dev_cases, expected_partition="development")
    eval_case_sets = _case_sets(eval_cases, expected_partition="evaluation")

    registry_overlaps = {
        field: len(dev_registry_sets[field] & eval_registry_sets[field])
        for field in REGISTRY_ISOLATION_FIELDS
    }
    case_overlaps = {
        field: len(dev_case_sets[field] & eval_case_sets[field])
        for field in CASE_ISOLATION_FIELDS
    }
    if any(registry_overlaps.values()) or any(case_overlaps.values()):
        raise EnrollmentFirewallAuditError(
            "development/evaluation identity or source overlap detected"
        )
    if (
        dev_registry_sets["global_speaker_id"]
        != dev_case_sets["global_speaker_ids"]
        or eval_registry_sets["global_speaker_id"]
        != eval_case_sets["global_speaker_ids"]
        or dev_registry_sets["enrolled_id"]
        != dev_case_sets["gallery_enrolled_ids"]
        or eval_registry_sets["enrolled_id"]
        != eval_case_sets["gallery_enrolled_ids"]
    ):
        raise EnrollmentFirewallAuditError(
            "case speaker/gallery membership differs from its enrollment registry"
        )

    preopen = _heldout_preopen_audit(workspace, job_manifest)
    runtime_sha = str(runtime_identity.get("identity_sha256") or "")
    if len(runtime_sha) != 64:
        raise EnrollmentFirewallAuditError("frozen runtime identity is malformed")
    source_inventory = [
        _source_row(path, protocol_root=protocol_root)
        for path in paths.values()
    ]
    source_inventory.sort(key=lambda row: str(row["logical_path"]))
    receipt: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "status": "VALID",
        "audit_id": AUDIT_ID,
        "created_at_utc": _utc_now(),
        "protocol_binding": {
            "h2_protocol_id": protocol_manifest.get("protocol_id"),
            "h2_protocol_manifest_sha256": _sha256_file(protocol_manifest_path),
            "h2_job_manifest_sha256": _sha256_file(job_manifest_path),
            "prepared_protocol_id": summary.get("protocol_id"),
            "prepared_protocol_summary_sha256": summary_sha,
            "development_partition_id": (
                summary.get("development_identity", {})
                if isinstance(summary.get("development_identity"), Mapping)
                else {}
            ).get("partition_id"),
            "evaluation_partition_id": (
                summary.get("evaluation_identity", {})
                if isinstance(summary.get("evaluation_identity"), Mapping)
                else {}
            ).get("partition_id"),
        },
        "runtime_binding": {
            "frozen_runtime_identity_sha256": runtime_sha,
            "frozen_runtime_identity_file_sha256": _sha256_file(runtime_path),
        },
        "partitions": {
            "development": {
                "registry_rows": len(dev_registry),
                "reserved_enrollment_clips": dev_clip_count,
                "case_manifest_rows": len(dev_cases),
                "global_speaker_count": len(dev_registry_sets["global_speaker_id"]),
                "enrolled_id_count": len(dev_registry_sets["enrolled_id"]),
                "speaker_set_sha256": _set_sha256(
                    dev_registry_sets["global_speaker_id"]
                ),
                "enrolled_id_set_sha256": _set_sha256(
                    dev_registry_sets["enrolled_id"]
                ),
                "gallery_exactly_matches_registry": True,
                "case_speakers_exactly_match_registry": True,
            },
            "evaluation": {
                "registry_rows": len(eval_registry),
                "reserved_enrollment_clips": eval_clip_count,
                "case_manifest_rows": len(eval_cases),
                "global_speaker_count": len(eval_registry_sets["global_speaker_id"]),
                "enrolled_id_count": len(eval_registry_sets["enrolled_id"]),
                "speaker_set_sha256": _set_sha256(
                    eval_registry_sets["global_speaker_id"]
                ),
                "enrolled_id_set_sha256": _set_sha256(
                    eval_registry_sets["enrolled_id"]
                ),
                "gallery_exactly_matches_registry": True,
                "case_speakers_exactly_match_registry": True,
            },
        },
        "cross_partition_overlap_counts": {
            "enrollment_registry": registry_overlaps,
            "case_manifest": case_overlaps,
        },
        "heldout_preopen": preopen,
        "source_file_inventory": source_inventory,
        "evidence_boundaries": {
            "metadata_only": True,
            "audio_opened_or_copied": False,
            "embeddings_or_biometric_templates_opened_or_copied": False,
            "evaluation_predictions_or_metrics_opened": False,
            "evaluation_reference_content_used_for_selection": False,
            "scientific_runtime_or_policy_changed": False,
            "used_for_scientific_selection": False,
            "large_case_manifests_embedded_in_compact_receipt": False,
            "exact_source_files_bound_by_sha256": True,
        },
    }
    receipt["receipt_sha256"] = _sha256_bytes(_canonical_bytes(receipt))
    return receipt


def validate_receipt(value: Mapping[str, object]) -> dict[str, object]:
    receipt = dict(value)
    signature = receipt.pop("receipt_sha256", None)
    if signature != _sha256_bytes(_canonical_bytes(receipt)):
        raise ValueError("enrollment firewall receipt signature differs")
    if (
        receipt.get("schema_version") != SCHEMA_VERSION
        or receipt.get("status") != "VALID"
        or receipt.get("audit_id") != AUDIT_ID
    ):
        raise ValueError("enrollment firewall receipt schema/status differs")
    partitions = receipt.get("partitions")
    overlaps = receipt.get("cross_partition_overlap_counts")
    preopen = receipt.get("heldout_preopen")
    boundaries = receipt.get("evidence_boundaries")
    sources = receipt.get("source_file_inventory")
    if not isinstance(partitions, Mapping) or set(partitions) != {
        "development",
        "evaluation",
    }:
        raise ValueError("enrollment firewall partition evidence differs")
    for split in ("development", "evaluation"):
        row = partitions[split]
        if (
            not isinstance(row, Mapping)
            or any(
                int(row.get(key) or 0) <= 0
                for key in (
                    "registry_rows",
                    "reserved_enrollment_clips",
                    "case_manifest_rows",
                    "global_speaker_count",
                    "enrolled_id_count",
                )
            )
            or row.get("gallery_exactly_matches_registry") is not True
            or row.get("case_speakers_exactly_match_registry") is not True
            or len(str(row.get("speaker_set_sha256") or "")) != 64
            or len(str(row.get("enrolled_id_set_sha256") or "")) != 64
        ):
            raise ValueError(f"enrollment firewall partition is incomplete: {split}")
    if not isinstance(overlaps, Mapping):
        raise ValueError("enrollment firewall overlap evidence is missing")
    expected_overlap_keys = {
        "enrollment_registry": set(REGISTRY_ISOLATION_FIELDS),
        "case_manifest": set(CASE_ISOLATION_FIELDS),
    }
    for group, expected in expected_overlap_keys.items():
        row = overlaps.get(group)
        if (
            not isinstance(row, Mapping)
            or set(map(str, row)) != expected
            or any(int(value) != 0 for value in row.values())
        ):
            raise ValueError(f"enrollment firewall overlap detected: {group}")
    if (
        not isinstance(preopen, Mapping)
        or int(preopen.get("evaluation_job_count") or 0) <= 0
        or int(preopen.get("evaluation_jobs_materialized_in_queue") or 0) < 0
        or int(preopen.get("evaluation_jobs_not_yet_materialized") or 0) < 0
        or int(preopen.get("evaluation_jobs_materialized_in_queue") or 0)
        + int(preopen.get("evaluation_jobs_not_yet_materialized") or 0)
        != int(preopen.get("evaluation_job_count") or 0)
        or preopen.get("all_evaluation_jobs_pending") is not True
        or preopen.get("evaluation_attempt_count") != 0
        or preopen.get("evaluation_attempt_directories_present") != 0
        or preopen.get("evaluation_result_directories_present") != 0
        or preopen.get("heldout_execution_manifest_present") is not False
        or preopen.get("freeze_receipt_present") is not False
        or preopen.get("evaluation_predictions_or_metrics_inspected") is not False
    ):
        raise ValueError("held-out queue was not proven unopened")
    required_boundaries = {
        "metadata_only": True,
        "audio_opened_or_copied": False,
        "embeddings_or_biometric_templates_opened_or_copied": False,
        "evaluation_predictions_or_metrics_opened": False,
        "evaluation_reference_content_used_for_selection": False,
        "scientific_runtime_or_policy_changed": False,
        "used_for_scientific_selection": False,
        "large_case_manifests_embedded_in_compact_receipt": False,
        "exact_source_files_bound_by_sha256": True,
    }
    if not isinstance(boundaries, Mapping) or any(
        boundaries.get(key) is not expected
        for key, expected in required_boundaries.items()
    ):
        raise ValueError("enrollment firewall evidence boundary differs")
    if not isinstance(sources, list) or len(sources) != 5:
        raise ValueError("enrollment firewall source inventory differs")
    names: set[str] = set()
    for row in sources:
        if not isinstance(row, Mapping):
            raise ValueError("invalid enrollment firewall source row")
        name = str(row.get("logical_path") or "")
        path = Path(name)
        if (
            not name
            or path.is_absolute()
            or ".." in path.parts
            or name in names
            or len(str(row.get("sha256") or "")) != 64
            or int(row.get("bytes") or 0) <= 0
        ):
            raise ValueError("invalid enrollment firewall source identity")
        names.add(name)
    return {**receipt, "receipt_sha256": signature}


def _atomic_publish(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        for index in range(len(RETRY_DELAYS_SEC) + 1):
            try:
                temporary.replace(path)
                return
            except PermissionError as exc:
                winerror = getattr(exc, "winerror", None)
                if index >= len(RETRY_DELAYS_SEC) or winerror not in RETRYABLE_WINERRORS:
                    raise
                time.sleep(RETRY_DELAYS_SEC[index])
    finally:
        temporary.unlink(missing_ok=True)


def run_audit(*, workspace: Path, output: Path) -> dict[str, object]:
    workspace = Path(workspace).resolve(strict=True)
    output = Path(output).resolve(strict=False)
    if workspace.drive.casefold() != "c:" or output.drive.casefold() != "c:":
        raise EnrollmentFirewallAuditError("workspace and output must remain on C:")
    receipt = build_receipt(workspace=workspace)
    validate_receipt(receipt)
    _atomic_publish(output, _canonical_bytes(receipt) + b"\n")
    published = _read_object(output)
    return validate_receipt(published)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.validate is not None:
        validated = validate_receipt(_read_object(args.validate.resolve(strict=True)))
        print(
            json.dumps(
                {
                    "status": "VALID",
                    "path": str(args.validate.resolve()),
                    "receipt_sha256": validated["receipt_sha256"],
                },
                indent=2,
            )
        )
        return 0
    receipt = run_audit(workspace=args.workspace, output=args.output)
    print(
        json.dumps(
            {
                "status": "VALID",
                "path": str(Path(args.output).resolve()),
                "receipt_sha256": receipt["receipt_sha256"],
                "partitions": receipt["partitions"],
                "heldout_preopen": receipt["heldout_preopen"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
