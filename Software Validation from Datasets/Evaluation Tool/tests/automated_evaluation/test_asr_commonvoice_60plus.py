from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.asr_commonvoice import analysis as analysis_module
from app.asr_commonvoice import collection as collection_module
from app.asr_commonvoice import runner as runner_module
from app.asr_commonvoice.analysis import analyze
from app.asr_commonvoice.collection import collect, validate_collection
from app.asr_commonvoice.contracts import (
    DEFAULT_PROTOCOL_ROOT,
    MODEL_COMPONENT_IDS,
    default_result_root,
    resolve_models,
)
from app.asr_commonvoice.protocol import read_manifest, validate_protocol
from app.dataset_registry.registry import TextNormalizationSpec
from app.scoring.text import normalize_for_scoring
from app.scoring.wer import compute_wer


TOOL_ROOT = Path(__file__).resolve().parents[2]


def test_frozen_manifest_exactly_preserves_breadth_membership_references_and_metadata() -> None:
    validation = validate_protocol(DEFAULT_PROTOCOL_ROOT)
    rows = read_manifest(DEFAULT_PROTOCOL_ROOT)
    assert validation["selected_items"] == 11685
    assert validation["selected_speakers"] == 413
    assert len({row["item_id"] for row in rows}) == 11685
    assert {row["age_category"] for row in rows} == {"sixties", "seventies", "eighties", "nineties"}
    assert all(str(row["speaker_key"]).startswith("spk_cv60p_") for row in rows)
    assert all(str(row["reference_text"]).strip() for row in rows)
    assert all(row["locale"] == "en" for row in rows)


def test_manifest_is_deterministic_and_has_no_out_of_protocol_clip() -> None:
    first = read_manifest(DEFAULT_PROTOCOL_ROOT)
    second = read_manifest(DEFAULT_PROTOCOL_ROOT)
    assert first == second
    source_ids = {
        line.split("\t", 1)[0]
        for line in (TOOL_ROOT / "benchmarks" / "speaker_breadth" / "commonvoice_60plus_v1" / "source_selection.tsv").read_text(encoding="utf-8").splitlines()[1:]
    }
    assert {row["item_id"] for row in first} == source_ids


def test_exact_three_models_and_environments_resolve_ready() -> None:
    models = resolve_models()
    assert tuple(row["component_id"] for row in models) == MODEL_COMPONENT_IDS
    assert [row["environment_profile"] for row in models] == ["onnx", "onnx", "core-cpu"]
    assert all(row["asset_ready"] and row["environment_ready"] for row in models)


def test_existing_normalization_and_error_scoring_are_reused() -> None:
    spec = TextNormalizationSpec(lowercase=True, remove_punctuation=True, strip_whitespace=True, collapse_whitespace=True)
    reference = normalize_for_scoring("We're 60-plus -- today!", spec)
    hypothesis = normalize_for_scoring("we're sixty plus today", spec)
    assert reference == "were 60plus today"
    result = compute_wer(reference, hypothesis)
    assert result.reference_words == 3
    assert result.substitutions + result.deletions + result.insertions == result.errors


def test_restart_reuses_valid_atomic_items_and_status_reports_progress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _manifest(9)
    protocol = {"valid": True, "protocol_id": "protocol-test", "manifest_sha256": "A" * 64}
    calls = {"count": 0}

    class FakePipeline:
        asr = SimpleNamespace(last_raw_text="RAW hypothesis")

        def predict(self, record, config):
            calls["count"] += 1
            return SimpleNamespace(text="reference words", warnings=(), diagnostics={"asr_backend_runtime": {"load_sec": 0.01}})

    class FakeResolution:
        pipeline_config = SimpleNamespace(runtime=SimpleNamespace(to_jsonable=lambda: {}))

        def write_artifacts(self, root):
            root.mkdir(parents=True, exist_ok=True)
            (root / "resolved.json").write_text("{}\n", encoding="utf-8")

    model = _model(MODEL_COMPONENT_IDS[0])
    monkeypatch.setattr(runner_module, "validate_protocol", lambda root: protocol)
    monkeypatch.setattr(runner_module, "read_manifest", lambda root: manifest)
    monkeypatch.setattr(runner_module, "read_smoke_ids", lambda root: tuple(row["item_id"] for row in manifest))
    monkeypatch.setattr(runner_module, "resolve_models", lambda: [model])
    monkeypatch.setattr(runner_module, "_validate_runtime", lambda model: None)
    monkeypatch.setattr(runner_module, "campaign_identity", lambda value: "campaign-test")
    monkeypatch.setattr(runner_module, "implementation_sha256", lambda: "B" * 64)
    monkeypatch.setattr(runner_module, "resolve_pipeline", lambda *args, **kwargs: FakeResolution())
    monkeypatch.setattr(runner_module.PipelineRunner, "from_config", lambda config: FakePipeline())
    monkeypatch.setattr(runner_module, "resolve_data_path_from_logical", lambda value: tmp_path / "audio.wav")
    monkeypatch.setattr(runner_module, "git_sha", lambda: "deadbeef")

    root = tmp_path / "smoke"
    first = runner_module.run_backend(
        MODEL_COMPONENT_IDS[0], root, tmp_path, smoke=True, concurrent_model_limit=2
    )
    assert first["successful_items"] == 9
    assert calls["count"] == 9
    second = runner_module.run_backend(
        MODEL_COMPONENT_IDS[0], root, tmp_path, smoke=True, concurrent_model_limit=2
    )
    assert second["reused_items_this_invocation"] == 9
    assert calls["count"] == 9
    progress = json.loads((root / MODEL_COMPONENT_IDS[0] / "progress.json").read_text(encoding="utf-8"))
    assert progress["completed_items"] == progress["total_items"] == 9
    assert progress["clips_per_sec"] > 0
    assert progress["concurrent_model_limit"] == 2
    identity = json.loads((root / MODEL_COMPONENT_IDS[0] / "backend_identity.json").read_text(encoding="utf-8"))
    assert identity["execution"]["resource_metrics_collected_during_concurrent_models"] is True


def test_analyze_and_collect_emit_required_tables_and_compact_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _manifest(3)
    result_root = tmp_path / "results"
    for model_index, component in enumerate(MODEL_COMPONENT_IDS):
        root = result_root / component
        (root / "inference").mkdir(parents=True)
        identity = {
            "campaign_id": "campaign-test",
            "backend_run_id": f"run-{model_index}",
            "mode": "smoke_non_scientific",
            "scientific_use_prohibited": True,
            "repository_git_sha": "deadbeef",
            "model": _model(component),
            "host": {"node": "test-host", "processor": "test-cpu"},
        }
        (root / "backend_identity.json").write_text(json.dumps(identity), encoding="utf-8")
        (root / "inference" / "resolved.json").write_text("{}\n", encoding="utf-8")
        rows = [_result(row, component, model_index) for row in manifest]
        pq.write_table(pa.Table.from_pylist(rows), root / "utterance_results.parquet")
        (root / "predictions.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        for name in ("summary.json", "validation.json", "progress.json"):
            (root / name).write_text("{}\n", encoding="utf-8")

    protocol = {"valid": True, "protocol_id": "protocol-test", "manifest_sha256": "A" * 64}
    monkeypatch.setattr(analysis_module, "validate_protocol", lambda root: protocol)
    monkeypatch.setattr(analysis_module, "read_manifest", lambda root: manifest)
    monkeypatch.setattr(analysis_module, "validate_backend", lambda root, protocol: {"valid": True})
    summary = analyze(result_root, tmp_path)
    assert summary["scientific_use_prohibited"] is True
    for name in ("overall_results.csv", "utterance_results.parquet", "speaker_results.csv", "age_category_results.csv", "pairwise_results.csv", "analysis_manifest.json", "report.md"):
        assert (result_root / "analysis" / name).is_file()

    protocol_root = tmp_path / "protocol"
    protocol_root.mkdir()
    for name, content in {
        "protocol_summary.json": "{}\n",
        "protocol_files.json": "{}\n",
        "campaign_config.yaml": "schema: test\n",
    }.items():
        (protocol_root / name).write_text(content, encoding="utf-8")
    pq.write_table(pa.Table.from_pylist(manifest), protocol_root / "manifest.parquet")
    monkeypatch.setattr(collection_module, "validate_protocol", lambda root: protocol)
    package = tmp_path / "package"
    collected = collect(result_root, protocol_root, package, create_zip=True)
    assert collected["valid"]
    assert validate_collection(package)["valid"]
    for name in ("RUN_SUMMARY.csv", "RUN_PROVENANCE.txt", "RESULT_FILE_INVENTORY.csv", "PROTOCOL_SUMMARY.json", "MODEL_SUMMARY.csv", "collection_manifest.json"):
        assert (package / name).is_file()
    assert not any(path.suffix in {".wav", ".mp3", ".pt", ".onnx"} for path in package.rglob("*"))


def test_storage_and_monitor_are_local_and_read_only() -> None:
    protocol = validate_protocol(DEFAULT_PROTOCOL_ROOT)
    root = default_result_root(protocol)
    assert "Evaluation Tool" in str(root)
    assert "JustPeachyResults" in str(root)
    monitor = (TOOL_ROOT / "scripts" / "monitor_asr_commonvoice_60plus.ps1").read_text(encoding="utf-8")
    assert "asr-commonvoice', 'status'" in monitor
    assert all(token not in monitor for token in ("Remove-Item", "Move-Item", "run-backend", "analyze", "collect"))


def test_wrapper_parallel_mode_preserves_exact_three_model_processes() -> None:
    wrapper = (TOOL_ROOT / "scripts" / "run_asr_commonvoice_60plus.ps1").read_text(encoding="utf-8")
    assert "[int]$ParallelModels = 1" in wrapper
    assert "[System.Diagnostics.Process]::Start" in wrapper
    assert "--parallel-models" in wrapper
    assert "Invoke-Core 'analyze'" in wrapper
    assert "Invoke-Core 'collect'" in wrapper


def _manifest(count: int) -> list[dict[str, object]]:
    ages = ("sixties", "seventies", "eighties", "nineties")
    return [
        {
            "item_id": f"item-{index}",
            "source_recording_id": f"recording-{index}",
            "speaker_key": f"spk_cv60p_{index}",
            "speaker_role": "known",
            "protocol_split": "evaluation",
            "age_category": ages[index % len(ages)],
            "age_group": "eighties_plus" if ages[index % len(ages)] in {"eighties", "nineties"} else ages[index % len(ages)],
            "logical_audio_path": f"Raw Datasets (Not formatted)/test-{index}.wav",
            "audio_sha256": "A" * 64,
            "duration_sec": 1.0 + index,
            "duration_bucket": "lt_2s" if index == 0 else "2_to_lt_4s",
            "reference_text": "reference words",
            "reference_normalized": "reference words",
            "reference_words": 2,
            "transcript_length_bucket": "1_to_5_words",
            "sample_rate_hz": 16000,
        }
        for index in range(count)
    ]


def _model(component: str) -> dict[str, object]:
    return {
        "human_name": component,
        "component_id": component,
        "adapter": "TestAdapter",
        "model_identity": {"name": component},
        "model_assets": [{"path": "models/test", "observed_bytes": 1, "observed_sha256": "A" * 64}],
        "asset_ready": True,
        "environment_profile": "onnx",
        "environment_interpreter": "python.exe",
        "environment_ready": True,
        "runtime": "test-runtime",
        "device": "cpu",
        "precision": "float32",
        "config_sha256": "C" * 64,
    }


def _result(row: dict[str, object], component: str, model_index: int) -> dict[str, object]:
    errors = model_index
    return {
        "status": "ok",
        "item_id": row["item_id"],
        "reference_text": row["reference_text"],
        "reference_normalized": row["reference_normalized"],
        "hypothesis_raw": "reference words" if model_index == 0 else "reference",
        "hypothesis_text": "reference words" if model_index == 0 else "reference",
        "hypothesis_normalized": "reference words" if model_index == 0 else "reference",
        "wer": errors / 2,
        "cer": errors / 10,
        "errors": errors,
        "substitutions": errors,
        "deletions": 0,
        "insertions": 0,
        "reference_words": 2,
        "hypothesis_words": 2 - min(model_index, 1),
        "duration_sec": row["duration_sec"],
        "elapsed_sec": 0.1 + model_index,
        "realtime_factor": (0.1 + model_index) / float(row["duration_sec"]),
        "process_cpu_sec": 0.05,
        "process_rss_mb": 100.0 + model_index,
        "warnings": [],
        "asr_backend_runtime": {"load_sec": 0.01},
    }
