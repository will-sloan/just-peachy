"""Bounded real-model functional smoke for the common demonstration layer."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from app.full_pipeline.factory import EVALUATION_ROOT, MATRIX_PATH, RUNTIME_CONFIG_PATH
from app.full_pipeline.matrix import FullPipelineMatrix
from app.full_pipeline.provenance import runtime_identities

from .enrollment import LabelledWav, LocalEnrollmentService
from .session import DemoSessionManager


SMOKE_PIPELINES = (
    ("AG-H5", "fullpipe_v1_ag_dr_ie"),
    ("AG-H2", "fullpipe_v1_ag_dr_ir"),
    ("AO-H4", "fullpipe_v1_ao_dw_ir"),
)


def run_common_demo_smoke(
    *,
    input_path: Path,
    output_root: Path | None = None,
    telemetry_enabled: bool = True,
) -> dict[str, object]:
    """Exercise enrollment, file mode, exports, and session model switching.

    This deliberately bounded smoke reuses one checked local WAV for each of
    three prompted-take slots.  It qualifies application mechanics only; it is
    not a diversity enrollment, scientific evaluation, or campaign.
    """

    source = Path(input_path).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    root = (
        Path(output_root).resolve()
        if output_root is not None
        else source.parents[2]
        / "JustPeachyResults/full_pipeline/demo_smoke"
        / f"prompt2_{stamp}"
    )
    if root.exists():
        raise FileExistsError(f"refusing to overwrite smoke root: {root}")
    root.mkdir(parents=True)
    matrix = FullPipelineMatrix(MATRIX_PATH, RUNTIME_CONFIG_PATH)
    enrollment_root = root / "enrollment"
    enrollment = LocalEnrollmentService(
        matrix=matrix,
        enrollment_root=enrollment_root,
    )
    labelled = tuple(
        LabelledWav(f"smoke_prompt_{index}", source, f"Bounded smoke take {index}")
        for index in range(1, 4)
    )
    shared_speaker_id = f"common_demo_smoke_speaker_{stamp.casefold()}"
    enrollment_rows = []
    expected_profiles: dict[str, dict[str, str]] = {}
    for pipeline_id in ("fullpipe_v1_ag_dr_ie", "fullpipe_v1_ag_dr_ir"):
        attempt = enrollment.import_wavs(
            pipeline_id=pipeline_id,
            display_label="Local Smoke Speaker",
            labelled_wavs=labelled,
            speaker_id=shared_speaker_id,
        )
        if attempt.state != "profile_created" or attempt.profile is None:
            raise RuntimeError(
                f"bounded enrollment did not create a profile: {attempt.to_dict()}"
            )
        if attempt.speaker_id != shared_speaker_id:
            raise RuntimeError("bounded enrollment did not preserve the shared speaker ID")
        expected_profiles[attempt.backend.backend_id] = {
            "profile_id": attempt.profile.profile_id,
            "profile_sha256": attempt.profile.profile_sha256,
        }
        enrollment_rows.append(attempt.to_dict())
    if {str(row["speaker_id"]) for row in enrollment_rows} != {shared_speaker_id}:
        raise RuntimeError("IE and IR smoke enrollments do not share one speaker ID")

    manager = DemoSessionManager(
        results_root=root / "sessions",
        enrollment_root=enrollment_root,
    )
    session_rows: list[dict[str, object]] = []
    previous_pipeline: str | None = None
    previous_session_id: str | None = None
    previous_output_root: str | None = None
    previous_component_ids: dict[str, str] | None = None
    previous_state: str | None = None
    previous_joined = False
    try:
        for index, (label, pipeline_id) in enumerate(SMOKE_PIPELINES):
            selection = matrix.resolve(pipeline_id)
            expected_pipeline_identity = _expected_pipeline_identity(selection)
            expected_components = [
                identity.to_contract()
                for _, identity in sorted(
                    runtime_identities(
                        selection,
                        evaluation_root=EVALUATION_ROOT,
                    ).items()
                )
            ]
            start_values = {
                "pipeline_id": pipeline_id,
                "input_path": source,
                "pace": 0.0,
                "play_audio": False,
                "duration_sec": None,
                "telemetry_enabled": telemetry_enabled,
                "session_id": f"prompt2_{label.lower().replace('-', '_')}_{stamp}",
                "output_root": None,
            }
            started = (
                manager.start_file(**start_values)
                if index == 0
                else manager.switch_file(**start_values)
            )
            _require_equal(
                started.get("pipeline_identity"),
                expected_pipeline_identity,
                f"{label} manager pipeline identity",
            )
            transition = _validate_immutable_transition(
                started=started,
                previous_pipeline=previous_pipeline,
                previous_session_id=previous_session_id,
                previous_output_root=previous_output_root,
                previous_component_ids=previous_component_ids,
                current_component_ids=_component_backend_ids(expected_components),
                previous_state=previous_state,
                previous_joined=previous_joined,
            )
            session_id = str(started["session_id"])
            finished = manager.join(session_id)
            if str(finished["state"]) != "completed":
                raise RuntimeError(f"{label} demo failed: {finished}")
            result = finished.get("result")
            result_value = result if isinstance(result, Mapping) else {}
            _require_equal(
                finished.get("pipeline_identity"),
                expected_pipeline_identity,
                f"{label} completed manager pipeline identity",
            )
            _require_equal(
                result_value.get("pipeline_id"),
                pipeline_id,
                f"{label} result pipeline ID",
            )
            _require_equal(
                result_value.get("pipeline_config_sha256"),
                selection.pipeline_config_sha256,
                f"{label} result pipeline configuration",
            )
            _require_equal(
                result_value.get("component_identities"),
                expected_components,
                f"{label} exact component identities",
            )
            session_root = Path(str(finished["output_root"]))
            session_state = _read_json(session_root / "session_state.json")
            expected_profile = expected_profiles[
                str(selection.identity["backend_id"])
            ]
            _require_equal(
                session_state.get("enrollment_profiles"),
                [expected_profile],
                f"{label} exact enrollment profile",
            )
            events = _read_jsonl(session_root / "events/events.jsonl")
            event_count = len(events)
            result_counts = result_value.get("counts")
            result_count_values = (
                result_counts if isinstance(result_counts, Mapping) else {}
            )
            _require_equal(
                event_count,
                result_count_values.get("events"),
                f"{label} durable event count",
            )
            if event_count <= 0:
                raise RuntimeError(f"{label} durable event log is empty")
            export_root = root / "exports" / label.lower().replace("-", "_")
            exported = manager.export(export_root, session_id=session_id)
            manifest_path = export_root / "manifest.json"
            manifest_sha256 = _sha256(manifest_path)
            _require_equal(
                exported.get("manifest_sha256"),
                manifest_sha256,
                f"{label} exported manifest SHA-256",
            )
            labelled_path = export_root / "transcript/labelled_transcript.jsonl"
            useful_labelled = _useful_labelled_attribution(labelled_path)
            _validate_export_identities(
                export_root=export_root,
                pipeline_id=pipeline_id,
                expected_pipeline_identity=expected_pipeline_identity,
                expected_components=expected_components,
                expected_profile=expected_profile,
            )
            component_ids = _component_backend_ids(expected_components)
            session_rows.append(
                {
                    "label": label,
                    "pipeline_id": pipeline_id,
                    "pipeline_config_sha256": selection.pipeline_config_sha256,
                    "component_backend_ids": component_ids,
                    "enrollment_profile_ids": [expected_profile["profile_id"]],
                    "previous_pipeline_id": previous_pipeline,
                    "previous_session_id": previous_session_id,
                    "model_switch_between_sessions": bool(
                        previous_pipeline is not None
                        and previous_pipeline != pipeline_id
                    ),
                    "immutable_transition": transition,
                    "session_id": session_id,
                    "state": finished["state"],
                    "completion_state": result_value.get("completion_state"),
                    "output_root": finished["output_root"],
                    "event_count": event_count,
                    "export_root": str(export_root),
                    "export_manifest_sha256": manifest_sha256,
                    "labelled_transcript_sha256": _sha256(labelled_path),
                    "useful_labelled_attribution": useful_labelled,
                }
            )
            previous_pipeline = pipeline_id
            previous_session_id = session_id
            previous_output_root = str(finished["output_root"])
            previous_component_ids = component_ids
            previous_state = str(finished["state"])
            previous_joined = finished.get("joined") is True
    finally:
        manager.shutdown(timeout_per_session=30)

    result = {
        "schema_version": "full-pipeline-common-demo-smoke.v1",
        "status": "PASS",
        "purpose": "bounded_application_mechanics_only",
        "scientific_campaign_started": False,
        "physical_microphone_capture_performed": False,
        "input_audio": str(source),
        "input_audio_sha256": _sha256(source),
        "output_root": str(root),
        "shared_speaker_id": shared_speaker_id,
        "enrollment": enrollment_rows,
        "sessions": session_rows,
        "required_presets_exercised": [row[0] for row in SMOKE_PIPELINES],
        "file_mode_exercised": True,
        "enrollment_exercised": True,
        "labelled_transcript_export_exercised": True,
        "model_switching_between_sessions_exercised": True,
        "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    path = root / "common_demo_smoke.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["summary_path"] = str(path)
    result["summary_sha256"] = _sha256(path)
    return result


def _expected_pipeline_identity(selection: Any) -> dict[str, object]:
    return {
        "pipeline_id": selection.pipeline_id,
        "pipeline_config_sha256": selection.pipeline_config_sha256,
        "protocol_version": selection.protocol_version,
        "asr_backend_id": selection.asr.get("component_id"),
        "diarization_backend_id": selection.diarization.get("pipeline_id"),
        "identity_backend_id": selection.identity.get("backend_id"),
        "hybrid_label": selection.hybrid_label,
        "frozen_hybrid_anchor": selection.frozen_hybrid_anchor,
    }


def _component_backend_ids(
    component_identities: list[dict[str, object]],
) -> dict[str, str]:
    return {
        str(row["component_family"]): str(row["backend_id"])
        for row in component_identities
    }


def _validate_immutable_transition(
    *,
    started: Mapping[str, object],
    previous_pipeline: str | None,
    previous_session_id: str | None,
    previous_output_root: str | None,
    previous_component_ids: Mapping[str, str] | None,
    current_component_ids: Mapping[str, str],
    previous_state: str | None,
    previous_joined: bool,
) -> dict[str, object] | None:
    if previous_pipeline is None:
        if started.get("predecessor_session_id") is not None:
            raise RuntimeError("first smoke session unexpectedly records a predecessor")
        return None
    if previous_session_id is None or previous_output_root is None:
        raise RuntimeError("model switch lacks prior immutable-session evidence")
    if previous_state != "completed" or not previous_joined:
        raise RuntimeError("model switch predecessor was not completed and joined")
    _require_equal(
        started.get("predecessor_session_id"),
        previous_session_id,
        "model-switch predecessor session",
    )
    if str(started.get("pipeline_id")) == previous_pipeline:
        raise RuntimeError("model-switch smoke did not change pipeline ID")
    if str(started.get("session_id")) == previous_session_id:
        raise RuntimeError("model-switch smoke reused the prior session ID")
    if str(started.get("output_root")) == previous_output_root:
        raise RuntimeError("model-switch smoke reused the prior output root")
    changed_components = sorted(
        family
        for family, backend_id in current_component_ids.items()
        if previous_component_ids is None
        or previous_component_ids.get(family) != backend_id
    )
    if not changed_components:
        raise RuntimeError("model-switch smoke did not change any component identity")
    return {
        "transition_kind": "new_immutable_session_after_join",
        "predecessor_session_id": previous_session_id,
        "predecessor_pipeline_id": previous_pipeline,
        "predecessor_state": previous_state,
        "predecessor_joined": previous_joined,
        "current_session_id": str(started.get("session_id")),
        "current_pipeline_id": str(started.get("pipeline_id")),
        "changed_component_families": changed_components,
        "distinct_session_id": True,
        "distinct_output_root": True,
    }


def _validate_export_identities(
    *,
    export_root: Path,
    pipeline_id: str,
    expected_pipeline_identity: Mapping[str, object],
    expected_components: list[dict[str, object]],
    expected_profile: Mapping[str, str],
) -> None:
    pipeline = _read_json(export_root / "manifests/pipeline_identity.json")
    components = _read_json(export_root / "manifests/component_identities.json")
    profiles = _read_json(export_root / "manifests/enrollment_profiles.json")
    _require_equal(pipeline.get("pipeline_id"), pipeline_id, "exported pipeline ID")
    _require_equal(
        pipeline.get("manager_pipeline_identity"),
        expected_pipeline_identity,
        "exported manager pipeline identity",
    )
    _require_equal(
        components.get("component_identities"),
        expected_components,
        "exported component identities",
    )
    _require_equal(
        profiles.get("enrollment_profiles"),
        [dict(expected_profile)],
        "exported enrollment profile identities",
    )
    _require_equal(
        profiles.get("biometric_vectors_inline"),
        False,
        "exported enrollment vector marker",
    )


def _useful_labelled_attribution(path: Path) -> dict[str, object]:
    for row in _read_jsonl(path):
        start = row.get("start_sec")
        end = row.get("end_sec")
        anonymous = row.get("anonymous_speaker_id")
        label = str(row.get("speaker_label") or "").strip()
        alignment = str(row.get("alignment_status") or "").strip()
        numeric_times = (
            isinstance(start, (int, float))
            and not isinstance(start, bool)
            and isinstance(end, (int, float))
            and not isinstance(end, bool)
            and float(end) > float(start)
        )
        if (
            numeric_times
            and isinstance(anonymous, str)
            and bool(anonymous.strip())
            and label.casefold() != "unassigned"
            and alignment
            and "insufficient" not in alignment.casefold()
        ):
            return {
                "span_index": row.get("span_index"),
                "start_sec": start,
                "end_sec": end,
                "anonymous_speaker_id": anonymous,
                "speaker_label": label,
                "alignment_status": alignment,
            }
    raise RuntimeError(
        "labelled transcript lacks a timed, attributed, sufficiently aligned span"
    )


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with Path(path).open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RuntimeError(f"expected JSON object at {path}:{line_number}")
            rows.append(value)
    return rows


def _require_equal(observed: object, expected: object, description: str) -> None:
    if observed != expected:
        raise RuntimeError(
            f"{description} mismatch: expected {expected!r}, observed {observed!r}"
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
