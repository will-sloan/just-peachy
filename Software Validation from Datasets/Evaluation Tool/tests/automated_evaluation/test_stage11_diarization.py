from __future__ import annotations

import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.cli.main import build_parser
from app.diarization_evaluation.analysis import aggregate_native_results
from app.diarization_evaluation.artifacts import file_sha256, write_json_atomic
from app.diarization_evaluation.contracts import (
    DiarizationEvaluationError,
    DiarizationScoringPolicy,
    backend_availability,
    resolve_segmentation_provenance,
)
from app.diarization_evaluation.execution import (
    run_diarization_unit,
    validate_diarization_result,
)
from app.diarization_evaluation.formats import (
    RttmTurn,
    UemRegion,
    parse_rttm,
    parse_uem,
    write_rttm,
    write_uem,
)
from app.diarization_evaluation.manifests import (
    NATIVE_MANIFEST_SCHEMA,
    build_native_diarization_manifest,
    read_native_manifest,
    validate_native_manifest_table,
)
from app.diarization_evaluation.scoring import (
    score_diarization,
    score_speaker_attributed_transcripts,
    validate_timebase,
)
from app.inference_pipeline.diarization.base import SpeakerTurnRegion


TOOL_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native_manifest_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("stage11-native")
    build_native_diarization_manifest(root, tier="small")
    return root


def _policy(collar: float = 0.0) -> DiarizationScoringPolicy:
    return DiarizationScoringPolicy(collar_sec=collar)


def test_rttm_parser_writer_round_trip_and_malformed_output(tmp_path: Path) -> None:
    turns = [
        RttmTurn("meeting", "1", 0.1, 1.2, "speaker_01"),
        RttmTurn("meeting", "1", 1.2, 2.0, "speaker_00"),
    ]
    path = write_rttm(tmp_path / "segments.rttm", reversed(turns))

    assert parse_rttm(path) == sorted(turns)
    with pytest.raises(DiarizationEvaluationError, match="invalid RTTM"):
        parse_rttm("SPEAKER too few fields", from_text=True)
    with pytest.raises(DiarizationEvaluationError, match="duration"):
        parse_rttm(
            "SPEAKER meeting 1 0.0 0.0 <NA> <NA> speaker_00 <NA> <NA>",
            from_text=True,
        )


def test_atomic_metadata_refresh_leaves_no_temporary_file(tmp_path: Path) -> None:
    path = tmp_path / "status.json"
    write_json_atomic(path, {"value": 1})
    write_json_atomic(path, {"value": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"value": 2}
    assert not list(tmp_path.glob("*.tmp.*"))


def test_uem_parser_writer_and_overlap_validation(tmp_path: Path) -> None:
    regions = [UemRegion("meeting", "1", 0.0, 2.0)]
    path = write_uem(tmp_path / "region.uem", regions)

    assert parse_uem(path) == regions
    with pytest.raises(DiarizationEvaluationError, match="overlapping UEM"):
        parse_uem("meeting 1 0 2\nmeeting 1 1 3\n", from_text=True)


def test_permutation_aware_scoring_keeps_anonymous_labels() -> None:
    reference = [
        RttmTurn("meeting", "1", 0.0, 1.0, "ref_alice"),
        RttmTurn("meeting", "1", 1.0, 2.0, "ref_bob"),
    ]
    hypothesis = [
        RttmTurn("meeting", "1", 0.0, 1.0, "speaker_17"),
        RttmTurn("meeting", "1", 1.0, 2.0, "speaker_03"),
    ]
    original_labels = [turn.speaker_label for turn in hypothesis]

    result = score_diarization(
        reference,
        hypothesis,
        [UemRegion("meeting", "1", 0.0, 2.0)],
        policy=_policy(),
    )

    assert result["der"] == pytest.approx(0.0)
    assert result["jer"] == pytest.approx(0.0)
    assert [turn.speaker_label for turn in hypothesis] == original_labels
    assert "ref_alice" not in original_labels


def test_overlap_aware_and_excluded_policies_are_distinct() -> None:
    reference = [
        RttmTurn("meeting", "1", 0.0, 2.0, "ref_a"),
        RttmTurn("meeting", "1", 1.0, 2.0, "ref_b"),
    ]
    hypothesis = [RttmTurn("meeting", "1", 0.0, 2.0, "speaker_00")]
    result = score_diarization(
        reference,
        hypothesis,
        [UemRegion("meeting", "1", 0.0, 2.0)],
        policy=_policy(),
    )

    assert result["modes"]["overlap_aware"]["der"] == pytest.approx(1.0 / 3.0)
    assert result["modes"]["overlap_excluded"]["der"] == pytest.approx(0.0)


def test_collar_and_uem_change_only_the_declared_scored_region() -> None:
    reference = [RttmTurn("meeting", "1", 0.0, 1.0, "ref_a")]
    hypothesis = [RttmTurn("meeting", "1", 0.1, 2.0, "speaker_00")]
    uem = [UemRegion("meeting", "1", 0.0, 1.0)]

    without_collar = score_diarization(reference, hypothesis, uem, policy=_policy())
    with_collar = score_diarization(reference, hypothesis, uem, policy=_policy(0.1))

    assert without_collar["der"] == pytest.approx(0.1)
    assert with_collar["der"] == pytest.approx(0.0)
    assert without_collar["false_alarm_sec"] == pytest.approx(0.0)


def test_invalid_timebase_and_incompatible_reference_suppress_der_jer() -> None:
    reference = [RttmTurn("reference", "1", 0.0, 1.0, "ref_a")]
    hypothesis = [RttmTurn("wrong", "1", 0.0, 1.0, "speaker_00")]
    uem = [UemRegion("reference", "1", 0.0, 1.0)]
    invalid = score_diarization(reference, hypothesis, uem, policy=_policy())
    incompatible = score_diarization(
        [],
        [],
        uem,
        policy=_policy(),
        reference_compatible=False,
        incompatibility_reason="no fine timing",
    )

    assert invalid["metrics_emitted"] is False
    assert "der" not in invalid and "jer" not in invalid
    assert incompatible["metrics_emitted"] is False
    assert "der" not in incompatible and "jer" not in incompatible


def test_channel_mismatch_is_an_invalid_timebase() -> None:
    reference = [RttmTurn("meeting", "1", 0.0, 1.0, "ref_a")]
    hypothesis = [RttmTurn("meeting", "2", 0.0, 1.0, "speaker_00")]
    result = score_diarization(
        reference,
        hypothesis,
        [UemRegion("meeting", "1", 0.0, 1.0)],
        policy=_policy(),
    )

    assert result["metrics_emitted"] is False
    assert "recording/channel pairs" in result["suppression_reasons"][0]


def test_anonymous_and_known_speaker_semantics_remain_distinct() -> None:
    reference = [RttmTurn("meeting", "1", 0.0, 1.0, "Alice")]
    identity_hypothesis = [RttmTurn("meeting", "1", 0.0, 1.0, "Alice")]
    uem = [UemRegion("meeting", "1", 0.0, 1.0)]

    anonymous = validate_timebase(reference, identity_hypothesis, uem)
    known = validate_timebase(
        reference,
        identity_hypothesis,
        uem,
        label_semantics="known_speaker",
    )

    assert anonymous.valid is False
    assert known.valid is True


def test_segmentation_provenance_reports_effective_not_merely_configured_source() -> None:
    replaced = resolve_segmentation_provenance(
        vad_enabled=True,
        vad_chunker_enabled=True,
        diarizer_enabled=True,
        diarizer_produced_turns=True,
        backend_internal_segmentation=True,
    )
    fallback = resolve_segmentation_provenance(
        vad_enabled=True,
        vad_chunker_enabled=True,
        diarizer_enabled=True,
        diarizer_produced_turns=False,
        backend_internal_segmentation=True,
    )
    oracle = resolve_segmentation_provenance(
        vad_enabled=True,
        vad_chunker_enabled=False,
        diarizer_enabled=False,
        diarizer_produced_turns=False,
        backend_internal_segmentation=False,
        oracle_reference_used=True,
    )

    assert replaced.effective_source == "backend_internal"
    assert replaced.diarization_replaced_external_vad is True
    assert replaced.external_vad_affected_final_segments is False
    assert fallback.effective_source == "vad_chunker"
    assert oracle.effective_source == "oracle_reference"
    assert oracle.diagnostic_only is True


def test_cpwer_is_permutation_aware_without_identity_rewrite() -> None:
    result = score_speaker_attributed_transcripts(
        {"ref_a": "hello world", "ref_b": "good day"},
        {"speaker_00": "good day", "speaker_01": "hello world"},
    )

    assert result["cpwer"] == pytest.approx(0.0)
    assert result["stored_labels_rewritten"] is False


def test_native_manifest_is_deterministic_and_preserves_native_constraints(
    native_manifest_root: Path,
    tmp_path: Path,
) -> None:
    second = tmp_path / "second"
    build_native_diarization_manifest(second, tier="small")
    for filename in (
        "native_diarization_manifest.parquet",
        "references.rttm",
        "scored_regions.uem",
        "reference_transcripts.jsonl",
    ):
        assert file_sha256(native_manifest_root / filename) == file_sha256(second / filename)
    rows = read_native_manifest(native_manifest_root / "native_diarization_manifest.parquet")

    assert len(rows) == 200
    assert all(row["augmentation_policy"] == "native_only" for row in rows)
    assert all(row["synthetic_augmentation_applied"] is False for row in rows)
    assert all(row["timebase"] == "source_recording_absolute_seconds" for row in rows)
    assert all(not row["der_jer_eligible"] for row in rows if row["dataset"] == "voices")
    assert any(row["meeting_id"] for row in rows if row["dataset"] == "ami")
    assert any(row["session_id"] for row in rows if row["dataset"] == "chime6")


def test_native_manifest_validator_blocks_augmentation(native_manifest_root: Path) -> None:
    rows = read_native_manifest(native_manifest_root / "native_diarization_manifest.parquet")
    rows[0]["augmentation_policy"] = "allow"
    table = pa.Table.from_pylist(rows, schema=NATIVE_MANIFEST_SCHEMA)

    with pytest.raises(DiarizationEvaluationError, match="may not be augmented"):
        validate_native_manifest_table(table)


def test_every_backend_has_explicit_qualification_and_authorization_status() -> None:
    statuses = backend_availability()

    assert set(statuses) == {
        "pyannote_community",
        "sherpa_onnx_diarization",
        "picovoice_falcon",
        "nemo_diarization",
    }
    assert statuses["sherpa_onnx_diarization"]["qualification_status"] == "qualified"
    assert statuses["pyannote_community"]["qualification_status"] == "licence_action_required"
    assert statuses["picovoice_falcon"]["qualification_status"] == "licence_action_required"
    assert statuses["nemo_diarization"]["qualification_status"] == "platform_required"
    assert all(row["implicit_downloads_allowed"] is False for row in statuses.values())


def test_fake_native_execution_preserves_anonymous_labels_and_outputs(
    native_manifest_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = read_native_manifest(native_manifest_root / "native_diarization_manifest.parquet")
    unit = next(
        row
        for row in rows
        if row["dataset"] == "ami" and row["stream_type"] == "array" and row["duration_sec"] > 2
    )
    _patch_fake_backend(monkeypatch)
    output = tmp_path / "result"

    run = run_diarization_unit(
        native_manifest_root,
        str(unit["evaluation_unit_id"]),
        "sherpa_onnx_diarization",
        output,
    )
    validation = validate_diarization_result(output)
    turns = parse_rttm(output / "predictions" / "segments.rttm")
    provenance = json.loads(
        (output / "diagnostics" / "segmentation_provenance.json").read_text(encoding="utf-8")
    )
    diagnostics = json.loads(
        (output / "diagnostics" / "diarization.json").read_text(encoding="utf-8")
    )

    assert run["record"]["recording_id"] == unit["recording_id"]
    assert validation["valid"] is True
    assert turns and all(turn.speaker_label == "speaker_00" for turn in turns)
    assert diagnostics["turns"][0]["label_semantics"] == "anonymous_diarization"
    assert diagnostics["turns"][0]["source_absolute_start_sec"] == pytest.approx(
        unit["source_start_sec"]
    )
    assert provenance["effective_source"] == "backend_internal"
    assert not (output / "predictions" / "speaker_attributed_transcript.jsonl").exists()


def test_voices_execution_keeps_native_diagnostics_but_suppresses_der(
    native_manifest_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unit = next(
        row
        for row in read_native_manifest(native_manifest_root / "native_diarization_manifest.parquet")
        if row["dataset"] == "voices"
    )
    _patch_fake_backend(monkeypatch)
    output = tmp_path / "voices-result"
    run_diarization_unit(
        native_manifest_root,
        str(unit["evaluation_unit_id"]),
        "sherpa_onnx_diarization",
        output,
    )
    metrics = json.loads((output / "metrics" / "summary.json").read_text(encoding="utf-8"))

    assert metrics["metrics_emitted"] is False
    assert "der" not in metrics and "jer" not in metrics
    assert "fine-grained speech timing" in metrics["suppression_reasons"][0]


def test_native_analysis_retains_suppressed_results(
    native_manifest_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = read_native_manifest(native_manifest_root / "native_diarization_manifest.parquet")
    selected = [
        next(row for row in rows if row["dataset"] == "ami" and row["stream_type"] == "array"),
        next(row for row in rows if row["dataset"] == "voices"),
    ]
    _patch_fake_backend(monkeypatch)
    results = []
    for index, unit in enumerate(selected):
        root = tmp_path / f"result-{index}"
        run_diarization_unit(
            native_manifest_root,
            str(unit["evaluation_unit_id"]),
            "sherpa_onnx_diarization",
            root,
        )
        results.append(root)
    summary = aggregate_native_results(results, tmp_path / "analysis")
    grouped = pq.read_table(tmp_path / "analysis" / "grouped_metrics.parquet").to_pylist()
    voices = next(
        row
        for row in grouped
        if row["grouping_dimension"] == "dataset" and row["grouping_value"] == "voices"
    )

    assert summary["result_count"] == 2
    assert summary["suppressed_result_count"] == 1
    assert voices["metric_result_count"] == 0
    assert voices["der"] is None


def test_cli_and_json_schemas_are_discoverable() -> None:
    args = build_parser().parse_args(["diarization", "status"])
    assert args.diarization_command == "status"
    for filename in ("diarization_result.v1.schema.json", "diarization_metrics.v1.schema.json"):
        payload = json.loads(
            (TOOL_ROOT / "configs" / "automated_evaluation" / "schemas" / filename).read_text(
                encoding="utf-8"
            )
        )
        assert payload["$schema"].endswith("2020-12/schema")


def test_real_sherpa_native_smoke_evidence_when_present() -> None:
    summary_path = TOOL_ROOT / "runs" / "diarization_evaluation" / "smoke_summary.json"
    if not summary_path.is_file():
        pytest.skip("real Stage 11 smoke evidence has not been generated")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    result = next(
        row for row in summary["results"] if row["backend_id"] == "sherpa_onnx_diarization"
    )
    result_root = (
        summary_path.parent
        / f"smoke_sherpa_onnx_diarization_{summary['evaluation_unit_id']}"
    )

    assert result.get("status", "succeeded") == "succeeded"
    assert validate_diarization_result(result_root)["valid"] is True


def _patch_fake_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.diarization_evaluation.execution as execution

    status = {
        "backend_id": "sherpa_onnx_diarization",
        "qualification_status": "qualified",
        "qualification_evidence": "synthetic-test",
        "environment_profile": "synthetic",
    }
    identity = {
        "schema_version": "resolved-diarization-component.v1",
        "backend_id": "sherpa_onnx_diarization",
        "source_config_sha256": "A" * 64,
    }

    class FakeDiarizer:
        def diarize(self, audio: object) -> list[SpeakerTurnRegion]:
            duration = min(1.0, float(getattr(audio, "duration_sec")))
            return [SpeakerTurnRegion(0.0, duration, "speaker_00", source="fake")]

    monkeypatch.setattr(execution, "require_executable_backend", lambda backend_id: status)
    monkeypatch.setattr(
        execution,
        "_resolved_component",
        lambda backend_id, backend_status: (
            {"name": backend_id, "enabled": True, "params": {"allow_model_downloads": False}},
            identity,
        ),
    )
    monkeypatch.setattr(execution, "build_diarizer_from_config", lambda config: FakeDiarizer())
