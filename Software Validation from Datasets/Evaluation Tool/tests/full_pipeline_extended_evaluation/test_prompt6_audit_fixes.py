from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.full_pipeline_evaluation.io import sha256_file
from app.full_pipeline_extended_evaluation import controller, execution
from app.full_pipeline_extended_evaluation.analysis import (
    _apply_native_metric_applicability,
    _native_applicability_audit,
)
from app.full_pipeline_extended_evaluation.protocol import (
    _execution_contract_binding,
    _select_distinct_long_sources,
)
from app.full_pipeline_extended_evaluation.reporting import (
    _validate_analysis_evidence,
)


def _proof(code: str = "a") -> dict[str, object]:
    return {
        "execution_contract_validation": "EXACT_LIVE_MATCH",
        "checksums_sha256": "b" * 64,
        "live_result_affecting_code_sha256": code * 64,
        "pipeline_freeze_identity_sha256s": {
            f"pipeline_{index:02d}": "c" * 64 for index in range(18)
        },
    }


def _metric(panel: str, category: str, metric_id: str) -> dict[str, object]:
    return {
        "panel_id": panel,
        "category": category,
        "metric_id": metric_id,
        "status": "computed",
        "value": 0.25,
        "numerator": 1,
        "denominator": 4,
        "details": {},
    }


def test_each_job_live_proof_rejects_result_affecting_code_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry = tmp_path / "registry.json"
    registry.write_text('{"synthetic":true}\n', encoding="utf-8")
    authorization = {
        "frozen_pipeline_configs": {"synthetic": True},
        "decision_policy_registry": {
            "path": str(registry),
            "sha256": sha256_file(registry),
        },
    }
    plan = {"frozen_execution_contract": _execution_contract_binding(_proof())}
    monkeypatch.setattr(
        controller, "_validate_frozen_configs", lambda *args, **kwargs: _proof()
    )

    controller._revalidate_live_execution_proof(authorization, plan)

    monkeypatch.setattr(
        controller,
        "_validate_frozen_configs",
        lambda *args, **kwargs: _proof("d"),
    )
    with pytest.raises(Exception, match="changed before Prompt-6 job"):
        controller._revalidate_live_execution_proof(authorization, plan)


def test_native_metric_applicability_suppresses_disallowed_computed_values() -> None:
    chime = _apply_native_metric_applicability(
        _metric("native_chime6", "asr", "wer"),
        {"cases": [{"supported_views": ["diarization"], "der_jer_eligible": True}]},
    )
    assert chime["status"] == "unsupported"
    assert chime["value"] is None
    assert chime["computed_metric_suppressed"] is True

    ami_supported = _apply_native_metric_applicability(
        _metric("native_ami", "speaker_transcription", "cpwer"),
        {
            "cases": [
                {
                    "supported_views": ["asr", "speaker_attributed_transcript"],
                    "cpwer_eligible": True,
                }
            ]
        },
    )
    assert ami_supported["status"] == "computed"
    assert ami_supported["value"] == 0.25

    voices = _apply_native_metric_applicability(
        _metric("native_voices", "diarization", "der"),
        {"cases": [{"supported_views": ["asr"], "reference_text": "hello"}]},
    )
    assert voices["status"] == "unsupported"
    audit = _native_applicability_audit([chime, ami_supported, voices])
    assert audit["status"] == "PASS"
    assert audit["disallowed_computed_metric_count"] == 0


def test_queue_fault_requires_counter_evidence_and_uninjectable_fault_is_not_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeRuntime:
        def __init__(self, output_root: Path) -> None:
            self.output_root = output_root

        def run(self) -> dict[str, object]:
            metrics = self.output_root / "metrics/runtime_metrics.json"
            metrics.parent.mkdir(parents=True, exist_ok=True)
            metrics.write_text(
                json.dumps(
                    {"queue": {"maximum_observed_depth": 3, "blocked_total_sec": 0.1}}
                ),
                encoding="utf-8",
            )
            return {"completion_state": "complete"}

        def request_stop(self) -> None:
            return None

    monkeypatch.setattr(
        execution,
        "build_file_runtime",
        lambda **kwargs: FakeRuntime(Path(str(kwargs["output_root"]))),
    )
    record = {
        "fault_id": "queue_pressure",
        "target_duration_sec": 30.0,
        "source_case": {},
    }
    spec = SimpleNamespace(pipeline_id="pipeline", job_id="job")
    value = execution._run_reliability(
        record,
        spec=spec,
        input_path=tmp_path / "unused.wav",
        output_root=tmp_path / "queue",
        stop_requested=lambda: False,
        decision_policy_registry_path=tmp_path / "registry.json",
    )
    assert value["harness_status"] == "PASS"
    assert value["fault_injected"] is True
    assert all(row["status"] == "PASS" for row in value["assertions"])

    unsupported = execution._run_reliability(
        {**record, "fault_id": "device_reconnect"},
        spec=spec,
        input_path=tmp_path / "unused.wav",
        output_root=tmp_path / "reconnect",
        stop_requested=lambda: False,
        decision_policy_registry_path=tmp_path / "registry.json",
    )
    assert unsupported["harness_status"] == "UNSUPPORTED"
    assert unsupported["fault_injected"] is False


def test_long_stream_selector_skips_duplicate_overlay_audio() -> None:
    rows = [
        {
            "protocol_case_id": "overlay_a",
            "audio_logical_path": "C:/audio/shared.wav",
            "audio_sha256": "a" * 64,
        },
        {
            "protocol_case_id": "overlay_b",
            "audio_logical_path": "C:/audio/shared.wav",
            "audio_sha256": "a" * 64,
        },
        {
            "protocol_case_id": "distinct",
            "audio_logical_path": "C:/audio/distinct.wav",
            "audio_sha256": "b" * 64,
        },
    ]
    selected = _select_distinct_long_sources(rows)
    assert len(selected) == 2
    assert len({row["audio_sha256"] for row in selected}) == 2


def test_component_rtf_requires_measured_processing_audio_pairs() -> None:
    supported = execution._measured_component_rtfs(
        [
            {
                "component": "asr",
                "processing_sec": 2.0,
                "audio_duration_sec": 10.0,
            },
            {
                "component": "asr",
                "processing_sec": 1.0,
                "audio_duration_sec": 5.0,
            },
        ]
    )
    assert supported["measurement_status"] == (
        "COMPUTED_FROM_MEASURED_PROCESSING_AUDIO_PAIRS"
    )
    assert supported["value"] == pytest.approx(0.2)

    unsupported = execution._measured_component_rtfs(
        [{"component": "asr", "process_cpu_percent": 50.0}]
    )
    assert unsupported["value"] is None
    assert unsupported["measurement_status"].startswith("UNSUPPORTED")


def test_completion_evidence_rejects_a_disallowed_native_metric_claim(
    tmp_path: Path,
) -> None:
    path = tmp_path / "analysis.json"
    value = {
        "schema_version": "full-pipeline-extended-analysis.v1",
        "status": "PASS",
        "native_metric_applicability": {
            "status": "PASS",
            "disallowed_computed_metric_count": 1,
        },
        "reliability_evidence": {
            "status": "PASS",
            "all_faults_have_explicit_evidence_status": True,
        },
        "long_stream_evidence": {"status": "PASS"},
        "component_rtf_evidence": {
            "status": "PASS",
            "false_computed_component_rtf_count": 0,
        },
        "deployment_evidence": {
            "status": "PASS",
            "pipeline_membership_changed": False,
            "deployment_evidence_used_as_filter": False,
            "desktop_evidence_relabelled_as_arm": False,
        },
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(Exception, match="disallowed native"):
        _validate_analysis_evidence(path)
    value["native_metric_applicability"]["disallowed_computed_metric_count"] = 0
    path.write_text(json.dumps(value), encoding="utf-8")
    assert _validate_analysis_evidence(path)["status"] == "PASS"
