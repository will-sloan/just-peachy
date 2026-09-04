"""Fail-closed H2 analysis, reporting, and compact-package publication.

This module intentionally performs no model inference.  It consumes only the
predeclared controller state and checksum-valid result artifacts.  Analysis is
refused until every prerequisite job is terminal and every required scientific
claim has measured evidence.  Collection uses an explicit allowlist and a
two-pass stage/validate/ZIP flow; it never recursively copies a result tree.
"""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
from itertools import product
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
from typing import Iterable, Mapping, Sequence
import zipfile

from app.full_pipeline_evaluation.metrics import METRIC_CATALOG
from app.full_pipeline_evaluation.results import validate_result_tree
from app.h2_portability.platform_support import two_gib_budget

from .contracts import H2Job, H2ProgramError, ProgramPaths
from .io import (
    canonical_sha256,
    read_json,
    read_jsonl,
    read_yaml,
    sha256_file,
    write_csv_atomic,
    write_json_atomic,
    write_yaml_atomic,
)


ANALYSIS_SCHEMA_VERSION = "h2-final-analysis.v1"
COLLECTION_SCHEMA_VERSION = "h2-final-collection.v1"
MAX_PACKAGE_MEMBER_BYTES = 25 * 1024 * 1024
MAX_PACKAGE_TOTAL_BYTES = 100 * 1024 * 1024

ARM64_PACKAGE_FILES = (
    "README.md",
    "requirements-linux-arm64.txt",
    "requirements-linux-arm64-native-reference.txt",
    "asset_manifest.json",
    "install_linux_arm64.sh",
    "run_h2_service.sh",
    "h2-pipeline.service",
    "Dockerfile.arm64",
    "Dockerfile.arm64.dockerignore",
    "validate_arm64_package.py",
)

REQUIRED_CSV_FILES = (
    "h2_segmentation_frontier.csv",
    "h2_boundary_results.csv",
    "h2_overlap_results.csv",
    "h2_embedding_policy_results.csv",
    "h2_model_sharing_results.csv",
    "h2_embedding_reuse_parity.csv",
    "h2_identity_policy_results.csv",
    "h2_hysteresis_results.csv",
    "h2_session_memory_results.csv",
    "h2_short_turn_results.csv",
    "h2_reentry_results.csv",
    "h2_expiry_results.csv",
    "h2_active_roster_results.csv",
    "h2_mode_comparison.csv",
    "h2_transcript_results.csv",
    "h2_ui_latency_results.csv",
    "h2_resource_results.csv",
    "h2_long_session_results.csv",
    "h2_onnx_parity.csv",
    "h2_final_summary.csv",
    "bootstrap_intervals.csv",
    "failure_inventory.csv",
)

REQUIRED_ANALYSIS_FILES = (
    "h2_configuration_registry.yaml",
    *REQUIRED_CSV_FILES,
    "h2_linux_portability.json",
    "h2_memory_budget.json",
    "historical_evidence_reconciliation.json",
    "analysis_manifest.json",
    "REPORT.md",
    "METRIC_GUIDE.md",
    "REPRODUCIBILITY_MANIFEST.json",
)

SUPPORTING_ANALYSIS_FILES = (
    "cache_inventory.json",
    "result_file_inventory.csv",
    "evidence_table.json",
)

FINAL_CONFIGURATION_IDS = (
    "H2_BASELINE_REFERENCE",
    "H2_KNOWN_ONLY_OPTIMIZED",
    "H2_SESSION_ANONYMOUS_OPTIMIZED",
    "H2_SESSION_MEMORY_OPTIMIZED",
    "H2_PORTABLE_ONNX_FP32",
)

FINAL_DOCUMENTS = (
    "H2_PRODUCT_ARCHITECTURE.md",
    "H2_PRODUCT_MODES.md",
    "H2_SESSION_MEMORY.md",
    "H2_XVF3800_FUTURE_INTERFACE.md",
    "H2_ONNX_EXPORT.md",
    "H2_ARM64_LINUX_HANDOFF.md",
    "H2_2GB_MEMORY_BUDGET.md",
    "H2_DEMO_RUNBOOK.md",
)

EXPERIMENT_FIELDS = (
    "schema_version",
    "evidence_scope",
    "job_id",
    "job_kind",
    "phase_index",
    "split",
    "pipeline_id",
    "mode",
    "configuration_id",
    "source_status",
    "selected",
    "metric_scope",
    "metric_view",
    "metric_subview",
    "metric_id",
    "metric_status",
    "value",
    "numerator",
    "denominator",
    "unit",
    "reason",
    "runtime_tuning_json",
    "source_result_sha256",
    "source_record_json",
)

POLICY_FIELDS = (
    "schema_version",
    "evidence_scope",
    "policy_id",
    "status",
    "selected",
    "metric_scope",
    "metric_id",
    "value",
    "reason",
    "parameters_json",
    "source_job_id",
    "source_result_sha256",
    "source_record_json",
)

PARITY_FIELDS = (
    "schema_version",
    "strategy",
    "component_id",
    "case_id",
    "status",
    "promotion_eligible",
    "measured",
    "metric_id",
    "value",
    "tolerance",
    "passed",
    "reason",
    "source_job_id",
    "source_result_sha256",
    "source_record_json",
)

BOOTSTRAP_FIELDS = (
    "schema_version",
    "job_id",
    "pipeline_id",
    "mode",
    "category",
    "metric_id",
    "status",
    "point_estimate",
    "ci_lower_95",
    "ci_upper_95",
    "reference_speaker_cluster_count",
    "case_count",
    "fallback_case_unit_row_count",
    "bootstrap_repetitions",
    "bootstrap_seed",
    "estimator",
    "resampling_unit",
    "multi_speaker_case_weighting",
)

FAILURE_FIELDS = (
    "schema_version",
    "scope",
    "job_id",
    "configuration_id",
    "mode",
    "artifact",
    "metric_view",
    "metric_subview",
    "metric_id",
    "status",
    "reason",
    "source_result_sha256",
)

RESULT_INVENTORY_FIELDS = (
    "schema_version",
    "job_id",
    "job_kind",
    "configuration_id",
    "state",
    "artifact_kind",
    "path",
    "sha256",
    "bytes",
    "validated",
)

EVIDENCE_LABELS = (
    "Existing work preserved",
    "Non-H2 work gracefully superseded",
    "H2 true streaming runtime",
    "Sherpa Giga integration",
    "Original Sherpa reduced regression",
    "Pyannote segmentation frontier",
    "ReDim shared worker",
    "Embedding reuse parity",
    "Known-only mode",
    "Session-anonymous mode",
    "Enhanced session-memory mode",
    "Hysteresis study",
    "Short-turn inheritance",
    "Warm reacquisition",
    "Expiry/decay",
    "Boundary correction",
    "Overlap study",
    "Transcript structure",
    "Live microphone application",
    "Audio-file simulation",
    "Speaker enrollment",
    "Embedding inspector",
    "ONNX FP32 export",
    "ONNX parity",
    "ARM64 Linux package",
    "2 GB memory analysis",
    "XVF3800 future hooks",
    "Development run",
    "Frozen evaluation",
    "Long-session/resource testing",
    "Final report",
    "Final ZIP",
)

FORBIDDEN_PACKAGE_SUFFIXES = frozenset(
    {
        ".wav",
        ".flac",
        ".mp3",
        ".m4a",
        ".ogg",
        ".onnx",
        ".pt",
        ".pth",
        ".ckpt",
        ".bin",
        ".safetensors",
        ".npy",
        ".npz",
        ".sqlite",
        ".sqlite3",
        ".db",
        ".lock",
        ".tmp",
        ".pem",
        ".key",
        ".pfx",
        ".p12",
    }
)

FORBIDDEN_PACKAGE_PARTS = frozenset(
    {
        "dataset",
        "datasets",
        "generated_audio",
        "recorded_audio",
        "audio_corpus",
        "model_weights",
        "weights",
        "credentials",
        "secrets",
        ".cache",
        "_shared_cache",
        "tmp",
        "temp",
        "__pycache__",
    }
)

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{30,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"(?i)(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|client[_-]?secret)"
        r"\s*[:=]\s*[\"']?(?!false\b|null\b|none\b|redacted\b|not[_ -]?set\b)"
        r"[A-Za-z0-9_./+=-]{8,}"
    ),
)

BIOMETRIC_VECTOR_PATTERN = re.compile(
    r"(?i)[\"\'](?:biometric_vectors?|speaker_embeddings?|embedding_vectors?|"
    r"enrollment_embeddings?|template_vectors?|speaker_vectors?)[\"\']\s*[:=]\s*\["
)


@dataclass(frozen=True)
class ResultArtifact:
    """One validated controller job artifact."""

    job: H2Job
    state_row: Mapping[str, object]
    path: Path | None
    root: Path | None
    artifact_kind: str
    sha256: str | None
    document: Mapping[str, object] | None
    validated: bool


@dataclass(frozen=True)
class PackageMember:
    """One explicitly allowlisted source-to-member mapping."""

    member: str
    source: Path
    category: str


def _json_text(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _write_text_atomic(path: Path, value: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(
        prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _state_rows(
    state: Mapping[str, object], jobs: Sequence[H2Job]
) -> Mapping[str, Mapping[str, object]]:
    raw = state.get("jobs")
    if not isinstance(raw, Mapping):
        raise H2ProgramError("H2 program state lacks a jobs mapping")
    expected = {job.job_id for job in jobs}
    if set(map(str, raw)) != expected:
        raise H2ProgramError("H2 program state job membership differs from manifest")
    rows: dict[str, Mapping[str, object]] = {}
    for job_id in sorted(expected):
        row = raw.get(job_id)
        if not isinstance(row, Mapping):
            raise H2ProgramError(f"invalid H2 program job row: {job_id}")
        rows[job_id] = row
    return rows


def resolve_runtime_result_root(result_path: Path | str) -> Path:
    """Resolve a controller result path that may be a file or a directory.

    Runtime result trees are directories.  Science, reliability, and
    portability handlers publish a primary ``job_result.json`` file and keep
    supporting artifacts beside it.  Returning the containing directory for a
    file keeps both shapes safe without guessing from a path suffix.
    """

    path = Path(result_path).expanduser().resolve(strict=True)
    if path.is_dir():
        return path
    if path.is_file():
        return path.parent
    raise H2ProgramError(f"result path is neither a file nor directory: {path}")


def _validate_relative_artifact(root: Path, relative: str) -> Path:
    logical = PurePosixPath(relative)
    if (
        logical.is_absolute()
        or not logical.parts
        or any(part in {"", ".", ".."} for part in logical.parts)
    ):
        raise H2ProgramError(f"artifact manifest path is unsafe: {relative!r}")
    target = (root / Path(*logical.parts)).resolve(strict=True)
    try:
        target.relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise H2ProgramError(
            f"artifact manifest path escapes its root: {relative}"
        ) from exc
    if not target.is_file():
        raise H2ProgramError(f"artifact manifest member is not a file: {target}")
    return target


def _validate_sidecar_checksums(root: Path) -> None:
    path = root / "checksums.json"
    if not path.is_file():
        return
    document = read_json(path)
    entries = document.get("entries")
    if not isinstance(entries, Mapping):
        return
    expected: dict[str, str] = {}
    for raw_name, raw_value in entries.items():
        name = str(raw_name).replace("\\", "/")
        source = _validate_relative_artifact(root, name)
        if isinstance(raw_value, Mapping):
            expected_sha = raw_value.get("sha256")
        else:
            expected_sha = raw_value
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise H2ProgramError(f"invalid sidecar checksum entry: {name}")
        observed = sha256_file(source)
        if observed != expected_sha:
            raise H2ProgramError(f"sidecar checksum differs: {source}")
        expected[name] = expected_sha
    actual_names = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item.name != "checksums.json" and ".tmp." not in item.name
    }
    if set(expected) != actual_names:
        raise H2ProgramError(
            f"sidecar checksum inventory differs at {root}: "
            f"missing={sorted(actual_names - set(expected))[:3]}, "
            f"extra={sorted(set(expected) - actual_names)[:3]}"
        )


def _validate_science_artifact_manifest(
    root: Path, document: Mapping[str, object]
) -> None:
    entries = document.get("artifact_manifest")
    if entries is None:
        return
    if not isinstance(entries, list):
        raise H2ProgramError("science artifact manifest is not a list")
    observed_names: set[str] = set()
    for raw in entries:
        if not isinstance(raw, Mapping):
            raise H2ProgramError("science artifact manifest row is invalid")
        name = str(raw.get("path") or "")
        source = _validate_relative_artifact(root, name)
        expected = raw.get("sha256")
        if expected != sha256_file(source):
            raise H2ProgramError(f"science artifact checksum differs: {source}")
        observed_names.add(name)
        if source.suffix.casefold() == ".csv" and raw.get("row_count") is not None:
            with source.open("r", encoding="utf-8-sig", newline="") as stream:
                count = sum(1 for _ in csv.DictReader(stream))
            if count != int(raw["row_count"]):
                raise H2ProgramError(f"science artifact row count differs: {source}")
    if len(observed_names) != len(entries):
        raise H2ProgramError("science artifact manifest contains duplicate paths")


def _read_primary_document(path: Path) -> Mapping[str, object] | None:
    if not path.is_file() or path.suffix.casefold() != ".json":
        return None
    return read_json(path)


def _validate_completed_artifact(
    job: H2Job, row: Mapping[str, object]
) -> ResultArtifact:
    raw_path = row.get("result_path")
    expected_sha = row.get("result_sha256")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise H2ProgramError(f"completed job lacks result_path: {job.job_id}")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise H2ProgramError(f"completed job lacks a SHA-256 identity: {job.job_id}")
    path = Path(raw_path).expanduser().resolve(strict=True)
    if path.is_file():
        observed_sha = sha256_file(path)
        if observed_sha != expected_sha:
            raise H2ProgramError(f"completed job result checksum differs: {job.job_id}")
        root = resolve_runtime_result_root(path)
        document = _read_primary_document(path)
        if document is not None:
            status = str(document.get("status") or "")
            if status.upper().startswith("FAILED") or status.upper() in {
                "FAIL",
                "STOPPED",
                "PARTIAL",
            }:
                raise H2ProgramError(
                    f"completed job primary artifact reports {status}: {job.job_id}"
                )
            _validate_science_artifact_manifest(root, document)
        _validate_sidecar_checksums(root)
        return ResultArtifact(
            job=job,
            state_row=row,
            path=path,
            root=root,
            artifact_kind="file",
            sha256=expected_sha,
            document=document,
            validated=True,
        )
    if not path.is_dir():
        raise H2ProgramError(f"completed result path is invalid: {path}")
    report = validate_result_tree(path)
    if not report.reusable:
        reasons = "; ".join(
            f"{issue.code}:{issue.logical_path}" for issue in report.issues[:5]
        )
        raise H2ProgramError(
            f"completed runtime result is not reusable ({job.job_id}): {reasons}"
        )
    checksum_path = path / "checksums.json"
    if not checksum_path.is_file() or sha256_file(checksum_path) != expected_sha:
        raise H2ProgramError(f"runtime result identity differs: {job.job_id}")
    return ResultArtifact(
        job=job,
        state_row=row,
        path=path,
        root=path,
        artifact_kind="directory",
        sha256=expected_sha,
        document=read_json(path / "run.json"),
        validated=True,
    )


def validate_prerequisite_artifacts(
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> Mapping[str, ResultArtifact]:
    """Validate every pre-analysis/pre-collection job and return its catalog."""

    rows = _state_rows(state, jobs)
    artifacts: dict[str, ResultArtifact] = {}
    for job in jobs:
        if job.job_kind in {"analysis", "collection"}:
            continue
        row = rows[job.job_id]
        status = str(row.get("state") or "")
        if status == "SUPERSEDED":
            if not job.optional:
                raise H2ProgramError(
                    f"mandatory job was superseded instead of completed: {job.job_id}"
                )
            artifacts[job.job_id] = ResultArtifact(
                job=job,
                state_row=row,
                path=None,
                root=None,
                artifact_kind="superseded",
                sha256=None,
                document=None,
                validated=True,
            )
            continue
        if status != "COMPLETE":
            raise H2ProgramError(
                f"H2 analysis requires complete evidence; {job.job_id} is {status or 'MISSING'}"
            )
        artifacts[job.job_id] = _validate_completed_artifact(job, row)
    return artifacts


def _artifact_for_kind(
    artifacts: Mapping[str, ResultArtifact], kind: str
) -> tuple[ResultArtifact, ...]:
    return tuple(
        value
        for value in artifacts.values()
        if value.job.job_kind == kind and value.artifact_kind != "superseded"
    )


def _artifact_for_configuration(
    artifacts: Mapping[str, ResultArtifact], configuration_id: str
) -> ResultArtifact | None:
    return next(
        (
            value
            for value in artifacts.values()
            if value.job.configuration_id == configuration_id
            and value.artifact_kind != "superseded"
        ),
        None,
    )


def _read_csv_rows(path: Path) -> tuple[dict[str, object], ...]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as stream:
        return tuple(dict(row) for row in csv.DictReader(stream))


def _read_jsonl_any(path: Path) -> tuple[dict[str, object], ...]:
    source = Path(path)
    if source.suffix.casefold() == ".gz":
        rows: list[dict[str, object]] = []
        with gzip.open(source, "rt", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
        return tuple(rows)
    return read_jsonl(source)


def _supporting_rows(
    artifact: ResultArtifact, filename: str
) -> tuple[dict[str, object], ...]:
    if artifact.root is None:
        return ()
    path = artifact.root / filename
    if not path.is_file():
        return ()
    if path.suffix.casefold() == ".csv":
        return _read_csv_rows(path)
    if path.suffix.casefold() in {".jsonl", ".gz"}:
        return _read_jsonl_any(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, list):
        return tuple(dict(row) for row in value if isinstance(row, Mapping))
    if isinstance(value, Mapping) and isinstance(value.get("rows"), list):
        return tuple(dict(row) for row in value["rows"] if isinstance(row, Mapping))
    return ()


def _metric_scope(subview_id: str) -> str:
    value = subview_id.casefold()
    if value in {"overall", "all", "global", "end_to_end", "end-to-end"}:
        return "END_TO_END"
    return f"CONDITIONAL:{subview_id}"


def _metric_rows(artifact: ResultArtifact) -> tuple[dict[str, object], ...]:
    if artifact.root is None:
        return ()
    rows: list[dict[str, object]] = []
    for view in ("asr", "diarization", "identity", "streaming", "resources"):
        path = artifact.root / "metrics" / f"{view}.json"
        if not path.is_file():
            continue
        document = read_json(path)
        subviews = document.get("subviews")
        if not isinstance(subviews, Mapping):
            continue
        for subview_id, raw_subview in sorted(
            subviews.items(), key=lambda item: str(item[0])
        ):
            if not isinstance(raw_subview, Mapping):
                continue
            metrics = raw_subview.get("metrics")
            if not isinstance(metrics, Mapping):
                continue
            for metric_id, raw_metric in sorted(
                metrics.items(), key=lambda item: str(item[0])
            ):
                if not isinstance(raw_metric, Mapping):
                    continue
                definition = METRIC_CATALOG.get(str(metric_id))
                rows.append(
                    {
                        "schema_version": "h2-normalized-metric-row.v1",
                        "evidence_scope": "MEASURED_RUNTIME",
                        "job_id": artifact.job.job_id,
                        "job_kind": artifact.job.job_kind,
                        "phase_index": artifact.job.phase_index,
                        "split": artifact.job.split,
                        "pipeline_id": artifact.job.pipeline_id,
                        "mode": artifact.job.mode,
                        "configuration_id": artifact.job.configuration_id,
                        "source_status": artifact.state_row.get("state"),
                        "selected": False,
                        "metric_scope": _metric_scope(str(subview_id)),
                        "metric_view": view,
                        "metric_subview": str(subview_id),
                        "metric_id": str(metric_id),
                        "metric_status": raw_metric.get("status"),
                        "value": raw_metric.get("value"),
                        "numerator": raw_metric.get("numerator"),
                        "denominator": raw_metric.get("denominator"),
                        "unit": definition.unit if definition is not None else None,
                        "reason": raw_metric.get("reason"),
                        "runtime_tuning_json": _json_text(
                            dict(artifact.job.runtime_tuning)
                        ),
                        "source_result_sha256": artifact.sha256,
                        "source_record_json": _json_text(dict(raw_metric)),
                    }
                )
    return tuple(rows)


def _all_metric_rows(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for artifact in sorted(artifacts.values(), key=lambda item: item.job.job_id):
        rows.extend(_metric_rows(artifact))
    return tuple(rows)


def _selected_configurations(
    state: Mapping[str, object], artifacts: Mapping[str, ResultArtifact]
) -> set[str]:
    selected: set[str] = set()
    promotions = state.get("promotions")
    if isinstance(promotions, Mapping):
        for raw in promotions.values():
            if not isinstance(raw, Mapping):
                continue
            selected.update(map(str, raw.get("selected_candidates") or ()))
    axes = state.get("axis_selections")
    if isinstance(axes, Mapping):
        for raw in axes.values():
            if not isinstance(raw, Mapping):
                continue
            selected.update(map(str, raw.get("selected_candidates") or ()))
    for artifact in artifacts.values():
        document = artifact.document
        if not isinstance(document, Mapping):
            continue
        if document.get("promotion_eligible") is True and document.get(
            "selected_runtime_tuning"
        ):
            selected.add(artifact.job.configuration_id)
    return selected


def _configuration_is_selected(configuration_id: str, selected: set[str]) -> bool:
    """Match successive-halving tier IDs to their checksum-bound base choice."""

    candidate = configuration_id
    for suffix in ("_SMALL", "_MEDIUM", "_FULL"):
        if candidate.endswith(suffix):
            candidate = candidate[: -len(suffix)]
            break
    return configuration_id in selected or candidate in selected


def _experiment_rows(
    artifacts: Iterable[ResultArtifact],
    *,
    selected: set[str],
    default_scope: str,
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for artifact in sorted(artifacts, key=lambda item: item.job.job_id):
        metrics = _metric_rows(artifact)
        if metrics:
            for raw in metrics:
                row = dict(raw)
                row["evidence_scope"] = default_scope
                row["selected"] = _configuration_is_selected(
                    artifact.job.configuration_id, selected
                )
                rows.append(row)
            continue
        document = artifact.document or {}
        status = document.get("status") or artifact.state_row.get("state")
        rows.append(
            {
                "schema_version": "h2-normalized-experiment-row.v1",
                "evidence_scope": default_scope,
                "job_id": artifact.job.job_id,
                "job_kind": artifact.job.job_kind,
                "phase_index": artifact.job.phase_index,
                "split": artifact.job.split,
                "pipeline_id": artifact.job.pipeline_id,
                "mode": artifact.job.mode,
                "configuration_id": artifact.job.configuration_id,
                "source_status": status,
                "selected": _configuration_is_selected(
                    artifact.job.configuration_id, selected
                ),
                "metric_scope": "JOB_LEVEL",
                "metric_view": "",
                "metric_subview": "",
                "metric_id": "job_status",
                "metric_status": status,
                "value": None,
                "numerator": None,
                "denominator": None,
                "unit": None,
                "reason": document.get("reason") or document.get("error"),
                "runtime_tuning_json": _json_text(dict(artifact.job.runtime_tuning)),
                "source_result_sha256": artifact.sha256,
                "source_record_json": _json_text(dict(document)),
            }
        )
    return tuple(rows)


def _coerce_scalar(value: object) -> object:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text == "":
        return None
    lowered = text.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"none", "null", "nan"}:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            return value


def _policy_rows(
    artifact: ResultArtifact,
    filenames: Sequence[str],
    *,
    selected_record: Mapping[str, object] | None = None,
    evidence_scope: str,
    parameter_keys: Sequence[str],
) -> tuple[dict[str, object], ...]:
    source_rows: list[dict[str, object]] = []
    for filename in filenames:
        source_rows.extend(_supporting_rows(artifact, filename))
    selected_parameters = {
        key: _coerce_scalar(selected_record[key])
        for key in parameter_keys
        if isinstance(selected_record, Mapping) and key in selected_record
    }
    output: list[dict[str, object]] = []
    context = {
        "schema_version",
        "status",
        "reason",
        "outcome_sha256",
        "source_bindings",
        "metrics",
        "metrics_computed",
        "synthetic_metrics_emitted",
        "promotion_eligible",
        "development_only_selection",
        "evaluation_material_inspected",
        *parameter_keys,
    }
    for ordinal, raw in enumerate(source_rows, start=1):
        row = {str(key): _coerce_scalar(value) for key, value in raw.items()}
        parameters = {key: row.get(key) for key in parameter_keys if key in row}
        # The selected record normally contains metrics in addition to the
        # tuning axes.  Comparing JSON substrings is therefore both brittle and
        # incorrect: ``{"hysteresis":0.02}`` is not a substring of a larger
        # canonical object when other keys sort between the braces.  Bind the
        # row to the selected axis values directly.
        is_selected = bool(selected_parameters) and all(
            key in parameters and parameters[key] == value
            for key, value in selected_parameters.items()
        )
        numeric = [
            (key, value)
            for key, value in sorted(row.items())
            if key not in context
            and isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        ]
        if not numeric:
            numeric = [
                (
                    (
                        "capability_outcome"
                        if row.get("cell_id")
                        or str(row.get("status") or "").upper()
                        == "UNSUPPORTED_CAPABILITY"
                        else "record"
                    ),
                    None,
                )
            ]
        semantic_policy_id = (
            row.get("cell_id")
            or row.get("hysteresis_policy")
            or row.get("memory_level")
            or row.get("short_turn_policy")
        )
        for metric_id, value in numeric:
            output.append(
                {
                    "schema_version": "h2-normalized-policy-row.v1",
                    "evidence_scope": evidence_scope,
                    "policy_id": (
                        str(semantic_policy_id)
                        if semantic_policy_id
                        else f"{artifact.job.configuration_id}:{ordinal}"
                    ),
                    "status": row.get("status") or "MEASURED",
                    "selected": is_selected,
                    "metric_scope": "DEVELOPMENT_SELECTION",
                    "metric_id": metric_id,
                    "value": value,
                    "reason": row.get("reason"),
                    "parameters_json": _json_text(parameters),
                    "source_job_id": artifact.job.job_id,
                    "source_result_sha256": artifact.sha256,
                    "source_record_json": _json_text(row),
                }
            )
    if not output:
        document = artifact.document or {}
        output.append(
            {
                "schema_version": "h2-normalized-policy-row.v1",
                "evidence_scope": evidence_scope,
                "policy_id": artifact.job.configuration_id,
                "status": "NOT_RUN",
                "selected": False,
                "metric_scope": "JOB_LEVEL",
                "metric_id": "record",
                "value": None,
                "reason": "declared supporting table was not produced",
                "parameters_json": "{}",
                "source_job_id": artifact.job.job_id,
                "source_result_sha256": artifact.sha256,
                "source_record_json": _json_text(dict(document)),
            }
        )
    return tuple(output)


def _walk_items(value: object, prefix: str = "") -> Iterable[tuple[str, object]]:
    if isinstance(value, Mapping):
        for raw_key, child in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            yield path, child
            yield from _walk_items(child, path)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for index, child in enumerate(value):
            path = f"{prefix}[{index}]"
            yield path, child
            yield from _walk_items(child, path)


def _normal_key(path: str) -> str:
    value = path.rsplit(".", 1)[-1]
    value = value.split("[", 1)[0]
    return re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")


def _document_values(
    artifact: ResultArtifact,
    *,
    include_supporting_json: bool = True,
) -> tuple[tuple[str, object], ...]:
    values: list[tuple[str, object]] = []
    if artifact.document is not None:
        values.extend(_walk_items(artifact.document))
    if include_supporting_json and artifact.root is not None:
        for path in sorted(artifact.root.glob("*.json")):
            if artifact.path is not None and path.resolve() == artifact.path.resolve():
                continue
            try:
                document = read_json(path)
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            values.extend(
                (f"{path.name}.{key}", value) for key, value in _walk_items(document)
            )
        for path in sorted(artifact.root.glob("*.csv")):
            try:
                rows = _read_csv_rows(path)
            except (OSError, ValueError, csv.Error):
                continue
            for index, row in enumerate(rows):
                values.extend(
                    (f"{path.name}[{index}].{key}", _coerce_scalar(value))
                    for key, value in _walk_items(row)
                )
    return tuple(values)


def _explicit_true(artifact: ResultArtifact, keys: Iterable[str]) -> bool:
    expected = {re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_") for key in keys}
    return any(
        _normal_key(path) in expected and value is True
        for path, value in _document_values(artifact)
    )


def _explicit_value(artifact: ResultArtifact, keys: Iterable[str]) -> object | None:
    expected = {re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_") for key in keys}
    for path, value in _document_values(artifact):
        if _normal_key(path) in expected and value is not None:
            return value
    return None


def _parity_rows(
    artifacts: Sequence[ResultArtifact], *, portability: bool
) -> tuple[dict[str, object], ...]:
    output: list[dict[str, object]] = []
    preferred_metric_tokens = (
        "cosine",
        "absolute",
        "relative",
        "score",
        "top1",
        "top2",
        "margin",
        "decision",
        "cluster",
        "transcript",
        "rttm",
        "event",
        "boundary",
        "activity",
    )
    for artifact in artifacts:
        document = dict(artifact.document or {})
        artifact_passed = _explicit_true(
            artifact,
            (
                "parity_passed",
                "required_parity_outputs_passed",
                "full_live_pipeline_parity_passed",
                "full_pipeline_e2e_parity_passed",
                "promotion_eligible",
            ),
        )
        supporting: list[dict[str, object]] = []
        if artifact.root is not None:
            for path in sorted(artifact.root.glob("*parity*.csv")):
                supporting.extend(_read_csv_rows(path))
        source_records = supporting or [document]
        for ordinal, raw in enumerate(source_records, start=1):
            flattened = list(_walk_items(raw))
            metrics = [
                (path, value)
                for path, value in flattened
                if any(token in _normal_key(path) for token in preferred_metric_tokens)
                and isinstance(value, (bool, int, float, str))
            ]
            if not metrics:
                metrics = [("record", None)]
            strategy = str(
                raw.get("strategy")
                or document.get("candidate_strategy")
                or artifact.job.configuration_id
            )
            for path, value in metrics:
                key = _normal_key(path)
                tolerance = (
                    raw["tolerance"]
                    if "tolerance" in raw
                    else raw.get(f"{key}_tolerance")
                )
                passed = (
                    raw["passed"]
                    if "passed" in raw
                    else (
                        raw[f"{key}_passed"]
                        if f"{key}_passed" in raw
                        else artifact_passed
                    )
                )
                output.append(
                    {
                        "schema_version": "h2-normalized-parity-row.v1",
                        "strategy": strategy,
                        "component_id": (
                            raw.get("component_id")
                            or document.get("component_id")
                            or "END_TO_END"
                            if portability
                            else "ReDimNet2-B2"
                        ),
                        "case_id": raw.get("case_id") or ordinal,
                        "status": raw.get("status") or document.get("status"),
                        "promotion_eligible": document.get("promotion_eligible"),
                        "measured": _explicit_true(
                            artifact,
                            (
                                "bounded_exact_parity_executed",
                                "parity_measured",
                                "full_pipeline_parity_measured",
                                "full_live_pipeline_parity_measured",
                            ),
                        ),
                        "metric_id": key,
                        "value": value,
                        "tolerance": tolerance,
                        "passed": passed,
                        "reason": raw.get("reason") or document.get("reason"),
                        "source_job_id": artifact.job.job_id,
                        "source_result_sha256": artifact.sha256,
                        "source_record_json": _json_text(raw),
                    }
                )
    return tuple(output)


def _artifact_status_passes(artifact: ResultArtifact) -> bool:
    document = artifact.document
    if not isinstance(document, Mapping):
        return artifact.validated
    status = str(document.get("status") or "").upper()
    return status in {
        "COMPLETE",
        "PASS",
        "PARITY_PASS",
        "E2E_CONTRACT_PARITY_PASS",
        "DIAGNOSTIC_PASS",
        "PREPARED",
    }


def _required_parity_keys_present(
    artifact: ResultArtifact, keys: Sequence[str]
) -> bool:
    observed = {
        _normal_key(path)
        for path, value in _document_values(artifact)
        if value is not None
    }
    return all(
        any(required == key or required in key or key in required for key in observed)
        for required in keys
    )


def _embedding_reuse_parity_complete(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[bool, str]:
    candidates = _artifact_for_kind(artifacts, "embedding_reuse_parity")
    required_strategies = {
        "R3_EXACT_WINDOW_EMBEDDING_REUSE",
        "R4_HYBRID_REUSE_WITH_IDENTITY_AGGREGATION",
    }
    by_strategy = {value.job.configuration_id: value for value in candidates}
    if set(by_strategy) != required_strategies:
        return False, "both predeclared R3 and R4 parity jobs are required"
    required_outputs = (
        "embedding_cosine_agreement",
        "maximum_absolute_error",
        "score_agreement",
        "top1_agreement",
        "top2_agreement",
        "margin_agreement",
        "known_unknown_decision_agreement",
        "cluster_assignment_agreement",
        "transcript_label_agreement",
        "event_sequence_semantic_agreement",
    )
    failures: list[str] = []
    for strategy in sorted(required_strategies):
        artifact = by_strategy[strategy]
        document = artifact.document if isinstance(artifact.document, Mapping) else {}
        measured = _explicit_true(
            artifact,
            (
                "bounded_exact_parity_executed",
                "parity_measured",
                "required_parity_outputs_measured",
            ),
        )
        fields = _required_parity_keys_present(artifact, required_outputs)
        status = str(document.get("status") or "").upper()
        candidate_qualified = document.get("candidate_qualified")
        parity_passed = document.get("parity_passed")
        terminal = (
            status == "COMPLETE"
            and candidate_qualified is True
            and parity_passed is True
        ) or (
            status == "GATED_NOT_PROMOTED"
            and candidate_qualified is False
        )
        if not (measured and fields and terminal):
            failures.append(
                f"{strategy}: measured={measured}, required_outputs={fields}, "
                f"terminal_scientific_outcome={terminal}, status={status}"
            )
    if failures:
        return False, "; ".join(failures)
    return (
        True,
        "R3 and R4 measured all required agreement outputs; only qualified "
        "strategies were eligible for promotion",
    )


def _onnx_end_to_end_parity_complete(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[bool, str]:
    values = _artifact_for_kind(artifacts, "onnx_parity")
    if len(values) != 1:
        return False, f"expected one ONNX parity job, observed {len(values)}"
    artifact = values[0]
    measured = _explicit_true(
        artifact,
        (
            "full_live_pipeline_parity_measured",
            "full_pipeline_e2e_parity_measured",
            "full_pipeline_parity_measured",
            "fresh_factory_pair_executed",
            "fresh_native_and_onnx_runs_executed",
        ),
    )
    passed = _explicit_true(
        artifact,
        (
            "full_live_pipeline_parity_passed",
            "full_pipeline_e2e_parity_passed",
            "full_pipeline_parity_passed",
            "fresh_factory_pair_passed",
            "end_to_end_parity_passed",
        ),
    )
    if not passed:
        for path, value in _document_values(artifact):
            normalized_path = path.casefold()
            normalized_value = str(value).upper()
            if any(
                token in normalized_path
                for token in ("e2e", "end_to_end", "full_pipeline")
            ) and normalized_value in {
                "PASS",
                "PARITY_PASS",
                "E2E_CONTRACT_PARITY_PASS",
            }:
                passed = True
                break
    required_outputs = (
        "transcript_agreement",
        "rttm_agreement",
        "cluster_agreement",
        "identity_agreement",
        "event_sequence_agreement",
    )
    fields = _required_parity_keys_present(artifact, required_outputs)
    complete = measured and passed and fields and _artifact_status_passes(artifact)
    return complete, (
        "fresh native-vs-ONNX full-pipeline parity measured and passed"
        if complete
        else (
            f"measured={measured}, passed={passed}, required_outputs={fields}, "
            f"status_pass={_artifact_status_passes(artifact)}"
        )
    )


def _non_h2_supersession_evidence(paths: ProgramPaths) -> tuple[bool, str]:
    candidates = (
        paths.evaluation_root
        / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1/stop_request.json",
        paths.evaluation_root
        / "automated_runs/full_pipeline_prompts_4_8_eight_day_v1/program_state.json",
        paths.evaluation_root / "docs/full_pipeline/PROGRAM_HANDOFF.md",
    )
    for path in candidates:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            continue
        normalized = text.casefold()
        if (
            "superseded_by_h2_product_decision" in normalized
            or "superseded by h2 product decision" in normalized
        ):
            return True, f"explicit supersession record: {path}"
    return False, "no checksum-readable SUPERSEDED_BY_H2_PRODUCT_DECISION record"


def _preservation_evidence(artifacts: Mapping[str, ResultArtifact]) -> tuple[bool, str]:
    values = _artifact_for_kind(artifacts, "evidence_audit")
    if len(values) != 1 or not isinstance(values[0].document, Mapping):
        return False, "exactly one completed evidence audit is required"
    document = values[0].document
    evidence = document.get("evidence")
    rows = (
        [row for row in evidence if isinstance(row, Mapping)]
        if isinstance(evidence, list)
        else []
    )
    existing = sum(row.get("exists") is True for row in rows)
    valid = (
        document.get("prior_evidence_modified") is False
        and existing >= 2
        and _artifact_status_passes(values[0])
    )
    return valid, (
        f"prior_evidence_modified={document.get('prior_evidence_modified')}; "
        f"checksum-inventoried existing sources={existing}/{len(rows)}"
    )


def _complete_configurations(
    artifacts: Mapping[str, ResultArtifact], prefix: str
) -> tuple[ResultArtifact, ...]:
    return tuple(
        value
        for value in artifacts.values()
        if value.artifact_kind != "superseded"
        and value.job.configuration_id.startswith(prefix)
    )


def _explicit_overlap_policies(artifacts: Mapping[str, ResultArtifact]) -> set[str]:
    expected = {
        "INCLUDE_PREDICTED_OVERLAP",
        "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
        "DEFER_IDENTITY_UNTIL_NON_OVERLAP",
        "DISPLAY_OVERLAPPING_SPEAKERS_WHEN_AMBIGUOUS",
    }
    observed: set[str] = set()
    for artifact in artifacts.values():
        if artifact.job.configuration_id in expected:
            observed.add(artifact.job.configuration_id)
        for _path, value in _document_values(artifact):
            if isinstance(value, str) and value in expected:
                observed.add(value)
    return observed


def _measured_overlap_policies(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[set[str], dict[str, list[str]]]:
    """Return A/B policies only when their declared outcome panel is measured."""

    required_metrics = {
        "miss_rate",
        "stable_name_latency_sec",
        "merge_contamination_rate",
        "wrong_known_time_sec",
        "stranger_false_known_time_sec",
        "identity_merge_count",
        "word_speaker_label_accuracy",
        "generic_known_time_sec",
    }
    policies = {
        "INCLUDE_PREDICTED_OVERLAP",
        "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
    }
    complete: set[str] = set()
    missing: dict[str, list[str]] = {}
    for policy in sorted(policies):
        values = [
            artifact
            for artifact in artifacts.values()
            if artifact.job.configuration_id == policy
            and artifact.artifact_kind != "superseded"
        ]
        computed = {
            str(row.get("metric_id"))
            for artifact in values
            for row in _metric_rows(artifact)
            if str(row.get("metric_status") or "").casefold() == "computed"
            and isinstance(row.get("value"), (int, float))
            and not isinstance(row.get("value"), bool)
        }
        absent = sorted(required_metrics - computed)
        if len(values) == 1 and not absent:
            complete.add(policy)
        else:
            missing[policy] = absent or ["exactly_one_checksum_valid_result"]
    return complete, missing


def _overlap_capability_contract(
    paths: ProgramPaths,
) -> tuple[set[str], str]:
    """Return protocol-bound unsupported overlap policies and provenance."""

    if not paths.protocol_path.is_file():
        return set(), "protocol manifest is missing"
    protocol = read_json(paths.protocol_path)
    unsigned = dict(protocol)
    observed_sha = unsigned.pop("protocol_sha256", None)
    unsigned.pop("protocol_id", None)
    if observed_sha != canonical_sha256(unsigned):
        return set(), "protocol manifest checksum is invalid"
    development = protocol.get("development_search")
    support = (
        development.get("overlap_runtime_support")
        if isinstance(development, Mapping)
        else None
    )
    if not isinstance(support, Mapping):
        return set(), "protocol lacks overlap runtime capability records"
    gated = set(map(str, support.get("gated_not_scheduled_until_connected") or ()))
    return gated, f"protocol_sha256={observed_sha}"


def _implementation_exists(paths: ProgramPaths, *relative_paths: str) -> bool:
    return all((paths.evaluation_root / value).is_file() for value in relative_paths)


def _preserved_targeted_test_evidence(
    paths: ProgramPaths,
    artifacts: Mapping[str, ResultArtifact],
    *,
    capability_id: str,
    required_test_suffixes: Sequence[str],
    required_sources: Sequence[str],
) -> tuple[bool, str]:
    """Validate the scheduled current app receipt, with legacy fallback."""

    current = _artifact_for_kind(artifacts, "app_validation")
    if current:
        if len(current) != 1 or not isinstance(current[0].document, Mapping):
            return False, "exactly one current app-validation receipt is required"
        artifact = current[0]
        document = artifact.document
        validation = document.get("validation")
        capabilities = document.get("capabilities")
        capability = (
            capabilities.get(capability_id)
            if isinstance(capabilities, Mapping)
            else None
        )
        test_hashes = document.get("test_hashes")
        source_hashes = document.get("source_hashes")
        if (
            document.get("schema_version") != "h2-app-validation-result.v1"
            or document.get("status") != "COMPLETE"
            or document.get("model_free") is not True
            or document.get("neural_inference_performed") is not False
            or document.get("physical_microphone_performance_claimed") is not False
            or document.get("controlled_or_mocked_device_behavior_only") is not True
            or not isinstance(validation, Mapping)
            or validation.get("status") != "PASS"
            or validation.get("failed_count") != 0
            or not isinstance(validation.get("passed_count"), int)
            or int(validation["passed_count"]) < 1
            or validation.get("python_compile_passed") is not True
            or validation.get("ruff_check_passed") is not True
            or not isinstance(capability, Mapping)
            or capability.get("status") != "PASS"
            or not isinstance(test_hashes, Mapping)
            or not isinstance(source_hashes, Mapping)
        ):
            return False, f"current app-validation contract differs: {capability_id}"
        if (
            document.get("job_id") != artifact.job.job_id
            or document.get("job_identity_sha256") != artifact.job.identity_sha256
        ):
            return False, "current app-validation job binding differs"
        if not paths.protocol_path.is_file():
            return False, "current app-validation protocol manifest is missing"
        protocol = read_json(paths.protocol_path)
        if document.get("protocol_id") != protocol.get("protocol_id") or document.get(
            "protocol_sha256"
        ) != protocol.get("protocol_sha256"):
            return False, "current app-validation protocol binding differs"
        implementation_path = paths.workspace / "runtime_implementation_identity.json"
        if not implementation_path.is_file():
            return False, "current runtime implementation identity is missing"
        implementation = read_json(implementation_path)
        if document.get("runtime_implementation_identity_sha256") != implementation.get(
            "identity_sha256"
        ):
            return False, "current app-validation runtime identity differs"
        handler_logical = str(document.get("handler_source_path") or "").replace(
            "\\", "/"
        )
        if handler_logical != "app/h2_product_program/controller.py":
            return False, "current app-validation handler path differs"
        handler_path = paths.evaluation_root / handler_logical
        if not handler_path.is_file() or document.get(
            "handler_source_sha256"
        ) != sha256_file(handler_path):
            return False, "current app-validation handler checksum differs"
        declared_tests = {
            str(value).replace("\\", "/")
            for value in capability.get("test_paths") or ()
        }
        declared_sources = {
            str(value).replace("\\", "/")
            for value in capability.get("source_paths") or ()
        }
        matched_tests: list[str] = []
        for suffix in required_test_suffixes:
            logical = next(
                (
                    str(name).replace("\\", "/")
                    for name in test_hashes
                    if str(name).replace("\\", "/").endswith(suffix.replace("\\", "/"))
                ),
                None,
            )
            if logical is None or logical not in declared_tests:
                return False, f"current app receipt lacks test: {suffix}"
            source = (paths.evaluation_root / logical).resolve(strict=False)
            expected = test_hashes.get(logical)
            if expected is None:
                expected = test_hashes.get(logical.replace("/", "\\"))
            if (
                not source.is_file()
                or not isinstance(expected, str)
                or sha256_file(source) != expected.casefold()
            ):
                return False, f"current app test checksum differs: {logical}"
            matched_tests.append(logical)
        matched_sources: list[str] = []
        for logical in required_sources:
            normalized = logical.replace("\\", "/")
            if normalized not in declared_sources:
                return False, f"current app receipt lacks source: {logical}"
            expected = source_hashes.get(normalized)
            if expected is None:
                expected = source_hashes.get(normalized.replace("/", "\\"))
            source = (paths.evaluation_root / normalized).resolve(strict=False)
            if (
                not source.is_file()
                or not isinstance(expected, str)
                or sha256_file(source) != expected.casefold()
            ):
                return False, f"current app source checksum differs: {logical}"
            matched_sources.append(normalized)
        return True, (
            f"current checksum-bound {capability_id} validation PASS; "
            f"tests={len(matched_tests)}, sources={len(matched_sources)}, "
            f"passed={validation['passed_count']}, failed=0, model_free=true"
        )

    state_path = paths.evaluation_root / "runs/full_pipeline_program/PROGRAM_STATE.json"
    if not state_path.is_file():
        return False, "preserved full-pipeline PROGRAM_STATE.json is missing"
    document = read_json(state_path)
    artifacts = document.get("artifacts")
    receipt = (
        artifacts.get("common_demo_targeted_tests")
        if isinstance(artifacts, Mapping)
        else None
    )
    path_hashes = receipt.get("paths") if isinstance(receipt, Mapping) else None
    if not isinstance(path_hashes, Mapping):
        return False, "preserved targeted-test checksum map is missing"
    matched: list[str] = []
    for suffix in required_test_suffixes:
        logical = next(
            (
                str(name)
                for name in path_hashes
                if str(name).replace("\\", "/").endswith(suffix.replace("\\", "/"))
            ),
            None,
        )
        if logical is None:
            return False, f"targeted-test receipt lacks {suffix}"
        source = (paths.evaluation_root / logical).resolve(strict=False)
        expected = path_hashes.get(logical)
        if not source.is_file() or expected != sha256_file(source):
            return False, f"targeted-test checksum differs: {logical}"
        matched.append(logical)
    package_receipt = (
        artifacts.get("common_demo_package") if isinstance(artifacts, Mapping) else None
    )
    source_hashes = (
        package_receipt.get("paths") if isinstance(package_receipt, Mapping) else None
    )
    if not isinstance(source_hashes, Mapping):
        return False, "preserved common-demo source checksum map is missing"
    matched_sources: list[str] = []
    for logical in required_sources:
        expected = source_hashes.get(logical)
        source = (paths.evaluation_root / logical).resolve(strict=False)
        if not isinstance(expected, str) or not source.is_file():
            return False, f"source receipt lacks current file: {logical}"
        if sha256_file(source) != expected:
            return False, f"implementation source checksum differs: {logical}"
        matched_sources.append(logical)
    validation = document.get("validation")
    passed_count = (
        validation.get("common_demo_targeted_tests_passed")
        if isinstance(validation, Mapping)
        else None
    )
    failed_count = (
        validation.get("targeted_tests_failed")
        if isinstance(validation, Mapping)
        else None
    )
    if (
        not isinstance(validation, Mapping)
        or validation.get("status") != "PASS"
        or validation.get("python_compile_passed") is not True
        or validation.get("ruff_check_passed") is not True
        or failed_count != 0
        or not isinstance(passed_count, int)
        or passed_count < 1
    ):
        return False, "preserved state lacks a positive targeted-test count"
    return True, (
        f"verified {len(matched)} test and {len(matched_sources)} source hashes "
        f"from {state_path}; preserved targeted tests passed={passed_count}, "
        "failed=0, validation=PASS"
    )


def _evidence_row(
    label: str,
    status: str,
    *,
    acceptable: bool,
    evidence: str,
) -> dict[str, object]:
    return {
        "label": label,
        "status": status,
        "acceptable": acceptable,
        "evidence": evidence,
    }


def _normalized_cell_values(artifact: ResultArtifact, key: str) -> set[object]:
    expected = _normal_key(key)
    return {
        _coerce_scalar(value)
        for path, value in _document_values(artifact)
        if _normal_key(path) == expected and isinstance(value, (str, int, float, bool))
    }


def _capability_source_hashes(row: Mapping[str, object]) -> set[str]:
    """Extract explicit SHA-256 source bindings from one exported study row."""

    values = " ".join(
        str(row.get(key) or "")
        for key in (
            "source_bindings",
            "source_result_sha256",
            "source_runtime_result_sha256",
            "source_result_hash",
        )
    )
    return set(re.findall(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", values.casefold()))


def _capability_rows_valid(
    rows: Sequence[Mapping[str, object]],
    artifacts: Mapping[str, ResultArtifact],
    *,
    require_measured: bool,
    measured_metrics_required: bool = True,
) -> tuple[bool, str]:
    """Validate measured/unsupported cells without inventing missing metrics.

    The science artifact manifest binds the complete CSV bytes to its primary
    result.  Each cell must additionally name a checksum-valid source result.
    Unsupported cells are allowed only when they contain a reason and state
    explicitly that no metrics were computed or synthesized.
    """

    if not rows:
        return False, "capability table is empty"
    known_hashes = {
        str(artifact.sha256)
        for artifact in artifacts.values()
        if isinstance(artifact.sha256, str)
    }
    measured = 0
    unsupported = 0
    failures: list[str] = []
    for index, raw in enumerate(rows, start=1):
        row = {str(key): _coerce_scalar(value) for key, value in raw.items()}
        status = str(row.get("status") or "").upper()
        cell_id = str(row.get("cell_id") or f"row-{index}")
        if status not in {"MEASURED", "UNSUPPORTED_CAPABILITY"}:
            failures.append(f"{cell_id}: invalid status {status or 'MISSING'}")
            continue
        outcome_sha = str(row.get("outcome_sha256") or "").casefold()
        if not re.fullmatch(r"[0-9a-f]{64}", outcome_sha):
            failures.append(f"{cell_id}: outcome checksum missing")
        if row.get("synthetic_metrics_emitted") is not False:
            failures.append(f"{cell_id}: synthetic-metric guard differs")
        if status == "MEASURED":
            measured += 1
            source_hashes = _capability_source_hashes(raw)
            if not source_hashes or not (source_hashes & known_hashes):
                failures.append(
                    f"{cell_id}: checksum-valid source result binding missing"
                )
            if measured_metrics_required and row.get("metrics_computed") is not True:
                failures.append(f"{cell_id}: measured cell lacks measured metrics")
        else:
            unsupported += 1
            if not str(row.get("reason") or "").strip():
                failures.append(f"{cell_id}: unsupported cell lacks reason")
            if row.get("metrics_computed") is not False:
                failures.append(f"{cell_id}: unsupported cell claims metrics")
    if require_measured and measured == 0:
        failures.append("no measured cell is present")
    return (
        not failures,
        (
            f"validated cells={len(rows)}, measured={measured}, "
            f"explicit_unsupported={unsupported}"
            if not failures
            else "; ".join(failures[:8])
        ),
    )


def _cell_value_key(value: object) -> str:
    return _json_text(_coerce_scalar(value))


def _coverage_axis_value(
    row: Mapping[str, object], axis: str, aliases: Sequence[str]
) -> object | None:
    raw_axis = str(row.get("axis") or row.get("parameter") or "")
    if _normal_key(raw_axis) in {_normal_key(axis), *map(_normal_key, aliases)}:
        for key in ("value", "candidate_value", "axis_value", "parameter_value"):
            if row.get(key) not in {None, ""}:
                return _coerce_scalar(row[key])
    for key in (axis, *aliases):
        if row.get(key) not in {None, ""}:
            return _coerce_scalar(row[key])
    return None


def _embedding_clustering_coverage_complete(
    paths: ProgramPaths,
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[bool, str]:
    """Require every declared embedding/clustering axis cell to be accounted for."""

    values = _artifact_for_kind(artifacts, "policy_replay")
    if len(values) != 1:
        return False, "one policy replay artifact is required for coverage"
    rows = _supporting_rows(values[0], "embedding_clustering_coverage.csv")
    valid, reason = _capability_rows_valid(
        rows,
        artifacts,
        require_measured=False,
        measured_metrics_required=False,
    )
    if not valid:
        return False, reason
    spec = read_yaml(paths.config_path)
    development = spec.get("development_search")
    frontier = (
        development.get("embedding_frontier")
        if isinstance(development, Mapping)
        else None
    )
    baseline = spec.get("historical_baseline")
    baseline_clustering = (
        baseline.get("clustering") if isinstance(baseline, Mapping) else None
    )
    if not isinstance(frontier, Mapping) or not isinstance(
        baseline_clustering, Mapping
    ):
        return False, "configuration lacks declared embedding/clustering axes"
    aliases: dict[str, tuple[str, ...]] = {
        "window_sec": ("embedding_window_sec", "window_duration_sec"),
        "hop_sec": ("embedding_hop_sec",),
        "minimum_voiced_proportion": ("embedding_minimum_voiced_proportion",),
        "minimum_non_overlap_sec": ("identity_minimum_non_overlap_sec",),
        "accumulation": ("identity_accumulation",),
        "aggregation": ("identity_aggregation", "embedding_aggregation"),
        "outlier_rejection": ("identity_outlier_rejection",),
        "redim_execution_strategy": ("redim_execution", "sharing_strategy"),
        "clustering_threshold": ("cosine_threshold",),
        "short_turn_attach_gap_sec": ("attach_gap_sec",),
    }
    expected: dict[str, set[str]] = {
        axis: {_cell_value_key(value) for value in frontier.get(axis) or ()}
        for axis in (
            "window_sec",
            "hop_sec",
            "minimum_voiced_proportion",
            "minimum_non_overlap_sec",
            "accumulation",
            "aggregation",
            "outlier_rejection",
        )
    }
    redim = (
        development.get("redim_execution") if isinstance(development, Mapping) else None
    )
    if not isinstance(redim, Sequence) or isinstance(redim, (str, bytes)):
        return False, "configuration lacks declared ReDim execution strategies"
    expected["redim_execution_strategy"] = {_cell_value_key(value) for value in redim}
    expected["clustering_threshold"] = {
        _cell_value_key(baseline_clustering.get("cosine_threshold"))
    }
    expected["short_turn_attach_gap_sec"] = {
        _cell_value_key(baseline_clustering.get("short_turn_attach_gap_sec"))
    }
    for artifact in artifacts.values():
        tuning = artifact.job.runtime_tuning
        for axis in ("clustering_threshold", "short_turn_attach_gap_sec"):
            value = _coverage_axis_value(tuning, axis, aliases[axis])
            if value is not None:
                expected[axis].add(_cell_value_key(value))
    observed: dict[str, set[str]] = {axis: set() for axis in expected}
    for row in rows:
        status = str(row.get("status") or "").upper()
        if status not in {"MEASURED", "UNSUPPORTED_CAPABILITY"}:
            continue
        for axis in expected:
            value = _coverage_axis_value(row, axis, aliases[axis])
            if value is not None:
                observed[axis].add(_cell_value_key(value))
    missing = {
        axis: sorted(values - observed[axis])
        for axis, values in expected.items()
        if values - observed[axis]
    }
    if missing:
        return False, "coverage lacks declared cells: " + _json_text(missing)
    strategy_rows = {
        str(
            _coverage_axis_value(
                row, "redim_execution_strategy", aliases["redim_execution_strategy"]
            )
        ): row
        for row in rows
        if _coverage_axis_value(
            row, "redim_execution_strategy", aliases["redim_execution_strategy"]
        )
        is not None
    }
    for strategy in ("R1_TWO_INDEPENDENT_MODELS", "R2_ONE_SHARED_MODEL"):
        row = strategy_rows.get(strategy)
        if (
            not isinstance(row, Mapping)
            or str(row.get("status") or "").upper() != "MEASURED"
            or _coerce_scalar(row.get("matched_resource_evidence")) is not True
            or not re.fullmatch(
                r"[0-9a-f]{64}",
                str(row.get("matched_resource_source_result_sha256") or "").casefold(),
            )
        ):
            return False, f"{strategy} lacks checksum-bound matched resource evidence"
    statuses = Counter(str(row.get("status") or "").upper() for row in rows)
    return True, (
        f"all declared embedding/clustering cells accounted for; "
        f"measured={statuses['MEASURED']}, "
        f"explicit_unsupported={statuses['UNSUPPORTED_CAPABILITY']}"
    )


def _named_policy_values(artifact: ResultArtifact) -> set[str]:
    output: set[str] = set()
    for _path, value in _document_values(artifact):
        if isinstance(value, str) and re.match(r"^(?:H\d|H2A|M\d)[A-Z0-9_\-]*$", value):
            output.add(value)
    return output


def _integrated_enrollment_complete(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[bool, str]:
    values = _artifact_for_kind(artifacts, "integrated_enrollment")
    if len(values) != 1:
        return False, "one integrated enrollment confirmation artifact is required"
    artifact = values[0]
    matrix_rows = _supporting_rows(artifact, "integrated_enrollment_matrix.csv")
    required_enrollment = {
        "utterances": {3, 5},
        "total_duration_sec": {10.0, 20.0},
        "sessions": {"single", "varied"},
        "aggregation": {"normalized_mean", "frozen_redim_multi_template"},
        "quality_filter": {"blind_accept", "quality_filtered"},
    }
    failures: list[str] = []
    historical_rows = _supporting_rows(artifact, "historical_enrollment_matrix.csv")
    selected_rows = _supporting_rows(
        artifact, "integrated_enrollment_selected_cell.csv"
    )
    panel_rows = _supporting_rows(artifact, "integrated_enrollment_panel.jsonl")
    cache_rows = _supporting_rows(artifact, "integrated_enrollment_cache_manifest.csv")
    for key, expected in required_enrollment.items():
        observed = _normalized_cell_values(artifact, key)
        if not expected.issubset(observed):
            failures.append(f"{key} lacks {sorted(expected - observed, key=str)}")
    expected_cells = {
        tuple(_cell_value_key(value) for value in cell)
        for cell in product(*required_enrollment.values())
    }
    observed_cells = {
        tuple(_cell_value_key(row.get(key)) for key in required_enrollment)
        for row in matrix_rows
        if str(row.get("status") or "").upper() in {"MEASURED", "TECHNICALLY_INVALID"}
    }
    if observed_cells != expected_cells:
        failures.append(
            "matrix does not account for every exact declared enrollment cell"
        )
    if len(matrix_rows) != 32 or any(
        str(row.get("status") or "").upper() not in {"MEASURED", "TECHNICALLY_INVALID"}
        or _coerce_scalar(row.get("attempted")) is not True
        for row in matrix_rows
    ):
        failures.append("integrated matrix is not 32 measured/attempted-invalid cells")
    historical_cells = {
        tuple(_cell_value_key(row.get(key)) for key in required_enrollment)
        for row in historical_rows
        if str(row.get("status") or "").upper()
        in {
            "HISTORICAL_STANDALONE_MEASURED",
            "HISTORICAL_STANDALONE_UNSUPPORTED",
        }
    }
    if len(historical_rows) != 32 or historical_cells != expected_cells:
        failures.append("historical standalone accounting is not the exact 32 cells")
    if any(
        _coerce_scalar(row.get("standalone_not_integrated")) is not True
        or _coerce_scalar(row.get("session_diversity_inferred")) is not False
        for row in historical_rows
    ):
        failures.append(
            "historical evidence is relabelled integrated or infers sessions"
        )
    if (
        len(selected_rows) != 1
        or str(selected_rows[0].get("status") if selected_rows else "").upper()
        != "INTEGRATED_SELECTED_CELL"
    ):
        failures.append("exactly one integrated selected cell is required")
    if len(panel_rows) != 1 or not cache_rows:
        failures.append("sealed panel/private-cache public manifest is missing")
    document = artifact.document or {}
    if any(
        document.get(key) is not True
        for key in (
            "panel_manifest_checksum_valid",
            "cache_manifest_checksum_valid",
            "all_declared_cells_attempted",
        )
    ):
        failures.append("panel/cache/cell-attempt checksum contract is incomplete")
    if document.get("public_embedding_payload_present") is not False:
        failures.append("public enrollment payload does not explicitly exclude vectors")
    if artifact.root is not None and any(
        path.is_file()
        for pattern in ("*.npz", "*.npy")
        for path in artifact.root.rglob(pattern)
    ):
        failures.append("public enrollment result contains a raw vector array")
    if not _explicit_true(
        artifact,
        {
            "integrated_enrollment_confirmation_measured",
            "enrollment_frontier_measured",
        },
    ):
        failures.append("comparison is not explicitly measured")
    return (
        not failures,
        (
            "historical standalone and integrated 32-cell enrollment evidence is complete"
            if not failures
            else "; ".join(failures)
        ),
    )


def _semantic_study_contract(
    paths: ProgramPaths,
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[bool, str]:
    """Validate exact named frontier cells required by the steering protocol."""

    failures: list[str] = []
    identity = _artifact_for_kind(artifacts, "policy_replay")
    if len(identity) != 1:
        failures.append("one identity policy frontier artifact is required")
    else:
        rows = _supporting_rows(identity[0], "open_set_policy_frontier.csv")
        cells = {
            "minimum_evidence_sec": {1.0, 1.5, 2.0, 2.5, 3.0},
            "margin_threshold": {0.01, 0.02, 0.03, 0.04, 0.05},
            "gallery_requested_size": {"1", "2", "5", "10", "20", "50", "full"},
        }
        for key, expected in cells.items():
            observed = {
                (
                    str(_coerce_scalar(row.get(key)))
                    if key == "gallery_requested_size"
                    else _coerce_scalar(row.get(key))
                )
                for row in rows
                if row.get(key) not in {None, ""}
            }
            if not expected.issubset(observed):
                failures.append(
                    f"identity frontier lacks {key} cells {sorted(expected - observed, key=str)}"
                )

    hysteresis = _artifact_for_kind(artifacts, "memory_policy_replay")
    required_h = {
        "H0_ONE_PASS_DIAGNOSTIC",
        "H1_TWO_CONFIRM_TWO_RELEASE",
        "H2A_ADAPTIVE_EARLY",
        "H3_THREE_CONFIRM_SAFE",
        "H4_DURATION_DEPENDENT",
    }
    required_m = {
        "M0_STATELESS",
        "M1_CLUSTER",
        "M2_CONFIRMED_NAME",
        "M3_SHORT_TURN",
        "M4_ACTIVE_ROSTER_DECAY",
        "M5_CLUSTER_RECONCILIATION",
    }
    if len(hysteresis) != 1:
        failures.append("one named hysteresis/session-memory artifact is required")
    else:
        frontier_rows = _supporting_rows(hysteresis[0], "memory_policy_frontier.csv")
        capability_rows = [
            row for row in frontier_rows if row.get("cell_id") not in {None, ""}
        ]
        valid_rows, row_reason = _capability_rows_valid(
            capability_rows, artifacts, require_measured=True
        )
        if not valid_rows:
            failures.append("memory/hysteresis capability rows: " + row_reason)
        named = _named_policy_values(hysteresis[0])
        if not required_h.issubset(named):
            failures.append(
                "hysteresis comparison lacks named cells "
                + ", ".join(sorted(required_h - named))
            )
        if not required_m.issubset(named):
            failures.append(
                "session-memory comparison lacks named cells "
                + ", ".join(sorted(required_m - named))
            )
        expiry = _normalized_cell_values(hysteresis[0], "identity_expiry_sec")
        expiry_numeric = {
            float(value)
            for value in expiry
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        }
        expiry_text = {str(value) for value in expiry if isinstance(value, str)}
        if not {15.0, 30.0, 60.0, 120.0}.issubset(expiry_numeric) or not any(
            value.casefold() in {"end_of_session", "session_end"}
            for value in expiry_text
        ):
            failures.append("expiry frontier lacks 15/30/60/120/end-of-session cells")
        expected_expiry = {
            _cell_value_key(value)
            for value in (15.0, 30.0, 60.0, 120.0, "end_of_session")
        }
        h_cells = {
            (
                str(row.get("hysteresis_policy") or ""),
                _cell_value_key(row.get("identity_expiry_sec")),
            )
            for row in frontier_rows
            if str(row.get("cell_type") or "") == "named_hysteresis"
            and str(row.get("status") or "").upper() == "MEASURED"
        }
        missing_h = {
            (policy, expiry) for policy in required_h for expiry in expected_expiry
        } - h_cells
        if missing_h:
            failures.append(
                f"named hysteresis matrix lacks {len(missing_h)} measured cells"
            )
        m_cells = {
            (
                str(row.get("memory_level") or ""),
                _cell_value_key(row.get("identity_expiry_sec")),
            )
            for row in frontier_rows
            if str(row.get("cell_type") or "") == "memory_level"
            and str(row.get("status") or "").upper()
            in {"MEASURED", "UNSUPPORTED_CAPABILITY"}
        }
        missing_m = {
            (policy, expiry) for policy in required_m for expiry in expected_expiry
        } - m_cells
        if missing_m:
            failures.append(
                f"session-memory matrix lacks {len(missing_m)} explicit cells"
            )

    short = _artifact_for_kind(artifacts, "short_turn_replay")
    if len(short) != 1:
        failures.append("one short-turn causal replay artifact is required")
    else:
        short_rows = _supporting_rows(short[0], "short_turn_replay_frontier.csv")
        valid_rows, row_reason = _capability_rows_valid(
            short_rows, artifacts, require_measured=True
        )
        if not valid_rows:
            failures.append("short-turn capability rows: " + row_reason)
        required_policies = {
            "FRESH_EMBEDDING_REQUIRED",
            "ANONYMOUS_CLUSTER_INHERITANCE",
            "CONFIRMED_NAME_INHERITANCE",
            "INHERITANCE_WITH_CONTRADICTION_CHECKS",
            "GENERIC_UNTIL_LATER_CORRECTION",
        }
        required_bins = {"LT_0P5", "GE_0P5_LT_1P0", "GE_1P0_LE_2P0"}
        observed_short = {
            (
                str(row.get("short_turn_policy") or ""),
                str(row.get("duration_bin") or ""),
            )
            for row in short_rows
            if str(row.get("status") or "").upper()
            in {"MEASURED", "UNSUPPORTED_CAPABILITY"}
        }
        if any(
            (policy, duration) not in observed_short
            for policy in required_policies
            for duration in required_bins
        ):
            failures.append("short-turn matrix lacks declared policy/duration cells")
        document = short[0].document or {}
        if not isinstance(document.get("selected_frontier_row"), Mapping):
            failures.append("short-turn replay has no measured selected policy")

    coverage, coverage_reason = _embedding_clustering_coverage_complete(
        paths, artifacts
    )
    if not coverage:
        failures.append("embedding/clustering coverage: " + coverage_reason)

    enrollment_complete, enrollment_reason = _integrated_enrollment_complete(artifacts)
    if not enrollment_complete:
        failures.append("integrated enrollment: " + enrollment_reason)
    return not failures, (
        "; ".join(failures)
        if failures
        else (
            "exact named H/M/enrollment/identity/short-turn and embedding/clustering "
            "frontier cells are checksum-accounted"
        )
    )


def build_final_evidence_table(
    paths: ProgramPaths,
    artifacts: Mapping[str, ResultArtifact],
    *,
    final_report_complete: bool,
    final_zip_valid: bool,
) -> tuple[dict[str, object], ...]:
    """Build the exact steering evidence rows from validated artifacts."""

    preserved, preserved_reason = _preservation_evidence(artifacts)
    superseded, superseded_reason = _non_h2_supersession_evidence(paths)
    reuse_complete, reuse_reason = _embedding_reuse_parity_complete(artifacts)
    onnx_complete, onnx_reason = _onnx_end_to_end_parity_complete(artifacts)

    streaming = bool(_artifact_for_kind(artifacts, "runtime_qualification"))
    giga = {
        value.job.configuration_id
        for value in artifacts.values()
        if value.job.pipeline_id == "fullpipe_v1_ag_dr_ir"
        and value.job.split == "evaluation"
        and value.artifact_kind != "superseded"
    }.issuperset(
        {
            "H2_KNOWN_ONLY_HELDOUT",
            "H2_SESSION_ANONYMOUS_HELDOUT",
            "H2_SESSION_MEMORY_ENHANCED_HELDOUT",
        }
    )
    original = (
        _artifact_for_configuration(artifacts, "H2_ORIGINAL_SHERPA_REDUCED_REGRESSION")
        is not None
    )
    segmentation_values = tuple(
        value
        for value in artifacts.values()
        if value.job.phase_index == 1
        and value.job.job_kind == "successive_halving_runtime"
        and value.artifact_kind != "superseded"
    )
    segmentation = bool(segmentation_values) and any(
        value.job.configuration_id.endswith("_FULL") for value in segmentation_values
    )
    shared = any(
        value.job.configuration_id.startswith("R2_ONE_SHARED_MODEL")
        and value.artifact_kind != "superseded"
        for value in artifacts.values()
    )
    known_mode = (
        _artifact_for_configuration(artifacts, "H2_KNOWN_ONLY_HELDOUT") is not None
    )
    anonymous_mode = (
        _artifact_for_configuration(artifacts, "H2_SESSION_ANONYMOUS_HELDOUT")
        is not None
    )
    memory_mode_artifact = _artifact_for_configuration(
        artifacts, "H2_SESSION_MEMORY_ENHANCED_HELDOUT"
    )
    memory_mode = memory_mode_artifact is not None
    warm_metrics = (
        {
            str(row.get("metric_id"))
            for row in _metric_rows(memory_mode_artifact)
            if str(row.get("metric_status") or "").casefold() == "computed"
            and row.get("value") is not None
        }
        if memory_mode_artifact is not None
        else set()
    )
    warm_reacquisition = {
        "reentry_accuracy",
        "warm_identity_accuracy",
    }.issubset(warm_metrics)
    memory_values = _artifact_for_kind(artifacts, "memory_policy_replay")
    memory_frontier = (
        _supporting_rows(memory_values[0], "memory_policy_frontier.csv")
        if len(memory_values) == 1
        else ()
    )
    memory_grid = (
        len(memory_values) == 1
        and bool(memory_frontier)
        and len({row.get("consecutive_passes_to_confirm") for row in memory_frontier})
        >= 3
        and len({row.get("hysteresis") for row in memory_frontier}) >= 5
        and len({row.get("identity_expiry_sec") for row in memory_frontier}) >= 4
    )
    named_memory_values = (
        _named_policy_values(memory_values[0]) if len(memory_values) == 1 else set()
    )
    named_hysteresis_complete = {
        "H0_ONE_PASS_DIAGNOSTIC",
        "H1_TWO_CONFIRM_TWO_RELEASE",
        "H2A_ADAPTIVE_EARLY",
        "H3_THREE_CONFIRM_SAFE",
        "H4_DURATION_DEPENDENT",
    }.issubset(named_memory_values)
    named_memory_complete = {
        "M0_STATELESS",
        "M1_CLUSTER",
        "M2_CONFIRMED_NAME",
        "M3_SHORT_TURN",
        "M4_ACTIVE_ROSTER_DECAY",
        "M5_CLUSTER_RECONCILIATION",
    }.issubset(named_memory_values)
    short_values = _artifact_for_kind(artifacts, "short_turn_replay")
    short_frontier = (
        _supporting_rows(short_values[0], "short_turn_replay_frontier.csv")
        if len(short_values) == 1
        else ()
    )
    short_grid = (
        len(short_values) == 1
        and bool(short_frontier)
        and {
            "FRESH_EMBEDDING_REQUIRED",
            "ANONYMOUS_CLUSTER_INHERITANCE",
            "CONFIRMED_NAME_INHERITANCE",
            "INHERITANCE_WITH_CONTRADICTION_CHECKS",
            "GENERIC_UNTIL_LATER_CORRECTION",
        }.issubset({str(row.get("short_turn_policy") or "") for row in short_frontier})
        and {"LT_0P5", "GE_0P5_LT_1P0", "GE_1P0_LE_2P0"}.issubset(
            {str(row.get("duration_bin") or "") for row in short_frontier}
        )
        and any(
            str(row.get("status") or "").upper() == "MEASURED" for row in short_frontier
        )
        and isinstance(
            (short_values[0].document or {}).get("selected_frontier_row"),
            Mapping,
        )
    )
    boundaries = len(_complete_configurations(artifacts, "BOUNDARY_CORRECTION_")) == 5
    measured_overlap, missing_overlap_metrics = _measured_overlap_policies(artifacts)
    unsupported_overlap, overlap_contract_reason = _overlap_capability_contract(paths)
    required_unsupported_overlap = {
        "DEFER_IDENTITY_UNTIL_NON_OVERLAP",
        "DISPLAY_OVERLAPPING_SPEAKERS_WHEN_AMBIGUOUS",
    }
    overlap = (
        measured_overlap
        == {
            "INCLUDE_PREDICTED_OVERLAP",
            "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
        }
        and unsupported_overlap == required_unsupported_overlap
    )
    paragraphs = (
        len(_artifact_for_kind(artifacts, "post_selection_paragraph_validation")) == 4
    )
    export_values = _artifact_for_kind(artifacts, "onnx_export")
    export_complete = len(export_values) == 1 and _artifact_status_passes(
        export_values[0]
    )
    linux_values = _artifact_for_kind(artifacts, "linux_portability")
    linux_prepared = len(linux_values) == 1 and _artifact_status_passes(linux_values[0])
    long_complete, long_reason = _long_session_completion_contract(artifacts)
    long_resource = (
        long_complete
        and len(_artifact_for_kind(artifacts, "reliability")) == 1
        and len(_artifact_for_kind(artifacts, "post_selection_resource_runtime")) == 3
    )
    development = all(
        artifact.validated
        for artifact in artifacts.values()
        if artifact.job.split != "evaluation"
    )
    frozen = (
        len(_artifact_for_kind(artifacts, "freeze")) == 1
        and all(
            artifact.validated
            for artifact in artifacts.values()
            if artifact.job.split == "evaluation"
        )
        and any(artifact.job.split == "evaluation" for artifact in artifacts.values())
    )
    live_app, live_evidence = _preserved_targeted_test_evidence(
        paths,
        artifacts,
        capability_id="live_microphone",
        required_test_suffixes=(
            "tests/full_pipeline_demo/test_state_devices.py",
            "tests/full_pipeline_demo/test_ui.py",
        ),
        required_sources=(
            "app/full_pipeline_demo/cli.py",
            "app/full_pipeline_demo/ui.py",
            "app/full_pipeline/factory.py",
        ),
    )
    file_app, file_evidence = _preserved_targeted_test_evidence(
        paths,
        artifacts,
        capability_id="audio_file_simulation",
        required_test_suffixes=(
            "tests/full_pipeline_demo/test_cli.py",
            "tests/full_pipeline_demo/test_session_export.py",
        ),
        required_sources=(
            "app/full_pipeline_demo/cli.py",
            "app/full_pipeline_demo/session.py",
        ),
    )
    enrollment_app, enrollment_app_evidence = _preserved_targeted_test_evidence(
        paths,
        artifacts,
        capability_id="speaker_enrollment",
        required_test_suffixes=("tests/full_pipeline_demo/test_presets_enrollment.py",),
        required_sources=(
            "app/full_pipeline_demo/enrollment.py",
            "app/full_pipeline_demo/cli.py",
        ),
    )
    inspector, inspector_evidence = _preserved_targeted_test_evidence(
        paths,
        artifacts,
        capability_id="embedding_inspector",
        required_test_suffixes=("tests/full_pipeline_demo/test_ui.py",),
        required_sources=("app/full_pipeline_demo/ui.py",),
    )
    xvf = _implementation_exists(
        paths,
        "app/h2_portability/spatial.py",
        "docs/full_pipeline/H2_XVF3800_FUTURE_INTERFACE.md",
    )
    resource_values = _artifact_for_kind(artifacts, "post_selection_resource_runtime")
    measured_resource_peaks = {
        artifact.job.configuration_id: float(row["value"])
        for artifact in resource_values
        for row in _metric_rows(artifact)
        if row.get("metric_id") == "peak_rss_bytes"
        and str(row.get("metric_status") or "").casefold() == "computed"
        and isinstance(row.get("value"), (int, float))
        and not isinstance(row.get("value"), bool)
    }
    memory_analysis = (
        len(resource_values) == 3
        and len(measured_resource_peaks) == 3
        and _implementation_exists(paths, "app/h2_portability/platform_support.py")
    )
    enrollment_science, enrollment_science_evidence = _integrated_enrollment_complete(
        artifacts
    )
    enrollment = enrollment_app and enrollment_science
    enrollment_evidence = enrollment_app_evidence + "; " + enrollment_science_evidence
    rows = (
        _evidence_row(
            "Existing work preserved",
            "PASS" if preserved else "FAIL",
            acceptable=preserved,
            evidence=preserved_reason,
        ),
        _evidence_row(
            "Non-H2 work gracefully superseded",
            "PASS" if superseded else "FAIL",
            acceptable=superseded,
            evidence=superseded_reason,
        ),
        _evidence_row(
            "H2 true streaming runtime",
            "COMPLETE" if streaming else "FAIL",
            acceptable=streaming,
            evidence="runtime_qualification job",
        ),
        _evidence_row(
            "Sherpa Giga integration",
            "COMPLETE" if giga else "FAIL",
            acceptable=giga,
            evidence="AG H2 held-out result",
        ),
        _evidence_row(
            "Original Sherpa reduced regression",
            "COMPLETE" if original else "FAIL",
            acceptable=original,
            evidence="AO reduced held-out result",
        ),
        _evidence_row(
            "Pyannote segmentation frontier",
            "COMPLETE" if segmentation else "FAIL",
            acceptable=segmentation,
            evidence=f"completed phase-1 frontier jobs={len(segmentation_values)}",
        ),
        _evidence_row(
            "ReDim shared worker",
            "COMPLETE" if shared else "FAIL",
            acceptable=shared,
            evidence="measured R2 shared-model runtime",
        ),
        _evidence_row(
            "Embedding reuse parity",
            "COMPLETE" if reuse_complete else "FAIL",
            acceptable=reuse_complete,
            evidence=reuse_reason,
        ),
        _evidence_row(
            "Known-only mode",
            "COMPLETE" if known_mode else "FAIL",
            acceptable=known_mode,
            evidence="known-only held-out result",
        ),
        _evidence_row(
            "Session-anonymous mode",
            "COMPLETE" if anonymous_mode else "FAIL",
            acceptable=anonymous_mode,
            evidence="session-anonymous held-out result",
        ),
        _evidence_row(
            "Enhanced session-memory mode",
            "COMPLETE" if memory_mode else "FAIL",
            acceptable=memory_mode,
            evidence="enhanced-memory held-out result",
        ),
        _evidence_row(
            "Hysteresis study",
            "COMPLETE" if memory_grid and named_hysteresis_complete else "FAIL",
            acceptable=memory_grid and named_hysteresis_complete,
            evidence="measured H0/H1/H2A/H3/H4 memory/hysteresis frontier",
        ),
        _evidence_row(
            "Short-turn inheritance",
            "COMPLETE" if short_grid else "FAIL",
            acceptable=short_grid,
            evidence="short-turn replay frontier",
        ),
        _evidence_row(
            "Warm reacquisition",
            "COMPLETE" if short_grid and warm_reacquisition else "FAIL",
            acceptable=short_grid and warm_reacquisition,
            evidence="returning-turn replay plus computed frozen reentry_accuracy and warm_identity_accuracy",
        ),
        _evidence_row(
            "Expiry/decay",
            "COMPLETE" if memory_grid and named_memory_complete else "FAIL",
            acceptable=memory_grid and named_memory_complete,
            evidence="measured H0/H1/H2A/H3/H4 expiry cells plus explicit M0-M5 capability outcomes; unsupported cells have no fabricated metrics",
        ),
        _evidence_row(
            "Boundary correction",
            "COMPLETE" if boundaries else "FAIL",
            acceptable=boundaries,
            evidence=f"measured correction windows={len(_complete_configurations(artifacts, 'BOUNDARY_CORRECTION_'))}/5",
        ),
        _evidence_row(
            "Overlap study",
            "COMPLETE" if overlap else "FAIL",
            acceptable=overlap,
            evidence=(
                f"measured={sorted(measured_overlap)}; missing_metrics={_json_text(missing_overlap_metrics)}; explicit unsupported="
                f"{sorted(unsupported_overlap)}; {overlap_contract_reason}"
            ),
        ),
        _evidence_row(
            "Transcript structure",
            "COMPLETE" if paragraphs else "FAIL",
            acceptable=paragraphs,
            evidence="four measured paragraph policies",
        ),
        _evidence_row(
            "Live microphone application",
            "COMPLETE" if live_app else "FAIL",
            acceptable=live_app,
            evidence=live_evidence
            + "; implementation-qualified only, not physical-microphone behavior",
        ),
        _evidence_row(
            "Audio-file simulation",
            "COMPLETE" if file_app else "FAIL",
            acceptable=file_app,
            evidence=file_evidence,
        ),
        _evidence_row(
            "Speaker enrollment",
            "COMPLETE" if enrollment else "FAIL",
            acceptable=enrollment,
            evidence=enrollment_evidence,
        ),
        _evidence_row(
            "Embedding inspector",
            "COMPLETE" if inspector else "FAIL",
            acceptable=inspector,
            evidence=inspector_evidence,
        ),
        _evidence_row(
            "ONNX FP32 export",
            "COMPLETE" if export_complete else ("PARTIAL" if export_values else "FAIL"),
            acceptable=export_complete,
            evidence="checksum-valid two-component export job",
        ),
        _evidence_row(
            "ONNX parity",
            "COMPLETE" if onnx_complete else "FAIL",
            acceptable=onnx_complete,
            evidence=onnx_reason,
        ),
        _evidence_row(
            "ARM64 Linux package",
            "PREPARED" if linux_prepared else "FAIL",
            acceptable=linux_prepared,
            evidence="checksum-bound package preparation; not hardware validation",
        ),
        _evidence_row(
            "2 GB memory analysis",
            "COMPLETE" if memory_analysis else "FAIL",
            acceptable=memory_analysis,
            evidence=(
                f"measured serial peak_rss_bytes modes={len(measured_resource_peaks)}/3; "
                "conservative design budget; not ARM64 hardware measurement"
            ),
        ),
        _evidence_row(
            "XVF3800 future hooks",
            "PREPARED" if xvf else "FAIL",
            acceptable=xvf,
            evidence="no-effect spatial interface and handoff document",
        ),
        _evidence_row(
            "Development run",
            "COMPLETE" if development else "FAIL",
            acceptable=development,
            evidence="all non-held-out planned evidence terminal and validated",
        ),
        _evidence_row(
            "Frozen evaluation",
            "COMPLETE" if frozen else "FAIL",
            acceptable=frozen,
            evidence="freeze plus every held-out job",
        ),
        _evidence_row(
            "Long-session/resource testing",
            "COMPLETE" if long_resource else "FAIL",
            acceptable=long_resource,
            evidence=(
                f"{long_reason}; reliability plus three serial mode resource jobs"
            ),
        ),
        _evidence_row(
            "Final report",
            "COMPLETE" if final_report_complete else "FAIL",
            acceptable=final_report_complete,
            evidence=(
                "validated final report bytes"
                if final_report_complete
                else "not yet published"
            ),
        ),
        _evidence_row(
            "Final ZIP",
            "VALID" if final_zip_valid else "FAIL",
            acceptable=final_zip_valid,
            evidence=(
                "self-validated allowlisted ZIP"
                if final_zip_valid
                else "not yet collected"
            ),
        ),
    )
    if tuple(str(row["label"]) for row in rows) != EVIDENCE_LABELS:
        raise AssertionError("final evidence table labels changed")
    return rows


def _require_analysis_completion_contract(
    paths: ProgramPaths,
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[dict[str, object], ...]:
    rows = build_final_evidence_table(
        paths,
        artifacts,
        final_report_complete=False,
        final_zip_valid=False,
    )
    failures = [
        f"{row['label']}: {row['evidence']}"
        for row in rows[:-2]
        if row.get("acceptable") is not True
    ]
    missing_docs = [
        name
        for name in FINAL_DOCUMENTS
        if not (paths.evaluation_root / "docs/full_pipeline" / name).is_file()
    ]
    if missing_docs:
        failures.append("missing final documents: " + ", ".join(missing_docs))
    semantic_complete, semantic_reason = _semantic_study_contract(paths, artifacts)
    if not semantic_complete:
        failures.append("semantic study contract: " + semantic_reason)
    if failures:
        raise H2ProgramError(
            "BLOCKED_SCIENTIFIC_RUN: final H2 analysis completion contract failed: "
            + "; ".join(failures[:12])
        )
    return rows


def _component_assets(artifact: ResultArtifact | None) -> list[dict[str, object]]:
    if artifact is None or artifact.root is None:
        return []
    model_assets_path = artifact.root / "model_assets.json"
    pipeline_path = artifact.root / "pipeline_identity.json"
    rows: list[dict[str, object]] = []
    if model_assets_path.is_file():
        document = read_json(model_assets_path)
        for raw in document.get("assets") or ():
            if not isinstance(raw, Mapping):
                continue
            rows.append(
                {
                    "role": raw.get("role"),
                    "asset_id": raw.get("asset_id"),
                    "sha256": raw.get("sha256"),
                }
            )
    if pipeline_path.is_file():
        document = read_json(pipeline_path)
        identities = document.get("component_identities")
        if isinstance(identities, list):
            by_role = {
                str(row.get("role")): row for row in rows if isinstance(row, Mapping)
            }
            for raw in identities:
                if not isinstance(raw, Mapping):
                    continue
                role = str(raw.get("role") or raw.get("component_role") or "")
                if role in by_role:
                    by_role[role]["backend_id"] = raw.get("backend_id")
                    by_role[role]["config_sha256"] = raw.get("config_sha256")
                    by_role[role]["environment_fingerprint_sha256"] = raw.get(
                        "environment_fingerprint_sha256"
                    )
    return rows


def _portable_component_assets(
    artifacts: Mapping[str, ResultArtifact],
) -> list[dict[str, object]]:
    export = _artifact_for_kind(artifacts, "onnx_export")
    if len(export) != 1 or not isinstance(export[0].document, Mapping):
        return []
    raw_components = export[0].document.get("component_artifacts")
    if not isinstance(raw_components, Mapping):
        return []
    rows: list[dict[str, object]] = []
    for component_id, raw in sorted(
        raw_components.items(), key=lambda item: str(item[0])
    ):
        if not isinstance(raw, Mapping):
            continue
        rows.append(
            {
                "component_id": str(component_id),
                "graph_sha256": raw.get("graph_sha256") or raw.get("onnx_sha256"),
                "graph_bytes": raw.get("graph_bytes") or raw.get("onnx_bytes"),
                "export_manifest_sha256": raw.get("manifest_sha256")
                or raw.get("export_manifest_sha256"),
                "precision": raw.get("precision") or "FP32",
                "opset": raw.get("opset"),
            }
        )
    return rows


def _evidence_number(value: object, *, label: str) -> float:
    if isinstance(value, bool):
        raise H2ProgramError(f"historical evidence is not numeric: {label}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise H2ProgramError(f"historical evidence is not numeric: {label}") from exc
    if not math.isfinite(result):
        raise H2ProgramError(f"historical evidence is not finite: {label}")
    return result


def _checked_historical_source(
    paths: ProgramPaths,
    section: Mapping[str, object],
    source_id: str,
) -> tuple[Path, str]:
    raw = section.get(source_id)
    if not isinstance(raw, Mapping) or not raw.get("path") or not raw.get("sha256"):
        raise H2ProgramError(f"historical source binding is invalid: {source_id}")
    source = Path(str(raw["path"]))
    if not source.is_absolute():
        source = paths.evaluation_root / source
    source = source.resolve(strict=True)
    observed = sha256_file(source)
    expected = str(raw["sha256"]).casefold()
    if observed.casefold() != expected:
        raise H2ProgramError(f"historical source checksum differs: {source_id}")
    return source, observed


def _one_historical_row(
    rows: Sequence[Mapping[str, object]],
    *,
    label: str,
    predicate: object,
) -> Mapping[str, object]:
    if not callable(predicate):
        raise H2ProgramError(f"historical row predicate is invalid: {label}")
    selected = [row for row in rows if predicate(row)]
    if len(selected) != 1:
        raise H2ProgramError(
            f"historical source must contain exactly one {label} row; "
            f"observed {len(selected)}"
        )
    return selected[0]


def _assert_historical_value(
    *,
    declared: object,
    observed: float,
    label: str,
) -> None:
    expected = _evidence_number(declared, label=f"declared {label}")
    if not math.isclose(expected, observed, rel_tol=1e-12, abs_tol=1e-12):
        raise H2ProgramError(
            f"historical manifest value differs from its machine-readable "
            f"source: {label}; declared={expected!r}, observed={observed!r}"
        )


def _verified_historical_values(
    paths: ProgramPaths,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...], str]:
    """Re-read every steering baseline from its checksum-bound source.

    The YAML manifest is provenance, not a substitute for the original result
    tables.  Any copied scalar that differs from those tables fails analysis.
    """

    manifest_path = paths.evaluation_root / (
        "configs/automated_evaluation/h2_historical_evidence.v1.yaml"
    )
    manifest = read_yaml(manifest_path)
    if manifest.get("schema_version") != "just-peachy-h2-historical-evidence.v1":
        raise H2ProgramError("historical H2 evidence schema differs")
    manifest_sha = sha256_file(manifest_path)
    output: list[dict[str, object]] = []
    sources: list[dict[str, object]] = [
        {
            "source_id": "historical_manifest",
            "path": str(manifest_path.resolve(strict=True)),
            "sha256": manifest_sha,
        }
    ]

    def bind(
        family: str,
        section: Mapping[str, object],
        source_id: str,
    ) -> tuple[Path, str]:
        source, source_sha = _checked_historical_source(paths, section, source_id)
        sources.append(
            {
                "source_id": f"{family}:{source_id}",
                "path": str(source),
                "sha256": source_sha,
            }
        )
        return source, source_sha

    def append(
        *,
        family: str,
        metric_id: str,
        value: float,
        unit: str,
        source_id: str,
        source_path: Path,
        source_sha: str,
    ) -> None:
        output.append(
            {
                "evidence_family": family,
                "metric_id": metric_id,
                "historical_value": value,
                "historical_unit": unit,
                "historical_source_id": source_id,
                "historical_source_path": str(source_path),
                "historical_source_sha256": source_sha,
                "historical_value_verified": True,
            }
        )

    frozen = manifest.get("frozen_h2")
    if not isinstance(frozen, Mapping) or not isinstance(
        frozen.get("metrics"), Mapping
    ):
        raise H2ProgramError("historical frozen H2 metrics are missing")
    h2_path, h2_sha = bind("frozen_h2", frozen, "finalist_summary")
    h2_row = _one_historical_row(
        _read_csv_rows(h2_path),
        label="H2 finalist",
        predicate=lambda row: str(row.get("combination_id")) == "H2",
    )
    h2_map = (
        (
            "correctly_named_known_time_rate",
            "end_to_end_correctly_named_known_rate",
            "ratio",
        ),
        ("wrong_known_time_rate", "end_to_end_wrong_known_rate", "ratio"),
        ("stranger_false_known_time_rate", "stranger_false_known_rate", "ratio"),
        ("generic_known_time_rate", "known_generic_rate", "ratio"),
        ("stable_name_latency_sec", "stable_name_latency_sec", "seconds"),
        (
            "stable_name_not_reached_rate",
            "stable_name_not_reached_probability",
            "ratio",
        ),
        ("unknown_label_consistency", "unknown_instance_consistency", "ratio"),
        ("unknown_rejection_rate", "unknown_rejection_rate", "ratio"),
        ("total_desktop_rtf", "total_rtf", "rtf"),
        ("peak_rss_mb", "peak_rss_mb", "megabytes"),
    )
    declared_h2 = frozen["metrics"]
    if set(declared_h2) != {row[0] for row in h2_map}:
        raise H2ProgramError("historical frozen H2 metric membership differs")
    for metric_id, field, unit in h2_map:
        observed = _evidence_number(h2_row.get(field), label=f"H2 {field}")
        _assert_historical_value(
            declared=declared_h2.get(metric_id),
            observed=observed,
            label=f"frozen_h2.{metric_id}",
        )
        append(
            family="FROZEN_H2_PRODUCT_V2",
            metric_id=metric_id,
            value=observed,
            unit=unit,
            source_id="frozen_h2:finalist_summary",
            source_path=h2_path,
            source_sha=h2_sha,
        )

    standalone = manifest.get("standalone_pyannote_redim")
    if not isinstance(standalone, Mapping) or not isinstance(
        standalone.get("metrics"), Mapping
    ):
        raise H2ProgramError("historical standalone metrics are missing")
    overall_path, overall_sha = bind(
        "standalone_pyannote_redim", standalone, "overall_results"
    )
    recording_path, recording_sha = bind(
        "standalone_pyannote_redim", standalone, "recording_results"
    )
    overall = _one_historical_row(
        _read_csv_rows(overall_path),
        label="standalone ReDimNet2 overall",
        predicate=lambda row: str(row.get("pipeline_id"))
        == "modular_pyannote_redimnet2",
    )
    recording_rows = tuple(
        row
        for row in _read_csv_rows(recording_path)
        if str(row.get("pipeline_id")) == "modular_pyannote_redimnet2"
        and str(row.get("protocol")) in {"controlled_v1", "controlled_v2"}
    )
    if not recording_rows:
        raise H2ProgramError("historical standalone recording rows are missing")
    reference_time = sum(
        _evidence_number(row.get("reference_speaker_time_sec"), label="reference time")
        for row in recording_rows
    )
    if reference_time <= 0:
        raise H2ProgramError("historical standalone reference time is not positive")
    derived_components = {
        "miss_rate": sum(
            _evidence_number(row.get("missed_speech_sec"), label="missed speech")
            for row in recording_rows
        )
        / reference_time,
        "false_alarm_rate": sum(
            _evidence_number(row.get("false_alarm_sec"), label="false alarm")
            for row in recording_rows
        )
        / reference_time,
        "speaker_confusion_rate": sum(
            _evidence_number(row.get("speaker_confusion_sec"), label="confusion")
            for row in recording_rows
        )
        / reference_time,
    }
    standalone_values = {
        "recording_count": float(len(recording_rows)),
        "der": _evidence_number(overall.get("controlled_der"), label="controlled DER"),
        "jer": _evidence_number(overall.get("controlled_jer"), label="controlled JER"),
        **derived_components,
        "catastrophic_contaminated_cluster_rate": _evidence_number(
            overall.get("catastrophic_contaminated_cluster_rate"),
            label="catastrophic cluster rate",
        ),
        "clean_evidence_yield_2s": _evidence_number(
            overall.get("clean_evidence_yield_2s"), label="clean evidence yield"
        ),
        "median_absolute_boundary_delay_ms": _evidence_number(
            overall.get("median_absolute_boundary_delay_ms"), label="boundary delay"
        ),
        "reentry_consistency": _evidence_number(
            overall.get("reentry_consistency"), label="re-entry consistency"
        ),
        "controlled_rtf": _evidence_number(
            overall.get("controlled_rtf"), label="controlled RTF"
        ),
    }
    declared_standalone = standalone["metrics"]
    if set(declared_standalone) != set(standalone_values):
        raise H2ProgramError("historical standalone metric membership differs")
    for metric_id, observed in standalone_values.items():
        _assert_historical_value(
            declared=declared_standalone.get(metric_id),
            observed=observed,
            label=f"standalone_pyannote_redim.{metric_id}",
        )
        component_metric = metric_id in derived_components
        append(
            family="STANDALONE_PYANNOTE_REDIM",
            metric_id=metric_id,
            value=observed,
            unit=(
                "recordings"
                if metric_id == "recording_count"
                else (
                    "milliseconds"
                    if metric_id == "median_absolute_boundary_delay_ms"
                    else "rtf" if metric_id == "controlled_rtf" else "ratio"
                )
            ),
            source_id=(
                "standalone_pyannote_redim:recording_results"
                if component_metric
                else "standalone_pyannote_redim:overall_results"
            ),
            source_path=recording_path if component_metric else overall_path,
            source_sha=recording_sha if component_metric else overall_sha,
        )

    enrollment = manifest.get("speaker_enrollment_live")
    if not isinstance(enrollment, Mapping):
        raise H2ProgramError("historical enrollment evidence is missing")
    reporting_sources = manifest.get("historical_reporting_sources")
    if not isinstance(reporting_sources, Mapping):
        raise H2ProgramError("historical reporting sources are missing")
    duration_path, duration_sha = bind(
        "speaker_enrollment_live", enrollment, "duration_curve"
    )
    causal_path, causal_sha = bind(
        "speaker_enrollment_live", enrollment, "causal_summary"
    )
    configuration_path, configuration_sha = bind(
        "historical_reporting_sources",
        reporting_sources,
        "speaker_enrollment_configuration_results",
    )
    telemetry_path, telemetry_sha = bind(
        "speaker_enrollment_live", enrollment, "runtime_telemetry"
    )
    backend_id = "redimnet2_b2_speaker_embedding"
    duration_rows = tuple(
        row
        for row in _read_csv_rows(duration_path)
        if str(row.get("backend")) == backend_id
        and str(row.get("phase")) == "ProbeDuration"
    )
    for duration in (1.0, 2.0, 3.0):
        row = _one_historical_row(
            duration_rows,
            label=f"ReDimNet2 {duration:g}-second probe duration",
            predicate=lambda value, duration=duration: math.isclose(
                _evidence_number(
                    value.get("probe_target_audio_sec"), label="probe duration"
                ),
                duration,
                abs_tol=1e-9,
            ),
        )
        append(
            family="REDIM_ENROLLMENT_LIVE_V2",
            metric_id=f"tpir_{duration:g}s",
            value=_evidence_number(row.get("tpir"), label=f"TPIR {duration:g}s"),
            unit="ratio",
            source_id="speaker_enrollment_live:duration_curve",
            source_path=duration_path,
            source_sha=duration_sha,
        )
    causal_rows = tuple(
        row
        for row in _read_csv_rows(causal_path)
        if str(row.get("backend")) == backend_id
    )
    for duration in (3.0, 5.0):
        selected = [
            row
            for row in causal_rows
            if math.isclose(
                _evidence_number(row.get("duration_sec"), label="causal duration"),
                duration,
                abs_tol=1e-9,
            )
        ]
        if not selected:
            raise H2ProgramError(
                f"historical ReDimNet2 causal rows are missing at {duration:g}s"
            )
        for metric_id, field in (
            (f"stateful_dir_{duration:g}s", "hysteresis_dir_rank1"),
            (f"stateful_fpir_{duration:g}s", "hysteresis_fpir"),
        ):
            value = sum(
                _evidence_number(row.get(field), label=metric_id) for row in selected
            ) / len(selected)
            append(
                family="REDIM_ENROLLMENT_LIVE_V2",
                metric_id=metric_id,
                value=value,
                unit="ratio",
                source_id="speaker_enrollment_live:causal_summary",
                source_path=causal_path,
                source_sha=causal_sha,
            )
    configuration_rows = tuple(
        row
        for row in _read_csv_rows(configuration_path)
        if str(row.get("backend")) == backend_id
        and row.get("storage_bytes_per_speaker_float32") not in {None, ""}
        and row.get("stored_templates_per_speaker") not in {None, ""}
    )
    dimensions = {
        _evidence_number(
            row.get("storage_bytes_per_speaker_float32"), label="template bytes"
        )
        / _evidence_number(
            row.get("stored_templates_per_speaker"), label="stored templates"
        )
        / 4.0
        for row in configuration_rows
    }
    if dimensions != {192.0}:
        raise H2ProgramError(
            f"historical ReDimNet2 embedding dimension is ambiguous: {dimensions}"
        )
    append(
        family="REDIM_ENROLLMENT_LIVE_V2",
        metric_id="embedding_dimension",
        value=192.0,
        unit="dimensions",
        source_id=(
            "historical_reporting_sources:speaker_enrollment_configuration_results"
        ),
        source_path=configuration_path,
        source_sha=configuration_sha,
    )
    telemetry = json.loads(telemetry_path.read_text(encoding="utf-8-sig"))
    if not isinstance(telemetry, Mapping):
        raise H2ProgramError("historical enrollment telemetry is invalid")
    telemetry_rows = telemetry.get("rows")
    if not isinstance(telemetry_rows, list):
        raise H2ProgramError("historical enrollment telemetry rows are missing")
    telemetry_row = _one_historical_row(
        tuple(row for row in telemetry_rows if isinstance(row, Mapping)),
        label="ReDimNet2 runtime telemetry",
        predicate=lambda row: str(row.get("backend")) == backend_id,
    )
    append(
        family="REDIM_ENROLLMENT_LIVE_V2",
        metric_id="embedding_rtf",
        value=_evidence_number(
            telemetry_row.get("embedding_realtime_factor"), label="embedding RTF"
        ),
        unit="rtf",
        source_id="speaker_enrollment_live:runtime_telemetry",
        source_path=telemetry_path,
        source_sha=telemetry_sha,
    )
    return tuple(output), tuple(sources), manifest_sha


def _historical_evidence_reconciliation(
    paths: ProgramPaths,
    baseline_artifact: ResultArtifact,
) -> dict[str, object]:
    historical, sources, manifest_sha = _verified_historical_values(paths)
    current_rows = _metric_rows(baseline_artifact)

    def current_metric(metric_id: str) -> tuple[float | None, str | None]:
        matches = [
            row
            for row in current_rows
            if row.get("metric_id") == metric_id
            and str(row.get("metric_status") or "").casefold() == "computed"
            and isinstance(row.get("value"), (int, float))
            and not isinstance(row.get("value"), bool)
        ]
        if not matches:
            return None, None
        if len(matches) != 1:
            raise H2ProgramError(f"fresh H2 baseline metric is ambiguous: {metric_id}")
        return float(matches[0]["value"]), str(matches[0].get("unit") or "")

    correctly_named, _ = current_metric("correctly_named_known_rate")
    correctly_named_rows = [
        row
        for row in current_rows
        if row.get("metric_id") == "correctly_named_known_rate"
        and str(row.get("metric_status") or "").casefold() == "computed"
    ]
    known_denominator = (
        _evidence_number(
            correctly_named_rows[0].get("denominator"), label="fresh known duration"
        )
        if len(correctly_named_rows) == 1
        and correctly_named_rows[0].get("denominator") not in {None, ""}
        else None
    )
    wrong_known, _ = current_metric("wrong_known_time_sec")
    generic_known, _ = current_metric("generic_known_time_sec")
    fpir, _ = current_metric("fpir")
    current_values: dict[tuple[str, str], tuple[float, str]] = {}

    def set_current(
        family: str, historical_metric: str, metric_id: str, *, scale: float = 1.0
    ) -> None:
        value, unit = current_metric(metric_id)
        if value is not None:
            current_values[(family, historical_metric)] = (value * scale, unit or "")

    if correctly_named is not None:
        current_values[("FROZEN_H2_PRODUCT_V2", "correctly_named_known_time_rate")] = (
            correctly_named,
            "ratio",
        )
    if known_denominator is not None and known_denominator > 0:
        if wrong_known is not None:
            current_values[("FROZEN_H2_PRODUCT_V2", "wrong_known_time_rate")] = (
                wrong_known / known_denominator,
                "ratio",
            )
        if generic_known is not None:
            current_values[("FROZEN_H2_PRODUCT_V2", "generic_known_time_rate")] = (
                generic_known / known_denominator,
                "ratio",
            )
    set_current(
        "FROZEN_H2_PRODUCT_V2", "stable_name_latency_sec", "stable_name_latency_sec"
    )
    set_current(
        "FROZEN_H2_PRODUCT_V2", "unknown_label_consistency", "unknown_n_consistency"
    )
    if fpir is not None:
        current_values[("FROZEN_H2_PRODUCT_V2", "unknown_rejection_rate")] = (
            1.0 - fpir,
            "ratio",
        )
    for historical_metric, current_id in (
        ("der", "der"),
        ("jer", "jer"),
        ("miss_rate", "miss_rate"),
        ("false_alarm_rate", "false_alarm_rate"),
        ("speaker_confusion_rate", "speaker_confusion_rate"),
        ("reentry_consistency", "reentry_accuracy"),
    ):
        set_current("STANDALONE_PYANNOTE_REDIM", historical_metric, current_id)
    boundary, _ = current_metric("boundary_delay_sec")
    if boundary is not None:
        current_values[
            ("STANDALONE_PYANNOTE_REDIM", "median_absolute_boundary_delay_ms")
        ] = (1000.0 * boundary, "milliseconds")

    explanations = {
        "FROZEN_H2_PRODUCT_V2": (
            "The historical value came from held-out Product V2 causal hybrid "
            "replay without ASR. The fresh value comes from the development "
            "H2_BASELINE_REFERENCE through the true full-pipeline runtime and the "
            "current scorer. Different panels, inference paths, and metric "
            "implementations make the delta descriptive, not a causal regression."
        ),
        "STANDALONE_PYANNOTE_REDIM": (
            "The historical value came from 192 standalone controlled diarization "
            "recordings. The fresh value comes from the 180-case full-pipeline "
            "development baseline with online integration and ASR. Scope and "
            "runtime differ, so the delta is descriptive only."
        ),
        "REDIM_ENROLLMENT_LIVE_V2": (
            "The historical enrollment campaign was checksum-reverified rather "
            "than rerun. The new campaign performs only the predeclared integrated "
            "3-vs-5 utterance, 10-vs-20 second, session, aggregation, and quality "
            "confirmation; it does not replace these duration-curve values."
        ),
    }
    rows: list[dict[str, object]] = []
    for historical_row in historical:
        family = str(historical_row["evidence_family"])
        metric_id = str(historical_row["metric_id"])
        current = current_values.get((family, metric_id))
        historical_value = float(historical_row["historical_value"])
        current_value = current[0] if current is not None else None
        current_unit = current[1] if current is not None else None
        same_unit = (
            current is not None and current_unit == historical_row["historical_unit"]
        )
        rows.append(
            {
                **historical_row,
                "current_baseline_configuration_id": (
                    "H2_BASELINE_REFERENCE" if current is not None else None
                ),
                "current_value": current_value,
                "current_unit": current_unit,
                "descriptive_delta": (
                    current_value - historical_value if same_unit else None
                ),
                "comparability": (
                    "DESCRIPTIVE_ONLY_PROTOCOL_CHANGED"
                    if current is not None
                    else "HISTORICAL_REVERIFIED_NO_EQUIVALENT_CURRENT_METRIC"
                ),
                "difference_explanation": explanations[family]
                + (
                    " No same-unit current baseline statistic was emitted, so the "
                    "historical value is retained instead of being replaced."
                    if current is None
                    else ""
                ),
                "current_source_job_id": (
                    baseline_artifact.job.job_id if current is not None else None
                ),
                "current_source_result_sha256": (
                    baseline_artifact.sha256 if current is not None else None
                ),
            }
        )
    required_families = {
        "FROZEN_H2_PRODUCT_V2",
        "STANDALONE_PYANNOTE_REDIM",
        "REDIM_ENROLLMENT_LIVE_V2",
    }
    if {str(row["evidence_family"]) for row in rows} != required_families:
        raise H2ProgramError("historical reconciliation family membership differs")
    if not all(row.get("historical_value_verified") is True for row in rows):
        raise H2ProgramError("historical reconciliation contains unverified values")
    return {
        "schema_version": "h2-historical-evidence-reconciliation.v1",
        "status": "COMPLETE",
        "historical_manifest_sha256": manifest_sha,
        "historical_values_verified_against_machine_readable_artifacts": True,
        "historical_values_silently_replaced": False,
        "cross_protocol_deltas_used_for_selection": False,
        "source_bindings": list(sources),
        "rows": rows,
    }


def _configuration_registry(
    paths: ProgramPaths,
    state: Mapping[str, object],
    artifacts: Mapping[str, ResultArtifact],
) -> dict[str, object]:
    baseline_artifact = _artifact_for_configuration(artifacts, "H2_BASELINE_REFERENCE")
    if baseline_artifact is None:
        raise H2ProgramError("measured H2 baseline artifact is missing")
    baseline = dict(baseline_artifact.job.runtime_tuning)
    shared_assets = _component_assets(baseline_artifact)
    freeze = read_json(paths.freeze_path) if paths.freeze_path.is_file() else {}
    selected = freeze.get("selected_runtime")
    selected_runtime = dict(selected) if isinstance(selected, Mapping) else {}
    frozen_root = paths.summary_root / "frozen_configurations"
    mode_configs = {
        "H2_KNOWN_ONLY_OPTIMIZED": "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS_OPTIMIZED": "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_OPTIMIZED": "H2_SESSION_MEMORY_ENHANCED",
    }
    configurations: list[dict[str, object]] = [
        {
            "configuration_id": "H2_BASELINE_REFERENCE",
            "mode": "H2_SESSION_ANONYMOUS",
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "status": "FROZEN_HISTORICAL_REFERENCE_MEASURED",
            "runtime_tuning": baseline,
            "runtime_tuning_identity_sha256": canonical_sha256(baseline),
            "assets": shared_assets,
            "source_job_id": baseline_artifact.job.job_id,
            "source_result_sha256": baseline_artifact.sha256,
            "source_configuration_sha256": sha256_file(paths.config_path),
        }
    ]
    for configuration_id, mode in mode_configs.items():
        path = frozen_root / f"{mode}.json"
        if not path.is_file():
            raise H2ProgramError(f"frozen product configuration is missing: {path}")
        document = read_json(path)
        tuning = document.get("runtime_tuning")
        if not isinstance(tuning, Mapping):
            raise H2ProgramError(f"frozen product configuration lacks tuning: {path}")
        heldout_artifact = _artifact_for_configuration(artifacts, f"{mode}_HELDOUT")
        if heldout_artifact is None:
            raise H2ProgramError(
                f"frozen product configuration lacks held-out result: {mode}"
            )
        mode_assets = _component_assets(heldout_artifact)
        if not mode_assets:
            raise H2ProgramError(
                f"held-out product configuration lacks asset identities: {mode}"
            )
        configurations.append(
            {
                "configuration_id": configuration_id,
                "mode": mode,
                "pipeline_id": document.get("pipeline_id"),
                "status": "FROZEN_OPTIMIZED_MEASURED",
                "runtime_tuning": dict(tuning),
                "runtime_tuning_identity_sha256": document.get(
                    "runtime_tuning_identity_sha256"
                ),
                "assets": mode_assets,
                "freeze_identity_sha256": document.get("freeze_identity_sha256"),
                "source_path": path.relative_to(paths.summary_root).as_posix(),
                "source_sha256": sha256_file(path),
                "heldout_source_job_id": heldout_artifact.job.job_id,
                "heldout_source_result_sha256": heldout_artifact.sha256,
            }
        )
    configurations.append(
        {
            "configuration_id": "H2_PORTABLE_ONNX_FP32",
            "mode": "H2_SESSION_MEMORY_ENHANCED",
            "pipeline_id": "fullpipe_v1_ag_dr_ir",
            "status": "FROZEN_PORTABLE_CANDIDATE_PARITY_VALIDATED_NOT_ARM64_HARDWARE_VALIDATED",
            "runtime_tuning": selected_runtime.get("runtime_tuning") or {},
            "runtime_tuning_identity_sha256": selected_runtime.get(
                "runtime_tuning_identity_sha256"
            ),
            "assets": _portable_component_assets(artifacts),
            "freeze_identity_sha256": freeze.get("freeze_identity_sha256"),
            "arm64_hardware_validated": False,
        }
    )
    observed_ids = tuple(row["configuration_id"] for row in configurations)
    if observed_ids != FINAL_CONFIGURATION_IDS:
        raise H2ProgramError("final configuration registry membership differs")
    return {
        "schema_version": "h2-configuration-registry.v1",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "freeze_identity_sha256": freeze.get("freeze_identity_sha256"),
        "default_product_mode": freeze.get("default_product_mode"),
        "default_product_mode_selection": freeze.get("default_product_mode_selection"),
        "demo_runtime_binding": {
            "path": "frozen_configurations/h2_demo_runtime_binding.frozen.json",
            "sha256": sha256_file(frozen_root / "h2_demo_runtime_binding.frozen.json"),
        },
        "weighted_composite_used": False,
        "selection_policy": "ordered safety constraints and Pareto promotion",
        "configurations": configurations,
    }


def _policy_to_experiment(
    rows: Sequence[Mapping[str, object]],
    *,
    artifact: ResultArtifact,
    evidence_scope: str,
) -> tuple[dict[str, object], ...]:
    output: list[dict[str, object]] = []
    for row in rows:
        output.append(
            {
                "schema_version": "h2-normalized-experiment-row.v1",
                "evidence_scope": evidence_scope,
                "job_id": artifact.job.job_id,
                "job_kind": artifact.job.job_kind,
                "phase_index": artifact.job.phase_index,
                "split": artifact.job.split,
                "pipeline_id": artifact.job.pipeline_id,
                "mode": artifact.job.mode,
                "configuration_id": row.get("policy_id")
                or artifact.job.configuration_id,
                "source_status": row.get("status"),
                "selected": row.get("selected"),
                "metric_scope": row.get("metric_scope"),
                "metric_view": "policy",
                "metric_subview": "development",
                "metric_id": row.get("metric_id"),
                "metric_status": row.get("status"),
                "value": row.get("value"),
                "numerator": None,
                "denominator": None,
                "unit": None,
                "reason": row.get("reason"),
                "runtime_tuning_json": row.get("parameters_json") or "{}",
                "source_result_sha256": artifact.sha256,
                "source_record_json": row.get("source_record_json") or "{}",
            }
        )
    return tuple(output)


def _coverage_to_experiment(
    rows: Sequence[Mapping[str, object]],
    *,
    artifact: ResultArtifact,
) -> tuple[dict[str, object], ...]:
    """Expose declared coverage outcomes without turning unsupported into zero."""

    output: list[dict[str, object]] = []
    for raw in rows:
        row = {str(key): _coerce_scalar(value) for key, value in raw.items()}
        axis = str(row.get("axis") or "")
        value = row.get("value")
        status = str(row.get("status") or "")
        output.append(
            {
                "schema_version": "h2-normalized-experiment-row.v1",
                "evidence_scope": "DECLARED_EMBEDDING_CLUSTERING_COVERAGE",
                "job_id": artifact.job.job_id,
                "job_kind": artifact.job.job_kind,
                "phase_index": artifact.job.phase_index,
                "split": artifact.job.split,
                "pipeline_id": artifact.job.pipeline_id,
                "mode": artifact.job.mode,
                "configuration_id": row.get("cell_id"),
                "source_status": status,
                "selected": row.get("selected") is True,
                "metric_scope": "DECLARED_AXIS_CELL",
                "metric_view": "embedding_clustering_coverage",
                "metric_subview": axis,
                "metric_id": "coverage_outcome",
                "metric_status": status,
                # The candidate value is an axis declaration, not a measured
                # metric.  Keep it in runtime_tuning_json and never turn it
                # into a synthetic numeric result.
                "value": None,
                "numerator": None,
                "denominator": None,
                "unit": None,
                "reason": row.get("reason"),
                "runtime_tuning_json": _json_text(
                    {
                        "axis": axis,
                        "value": value,
                        "runtime_field": row.get("runtime_field"),
                        "matched_resource_evidence": row.get(
                            "matched_resource_evidence"
                        ),
                        "isolated_one_axis_comparison": row.get(
                            "isolated_one_axis_comparison"
                        ),
                    }
                ),
                "source_result_sha256": artifact.sha256,
                "source_record_json": _json_text(row),
            }
        )
    return tuple(output)


def _specialize_policy_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    evidence_scope: str,
    metric_tokens: Sequence[str],
    required_parameter_keys: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Return a claim-specific measured slice instead of aliasing a frontier.

    Several H2 studies share one causal replay, but the final machine tables
    must still expose the rows that actually support each claim.  This helper
    clones only semantically matching measurements and records the narrower
    evidence scope in every row.
    """

    output: list[dict[str, object]] = []
    normalized_tokens = tuple(value.casefold() for value in metric_tokens)
    for raw in rows:
        metric_id = str(raw.get("metric_id") or "").casefold()
        if normalized_tokens and not any(
            token in metric_id for token in normalized_tokens
        ):
            continue
        try:
            parameters = json.loads(str(raw.get("parameters_json") or "{}"))
        except json.JSONDecodeError:
            continue
        if not isinstance(parameters, Mapping) or any(
            key not in parameters for key in required_parameter_keys
        ):
            continue
        row = dict(raw)
        row["evidence_scope"] = evidence_scope
        output.append(row)
    if not output:
        raise H2ProgramError(
            f"no measured rows support required final study: {evidence_scope}"
        )
    return tuple(output)


def _policy_cell_subset(
    rows: Sequence[Mapping[str, object]],
    *,
    evidence_scope: str,
    required_parameters: Sequence[str],
    parameter_equals: Mapping[str, object] | None = None,
) -> tuple[dict[str, object], ...]:
    """Return exact named study cells, including explicit unsupported rows."""

    expected = dict(parameter_equals or {})
    output: list[dict[str, object]] = []
    for raw in rows:
        try:
            parameters = json.loads(str(raw.get("parameters_json") or "{}"))
        except json.JSONDecodeError:
            continue
        if not isinstance(parameters, Mapping) or any(
            key not in parameters for key in required_parameters
        ):
            continue
        if any(parameters.get(key) != value for key, value in expected.items()):
            continue
        row = dict(raw)
        row["evidence_scope"] = evidence_scope
        output.append(row)
    if not output:
        raise H2ProgramError(
            f"no named rows support required final study: {evidence_scope}"
        )
    return tuple(output)


def _experiment_metric_subset(
    rows: Sequence[Mapping[str, object]],
    *,
    evidence_scope: str,
    metric_ids: Iterable[str] = (),
    metric_tokens: Iterable[str] = (),
    require_computed: bool = True,
) -> tuple[dict[str, object], ...]:
    exact = {value.casefold() for value in metric_ids}
    tokens = tuple(value.casefold() for value in metric_tokens)
    output: list[dict[str, object]] = []
    for raw in rows:
        metric_id = str(raw.get("metric_id") or "").casefold()
        if exact or tokens:
            if metric_id not in exact and not any(
                token in metric_id for token in tokens
            ):
                continue
        status = str(raw.get("metric_status") or "").casefold()
        if require_computed and status not in {"computed", "measured"}:
            continue
        row = dict(raw)
        row["evidence_scope"] = evidence_scope
        output.append(row)
    if not output:
        raise H2ProgramError(
            f"no measured rows support required final study: {evidence_scope}"
        )
    return tuple(output)


def _long_session_rows(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[dict[str, object], ...]:
    values = _long_session_artifacts(artifacts)
    if not values:
        return ()
    output: list[dict[str, object]] = []
    for artifact in values:
        source = _supporting_rows(artifact, "long_session_results.jsonl")
        for raw in source:
            measurements = raw.get("measurements")
            scalar_measurements = [
                (path, value)
                for path, value in _walk_items(measurements)
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            ]
            if not scalar_measurements:
                scalar_measurements = [("record", None)]
            for path, value in scalar_measurements:
                output.append(
                    {
                        "schema_version": "h2-normalized-experiment-row.v1",
                        "evidence_scope": (
                            "FROZEN_EVALUATION_LONG_SESSION"
                            if artifact.job.split == "evaluation"
                            else "CONTROLLED_PRERECORDED_DEVELOPMENT_LONG_SESSION"
                        ),
                        "job_id": artifact.job.job_id,
                        "job_kind": artifact.job.job_kind,
                        "phase_index": artifact.job.phase_index,
                        "split": artifact.job.split,
                        "pipeline_id": artifact.job.pipeline_id,
                        "mode": artifact.job.mode,
                        "configuration_id": raw.get("stream_id"),
                        "source_status": raw.get("harness_status"),
                        "selected": True,
                        "metric_scope": "PER_LONG_STREAM",
                        "metric_view": "long_session",
                        "metric_subview": raw.get("stream_id"),
                        "metric_id": _normal_key(path),
                        "metric_status": (
                            "computed" if value is not None else "unsupported"
                        ),
                        "value": value,
                        "numerator": None,
                        "denominator": None,
                        "unit": None,
                        "reason": raw.get("harness_error"),
                        "runtime_tuning_json": _json_text(
                            dict(artifact.job.runtime_tuning)
                        ),
                        "source_result_sha256": artifact.sha256,
                        "source_record_json": _json_text(raw),
                    }
                )
    return tuple(output)


def _long_session_artifacts(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[ResultArtifact, ...]:
    return tuple(
        artifact
        for artifact in artifacts.values()
        if artifact.job.job_kind in {"long_session", "long_session_evaluation"}
        and artifact.artifact_kind != "superseded"
    )


def _long_session_completion_contract(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[bool, str]:
    """Require the frozen 4-source dev and 8-source evaluation campaigns."""

    values = _long_session_artifacts(artifacts)
    expected = {
        "development": (4, 8, "long_session"),
        "evaluation": (8, 16, "long_session_evaluation"),
    }
    failures: list[str] = []
    details: list[str] = []
    for split, (source_count, stream_count, job_kind) in expected.items():
        matching = [
            artifact
            for artifact in values
            if artifact.job.split == split and artifact.job.job_kind == job_kind
        ]
        if len(matching) != 1:
            failures.append(f"{split}: expected one {job_kind} result")
            continue
        artifact = matching[0]
        if artifact.root is None:
            failures.append(f"{split}: result root missing")
            continue
        plan_path = artifact.root / "long_session_source_plan.json"
        result_rows = _supporting_rows(artifact, "long_session_results.jsonl")
        if not plan_path.is_file():
            failures.append(f"{split}: source plan missing")
            continue
        plan = read_json(plan_path)
        document = artifact.document or {}
        outcome = document.get("outcome")
        outcome_map = outcome if isinstance(outcome, Mapping) else {}
        valid = (
            plan.get("split") == split
            and plan.get("source_count") == source_count
            and plan.get("stream_count") == stream_count
            and len(result_rows) == stream_count
            and all(row.get("harness_status") == "PASS" for row in result_rows)
            and outcome_map.get("status") == "COMPLETE"
            and outcome_map.get("expected_subtests") == stream_count
            and outcome_map.get("completed_subtests") == stream_count
            and outcome_map.get("pass_count") == stream_count
            and outcome_map.get("fail_count") == 0
            and plan.get("evaluation_material_inspected_for_selection") is False
            and (
                split != "evaluation"
                or (
                    plan.get("heldout_execution_opened_after_freeze") is True
                    and plan.get("no_recalibration") is True
                )
            )
        )
        if not valid:
            failures.append(f"{split}: source/stream/pass/freeze contract differs")
        details.append(
            f"{split} sources={plan.get('source_count')}, "
            f"streams={len(result_rows)}, passes={outcome_map.get('pass_count')}"
        )
    return not failures, "; ".join(failures or details)


def _missing_policy_rows(
    spec: Mapping[str, object],
    observed: set[str],
    *,
    protocol_sha256: str | None,
) -> tuple[dict[str, object], ...]:
    development = spec.get("development_search")
    if not isinstance(development, Mapping):
        return ()
    policies = tuple(map(str, development.get("overlap_policies") or ()))
    support = development.get("overlap_runtime_support")
    gated = (
        set(map(str, support.get("gated_not_scheduled_until_connected") or ()))
        if isinstance(support, Mapping)
        else set()
    )
    rows: list[dict[str, object]] = []
    for policy in policies:
        if policy in observed:
            continue
        rows.append(
            {
                "schema_version": "h2-normalized-experiment-row.v1",
                "evidence_scope": "DECLARED_OVERLAP_POLICY",
                "job_id": "NOT_SCHEDULED",
                "job_kind": "overlap_policy",
                "phase_index": 1,
                "split": "development",
                "pipeline_id": "fullpipe_v1_ag_dr_ir",
                "mode": "H2_SESSION_MEMORY_ENHANCED",
                "configuration_id": policy,
                "source_status": (
                    "UNSUPPORTED_CAPABILITY" if policy in gated else "NOT_RUN"
                ),
                "selected": False,
                "metric_scope": "POLICY_LEVEL",
                "metric_view": "overlap",
                "metric_subview": policy,
                "metric_id": "job_status",
                "metric_status": (
                    "UNSUPPORTED_CAPABILITY" if policy in gated else "NOT_RUN"
                ),
                "value": None,
                "numerator": None,
                "denominator": None,
                "unit": None,
                "reason": (
                    "protocol-bound capability limitation; no metric was fabricated"
                    if policy in gated
                    else "no measured result artifact"
                ),
                "runtime_tuning_json": _json_text({"overlap_policy": policy}),
                "source_result_sha256": protocol_sha256 if policy in gated else None,
                "source_record_json": _json_text(
                    {
                        "policy": policy,
                        "status": (
                            "UNSUPPORTED_CAPABILITY" if policy in gated else "NOT_RUN"
                        ),
                        "protocol_sha256": protocol_sha256,
                        "metrics_computed": False,
                        "synthetic_metrics_emitted": False,
                    }
                ),
            }
        )
    return tuple(rows)


def _build_analysis_tables(
    paths: ProgramPaths,
    state: Mapping[str, object],
    artifacts: Mapping[str, ResultArtifact],
) -> Mapping[str, tuple[dict[str, object], ...]]:
    selected = _selected_configurations(state, artifacts)
    spec = read_yaml(paths.config_path)
    phase1 = tuple(
        value
        for value in artifacts.values()
        if value.job.phase_index == 1
        and value.job.job_kind == "successive_halving_runtime"
        and value.artifact_kind != "superseded"
    )
    boundary = tuple(
        value
        for value in artifacts.values()
        if value.job.configuration_id.startswith("BOUNDARY_CORRECTION_")
        and value.artifact_kind != "superseded"
    )
    overlap_artifacts = tuple(
        value
        for value in artifacts.values()
        if value.job.configuration_id
        in {
            "INCLUDE_PREDICTED_OVERLAP",
            "EXCLUDE_PREDICTED_OVERLAP_FROM_IDENTITY",
            "DEFER_IDENTITY_UNTIL_NON_OVERLAP",
            "DISPLAY_OVERLAPPING_SPEAKERS_WHEN_AMBIGUOUS",
        }
        and value.artifact_kind != "superseded"
    )
    embedding = tuple(
        value
        for value in artifacts.values()
        if re.match(r"W\d{3}_H\d{3}", value.job.configuration_id)
        and value.artifact_kind != "superseded"
    )
    sharing = tuple(
        value
        for value in artifacts.values()
        if value.job.configuration_id.startswith(("R1_", "R2_"))
        and value.artifact_kind != "superseded"
    )
    policy = _artifact_for_kind(artifacts, "policy_replay")
    memory = _artifact_for_kind(artifacts, "memory_policy_replay")
    short = _artifact_for_kind(artifacts, "short_turn_replay")
    transcript_policy = _artifact_for_kind(artifacts, "transcript_policy_replay")
    bootstrap = _artifact_for_kind(artifacts, "bootstrap")
    if not all(
        len(values) == 1
        for values in (policy, memory, short, transcript_policy, bootstrap)
    ):
        raise H2ProgramError("one or more singleton science result jobs are missing")
    policy_doc = policy[0].document or {}
    memory_doc = memory[0].document or {}
    short_doc = short[0].document or {}
    transcript_doc = transcript_policy[0].document or {}
    identity_rows = _policy_rows(
        policy[0],
        ("open_set_policy_frontier.csv",),
        selected_record=(
            policy_doc.get("selected_policy")
            if isinstance(policy_doc.get("selected_policy"), Mapping)
            else None
        ),
        evidence_scope="OPEN_SET_IDENTITY_POLICY",
        parameter_keys=(
            "gallery_requested_size",
            "target_fpir",
            "score_threshold",
            "margin_threshold",
            "minimum_evidence_sec",
            "minimum_embedding_consistency",
        ),
    )
    memory_rows = _policy_rows(
        memory[0],
        ("memory_policy_frontier.csv",),
        selected_record=(
            memory_doc.get("selected_frontier_row")
            if isinstance(memory_doc.get("selected_frontier_row"), Mapping)
            else None
        ),
        evidence_scope="HYSTERESIS_AND_SESSION_MEMORY",
        parameter_keys=(
            "cell_type",
            "cell_id",
            "hysteresis_policy",
            "memory_level",
            "consecutive_passes_to_confirm",
            "consecutive_failures_to_release",
            "hysteresis",
            "identity_expiry_sec",
            "identity_expiry_mode",
            "confidence_decay_half_life_sec",
            "confidence_decay_release_floor",
            "cluster_reconciliation_threshold",
            "cluster_reconciliation_max_gap_sec",
            "cluster_reconciliation_min_embeddings",
        ),
    )
    short_rows = _policy_rows(
        short[0],
        ("short_turn_replay_frontier.csv",),
        selected_record=(
            short_doc.get("selected_frontier_row")
            if isinstance(short_doc.get("selected_frontier_row"), Mapping)
            else None
        ),
        evidence_scope="SHORT_TURN_AND_REENTRY",
        parameter_keys=(
            "cell_id",
            "short_turn_policy",
            "duration_bin",
            "short_turn_inheritance_max_sec",
            "retroactive_correction_sec",
        ),
    )
    transcript_rows = _policy_rows(
        transcript_policy[0],
        ("transcript_policy_frontier.csv", "boundary_overlap_selection_evidence.csv"),
        selected_record=(
            transcript_doc.get("selected_frontier_row")
            if isinstance(transcript_doc.get("selected_frontier_row"), Mapping)
            else None
        ),
        evidence_scope="TRANSCRIPT_POLICY",
        parameter_keys=("paragraph_policy", "axis", "selected_value"),
    )
    mode_artifacts = tuple(
        value
        for value in artifacts.values()
        if value.job.configuration_id
        in {
            "H2_KNOWN_ONLY_HELDOUT",
            "H2_SESSION_ANONYMOUS_HELDOUT",
            "H2_SESSION_MEMORY_ENHANCED_HELDOUT",
        }
    )
    mode_rows = _experiment_rows(
        mode_artifacts, selected=selected, default_scope="HELD_OUT_MODE_COMPARISON"
    )
    paragraph_artifacts = _artifact_for_kind(
        artifacts, "post_selection_paragraph_validation"
    )
    transcript_experiment = list(
        _experiment_rows(
            paragraph_artifacts,
            selected=selected,
            default_scope="DEVELOPMENT_TRANSCRIPT_RUNTIME",
        )
    )
    transcript_experiment.extend(
        _policy_to_experiment(
            transcript_rows,
            artifact=transcript_policy[0],
            evidence_scope="DEVELOPMENT_TRANSCRIPT_POLICY",
        )
    )
    ui_ids = {
        "time_to_first_text_sec",
        "time_to_stable_text_sec",
        "time_to_first_anonymous_label_sec",
        "time_to_tentative_known_name_sec",
        "time_to_confirmed_known_name_sec",
        "stable_name_latency_sec",
        "wrong_name_dwell_sec",
        "transcript_revision_count",
        "ux_identity_revision_count",
        "ui_event_lag_sec",
        "dropped_audio_sec",
        "stall_time_sec",
    }
    ui_rows = tuple(row for row in mode_rows if row.get("metric_id") in ui_ids)
    resource_artifacts = _artifact_for_kind(
        artifacts, "post_selection_resource_runtime"
    )
    resource_rows = _experiment_rows(
        resource_artifacts,
        selected=selected,
        default_scope="SERIAL_MATCHED_RESOURCE",
    )
    parity_rows = _parity_rows(
        _artifact_for_kind(artifacts, "embedding_reuse_parity"), portability=False
    )
    onnx_rows = _parity_rows(
        _artifact_for_kind(artifacts, "onnx_parity"), portability=True
    )
    observed_overlap = {value.job.configuration_id for value in overlap_artifacts}
    protocol_sha256: str | None = None
    unsupported_overlap, _overlap_reason = _overlap_capability_contract(paths)
    if unsupported_overlap:
        protocol_document = read_json(paths.protocol_path)
        raw_protocol_sha = protocol_document.get("protocol_sha256")
        if isinstance(raw_protocol_sha, str):
            protocol_sha256 = raw_protocol_sha
    overlap_rows = list(
        _experiment_rows(
            overlap_artifacts,
            selected=selected,
            default_scope="DEVELOPMENT_OVERLAP_POLICY",
        )
    )
    overlap_rows.extend(
        _missing_policy_rows(
            spec,
            observed_overlap,
            protocol_sha256=protocol_sha256,
        )
    )
    bootstrap_rows = _supporting_rows(bootstrap[0], "bootstrap_intervals.csv")
    hysteresis_rows = _policy_cell_subset(
        memory_rows,
        evidence_scope="HYSTERESIS_CONFIRMATION_STUDY",
        required_parameters=(
            "hysteresis_policy",
            "identity_expiry_sec",
        ),
        parameter_equals={"cell_type": "named_hysteresis"},
    )
    session_memory_rows = _policy_cell_subset(
        memory_rows,
        evidence_scope="CAUSAL_SESSION_MEMORY_STUDY",
        required_parameters=(
            "memory_level",
            "identity_expiry_sec",
        ),
        parameter_equals={"cell_type": "memory_level"},
    )
    short_turn_rows = _policy_cell_subset(
        short_rows,
        evidence_scope="SHORT_TURN_INHERITANCE_STUDY",
        required_parameters=("short_turn_policy", "duration_bin"),
    )
    expiry_rows = _policy_cell_subset(
        memory_rows,
        evidence_scope="SOURCE_CLOCK_EXPIRY_DECAY_STUDY",
        required_parameters=(
            "hysteresis_policy",
            "identity_expiry_sec",
        ),
        parameter_equals={"cell_type": "named_hysteresis"},
    )
    heldout_reentry_rows = _experiment_metric_subset(
        mode_rows,
        evidence_scope="FROZEN_WARM_REENTRY_STUDY",
        metric_ids=("reentry_accuracy", "warm_identity_accuracy"),
    )
    causal_reentry_rows = _specialize_policy_rows(
        session_memory_rows,
        evidence_scope="CAUSAL_DEVELOPMENT_REENTRY_STUDY",
        metric_tokens=("reentry", "returning_turn", "fragmentation"),
        required_parameter_keys=("memory_level", "identity_expiry_sec"),
    )
    reentry_rows = (*heldout_reentry_rows, *causal_reentry_rows)
    active_roster_bounds = _experiment_metric_subset(
        _long_session_rows(artifacts),
        evidence_scope="LONG_SESSION_ACTIVE_ROSTER_BOUNDS",
        metric_tokens=(
            "roster_count",
            "maximum_roster_entries",
            "session_memory_history_count",
            "maximum_session_event_history",
        ),
    )
    active_roster_policy_rows = tuple(
        row
        for row in _specialize_policy_rows(
            session_memory_rows,
            evidence_scope="CAUSAL_DEVELOPMENT_ACTIVE_ROSTER_SAFETY",
            metric_tokens=(
                "active_roster",
                "new_speaker_lockout",
                "full_gallery_completion",
                "false_inheritance",
                "correct_known",
                "wrong_known",
                "stranger_false_known",
            ),
            required_parameter_keys=("memory_level", "identity_expiry_sec"),
        )
        if json.loads(str(row.get("parameters_json") or "{}")).get("memory_level")
        in {"M4_ACTIVE_ROSTER_DECAY", "M5_CLUSTER_RECONCILIATION"}
    )
    if not active_roster_policy_rows:
        raise H2ProgramError(
            "no measured M4/M5 active-roster safety rows were produced"
        )
    active_roster_rows = (*active_roster_policy_rows, *active_roster_bounds)
    causal_expiry_rows = _specialize_policy_rows(
        session_memory_rows,
        evidence_scope="CAUSAL_SOURCE_CLOCK_EXPIRY_DECAY_STUDY",
        metric_tokens=("expiry", "decay", "stale"),
        required_parameter_keys=("memory_level", "identity_expiry_sec"),
    )
    expiry_rows = (*expiry_rows, *causal_expiry_rows)
    final_summary = tuple(
        row
        for row in mode_rows
        if row.get("metric_scope") == "END_TO_END"
        or str(row.get("metric_scope") or "").startswith("CONDITIONAL:")
    )
    return {
        "h2_segmentation_frontier.csv": _experiment_rows(
            phase1, selected=selected, default_scope="DEVELOPMENT_SEGMENTATION_FRONTIER"
        ),
        "h2_boundary_results.csv": _experiment_rows(
            boundary, selected=selected, default_scope="DEVELOPMENT_BOUNDARY_WINDOWS"
        ),
        "h2_overlap_results.csv": tuple(overlap_rows),
        "h2_embedding_policy_results.csv": (
            *_experiment_rows(
                embedding,
                selected=selected,
                default_scope="DEVELOPMENT_EMBEDDING_FRONTIER",
            ),
            *_coverage_to_experiment(
                _supporting_rows(policy[0], "embedding_clustering_coverage.csv"),
                artifact=policy[0],
            ),
        ),
        "h2_model_sharing_results.csv": _experiment_rows(
            sharing, selected=selected, default_scope="SERIAL_MODEL_SHARING"
        ),
        "h2_embedding_reuse_parity.csv": parity_rows,
        "h2_identity_policy_results.csv": identity_rows,
        "h2_hysteresis_results.csv": hysteresis_rows,
        "h2_session_memory_results.csv": session_memory_rows,
        "h2_short_turn_results.csv": short_turn_rows,
        "h2_reentry_results.csv": reentry_rows,
        "h2_expiry_results.csv": expiry_rows,
        "h2_active_roster_results.csv": active_roster_rows,
        "h2_mode_comparison.csv": mode_rows,
        "h2_transcript_results.csv": tuple(transcript_experiment),
        "h2_ui_latency_results.csv": ui_rows,
        "h2_resource_results.csv": resource_rows,
        "h2_long_session_results.csv": _long_session_rows(artifacts),
        "h2_onnx_parity.csv": onnx_rows,
        "h2_final_summary.csv": final_summary,
        "bootstrap_intervals.csv": tuple(dict(row) for row in bootstrap_rows),
    }


def _failure_inventory(
    artifacts: Mapping[str, ResultArtifact],
    metric_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for artifact in sorted(artifacts.values(), key=lambda item: item.job.job_id):
        if artifact.artifact_kind == "superseded":
            rows.append(
                {
                    "schema_version": "h2-failure-inventory-row.v1",
                    "scope": "PROMOTION_DECISION",
                    "job_id": artifact.job.job_id,
                    "configuration_id": artifact.job.configuration_id,
                    "mode": artifact.job.mode,
                    "artifact": "",
                    "metric_view": "",
                    "metric_subview": "",
                    "metric_id": "",
                    "status": "SUPERSEDED",
                    "reason": artifact.state_row.get("latest_activity")
                    or "not advanced by development-only promotion",
                    "source_result_sha256": None,
                }
            )
            continue
        document = artifact.document
        if isinstance(document, Mapping):
            status = str(document.get("status") or "")
            if status and status not in {
                "COMPLETE",
                "PASS",
                "PARITY_PASS",
                "E2E_CONTRACT_PARITY_PASS",
                "DIAGNOSTIC_PASS",
                "PREPARED",
            }:
                rows.append(
                    {
                        "schema_version": "h2-failure-inventory-row.v1",
                        "scope": "JOB_RESULT_STATUS",
                        "job_id": artifact.job.job_id,
                        "configuration_id": artifact.job.configuration_id,
                        "mode": artifact.job.mode,
                        "artifact": str(artifact.path or ""),
                        "metric_view": "",
                        "metric_subview": "",
                        "metric_id": "",
                        "status": status,
                        "reason": document.get("reason") or document.get("error"),
                        "source_result_sha256": artifact.sha256,
                    }
                )
        if artifact.root is not None:
            case_status_path = artifact.root / "diagnostics/case_status.jsonl"
            if case_status_path.is_file():
                for raw in _read_jsonl_any(case_status_path):
                    status = str(raw.get("status") or raw.get("completion_state") or "")
                    if status.casefold() in {"complete", "pass", "computed"}:
                        continue
                    rows.append(
                        {
                            "schema_version": "h2-failure-inventory-row.v1",
                            "scope": "RUNTIME_CASE",
                            "job_id": artifact.job.job_id,
                            "configuration_id": artifact.job.configuration_id,
                            "mode": artifact.job.mode,
                            "artifact": "diagnostics/case_status.jsonl",
                            "metric_view": "",
                            "metric_subview": str(raw.get("case_id") or ""),
                            "metric_id": "",
                            "status": status or "UNDEFINED",
                            "reason": raw.get("error")
                            or raw.get("reason")
                            or raw.get("errors"),
                            "source_result_sha256": artifact.sha256,
                        }
                    )
            reliability_path = artifact.root / "reliability_results.jsonl"
            if reliability_path.is_file():
                for raw in _read_jsonl_any(reliability_path):
                    status = str(raw.get("harness_status") or "")
                    if status == "PASS":
                        continue
                    rows.append(
                        {
                            "schema_version": "h2-failure-inventory-row.v1",
                            "scope": "RELIABILITY_SUBTEST",
                            "job_id": artifact.job.job_id,
                            "configuration_id": artifact.job.configuration_id,
                            "mode": artifact.job.mode,
                            "artifact": "reliability_results.jsonl",
                            "metric_view": "reliability",
                            "metric_subview": str(raw.get("fault_id") or ""),
                            "metric_id": "",
                            "status": status or "UNDEFINED",
                            "reason": raw.get("unsupported_reason") or raw.get("error"),
                            "source_result_sha256": artifact.sha256,
                        }
                    )
            for filename in (
                "embedding_clustering_coverage.csv",
                "integrated_enrollment_matrix.csv",
                "memory_policy_frontier.csv",
                "short_turn_replay_frontier.csv",
            ):
                for raw in _supporting_rows(artifact, filename):
                    status = str(raw.get("status") or "").upper()
                    if status not in {
                        "UNSUPPORTED_CAPABILITY",
                        "NOT_RUN",
                        "FAILED",
                    }:
                        continue
                    rows.append(
                        {
                            "schema_version": "h2-failure-inventory-row.v1",
                            "scope": "DECLARED_CAPABILITY",
                            "job_id": artifact.job.job_id,
                            "configuration_id": artifact.job.configuration_id,
                            "mode": artifact.job.mode,
                            "artifact": filename,
                            "metric_view": str(raw.get("study_id") or "capability"),
                            "metric_subview": str(raw.get("cell_id") or ""),
                            "metric_id": str(raw.get("axis") or "capability_outcome"),
                            "status": status,
                            "reason": raw.get("reason"),
                            "source_result_sha256": artifact.sha256,
                        }
                    )
    for raw in metric_rows:
        status = str(raw.get("metric_status") or "")
        if status.casefold() == "computed":
            continue
        rows.append(
            {
                "schema_version": "h2-failure-inventory-row.v1",
                "scope": "DECLARED_METRIC",
                "job_id": raw.get("job_id"),
                "configuration_id": raw.get("configuration_id"),
                "mode": raw.get("mode"),
                "artifact": f"metrics/{raw.get('metric_view')}.json",
                "metric_view": raw.get("metric_view"),
                "metric_subview": raw.get("metric_subview"),
                "metric_id": raw.get("metric_id"),
                "status": status or "UNDEFINED",
                "reason": raw.get("reason") or "metric was not computed",
                "source_result_sha256": raw.get("source_result_sha256"),
            }
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: tuple(
                str(row.get(key) or "")
                for key in (
                    "scope",
                    "job_id",
                    "metric_view",
                    "metric_subview",
                    "metric_id",
                    "status",
                )
            ),
        )
    )


def _result_inventory(
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for artifact in sorted(artifacts.values(), key=lambda item: item.job.job_id):
        size: int | None
        if artifact.path is None:
            size = None
        elif artifact.path.is_file():
            size = artifact.path.stat().st_size
        elif artifact.root is not None and (artifact.root / "checksums.json").is_file():
            size = sum(
                path.stat().st_size
                for path in artifact.root.rglob("*")
                if path.is_file()
            )
        else:
            size = None
        rows.append(
            {
                "schema_version": "h2-result-file-inventory-row.v1",
                "job_id": artifact.job.job_id,
                "job_kind": artifact.job.job_kind,
                "configuration_id": artifact.job.configuration_id,
                "state": artifact.state_row.get("state"),
                "artifact_kind": artifact.artifact_kind,
                "path": str(artifact.path) if artifact.path is not None else None,
                "sha256": artifact.sha256,
                "bytes": size,
                "validated": artifact.validated,
            }
        )
    return tuple(rows)


def _cache_inventory(
    paths: ProgramPaths, artifacts: Mapping[str, ResultArtifact]
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for artifact in sorted(artifacts.values(), key=lambda item: item.job.job_id):
        cache_regime = (
            artifact.root / "diagnostics/cache_regime.json"
            if artifact.root is not None
            else None
        )
        rows.append(
            {
                "job_id": artifact.job.job_id,
                "configuration_id": artifact.job.configuration_id,
                "cache_hits": int(artifact.state_row.get("cache_hits") or 0),
                "cache_regime_sha256": (
                    sha256_file(cache_regime)
                    if cache_regime is not None and cache_regime.is_file()
                    else None
                ),
                "cached_payload_included_in_package": False,
            }
        )
    return {
        "schema_version": "h2-cache-inventory.v1",
        "cache_root": str(
            paths.evaluation_root / "JustPeachyResults/full_pipeline/_shared_cache"
        ),
        "cache_payloads_included": False,
        "total_controller_cache_hits": sum(int(row["cache_hits"]) for row in rows),
        "jobs": rows,
    }


def _linux_portability_document(
    artifacts: Mapping[str, ResultArtifact],
) -> dict[str, object]:
    values = _artifact_for_kind(artifacts, "linux_portability")
    if len(values) != 1 or not isinstance(values[0].document, Mapping):
        raise H2ProgramError("one completed Linux portability result is required")
    source = values[0].document
    diagnostic = source.get("desktop_preparation_diagnostic")
    dependency_support = (
        diagnostic.get("dependency_support")
        if isinstance(diagnostic, Mapping)
        else None
    )
    return {
        "schema_version": "h2-linux-portability-analysis.v1",
        "status": "PREPARED_NOT_HARDWARE_VALIDATED",
        "source_job_id": values[0].job.job_id,
        "source_result_sha256": values[0].sha256,
        "candidate_classification": source.get("candidate_classification"),
        "package_file_set_sha256": source.get("package_file_set_sha256"),
        "component_graph_sha256": source.get("component_graph_sha256"),
        "component_parity_report_sha256": source.get("component_parity_report_sha256"),
        "dependency_support": dependency_support or [],
        "remaining_hardware_gate": source.get("remaining_hardware_gate"),
        "linux_arm64_ready_claimed": False,
        "raspberry_pi_hardware_validated": False,
        "arduino_uno_q_linux_hardware_validated": False,
        "arm64_audio_capture_validated": False,
        "arm64_sustained_streaming_validated": False,
    }


def _memory_budget_document(
    resource_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    measured_peaks = [
        float(row["value"])
        for row in resource_rows
        if row.get("metric_id") == "peak_rss_bytes"
        and str(row.get("metric_status")).casefold() == "computed"
        and isinstance(row.get("value"), (int, float))
        and not isinstance(row.get("value"), bool)
    ]
    maximum = max(measured_peaks) if measured_peaks else None
    if maximum is None:
        raise H2ProgramError(
            "2 GB classification requires measured serial peak_rss_bytes evidence"
        )
    classification = (
        "HIGH_RISK_FOR_2GB"
        if maximum > 1700 * 1024**2
        else "POSSIBLY_2GB_FEASIBLE_AFTER_OPTIMIZATION"
    )
    return {
        **two_gib_budget(),
        "analysis_schema_version": "h2-memory-budget-analysis.v1",
        "classification": classification,
        "desktop_serial_peak_rss_bytes": maximum,
        "desktop_resource_row_count": len(resource_rows),
        "classification_uses_desktop_rss_alone": False,
        "arm64_hardware_measured": False,
        "swap_behavior_measured_on_target": False,
        "final_target_gate": (
            "Measure whole-system RSS, startup peak, audio services, swap, and "
            "60-minute sustained streaming on the exact 2 GB ARM64 target."
        ),
    }


def _metric_guide() -> str:
    lines = [
        "# H2 metric guide",
        "",
        "Every metric retains its declared status. `unsupported`, `undefined`, "
        "`NOT_RUN`, and `NOT_APPLICABLE` are not converted to zero. Conditional "
        "subviews remain separate from `END_TO_END`; this package never pools them.",
        "",
        "Rates are fractions unless the unit says percent. Latencies and durations "
        "are seconds. Raw cosine scores and margins are similarity statistics, not "
        "probabilities. Configuration choice uses ordered safety constraints and "
        "Pareto reasoning; no weighted composite score is emitted.",
        "",
        "| Metric ID | Category | Unit | Direction | Definition |",
        "|---|---|---|---|---|",
    ]
    for metric_id, definition in sorted(METRIC_CATALOG.items()):
        direction = (
            "higher is better"
            if definition.higher_is_better is True
            else (
                "lower is better"
                if definition.higher_is_better is False
                else "context-dependent"
            )
        )
        description = definition.description.replace("|", "\\|")
        lines.append(
            f"| `{metric_id}` | {definition.category} | {definition.unit} | "
            f"{direction} | {description} |"
        )
    lines.extend(
        [
            "",
            "## Bootstrap interpretation",
            "",
            "Key held-out intervals use seed 3800 and resample reference speakers, "
            "then cases within speaker. Multi-speaker cases receive fractional "
            "speaker contribution. Confidence intervals describe protocol sampling "
            "uncertainty; they do not establish ARM64 hardware performance.",
        ]
    )
    return "\n".join(lines) + "\n"


def _computed_metric(
    rows: Sequence[Mapping[str, object]],
    *,
    mode: str | None,
    metric_id: str,
    configuration_id: str | None = None,
) -> float | None:
    candidates = [
        row
        for row in rows
        if row.get("metric_id") == metric_id
        and str(row.get("metric_status") or row.get("status") or "").casefold()
        in {"computed", "measured"}
        and (mode is None or row.get("mode") == mode)
        and (
            configuration_id is None or row.get("configuration_id") == configuration_id
        )
        and isinstance(row.get("value"), (int, float))
        and not isinstance(row.get("value"), bool)
    ]
    if not candidates:
        return None
    end_to_end = [row for row in candidates if row.get("metric_scope") == "END_TO_END"]
    selected = end_to_end or candidates
    return float(selected[0]["value"])


def _format_value(value: float | None, *, percent: bool = False) -> str:
    if value is None:
        return "UNSUPPORTED"
    if percent:
        return f"{100.0 * value:.2f}%"
    return f"{value:.4g}"


def _default_mode_recommendation(
    frozen_policy: Mapping[str, object],
) -> tuple[str | None, str]:
    selection = frozen_policy.get("default_product_mode_selection")
    if not isinstance(selection, Mapping):
        return None, "frozen development default-mode selection is missing"
    unsigned = dict(selection)
    supplied_sha = unsigned.pop("selection_identity_sha256", None)
    selected = selection.get("selected_default_mode")
    modes = {
        "H2_KNOWN_ONLY",
        "H2_SESSION_ANONYMOUS",
        "H2_SESSION_MEMORY_ENHANCED",
    }
    if (
        supplied_sha != canonical_sha256(unsigned)
        or selection.get("development_only") is not True
        or selection.get("evaluation_material_inspected") is not False
        or selection.get("weighted_composite_used") is not False
        or selected not in modes
        or frozen_policy.get("default_product_mode") != selected
    ):
        return None, "frozen development default-mode selection is invalid"
    priority = selection.get("common_metric_priority")
    priority_text = (
        ", ".join(map(str, priority)) if isinstance(priority, list) else "UNAVAILABLE"
    )
    return str(selected), (
        "checksum-frozen before held-out evaluation from matched development "
        "results using declared lexicographic priorities: "
        + priority_text
        + "; held-out mode metrics are confirmation evidence only"
    )


def _delta(
    rows: Sequence[Mapping[str, object]],
    metric_id: str,
    left_mode: str,
    right_mode: str,
) -> str:
    left = _computed_metric(rows, mode=left_mode, metric_id=metric_id)
    right = _computed_metric(rows, mode=right_mode, metric_id=metric_id)
    if left is None or right is None:
        return "UNSUPPORTED"
    return f"{right - left:+.4g} ({right:.4g} vs {left:.4g})"


def _selected_policy_description(
    rows: Sequence[Mapping[str, object]],
) -> str:
    selected = [row for row in rows if row.get("selected") is True]
    if not selected:
        return "UNSUPPORTED"
    parameters = str(selected[0].get("parameters_json") or "{}")
    return parameters


def _matched_sharing_configurations(
    rows: Sequence[Mapping[str, object]],
) -> tuple[str | None, str | None]:
    configurations = {str(row.get("configuration_id") or "") for row in rows}
    for suffix in ("_MATCHED_SERIAL_RESOURCE",):
        left = next(
            (
                value
                for value in configurations
                if value.startswith("R1_TWO_INDEPENDENT_MODELS")
                and value.endswith(suffix)
            ),
            None,
        )
        right = next(
            (
                value
                for value in configurations
                if value.startswith("R2_ONE_SHARED_MODEL") and value.endswith(suffix)
            ),
            None,
        )
        if left is not None and right is not None:
            return left, right
    return None, None


def _matched_sharing_accuracy_evidence(
    rows: Sequence[Mapping[str, object]],
) -> tuple[str | None, str | None, tuple[str, ...]]:
    """Find a same-tier R1/R2 pair with common measured speaker metrics."""

    configurations = {str(row.get("configuration_id") or "") for row in rows}
    accuracy_metrics = (
        "der",
        "word_speaker_label_accuracy",
        "correct_transcribed_attributed_word_rate",
        "known_speaker_accuracy",
    )
    for suffix in ("_FULL", "_MEDIUM", "_SMALL"):
        left = next(
            (
                value
                for value in configurations
                if value.startswith("R1_TWO_INDEPENDENT_MODELS")
                and value.endswith(suffix)
            ),
            None,
        )
        right = next(
            (
                value
                for value in configurations
                if value.startswith("R2_ONE_SHARED_MODEL") and value.endswith(suffix)
            ),
            None,
        )
        if left is None or right is None:
            continue
        common = tuple(
            metric_id
            for metric_id in accuracy_metrics
            if _computed_metric(
                rows,
                mode=None,
                metric_id=metric_id,
                configuration_id=left,
            )
            is not None
            and _computed_metric(
                rows,
                mode=None,
                metric_id=metric_id,
                configuration_id=right,
            )
            is not None
        )
        if common:
            return left, right, common
    return None, None, ()


def _fine_tuning_assessment(
    mode_rows: Sequence[Mapping[str, object]],
    segmentation_rows: Sequence[Mapping[str, object]],
    *,
    selected_segmentation_id: str | None,
) -> tuple[str, str]:
    """Make the no-fine-tuning handoff depend on measured frozen evidence.

    Error prevalence alone does not demonstrate that changing neural weights
    will improve a component.  This program contains no adapted-vs-frozen
    intervention and no real XVF target-audio training panel, so it may expose
    diagnostic targets but cannot make a causal adaptation claim.  Requiring
    measured diagnostics here prevents the final answer from becoming a
    context-free boilerplate conclusion.
    """

    observations: list[str] = []
    for metric_id, label in (
        ("wer", "enhanced end-to-end WER"),
        ("wrong_known_time_sec", "enhanced wrong-known time"),
        (
            "stranger_false_known_time_sec",
            "enhanced stranger false-known time",
        ),
    ):
        value = _computed_metric(
            mode_rows,
            mode="H2_SESSION_MEMORY_ENHANCED",
            metric_id=metric_id,
        )
        if value is not None:
            observations.append(f"{label}={value:.4g}")
    for metric_id, label in (
        ("miss_rate", "selected segmentation miss rate"),
        ("false_alarm_rate", "selected segmentation false-alarm rate"),
    ):
        value = _computed_metric(
            segmentation_rows,
            mode=None,
            metric_id=metric_id,
            configuration_id=selected_segmentation_id,
        )
        if value is not None:
            observations.append(f"{label}={value:.4g}")
    if len(observations) < 2:
        return (
            "INSUFFICIENT_EVIDENCE_TO_JUSTIFY_FINE_TUNING",
            "Fewer than two required frozen diagnostic measurements were available; "
            "no neural adaptation claim is permitted.",
        )
    return (
        "NO_FINE_TUNING_CURRENTLY_JUSTIFIED",
        "Measured frozen-model diagnostics: "
        + "; ".join(observations)
        + ". These measurements establish error prevalence, but this campaign "
        "contains no adapted-vs-frozen causal comparison and no real XVF target-"
        "audio training panel. Resolve policy, coverage, portability, and hardware "
        "data gaps before proposing neural-weight changes.",
    )


def _report_questions(
    tables: Mapping[str, Sequence[Mapping[str, object]]],
    memory_budget: Mapping[str, object],
    linux: Mapping[str, object],
    frozen_policy: Mapping[str, object],
) -> tuple[dict[str, str], ...]:
    mode_rows = tables["h2_mode_comparison.csv"]
    default_mode, default_reason = _default_mode_recommendation(frozen_policy)
    reuse_rows = tables["h2_embedding_reuse_parity.csv"]
    measured_reuse_rows = [
        row for row in reuse_rows if row.get("metric_id") != "record"
    ]
    reuse_pass = bool(measured_reuse_rows) and all(
        row.get("measured") is True and row.get("passed") is True
        for row in measured_reuse_rows
    )
    onnx_rows = tables["h2_onnx_parity.csv"]
    measured_onnx_rows = [row for row in onnx_rows if row.get("measured") is True]
    onnx_pass = bool(measured_onnx_rows) and all(
        row.get("passed") is True for row in measured_onnx_rows
    )
    segmentation_rows = tables["h2_segmentation_frontier.csv"]
    selected_segmentation_ids = sorted(
        {
            str(row.get("configuration_id"))
            for row in segmentation_rows
            if row.get("selected") is True and row.get("configuration_id")
        },
        key=lambda value: (
            not value.endswith("_FULL"),
            not value.endswith("_MEDIUM"),
            value,
        ),
    )
    required_segmentation_metrics = {
        "miss_rate",
        "false_alarm_rate",
        "boundary_delay_sec",
        "short_turn_der_lt_0_5_sec",
        "short_turn_der_0_5_to_1_0_sec",
        "short_turn_der_1_0_to_2_0_sec",
    }
    selected_segmentation_id = next(
        (
            configuration_id
            for configuration_id in selected_segmentation_ids
            if required_segmentation_metrics.issubset(
                {
                    str(row.get("metric_id"))
                    for row in segmentation_rows
                    if row.get("configuration_id") == configuration_id
                    and str(row.get("metric_status") or "").casefold() == "computed"
                }
            )
        ),
        None,
    )
    selected_segmentation = next(
        (
            row
            for row in segmentation_rows
            if row.get("configuration_id") == selected_segmentation_id
        ),
        None,
    )
    selected_segmentation_valid = selected_segmentation_id is not None
    boundary_rows = tables["h2_boundary_results.csv"]
    selected_boundary = next(
        (row for row in boundary_rows if row.get("selected") is True), None
    )
    selected_boundary_id = (
        str(selected_boundary.get("configuration_id"))
        if selected_boundary is not None
        else None
    )
    boundary_reference_id = next(
        (
            str(row.get("configuration_id"))
            for row in boundary_rows
            if str(row.get("configuration_id") or "") == "BOUNDARY_CORRECTION_0000MS"
        ),
        None,
    )
    boundary_improvement = "UNSUPPORTED"
    boundary_metric = "UNSUPPORTED"
    for metric_id in (
        "word_speaker_label_accuracy",
        "correct_transcribed_attributed_word_rate",
        "speaker_attributed_wer",
    ):
        reference_value = _computed_metric(
            boundary_rows,
            mode=None,
            metric_id=metric_id,
            configuration_id=boundary_reference_id,
        )
        selected_value = _computed_metric(
            boundary_rows,
            mode=None,
            metric_id=metric_id,
            configuration_id=selected_boundary_id,
        )
        if reference_value is None or selected_value is None:
            continue
        boundary_metric = metric_id
        boundary_improvement = f"{selected_value - reference_value:+.4g}"
        break
    overlap_rows = tables["h2_overlap_results.csv"]
    selected_overlap = next(
        (row for row in overlap_rows if row.get("selected") is True), None
    )
    sharing_rows = tables["h2_model_sharing_results.csv"]
    r1_configuration, r2_configuration = _matched_sharing_configurations(sharing_rows)
    r1_accuracy, r2_accuracy, shared_accuracy_metrics = (
        _matched_sharing_accuracy_evidence(sharing_rows)
    )
    r1_ram = _computed_metric(
        sharing_rows,
        mode=None,
        metric_id="peak_rss_bytes",
        configuration_id=r1_configuration,
    )
    r2_ram = _computed_metric(
        sharing_rows,
        mode=None,
        metric_id="peak_rss_bytes",
        configuration_id=r2_configuration,
    )
    r1_rtf = _computed_metric(
        sharing_rows,
        mode=None,
        metric_id="total_rtf",
        configuration_id=r1_configuration,
    )
    r2_rtf = _computed_metric(
        sharing_rows,
        mode=None,
        metric_id="total_rtf",
        configuration_id=r2_configuration,
    )
    ram_saving = (
        f"{r1_ram - r2_ram:.0f} bytes"
        if r1_ram is not None and r2_ram is not None
        else "UNSUPPORTED"
    )
    rtf_saving = (
        f"{r1_rtf - r2_rtf:+.4g} total RTF"
        if r1_rtf is not None and r2_rtf is not None
        else "UNSUPPORTED"
    )
    shared_supported = all(
        value is not None for value in (r1_ram, r2_ram, r1_rtf, r2_rtf)
    ) and bool(shared_accuracy_metrics)
    timings = {
        metric: _computed_metric(
            mode_rows,
            mode="H2_SESSION_MEMORY_ENHANCED",
            metric_id=metric,
        )
        for metric in (
            "time_to_first_text_sec",
            "time_to_first_anonymous_label_sec",
            "time_to_tentative_known_name_sec",
            "time_to_confirmed_known_name_sec",
            "stable_name_latency_sec",
        )
    }
    wrong_known = _computed_metric(
        mode_rows,
        mode="H2_SESSION_MEMORY_ENHANCED",
        metric_id="wrong_known_time_sec",
    )
    wrong_dwell = _computed_metric(
        mode_rows,
        mode="H2_SESSION_MEMORY_ENHANCED",
        metric_id="wrong_name_dwell_sec",
    )
    anonymous_rtf = _computed_metric(
        mode_rows,
        mode="H2_SESSION_ANONYMOUS",
        metric_id="total_rtf",
    )
    known_only_rtf = _computed_metric(
        mode_rows,
        mode="H2_KNOWN_ONLY",
        metric_id="total_rtf",
    )
    anonymous_rtf_delta = (
        f"{anonymous_rtf - known_only_rtf:+.4g}"
        if anonymous_rtf is not None and known_only_rtf is not None
        else "UNSUPPORTED"
    )
    fine_tuning_answer, fine_tuning_evidence = _fine_tuning_assessment(
        mode_rows,
        segmentation_rows,
        selected_segmentation_id=selected_segmentation_id,
    )
    return (
        {
            "number": "1",
            "question": "Which H2 mode should be the default product mode?",
            "answer": default_mode or "UNSUPPORTED",
            "evidence": default_reason,
        },
        {
            "number": "2",
            "question": "Is generic Unknown sufficient, or is session-local Speaker_N worth its additional compute and complexity?",
            "answer": (
                "Use generic Unknown only for the privacy-minimal mode; use session-local Speaker_N for the selected default."
                if default_mode
                in {"H2_SESSION_ANONYMOUS", "H2_SESSION_MEMORY_ENHANCED"}
                else "UNSUPPORTED"
            ),
            "evidence": (
                "anonymous consistency="
                + _format_value(
                    _computed_metric(
                        mode_rows,
                        mode="H2_SESSION_ANONYMOUS",
                        metric_id="unknown_n_consistency",
                    ),
                    percent=True,
                )
                + "; Mode A anonymous metrics remain NOT_APPLICABLE"
                + f"; anonymous-minus-known total RTF={anonymous_rtf_delta}"
            ),
        },
        {
            "number": "3",
            "question": "How much does enhanced session memory improve returning-speaker and short-turn behavior?",
            "answer": "Measured deltas are reported without pooling conditional subviews.",
            "evidence": (
                "warm identity accuracy delta="
                + _delta(
                    mode_rows,
                    "warm_identity_accuracy",
                    "H2_SESSION_ANONYMOUS",
                    "H2_SESSION_MEMORY_ENHANCED",
                )
                + "; short-turn DER delta="
                + _delta(
                    mode_rows,
                    "short_turn_der",
                    "H2_SESSION_ANONYMOUS",
                    "H2_SESSION_MEMORY_ENHANCED",
                )
                + "; <0.5 s DER delta="
                + _delta(
                    mode_rows,
                    "short_turn_der_lt_0_5_sec",
                    "H2_SESSION_ANONYMOUS",
                    "H2_SESSION_MEMORY_ENHANCED",
                )
                + "; 0.5-1.0 s DER delta="
                + _delta(
                    mode_rows,
                    "short_turn_der_0_5_to_1_0_sec",
                    "H2_SESSION_ANONYMOUS",
                    "H2_SESSION_MEMORY_ENHANCED",
                )
                + "; 1.0-2.0 s DER delta="
                + _delta(
                    mode_rows,
                    "short_turn_der_1_0_to_2_0_sec",
                    "H2_SESSION_ANONYMOUS",
                    "H2_SESSION_MEMORY_ENHANCED",
                )
            ),
        },
        {
            "number": "4",
            "question": "What stale-name or false-inheritance risks does session memory introduce?",
            "answer": "See selected wrong-inheritance/stale-expiry rows; temporary generic labels remain safer than forced names.",
            "evidence": _selected_policy_description(
                tables["h2_short_turn_results.csv"]
            ),
        },
        {
            "number": "5",
            "question": "Which hysteresis rule gives the best safety/latency trade-off?",
            "answer": _selected_policy_description(tables["h2_hysteresis_results.csv"]),
            "evidence": "development-only lexicographic safety/yield/latency/revision selection",
        },
        {
            "number": "6",
            "question": "How quickly do transcript text, a generic speaker label, a tentative name, a confirmed name, and a stable name appear?",
            "answer": (
                f"text={_format_value(timings['time_to_first_text_sec'])} s; "
                f"generic label={_format_value(timings['time_to_first_anonymous_label_sec'])} s; "
                f"tentative name={_format_value(timings['time_to_tentative_known_name_sec'])} s; "
                f"confirmed name={_format_value(timings['time_to_confirmed_known_name_sec'])} s; "
                f"stable name={_format_value(timings['stable_name_latency_sec'])} s"
            ),
            "evidence": "H2_SESSION_MEMORY_ENHANCED held-out END_TO_END rows",
        },
        {
            "number": "7",
            "question": "How often does a wrong name appear and for how long?",
            "answer": (
                f"wrong-known time={_format_value(wrong_known)} s; "
                f"user-visible wrong-name dwell={_format_value(wrong_dwell)} s"
            ),
            "evidence": "held-out identity and UX rows; unsupported values are not zero",
        },
        {
            "number": "8",
            "question": "Which segmentation settings reduce misses and boundary delay without unacceptable false alarms?",
            "answer": (
                str(selected_segmentation.get("configuration_id"))
                if selected_segmentation is not None and selected_segmentation_valid
                else "UNSUPPORTED"
            ),
            "evidence": (
                str(selected_segmentation.get("runtime_tuning_json"))
                if selected_segmentation is not None and selected_segmentation_valid
                else "no selected row with computed miss, false-alarm, boundary-delay, and all three frozen short-turn-bin metrics"
            ),
        },
        {
            "number": "9",
            "question": "How much does bounded retroactive correction improve word-level attribution?",
            "answer": (
                f"selected-minus-0 ms {boundary_metric}={boundary_improvement}; "
                "no cross-subview pooling was performed."
            ),
            "evidence": (
                f"selected={selected_boundary_id}; reference={boundary_reference_id}"
                if selected_boundary_id is not None
                else "UNSUPPORTED"
            ),
        },
        {
            "number": "10",
            "question": "Should predicted overlap be excluded, included, or deferred for identity?",
            "answer": (
                str(selected_overlap.get("configuration_id"))
                if selected_overlap is not None
                else "UNSUPPORTED"
            ),
            "evidence": "A/B measured; C/D retain explicit UNSUPPORTED capability rows",
        },
        {
            "number": "11",
            "question": "Can one shared ReDimNet instance serve diarization and identity?",
            "answer": (
                "SUPPORTED_BY_MATCHED_MEASURED_R2"
                if shared_supported
                else "UNSUPPORTED"
            ),
            "evidence": (
                f"matched serial resources={r1_configuration},{r2_configuration}; "
                f"same-tier accuracy={r1_accuracy},{r2_accuracy}; "
                f"common measured metrics={','.join(shared_accuracy_metrics)}"
            ),
        },
        {
            "number": "12",
            "question": "Can diarization embeddings be reused safely for identity?",
            "answer": (
                "Yes for the parity-qualified strategy."
                if reuse_pass
                else "UNSUPPORTED"
            ),
            "evidence": f"measured parity rows={sum(row.get('measured') is True for row in reuse_rows)}",
        },
        {
            "number": "13",
            "question": "What RAM/RTF savings result from sharing and reuse?",
            "answer": (
                f"R1 minus R2 peak RSS={ram_saving}; R1 minus R2={rtf_saving}; "
                "reuse-only RAM/RTF savings=UNSUPPORTED unless separately measured."
            ),
            "evidence": (
                f"serial matched tier {r1_configuration} vs {r2_configuration}; "
                "parity is not a resource-savings measurement"
            ),
        },
        {
            "number": "14",
            "question": "Is H2 likely to fit a 2 GB ARM64 Linux system after optimization?",
            "answer": str(memory_budget.get("classification") or "UNSUPPORTED"),
            "evidence": "conservative design budget plus desktop serial resources; not target hardware",
        },
        {
            "number": "15",
            "question": "Did the ONNX FP32 candidate preserve scientific behavior?",
            "answer": (
                "Yes under the frozen parity contract." if onnx_pass else "UNSUPPORTED"
            ),
            "evidence": f"ONNX parity rows={len(onnx_rows)}",
        },
        {
            "number": "16",
            "question": "What remains before Raspberry Pi Compute Module or Arduino UNO Q testing?",
            "answer": str(linux.get("remaining_hardware_gate") or "UNSUPPORTED"),
            "evidence": "ARM64 package is PREPARED, never hardware-validated",
        },
        {
            "number": "17",
            "question": "Exactly where should XVF3800 energy, activity, AoA, AoA confidence, direction change, and processed audio enter the future pipeline?",
            "answer": (
                "Energy/activity: segmentation and endpoint priors plus ReDim call suppression; "
                "AoA/confidence/direction change: boundary, cluster, inheritance-challenge, and roster evidence; "
                "processed audio: AudioNormalizer input before ASR, segmentation, and embeddings."
            ),
            "evidence": "SpatialEvidenceFrame is unavailable/no-effect in this campaign",
        },
        {
            "number": "18",
            "question": "Which components show an evidence-based need for later fine-tuning?",
            "answer": fine_tuning_answer,
            "evidence": fine_tuning_evidence,
        },
    )


def _validate_report_question_contract(
    questions: Sequence[Mapping[str, str]],
) -> None:
    by_number = {str(row.get("number")): row for row in questions}
    if set(by_number) != {str(value) for value in range(1, 19)}:
        raise H2ProgramError("final report does not answer exactly 18 questions")
    if by_number["1"].get("answer") == "UNSUPPORTED":
        raise H2ProgramError("question 1 lacks a measured default-mode decision")
    if "UNSUPPORTED" in str(by_number["3"].get("evidence") or ""):
        raise H2ProgramError(
            "question 3 lacks measured warm and short-turn mode deltas"
        )
    if by_number["5"].get("answer") == "UNSUPPORTED":
        raise H2ProgramError("question 5 lacks one measured hysteresis selection")
    if "UNSUPPORTED" in str(by_number["6"].get("answer") or ""):
        raise H2ProgramError(
            "question 6 lacks one or more required measured product-event timings"
        )
    if "UNSUPPORTED" in str(by_number["7"].get("answer") or ""):
        raise H2ProgramError(
            "question 7 lacks measured wrong-name frequency or dwell evidence"
        )
    if by_number["8"].get("answer") == "UNSUPPORTED":
        raise H2ProgramError(
            "question 8 lacks a selected segmentation row with all safety metrics"
        )
    if "UNSUPPORTED" in str(by_number["9"].get("answer") or ""):
        raise H2ProgramError(
            "question 9 lacks a measured selected-vs-zero boundary attribution delta"
        )
    if by_number["10"].get("answer") == "UNSUPPORTED":
        raise H2ProgramError("question 10 lacks a measured A/B overlap selection")
    if by_number["11"].get("answer") != "SUPPORTED_BY_MATCHED_MEASURED_R2":
        raise H2ProgramError(
            "question 11 lacks matched measured shared-model resource/accuracy evidence"
        )
    question_13 = str(by_number["13"].get("answer") or "")
    if (
        "R1 minus R2 peak RSS=UNSUPPORTED" in question_13
        or "R1 minus R2=UNSUPPORTED" in question_13
    ):
        raise H2ProgramError(
            "question 13 lacks matched measured sharing RAM/RTF evidence"
        )
    if by_number["12"].get("answer") == "UNSUPPORTED":
        raise H2ProgramError("question 12 lacks paired embedding-reuse parity")
    if by_number["14"].get("answer") == "UNSUPPORTED":
        raise H2ProgramError("question 14 lacks measured memory classification")
    if by_number["15"].get("answer") == "UNSUPPORTED":
        raise H2ProgramError("question 15 lacks fresh end-to-end ONNX parity")
    if by_number["18"].get("answer") != "NO_FINE_TUNING_CURRENTLY_JUSTIFIED":
        raise H2ProgramError(
            "question 18 lacks enough measured frozen diagnostics for the "
            "fine-tuning handoff"
        )
    if not str(by_number["18"].get("evidence") or "").startswith(
        "Measured frozen-model diagnostics:"
    ):
        raise H2ProgramError(
            "question 18 is not tied to measured frozen-model diagnostics"
        )


def _render_evidence_table(rows: Sequence[Mapping[str, object]]) -> list[str]:
    lines = ["| Evidence | Status |", "|---|---|"]
    lines.extend(f"| {row['label']} | {row['status']} |" for row in rows)
    return lines


def _validate_historical_reconciliation(document: Mapping[str, object]) -> None:
    if (
        document.get("schema_version") != "h2-historical-evidence-reconciliation.v1"
        or document.get("status") != "COMPLETE"
        or document.get("historical_values_verified_against_machine_readable_artifacts")
        is not True
        or document.get("historical_values_silently_replaced") is not False
        or document.get("cross_protocol_deltas_used_for_selection") is not False
    ):
        raise H2ProgramError("historical evidence reconciliation contract differs")
    raw_rows = document.get("rows")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise H2ProgramError("historical evidence reconciliation rows are missing")
    required_families = {
        "FROZEN_H2_PRODUCT_V2",
        "STANDALONE_PYANNOTE_REDIM",
        "REDIM_ENROLLMENT_LIVE_V2",
    }
    if {
        str(row.get("evidence_family")) for row in raw_rows if isinstance(row, Mapping)
    } != required_families:
        raise H2ProgramError("historical reconciliation family membership differs")
    for row in raw_rows:
        if (
            not isinstance(row, Mapping)
            or row.get("historical_value_verified") is not True
            or not row.get("metric_id")
            or not row.get("historical_source_sha256")
            or not row.get("difference_explanation")
            or row.get("comparability")
            not in {
                "DESCRIPTIVE_ONLY_PROTOCOL_CHANGED",
                "HISTORICAL_REVERIFIED_NO_EQUIVALENT_CURRENT_METRIC",
            }
        ):
            raise H2ProgramError("historical reconciliation row is incomplete")


def _render_historical_reconciliation(
    document: Mapping[str, object],
) -> list[str]:
    _validate_historical_reconciliation(document)
    rows = [row for row in document["rows"] if isinstance(row, Mapping)]
    lines = [
        "## Historical evidence reconciliation",
        "",
        "All values below were re-read from checksum-bound machine-readable "
        "artifacts. A blank fresh value means that this campaign does not emit a "
        "same-unit statistic; the historical result is preserved, not replaced. "
        "No cross-protocol delta affected development selection.",
        "",
        "| Evidence family | Metric | Historical | Fresh H2 baseline | Descriptive delta | Comparability |",
        "|---|---|---:|---:|---:|---|",
    ]

    def format_number(value: object) -> str:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return "—"
        return f"{float(value):.8g}"

    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    str(row["evidence_family"]),
                    f"`{row['metric_id']}`",
                    format_number(row.get("historical_value")),
                    format_number(row.get("current_value")),
                    format_number(row.get("descriptive_delta")),
                    str(row.get("comparability")),
                )
            )
            + " |"
        )
    lines.extend(["", "Why values differ or remain historical-only:", ""])
    seen: set[str] = set()
    for row in rows:
        family = str(row["evidence_family"])
        if family in seen:
            continue
        seen.add(family)
        lines.append(f"- **{family}:** {row['difference_explanation']}")
    lines.append("")
    return lines


def _render_report(
    *,
    questions: Sequence[Mapping[str, str]],
    evidence_rows: Sequence[Mapping[str, object]],
    historical_reconciliation: Mapping[str, object],
    final_zip_valid: bool,
) -> str:
    final_status = (
        "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM" if final_zip_valid else "BLOCKED_OTHER"
    )
    lines = [
        "# H2 complete product-pipeline report",
        "",
        f"Final status: `{final_status}`",
        "",
        "This report uses only checksum-valid, predeclared H2 evidence. Conditional "
        "and end-to-end metrics remain separate, unsupported values are not zero, "
        "and no weighted composite score is used. The ARM64 candidate is a prepared "
        "software package, not a hardware-validation claim.",
        "",
        "## Answers to the 18 steering questions",
        "",
    ]
    historical_lines = _render_historical_reconciliation(historical_reconciliation)
    lines[8:8] = historical_lines
    for row in questions:
        lines.extend(
            [
                f"### {row['number']}. {row['question']}",
                "",
                str(row["answer"]),
                "",
                f"Evidence: {row['evidence']}",
                "",
            ]
        )
    lines.extend(["## Final evidence table", ""])
    lines.extend(_render_evidence_table(evidence_rows))
    lines.extend(
        [
            "",
            "## Interpretation boundaries",
            "",
            "- R3/R4 reuse is recommended only when paired vector, decision, cluster, and transcript-label parity all pass.",
            "- ONNX equivalence requires fresh native-vs-ONNX full-pipeline parity, not component export alone.",
            "- Live-microphone application completion qualifies implementation and targeted tests; it does not claim a physical microphone campaign.",
            "- CHiME-6 and VOiCES remain limited to their supported ASR/anonymous-diarization diagnostic views.",
            "- No real or simulated XVF3800 input affected results.",
        ]
    )
    return "\n".join(lines) + "\n"


def _evidence_timestamp(state: Mapping[str, object]) -> str:
    jobs = state.get("jobs")
    values: list[datetime] = []
    if isinstance(jobs, Mapping):
        for row in jobs.values():
            if not isinstance(row, Mapping):
                continue
            raw = row.get("completed_at_utc")
            if not isinstance(raw, str) or not raw:
                continue
            try:
                values.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
            except ValueError:
                continue
    selected = max(values) if values else datetime(1970, 1, 1, tzinfo=timezone.utc)
    return selected.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_inventory(
    artifacts: Mapping[str, ResultArtifact],
) -> list[dict[str, object]]:
    return [
        {
            "job_id": artifact.job.job_id,
            "job_identity_sha256": artifact.job.identity_sha256,
            "job_kind": artifact.job.job_kind,
            "configuration_id": artifact.job.configuration_id,
            "state": artifact.state_row.get("state"),
            "result_path": str(artifact.path) if artifact.path is not None else None,
            "result_sha256": artifact.sha256,
            "artifact_kind": artifact.artifact_kind,
            "validated": artifact.validated,
        }
        for artifact in sorted(artifacts.values(), key=lambda item: item.job.job_id)
    ]


def _hash_inventory(root: Path, names: Iterable[str]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for name in sorted(set(names)):
        path = root / name
        if not path.is_file():
            raise H2ProgramError(f"required analysis output is missing: {path}")
        result[name] = {"sha256": sha256_file(path), "bytes": path.stat().st_size}
    return result


def _csv_fields_for(name: str) -> tuple[str, ...]:
    if name in {"h2_embedding_reuse_parity.csv", "h2_onnx_parity.csv"}:
        return PARITY_FIELDS
    if name in {
        "h2_identity_policy_results.csv",
        "h2_hysteresis_results.csv",
        "h2_session_memory_results.csv",
        "h2_short_turn_results.csv",
        "h2_expiry_results.csv",
    }:
        return POLICY_FIELDS
    if name == "bootstrap_intervals.csv":
        return BOOTSTRAP_FIELDS
    if name == "failure_inventory.csv":
        return FAILURE_FIELDS
    return EXPERIMENT_FIELDS


def validate_analysis_outputs(root: Path) -> dict[str, object]:
    """Validate required names, schemas, status semantics, and self identities."""

    summary = Path(root).resolve(strict=True)
    missing = [
        name for name in REQUIRED_ANALYSIS_FILES if not (summary / name).is_file()
    ]
    if missing:
        raise H2ProgramError("analysis outputs are incomplete: " + ", ".join(missing))
    csv_rows: dict[str, list[dict[str, str]]] = {}
    for name in REQUIRED_CSV_FILES:
        path = summary / name
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != _csv_fields_for(name):
                raise H2ProgramError(f"analysis CSV schema differs: {name}")
            csv_rows[name] = []
            for row in reader:
                if any(key is None for key in row):
                    raise H2ProgramError(f"analysis CSV has extra columns: {name}")
                csv_rows[name].append(dict(row))
    empty_forbidden = [
        name
        for name, rows in csv_rows.items()
        if not rows and name != "failure_inventory.csv"
    ]
    if empty_forbidden:
        raise H2ProgramError(
            "required analysis tables are empty: " + ", ".join(empty_forbidden)
        )
    generic = [
        name
        for name, rows in csv_rows.items()
        if name not in {"failure_inventory.csv"}
        and rows
        and all(row.get("metric_id") in {"", "record", "job_status"} for row in rows)
    ]
    if generic:
        raise H2ProgramError(
            "required analysis tables contain only generic job rows: "
            + ", ".join(generic)
        )
    for name in (
        "h2_identity_policy_results.csv",
        "h2_hysteresis_results.csv",
        "h2_short_turn_results.csv",
        "h2_expiry_results.csv",
    ):
        selected = {
            row.get("policy_id")
            for row in csv_rows[name]
            if str(row.get("selected") or "").casefold() == "true"
        }
        if len(selected) != 1 or None in selected:
            raise H2ProgramError(
                f"analysis table lacks exactly one selected policy: {name}"
            )
    session_selected = {
        row.get("policy_id")
        for row in csv_rows["h2_session_memory_results.csv"]
        if str(row.get("selected") or "").casefold() == "true"
    }
    if len(session_selected) > 1:
        raise H2ProgramError("session-memory study selects more than one named policy")
    for name, rows in csv_rows.items():
        if name in {"failure_inventory.csv", "bootstrap_intervals.csv"}:
            continue
        for row in rows:
            status = str(row.get("metric_status") or row.get("status") or "").casefold()
            if status in {
                "unsupported",
                "unsupported_capability",
                "not_run",
                "not_applicable",
                "undefined",
            }:
                continue
            source_sha = str(row.get("source_result_sha256") or "")
            if len(source_sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", source_sha):
                raise H2ProgramError(
                    f"measured analysis row lacks source checksum: {name}"
                )
    policy_semantics = {
        "h2_hysteresis_results.csv": (
            "hysteresis_policy",
            {
                "H0_ONE_PASS_DIAGNOSTIC",
                "H1_TWO_CONFIRM_TWO_RELEASE",
                "H2A_ADAPTIVE_EARLY",
                "H3_THREE_CONFIRM_SAFE",
                "H4_DURATION_DEPENDENT",
            },
        ),
        "h2_session_memory_results.csv": (
            "memory_level",
            {
                "M0_STATELESS",
                "M1_CLUSTER",
                "M2_CONFIRMED_NAME",
                "M3_SHORT_TURN",
                "M4_ACTIVE_ROSTER_DECAY",
                "M5_CLUSTER_RECONCILIATION",
            },
        ),
        "h2_short_turn_results.csv": (
            "short_turn_policy",
            {
                "FRESH_EMBEDDING_REQUIRED",
                "ANONYMOUS_CLUSTER_INHERITANCE",
                "CONFIRMED_NAME_INHERITANCE",
                "INHERITANCE_WITH_CONTRADICTION_CHECKS",
                "GENERIC_UNTIL_LATER_CORRECTION",
            },
        ),
    }
    for name, (key, required) in policy_semantics.items():
        observed: set[str] = set()
        expiry_values: set[str] = set()
        duration_bins: set[str] = set()
        for row in csv_rows[name]:
            try:
                parameters = json.loads(row.get("parameters_json") or "{}")
            except json.JSONDecodeError:
                continue
            if isinstance(parameters, Mapping) and parameters.get(key):
                observed.add(str(parameters[key]))
                if parameters.get("identity_expiry_sec") is not None:
                    expiry_values.add(
                        _cell_value_key(parameters["identity_expiry_sec"])
                    )
                if parameters.get("duration_bin") is not None:
                    duration_bins.add(str(parameters["duration_bin"]))
        if not required.issubset(observed):
            raise H2ProgramError(
                f"analysis table lacks exact named {key} cells: {name}"
            )
        if name in {
            "h2_hysteresis_results.csv",
            "h2_session_memory_results.csv",
        } and not {
            _cell_value_key(value)
            for value in (15.0, 30.0, 60.0, 120.0, "end_of_session")
        }.issubset(
            expiry_values
        ):
            raise H2ProgramError(f"analysis table lacks exact expiry cells: {name}")
        if name == "h2_short_turn_results.csv" and not {
            "LT_0P5",
            "GE_0P5_LT_1P0",
            "GE_1P0_LE_2P0",
        }.issubset(duration_bins):
            raise H2ProgramError("short-turn analysis lacks exact duration-bin cells")
    coverage_rows = [
        row
        for row in csv_rows["h2_embedding_policy_results.csv"]
        if row.get("metric_view") == "embedding_clustering_coverage"
        and row.get("metric_id") == "coverage_outcome"
    ]
    if not coverage_rows:
        raise H2ProgramError("embedding-policy table lacks declared coverage outcomes")
    registry = read_yaml(summary / "h2_configuration_registry.yaml")
    configurations = registry.get("configurations")
    ids = (
        tuple(
            str(row.get("configuration_id"))
            for row in configurations
            if isinstance(row, Mapping)
        )
        if isinstance(configurations, list)
        else ()
    )
    if ids != FINAL_CONFIGURATION_IDS:
        raise H2ProgramError("configuration registry schema/membership differs")
    for row in configurations if isinstance(configurations, list) else ():
        if not isinstance(row, Mapping):
            raise H2ProgramError("configuration registry row is invalid")
        tuning = row.get("runtime_tuning")
        identity = row.get("runtime_tuning_identity_sha256")
        assets = row.get("assets")
        if (
            not isinstance(tuning, Mapping)
            or not tuning
            or not isinstance(identity, str)
            or not re.fullmatch(r"[0-9a-f]{64}", identity)
            or not isinstance(assets, list)
            or not assets
        ):
            raise H2ProgramError(
                f"configuration registry lacks exact tuning/assets: {row.get('configuration_id')}"
            )
        for asset in assets:
            if not isinstance(asset, Mapping) or not any(
                isinstance(asset.get(key), str)
                and re.fullmatch(r"[0-9a-f]{64}", str(asset.get(key)))
                for key in ("sha256", "graph_sha256")
            ):
                raise H2ProgramError(
                    f"configuration asset lacks checksum: {row.get('configuration_id')}"
                )
    reconciliation = read_json(summary / "historical_evidence_reconciliation.json")
    _validate_historical_reconciliation(reconciliation)
    report_text = (summary / "REPORT.md").read_text(encoding="utf-8")
    if (
        "## Historical evidence reconciliation" not in report_text
        or "Why values differ or remain historical-only:" not in report_text
    ):
        raise H2ProgramError(
            "final report lacks explicit historical evidence reconciliation"
        )
    analysis = read_json(summary / "analysis_manifest.json")
    if analysis.get("schema_version") != "h2-analysis-manifest.v1":
        raise H2ProgramError("analysis manifest schema differs")
    reproducibility = read_json(summary / "REPRODUCIBILITY_MANIFEST.json")
    if reproducibility.get("schema_version") != "h2-reproducibility-manifest.v1":
        raise H2ProgramError("reproducibility manifest schema differs")
    if reproducibility.get("weighted_composite_used") is not False:
        raise H2ProgramError("reproducibility manifest permits a composite score")
    return {
        "status": "PASS",
        "required_file_count": len(REQUIRED_ANALYSIS_FILES),
        "required_files": list(REQUIRED_ANALYSIS_FILES),
    }


def _execute_partial_analysis(
    paths: ProgramPaths,
    *,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    """Write a non-promotable inventory without weakening the final job gate."""

    rows = _state_rows(state, jobs)
    artifacts: dict[str, ResultArtifact] = {}
    blockers: list[dict[str, object]] = []
    for job in jobs:
        if job.job_kind in {"analysis", "collection"}:
            continue
        row = rows[job.job_id]
        status = str(row.get("state") or "MISSING")
        if status == "COMPLETE":
            try:
                artifacts[job.job_id] = _validate_completed_artifact(job, row)
            except Exception as exc:
                blockers.append(
                    {
                        "job_id": job.job_id,
                        "job_kind": job.job_kind,
                        "state": status,
                        "reason": f"{type(exc).__name__}: {exc}",
                    }
                )
            continue
        if status == "SUPERSEDED" and job.optional:
            artifacts[job.job_id] = ResultArtifact(
                job=job,
                state_row=row,
                path=None,
                root=None,
                artifact_kind="superseded",
                sha256=None,
                document=None,
                validated=True,
            )
            continue
        blockers.append(
            {
                "job_id": job.job_id,
                "job_kind": job.job_kind,
                "state": status,
                "reason": row.get("last_error")
                or "required final evidence is not complete",
            }
        )
    output = paths.summary_root / "partial_analysis"
    output.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "h2-partial-analysis.v1",
        "status": "PARTIAL_NOT_PROMOTABLE",
        "program_status": state.get("status"),
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "validated_artifact_count": len(artifacts),
        "blocker_count": len(blockers),
        "blockers": blockers,
        "final_report_published": False,
        "final_zip_published": False,
        "complete_status_claimed": False,
    }
    result_path = output / "partial_analysis.json"
    write_json_atomic(result_path, payload)
    write_csv_atomic(
        output / "partial_result_inventory.csv",
        _result_inventory(artifacts),
        RESULT_INVENTORY_FIELDS,
    )
    lines = [
        "# H2 partial analysis",
        "",
        "Status: `PARTIAL_NOT_PROMOTABLE`",
        "",
        "This read-only diagnostic inventories checksum-valid evidence currently "
        "available. It is not the final report, does not satisfy any missing job, "
        "and cannot authorize collection or program completion.",
        "",
        f"Validated artifacts: {len(artifacts)}",
        "",
        f"Outstanding or invalid prerequisites: {len(blockers)}",
        "",
    ]
    lines.extend(
        f"- `{row['job_id']}` ({row['state']}): {row['reason']}" for row in blockers
    )
    _write_text_atomic(output / "PARTIAL_REPORT.md", "\n".join(lines) + "\n")
    return {
        "state": "complete",
        "result_path": str(result_path),
        "result_sha256": sha256_file(result_path),
        "completed_cases": 0,
        "completed_audio_sec": 0.0,
        "cache_hits": 0,
        "status": "PARTIAL_NOT_PROMOTABLE",
    }


def execute_analysis(
    paths: ProgramPaths,
    *,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    require_complete: bool,
) -> dict[str, object]:
    """Publish final analysis only after the evidence contract passes."""

    if not require_complete:
        return _execute_partial_analysis(paths, state=state, jobs=jobs)
    rows = _state_rows(state, jobs)
    analysis_jobs = [job for job in jobs if job.job_kind == "analysis"]
    collection_jobs = [job for job in jobs if job.job_kind == "collection"]
    if len(analysis_jobs) != 1 or len(collection_jobs) != 1:
        raise H2ProgramError("exactly one analysis and one collection job are required")
    if require_complete and rows[analysis_jobs[0].job_id].get("state") != "RUNNING":
        raise H2ProgramError("controller-managed analysis job must be RUNNING")
    artifacts = validate_prerequisite_artifacts(state, jobs)
    _require_analysis_completion_contract(paths, artifacts)
    paths.summary_root.mkdir(parents=True, exist_ok=True)

    registry = _configuration_registry(paths, state, artifacts)
    baseline_artifact = _artifact_for_configuration(artifacts, "H2_BASELINE_REFERENCE")
    if baseline_artifact is None:
        raise H2ProgramError("measured H2 baseline artifact is missing")
    historical_reconciliation = _historical_evidence_reconciliation(
        paths, baseline_artifact
    )
    tables = dict(_build_analysis_tables(paths, state, artifacts))
    metric_rows = _all_metric_rows(artifacts)
    failures = list(_failure_inventory(artifacts, metric_rows))
    for raw in tables["h2_overlap_results.csv"]:
        status = str(raw.get("metric_status") or "").upper()
        if status not in {"UNSUPPORTED_CAPABILITY", "NOT_RUN", "FAILED"}:
            continue
        failures.append(
            {
                "schema_version": "h2-failure-inventory-row.v1",
                "scope": "DECLARED_CAPABILITY",
                "job_id": raw.get("job_id"),
                "configuration_id": raw.get("configuration_id"),
                "mode": raw.get("mode"),
                "artifact": "h2_overlap_results.csv",
                "metric_view": "overlap",
                "metric_subview": raw.get("metric_subview"),
                "metric_id": raw.get("metric_id"),
                "status": status,
                "reason": raw.get("reason"),
                "source_result_sha256": raw.get("source_result_sha256"),
            }
        )
    failures = sorted(
        failures,
        key=lambda row: tuple(
            str(row.get(key) or "")
            for key in (
                "scope",
                "job_id",
                "metric_view",
                "metric_subview",
                "metric_id",
                "status",
            )
        ),
    )
    tables["failure_inventory.csv"] = failures
    linux = _linux_portability_document(artifacts)
    memory = _memory_budget_document(tables["h2_resource_results.csv"])
    provisional_evidence = build_final_evidence_table(
        paths,
        artifacts,
        final_report_complete=True,
        final_zip_valid=False,
    )
    questions = _report_questions(
        tables,
        memory,
        linux,
        read_json(paths.freeze_path),
    )
    _validate_report_question_contract(questions)

    write_yaml_atomic(paths.summary_root / "h2_configuration_registry.yaml", registry)
    for name in REQUIRED_CSV_FILES:
        write_csv_atomic(
            paths.summary_root / name,
            tuple(tables.get(name, ())),
            _csv_fields_for(name),
        )
    write_json_atomic(paths.summary_root / "h2_linux_portability.json", linux)
    write_json_atomic(paths.summary_root / "h2_memory_budget.json", memory)
    write_json_atomic(
        paths.summary_root / "historical_evidence_reconciliation.json",
        historical_reconciliation,
    )
    write_json_atomic(
        paths.summary_root / "cache_inventory.json",
        _cache_inventory(paths, artifacts),
    )
    write_csv_atomic(
        paths.summary_root / "result_file_inventory.csv",
        _result_inventory(artifacts),
        RESULT_INVENTORY_FIELDS,
    )
    write_json_atomic(
        paths.summary_root / "evidence_table.json",
        {
            "schema_version": "h2-final-evidence-table.v1",
            "collection_status": "NOT_RUN",
            "rows": list(provisional_evidence),
        },
    )
    _write_text_atomic(paths.summary_root / "METRIC_GUIDE.md", _metric_guide())
    _write_text_atomic(
        paths.summary_root / "REPORT.md",
        _render_report(
            questions=questions,
            evidence_rows=provisional_evidence,
            historical_reconciliation=historical_reconciliation,
            final_zip_valid=False,
        ),
    )

    evidence_time = _evidence_timestamp(state)
    mutable_on_collection = {
        "analysis_manifest.json",
        "REPORT.md",
        "REPRODUCIBILITY_MANIFEST.json",
        "evidence_table.json",
    }
    immutable_names = [
        name
        for name in (*REQUIRED_ANALYSIS_FILES, *SUPPORTING_ANALYSIS_FILES)
        if name not in mutable_on_collection
    ]
    analysis_manifest = {
        "schema_version": "h2-analysis-manifest.v1",
        "status": "COMPLETE_EVIDENCE_PACKAGE_PENDING",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "freeze_identity_sha256": state.get("freeze_identity_sha256"),
        "evidence_completed_at_utc": evidence_time,
        "source_inventory": _source_inventory(artifacts),
        "source_inventory_sha256": canonical_sha256(_source_inventory(artifacts)),
        "generated_outputs": _hash_inventory(paths.summary_root, immutable_names),
        "collection_finalizable_outputs": sorted(mutable_on_collection),
        "conditional_and_end_to_end_metrics_separate": True,
        "weighted_composite_used": False,
        "failure_inventory_row_count": len(failures),
        "analysis_completion_contract_passed": True,
    }
    write_json_atomic(paths.summary_root / "analysis_manifest.json", analysis_manifest)
    reproducibility = {
        "schema_version": "h2-reproducibility-manifest.v1",
        "status": "ANALYSIS_COMPLETE_COLLECTION_PENDING",
        "program_status": "BLOCKED_OTHER",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "freeze_identity_sha256": state.get("freeze_identity_sha256"),
        "seed": 3800,
        "evidence_completed_at_utc": evidence_time,
        "source_inventory_sha256": analysis_manifest["source_inventory_sha256"],
        "generated_output_sha256s": _hash_inventory(
            paths.summary_root,
            [
                name
                for name in (*REQUIRED_ANALYSIS_FILES, *SUPPORTING_ANALYSIS_FILES)
                if name != "REPRODUCIBILITY_MANIFEST.json"
            ],
        ),
        "weighted_composite_used": False,
        "selection_policy": "ordered safety constraints and Pareto reasoning",
        "conditional_and_end_to_end_metrics_separate": True,
        "package_policy": {
            "allowlist_only": True,
            "maximum_member_bytes": MAX_PACKAGE_MEMBER_BYTES,
            "raw_datasets_included": False,
            "audio_included": False,
            "onnx_or_model_weights_included": False,
            "credentials_or_secrets_included": False,
            "biometric_vectors_included": False,
            "shared_or_large_caches_included": False,
            "sqlite_locks_or_temporary_files_included": False,
        },
        "scientific_actions": {
            "fine_tuning_performed": False,
            "xvf_result_affecting_input_used": False,
            "arm64_hardware_validation_claimed": False,
        },
    }
    write_json_atomic(
        paths.summary_root / "REPRODUCIBILITY_MANIFEST.json", reproducibility
    )
    validation = validate_analysis_outputs(paths.summary_root)
    receipt_path = paths.summary_root / "analysis_receipt.json"
    receipt = {
        "schema_version": "h2-analysis-receipt.v1",
        "status": "COMPLETE",
        "require_complete": require_complete,
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "source_inventory_sha256": analysis_manifest["source_inventory_sha256"],
        "immutable_output_inventory": _hash_inventory(
            paths.summary_root, immutable_names
        ),
        "collection_finalizable_outputs": sorted(mutable_on_collection),
        "validation": validation,
        "marked_complete_before_evidence": False,
    }
    write_json_atomic(receipt_path, receipt)
    return {
        "state": "complete",
        "result_path": str(receipt_path),
        "result_sha256": sha256_file(receipt_path),
        "completed_cases": 0,
        "completed_audio_sec": 0.0,
        "cache_hits": 0,
        "status": "COMPLETE",
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _validate_package_member_name(member: str) -> PurePosixPath:
    if not member or "\\" in member or "\x00" in member:
        raise H2ProgramError(f"unsafe package member name: {member!r}")
    path = PurePosixPath(member)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise H2ProgramError(f"unsafe package member path: {member}")
    lowered_parts = {part.casefold() for part in path.parts}
    if lowered_parts & FORBIDDEN_PACKAGE_PARTS:
        raise H2ProgramError(f"forbidden package path: {member}")
    if path.suffix.casefold() in FORBIDDEN_PACKAGE_SUFFIXES:
        raise H2ProgramError(f"forbidden package suffix: {member}")
    return path


def _validate_package_payload(member: str, payload: bytes) -> None:
    _validate_package_member_name(member)
    if len(payload) > MAX_PACKAGE_MEMBER_BYTES:
        raise H2ProgramError(
            f"package member exceeds conservative size threshold: {member}"
        )
    if b"\x00" in payload[:8192]:
        raise H2ProgramError(f"binary payload is not allowlisted: {member}")
    text = payload.decode("utf-8-sig", errors="replace")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise H2ProgramError(f"possible credential or secret in package: {member}")
    if BIOMETRIC_VECTOR_PATTERN.search(text):
        raise H2ProgramError(f"possible biometric vector in package: {member}")


def _validated_package_member(member: PackageMember) -> PackageMember:
    _validate_package_member_name(member.member)
    source = member.source.resolve(strict=True)
    if not source.is_file():
        raise H2ProgramError(f"package source is not a file: {source}")
    _validate_package_payload(member.member, source.read_bytes())
    return PackageMember(member.member, source, member.category)


def _append_member(
    output: list[PackageMember],
    *,
    member: str,
    source: Path,
    category: str,
    required: bool = True,
) -> None:
    if not source.is_file():
        if required:
            raise H2ProgramError(f"required package source is missing: {source}")
        return
    output.append(
        _validated_package_member(
            PackageMember(member=member, source=source, category=category)
        )
    )


def _declared_json_member(
    output: list[PackageMember],
    *,
    member: str,
    raw_path: object,
    expected_sha256: object,
    allowed_root: Path,
) -> None:
    if not isinstance(raw_path, str) or not isinstance(expected_sha256, str):
        raise H2ProgramError(f"portability JSON binding is incomplete: {member}")
    path = Path(raw_path).resolve(strict=True)
    if (
        path.suffix.casefold() != ".json"
        or not _is_within(path, allowed_root)
        or sha256_file(path) != expected_sha256
    ):
        raise H2ProgramError(f"portability JSON binding differs: {member}")
    _append_member(
        output,
        member=member,
        source=path,
        category="portability_parity",
    )


def build_package_allowlist(
    paths: ProgramPaths,
    artifacts: Mapping[str, ResultArtifact],
) -> tuple[PackageMember, ...]:
    """Build and validate an explicit, non-recursive package inventory."""

    output: list[PackageMember] = []
    for name in (
        *REQUIRED_ANALYSIS_FILES,
        *SUPPORTING_ANALYSIS_FILES,
        "analysis_receipt.json",
    ):
        _append_member(
            output,
            member=f"summary/{name}",
            source=paths.summary_root / name,
            category="summary",
        )
    frozen_root = paths.summary_root / "frozen_configurations"
    frozen_names = (
        "H2_KNOWN_ONLY.json",
        "H2_SESSION_ANONYMOUS.json",
        "H2_SESSION_MEMORY_ENHANCED.json",
        "h2_demo_runtime_binding.frozen.json",
    )
    for name in frozen_names:
        _append_member(
            output,
            member=f"summary/frozen_configurations/{name}",
            source=frozen_root / name,
            category="frozen_configuration",
        )

    config_sources = (
        paths.config_path,
        paths.evaluation_root
        / "configs/automated_evaluation/full_pipeline_matrix.v1.yaml",
        paths.evaluation_root
        / "configs/automated_evaluation/full_pipeline_runtime.v1.yaml",
    )
    for source in config_sources:
        _append_member(
            output,
            member=f"configs/{source.name}",
            source=source,
            category="configuration",
        )

    workspace_sources = (
        ("protocol/protocol_manifest.json", paths.protocol_path, True),
        ("protocol/job_manifest.json", paths.jobs_path, True),
        ("protocol/frozen_policy.json", paths.freeze_path, True),
        (
            "protocol/runtime_implementation_identity.json",
            paths.workspace / "runtime_implementation_identity.json",
            True,
        ),
        (
            "protocol/heldout_execution_manifest.json",
            paths.workspace / "heldout_execution_manifest.json",
            True,
        ),
        ("controller/program_state.json", paths.state_path, True),
        ("controller/milestones.jsonl", paths.workspace / "milestones.jsonl", True),
        (
            "controller/stop_history.jsonl",
            paths.workspace / "stop_history.jsonl",
            False,
        ),
    )
    for member, source, required in workspace_sources:
        _append_member(
            output,
            member=member,
            source=source,
            category=(
                "protocol" if member.startswith("protocol/") else "controller_history"
            ),
            required=required,
        )
    promotions = paths.workspace / "promotions"
    if promotions.is_dir():
        for source in sorted(promotions.glob("*.json")):
            _append_member(
                output,
                member=f"controller/promotions/{source.name}",
                source=source,
                category="controller_history",
            )

    for name in FINAL_DOCUMENTS:
        _append_member(
            output,
            member=f"reports/docs/full_pipeline/{name}",
            source=paths.evaluation_root / "docs/full_pipeline" / name,
            category="report",
        )
    _append_member(
        output,
        member="reports/app/h2_product_program/README.md",
        source=paths.evaluation_root / "app/h2_product_program/README.md",
        category="report",
    )

    portability_by_kind: dict[str, ResultArtifact] = {}
    for kind in ("onnx_export", "onnx_parity", "linux_portability"):
        values = _artifact_for_kind(artifacts, kind)
        if len(values) != 1 or values[0].path is None:
            raise H2ProgramError(
                f"exactly one portability artifact is required: {kind}"
            )
        portability_by_kind[kind] = values[0]
        _append_member(
            output,
            member=f"portability/job_results/{kind}.json",
            source=values[0].path,
            category="portability_receipt",
        )

    parity = portability_by_kind["onnx_parity"].document or {}
    _declared_json_member(
        output,
        member="portability/parity/e2e_component_hook.json",
        raw_path=parity.get("e2e_component_hook_path"),
        expected_sha256=parity.get("e2e_component_hook_sha256"),
        allowed_root=paths.results_root,
    )
    _declared_json_member(
        output,
        member="portability/parity/e2e_protocol_freeze.json",
        raw_path=parity.get("e2e_protocol_freeze_path"),
        expected_sha256=parity.get("e2e_protocol_freeze_sha256"),
        allowed_root=paths.results_root,
    )
    component_reports = parity.get("component_reports")
    if not isinstance(component_reports, Mapping) or len(component_reports) != 2:
        raise H2ProgramError("portability parity lacks two component report bindings")
    for component_id, raw in sorted(
        component_reports.items(), key=lambda item: str(item[0])
    ):
        if not isinstance(raw, Mapping):
            raise H2ProgramError(f"invalid component parity binding: {component_id}")
        _declared_json_member(
            output,
            member=f"portability/parity/components/{component_id}.json",
            raw_path=raw.get("report_path"),
            expected_sha256=raw.get("report_sha256"),
            allowed_root=paths.results_root,
        )
    for case_name, key in (
        ("enrolled", "e2e_enrolled_case"),
        ("empty_enrollment", "e2e_empty_enrollment_case"),
    ):
        raw = parity.get(key)
        if not isinstance(raw, Mapping):
            raise H2ProgramError(f"portability parity lacks {key}")
        _declared_json_member(
            output,
            member=f"portability/parity/full_pipeline/{case_name}.json",
            raw_path=raw.get("report_path"),
            expected_sha256=raw.get("report_sha256"),
            allowed_root=paths.results_root,
        )

    linux = portability_by_kind["linux_portability"].document or {}
    package_root = Path(str(linux.get("package_root") or "")).resolve(strict=False)
    expected_package_root = (paths.evaluation_root / "deployment/h2_arm64").resolve()
    if package_root != expected_package_root:
        raise H2ProgramError("ARM64 package root differs from deployment/h2_arm64")
    declared_files = linux.get("package_files")
    if not isinstance(declared_files, list):
        raise H2ProgramError("ARM64 portability result lacks package file inventory")
    declared = {
        str(row.get("relative_path")): row
        for row in declared_files
        if isinstance(row, Mapping)
    }
    if set(declared) != set(ARM64_PACKAGE_FILES):
        raise H2ProgramError("ARM64 package inventory membership differs")
    for relative in ARM64_PACKAGE_FILES:
        row = declared[relative]
        source = (package_root / relative).resolve(strict=True)
        if (
            not _is_within(source, package_root)
            or row.get("sha256") != sha256_file(source)
            or row.get("bytes") != source.stat().st_size
        ):
            raise H2ProgramError(f"ARM64 package file binding differs: {relative}")
        _append_member(
            output,
            member=f"deployment/h2_arm64/{relative}",
            source=source,
            category="arm64_preparation_package",
        )

    names = [value.member for value in output]
    folded = [value.casefold() for value in names]
    if len(folded) != len(set(folded)):
        duplicates = [name for name, count in Counter(folded).items() if count > 1]
        raise H2ProgramError(f"duplicate package allowlist members: {duplicates}")
    total = sum(value.source.stat().st_size for value in output)
    if total > MAX_PACKAGE_TOTAL_BYTES:
        raise H2ProgramError("package allowlist exceeds conservative total size limit")
    return tuple(sorted(output, key=lambda value: value.member))


def _stage_package_members(members: Sequence[PackageMember], stage: Path) -> None:
    for item in members:
        destination = stage / PurePosixPath(item.member)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item.source, destination)
        if sha256_file(destination) != sha256_file(item.source):
            raise H2ProgramError(f"staged package copy differs: {item.member}")


def _finalize_staged_summary(
    stage: Path,
    *,
    state: Mapping[str, object],
    tables: Mapping[str, Sequence[Mapping[str, object]]],
    memory: Mapping[str, object],
    linux: Mapping[str, object],
    evidence_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    summary = stage / "summary"
    questions = _report_questions(
        tables,
        memory,
        linux,
        read_json(stage / "protocol/frozen_policy.json"),
    )
    _validate_report_question_contract(questions)
    final_rows = tuple(dict(row) for row in evidence_rows)
    if not all(row.get("acceptable") is True for row in final_rows):
        raise H2ProgramError("staged final evidence table contains a failed row")
    _write_text_atomic(
        summary / "REPORT.md",
        _render_report(
            questions=questions,
            evidence_rows=final_rows,
            historical_reconciliation=read_json(
                summary / "historical_evidence_reconciliation.json"
            ),
            final_zip_valid=True,
        ),
    )
    write_json_atomic(
        summary / "evidence_table.json",
        {
            "schema_version": "h2-final-evidence-table.v1",
            "collection_status": "VALID",
            "rows": list(final_rows),
        },
    )
    analysis = read_json(summary / "analysis_manifest.json")
    analysis.update(
        {
            "status": "COMPLETE",
            "collection_status": "VALIDATED_ALLOWLIST_PACKAGE",
            "final_report_sha256": sha256_file(summary / "REPORT.md"),
            "final_evidence_table_sha256": sha256_file(summary / "evidence_table.json"),
            "program_completion_status": "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
            "final_zip_validated_before_publication": True,
        }
    )
    write_json_atomic(summary / "analysis_manifest.json", analysis)
    reproducibility = read_json(summary / "REPRODUCIBILITY_MANIFEST.json")
    reproducibility.update(
        {
            "status": "COMPLETE",
            "program_status": "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
            "collection_status": "VALIDATED_ALLOWLIST_PACKAGE",
            "generated_output_sha256s": _hash_inventory(
                summary,
                [
                    name
                    for name in (*REQUIRED_ANALYSIS_FILES, *SUPPORTING_ANALYSIS_FILES)
                    if name != "REPRODUCIBILITY_MANIFEST.json"
                ],
            ),
            "package_validation_is_required_before_external_state_update": True,
        }
    )
    write_json_atomic(summary / "REPRODUCIBILITY_MANIFEST.json", reproducibility)
    validate_analysis_outputs(summary)
    if state.get("protocol_sha256") != analysis.get("protocol_sha256"):
        raise H2ProgramError("staged analysis protocol binding differs")
    return final_rows


def _write_package_metadata(
    stage: Path,
    *,
    state: Mapping[str, object],
    members: Sequence[PackageMember],
) -> None:
    rows = [
        {
            "member": item.member,
            "category": item.category,
            "bytes": (stage / PurePosixPath(item.member)).stat().st_size,
            "sha256": sha256_file(stage / PurePosixPath(item.member)),
        }
        for item in sorted(members, key=lambda value: value.member)
    ]
    manifest = {
        "schema_version": "h2-compact-package-manifest.v1",
        "status": "VALIDATED_BY_COLLECTION_BEFORE_ZIP_PUBLICATION",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "freeze_identity_sha256": state.get("freeze_identity_sha256"),
        "evidence_completed_at_utc": _evidence_timestamp(state),
        "allowlist_only": True,
        "member_count_excluding_metadata": len(rows),
        "member_inventory_sha256": canonical_sha256(rows),
        "members": rows,
        "exclusions": {
            "raw_datasets": True,
            "generated_or_recorded_audio": True,
            "onnx_and_model_weights": True,
            "credentials_tokens_and_secrets": True,
            "biometric_vectors_and_embeddings": True,
            "shared_or_large_caches": True,
            "sqlite_locks_and_temporary_files": True,
        },
    }
    write_json_atomic(stage / "PACKAGE_MANIFEST.json", manifest)
    checksum_names = [item.member for item in members] + ["PACKAGE_MANIFEST.json"]
    checksums = {
        name: {
            "sha256": sha256_file(stage / PurePosixPath(name)),
            "bytes": (stage / PurePosixPath(name)).stat().st_size,
        }
        for name in sorted(checksum_names)
    }
    write_json_atomic(
        stage / "PACKAGE_CHECKSUMS.json",
        {
            "schema_version": "h2-compact-package-checksums.v1",
            "algorithm": "sha256",
            "files": checksums,
        },
    )


def validate_staged_package(stage: Path) -> dict[str, object]:
    """Validate stage contents against the internal inventory and policy."""

    root = Path(stage).resolve(strict=True)
    manifest = read_json(root / "PACKAGE_MANIFEST.json")
    checksums = read_json(root / "PACKAGE_CHECKSUMS.json")
    raw_members = manifest.get("members")
    raw_checksums = checksums.get("files")
    if (
        manifest.get("schema_version") != "h2-compact-package-manifest.v1"
        or manifest.get("status") != "VALIDATED_BY_COLLECTION_BEFORE_ZIP_PUBLICATION"
        or checksums.get("schema_version") != "h2-compact-package-checksums.v1"
        or not isinstance(raw_members, list)
        or not isinstance(raw_checksums, Mapping)
    ):
        raise H2ProgramError("staged package metadata schema differs")
    member_rows = [dict(row) for row in raw_members if isinstance(row, Mapping)]
    if len(member_rows) != len(raw_members):
        raise H2ProgramError("staged package member inventory contains invalid rows")
    if manifest.get("member_inventory_sha256") != canonical_sha256(member_rows):
        raise H2ProgramError("staged package member inventory checksum differs")
    declared = {str(row.get("member")): row for row in member_rows}
    if len(declared) != len(member_rows) or manifest.get(
        "member_count_excluding_metadata"
    ) != len(member_rows):
        raise H2ProgramError("staged package member inventory count/uniqueness differs")
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    expected = set(declared) | {"PACKAGE_MANIFEST.json", "PACKAGE_CHECKSUMS.json"}
    if actual != expected:
        raise H2ProgramError(
            f"staged package contents differ: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    if set(map(str, raw_checksums)) != expected - {"PACKAGE_CHECKSUMS.json"}:
        raise H2ProgramError("staged package checksum membership differs")
    required = {f"summary/{name}" for name in REQUIRED_ANALYSIS_FILES}
    required.update(f"deployment/h2_arm64/{name}" for name in ARM64_PACKAGE_FILES)
    missing = required - actual
    if missing:
        raise H2ProgramError(
            "staged package lacks required members: " + ", ".join(sorted(missing))
        )
    total = 0
    for name in sorted(actual):
        path = root / PurePosixPath(name)
        payload = path.read_bytes()
        _validate_package_payload(name, payload)
        total += len(payload)
        if name == "PACKAGE_CHECKSUMS.json":
            continue
        row = raw_checksums.get(name)
        if (
            not isinstance(row, Mapping)
            or row.get("sha256") != hashlib.sha256(payload).hexdigest()
            or row.get("bytes") != len(payload)
        ):
            raise H2ProgramError(f"staged package checksum differs: {name}")
        if name in declared:
            declared_row = declared[name]
            if declared_row.get("sha256") != hashlib.sha256(
                payload
            ).hexdigest() or declared_row.get("bytes") != len(payload):
                raise H2ProgramError(f"staged package manifest differs: {name}")
    if total > MAX_PACKAGE_TOTAL_BYTES:
        raise H2ProgramError("staged package exceeds conservative total size limit")
    report = (root / "summary/REPORT.md").read_text(encoding="utf-8")
    if "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM" not in report:
        raise H2ProgramError("staged final report lacks exact completion status")
    evidence = read_json(root / "summary/evidence_table.json")
    rows = evidence.get("rows")
    if (
        evidence.get("collection_status") != "VALID"
        or not isinstance(rows, list)
        or tuple(str(row.get("label")) for row in rows if isinstance(row, Mapping))
        != EVIDENCE_LABELS
        or not all(
            isinstance(row, Mapping) and row.get("acceptable") is True for row in rows
        )
    ):
        raise H2ProgramError("staged final evidence table is not fully valid")
    return {
        "status": "PASS",
        "member_count": len(actual),
        "total_uncompressed_bytes": total,
        "member_inventory_sha256": manifest.get("member_inventory_sha256"),
    }


def create_deterministic_zip(stage: Path, destination: Path) -> str:
    """Create a byte-deterministic ZIP from an already validated stage."""

    validate_staged_package(stage)
    root = Path(stage).resolve(strict=True)
    target = Path(destination).resolve(strict=False)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".partial", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
            allowZip64=False,
        ) as archive:
            for source in sorted(
                (path for path in root.rglob("*") if path.is_file()),
                key=lambda path: path.relative_to(root).as_posix(),
            ):
                member = source.relative_to(root).as_posix()
                info = zipfile.ZipInfo(member, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.flag_bits = 0
                archive.writestr(
                    info,
                    source.read_bytes(),
                    compress_type=zipfile.ZIP_DEFLATED,
                    compresslevel=9,
                )
        validate_package_zip(temporary)
        digest = sha256_file(temporary)
        if target.is_file():
            if sha256_file(target) != digest:
                raise H2ProgramError(
                    f"existing deterministic package bytes differ: {target}"
                )
            temporary.unlink(missing_ok=True)
        else:
            os.replace(temporary, target)
        return sha256_file(target)
    finally:
        temporary.unlink(missing_ok=True)


def validate_package_zip(
    path: Path, *, expected_sha256: str | None = None
) -> dict[str, object]:
    """Self-validate ZIP names, allowlist, checksums, payloads, and CRCs."""

    source = Path(path).resolve(strict=True)
    observed_sha = sha256_file(source)
    if expected_sha256 is not None and observed_sha != expected_sha256:
        raise H2ProgramError("final ZIP SHA-256 differs from collection receipt")
    with zipfile.ZipFile(source, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(value.casefold() for value in names)):
            raise H2ProgramError("final ZIP contains duplicate member names")
        if archive.testzip() is not None:
            raise H2ProgramError("final ZIP CRC validation failed")
        payloads: dict[str, bytes] = {}
        total = 0
        for info in infos:
            _validate_package_member_name(info.filename)
            if info.is_dir() or info.flag_bits & 0x1:
                raise H2ProgramError(
                    "final ZIP contains a directory or encrypted member"
                )
            if info.file_size > MAX_PACKAGE_MEMBER_BYTES:
                raise H2ProgramError(f"final ZIP member is too large: {info.filename}")
            payload = archive.read(info)
            if len(payload) != info.file_size:
                raise H2ProgramError(
                    f"final ZIP member length differs: {info.filename}"
                )
            _validate_package_payload(info.filename, payload)
            payloads[info.filename] = payload
            total += len(payload)
        if total > MAX_PACKAGE_TOTAL_BYTES:
            raise H2ProgramError("final ZIP uncompressed size exceeds limit")
    if (
        "PACKAGE_MANIFEST.json" not in payloads
        or "PACKAGE_CHECKSUMS.json" not in payloads
    ):
        raise H2ProgramError("final ZIP lacks internal package metadata")
    manifest = json.loads(payloads["PACKAGE_MANIFEST.json"])
    checksums = json.loads(payloads["PACKAGE_CHECKSUMS.json"])
    if not isinstance(manifest, Mapping) or not isinstance(checksums, Mapping):
        raise H2ProgramError("final ZIP metadata roots are invalid")
    if (
        manifest.get("schema_version") != "h2-compact-package-manifest.v1"
        or manifest.get("status") != "VALIDATED_BY_COLLECTION_BEFORE_ZIP_PUBLICATION"
        or checksums.get("schema_version") != "h2-compact-package-checksums.v1"
    ):
        raise H2ProgramError("final ZIP metadata schema/status differs")
    rows = manifest.get("members")
    files = checksums.get("files")
    if not isinstance(rows, list) or not isinstance(files, Mapping):
        raise H2ProgramError("final ZIP internal inventory is invalid")
    if not all(isinstance(row, Mapping) for row in rows):
        raise H2ProgramError("final ZIP manifest has invalid member rows")
    declared = {str(row.get("member")): row for row in rows if isinstance(row, Mapping)}
    if len(declared) != len(rows) or manifest.get(
        "member_count_excluding_metadata"
    ) != len(rows):
        raise H2ProgramError("final ZIP manifest membership count differs")
    expected_names = set(declared) | {"PACKAGE_MANIFEST.json", "PACKAGE_CHECKSUMS.json"}
    if set(payloads) != expected_names or set(map(str, files)) != expected_names - {
        "PACKAGE_CHECKSUMS.json"
    }:
        raise H2ProgramError("final ZIP member allowlist differs")
    if manifest.get("member_inventory_sha256") != canonical_sha256(rows):
        raise H2ProgramError("final ZIP member inventory identity differs")
    for name, raw in files.items():
        row = raw if isinstance(raw, Mapping) else {}
        payload = payloads[str(name)]
        if row.get("sha256") != hashlib.sha256(payload).hexdigest() or row.get(
            "bytes"
        ) != len(payload):
            raise H2ProgramError(f"final ZIP internal checksum differs: {name}")
    for name, raw in declared.items():
        row = raw if isinstance(raw, Mapping) else {}
        payload = payloads[name]
        if row.get("sha256") != hashlib.sha256(payload).hexdigest() or row.get(
            "bytes"
        ) != len(payload):
            raise H2ProgramError(f"final ZIP manifest checksum differs: {name}")
    required = {f"summary/{name}" for name in REQUIRED_ANALYSIS_FILES}
    required.update(f"deployment/h2_arm64/{name}" for name in ARM64_PACKAGE_FILES)
    if not required.issubset(payloads):
        raise H2ProgramError("final ZIP lacks required summary or ARM64 members")
    return {
        "status": "VALID",
        "path": str(source),
        "sha256": observed_sha,
        "member_count": len(payloads),
        "total_uncompressed_bytes": total,
        "member_inventory_sha256": manifest.get("member_inventory_sha256"),
    }


def _verify_analysis_receipt(
    paths: ProgramPaths,
    state_row: Mapping[str, object],
    state: Mapping[str, object],
) -> dict[str, object]:
    raw_path = state_row.get("result_path")
    expected_sha = state_row.get("result_sha256")
    if not isinstance(raw_path, str) or not isinstance(expected_sha, str):
        raise H2ProgramError("analysis state lacks a receipt path/checksum")
    path = Path(raw_path).resolve(strict=True)
    if not _is_within(path, paths.summary_root) or sha256_file(path) != expected_sha:
        raise H2ProgramError("analysis receipt path/checksum differs")
    receipt = read_json(path)
    if (
        receipt.get("schema_version") != "h2-analysis-receipt.v1"
        or receipt.get("status") != "COMPLETE"
        or receipt.get("protocol_sha256") != state.get("protocol_sha256")
        or receipt.get("job_manifest_sha256") != state.get("job_manifest_sha256")
        or not isinstance(receipt.get("immutable_output_inventory"), Mapping)
    ):
        raise H2ProgramError("analysis receipt binding/status differs")
    for name, raw in receipt["immutable_output_inventory"].items():  # type: ignore[union-attr]
        output = paths.summary_root / str(name)
        if (
            not output.is_file()
            or not isinstance(raw, Mapping)
            or raw.get("sha256") != sha256_file(output)
            or raw.get("bytes") != output.stat().st_size
        ):
            raise H2ProgramError(f"immutable analysis output differs: {name}")
    return receipt


def _package_destination(paths: ProgramPaths, state: Mapping[str, object]) -> Path:
    protocol = re.sub(
        r"[^A-Za-z0-9_.-]+", "_", str(state.get("protocol_id") or "unknown")
    ).strip("._-")
    evidence = datetime.fromisoformat(
        _evidence_timestamp(state).replace("Z", "+00:00")
    ).astimezone(timezone.utc)
    timestamp = evidence.strftime("%Y%m%dT%H%M%SZ")
    return (
        paths.summary_root.parent
        / f"h2_complete_product_pipeline_{protocol}_{timestamp}.zip"
    ).resolve(strict=False)


def execute_collection(
    paths: ProgramPaths,
    *,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
    require_complete: bool,
) -> dict[str, object]:
    """Create and validate the final compact H2 reproducibility package."""

    rows = _state_rows(state, jobs)
    analysis_jobs = [job for job in jobs if job.job_kind == "analysis"]
    collection_jobs = [job for job in jobs if job.job_kind == "collection"]
    if len(analysis_jobs) != 1 or len(collection_jobs) != 1:
        raise H2ProgramError("exactly one analysis and one collection job are required")
    analysis_row = rows[analysis_jobs[0].job_id]
    collection_row = rows[collection_jobs[0].job_id]
    if analysis_row.get("state") != "COMPLETE":
        raise H2ProgramError("final collection requires controller-complete analysis")
    if require_complete and collection_row.get("state") != "RUNNING":
        raise H2ProgramError("controller-managed collection job must be RUNNING")
    _verify_analysis_receipt(paths, analysis_row, state)
    validate_analysis_outputs(paths.summary_root)
    artifacts = validate_prerequisite_artifacts(state, jobs)
    _require_analysis_completion_contract(paths, artifacts)
    # Pass 1: explicit source inventory, path/checksum validation, and security
    # scan. No recursive result or workspace tree is accepted.
    members = build_package_allowlist(paths, artifacts)
    tables = _build_analysis_tables(paths, state, artifacts)
    memory = _memory_budget_document(tables["h2_resource_results.csv"])
    linux = _linux_portability_document(artifacts)
    questions = _report_questions(
        tables,
        memory,
        linux,
        read_json(paths.freeze_path),
    )
    _validate_report_question_contract(questions)
    final_evidence = build_final_evidence_table(
        paths,
        artifacts,
        final_report_complete=True,
        final_zip_valid=True,
    )
    if not all(row.get("acceptable") is True for row in final_evidence):
        raise H2ProgramError("final collection evidence table contains a failed row")

    staging_parent = paths.workspace / "collection_staging"
    staging_parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="h2_final_", dir=staging_parent)).resolve()
    if not _is_within(stage, staging_parent):
        raise H2ProgramError("collection staging path escaped its workspace")
    try:
        # Pass 2: stage only allowlisted bytes, finalize the private report,
        # validate the staged inventory, then create and self-validate the ZIP.
        _stage_package_members(members, stage)
        _finalize_staged_summary(
            stage,
            state=state,
            tables=tables,
            memory=memory,
            linux=linux,
            evidence_rows=final_evidence,
        )
        _write_package_metadata(stage, state=state, members=members)
        staged_validation = validate_staged_package(stage)
        destination = _package_destination(paths, state)
        package_sha = create_deterministic_zip(stage, destination)
        zip_validation = validate_package_zip(destination, expected_sha256=package_sha)

        # Publish the four collection-finalizable summary files only after ZIP
        # validation. Immutable analysis tables remain byte-for-byte unchanged.
        staged_summary = stage / "summary"
        _write_text_atomic(
            paths.summary_root / "REPORT.md",
            (staged_summary / "REPORT.md").read_text(encoding="utf-8"),
        )
        for name in (
            "evidence_table.json",
            "analysis_manifest.json",
            "REPRODUCIBILITY_MANIFEST.json",
        ):
            write_json_atomic(
                paths.summary_root / name, read_json(staged_summary / name)
            )
        summary_validation = validate_analysis_outputs(paths.summary_root)
        published_evidence = read_json(paths.summary_root / "evidence_table.json")
        if published_evidence.get("collection_status") != "VALID":
            raise H2ProgramError("published evidence table did not finalize")

        receipt_path = paths.summary_root / "collection_receipt.json"
        receipt = {
            "schema_version": "h2-final-collection-receipt.v1",
            "status": "VALID",
            "protocol_id": state.get("protocol_id"),
            "protocol_sha256": state.get("protocol_sha256"),
            "job_manifest_sha256": state.get("job_manifest_sha256"),
            "freeze_identity_sha256": state.get("freeze_identity_sha256"),
            "evidence_completed_at_utc": _evidence_timestamp(state),
            "upload_path": str(destination),
            "zip_sha256": package_sha,
            "zip_bytes": destination.stat().st_size,
            "staged_validation": staged_validation,
            "zip_validation": zip_validation,
            "summary_validation": summary_validation,
            "allowlist_member_count_excluding_metadata": len(members),
            "raw_datasets_included": False,
            "audio_included": False,
            "onnx_or_model_weights_included": False,
            "credentials_or_secrets_included": False,
            "biometric_vectors_included": False,
            "marked_complete_before_zip_validation": False,
        }
        write_json_atomic(receipt_path, receipt)
        # Revalidate the published archive and receipt immediately before
        # returning success to the controller.
        validate_package_zip(destination, expected_sha256=package_sha)
        if read_json(receipt_path) != receipt:
            raise H2ProgramError("published collection receipt bytes differ")
        return {
            "state": "complete",
            "result_path": str(receipt_path),
            "result_sha256": sha256_file(receipt_path),
            "completed_cases": 0,
            "completed_audio_sec": 0.0,
            "cache_hits": 0,
            "status": "VALID",
            "package_path": str(destination),
            "package_sha256": package_sha,
        }
    finally:
        if stage.is_dir() and _is_within(stage, staging_parent):
            shutil.rmtree(stage)


def validate_published_completion(
    paths: ProgramPaths,
    *,
    state: Mapping[str, object],
    jobs: Sequence[H2Job],
) -> dict[str, object]:
    """Read-only validation for a controller-complete published package."""

    rows = _state_rows(state, jobs)
    if any(row.get("state") not in {"COMPLETE", "SUPERSEDED"} for row in rows.values()):
        raise H2ProgramError("published completion has a non-successful job")
    analysis_jobs = [job for job in jobs if job.job_kind == "analysis"]
    collection_jobs = [job for job in jobs if job.job_kind == "collection"]
    if len(analysis_jobs) != 1 or len(collection_jobs) != 1:
        raise H2ProgramError("published completion lacks final jobs")
    _verify_analysis_receipt(paths, rows[analysis_jobs[0].job_id], state)
    collection_row = rows[collection_jobs[0].job_id]
    raw_path = collection_row.get("result_path")
    expected_sha = collection_row.get("result_sha256")
    if not isinstance(raw_path, str) or not isinstance(expected_sha, str):
        raise H2ProgramError("published completion lacks collection receipt")
    receipt_path = Path(raw_path).resolve(strict=True)
    if (
        not _is_within(receipt_path, paths.summary_root)
        or sha256_file(receipt_path) != expected_sha
    ):
        raise H2ProgramError("published collection receipt differs")
    receipt = read_json(receipt_path)
    if (
        receipt.get("schema_version") != "h2-final-collection-receipt.v1"
        or receipt.get("status") != "VALID"
        or receipt.get("protocol_sha256") != state.get("protocol_sha256")
        or receipt.get("job_manifest_sha256") != state.get("job_manifest_sha256")
    ):
        raise H2ProgramError("published collection receipt binding differs")
    artifacts = validate_prerequisite_artifacts(state, jobs)
    _require_analysis_completion_contract(paths, artifacts)
    build_package_allowlist(paths, artifacts)
    validate_analysis_outputs(paths.summary_root)
    package = validate_package_zip(
        Path(str(receipt.get("upload_path") or "")),
        expected_sha256=str(receipt.get("zip_sha256") or ""),
    )
    evidence = read_json(paths.summary_root / "evidence_table.json")
    evidence_rows = evidence.get("rows")
    if (
        evidence.get("collection_status") != "VALID"
        or not isinstance(evidence_rows, list)
        or tuple(
            str(row.get("label")) for row in evidence_rows if isinstance(row, Mapping)
        )
        != EVIDENCE_LABELS
        or not all(
            isinstance(row, Mapping) and row.get("acceptable") is True
            for row in evidence_rows
        )
    ):
        raise H2ProgramError("published evidence table differs")
    report = (paths.summary_root / "REPORT.md").read_text(encoding="utf-8")
    if "Final status: `COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`" not in report:
        raise H2ProgramError("published report completion status differs")
    return {
        "status": "VALID",
        "collection_receipt_path": str(receipt_path),
        "collection_receipt_sha256": expected_sha,
        "package": package,
    }


def _handoff_with_final_block(
    current: str,
    *,
    state: Mapping[str, object],
    receipt: Mapping[str, object],
) -> str:
    start = "<!-- H2_COMPLETE_PRODUCT_PIPELINE:START -->"
    end = "<!-- H2_COMPLETE_PRODUCT_PIPELINE:END -->"
    block = "\n".join(
        (
            start,
            "## H2 complete product-pipeline final handoff",
            "",
            "Status: `COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`",
            "",
            f"Protocol: `{state.get('protocol_id')}` (`{state.get('protocol_sha256')}`)",
            "",
            f"Final ZIP: `{receipt.get('upload_path')}`",
            "",
            f"SHA-256: `{receipt.get('zip_sha256')}`",
            "",
            "The ZIP was validated against its explicit member allowlist, internal "
            "checksums, required-file set, size limits, forbidden paths/suffixes, "
            "secret patterns, and biometric-vector exclusions immediately before "
            "this completion record was written. ARM64 remains package preparation, "
            "not target-hardware validation.",
            end,
        )
    )
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(current):
        return pattern.sub(block, current).rstrip() + "\n"
    return current.rstrip() + "\n\n" + block + "\n"


def finalize_program_completion(
    paths: ProgramPaths,
    *,
    state: dict[str, object],
    jobs: Sequence[H2Job],
    collection_result_path: Path | str | None = None,
) -> dict[str, object]:
    """Revalidate all evidence/package bytes, then publish exact final state."""

    rows = _state_rows(state, jobs)
    if any(row.get("state") not in {"COMPLETE", "SUPERSEDED"} for row in rows.values()):
        raise H2ProgramError("program completion requires every job to be successful")
    analysis_jobs = [job for job in jobs if job.job_kind == "analysis"]
    collection_jobs = [job for job in jobs if job.job_kind == "collection"]
    if len(analysis_jobs) != 1 or len(collection_jobs) != 1:
        raise H2ProgramError("program completion lacks final analysis/collection jobs")
    collection_row = rows[collection_jobs[0].job_id]
    raw_receipt = collection_result_path or collection_row.get("result_path")
    expected_receipt_sha = collection_row.get("result_sha256")
    if not isinstance(raw_receipt, (str, Path)) or not isinstance(
        expected_receipt_sha, str
    ):
        raise H2ProgramError("collection state lacks receipt binding")
    receipt_path = Path(raw_receipt).resolve(strict=True)
    if (
        not _is_within(receipt_path, paths.summary_root)
        or sha256_file(receipt_path) != expected_receipt_sha
    ):
        raise H2ProgramError("collection receipt checksum differs")
    receipt = read_json(receipt_path)
    if (
        receipt.get("schema_version") != "h2-final-collection-receipt.v1"
        or receipt.get("status") != "VALID"
        or receipt.get("protocol_sha256") != state.get("protocol_sha256")
        or receipt.get("job_manifest_sha256") != state.get("job_manifest_sha256")
    ):
        raise H2ProgramError("collection receipt status/binding differs")

    validate_published_completion(paths, state=state, jobs=jobs)

    # Final fail-closed audit: result paths may be files or directories, all
    # checksums are reread, semantic gates rerun, and both published summary and
    # ZIP bytes are rescanned immediately before the external completion state.
    artifacts = validate_prerequisite_artifacts(state, jobs)
    _require_analysis_completion_contract(paths, artifacts)
    build_package_allowlist(paths, artifacts)
    validate_analysis_outputs(paths.summary_root)
    package_path = Path(str(receipt.get("upload_path") or "")).resolve(strict=True)
    package_validation = validate_package_zip(
        package_path, expected_sha256=str(receipt.get("zip_sha256") or "")
    )
    evidence = read_json(paths.summary_root / "evidence_table.json")
    evidence_rows = evidence.get("rows")
    if (
        evidence.get("collection_status") != "VALID"
        or not isinstance(evidence_rows, list)
        or not all(
            isinstance(row, Mapping) and row.get("acceptable") is True
            for row in evidence_rows
        )
    ):
        raise H2ProgramError("published evidence table is not complete")
    report = (paths.summary_root / "REPORT.md").read_text(encoding="utf-8")
    if "Final status: `COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM`" not in report:
        raise H2ProgramError("published report lacks exact final status")

    handoff_path = paths.evaluation_root / "docs/full_pipeline/PROGRAM_HANDOFF.md"
    prior_state_path = (
        paths.evaluation_root / "runs/full_pipeline_program/PROGRAM_STATE.json"
    )
    current_handoff = handoff_path.read_text(encoding="utf-8-sig")
    next_handoff = _handoff_with_final_block(
        current_handoff, state=state, receipt=receipt
    )
    _write_text_atomic(handoff_path, next_handoff)
    prior = read_json(prior_state_path)
    prior["status"] = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
    prior["h2_product_pipeline_program"] = {
        "schema_version": "h2-final-program-reference.v1",
        "status": "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
        "protocol_id": state.get("protocol_id"),
        "protocol_sha256": state.get("protocol_sha256"),
        "job_manifest_sha256": state.get("job_manifest_sha256"),
        "freeze_identity_sha256": state.get("freeze_identity_sha256"),
        "completed_at_utc": _evidence_timestamp(state),
        "collection_receipt_path": str(receipt_path),
        "collection_receipt_sha256": expected_receipt_sha,
        "upload_path": str(package_path),
        "zip_sha256": receipt.get("zip_sha256"),
        "zip_bytes": receipt.get("zip_bytes"),
        "zip_member_count": package_validation.get("member_count"),
        "arm64_hardware_validated": False,
    }
    canonical = prior.get("canonical_artifacts")
    if isinstance(canonical, dict):
        canonical["program_handoff"] = {
            "path": "docs/full_pipeline/PROGRAM_HANDOFF.md",
            "sha256": sha256_file(handoff_path),
        }
    write_json_atomic(prior_state_path, prior)
    state["status"] = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
    state["detail"] = "All H2 evidence, final report, and compact ZIP validated"
    state["final_collection"] = dict(prior["h2_product_pipeline_program"])
    return {
        "status": "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM",
        "package_path": str(package_path),
        "package_sha256": receipt.get("zip_sha256"),
    }
