from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pytest

from app.artifact_contracts import atomic as atomic_module
from app.artifact_contracts.atomic import (
    ScenarioArtifactStore,
    file_sha256,
    publish_campaign_manifest,
    validate_campaign_manifest_pair,
)
from app.artifact_contracts.completion import validate_scenario_completion
from app.artifact_contracts.environment import (
    collect_environment_fingerprint,
    finalize_environment_fingerprint,
    identity_hashes_from_resolved_scenario,
    validate_environment_fingerprint,
)
from app.artifact_contracts.layout import (
    CAMPAIGN_SUBDIRECTORIES,
    SCENARIO_SUBDIRECTORIES,
    CampaignLayout,
)
from app.artifact_contracts.registry import (
    ARTIFACT_REGISTRY_VERSION,
    ArtifactRegistry,
    ArtifactRegistryError,
    normalize_artifact_path,
)
from app.artifact_contracts.schemas import (
    ArtifactSchemaError,
    IncompatibleArtifactError,
    validate_artifact,
)
from app.benchmark_contracts.canonical import canonical_sha256


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = TOOL_ROOT.parents[1]
STAGE2_FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage2"
FIXED_TIME = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)


def _scenario(*, capabilities: list[str] | None = None) -> dict[str, object]:
    value = json.loads(
        (STAGE2_FIXTURES / "golden_scenario.json").read_text(encoding="utf-8")
    )
    value["artifact_contract"] = {
        "schema_version": "scenario-artifact-requirements.v1",
        "scenario_type": "asr",
        "capabilities": capabilities or [],
    }
    return value


def _counts(*, words: int | None = None) -> dict[str, int]:
    values = {
        "selected_items": 4,
        "successful_items": 3,
        "failed_items": 1,
        "predictions": 3,
        "diagnostics": 3,
        "item_metrics": 4,
        "grouped_metrics": 1,
        "error_records": 0,
    }
    if words is not None:
        values["words"] = words
    return values


def _store(
    root: Path, scenario: dict[str, object], *, hook=None
) -> ScenarioArtifactStore:
    return ScenarioArtifactStore(
        root,
        str(scenario["scenario_id"]),
        phase_hook=hook,
        clock=lambda: FIXED_TIME,
    )


def _build_complete_asr(
    parent: Path,
    *,
    word_timestamps: bool = False,
) -> tuple[Path, dict[str, object], ScenarioArtifactStore]:
    scenario = _scenario(capabilities=["word_timestamps"] if word_timestamps else [])
    scenario_root = parent / str(scenario["scenario_id"])
    layout = CampaignLayout.resolve(parent / "automated_runs", "campaign_fixture01")
    layout.create([str(scenario["scenario_id"])])
    scenario_root = layout.scenario_root(str(scenario["scenario_id"]))
    store = _store(scenario_root, scenario)
    counts = _counts(words=3 if word_timestamps else None)
    scenario_id = str(scenario["scenario_id"])
    scenario_hash = str(scenario["scenario_hash"])

    store.publish_json("resolved_scenario.json", scenario)
    store.publish_yaml(
        "run_config.yaml",
        {
            "schema_version": "run-config.v1",
            "artifact_registry_version": ARTIFACT_REGISTRY_VERSION,
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "settings": {"output_root": "scenarios/current"},
        },
    )
    store.publish_json(
        "status.json",
        {
            "schema_version": "scenario-status.v1",
            "artifact_registry_version": ARTIFACT_REGISTRY_VERSION,
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "scenario_type": "asr",
            "state": "successful",
            "counts": counts,
        },
    )
    utterances = [
        {
            "recording_id": f"rec-{index}",
            "utt_id": f"utt-{index}",
            "start_sec": 0.0,
            "end_sec": 1.0,
            "speaker_label": "Unknown",
            "text": f"fixture prediction {index}",
        }
        for index in range(3)
    ]
    store.publish_jsonl("predictions/utterances.jsonl", utterances)
    store.publish_jsonl(
        "predictions/diagnostics.jsonl",
        [
            {"recording_id": row["recording_id"], "utt_id": row["utt_id"]}
            for row in utterances
        ],
    )
    if word_timestamps:
        store.publish_jsonl(
            "predictions/words.jsonl",
            [
                {
                    "recording_id": row["recording_id"],
                    "utt_id": row["utt_id"],
                    "start_sec": 0.0,
                    "end_sec": 0.5,
                    "word": "fixture",
                    "speaker_label": "Unknown",
                    "confidence": 0.9,
                }
                for row in utterances
            ],
        )
    store.publish_parquet(
        "metrics/item_metrics.parquet",
        pa.table(
            {
                "recording_id": [f"rec-{index}" for index in range(4)],
                "utt_id": [f"utt-{index}" for index in range(4)],
            }
        ),
    )
    store.publish_parquet(
        "metrics/grouped_metrics.parquet",
        pa.table(
            {
                "group_key": ["dataset"],
                "group_value": ["fixture"],
                "metric_name": ["wer"],
                "metric_value": pa.array([0.25], type=pa.float64()),
            }
        ),
    )
    store.publish_json(
        "metrics/summary.json",
        {
            "schema_version": "metrics-summary.v1",
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "counts": counts,
            "metrics": {"wer": 0.25},
        },
    )
    store.publish_parquet(
        "metrics/failures.parquet",
        pa.table(
            {
                "recording_id": ["rec-3"],
                "utt_id": ["utt-3"],
                "error_type": ["FixtureError"],
                "message": ["synthetic contract failure"],
            }
        ),
    )
    store.publish_jsonl(
        "logs/events.jsonl",
        [
            {
                "schema_version": "scenario-events.v1",
                "scenario_id": scenario_id,
                "timestamp_utc": "2026-08-08T12:00:00Z",
                "event_type": "scenario_completed",
            }
        ],
    )
    store.publish_text("logs/runner.log", "synthetic executor contract fixture\n")
    store.publish_jsonl("logs/errors.jsonl", [])
    store.publish_json(
        "report/scenario_report.json",
        {
            "schema_version": "scenario-report.v1",
            "scenario_id": scenario_id,
            "scenario_hash": scenario_hash,
            "completion_state": "complete",
            "counts": counts,
            "metrics": {"wer": 0.25},
        },
    )
    store.publish_text("report/scenario_report.md", "# Synthetic scenario report\n")
    return scenario_root, scenario, store


def test_artifact_registry_definitions_are_complete_and_pickle_is_forbidden() -> None:
    registry = ArtifactRegistry.load()
    assert registry.schema_version == "artifact-registry.v1"
    assert "pickle" not in registry.allowed_formats
    assert len(registry.artifacts) >= 25
    for definition in registry.artifacts:
        assert definition.path
        assert definition.producer
        assert definition.format
        assert definition.schema_version
        assert definition.status in {"mandatory", "conditional"}
        assert definition.validation_rules
        assert definition.checksum_policy
        assert definition.privacy_classification
        assert definition.downstream_consumers


def test_stage3_public_json_and_table_schemas_are_parseable() -> None:
    schema_root = TOOL_ROOT / "configs" / "automated_evaluation" / "schemas"
    expected = {
        "artifact_registry.v1.schema.json",
        "campaign_manifest.v1.schema.json",
        "checksums.v1.schema.json",
        "environment_fingerprint.v1.schema.json",
        "metrics_summary.v1.schema.json",
        "run_config.v1.schema.json",
        "scenario_event.v1.schema.json",
        "scenario_report.v1.schema.json",
        "scenario_status.v1.schema.json",
    }
    assert expected.issubset({path.name for path in schema_root.glob("*.json")})
    for name in expected:
        value = json.loads((schema_root / name).read_text(encoding="utf-8"))
        assert value["$schema"].endswith("2020-12/schema")
    table_contract = (
        TOOL_ROOT / "configs" / "automated_evaluation" / "table_schemas.v1.yaml"
    ).read_text(encoding="utf-8")
    assert "artifact-table-schemas.v1" in table_contract
    assert "failures.v1" in table_contract


def test_scenario_profiles_are_explicit_for_every_required_type() -> None:
    registry = ArtifactRegistry.load()
    assert set(registry.scenario_profiles) == {
        "asr",
        "vad_only",
        "embedding_extraction",
        "speaker_verification",
        "diarization",
        "synthetic_executor",
    }
    embedding = registry.scenario_profiles["embedding_extraction"].required_artifacts
    assert {"embedding_index", "embedding_npz"}.issubset(embedding)
    diarization = registry.scenario_profiles["diarization"].required_artifacts
    assert {"segments_rttm", "diarization_diagnostics"}.issubset(diarization)


def test_campaign_layout_creates_only_contract_directories(tmp_path: Path) -> None:
    layout = CampaignLayout.resolve(tmp_path / "automated_runs", "campaign_fixture01")
    scenario_id = str(_scenario()["scenario_id"])
    layout.create([scenario_id])
    for relative in CAMPAIGN_SUBDIRECTORIES:
        assert (layout.campaign_root / relative).is_dir()
    for relative in SCENARIO_SUBDIRECTORIES:
        assert (layout.scenario_root(scenario_id) / relative).is_dir()
    assert not (layout.campaign_root / "campaign_manifest.json").exists()


def test_cross_machine_artifact_paths_normalize_to_posix() -> None:
    assert normalize_artifact_path(r"metrics\summary.json") == "metrics/summary.json"
    with pytest.raises(ArtifactRegistryError):
        normalize_artifact_path(r"C:\machine-a\summary.json")
    with pytest.raises(ArtifactRegistryError):
        normalize_artifact_path("../machine-b/summary.json")


def test_campaign_manifest_and_detached_checksum_are_atomic(tmp_path: Path) -> None:
    campaign_root = tmp_path / "campaign_fixture01"
    manifest = {
        "schema_version": "campaign-manifest.v1",
        "campaign_id": "campaign_fixture01",
        "created_at_utc": "2026-08-08T12:00:00Z",
        "artifact_registry_version": ARTIFACT_REGISTRY_VERSION,
        "scenario_schema_version": "scenario-definition.v1",
        "benchmark_manifests": [
            {
                "manifest_id": "manifest_aaaaaaaaaaaa",
                "path": "benchmark_manifests/small.parquet",
                "sha256": "A" * 64,
            }
        ],
        "scenario_ids": [str(_scenario()["scenario_id"])],
    }
    identity = publish_campaign_manifest(campaign_root, manifest)
    assert identity["sha256"] == file_sha256(campaign_root / "campaign_manifest.json")
    validate_campaign_manifest_pair(campaign_root)


def test_complete_asr_scenario_satisfies_contract(tmp_path: Path) -> None:
    scenario_root, _, _ = _build_complete_asr(tmp_path)
    report = validate_scenario_completion(scenario_root)
    assert report.state == "complete", report.to_jsonable()
    assert report.observed_counts["predictions"] == 3
    assert report.observed_counts["failed_items"] == 1


def test_atomic_interruption_before_replace_preserves_previous_artifact(
    tmp_path: Path,
) -> None:
    scenario_root, scenario, _ = _build_complete_asr(tmp_path)
    target = scenario_root / "logs" / "runner.log"
    previous = target.read_bytes()

    def interrupt(phase: str, _target: Path) -> None:
        if phase == "after_write":
            raise RuntimeError("simulated interruption")

    interrupted_store = _store(scenario_root, scenario, hook=interrupt)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        interrupted_store.publish_text("logs/runner.log", "replacement\n")
    assert target.read_bytes() == previous
    assert not list(scenario_root.rglob("*.tmp-*"))
    assert validate_scenario_completion(scenario_root).state == "complete"


def test_atomic_replace_retries_transient_windows_sharing_violation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = _scenario()
    scenario_root = tmp_path / str(scenario["scenario_id"])
    original_replace = atomic_module.os.replace
    replace_attempts = 0

    def sharing_violation_once(source: Path, target: Path) -> None:
        nonlocal replace_attempts
        if Path(target).name == "runner.log":
            replace_attempts += 1
            if replace_attempts == 1:
                error = PermissionError("simulated Windows sharing violation")
                error.winerror = 32
                raise error
        original_replace(source, target)

    monkeypatch.setattr(atomic_module.os, "replace", sharing_violation_once)
    _store(scenario_root, scenario).publish_text("logs/runner.log", "published\n")

    assert replace_attempts == 2
    assert (scenario_root / "logs" / "runner.log").read_text(encoding="utf-8") == (
        "published\n"
    )
    assert not list(scenario_root.rglob("*.tmp-*"))


def test_interruption_after_replace_is_detected_and_reconcilable(
    tmp_path: Path,
) -> None:
    scenario_root, scenario, _ = _build_complete_asr(tmp_path)

    def interrupt(phase: str, _target: Path) -> None:
        if phase == "after_replace":
            raise RuntimeError("simulated post-rename interruption")

    interrupted_store = _store(scenario_root, scenario, hook=interrupt)
    with pytest.raises(RuntimeError, match="post-rename"):
        interrupted_store.publish_text("logs/runner.log", "valid replacement\n")
    assert validate_scenario_completion(scenario_root).state == "corrupt"
    _store(scenario_root, scenario).reconcile_checksum_manifest()
    assert validate_scenario_completion(scenario_root).state == "complete"


def test_truncated_jsonl_is_corrupt(tmp_path: Path) -> None:
    scenario_root, _, _ = _build_complete_asr(tmp_path)
    path = scenario_root / "predictions" / "utterances.jsonl"
    path.write_text('{"recording_id":', encoding="utf-8")
    report = validate_scenario_completion(scenario_root)
    assert report.state == "corrupt"
    assert any(issue.code == "artifact_invalid" for issue in report.issues)


def test_checksum_detects_byte_modification(tmp_path: Path) -> None:
    scenario_root, _, _ = _build_complete_asr(tmp_path)
    path = scenario_root / "logs" / "runner.log"
    path.write_text(path.read_text(encoding="utf-8") + "modified\n", encoding="utf-8")
    report = validate_scenario_completion(scenario_root)
    assert report.state == "corrupt"
    assert any(issue.code == "checksum_mismatch" for issue in report.issues)


def test_missing_required_artifact_is_incomplete(tmp_path: Path) -> None:
    scenario_root, _, _ = _build_complete_asr(tmp_path)
    (scenario_root / "report" / "scenario_report.md").unlink()
    report = validate_scenario_completion(scenario_root)
    assert report.state == "incomplete"
    assert any(issue.code == "missing_required_artifact" for issue in report.issues)


def test_conditional_word_artifact_is_required_only_when_declared(
    tmp_path: Path,
) -> None:
    scenario_root, _, _ = _build_complete_asr(tmp_path, word_timestamps=True)
    assert validate_scenario_completion(scenario_root).state == "complete"
    (scenario_root / "predictions" / "words.jsonl").unlink()
    report = validate_scenario_completion(scenario_root)
    assert report.state == "incomplete"
    assert "words" in report.expected_artifact_ids


def test_count_reconciliation_detects_logically_inconsistent_status(
    tmp_path: Path,
) -> None:
    scenario_root, scenario, store = _build_complete_asr(tmp_path)
    wrong_counts = _counts()
    wrong_counts["successful_items"] = 2
    store.publish_json(
        "status.json",
        {
            "schema_version": "scenario-status.v1",
            "artifact_registry_version": ARTIFACT_REGISTRY_VERSION,
            "scenario_id": scenario["scenario_id"],
            "scenario_hash": scenario["scenario_hash"],
            "scenario_type": "asr",
            "state": "successful",
            "counts": wrong_counts,
        },
    )
    report = validate_scenario_completion(scenario_root)
    assert report.state == "corrupt"
    assert any(issue.code == "outcome_count_mismatch" for issue in report.issues)


def test_stale_temporary_file_makes_scenario_incomplete(tmp_path: Path) -> None:
    scenario_root, _, _ = _build_complete_asr(tmp_path)
    stale = scenario_root / "logs" / ".runner.log.tmp-deadbeef"
    stale.write_text("partial", encoding="utf-8")
    report = validate_scenario_completion(scenario_root)
    assert report.state == "incomplete"
    assert any(issue.code == "stale_temporary_file" for issue in report.issues)


def test_unsupported_artifact_schema_is_incompatible(tmp_path: Path) -> None:
    scenario_root, _, _ = _build_complete_asr(tmp_path)
    status_path = scenario_root / "status.json"
    value = json.loads(status_path.read_text(encoding="utf-8"))
    value["schema_version"] = "scenario-status.v2"
    status_path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    report = validate_scenario_completion(scenario_root)
    assert report.state == "incompatible"


def test_environment_fingerprint_hash_excludes_collection_time() -> None:
    package_freeze = [{"name": "fixture", "version": "1.0"}]
    base = {
        "schema_version": "environment-fingerprint.v1",
        "captured_at_utc": "2026-08-08T12:00:00Z",
        "git": {"commit": "A" * 40, "dirty": False, "changed_path_count": 0},
        "os": {
            "system": "Windows",
            "release": "11",
            "version": "fixture",
            "machine": "AMD64",
        },
        "python": {
            "executable": r"C:\envs\speech\python.exe",
            "version": "3.12.7",
            "implementation": "CPython",
        },
        "packages": {
            "profile_identity": "core_cpu_development",
            "freeze": package_freeze,
            "freeze_sha256": canonical_sha256(package_freeze),
        },
        "hardware": {
            "cpu": "Fixture CPU",
            "logical_cpu_count": 8,
            "ram_bytes": 16_000_000_000,
        },
        "accelerator": {
            "gpus": [{"name": "Fixture GPU", "uuid": "GPU-fixture"}],
            "driver": "1.0",
            "cuda_runtime": "12.8",
        },
        "model_hashes": {"asr": "B" * 64},
        "component_config_hashes": {"asr": "C" * 64},
        "clock": {
            "timezone_name": "America/Toronto",
            "utc_offset_seconds": -14400,
            "wall_clock": "fixture",
            "wall_clock_resolution_sec": 1e-07,
            "monotonic_clock": "fixture",
            "monotonic_resolution_sec": 1e-07,
        },
    }
    first = finalize_environment_fingerprint(base)
    second_source = deepcopy(base)
    second_source["captured_at_utc"] = "2026-08-09T12:00:00Z"
    second = finalize_environment_fingerprint(second_source)
    assert first["fingerprint_id"] == second["fingerprint_id"]
    validate_environment_fingerprint(first)


def test_environment_fingerprint_accepts_cross_machine_python_paths() -> None:
    package_freeze: list[dict[str, str]] = []
    common = {
        "schema_version": "environment-fingerprint.v1",
        "captured_at_utc": "2026-08-08T12:00:00Z",
        "git": {"commit": "A" * 40, "dirty": True, "changed_path_count": 2},
        "os": {"system": "fixture"},
        "packages": {
            "profile_identity": "fixture",
            "freeze": package_freeze,
            "freeze_sha256": canonical_sha256(package_freeze),
        },
        "hardware": {"cpu": "fixture", "logical_cpu_count": 4, "ram_bytes": 1},
        "accelerator": {"gpus": [], "driver": None, "cuda_runtime": None},
        "model_hashes": {},
        "component_config_hashes": {},
        "clock": {
            "timezone_name": "UTC",
            "utc_offset_seconds": 0,
            "wall_clock": "fixture",
            "wall_clock_resolution_sec": 1e-06,
            "monotonic_clock": "fixture",
            "monotonic_resolution_sec": 1e-06,
        },
    }
    for executable in (r"C:\envs\speech\python.exe", "/opt/speech/bin/python"):
        value = dict(common)
        value["python"] = {
            "executable": executable,
            "version": "3.12.7",
            "implementation": "CPython",
        }
        validate_environment_fingerprint(finalize_environment_fingerprint(value))


def test_environment_hashes_are_extracted_from_resolved_scenario() -> None:
    model_hashes, component_hashes = identity_hashes_from_resolved_scenario(_scenario())
    assert model_hashes["asr"]["asset_000"] == "D" * 64
    assert component_hashes["asr"]["config_contents"] == (
        "1AFD8F5452C2CB6EAFAF4DB9D28CE992F894BB6E6A1E02D35BE1D3611C39487E"
    )


def test_atomic_writer_rejects_credential_values_and_removes_temp_file(
    tmp_path: Path,
) -> None:
    scenario = _scenario()
    root = tmp_path / str(scenario["scenario_id"])
    store = _store(root, scenario)
    with pytest.raises(ArtifactSchemaError, match="credential"):
        store.publish_text("logs/runner.log", "API_KEY=super-secret-value\n")
    assert not (root / "logs" / "runner.log").exists()
    assert not list(root.rglob("*.tmp-*"))


def test_host_environment_fingerprint_contains_required_static_identity() -> None:
    fingerprint = collect_environment_fingerprint(
        REPOSITORY_ROOT,
        profile_identity="core_cpu_development",
        model_hashes={"fixture": "A" * 64},
        component_config_hashes={"fixture": "B" * 64},
        captured_at=FIXED_TIME,
    )
    validate_environment_fingerprint(fingerprint)
    assert fingerprint["git"]["commit"]
    assert isinstance(fingerprint["git"]["dirty"], bool)
    assert fingerprint["python"]["executable"]
    assert fingerprint["hardware"]["logical_cpu_count"]


def test_direct_schema_validation_rejects_wrong_parquet_types(tmp_path: Path) -> None:
    registry = ArtifactRegistry.load()
    scenario = _scenario()
    root = tmp_path / str(scenario["scenario_id"])
    store = _store(root, scenario)
    with pytest.raises(ArtifactSchemaError, match="metric_value"):
        store.publish_parquet(
            "metrics/grouped_metrics.parquet",
            pa.table(
                {
                    "group_key": ["dataset"],
                    "group_value": ["fixture"],
                    "metric_name": ["wer"],
                    "metric_value": ["not-a-float"],
                }
            ),
        )
    assert not list(root.rglob("*.tmp-*"))
    assert registry.get("grouped_metrics").schema_version == "grouped-metrics.v1"


def test_embedding_and_similarity_conditional_formats_are_typed(tmp_path: Path) -> None:
    scenario = _scenario()
    root = tmp_path / str(scenario["scenario_id"])
    store = _store(root, scenario)
    store.publish_npz(
        "predictions/embeddings/embedding_000.npz",
        {"embedding": np.asarray([0.1, 0.2, 0.3], dtype=np.float32)},
    )
    store.publish_parquet(
        "predictions/embeddings/index.parquet",
        pa.table(
            {
                "embedding_id": ["embedding_000"],
                "recording_id": ["rec-0"],
                "utt_id": ["utt-0"],
                "path": ["predictions/embeddings/embedding_000.npz"],
                "dimensions": pa.array([3], type=pa.int64()),
                "model_id": ["fixture-model"],
            }
        ),
    )
    store.publish_parquet(
        "predictions/similarity_scores.parquet",
        pa.table(
            {
                "probe_id": ["utt-0"],
                "candidate_speaker_id": ["speaker-a"],
                "score": pa.array([0.8], type=pa.float64()),
                "decision": ["known"],
            }
        ),
    )
    checksums = json.loads((root / "checksums.json").read_text(encoding="utf-8"))
    assert len(checksums["entries"]) == 3


def test_embedding_npz_rejects_pickle_object_arrays(tmp_path: Path) -> None:
    scenario = _scenario()
    root = tmp_path / str(scenario["scenario_id"])
    store = _store(root, scenario)
    with pytest.raises(ArtifactSchemaError, match="unsafe NPZ"):
        store.publish_npz(
            "predictions/embeddings/unsafe.npz",
            {"embedding": np.asarray([{"unsafe": True}], dtype=object)},
        )
    assert not (root / "predictions" / "embeddings" / "unsafe.npz").exists()


def test_diarization_conditional_formats_validate(tmp_path: Path) -> None:
    scenario = _scenario()
    root = tmp_path / str(scenario["scenario_id"])
    store = _store(root, scenario)
    store.publish_text(
        "predictions/segments.rttm",
        "SPEAKER rec-0 1 0.000 1.000 <NA> <NA> speaker-a <NA> <NA>\n",
    )
    store.publish_jsonl(
        "predictions/diarization_diagnostics.jsonl",
        [{"recording_id": "rec-0", "utt_id": "utt-0", "turn_count": 1}],
    )
    assert (root / "predictions" / "segments.rttm").is_file()
    assert (root / "predictions" / "diarization_diagnostics.jsonl").is_file()


def test_truncated_parquet_validation_is_corrupt_not_incompatible(
    tmp_path: Path,
) -> None:
    path = tmp_path / "failures.parquet"
    path.write_bytes(b"PAR1truncated")
    with pytest.raises(ArtifactSchemaError) as captured:
        validate_artifact(path, ArtifactRegistry.load().get("failures"))
    assert not isinstance(captured.value, IncompatibleArtifactError)
