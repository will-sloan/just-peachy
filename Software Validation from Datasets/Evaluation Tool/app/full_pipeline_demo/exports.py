"""Local, checksum-bound exports for completed common-demo sessions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid


class ExportSafetyError(RuntimeError):
    """A requested export would violate integrity or biometric-safety rules."""


def export_session(
    run_root: Path,
    export_root: Path,
    *,
    manager_status: Mapping[str, object] | None = None,
    input_audio_path: Path | None = None,
    authorize_input_audio: bool = False,
) -> dict[str, object]:
    """Create one portable local export after a runtime session has joined.

    The export performs no upload and never copies protected enrollment stores,
    runtime caches, model work directories, or embedding vectors.  Input audio
    is copied only when ``authorize_input_audio`` is explicitly true.
    """

    source = Path(run_root).resolve()
    destination = Path(export_root).resolve()
    source_available = source.is_dir()
    manager_failed = str((manager_status or {}).get("state") or "").casefold() == "failed"
    if not source_available and not manager_failed:
        raise FileNotFoundError(source)
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite export root: {destination}")
    if destination == source or source in destination.parents:
        raise ExportSafetyError("export_root must be outside the source run root")
    if input_audio_path is not None and not authorize_input_audio:
        raise PermissionError("input audio export requires explicit user authorization")

    result = _read_optional_json(source / "result.json") or {}
    session_state = _read_optional_json(source / "session_state.json") or {}
    provenance = _read_optional_json(source / "manifests/provenance.json") or {}
    source_scientific_configuration = _read_optional_json(
        source / "manifests/demo_runtime_configuration.json"
    )
    manager_scientific_configuration = (manager_status or {}).get(
        "scientific_runtime_configuration"
    )
    if manager_scientific_configuration is not None and not isinstance(
        manager_scientific_configuration, Mapping
    ):
        raise ExportSafetyError(
            "manager scientific_runtime_configuration is not an object"
        )
    if (
        source_scientific_configuration is not None
        and manager_scientific_configuration is not None
        and source_scientific_configuration
        != dict(manager_scientific_configuration)
    ):
        raise ExportSafetyError(
            "manager and durable scientific runtime configurations differ"
        )
    scientific_configuration = dict(
        manager_scientific_configuration
        or source_scientific_configuration
        or {
            "schema_version": (
                "full-pipeline-demo-scientific-config-status.v1"
            ),
            "status": "UNAVAILABLE_LEGACY_SESSION_NOT_SCIENTIFIC",
            "source_path": None,
            "source_file_sha256": None,
            "runtime_tuning_identity_sha256": None,
            "final_scientific_validation": False,
            "engineering_baseline": True,
        }
    )
    _assert_no_biometric_vectors(scientific_configuration)
    transcript = _load_referenced_json(
        source,
        result.get("final_transcript_artifact"),
        fallback=source / "transcript/final_transcript.json",
    )
    events_path = _referenced_path(
        source,
        result.get("event_log_artifact"),
        fallback=source / "events/events.jsonl",
    )
    telemetry_path = _referenced_path(
        source,
        result.get("resource_telemetry_artifact"),
        fallback=source / "telemetry/resource_samples.jsonl",
    )
    identity_evidence_path = _referenced_path(
        source,
        result.get("identity_evidence_artifact"),
        fallback=source / "speakers/identity_evidence.jsonl",
    )
    if events_path is not None:
        _assert_no_biometric_vectors_jsonl(events_path)
    if identity_evidence_path is not None:
        _assert_no_biometric_vectors_jsonl(identity_evidence_path)

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    staging.mkdir(parents=False, exist_ok=False)
    artifact_rows: list[dict[str, object]] = []
    try:
        labelled = _labelled_spans(transcript)
        artifact_rows.append(
            _write_jsonl(staging, "transcript/labelled_transcript.jsonl", labelled)
        )
        artifact_rows.append(
            _write_text(staging, "transcript/labelled_transcript.txt", _as_text(labelled))
        )
        artifact_rows.append(
            _write_text(
                staging,
                "transcript/labelled_transcript.md",
                _as_markdown(labelled, result),
            )
        )

        if events_path is not None:
            artifact_rows.append(
                _copy_file(
                    staging,
                    "events/events.jsonl",
                    events_path,
                    "biometric_sensitive",
                )
            )
        else:
            artifact_rows.append(
                _write_text(
                    staging,
                    "events/events.jsonl",
                    "",
                    privacy="biometric_sensitive",
                )
            )
        if identity_evidence_path is not None:
            artifact_rows.append(
                _copy_file(
                    staging,
                    "evidence/identity_evidence.jsonl",
                    identity_evidence_path,
                    "biometric_sensitive",
                )
            )
        else:
            artifact_rows.append(
                _write_text(
                    staging,
                    "evidence/identity_evidence.jsonl",
                    "",
                    privacy="biometric_sensitive",
                )
            )
        if telemetry_path is not None:
            artifact_rows.append(
                _copy_file(
                    staging,
                    "telemetry/resource_samples.jsonl",
                    telemetry_path,
                    "internal",
                )
            )
        else:
            artifact_rows.append(
                _write_text(staging, "telemetry/resource_samples.jsonl", "")
            )

        session_id = (
            result.get("session_id")
            or session_state.get("session_id")
            or (manager_status or {}).get("session_id")
        )
        pipeline_id = (
            result.get("pipeline_id")
            or session_state.get("pipeline_id")
            or (manager_status or {}).get("pipeline_id")
        )
        protocol_version = (
            result.get("protocol_version")
            or session_state.get("protocol_version")
            or dict((manager_status or {}).get("pipeline_identity") or {}).get(
                "protocol_version"
            )
        )
        pipeline_config_sha256 = (
            result.get("pipeline_config_sha256")
            or session_state.get("pipeline_config_sha256")
            or dict((manager_status or {}).get("pipeline_identity") or {}).get(
                "pipeline_config_sha256"
            )
        )
        component_identities = list(result.get("component_identities") or [])
        worker_reported_identities = list(
            provenance.get("worker_reported_identities") or []
        )
        enrollment_profiles = list(session_state.get("enrollment_profiles") or [])
        manager_pipeline_identity = dict(
            (manager_status or {}).get("pipeline_identity") or {}
        )
        pipeline_identity_manifest = {
            "schema_version": "full-pipeline-demo-pipeline-identity.v1",
            "session_id": session_id,
            "pipeline_id": pipeline_id,
            "protocol_version": protocol_version,
            "pipeline_config_sha256": pipeline_config_sha256,
            "manager_pipeline_identity": manager_pipeline_identity,
            "scientific_runtime_configuration": scientific_configuration,
        }
        component_identity_manifest = {
            "schema_version": "full-pipeline-demo-component-identities.v1",
            "session_id": session_id,
            "pipeline_id": pipeline_id,
            "component_identities": component_identities,
            "worker_reported_identities": worker_reported_identities,
        }
        enrollment_profile_manifest = {
            "schema_version": "full-pipeline-demo-enrollment-profiles.v1",
            "session_id": session_id,
            "pipeline_id": pipeline_id,
            "enrollment_profiles": enrollment_profiles,
            "biometric_vectors_inline": False,
        }
        identities = {
            "schema_version": "full-pipeline-demo-identities.v1",
            "session_id": session_id,
            "pipeline_id": pipeline_id,
            "protocol_version": protocol_version,
            "pipeline_config_sha256": pipeline_config_sha256,
            "component_identities": component_identities,
            "worker_reported_identities": worker_reported_identities,
            "enrollment_profiles": enrollment_profiles,
            "manager_pipeline_identity": manager_pipeline_identity,
            "scientific_runtime_configuration": scientific_configuration,
        }
        for value in (
            pipeline_identity_manifest,
            component_identity_manifest,
            enrollment_profile_manifest,
            identities,
        ):
            _assert_no_biometric_vectors(value)
        artifact_rows.extend(
            (
                _write_json(
                    staging,
                    "manifests/pipeline_identity.json",
                    pipeline_identity_manifest,
                ),
                _write_json(
                    staging,
                    "manifests/component_identities.json",
                    component_identity_manifest,
                ),
                _write_json(
                    staging,
                    "manifests/enrollment_profiles.json",
                    enrollment_profile_manifest,
                    privacy="biometric_sensitive",
                ),
                _write_json(
                    staging,
                    "manifests/scientific_runtime_configuration.json",
                    scientific_configuration,
                ),
            )
        )
        artifact_rows.append(
            _write_json(
                staging,
                "identities/pipeline_models_profiles.json",
                identities,
                privacy="biometric_sensitive",
            )
        )

        failures = {
            "schema_version": "full-pipeline-demo-failure-log.v1",
            "completion_state": result.get("completion_state")
            or (manager_status or {}).get("state"),
            "runtime_warnings": list(result.get("warnings") or []),
            "runtime_errors": list(result.get("errors") or []),
            "manager_warnings": list((manager_status or {}).get("warnings") or []),
            "manager_failures": list((manager_status or {}).get("failures") or []),
        }
        artifact_rows.append(
            _write_json(
                staging,
                "diagnostics/failures.json",
                failures,
                privacy="private",
            )
        )
        artifact_rows.append(
            _write_json(
                staging,
                "logs/failure.json",
                failures,
                privacy="private",
            )
        )

        for logical, path, privacy in (
            ("source/result.json", source / "result.json", "private"),
            (
                "source/session_state.json",
                source / "session_state.json",
                "biometric_sensitive",
            ),
            (
                "source/provenance.json",
                source / "manifests/provenance.json",
                "private",
            ),
        ):
            if path.is_file():
                _assert_no_biometric_vectors(_read_json(path))
                artifact_rows.append(_copy_file(staging, logical, path, privacy))

        audio_included = False
        if input_audio_path is not None:
            audio = Path(input_audio_path).resolve()
            if not audio.is_file():
                raise FileNotFoundError(audio)
            suffix = audio.suffix.casefold()
            if suffix not in {".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus"}:
                raise ExportSafetyError(f"unsupported input audio extension: {suffix}")
            artifact_rows.append(
                _copy_file(staging, f"audio/input{suffix}", audio, "private")
            )
            audio_included = True

        manifest = {
            "schema_version": "full-pipeline-demo-export-manifest.v1",
            "created_at_utc": _utc_now(),
            "session_id": result.get("session_id")
            or session_state.get("session_id")
            or (manager_status or {}).get("session_id"),
            "pipeline_id": result.get("pipeline_id")
            or session_state.get("pipeline_id")
            or (manager_status or {}).get("pipeline_id"),
            "source_result_sha256": result.get("result_sha256"),
            "source_completion_state": result.get("completion_state")
            or (manager_status or {}).get("state"),
            "scientific_config_status": scientific_configuration.get("status"),
            "scientific_config_source_path": scientific_configuration.get(
                "source_path"
            ),
            "scientific_config_source_sha256": scientific_configuration.get(
                "source_file_sha256"
            ),
            "runtime_tuning_identity_sha256": scientific_configuration.get(
                "runtime_tuning_identity_sha256"
            ),
            "final_scientific_validation": scientific_configuration.get(
                "final_scientific_validation"
            ),
            "local_export_only": True,
            "contains_biometric_vectors": False,
            "protected_enrollment_store_copied": False,
            "runtime_work_or_cache_copied": False,
            "input_audio_included_with_user_authorization": audio_included,
            "artifacts": artifact_rows,
        }
        manifest_row = _write_json(staging, "manifest.json", manifest)
        checksum_rows = [*artifact_rows, manifest_row]
        checksums = {
            "schema_version": "full-pipeline-demo-export-checksums.v1",
            "artifacts": [
                {
                    "logical_path": value["logical_path"],
                    "sha256": value["sha256"],
                    "byte_count": value["byte_count"],
                }
                for value in checksum_rows
            ],
        }
        checksum_row = _write_json(staging, "checksums.json", checksums)
        staging.replace(destination)
        return {
            "schema_version": "full-pipeline-demo-export-result.v1",
            "status": "COMPLETE",
            "session_id": manifest["session_id"],
            "pipeline_id": manifest["pipeline_id"],
            "output_root": str(destination),
            "manifest_sha256": manifest_row["sha256"],
            "checksums_sha256": checksum_row["sha256"],
            "artifact_count": len(checksum_rows),
            "input_audio_included": audio_included,
            "scientific_config_status": scientific_configuration.get("status"),
            "runtime_tuning_identity_sha256": scientific_configuration.get(
                "runtime_tuning_identity_sha256"
            ),
        }
    except BaseException:
        if staging.is_dir():
            shutil.rmtree(staging)
        raise


def _labelled_spans(transcript: Mapping[str, object]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    spans = transcript.get("spans") or []
    if not isinstance(spans, Sequence) or isinstance(spans, (str, bytes)):
        return rows
    for index, raw in enumerate(spans, start=1):
        if not isinstance(raw, Mapping):
            continue
        speaker = raw.get("speaker_label")
        if isinstance(speaker, Mapping):
            label = speaker.get("display_label") or speaker.get("label_kind")
            enrolled_id = speaker.get("enrolled_speaker_id")
        else:
            label = speaker
            enrolled_id = None
        rows.append(
            {
                "schema_version": "full-pipeline-demo-labelled-span.v1",
                "span_index": index,
                "span_id": raw.get("span_id"),
                "start_sec": raw.get("start_sec"),
                "end_sec": raw.get("end_sec"),
                "speaker_label": str(label) if label else "Unassigned",
                "enrolled_speaker_id": enrolled_id,
                "anonymous_speaker_id": raw.get("anonymous_speaker_id"),
                "text": str(raw.get("text") or ""),
                "state": raw.get("state"),
                "alignment_status": raw.get("alignment_status"),
                "timing_provenance": raw.get("timing_provenance"),
                "source_event_ids": list(raw.get("source_event_ids") or []),
            }
        )
    return rows


def _as_text(rows: Sequence[Mapping[str, object]]) -> str:
    values = []
    for row in rows:
        start = _format_time(row.get("start_sec"))
        end = _format_time(row.get("end_sec"))
        text = " ".join(str(row.get("text") or "").split())
        values.append(f"[{start} - {end}] {row['speaker_label']}: {text}".rstrip())
    return "\n".join(values) + ("\n" if values else "")


def _as_markdown(
    rows: Sequence[Mapping[str, object]], result: Mapping[str, object]
) -> str:
    values = [
        "# Labelled transcript",
        "",
        f"- Session: `{result.get('session_id') or 'unknown'}`",
        f"- Pipeline: `{result.get('pipeline_id') or 'unknown'}`",
        f"- Completion: `{result.get('completion_state') or 'unknown'}`",
        "",
    ]
    for row in rows:
        start = _format_time(row.get("start_sec"))
        end = _format_time(row.get("end_sec"))
        label = str(row.get("speaker_label") or "Unassigned").replace("`", "'")
        text = " ".join(str(row.get("text") or "").split())
        values.extend((f"## {start}–{end} — {label}", "", text, ""))
    return "\n".join(values).rstrip() + "\n"


def _format_time(value: object) -> str:
    if value is None:
        return "time unavailable"
    try:
        total_ms = max(0, round(float(value) * 1000))
    except (TypeError, ValueError):
        return "time unavailable"
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def _load_referenced_json(
    root: Path, reference: object, *, fallback: Path
) -> dict[str, object]:
    path = _referenced_path(root, reference, fallback=fallback)
    return _read_json(path) if path is not None else {"spans": []}


def _referenced_path(
    root: Path, reference: object, *, fallback: Path
) -> Path | None:
    if isinstance(reference, Mapping) and reference.get("logical_path"):
        relative = str(reference["logical_path"]).replace("\\", "/")
        candidate = (root / relative).resolve()
        if root != candidate and root not in candidate.parents:
            raise ExportSafetyError(f"artifact escapes run root: {relative}")
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
        expected = reference.get("sha256")
        if expected and _sha256(candidate) != str(expected).casefold():
            raise ExportSafetyError(f"artifact checksum mismatch: {relative}")
        return candidate
    return fallback.resolve() if fallback.is_file() else None


def _read_optional_json(path: Path) -> dict[str, object] | None:
    return _read_json(path) if path.is_file() else None


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ExportSafetyError(f"JSON artifact is not an object: {path}")
    return value


def _assert_no_biometric_vectors_jsonl(path: Path) -> None:
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ExportSafetyError(
                    f"invalid event JSONL at line {line_number}: {path}"
                ) from exc
            _assert_no_biometric_vectors(value)


def _assert_no_biometric_vectors(value: object, path: str = "$") -> None:
    vector_keys = {
        "embedding",
        "embedding_vector",
        "embeddings",
        "template_vector",
        "template_vectors",
        "speaker_vector",
    }
    if isinstance(value, Mapping):
        for key, child in value.items():
            name = str(key).casefold()
            if name in vector_keys:
                raise ExportSafetyError(f"biometric vector field is not exportable: {path}.{key}")
            _assert_no_biometric_vectors(child, f"{path}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for index, child in enumerate(value):
            _assert_no_biometric_vectors(child, f"{path}[{index}]")


def _write_json(
    root: Path,
    logical_path: str,
    value: object,
    *,
    privacy: str = "internal",
) -> dict[str, object]:
    payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return _write_bytes(root, logical_path, payload, privacy)


def _write_jsonl(
    root: Path,
    logical_path: str,
    values: Sequence[Mapping[str, object]],
    *,
    privacy: str = "private",
) -> dict[str, object]:
    payload = "".join(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":")) + "\n"
        for value in values
    ).encode("utf-8")
    return _write_bytes(root, logical_path, payload, privacy)


def _write_text(
    root: Path,
    logical_path: str,
    value: str,
    *,
    privacy: str = "private",
) -> dict[str, object]:
    return _write_bytes(root, logical_path, value.encode("utf-8"), privacy)


def _copy_file(
    root: Path, logical_path: str, source: Path, privacy: str
) -> dict[str, object]:
    destination = _safe_destination(root, logical_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    shutil.copyfile(source, temporary)
    temporary.replace(destination)
    return _artifact_row(root, destination, privacy)


def _write_bytes(
    root: Path, logical_path: str, payload: bytes, privacy: str
) -> dict[str, object]:
    destination = _safe_destination(root, logical_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(destination)
    return _artifact_row(root, destination, privacy)


def _safe_destination(root: Path, logical_path: str) -> Path:
    normalized = str(logical_path).replace("\\", "/").strip("/")
    destination = (root / normalized).resolve()
    if not normalized or root not in destination.parents:
        raise ExportSafetyError(f"invalid export logical path: {logical_path}")
    return destination


def _artifact_row(root: Path, path: Path, privacy: str) -> dict[str, object]:
    return {
        "logical_path": path.relative_to(root).as_posix(),
        "sha256": _sha256(path),
        "byte_count": path.stat().st_size,
        "privacy_classification": privacy,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )
