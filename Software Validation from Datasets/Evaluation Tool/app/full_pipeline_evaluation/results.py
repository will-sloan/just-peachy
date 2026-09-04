"""Atomic common result-tree construction and checksum-bound validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Iterable, Mapping, Sequence
import uuid

from .io import replace_file_atomic, write_bytes_atomic
from .schema import (
    ARTIFACT_SUPPORT_IDS,
    CHECKSUM_SCHEMA_VERSION,
    COMPACT_RESULT_TREE_SCHEMA_VERSION,
    DIAGNOSTIC_MANIFEST_SCHEMA_VERSION,
    FIXED_REQUIRED_FILES,
    METRIC_VIEWS,
    REFERENCE_MANIFEST_SCHEMA_VERSION,
    REQUIRED_DIRECTORIES,
    RESULT_TREE_SCHEMA_VERSION,
    RESULT_TREE_SCHEMA_VERSIONS,
    TERMINAL_RUN_STATES,
    ResultSchemaError,
    build_summary_document,
    fixed_required_files,
    is_sha256,
    normalize_reuse_identity,
    validate_directory_manifest,
    validate_metric_document,
    validate_model_assets_document,
    validate_pipeline_identity_document,
    validate_run_document,
    validate_summary_document,
)


class ResultTreeError(RuntimeError):
    """Base result-tree construction or validation error."""


class ResultReuseError(ResultTreeError):
    """Existing result bytes cannot be reused for the requested identity."""


class ResultTreeValidationError(ResultTreeError):
    """One or more result-tree invariants failed."""

    def __init__(self, issues: Sequence["ValidationIssue"]) -> None:
        self.issues = tuple(issues)
        super().__init__(
            "Full-pipeline result validation failed:\n- "
            + "\n- ".join(
                f"{value.code} [{value.logical_path}]: {value.message}"
                for value in self.issues
            )
        )


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    logical_path: str
    message: str


@dataclass(frozen=True)
class ResultTreeValidation:
    root: Path
    run_id: str | None
    run_status: str | None
    checked_file_count: int
    issues: tuple[ValidationIssue, ...]

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def reusable(self) -> bool:
        return self.valid and self.run_status == "complete"

    def raise_for_errors(self) -> None:
        if self.issues:
            raise ResultTreeValidationError(self.issues)


class ResultTreeBuilder:
    """Build one immutable attempt tree with safe idempotent restart semantics.

    A partial attempt may be reopened only with the exact same canonical reuse
    identity.  Existing result artifacts are accepted only when their bytes are
    identical; a conflicting retry must use a new attempt directory.  The sole
    mutable document before finalization is ``run.json``, whose state may move
    forward while its run, attempt, and reuse identities remain fixed.
    """

    def __init__(
        self,
        root: Path,
        reuse_identity: Mapping[str, object],
        *,
        resume: bool = False,
        compact: bool = False,
    ) -> None:
        self.root = Path(root).resolve()
        self.reuse_identity = normalize_reuse_identity(reuse_identity)
        self.run_id: str | None = None
        self.pipeline_id = str(self.reuse_identity["pipeline_id"])
        self.result_tree_schema_version = (
            COMPACT_RESULT_TREE_SCHEMA_VERSION if compact else RESULT_TREE_SCHEMA_VERSION
        )
        self.event_log_path = "events.jsonl.gz" if compact else "events.jsonl"
        self._sealed = False
        if self.root.exists():
            if not self.root.is_dir():
                raise NotADirectoryError(self.root)
            if any(self.root.iterdir()) and not resume:
                raise FileExistsError(f"result root already exists: {self.root}")
            if resume:
                self._inspect_resume_root()
        else:
            self.root.mkdir(parents=True)
        for relative in REQUIRED_DIRECTORIES:
            (self.root / relative).mkdir(parents=True, exist_ok=True)

    def publish_run(self, document: Mapping[str, object]) -> dict[str, object]:
        value = dict(document)
        validate_run_document(value)
        if value["reuse_identity"] != self.reuse_identity:
            raise ResultReuseError("run.json reuse identity differs from the builder")
        if value.get("result_tree_schema_version") != self.result_tree_schema_version:
            raise ResultReuseError("run.json result-tree version differs from the builder")
        self._bind_run_id(str(value["run_id"]))
        target = self.root / "run.json"
        if target.is_file():
            prior = _read_json(target)
            _validate_run_update(prior, value)
        return self._publish_json("run.json", value, allow_update=True)

    def publish_pipeline_identity(
        self, document: Mapping[str, object]
    ) -> dict[str, object]:
        value = dict(document)
        validate_pipeline_identity_document(value)
        self._require_run_document_identity(value)
        if value.get("pipeline_config_sha256") != self.reuse_identity[
            "pipeline_config_sha256"
        ]:
            raise ResultReuseError("pipeline identity configuration hash differs")
        return self._publish_json("pipeline_identity.json", value)

    def publish_model_assets(
        self, document: Mapping[str, object]
    ) -> dict[str, object]:
        value = dict(document)
        validate_model_assets_document(value)
        self._require_run_document_identity(value)
        _assert_no_biometric_vectors(value)
        return self._publish_json("model_assets.json", value)

    def publish_events(
        self, rows: Iterable[Mapping[str, object]]
    ) -> dict[str, object]:
        if self.result_tree_schema_version == RESULT_TREE_SCHEMA_VERSION:
            return self._publish_jsonl(self.event_log_path, rows)
        temporary = self.root / f".events-{uuid.uuid4().hex}.jsonl.gz"
        try:
            with temporary.open("wb") as raw:
                with gzip.GzipFile(
                    filename="", fileobj=raw, mode="wb", mtime=0
                ) as stream:
                    for raw_row in rows:
                        row = dict(raw_row)
                        _assert_no_biometric_vectors(row)
                        stream.write(
                            (
                                json.dumps(
                                    row,
                                    sort_keys=True,
                                    separators=(",", ":"),
                                    ensure_ascii=False,
                                )
                                + "\n"
                            ).encode("utf-8")
                        )
            return self.publish_events_file(temporary)
        finally:
            if temporary.exists():
                temporary.unlink()

    def publish_events_file(self, source: Path) -> dict[str, object]:
        """Publish a prebuilt event stream without materializing it in memory."""

        path = Path(source).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        _validate_jsonl_or_raise(path, compressed=self.event_log_path.endswith(".gz"))
        return self._publish_file(self.event_log_path, path)

    def publish_predictions(
        self,
        *,
        transcript_rows: Iterable[Mapping[str, object]],
        labelled_rows: Iterable[Mapping[str, object]],
        diarization_rttm: str,
    ) -> dict[str, dict[str, object]]:
        _validate_rttm(diarization_rttm, allow_empty=True)
        return {
            "transcript": self._publish_jsonl(
                "predictions/transcript.jsonl", transcript_rows
            ),
            "labelled_transcript": self._publish_jsonl(
                "predictions/labelled_transcript.jsonl", labelled_rows
            ),
            "diarization": self._publish_bytes(
                "predictions/diarization.rttm",
                diarization_rttm.encode("utf-8"),
            ),
        }

    def publish_references(
        self,
        manifest: Mapping[str, object],
        *,
        artifacts: Mapping[str, bytes] | None = None,
    ) -> dict[str, object]:
        return self._publish_directory(
            "references",
            REFERENCE_MANIFEST_SCHEMA_VERSION,
            manifest,
            artifacts or {},
        )

    def publish_metric(
        self, view: str, document: Mapping[str, object]
    ) -> dict[str, object]:
        value = dict(document)
        validate_metric_document(value, expected_view=view)
        self._require_run_document_identity(value)
        return self._publish_json(f"metrics/{view}.json", value)

    def publish_diagnostics(
        self,
        manifest: Mapping[str, object],
        *,
        artifacts: Mapping[str, bytes] | None = None,
    ) -> dict[str, object]:
        return self._publish_directory(
            "diagnostics",
            DIAGNOSTIC_MANIFEST_SCHEMA_VERSION,
            manifest,
            artifacts or {},
        )

    def finalize(self) -> ResultTreeValidation:
        if self._sealed:
            report = validate_result_tree(
                self.root,
                expected_reuse_identity=self.reuse_identity,
            )
            report.raise_for_errors()
            return report
        self._require_writable()
        run = _read_json(self.root / "run.json")
        validate_run_document(run)
        if run.get("status") not in TERMINAL_RUN_STATES:
            raise ResultTreeError("run.json must be terminal before finalization")
        self._bind_run_id(str(run["run_id"]))
        metric_documents = {
            view: _read_json(self.root / f"metrics/{view}.json")
            for view in METRIC_VIEWS
        }
        summary = build_summary_document(
            run_id=self._require_run_id(),
            pipeline_id=self.pipeline_id,
            completion_state=str(run["status"]),
            metric_documents=metric_documents,
        )
        self._publish_json("metrics/summary.json", summary)
        _validate_pre_checksum_tree(
            self.root,
            expected_identity=self.reuse_identity,
            result_tree_schema_version=self.result_tree_schema_version,
        )
        entries = {
            relative: _checksum_entry(self.root / relative, relative)
            for relative in _materialized_relative_files(self.root)
            if relative != "checksums.json"
        }
        checksum_document = {
            "schema_version": CHECKSUM_SCHEMA_VERSION,
            "result_tree_schema_version": self.result_tree_schema_version,
            "run_id": self._require_run_id(),
            "reuse_identity_sha256": self.reuse_identity["identity_sha256"],
            "hash_algorithm": "sha256",
            "created_at_utc": _utc_now(),
            "entries": dict(sorted(entries.items())),
        }
        self._publish_json("checksums.json", checksum_document)
        report = validate_result_tree(
            self.root,
            expected_reuse_identity=self.reuse_identity,
        )
        report.raise_for_errors()
        self._sealed = True
        return report

    def _publish_directory(
        self,
        directory: str,
        schema_version: str,
        manifest: Mapping[str, object],
        artifacts: Mapping[str, bytes],
    ) -> dict[str, object]:
        run_id = self._require_run_id()
        raw_entries = manifest.get("artifacts")
        if not isinstance(raw_entries, list):
            raise ResultSchemaError(f"{directory} manifest artifacts must be a list")
        payloads = {_normalize_path(key): bytes(value) for key, value in artifacts.items()}
        entries: list[dict[str, object]] = []
        expected_payloads: set[str] = set()
        for raw in raw_entries:
            if not isinstance(raw, Mapping):
                raise ResultSchemaError(f"{directory} manifest entry must be an object")
            entry = dict(raw)
            logical_path = _normalize_path(str(entry.get("logical_path") or ""))
            if not logical_path.startswith(f"{directory}/"):
                raise ResultSchemaError(f"{directory} artifact path escapes its directory")
            entry["logical_path"] = logical_path
            if entry.get("status") == "available":
                try:
                    payload = payloads[logical_path]
                except KeyError as exc:
                    raise ResultSchemaError(
                        f"available {directory} artifact has no payload: {logical_path}"
                    ) from exc
                expected_payloads.add(logical_path)
                entry.update(
                    {
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload),
                        "reason": None,
                    }
                )
            else:
                if logical_path in payloads:
                    raise ResultSchemaError(
                        f"unsupported {directory} artifact cannot have a payload"
                    )
                entry["sha256"] = None
                entry["bytes"] = None
            entries.append(entry)
        if set(payloads) != expected_payloads:
            raise ResultSchemaError(
                f"unregistered {directory} payloads: {sorted(set(payloads) - expected_payloads)}"
            )
        value = {
            **dict(manifest),
            "schema_version": schema_version,
            "run_id": run_id,
            "artifacts": entries,
        }
        validate_directory_manifest(value, directory=directory)
        for logical_path in sorted(expected_payloads):
            self._publish_bytes(logical_path, payloads[logical_path])
        return self._publish_json(f"{directory}/manifest.json", value)

    def _publish_json(
        self,
        logical_path: str,
        value: object,
        *,
        allow_update: bool = False,
    ) -> dict[str, object]:
        _assert_no_biometric_vectors(value)
        payload = (
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        ).encode("utf-8")
        return self._publish_bytes(logical_path, payload, allow_update=allow_update)

    def _publish_jsonl(
        self,
        logical_path: str,
        rows: Iterable[Mapping[str, object]],
    ) -> dict[str, object]:
        materialized = [dict(value) for value in rows]
        _assert_no_biometric_vectors(materialized)
        payload = "".join(
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
            for value in materialized
        ).encode("utf-8")
        return self._publish_bytes(logical_path, payload)

    def _publish_bytes(
        self,
        logical_path: str,
        payload: bytes,
        *,
        allow_update: bool = False,
    ) -> dict[str, object]:
        self._require_writable()
        relative = _normalize_path(logical_path)
        target = _safe_target(self.root, relative)
        if target.is_file() and target.read_bytes() == payload:
            return _checksum_entry(target, relative)
        if target.exists() and not allow_update:
            raise ResultReuseError(
                f"existing result artifact conflicts with retry bytes: {relative}"
            )
        write_bytes_atomic(target, payload)
        return _checksum_entry(target, relative)

    def _publish_file(self, logical_path: str, source: Path) -> dict[str, object]:
        """Atomically copy a large artifact with bounded memory and hash checks."""

        self._require_writable()
        relative = _normalize_path(logical_path)
        target = _safe_target(self.root, relative)
        source_sha = _sha256(source)
        source_bytes = source.stat().st_size
        if (
            target.is_file()
            and target.stat().st_size == source_bytes
            and _sha256(target) == source_sha
        ):
            return _checksum_entry(target, relative)
        if target.exists():
            raise ResultReuseError(
                f"existing result artifact conflicts with retry bytes: {relative}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp-{uuid.uuid4().hex}")
        try:
            with source.open("rb") as source_stream, temporary.open("wb") as output:
                shutil.copyfileobj(source_stream, output, length=1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            if temporary.stat().st_size != source_bytes or _sha256(temporary) != source_sha:
                raise ResultTreeError(f"large artifact copy verification failed: {relative}")
            replace_file_atomic(temporary, target)
        finally:
            # Verification can fail before the canonical replace helper owns
            # cleanup. Never allow exact-temp cleanup to hide that exception.
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        return _checksum_entry(target, relative)

    def _inspect_resume_root(self) -> None:
        run_path = self.root / "run.json"
        checksum_path = self.root / "checksums.json"
        files = [value for value in self.root.rglob("*") if value.is_file()]
        if files and not run_path.is_file():
            raise ResultReuseError("partial result has artifacts but no run.json identity")
        if run_path.is_file():
            run = _read_json(run_path)
            validate_run_document(run)
            observed_version = str(run["result_tree_schema_version"])
            if observed_version != self.result_tree_schema_version:
                raise ResultReuseError("partial result-tree version differs from builder")
            if normalize_reuse_identity(run["reuse_identity"]) != self.reuse_identity:
                raise ResultReuseError("partial result belongs to another reuse identity")
            self._bind_run_id(str(run["run_id"]))
        if checksum_path.is_file():
            report = validate_result_tree(
                self.root,
                expected_reuse_identity=self.reuse_identity,
            )
            report.raise_for_errors()
            self._sealed = True

    def _require_run_document_identity(self, value: Mapping[str, object]) -> None:
        if value.get("run_id") != self._require_run_id():
            raise ResultReuseError("artifact run ID differs from run.json")
        if value.get("pipeline_id") != self.pipeline_id:
            raise ResultReuseError("artifact pipeline ID differs from reuse identity")

    def _bind_run_id(self, run_id: str) -> None:
        if self.run_id is None:
            self.run_id = run_id
        elif self.run_id != run_id:
            raise ResultReuseError("attempt contains conflicting run IDs")

    def _require_run_id(self) -> str:
        if self.run_id is None:
            raise ResultTreeError("publish run.json before dependent artifacts")
        return self.run_id

    def _require_writable(self) -> None:
        if self._sealed:
            raise ResultReuseError("finalized result tree is immutable")


def validate_result_tree(
    root: Path,
    *,
    expected_reuse_identity: Mapping[str, object] | None = None,
) -> ResultTreeValidation:
    path = Path(root).resolve()
    issues: list[ValidationIssue] = []
    if not path.is_dir():
        return ResultTreeValidation(
            root=path,
            run_id=None,
            run_status=None,
            checked_file_count=0,
            issues=(ValidationIssue("missing_root", ".", "result root is missing"),),
        )
    for directory in REQUIRED_DIRECTORIES:
        if not (path / directory).is_dir():
            issues.append(_issue("missing_directory", directory, "required directory is missing"))
    run = _safe_json(path / "run.json", "run.json", issues)
    result_tree_schema_version = str(
        run.get("result_tree_schema_version") or RESULT_TREE_SCHEMA_VERSION
    )
    try:
        required_files = fixed_required_files(result_tree_schema_version)
    except ResultSchemaError as exc:
        issues.append(_issue("invalid_schema", "run.json", str(exc)))
        required_files = FIXED_REQUIRED_FILES
    for relative in required_files:
        if not (path / relative).is_file():
            issues.append(_issue("missing_artifact", relative, "required artifact is missing"))
    files = _materialized_relative_files(path)
    for relative in files:
        candidate = path / relative
        if candidate.is_symlink():
            issues.append(_issue("symlink_artifact", relative, "result artifacts cannot be symlinks"))
        if ".tmp-" in candidate.name or candidate.name.endswith((".tmp", ".partial")):
            issues.append(_issue("temporary_artifact", relative, "temporary artifact was not finalized"))

    pipeline = _safe_json(path / "pipeline_identity.json", "pipeline_identity.json", issues)
    assets = _safe_json(path / "model_assets.json", "model_assets.json", issues)
    references = _safe_json(path / "references/manifest.json", "references/manifest.json", issues)
    diagnostics = _safe_json(path / "diagnostics/manifest.json", "diagnostics/manifest.json", issues)
    summary = _safe_json(path / "metrics/summary.json", "metrics/summary.json", issues)
    checksums = _safe_json(path / "checksums.json", "checksums.json", issues)
    metrics = {
        view: _safe_json(path / f"metrics/{view}.json", f"metrics/{view}.json", issues)
        for view in METRIC_VIEWS
    }
    run_id = str(run.get("run_id")) if run else None
    run_status = str(run.get("status")) if run else None

    _capture_validation(lambda: validate_run_document(run), "run.json", issues)
    _capture_validation(
        lambda: validate_pipeline_identity_document(pipeline),
        "pipeline_identity.json",
        issues,
    )
    _capture_validation(
        lambda: validate_model_assets_document(assets), "model_assets.json", issues
    )
    _capture_validation(
        lambda: validate_directory_manifest(references, directory="references"),
        "references/manifest.json",
        issues,
    )
    _capture_validation(
        lambda: validate_directory_manifest(diagnostics, directory="diagnostics"),
        "diagnostics/manifest.json",
        issues,
    )
    for view, document in metrics.items():
        _capture_validation(
            lambda view=view, document=document: validate_metric_document(
                document, expected_view=view
            ),
            f"metrics/{view}.json",
            issues,
        )
    _capture_validation(
        lambda: validate_summary_document(summary, metrics),
        "metrics/summary.json",
        issues,
    )

    if run:
        if run.get("status") not in TERMINAL_RUN_STATES:
            issues.append(
                _issue(
                    "nonterminal_result",
                    "run.json",
                    "a finalized result tree must have a terminal run status",
                )
            )
        identity = run.get("reuse_identity")
        if isinstance(identity, Mapping):
            try:
                observed_identity = normalize_reuse_identity(identity)
                if expected_reuse_identity is not None:
                    expected = normalize_reuse_identity(expected_reuse_identity)
                    if observed_identity != expected:
                        issues.append(
                            _issue(
                                "reuse_identity_mismatch",
                                "run.json",
                                "result belongs to a different canonical reuse identity",
                            )
                        )
            except ResultSchemaError as exc:
                issues.append(_issue("invalid_schema", "run.json", str(exc)))
        _validate_cross_document_identities(
            run,
            pipeline,
            assets,
            metrics,
            summary,
            references,
            diagnostics,
            issues,
        )
        _validate_artifact_support(path, run, references, diagnostics, issues)
    event_log_path = (
        "events.jsonl.gz"
        if result_tree_schema_version == COMPACT_RESULT_TREE_SCHEMA_VERSION
        else "events.jsonl"
    )
    _validate_jsonl(
        path / event_log_path,
        event_log_path,
        issues,
        compressed=event_log_path.endswith(".gz"),
    )
    _validate_jsonl(
        path / "predictions/transcript.jsonl",
        "predictions/transcript.jsonl",
        issues,
    )
    _validate_jsonl(
        path / "predictions/labelled_transcript.jsonl",
        "predictions/labelled_transcript.jsonl",
        issues,
    )
    _validate_rttm_path(path / "predictions/diarization.rttm", issues)
    available_dynamic = _validate_manifest_files(path, "references", references, issues)
    available_dynamic |= _validate_manifest_files(path, "diagnostics", diagnostics, issues)
    allowed = set(required_files) | available_dynamic
    for relative in sorted(set(files) - allowed):
        issues.append(
            _issue("unregistered_artifact", relative, "artifact is not declared by the result schema")
        )
    _validate_checksums(path, checksums, files, run, issues)
    return ResultTreeValidation(
        root=path,
        run_id=run_id,
        run_status=run_status,
        checked_file_count=len(files),
        issues=tuple(issues),
    )


def result_tree_reusable(
    root: Path, expected_reuse_identity: Mapping[str, object]
) -> bool:
    """Return true only for a complete, exact-identity, checksum-valid tree."""

    try:
        report = validate_result_tree(
            root,
            expected_reuse_identity=expected_reuse_identity,
        )
    except (OSError, ValueError, ResultTreeError):
        return False
    return report.reusable


def _validate_pre_checksum_tree(
    root: Path,
    *,
    expected_identity: Mapping[str, object],
    result_tree_schema_version: str,
) -> None:
    required_files = fixed_required_files(result_tree_schema_version)
    missing = [
        relative
        for relative in required_files
        if relative != "checksums.json" and not (root / relative).is_file()
    ]
    if missing:
        raise ResultTreeError(f"result tree lacks required artifacts: {missing}")
    run = _read_json(root / "run.json")
    if normalize_reuse_identity(run["reuse_identity"]) != normalize_reuse_identity(
        expected_identity
    ):
        raise ResultReuseError("run identity changed before finalization")
    pipeline = _read_json(root / "pipeline_identity.json")
    assets = _read_json(root / "model_assets.json")
    validate_pipeline_identity_document(pipeline)
    validate_model_assets_document(assets)
    metrics = {
        view: _read_json(root / f"metrics/{view}.json") for view in METRIC_VIEWS
    }
    summary = _read_json(root / "metrics/summary.json")
    validate_summary_document(summary, metrics)
    references = _read_json(root / "references/manifest.json")
    diagnostics = _read_json(root / "diagnostics/manifest.json")
    validate_directory_manifest(references, directory="references")
    validate_directory_manifest(diagnostics, directory="diagnostics")
    issues: list[ValidationIssue] = []
    _validate_cross_document_identities(
        run,
        pipeline,
        assets,
        metrics,
        summary,
        references,
        diagnostics,
        issues,
    )
    _validate_artifact_support(root, run, references, diagnostics, issues)
    event_log_path = (
        "events.jsonl.gz"
        if result_tree_schema_version == COMPACT_RESULT_TREE_SCHEMA_VERSION
        else "events.jsonl"
    )
    _validate_jsonl(
        root / event_log_path,
        event_log_path,
        issues,
        compressed=event_log_path.endswith(".gz"),
    )
    _validate_jsonl(
        root / "predictions/transcript.jsonl",
        "predictions/transcript.jsonl",
        issues,
    )
    _validate_jsonl(
        root / "predictions/labelled_transcript.jsonl",
        "predictions/labelled_transcript.jsonl",
        issues,
    )
    _validate_rttm_path(root / "predictions/diarization.rttm", issues)
    dynamic = _validate_manifest_files(root, "references", references, issues)
    dynamic |= _validate_manifest_files(root, "diagnostics", diagnostics, issues)
    allowed = (set(required_files) - {"checksums.json"}) | dynamic
    for relative in set(_materialized_relative_files(root)) - allowed:
        issues.append(_issue("unregistered_artifact", relative, "artifact is not registered"))
    if issues:
        raise ResultTreeValidationError(issues)


def _validate_cross_document_identities(
    run: Mapping[str, object],
    pipeline: Mapping[str, object],
    assets: Mapping[str, object],
    metrics: Mapping[str, Mapping[str, object]],
    summary: Mapping[str, object],
    references: Mapping[str, object],
    diagnostics: Mapping[str, object],
    issues: list[ValidationIssue],
) -> None:
    run_id = run.get("run_id")
    identity = run.get("reuse_identity")
    pipeline_id = identity.get("pipeline_id") if isinstance(identity, Mapping) else None
    config_sha = (
        identity.get("pipeline_config_sha256") if isinstance(identity, Mapping) else None
    )
    for logical, document in (
        ("pipeline_identity.json", pipeline),
        ("model_assets.json", assets),
        ("metrics/summary.json", summary),
        *((f"metrics/{view}.json", metrics[view]) for view in METRIC_VIEWS),
    ):
        if document.get("run_id") != run_id:
            issues.append(_issue("identity_mismatch", logical, "run ID differs from run.json"))
        if document.get("pipeline_id") != pipeline_id:
            issues.append(
                _issue("identity_mismatch", logical, "pipeline ID differs from run.json")
            )
    for logical, document in (
        ("references/manifest.json", references),
        ("diagnostics/manifest.json", diagnostics),
    ):
        if document.get("run_id") != run_id:
            issues.append(_issue("identity_mismatch", logical, "run ID differs from run.json"))
    if pipeline.get("pipeline_config_sha256") != config_sha:
        issues.append(
            _issue(
                "identity_mismatch",
                "pipeline_identity.json",
                "pipeline configuration hash differs from run.json",
            )
        )
    if summary.get("completion_state") != run.get("status"):
        issues.append(
            _issue(
                "identity_mismatch",
                "metrics/summary.json",
                "summary completion state differs from run.json",
            )
        )


def _validate_artifact_support(
    root: Path,
    run: Mapping[str, object],
    references: Mapping[str, object],
    diagnostics: Mapping[str, object],
    issues: list[ValidationIssue],
) -> None:
    support = run.get("artifact_support")
    if not isinstance(support, Mapping) or set(support) != set(ARTIFACT_SUPPORT_IDS):
        return
    compact = (
        run.get("result_tree_schema_version") == COMPACT_RESULT_TREE_SCHEMA_VERSION
    )
    file_by_support = {
        "events": "events.jsonl.gz" if compact else "events.jsonl",
        "transcript_predictions": "predictions/transcript.jsonl",
        "labelled_transcript_predictions": "predictions/labelled_transcript.jsonl",
        "diarization_predictions": "predictions/diarization.rttm",
    }
    for artifact_id, relative in file_by_support.items():
        raw = support[artifact_id]
        if isinstance(raw, Mapping) and raw.get("status") == "unsupported":
            path = root / relative
            if path.is_file() and path.stat().st_size != 0:
                issues.append(
                    _issue(
                        "unsupported_artifact_has_content",
                        relative,
                        "unsupported artifact must be an explicit empty placeholder",
                    )
                )
    for artifact_id, manifest in (
        ("references", references),
        ("diagnostics", diagnostics),
    ):
        raw = support[artifact_id]
        entries = manifest.get("artifacts")
        available = (
            [
                value
                for value in entries
                if isinstance(value, Mapping) and value.get("status") == "available"
            ]
            if isinstance(entries, list)
            else []
        )
        if isinstance(raw, Mapping) and raw.get("status") == "unsupported" and available:
            issues.append(
                _issue(
                    "unsupported_artifact_has_content",
                    f"{artifact_id}/manifest.json",
                    "unsupported directory cannot contain available artifacts",
                )
            )


def _validate_manifest_files(
    root: Path,
    directory: str,
    manifest: Mapping[str, object],
    issues: list[ValidationIssue],
) -> set[str]:
    entries = manifest.get("artifacts")
    available: set[str] = set()
    if not isinstance(entries, list):
        return available
    for raw in entries:
        if not isinstance(raw, Mapping):
            continue
        try:
            relative = _normalize_path(str(raw.get("logical_path") or ""))
        except ResultSchemaError:
            continue
        if not relative.startswith(f"{directory}/"):
            continue
        path = _safe_target(root, relative)
        if raw.get("status") == "available":
            available.add(relative)
            if not path.is_file():
                issues.append(_issue("missing_artifact", relative, "manifest artifact is missing"))
                continue
            if raw.get("sha256") != _sha256(path) or raw.get("bytes") != path.stat().st_size:
                issues.append(
                    _issue("manifest_checksum_mismatch", relative, "directory manifest hash or size differs")
                )
        elif path.exists():
            issues.append(
                _issue("unsupported_artifact_materialized", relative, "unsupported manifest entry has a file")
            )
    actual = {
        value.relative_to(root).as_posix()
        for value in (root / directory).rglob("*")
        if value.is_file() and value.name != "manifest.json"
    }
    for relative in sorted(actual - available):
        issues.append(_issue("unregistered_artifact", relative, "directory artifact is not in its manifest"))
    return available


def _validate_checksums(
    root: Path,
    checksums: Mapping[str, object],
    files: Sequence[str],
    run: Mapping[str, object],
    issues: list[ValidationIssue],
) -> None:
    if checksums.get("schema_version") != CHECKSUM_SCHEMA_VERSION:
        issues.append(_issue("invalid_schema", "checksums.json", "checksum schema version is invalid"))
    if checksums.get("hash_algorithm") != "sha256":
        issues.append(_issue("invalid_schema", "checksums.json", "checksum algorithm is invalid"))
    checksum_tree_version = checksums.get("result_tree_schema_version")
    if (
        checksum_tree_version not in RESULT_TREE_SCHEMA_VERSIONS
        or checksum_tree_version != run.get("result_tree_schema_version")
    ):
        issues.append(
            _issue(
                "invalid_schema",
                "checksums.json",
                "checksum result-tree schema version is invalid",
            )
        )
    created_at = checksums.get("created_at_utc")
    if not isinstance(created_at, str) or not created_at.endswith("Z"):
        issues.append(
            _issue(
                "invalid_schema",
                "checksums.json",
                "checksum creation time must be RFC3339 UTC",
            )
        )
    if checksums.get("run_id") != run.get("run_id"):
        issues.append(_issue("identity_mismatch", "checksums.json", "checksum run ID differs"))
    identity = run.get("reuse_identity")
    expected_identity_hash = identity.get("identity_sha256") if isinstance(identity, Mapping) else None
    if checksums.get("reuse_identity_sha256") != expected_identity_hash:
        issues.append(
            _issue("identity_mismatch", "checksums.json", "checksum reuse identity differs")
        )
    entries = checksums.get("entries")
    if not isinstance(entries, Mapping):
        issues.append(_issue("invalid_schema", "checksums.json", "checksum entries must be an object"))
        return
    expected_paths = set(files) - {"checksums.json"}
    if set(entries) != expected_paths:
        issues.append(
            _issue(
                "checksum_coverage_mismatch",
                "checksums.json",
                "checksums must cover every and only non-checksum artifact",
            )
        )
    for relative in sorted(expected_paths & set(entries)):
        raw = entries[relative]
        if not isinstance(raw, Mapping):
            issues.append(_issue("invalid_schema", relative, "checksum entry is not an object"))
            continue
        path = root / relative
        byte_count = raw.get("bytes")
        if (
            not is_sha256(raw.get("sha256"))
            or not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            issues.append(
                _issue("invalid_schema", relative, "checksum entry hash or size is invalid")
            )
        if raw.get("sha256") != _sha256(path) or raw.get("bytes") != path.stat().st_size:
            issues.append(_issue("checksum_mismatch", relative, "artifact bytes differ from checksums.json"))
        expected_meta = _artifact_metadata(relative)
        for key in ("media_type", "privacy_classification"):
            if raw.get(key) != expected_meta[key]:
                issues.append(
                    _issue("checksum_metadata_mismatch", relative, f"checksum {key} differs")
                )


def _validate_jsonl(
    path: Path,
    logical: str,
    issues: list[ValidationIssue],
    *,
    compressed: bool = False,
) -> None:
    if not path.is_file():
        return
    line_number = 0
    try:
        opener = gzip.open if compressed else Path.open
        if compressed:
            stream_context = opener(path, "rt", encoding="utf-8")
        else:
            stream_context = path.open("r", encoding="utf-8")
        with stream_context as stream:
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, Mapping):
                    raise ResultSchemaError("JSONL row is not an object")
                _assert_no_biometric_vectors(value)
    except (
        OSError,
        EOFError,
        UnicodeError,
        json.JSONDecodeError,
        ResultSchemaError,
    ) as exc:
        issues.append(_issue("invalid_jsonl", logical, f"line {line_number}: {exc}"))


def _validate_jsonl_or_raise(path: Path, *, compressed: bool) -> None:
    issues: list[ValidationIssue] = []
    _validate_jsonl(path, path.name, issues, compressed=compressed)
    if issues:
        raise ResultTreeValidationError(issues)


def _validate_rttm_path(path: Path, issues: list[ValidationIssue]) -> None:
    if not path.is_file():
        return
    try:
        _validate_rttm(path.read_text(encoding="utf-8"), allow_empty=True)
    except (OSError, UnicodeError, ResultSchemaError) as exc:
        issues.append(_issue("invalid_rttm", "predictions/diarization.rttm", str(exc)))


def _validate_rttm(value: str, *, allow_empty: bool) -> None:
    observed = 0
    for line_number, line in enumerate(value.splitlines(), start=1):
        if not line.strip():
            continue
        observed += 1
        parts = line.split()
        if len(parts) != 10 or parts[0] != "SPEAKER":
            raise ResultSchemaError(f"RTTM line {line_number} must have 10 SPEAKER fields")
        try:
            start = float(parts[3])
            duration = float(parts[4])
        except ValueError as exc:
            raise ResultSchemaError(f"RTTM line {line_number} has nonnumeric timing") from exc
        if start < 0 or duration <= 0:
            raise ResultSchemaError(f"RTTM line {line_number} has invalid timing")
        if parts[7] in {"", "<NA>"}:
            raise ResultSchemaError(f"RTTM line {line_number} has no speaker label")
    if not allow_empty and observed == 0:
        raise ResultSchemaError("RTTM is empty")


def _validate_run_update(prior: Mapping[str, object], current: Mapping[str, object]) -> None:
    for field in ("run_id", "attempt_id", "reuse_identity", "created_at_utc"):
        if prior.get(field) != current.get(field):
            raise ResultReuseError(f"run.json update changed immutable field {field}")
    transitions = {
        "prepared": {"prepared", "running", "complete", "failed", "stopped"},
        "running": {"running", "complete", "failed", "stopped"},
        "complete": {"complete"},
        "failed": {"failed"},
        "stopped": {"stopped"},
    }
    if current.get("status") not in transitions.get(str(prior.get("status")), set()):
        raise ResultReuseError("run.json attempted a backward or conflicting state transition")
    if prior.get("status") in TERMINAL_RUN_STATES and prior != current:
        raise ResultReuseError("terminal run.json is immutable")


def _safe_json(
    path: Path, logical: str, issues: list[ValidationIssue]
) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        return _read_json(path)
    except (OSError, UnicodeError, json.JSONDecodeError, ResultSchemaError) as exc:
        issues.append(_issue("invalid_json", logical, str(exc)))
        return {}


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ResultSchemaError(f"JSON document is not an object: {path}")
    _assert_no_biometric_vectors(value)
    return value


def _capture_validation(
    operation, logical: str, issues: list[ValidationIssue]
) -> None:
    try:
        operation()
    except (KeyError, TypeError, ValueError, ResultSchemaError) as exc:
        issues.append(_issue("invalid_schema", logical, str(exc)))


def _materialized_relative_files(root: Path) -> list[str]:
    return sorted(
        value.relative_to(root).as_posix()
        for value in root.rglob("*")
        if value.is_file()
    )


def _checksum_entry(path: Path, relative: str) -> dict[str, object]:
    return {
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
        **_artifact_metadata(relative),
    }


def _artifact_metadata(relative: str) -> dict[str, str]:
    suffix = Path(relative).suffix.casefold()
    media_type = {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".rttm": "text/x-rttm",
        ".txt": "text/plain",
        ".csv": "text/csv",
        ".wav": "audio/wav",
    }.get(suffix, "application/octet-stream")
    if relative.endswith(".jsonl.gz"):
        media_type = "application/gzip"
    if relative in {"events.jsonl", "events.jsonl.gz"} or relative.startswith(
        "diagnostics/"
    ):
        privacy = (
            "biometric_sensitive"
            if relative in {"events.jsonl", "events.jsonl.gz"}
            else "private"
        )
    elif relative.startswith("predictions/") or relative.startswith("references/"):
        privacy = "private"
    else:
        privacy = "internal"
    return {"media_type": media_type, "privacy_classification": privacy}


def _normalize_path(value: str) -> str:
    normalized = str(value).replace("\\", "/").strip("/")
    parts = normalized.split("/")
    if (
        not normalized
        or ":" in normalized
        or any(part in {"", ".", ".."} for part in parts)
    ):
        raise ResultSchemaError(f"artifact path is not portable: {value!r}")
    return normalized


def _safe_target(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ResultSchemaError(f"artifact escapes result root: {relative}") from exc
    return target


def _assert_no_biometric_vectors(value: object, path: str = "$") -> None:
    forbidden = {
        "biometric_vector",
        "biometric_vectors",
        "centroid",
        "centroids",
        "embedding",
        "embeddings",
        "embedding_vector",
        "enrollment_embedding",
        "enrollment_embeddings",
        "enrollment_template",
        "enrollment_templates",
        "speaker_embedding",
        "speaker_embeddings",
        "template_vector",
        "template_vectors",
        "speaker_vector",
        "vector",
        "vectors",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key).casefold() in forbidden:
                raise ResultSchemaError(f"biometric vector field is forbidden: {path}.{key}")
            _assert_no_biometric_vectors(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _assert_no_biometric_vectors(child, f"{path}[{index}]")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _issue(code: str, logical_path: str, message: str) -> ValidationIssue:
    return ValidationIssue(code=code, logical_path=logical_path, message=message)


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
