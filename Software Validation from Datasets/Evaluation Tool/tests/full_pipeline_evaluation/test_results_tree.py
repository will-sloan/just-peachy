from __future__ import annotations

from copy import deepcopy
import gzip
import json
from pathlib import Path

import pytest

from app.full_pipeline_evaluation import io as evaluation_io
from app.full_pipeline_evaluation.metrics import (
    build_metric_report,
    computed_metric,
    undefined_metric,
)
from app.full_pipeline_evaluation.results import (
    ResultReuseError,
    ResultTreeBuilder,
    result_tree_reusable,
    validate_result_tree,
)
from app.full_pipeline_evaluation.schema import (
    ARTIFACT_SUPPORT_IDS,
    MODEL_ASSETS_SCHEMA_VERSION,
    PIPELINE_IDENTITY_SCHEMA_VERSION,
    PROGRAM_ID,
    ResultSchemaError,
    build_metric_documents_from_reports,
    build_run_document,
    validate_metric_document,
)


PIPELINE_ID = "fullpipe_v1_ag_h5_ir"
RUN_ID = "prompt3-result-test"
TIMESTAMP = "2026-08-23T12:00:00Z"
SCHEMA_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs/automated_evaluation/schemas/full_pipeline_evaluation_result.v1.schema.json"
)
COMPACT_SCHEMA_PATH = SCHEMA_PATH.with_name(
    "full_pipeline_evaluation_result.v2.schema.json"
)


def _reuse_identity(*, seed: int = 1729) -> dict[str, object]:
    return {
        "program_id": PROGRAM_ID,
        "evaluation_protocol_id": "full_pipeline_eval_v1",
        "evaluation_protocol_sha256": "1" * 64,
        "pipeline_id": PIPELINE_ID,
        "pipeline_config_sha256": "2" * 64,
        "case_manifest_id": "prompt3-smoke-cases-v1",
        "case_manifest_sha256": "3" * 64,
        "runtime_config_sha256": "4" * 64,
        "partition": "smoke",
        "seed": seed,
    }


def _artifact_support(status: str = "supported") -> dict[str, dict[str, object]]:
    reason = None if status == "supported" else "not produced by this attempt"
    return {
        artifact_id: {"status": status, "reason": reason}
        for artifact_id in ARTIFACT_SUPPORT_IDS
    }


def _complete_tree(
    root: Path, *, compact: bool = False
) -> tuple[ResultTreeBuilder, dict[str, object]]:
    identity = _reuse_identity()
    builder = ResultTreeBuilder(root, identity, compact=compact)
    builder.publish_run(
        build_run_document(
            run_id=RUN_ID,
            attempt_id="attempt-001",
            reuse_identity=identity,
            status="complete",
            created_at_utc=TIMESTAMP,
            started_at_utc=TIMESTAMP,
            ended_at_utc=TIMESTAMP,
            artifact_support=_artifact_support(),
            counts={"cases_selected": 1, "cases_completed": 1},
            result_tree_schema_version=builder.result_tree_schema_version,
        )
    )
    builder.publish_pipeline_identity(
        {
            "schema_version": PIPELINE_IDENTITY_SCHEMA_VERSION,
            "run_id": RUN_ID,
            "pipeline_id": PIPELINE_ID,
            "protocol_version": "full-pipeline-evaluation-protocol.v1",
            "pipeline_config_sha256": "2" * 64,
            "matrix_sha256": "5" * 64,
            "aliases": {"asr": "AG", "diarization": "H5", "identity": "IR"},
            "component_identities": [],
            "policy_identities": [],
            "environment_identities": [],
        }
    )
    builder.publish_model_assets(
        {
            "schema_version": MODEL_ASSETS_SCHEMA_VERSION,
            "run_id": RUN_ID,
            "pipeline_id": PIPELINE_ID,
            "no_implicit_downloads": True,
            "assets": [
                {"role": "asr", "asset_id": "sherpa-giga", "sha256": "6" * 64}
            ],
        }
    )
    builder.publish_events(
        [
            {
                "event_id": "event-1",
                "event_type": "transcript_final",
                "start_sec": 0.0,
                "end_sec": 1.0,
                "anonymous_speaker_id": "anon_1",
            }
        ]
    )
    builder.publish_predictions(
        transcript_rows=[{"start_sec": 0.0, "end_sec": 1.0, "text": "hello"}],
        labelled_rows=[
            {
                "start_sec": 0.0,
                "end_sec": 1.0,
                "text": "hello",
                "anonymous_speaker_id": "anon_1",
                "identity_label": "Unknown_1",
            }
        ],
        diarization_rttm="SPEAKER sample 1 0.000 1.000 <NA> <NA> anon_1 <NA> <NA>\n",
    )
    builder.publish_references(
        {
            "artifacts": [
                {
                    "artifact_id": "transcript",
                    "logical_path": "references/transcript.jsonl",
                    "status": "available",
                },
                {
                    "artifact_id": "word_timing",
                    "logical_path": "references/word_timing.jsonl",
                    "status": "unsupported",
                    "reason": "fixture has no word timing",
                },
            ]
        },
        artifacts={"references/transcript.jsonl": b'{"text":"hello"}\n'},
    )
    asr_report = build_metric_report(
        "asr",
        [
            computed_metric("wer", 0.0, numerator=0, denominator=1),
            undefined_metric(
                "output_failure_rate",
                "attempt denominator is zero in the selected slice",
                numerator=0,
                denominator=0,
            ),
        ],
        missing_reason="fixture does not compute this ASR metric",
    )
    metric_documents = build_metric_documents_from_reports(
        {"asr": asr_report},
        run_id=RUN_ID,
        pipeline_id=PIPELINE_ID,
        missing_reason="fixture does not evaluate this Track-B subview",
    )
    for view, document in metric_documents.items():
        builder.publish_metric(view, document)
    builder.publish_diagnostics(
        {
            "artifacts": [
                {
                    "artifact_id": "failures",
                    "logical_path": "diagnostics/failures.json",
                    "status": "available",
                }
            ]
        },
        artifacts={"diagnostics/failures.json": b"[]\n"},
    )
    return builder, identity


def test_builds_exact_checksum_bound_result_tree(tmp_path: Path) -> None:
    builder, identity = _complete_tree(tmp_path / "result")

    report = builder.finalize()

    assert report.valid
    assert report.reusable
    assert result_tree_reusable(builder.root, identity)
    assert builder.finalize().valid  # finalized retry is an idempotent read
    summary = json.loads((builder.root / "metrics/summary.json").read_text())
    assert set(summary["views"]["asr"]["subviews"]) == {
        "asr",
        "speaker_transcription",
    }
    asr = json.loads((builder.root / "metrics/asr.json").read_text())
    assert asr["subviews"]["asr"]["metrics"]["wer"]["status"] == "computed"
    failure_rate = asr["subviews"]["asr"]["metrics"]["output_failure_rate"]
    assert failure_rate["status"] == "undefined"
    assert failure_rate["value"] is None
    assert asr["subviews"]["speaker_transcription"]["unsupported_metric_count"] > 0
    checksums = json.loads((builder.root / "checksums.json").read_text())
    materialized = {
        path.relative_to(builder.root).as_posix()
        for path in builder.root.rglob("*")
        if path.is_file() and path.name != "checksums.json"
    }
    assert set(checksums["entries"]) == materialized


def test_compact_result_tree_streams_valid_gzip_and_detects_tampering(
    tmp_path: Path,
) -> None:
    builder, identity = _complete_tree(tmp_path / "compact", compact=True)

    report = builder.finalize()

    assert report.reusable
    assert not (builder.root / "events.jsonl").exists()
    event_path = builder.root / "events.jsonl.gz"
    with gzip.open(event_path, "rt", encoding="utf-8") as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    assert [row["event_id"] for row in rows] == ["event-1"]
    with event_path.open("ab") as stream:
        stream.write(b"tamper")
    assert not result_tree_reusable(builder.root, identity)


def test_compact_event_bytes_are_deterministic_and_truncation_is_structured(
    tmp_path: Path,
) -> None:
    first, _ = _complete_tree(tmp_path / "first", compact=True)
    second, second_identity = _complete_tree(tmp_path / "second", compact=True)
    first.finalize()
    second.finalize()

    assert (first.root / "events.jsonl.gz").read_bytes() == (
        second.root / "events.jsonl.gz"
    ).read_bytes()
    event_path = second.root / "events.jsonl.gz"
    payload = event_path.read_bytes()
    event_path.write_bytes(payload[:-6])

    report = validate_result_tree(
        second.root, expected_reuse_identity=second_identity
    )

    assert not report.valid
    assert any(issue.code == "invalid_jsonl" for issue in report.issues)
    assert not result_tree_reusable(second.root, second_identity)


def test_json_schema_preserves_track_b_subviews_and_statuses() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    definitions = schema["$defs"]
    assert set(definitions["metricDocument"]["properties"]["subviews"]["properties"]) == {
        "asr",
        "streaming",
        "diarization",
        "identity",
        "speaker_transcription",
        "ux",
        "resources",
    }
    assert definitions["trackBMetric"]["properties"]["status"]["enum"] == [
        "computed",
        "unsupported",
        "undefined",
    ]
    assert "undefined_metric_count" in definitions["summary"]["required"]
    compact_schema = json.loads(COMPACT_SCHEMA_PATH.read_text(encoding="utf-8"))
    assert compact_schema["$defs"]["run"]["properties"][
        "result_tree_schema_version"
    ]["const"] == "full-pipeline-evaluation-result-tree.v2"


def test_metric_contract_rejects_missing_or_fabricated_values() -> None:
    document = build_metric_documents_from_reports(
        {}, run_id=RUN_ID, pipeline_id=PIPELINE_ID
    )["asr"]
    missing = deepcopy(document)
    del missing["subviews"]["asr"]["metrics"]["wer"]
    with pytest.raises(ResultSchemaError, match="metric coverage differs"):
        validate_metric_document(missing, expected_view="asr")

    fabricated = deepcopy(document)
    fabricated["subviews"]["asr"]["metrics"]["wer"]["value"] = 0.0
    with pytest.raises(ResultSchemaError, match="fabricated a value"):
        validate_metric_document(fabricated, expected_view="asr")


def test_checksum_mutation_and_unregistered_artifact_disable_reuse(
    tmp_path: Path,
) -> None:
    builder, identity = _complete_tree(tmp_path / "result")
    builder.finalize()
    with (builder.root / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write('{"event_id":"tampered"}\n')
    (builder.root / "diagnostics/unregistered.txt").write_text(
        "not in the manifest", encoding="utf-8"
    )

    report = validate_result_tree(builder.root, expected_reuse_identity=identity)

    assert not report.valid
    assert not result_tree_reusable(builder.root, identity)
    assert {issue.code for issue in report.issues} >= {
        "checksum_mismatch",
        "unregistered_artifact",
        "checksum_coverage_mismatch",
    }


def test_partial_resume_requires_exact_reuse_identity(tmp_path: Path) -> None:
    root = tmp_path / "partial"
    identity = _reuse_identity()
    builder = ResultTreeBuilder(root, identity)
    builder.publish_run(
        build_run_document(
            run_id=RUN_ID,
            attempt_id="attempt-001",
            reuse_identity=identity,
            status="running",
            created_at_utc=TIMESTAMP,
            started_at_utc=TIMESTAMP,
            artifact_support=_artifact_support(),
        )
    )

    resumed = ResultTreeBuilder(root, identity, resume=True)
    assert resumed.run_id == RUN_ID
    with pytest.raises(ResultReuseError, match="another reuse identity"):
        ResultTreeBuilder(root, _reuse_identity(seed=1730), resume=True)


def test_stopped_run_publication_retries_transient_windows_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    identity = _reuse_identity()
    builder = ResultTreeBuilder(tmp_path / "stopped-result", identity)
    running = build_run_document(
        run_id=RUN_ID,
        attempt_id="attempt-001",
        reuse_identity=identity,
        status="running",
        created_at_utc=TIMESTAMP,
        started_at_utc=TIMESTAMP,
        artifact_support=_artifact_support(),
    )
    builder.publish_run(running)
    actual_replace = evaluation_io.os.replace
    replace_calls = 0

    def transient_permission_error(source: object, target: object) -> None:
        nonlocal replace_calls
        replace_calls += 1
        if replace_calls < 3:
            raise PermissionError(5, "transient Windows sharing violation")
        actual_replace(source, target)

    monkeypatch.setattr(evaluation_io.os, "replace", transient_permission_error)
    monkeypatch.setattr(evaluation_io.time, "sleep", lambda _seconds: None)
    stopped = build_run_document(
        run_id=RUN_ID,
        attempt_id="attempt-001",
        reuse_identity=identity,
        status="stopped",
        created_at_utc=TIMESTAMP,
        started_at_utc=TIMESTAMP,
        ended_at_utc=TIMESTAMP,
        artifact_support=_artifact_support(),
        counts={"planned_cases": 2, "completed_cases": 1},
    )

    builder.publish_run(stopped)

    published = json.loads((builder.root / "run.json").read_text(encoding="utf-8"))
    assert published["status"] == "stopped"
    assert replace_calls == 3
    assert not tuple(builder.root.glob(".run.json.tmp*"))


def test_atomic_replace_exhaustion_reraises_first_error_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "run.json"
    temporary = tmp_path / ".run.json.tmp.fixture"
    temporary.write_bytes(b"stopped\n")
    errors: list[PermissionError] = []

    def permanent_permission_error(_source: object, _target: object) -> None:
        error = PermissionError(5, f"sharing violation {len(errors) + 1}")
        errors.append(error)
        raise error

    monkeypatch.setattr(evaluation_io.os, "replace", permanent_permission_error)
    monkeypatch.setattr(evaluation_io.time, "sleep", lambda _seconds: None)

    with pytest.raises(PermissionError) as captured:
        evaluation_io.replace_file_atomic(temporary, target)

    assert captured.value is errors[0]
    assert len(errors) == evaluation_io.ATOMIC_REPLACE_ATTEMPTS
    assert not temporary.exists()
    assert not target.exists()


def test_terminal_run_and_biometric_vector_artifacts_are_immutable(
    tmp_path: Path,
) -> None:
    builder, _ = _complete_tree(tmp_path / "result")
    terminal = json.loads((builder.root / "run.json").read_text())
    changed = deepcopy(terminal)
    changed["counts"]["cases_completed"] = 2
    with pytest.raises(ResultReuseError, match="terminal run.json is immutable"):
        builder.publish_run(changed)
    with pytest.raises(ResultSchemaError, match="biometric vector field is forbidden"):
        builder.publish_events([{"speaker_embedding": [0.1, 0.2]}])


def test_invalid_rttm_is_rejected_before_publication(tmp_path: Path) -> None:
    root = tmp_path / "invalid-rttm"
    builder = ResultTreeBuilder(root, _reuse_identity())
    with pytest.raises(ResultSchemaError, match="invalid timing"):
        builder.publish_predictions(
            transcript_rows=[],
            labelled_rows=[],
            diarization_rttm=(
                "SPEAKER sample 1 0.000 0.000 <NA> <NA> anon_1 <NA> <NA>\n"
            ),
        )
