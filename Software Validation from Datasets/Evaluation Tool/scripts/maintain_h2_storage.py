"""Safely prune sealed, reproducible H2 case-shard intermediates.

This utility deliberately lives outside ``app/`` so attaching it to an active
campaign cannot alter the frozen result-affecting runtime identity.  A shard
tree is removed only after the queue state, every shard, the portable case
references, and the immutable result tree all agree.  A checksum-bound receipt
keeps the exact reproduction map after the regenerable bytes are removed.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import time
from typing import Mapping, Sequence


TOOL_ROOT = Path(__file__).resolve().parents[1]
if str(TOOL_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOL_ROOT))

from app.full_pipeline_evaluation.host_lock import (  # noqa: E402
    _try_lock,
    _unlock,
)
from app.full_pipeline_evaluation.io import (  # noqa: E402
    canonical_json_bytes,
    read_json,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from app.full_pipeline_evaluation.results import validate_result_tree  # noqa: E402
from app.full_pipeline_evaluation.store import (  # noqa: E402
    EvaluationJobState,
    EvaluationStateStore,
)
from app.full_pipeline_evaluation.worker import (  # noqa: E402
    _load_valid_case_shard,
)


RECEIPT_SCHEMA = "h2-storage-prune-receipt.v1"
PENDING_SCHEMA = "h2-storage-prune-pending.v1"
FORECAST_SCHEMA = "h2-storage-forecast.v1"
LIFECYCLE_SCHEMA = "h2-storage-artifact-lifecycle.v1"
EVENT_SCHEMA = "h2-storage-guardian-event.v1"
COMPRESSION_RECEIPT_SCHEMA = "h2-storage-compression-receipt.v1"
COMPRESSIBLE_JOB_KINDS = frozenset({"long_session", "long_session_evaluation"})
FORECAST_SAFETY_FACTOR = 1.5
TERMINAL_PROGRAM_STATUSES = frozenset(
    {
        "COMPLETE",
        "FAILED",
        "STOPPED",
        "BLOCKED",
        "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
    }
)


class StorageSafetyError(RuntimeError):
    """An exact safety or reproducibility invariant did not hold."""


class GuardianLock:
    """Hold a byte-range lock without publishing a replaceable owner file.

    The controller's host lock also publishes owner metadata. Windows indexing
    software can briefly hold that metadata and reject ``os.replace``. The
    guardian needs only single-instance exclusion, so the locked byte itself is
    sufficient and avoids that unrelated failure mode.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._handle: object | None = None

    def __enter__(self) -> "GuardianLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)
        handle = self.path.open("r+b")
        try:
            _try_lock(handle)
        except Exception:
            handle.close()
            raise
        self._handle = handle
        return self

    def __exit__(self, *_: object) -> None:
        handle = self._handle
        self._handle = None
        if handle is None:
            return
        try:
            _unlock(handle)
        finally:
            handle.close()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_local_path(path: Path, *, parent: Path | None = None) -> Path:
    candidate = Path(path)
    if candidate.is_symlink():
        raise StorageSafetyError(f"symlink path is not allowed: {candidate}")
    resolved = candidate.resolve()
    if parent is not None and not _is_relative_to(resolved, parent.resolve()):
        raise StorageSafetyError(f"path escapes its required parent: {candidate}")
    return resolved


def _require_drive(path: Path, required_drive: str) -> None:
    drive = Path(path).resolve().drive.casefold()
    expected = required_drive.rstrip("\\/").casefold()
    if not expected.endswith(":"):
        expected += ":"
    if drive != expected:
        raise StorageSafetyError(
            f"storage guardian requires drive {expected.upper()}, got {drive or '<none>'}"
        )


def _queue_databases(workspace: Path) -> tuple[Path, ...]:
    databases: list[Path] = []
    for directory, names, files in os.walk(workspace, followlinks=False):
        base = Path(directory)
        for name in tuple(names):
            child = base / name
            if child.is_symlink():
                names.remove(name)
        if "campaign.sqlite3" in files:
            database = base / "campaign.sqlite3"
            if database.is_symlink():
                raise StorageSafetyError(f"queue database cannot be a symlink: {database}")
            databases.append(database.resolve())
    return tuple(sorted(databases))


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise StorageSafetyError(
                    f"JSONL row {line_number} is not an object: {path}"
                )
            rows.append(value)
    return rows


def _case_id(case: Mapping[str, object]) -> str:
    value = (
        case.get("case_id")
        or case.get("protocol_case_id")
        or case.get("recording_id")
        or case.get("utt_id")
    )
    if value is None:
        raise StorageSafetyError("portable result reference lacks a case identity")
    return str(value)


def _portable_name(value: str) -> str:
    result = "".join(char if char.isalnum() or char in "_.-" else "_" for char in value)
    return result[:120] or "unnamed"


def _queue_label(database: Path, workspace: Path) -> str:
    relative = database.parent.relative_to(workspace).as_posix() or "root"
    return f"{_portable_name(relative)}_{sha256_bytes(relative.encode('utf-8'))[:10]}"


def _receipt_paths(
    *, receipt_root: Path, database: Path, workspace: Path, job_id: str
) -> tuple[Path, Path]:
    stem = f"{_queue_label(database, workspace)}__{_portable_name(job_id)}"
    final = receipt_root / f"{stem}.json"
    pending = receipt_root / f"{stem}.pending.json"
    return final, pending


def _validate_signed_document(
    document: Mapping[str, object], *, signature_key: str, schema_version: str
) -> None:
    if document.get("schema_version") != schema_version:
        raise StorageSafetyError(f"invalid receipt schema: {document.get('schema_version')}")
    unsigned = dict(document)
    observed = unsigned.pop(signature_key, None)
    expected = sha256_bytes(canonical_json_bytes(unsigned))
    if observed != expected:
        raise StorageSafetyError("storage-maintenance receipt checksum differs")


def _sign_document(
    document: Mapping[str, object], *, signature_key: str
) -> dict[str, object]:
    value = dict(document)
    value[signature_key] = sha256_bytes(canonical_json_bytes(value))
    return value


def _result_checksum_index(results_root: Path) -> dict[str, tuple[Path, ...]]:
    by_sha: dict[str, list[Path]] = {}
    for checksum_path in results_root.rglob("checksums.json"):
        if checksum_path.is_symlink() or not checksum_path.is_file():
            continue
        root = checksum_path.parent.resolve()
        if not _is_relative_to(root, results_root):
            continue
        digest = sha256_file(checksum_path)
        by_sha.setdefault(digest, []).append(root)
    return {key: tuple(sorted(values)) for key, values in by_sha.items()}


def _resolve_result_root(
    state: EvaluationJobState,
    *,
    results_root: Path,
    result_index: Mapping[str, Sequence[Path]],
) -> Path:
    expected = state.result_sha256
    if not expected:
        raise StorageSafetyError(f"complete queue row lacks result SHA: {state.spec.job_id}")
    matches = tuple(result_index.get(expected.casefold(), ()))
    if not matches:
        # Existing hashes are lowercase, but accept an uppercase database value.
        matches = tuple(result_index.get(expected.lower(), ()))
    if len(matches) != 1:
        raise StorageSafetyError(
            f"expected one sealed result for {state.spec.job_id}, found {len(matches)}"
        )
    root = _require_local_path(matches[0], parent=results_root)
    checksum = root / "checksums.json"
    if sha256_file(checksum).casefold() != expected.casefold():
        raise StorageSafetyError(f"sealed-result checksum differs: {root}")
    validation = validate_result_tree(
        root, expected_reuse_identity=state.spec.reuse_identity
    )
    if not validation.reusable:
        issues = "; ".join(
            f"{item.code}:{item.logical_path}" for item in validation.issues
        )
        raise StorageSafetyError(
            f"result tree is not reusable for {state.spec.job_id}: {issues or validation.run_status}"
        )
    return root


def _directory_inventory(root: Path) -> tuple[int, int]:
    total = 0
    files = 0
    for directory, names, file_names in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in names:
            if (base / name).is_symlink():
                raise StorageSafetyError(f"symlink below shard root: {base / name}")
        for name in file_names:
            path = base / name
            if path.is_symlink():
                raise StorageSafetyError(f"symlink below shard root: {path}")
            total += path.stat().st_size
            files += 1
    return total, files


def _validate_case_shards(
    *, shard_root: Path, state: EvaluationJobState, result_root: Path
) -> tuple[list[dict[str, object]], int, int]:
    spec = state.spec
    shard_root = _require_local_path(shard_root, parent=shard_root.parent)
    if shard_root.name != "case_shards_v1":
        raise StorageSafetyError(f"unexpected shard-root name: {shard_root}")
    if state.state != "complete" or state.completed_cases != spec.case_count:
        raise StorageSafetyError(f"queue job is not fully complete: {spec.job_id}")
    if spec.case_count < 1:
        raise StorageSafetyError(f"job has no case intermediates: {spec.job_id}")
    if len(set(spec.case_ids)) != spec.case_count:
        raise StorageSafetyError(f"job case IDs are not unique: {spec.job_id}")

    references = _read_jsonl(result_root / "references" / "cases.jsonl")
    reference_ids = tuple(_case_id(row) for row in references)
    if reference_ids != spec.case_ids:
        raise StorageSafetyError(
            f"portable result references differ from queue cases: {spec.job_id}"
        )

    allowed_root_names = set(spec.case_ids) | {"cursor.json"}
    observed_root_names = {entry.name for entry in shard_root.iterdir()}
    if observed_root_names != allowed_root_names:
        missing = sorted(allowed_root_names - observed_root_names)
        extra = sorted(observed_root_names - allowed_root_names)
        raise StorageSafetyError(
            f"shard-root inventory differs for {spec.job_id}; missing={missing}, extra={extra}"
        )

    receipt_cases: list[dict[str, object]] = []
    # Worker shard ordinals are intentionally one-based (the live worker uses
    # ``enumerate(cases, start=1)``). Preserve that exact published contract.
    for ordinal, (case_id, case) in enumerate(
        zip(spec.case_ids, references), start=1
    ):
        if Path(case_id).name != case_id or case_id in {".", ".."}:
            raise StorageSafetyError(f"unsafe case ID in queue: {case_id}")
        directory = shard_root / case_id
        if directory.is_symlink() or not directory.is_dir():
            raise StorageSafetyError(f"case directory is not a physical directory: {directory}")
        entries = tuple(directory.iterdir())
        if len(entries) != 1 or entries[0].name != "case_shard.json":
            raise StorageSafetyError(f"case directory inventory differs: {directory}")
        shard_path = entries[0]
        if shard_path.is_symlink() or not shard_path.is_file():
            raise StorageSafetyError(f"case shard is not a physical file: {shard_path}")
        document = _load_valid_case_shard(
            shard_path, job=spec, case=case, ordinal=ordinal
        )
        if document is None:
            raise StorageSafetyError(f"case shard failed exact validation: {shard_path}")
        receipt_cases.append(
            {
                "case_id": case_id,
                "ordinal": ordinal,
                "case_identity_sha256": document["case_identity_sha256"],
                "case_shard_sha256": document["shard_sha256"],
                "portable_reference_sha256": sha256_bytes(
                    canonical_json_bytes(case)
                ),
                "logical_bytes": shard_path.stat().st_size,
            }
        )

    cursor = read_json(shard_root / "cursor.json")
    unsigned_cursor = dict(cursor)
    cursor_sha = unsigned_cursor.pop("cursor_sha256", None)
    if cursor_sha is not None:
        expected_cursor_sha = sha256_bytes(canonical_json_bytes(unsigned_cursor))
        if cursor_sha != expected_cursor_sha:
            raise StorageSafetyError(f"cursor checksum differs: {shard_root}")
    total_bytes, file_count = _directory_inventory(shard_root)
    return receipt_cases, total_bytes, file_count


def _reproduction_inputs(workspace: Path) -> dict[str, object]:
    logical_names = (
        "campaign_manifest.json",
        "job_manifest.json",
        "protocol_manifest.json",
        "runtime_implementation_identity.json",
    )
    files: list[dict[str, object]] = []
    for name in logical_names:
        path = workspace / name
        if path.is_file() and not path.is_symlink():
            files.append(
                {
                    "logical_path": name,
                    "absolute_path": str(path.resolve()),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
    protocol_path = workspace / "protocol_manifest.json"
    config_path: Path | None = None
    config_expected: str | None = None
    if protocol_path.is_file():
        protocol = read_json(protocol_path)
        raw_path = protocol.get("config_path")
        if isinstance(raw_path, str) and raw_path:
            config_path = Path(raw_path).resolve()
            config_expected = str(protocol.get("config_sha256") or "")
    if config_path is not None and config_path.is_file() and not config_path.is_symlink():
        observed = sha256_file(config_path)
        if config_expected and observed.casefold() != config_expected.casefold():
            raise StorageSafetyError("frozen H2 configuration checksum differs")
        files.append(
            {
                "logical_path": "frozen_config",
                "absolute_path": str(config_path),
                "sha256": observed,
                "bytes": config_path.stat().st_size,
            }
        )
    return {"files": files}


def _prepare_pending_receipt(
    *,
    workspace: Path,
    database: Path,
    state: EvaluationJobState,
    shard_root: Path,
    result_root: Path,
    cases: Sequence[Mapping[str, object]],
    source_bytes: int,
    source_file_count: int,
    queue_metadata: Mapping[str, str],
) -> dict[str, object]:
    return _sign_document(
        {
            "schema_version": PENDING_SCHEMA,
            "status": "VALIDATED_PENDING_PRUNE",
            "created_at_utc": utc_now(),
            "workspace": str(workspace),
            "queue_database": str(database),
            "queue_database_relative_path": database.relative_to(workspace).as_posix(),
            "queue_metadata": dict(queue_metadata),
            "job": state.spec.to_jsonable(),
            "queue_completion": {
                "state": state.state,
                "completed_cases": state.completed_cases,
                "completed_audio_sec": state.completed_audio_sec,
                "completed_at_utc": state.completed_at_utc,
                "result_sha256": state.result_sha256,
            },
            "regenerable_source": {
                "absolute_path": str(shard_root),
                "logical_bytes": source_bytes,
                "file_count": source_file_count,
                "case_shards": list(cases),
            },
            "retained_sealed_result": {
                "absolute_path": str(result_root),
                "checksums_path": str(result_root / "checksums.json"),
                "checksums_sha256": state.result_sha256,
            },
            "reproduction_inputs": _reproduction_inputs(workspace),
            "prune_reason": (
                "The complete checksum-bound result tree contains the scientific "
                "outputs. Per-case shards are restart intermediates reproducible "
                "from the frozen job, protocol, runtime, source assets, and caches."
            ),
        },
        signature_key="pending_sha256",
    )


def _finalize_receipt(
    pending: Mapping[str, object], *, recovery: bool = False
) -> dict[str, object]:
    _validate_signed_document(
        pending, signature_key="pending_sha256", schema_version=PENDING_SCHEMA
    )
    return _sign_document(
        {
            "schema_version": RECEIPT_SCHEMA,
            "status": (
                "PRUNED_REGENERABLE_CASE_SHARDS_RECOVERED"
                if recovery
                else "PRUNED_REGENERABLE_CASE_SHARDS"
            ),
            "completed_at_utc": utc_now(),
            "validation_receipt": dict(pending),
            "retained": [
                "sealed result tree and its checksums",
                "transactional campaign database and immutable job spec",
                "frozen config, protocol, job manifest, and runtime identity",
                "source audio, model assets, shared caches, and enrollment profiles",
                "per-case IDs, identities, shard checksums, and reference checksums",
            ],
            "removed": ["fully completed case_shards_v1 restart intermediates"],
            "recovery_note": (
                "The pending receipt was durable and the exact source was already "
                "absent, so the interrupted receipt commit was completed."
                if recovery
                else None
            ),
        },
        signature_key="receipt_sha256",
    )


def _prune_one(
    *,
    workspace: Path,
    results_root: Path,
    database: Path,
    state: EvaluationJobState,
    result_index: Mapping[str, Sequence[Path]],
    receipt_root: Path,
    dry_run: bool,
) -> dict[str, object]:
    spec = state.spec
    final_path, pending_path = _receipt_paths(
        receipt_root=receipt_root,
        database=database,
        workspace=workspace,
        job_id=spec.job_id,
    )
    if final_path.is_symlink() or pending_path.is_symlink():
        raise StorageSafetyError("storage receipt paths cannot be symlinks")
    if final_path.is_file():
        document = read_json(final_path)
        _validate_signed_document(
            document, signature_key="receipt_sha256", schema_version=RECEIPT_SCHEMA
        )
        return {"action": "already_pruned", "job_id": spec.job_id, "receipt": str(final_path)}

    shard_root = database.parent / "attempts" / spec.job_id / "case_shards_v1"
    shard_root = shard_root.resolve()
    expected_parent = (database.parent / "attempts" / spec.job_id).resolve()
    if shard_root.parent != expected_parent or shard_root.name != "case_shards_v1":
        raise StorageSafetyError(f"computed shard target is not exact: {shard_root}")

    if pending_path.is_file() and not shard_root.exists():
        pending = read_json(pending_path)
        final = _finalize_receipt(pending, recovery=True)
        if not dry_run:
            write_json_atomic(final_path, final)
            pending_path.unlink()
        return {
            "action": "would_recover_receipt" if dry_run else "recovered_receipt",
            "job_id": spec.job_id,
            "receipt": str(final_path),
        }
    if not shard_root.is_dir():
        return {"action": "no_shard_tree", "job_id": spec.job_id}

    result_root = _resolve_result_root(
        state, results_root=results_root, result_index=result_index
    )
    cases, source_bytes, file_count = _validate_case_shards(
        shard_root=shard_root, state=state, result_root=result_root
    )
    pending = _prepare_pending_receipt(
        workspace=workspace,
        database=database,
        state=state,
        shard_root=shard_root,
        result_root=result_root,
        cases=cases,
        source_bytes=source_bytes,
        source_file_count=file_count,
        queue_metadata=EvaluationStateStore(database).metadata(),
    )
    if dry_run:
        return {
            "action": "would_prune",
            "job_id": spec.job_id,
            "logical_bytes": source_bytes,
            "file_count": file_count,
            "sealed_result": str(result_root),
        }

    write_json_atomic(pending_path, pending)
    # This is the only destructive operation. All path and scientific gates above
    # must succeed before this exact, non-symlink shard directory is removed.
    shutil.rmtree(shard_root)
    if shard_root.exists():
        raise StorageSafetyError(f"exact shard target still exists after prune: {shard_root}")
    final = _finalize_receipt(pending)
    write_json_atomic(final_path, final)
    pending_path.unlink()
    return {
        "action": "pruned",
        "job_id": spec.job_id,
        "logical_bytes": source_bytes,
        "file_count": file_count,
        "receipt": str(final_path),
        "sealed_result": str(result_root),
    }


def _receipt_observations(receipt_root: Path) -> list[tuple[int, int, float]]:
    observations: list[tuple[int, int, float]] = []
    for path in receipt_root.glob("*.json"):
        if path.name.endswith(".pending.json"):
            continue
        try:
            document = read_json(path)
            _validate_signed_document(
                document, signature_key="receipt_sha256", schema_version=RECEIPT_SCHEMA
            )
            pending = document["validation_receipt"]
            if not isinstance(pending, Mapping):
                continue
            source = pending["regenerable_source"]
            completion = pending["queue_completion"]
            if not isinstance(source, Mapping) or not isinstance(completion, Mapping):
                continue
            observations.append(
                (
                    int(source["logical_bytes"]),
                    int(completion["completed_cases"]),
                    float(completion["completed_audio_sec"]),
                )
            )
        except (OSError, ValueError, KeyError, TypeError, StorageSafetyError):
            continue
    return observations


def _projection_rates(
    *,
    sealed_observations: Sequence[tuple[int, int, float]],
    live_observations: Sequence[tuple[int, int, float]],
) -> tuple[float | None, float | None, str]:
    """Choose stable upper-bound rates for forecasting a whole future job.

    Partial panels are often ordered with very short cases first. Dividing
    their fixed per-case JSON overhead by only those few seconds creates a
    transient multi-gigabyte-per-hour rate that is not representative of a
    30–60 minute case. Prefer checksum-validated complete-job receipts and use
    partial observations only until the first sealed receipt exists.
    """

    basis = list(sealed_observations) or list(live_observations)
    label = (
        "sealed_complete_job_receipts"
        if sealed_observations
        else "partial_live_fallback_no_sealed_receipts"
    )
    per_audio = [value / audio for value, _, audio in basis if audio > 0]
    per_case = [value / cases for value, cases, _ in basis if cases > 0]
    return (
        max(per_audio) if per_audio else None,
        max(per_case) if per_case else None,
        label,
    )


def _should_scan_live_inventory(
    sealed_observations: Sequence[tuple[int, int, float]],
) -> bool:
    """Use expensive active-tree inventories only until a sealed basis exists."""

    return not sealed_observations


def _guardian_sleep_interval(requested_sec: float, capacity_risk: str) -> float:
    """Poll quickly at capacity risk and otherwise avoid inference contention."""

    if capacity_risk in {"EARLY_RECLAIM", "CRITICAL_RECLAIM"}:
        return min(requested_sec, 60.0)
    return requested_sec


def _program_status(workspace: Path) -> str:
    path = workspace / "program_state.json"
    if not path.is_file():
        return "UNKNOWN"
    try:
        return str(read_json(path).get("status") or "UNKNOWN").upper()
    except (OSError, ValueError, json.JSONDecodeError):
        return "UNKNOWN"


def _capacity_state(
    *,
    free_gib: float,
    minimum_free_gib: float,
    target_free_gib: float,
    estimated_peak_gib: float,
) -> dict[str, object]:
    """Classify capacity after reserving the largest observed future job.

    The controller's minimum remains the final corruption-prevention reserve.
    The higher guardian target is where operators should reclaim inactive,
    reproducible storage before the controller ever reaches that reserve.
    """

    projected_free = free_gib - estimated_peak_gib
    if projected_free >= target_free_gib:
        risk = "OK"
    elif projected_free >= minimum_free_gib:
        risk = "EARLY_RECLAIM"
    else:
        risk = "CRITICAL_RECLAIM"
    return {
        "risk": risk,
        "headroom_above_controller_minimum_gib": free_gib - minimum_free_gib,
        "projected_free_after_largest_job_gib": projected_free,
        "projected_headroom_after_largest_job_gib": (
            projected_free - minimum_free_gib
        ),
        "reclaim_to_guardian_target_gib": max(0.0, target_free_gib - projected_free),
        "controller_stop_expected_from_h2_growth": projected_free < minimum_free_gib,
    }


def _compression_policy_decision(
    *, job_kind: str, measurement_mode: str, capacity_risk: str
) -> tuple[bool, str]:
    """Return whether a running shard directory may inherit NTFS compression.

    Only the unusually large long-session restart payloads are eligible. The
    final matched resource measurements are excluded even if their manifest
    label changes, because filesystem compression could bias CPU or I/O.
    """

    if measurement_mode.casefold() == "resources":
        return False, "matched serial resource measurements are excluded"
    if job_kind not in COMPRESSIBLE_JOB_KINDS:
        return False, "job is not a long-session restart-payload producer"
    if capacity_risk not in {"EARLY_RECLAIM", "CRITICAL_RECLAIM"}:
        return False, "forecast retains the guardian target without compression"
    return True, "large non-resource restart payload with forecasted capacity risk"


def _manifest_jobs_by_id(workspace: Path) -> dict[str, dict[str, object]]:
    path = workspace / "job_manifest.json"
    if not path.is_file() or path.is_symlink():
        return {}
    rows = read_json(path).get("jobs")
    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        job_id = str(row.get("job_id") or "")
        if job_id:
            result[job_id] = dict(row)
    return result


def _directory_is_compressed(path: Path) -> bool:
    # FILE_ATTRIBUTE_COMPRESSED. Python exposes the raw Windows attributes on
    # stat results without requiring pywin32 or another campaign dependency.
    attributes = int(getattr(path.stat(), "st_file_attributes", 0))
    return bool(attributes & 0x800)


def _compression_receipt_path(
    *, receipt_root: Path, database: Path, workspace: Path, job_id: str
) -> Path:
    stem = f"{_queue_label(database, workspace)}__{_portable_name(job_id)}"
    return receipt_root / f"{stem}.json"


def _arm_ntfs_compression(
    *,
    workspace: Path,
    database: Path,
    state: EvaluationJobState,
    manifest_job: Mapping[str, object],
    receipt_root: Path,
    capacity_risk: str,
    dry_run: bool,
) -> dict[str, object]:
    """Mark one exact live shard directory for inherited NTFS compression.

    ``compact.exe`` is applied to the directory itself, not recursively. This
    makes future case directories/files inherit lossless compression while
    avoiding a competing scan or rewrite of files the worker already sealed.
    """

    spec = state.spec
    job_kind = str(manifest_job.get("job_kind") or "")
    eligible, reason = _compression_policy_decision(
        job_kind=job_kind,
        measurement_mode=spec.measurement_mode,
        capacity_risk=capacity_risk,
    )
    if not eligible:
        return {
            "action": "compression_not_eligible",
            "job_id": spec.job_id,
            "reason": reason,
        }
    if os.name != "nt":
        return {
            "action": "compression_unsupported_platform",
            "job_id": spec.job_id,
            "reason": "lossless inherited directory compression is Windows/NTFS only",
        }

    expected_parent = (database.parent / "attempts" / spec.job_id).resolve()
    shard_root = (expected_parent / "case_shards_v1").resolve()
    if (
        not _is_relative_to(expected_parent, workspace)
        or shard_root.parent != expected_parent
        or shard_root.name != "case_shards_v1"
    ):
        raise StorageSafetyError(f"computed compression target is not exact: {shard_root}")
    if shard_root.is_symlink():
        raise StorageSafetyError(f"compression target cannot be a symlink: {shard_root}")

    receipt_root.mkdir(parents=True, exist_ok=True)
    receipt_path = _compression_receipt_path(
        receipt_root=receipt_root,
        database=database,
        workspace=workspace,
        job_id=spec.job_id,
    )
    if receipt_path.is_symlink():
        raise StorageSafetyError(f"compression receipt cannot be a symlink: {receipt_path}")
    if receipt_path.is_file():
        receipt = read_json(receipt_path)
        _validate_signed_document(
            receipt,
            signature_key="receipt_sha256",
            schema_version=COMPRESSION_RECEIPT_SCHEMA,
        )
        return {
            "action": "compression_already_armed",
            "job_id": spec.job_id,
            "receipt": str(receipt_path),
        }
    if not shard_root.is_dir():
        return {
            "action": "compression_waiting_for_shard_tree",
            "job_id": spec.job_id,
            "path": str(shard_root),
        }

    before_compressed = _directory_is_compressed(shard_root)
    logical_bytes, file_count = _directory_inventory(shard_root)
    if dry_run:
        return {
            "action": "would_arm_lossless_ntfs_compression",
            "job_id": spec.job_id,
            "path": str(shard_root),
            "existing_logical_bytes_untouched": logical_bytes,
            "existing_file_count_untouched": file_count,
            "already_compressed": before_compressed,
        }

    compact = shutil.which("compact.exe") or shutil.which("compact")
    if compact is None:
        raise StorageSafetyError("Windows compact.exe is unavailable")
    completed = subprocess.run(
        [compact, "/C", "/I", "/Q", str(shard_root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    after_compressed = _directory_is_compressed(shard_root)
    if completed.returncode != 0 or not after_compressed:
        raise StorageSafetyError(
            "compact.exe did not arm inherited lossless compression; "
            f"exit={completed.returncode}, compressed={after_compressed}, "
            f"stderr={completed.stderr.strip()[:500]}"
        )
    after_bytes, after_file_count = _directory_inventory(shard_root)
    if (after_bytes, after_file_count) != (logical_bytes, file_count):
        raise StorageSafetyError(
            "logical shard inventory changed while directory compression was armed"
        )

    receipt = _sign_document(
        {
            "schema_version": COMPRESSION_RECEIPT_SCHEMA,
            "status": "LOSSLESS_NTFS_COMPRESSION_ARMED",
            "completed_at_utc": utc_now(),
            "workspace": str(workspace),
            "queue_database": str(database),
            "queue_database_relative_path": database.relative_to(workspace).as_posix(),
            "job": spec.to_jsonable(),
            "manifest_job_kind": job_kind,
            "capacity_risk_at_action": capacity_risk,
            "exact_directory": str(shard_root),
            "scope": (
                "directory metadata only; future descendant directories and files "
                "inherit lossless NTFS compression; no recursive rewrite was requested"
            ),
            "logical_inventory_before_and_after": {
                "logical_bytes": logical_bytes,
                "file_count": file_count,
                "unchanged": True,
            },
            "directory_compressed_before": before_compressed,
            "directory_compressed_after": after_compressed,
            "command": [str(compact), "/C", "/I", "/Q", str(shard_root)],
            "command_exit_code": completed.returncode,
            "command_stdout": completed.stdout.strip()[:2000],
            "command_stderr": completed.stderr.strip()[:2000],
            "scientific_boundary": {
                "content_hash_semantics": "unchanged; NTFS storage metadata only",
                "serial_resource_measurements_excluded": True,
                "frozen_runtime_identity_affected": False,
                "performance_note": (
                    "Compression can alter filesystem CPU/I/O cost, so it is never "
                    "enabled for matched serial resource jobs."
                ),
            },
            "reversal": f'compact.exe /U /I /Q "{shard_root}"',
        },
        signature_key="receipt_sha256",
    )
    write_json_atomic(receipt_path, receipt)
    return {
        "action": "armed_lossless_ntfs_compression",
        "job_id": spec.job_id,
        "path": str(shard_root),
        "receipt": str(receipt_path),
        "logical_bytes_untouched": logical_bytes,
        "file_count_untouched": file_count,
    }


def _protect_active_long_sessions(
    *,
    workspace: Path,
    stores: Sequence[tuple[Path, EvaluationStateStore]],
    capacity_risk: str,
    receipt_root: Path,
    dry_run: bool,
) -> list[dict[str, object]]:
    jobs_by_id = _manifest_jobs_by_id(workspace)
    outcomes: list[dict[str, object]] = []
    for database, store in stores:
        for state in store.list_jobs():
            if state.state not in {"running", "partial"}:
                continue
            manifest_job = jobs_by_id.get(state.spec.job_id, {})
            job_kind = str(manifest_job.get("job_kind") or "")
            eligible, _ = _compression_policy_decision(
                job_kind=job_kind,
                measurement_mode=state.spec.measurement_mode,
                capacity_risk=capacity_risk,
            )
            if not eligible:
                continue
            outcomes.append(
                _arm_ntfs_compression(
                    workspace=workspace,
                    database=database,
                    state=state,
                    manifest_job=manifest_job,
                    receipt_root=receipt_root,
                    capacity_risk=capacity_risk,
                    dry_run=dry_run,
                )
            )
    return outcomes


def _artifact_lifecycle(
    *, workspace: Path, results_root: Path
) -> dict[str, object]:
    """Build the compact retention/reproduction map for campaign artifacts.

    This is intentionally a policy map rather than a second file inventory.
    Checksummed result trees and prune receipts already contain exact payload
    inventories. Repeating them here would consume space without improving
    reproducibility.
    """

    program: Mapping[str, object] = {}
    program_path = workspace / "program_state.json"
    if program_path.is_file():
        raw_program = read_json(program_path)
        if isinstance(raw_program, Mapping):
            program = raw_program
    manifest: Mapping[str, object] = {}
    manifest_path = workspace / "job_manifest.json"
    if manifest_path.is_file():
        raw_manifest = read_json(manifest_path)
        if isinstance(raw_manifest, Mapping):
            manifest = raw_manifest
    rows = manifest.get("jobs")
    jobs = (
        [dict(row) for row in rows if isinstance(row, Mapping)]
        if isinstance(rows, list)
        else []
    )
    neural_kinds = {
        "runtime_accuracy",
        "runtime_qualification",
        "successive_halving_runtime",
        "resource_runtime",
        "post_selection_resource_runtime",
        "post_promotion_integration",
        "post_selection_mode_validation",
        "post_selection_paragraph_validation",
        "diagnostic_runtime",
        "long_session",
        "long_session_evaluation",
        "reliability",
        "app_validation",
        "onnx_export",
        "onnx_parity",
    }
    neural_rows = [
        row for row in jobs if str(row.get("job_kind") or "") in neural_kinds
    ]
    last_neural_phase = max(
        (int(row.get("phase_index") or 0) for row in neural_rows), default=None
    )
    current_phase = int(program.get("current_phase_index") or 0)
    terminal = _program_status(workspace) in TERMINAL_PROGRAM_STATUSES
    shared_cache = results_root.parent / "_shared_cache"
    receipt_root = workspace / "storage_maintenance" / "receipts"
    neural_consumers_finished = (
        last_neural_phase is not None and current_phase > last_neural_phase
    )
    document = {
        "schema_version": LIFECYCLE_SCHEMA,
        "updated_at_utc": utc_now(),
        "campaign_status": _program_status(workspace),
        "current_phase_index": current_phase,
        "last_planned_neural_consumer_phase": last_neural_phase,
        "principle": (
            "Retain compact evidence and exact regeneration identities; retain "
            "regenerable payloads only through their last verified consumer."
        ),
        "artifacts": [
            {
                "artifact_class": "scientific_results",
                "absolute_scope": str(results_root),
                "retention": "RETAIN",
                "payload_inventory_source": "per-result checksums.json",
                "reason": "authoritative measurements and portable case references",
            },
            {
                "artifact_class": "campaign_control_and_reproduction_map",
                "absolute_scope": str(workspace),
                "retention": "RETAIN_COMPACT_CONTROL_FILES",
                "payload_inventory_source": str(receipt_root),
                "reason": (
                    "manifests, SQLite state, hashes, signed prune receipts, and "
                    "final reports reproduce removed intermediates"
                ),
            },
            {
                "artifact_class": "windows_atomic_publication_recovery",
                "absolute_scope": str(
                    workspace
                    / "storage_maintenance"
                    / "windows_atomic_publication_policy.json"
                ),
                "event_log": str(
                    workspace / "logs" / "windows_atomic_publication_events.jsonl"
                ),
                "retention": "RETAIN_COMPACT_POLICY_AND_EVENTS",
                "currently_needed_soon": not terminal,
                "reason": (
                    "checksum-bound operational mapping for bounded retries of "
                    "transient Windows atomic-publication sharing violations"
                ),
            },
            {
                "artifact_class": "sealed_case_restart_shards",
                "absolute_scope": str(
                    workspace / "attempts" / "<job_id>" / "case_shards_v1"
                ),
                "retention": "AUTO_PRUNE_AFTER_RESULT_SEAL",
                "reproduction_map": str(receipt_root / "<queue>__<job_id>.json"),
                "reason": "duplicate restart payload after immutable result validation",
            },
            {
                "artifact_class": "running_or_incomplete_restart_state",
                "absolute_scope": str(workspace / "attempts"),
                "retention": (
                    "RETAIN_UNTIL_JOB_SEALED; LOSSLESS_NTFS_COMPRESSION_ALLOWED_FOR_"
                    "CAPACITY_RISK_LONG_SESSIONS"
                ),
                "reason": (
                    "required for crash-safe restart of the current atomic job; only "
                    "non-resource long-session descendants may inherit compression"
                ),
            },
            {
                "artifact_class": "shared_content_addressed_inference_cache",
                "absolute_scope": str(shared_cache),
                "retention": (
                    "OWNERSHIP_AUDIT_THEN_PRUNE_REGENERABLE_ENTRIES"
                    if terminal or neural_consumers_finished
                    else "RETAIN_THROUGH_LAST_NEURAL_CONSUMER"
                ),
                "last_planned_consumer_phase": last_neural_phase,
                "currently_needed_soon": (
                    not terminal
                    and last_neural_phase is not None
                    and current_phase <= last_neural_phase
                ),
                "retirement_trigger": (
                    "after the last checksum-verified neural consumer; preserve the "
                    "content-address map and hashes, then remove only entries proven "
                    "unowned by another active campaign"
                ),
                "automatic_blind_deletion_allowed": False,
                "reason": (
                    "shared across development, held-out, streaming, reliability, and "
                    "resource jobs; global ownership forbids blind campaign deletion"
                ),
            },
            {
                "artifact_class": "private_biometric_restart_cache",
                "absolute_scope": str(workspace / "private_biometric_cache"),
                "retention": "RETAIN_THROUGH_FINAL_VALIDATION_THEN_PRUNE",
                "public_package": "EXCLUDED",
                "reason": "restartable enrollment evidence with biometric sensitivity",
            },
            {
                "artifact_class": "source_audio_and_model_assets",
                "absolute_scope": "repository-managed C: datasets and model stores",
                "retention": "RETAIN_SHARED_SINGLE_COPY",
                "reason": "not duplicated into campaign workspaces; required for exact reruns",
            },
            {
                "artifact_class": "preflight_python_bytecode",
                "absolute_scope": str(workspace / "preflight_pycache*"),
                "retention": "REGENERABLE_EXCLUDE_FROM_FINAL_PACKAGE",
                "reason": "not a scientific input or result",
            },
        ],
        "automatic_deletion_boundary": (
            "Only exact sealed case_shards_v1 trees are automatically removed. "
            "Active long-session trees may receive lossless NTFS directory metadata "
            "when capacity is at risk; global caches require a final ownership review."
        ),
    }
    return _sign_document(document, signature_key="lifecycle_sha256")


def _forecast(
    *,
    workspace: Path,
    results_root: Path,
    states: Sequence[EvaluationJobState],
    receipt_root: Path,
    minimum_free_gib: float,
    target_free_gib: float,
) -> dict[str, object]:
    usage = shutil.disk_usage(workspace)
    sealed_observations = _receipt_observations(receipt_root)
    # Once checksum-validated complete-job receipts exist, they are the
    # authoritative projection basis (see _projection_rates).  Rewalking every
    # active case-shard tree would not change that projection, but on Windows it
    # can contend with model imports and worker startup for tens of seconds.
    # Exact free space is still measured above on every pass.  Fall back to a
    # live inventory only before the first sealed observation exists.
    scan_live_inventory = _should_scan_live_inventory(sealed_observations)
    live_observations: list[tuple[int, int, float]] = []
    if scan_live_inventory:
        for state in states:
            shard_root = workspace / "attempts" / state.spec.job_id / "case_shards_v1"
            if shard_root.is_dir() and not shard_root.is_symlink():
                try:
                    byte_count, _ = _directory_inventory(shard_root)
                except StorageSafetyError:
                    continue
                completed = max(1, state.completed_cases)
                completed_audio = max(0.0, state.completed_audio_sec)
                live_observations.append((byte_count, completed, completed_audio))

    observations = [*sealed_observations, *live_observations]
    bytes_per_case = [value / cases for value, cases, _ in observations if cases > 0]
    median_per_case = statistics.median(bytes_per_case) if bytes_per_case else None
    conservative_per_audio_sec, conservative_per_case, projection_basis = (
        _projection_rates(
            sealed_observations=sealed_observations,
            live_observations=live_observations,
        )
    )
    incomplete = [state for state in states if state.state != "complete"]
    queued_by_job = {state.spec.job_id: state for state in states}
    program_jobs: Mapping[str, object] = {}
    program_path = workspace / "program_state.json"
    if program_path.is_file():
        raw_jobs = read_json(program_path).get("jobs")
        if isinstance(raw_jobs, Mapping):
            program_jobs = raw_jobs

    # Future promotion/held-out queues are materialized only when their phase
    # opens. Forecast from the complete frozen job manifest, not only today's
    # SQLite queues, so the long-session peak is visible before that phase.
    manifest_rows: list[dict[str, object]] = []
    manifest_path = workspace / "job_manifest.json"
    if manifest_path.is_file():
        raw_manifest_jobs = read_json(manifest_path).get("jobs")
        if isinstance(raw_manifest_jobs, list):
            manifest_rows = [
                dict(row) for row in raw_manifest_jobs if isinstance(row, Mapping)
            ]
    remaining_work: list[tuple[str, int, float]] = []
    for row in manifest_rows:
        job_id = str(row.get("job_id") or "")
        case_ids = row.get("case_ids")
        case_count = len(case_ids) if isinstance(case_ids, list) else 0
        audio_sec = float(row.get("audio_duration_sec") or 0.0)
        if not job_id or case_count < 1 or audio_sec <= 0:
            continue
        program_row = program_jobs.get(job_id)
        program_state = (
            str(program_row.get("state") or "").upper()
            if isinstance(program_row, Mapping)
            else ""
        )
        if program_state == "COMPLETE":
            continue
        queue_state = queued_by_job.get(job_id)
        completed_cases = queue_state.completed_cases if queue_state else 0
        completed_audio = queue_state.completed_audio_sec if queue_state else 0.0
        remaining_work.append(
            (
                job_id,
                max(0, case_count - completed_cases),
                max(0.0, audio_sec - completed_audio),
            )
        )
    if not remaining_work:
        remaining_work = [
            (
                state.spec.job_id,
                max(0, state.spec.case_count - state.completed_cases),
                max(0.0, state.spec.audio_duration_sec - state.completed_audio_sec),
            )
            for state in incomplete
        ]
    remaining_cases = sum(value[1] for value in remaining_work)
    remaining_audio = sum(value[2] for value in remaining_work)
    largest_job = max(
        (
            max(
                (
                    audio_sec * conservative_per_audio_sec
                    if conservative_per_audio_sec is not None
                    else 0.0
                ),
                (
                    case_count * conservative_per_case
                    if conservative_per_case is not None
                    else 0.0
                ),
            )
            * FORECAST_SAFETY_FACTOR
            for _, case_count, audio_sec in remaining_work
        ),
        default=0.0,
    )
    free_gib = usage.free / (1024**3)
    estimated_peak_gib = largest_job / (1024**3)
    capacity = _capacity_state(
        free_gib=free_gib,
        minimum_free_gib=minimum_free_gib,
        target_free_gib=target_free_gib,
        estimated_peak_gib=estimated_peak_gib,
    )
    return {
        "schema_version": FORECAST_SCHEMA,
        "updated_at_utc": utc_now(),
        "workspace": str(workspace),
        "results_root": str(results_root),
        "program_status": _program_status(workspace),
        "disk": {
            "drive": workspace.drive,
            "total_gib": usage.total / (1024**3),
            "free_gib": free_gib,
            "used_gib": usage.used / (1024**3),
            "minimum_free_gib": minimum_free_gib,
            "target_free_gib": target_free_gib,
            "above_controller_minimum": free_gib >= minimum_free_gib,
            "above_guardian_target": free_gib >= target_free_gib,
        },
        "queue_upper_bound": {
            "incomplete_job_count": len(remaining_work),
            "remaining_case_count": remaining_cases,
            "remaining_audio_sec": remaining_audio,
            "note": (
                "Conservative upper bound comes from the complete frozen job manifest, "
                "including future queues and candidates that may be eliminated by "
                "successive halving. It is not a runtime commitment."
            ),
        },
        "observed_intermediate_rate": {
            "observation_count": len(observations),
            "sealed_complete_observation_count": len(sealed_observations),
            "partial_live_observation_count": len(live_observations),
            "live_inventory_scanned": scan_live_inventory,
            "live_inventory_policy": (
                "scan_until_first_sealed_complete_job_receipt"
                if scan_live_inventory
                else "skip_after_sealed_projection_basis_to_avoid_inference_contention"
            ),
            "whole_job_projection_basis": projection_basis,
            "projection_safety_factor": FORECAST_SAFETY_FACTOR,
            "median_logical_bytes_per_case": median_per_case,
            "conservative_logical_bytes_per_audio_sec": conservative_per_audio_sec,
            "conservative_logical_bytes_per_case": conservative_per_case,
            "partial_live_max_logical_bytes_per_audio_sec_diagnostic": max(
                (
                    value / audio
                    for value, _, audio in live_observations
                    if audio > 0
                ),
                default=None,
            ),
            "note": (
                "Whole-job projection prefers sealed complete-job receipts. Before "
                "the first seal, partial live rates provide a fallback. After a "
                "sealed basis exists, active shard trees are not rewalked because "
                "they cannot change the projection and the disk walk can contend "
                "with model-worker startup. Exact drive free space is still measured "
                "on every pass."
            ),
        },
        "estimated_peak_next_single_job_gib": estimated_peak_gib,
        "estimated_free_after_largest_single_job_gib": capacity[
            "projected_free_after_largest_job_gib"
        ],
        "estimated_largest_single_job_preserves_minimum": (
            not capacity["controller_stop_expected_from_h2_growth"]
        ),
        "capacity_protection": capacity,
        "policy": {
            "automatic_prune_scope": "sealed complete case_shards_v1 only",
            "never_pruned": [
                "raw/source audio",
                "sealed scientific results",
                "shared inference caches through their last verified neural consumer",
                "model weights",
                "enrollment profiles",
                "incomplete/failed/running intermediates",
            ],
        },
    }


def _emit(event: Mapping[str, object]) -> None:
    value = {"schema_version": EVENT_SCHEMA, "at_utc": utc_now(), **dict(event)}
    print(json.dumps(value, sort_keys=True), flush=True)


def run_pass(args: argparse.Namespace) -> dict[str, object]:
    workspace = _require_local_path(args.workspace)
    results_root = _require_local_path(args.results_root)
    if not workspace.is_dir() or not results_root.is_dir():
        raise StorageSafetyError("workspace and results root must already exist")
    _require_drive(workspace, args.required_drive)
    _require_drive(results_root, args.required_drive)

    maintenance_root = workspace / "storage_maintenance"
    receipt_root = maintenance_root / "receipts"
    receipt_root.mkdir(parents=True, exist_ok=True)
    databases = _queue_databases(workspace)
    stores = [(database, EvaluationStateStore(database)) for database in databases]
    states = [state for _, store in stores for state in store.list_jobs()]
    complete_states = [
        (database, state)
        for database, store in stores
        for state in store.list_jobs(states=("complete",))
        if state.spec.case_count >= 1
    ]
    # Building the checksum index walks every historical result directory. It is
    # needed only when a newly sealed shard tree is actually eligible for its
    # first prune. Existing signed receipts and absent shard trees are handled
    # before _prune_one consults the index.
    needs_result_index = False
    for database, state in complete_states:
        final_path, _ = _receipt_paths(
            receipt_root=receipt_root,
            database=database,
            workspace=workspace,
            job_id=state.spec.job_id,
        )
        shard_root = database.parent / "attempts" / state.spec.job_id / "case_shards_v1"
        if not final_path.is_file() and shard_root.is_dir():
            needs_result_index = True
            break
    result_index = _result_checksum_index(results_root) if needs_result_index else {}
    outcomes: list[dict[str, object]] = []

    for database, state in complete_states:
        try:
            outcome = _prune_one(
                workspace=workspace,
                results_root=results_root,
                database=database,
                state=state,
                result_index=result_index,
                receipt_root=receipt_root,
                dry_run=bool(args.dry_run),
            )
        except Exception as exc:
            outcome = {
                "action": "refused",
                "job_id": state.spec.job_id,
                "queue_database": str(database),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
        outcomes.append(outcome)
        if outcome["action"] not in {"already_pruned", "no_shard_tree"}:
            _emit(outcome)

    forecast = _forecast(
        workspace=workspace,
        results_root=results_root,
        states=states,
        receipt_root=receipt_root,
        minimum_free_gib=float(args.minimum_free_gib),
        target_free_gib=float(args.target_free_gib),
    )
    compression_outcomes: list[dict[str, object]] = []
    if not args.disable_active_long_session_compression:
        compression_outcomes = _protect_active_long_sessions(
            workspace=workspace,
            stores=stores,
            capacity_risk=str(forecast["capacity_protection"]["risk"]),
            receipt_root=maintenance_root / "compression_receipts",
            dry_run=bool(args.dry_run),
        )
        for outcome in compression_outcomes:
            if outcome["action"] not in {
                "compression_already_armed",
                "compression_waiting_for_shard_tree",
            }:
                _emit(outcome)
    forecast["lossless_compression_protection"] = {
        "enabled": not args.disable_active_long_session_compression,
        "eligible_job_kinds": sorted(COMPRESSIBLE_JOB_KINDS),
        "activated_only_at_risk": ["EARLY_RECLAIM", "CRITICAL_RECLAIM"],
        "serial_resource_measurements_excluded": True,
        "receipt_root": str(maintenance_root / "compression_receipts"),
        "current_outcomes": compression_outcomes,
        "forecast_note": (
            "Peak estimates use logical bytes and remain conservative after NTFS "
            "compression; actual allocated-byte savings are not assumed."
        ),
    }
    lifecycle = _artifact_lifecycle(
        workspace=workspace,
        results_root=results_root,
    )
    if not args.dry_run:
        write_json_atomic(maintenance_root / "storage_forecast.json", forecast)
        write_json_atomic(
            maintenance_root / "artifact_lifecycle.json",
            lifecycle,
        )
        write_json_atomic(
            maintenance_root / "last_guardian_pass.json",
            {
                "schema_version": "h2-storage-guardian-pass.v1",
                "completed_at_utc": utc_now(),
                "outcomes": outcomes,
                "compression_outcomes": compression_outcomes,
                "forecast": forecast,
                "artifact_lifecycle_sha256": lifecycle["lifecycle_sha256"],
            },
        )
    return {
        "outcomes": outcomes,
        "compression_outcomes": compression_outcomes,
        "forecast": forecast,
        "lifecycle": lifecycle,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate sealed H2 results and prune only their regenerable "
            "case-shard intermediates while retaining checksum-bound receipts."
        )
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--results-root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--once", action="store_true", help="run one pass and exit")
    mode.add_argument("--follow", action="store_true", help="continue until the program is terminal")
    parser.add_argument("--interval-seconds", type=float, default=300.0)
    parser.add_argument("--minimum-free-gib", type=float, default=35.0)
    parser.add_argument("--target-free-gib", type=float, default=80.0)
    parser.add_argument("--required-drive", default="C:")
    parser.add_argument(
        "--disable-active-long-session-compression",
        action="store_true",
        help=(
            "disable inherited lossless NTFS compression for active non-resource "
            "long-session restart shards when the capacity forecast is at risk"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.interval_seconds < 5:
        parser.error("--interval-seconds must be at least 5")
    workspace = Path(args.workspace).resolve()
    lock_path = workspace / "storage_maintenance" / "guardian.lock"
    with GuardianLock(lock_path):
        while True:
            forecast: Mapping[str, object] | None = None
            try:
                report = run_pass(args)
                forecast = report["forecast"]
                disk = forecast["disk"]
                _emit(
                    {
                        "action": "pass_complete",
                        "dry_run": bool(args.dry_run),
                        "free_gib": disk["free_gib"],
                        "program_status": forecast["program_status"],
                        "estimated_peak_next_single_job_gib": forecast[
                            "estimated_peak_next_single_job_gib"
                        ],
                        "capacity_risk": forecast["capacity_protection"]["risk"],
                    }
                )
            except Exception as exc:
                _emit(
                    {
                        "action": "pass_failed_safe",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                if not args.follow:
                    return 2
            if not args.follow:
                return 0
            if forecast is None:
                time.sleep(min(args.interval_seconds, 60.0))
                continue
            if str(forecast["program_status"]).upper() in TERMINAL_PROGRAM_STATUSES:
                _emit({"action": "guardian_complete", "reason": "program terminal"})
                return 0
            time.sleep(
                _guardian_sleep_interval(
                    args.interval_seconds,
                    str(forecast["capacity_protection"]["risk"]),
                )
            )


if __name__ == "__main__":
    raise SystemExit(main())
