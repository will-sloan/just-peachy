from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import random

import pyarrow.parquet as pq
import pytest

from app.benchmark_contracts.canonical import (
    CanonicalizationError,
    canonical_json_bytes,
    canonical_sha256,
    normalize_project_relative_path,
    stable_rank,
)
from app.benchmark_contracts.manifest import (
    BenchmarkBuildError,
    selection_audit_row,
)
from app.benchmark_contracts.manifest_io import (
    ManifestValidationError,
    file_sha256,
    manifest_row,
    read_manifest,
    validate_manifest_rows,
    validate_manifest_table,
    write_manifest,
)
from app.benchmark_contracts.policy import (
    AugmentationPolicyError,
    augmentation_policy_for_record,
    validate_augmentation_request,
)
from app.benchmark_contracts.rir_registry import (
    RIRRegistry,
    RIRRegistryError,
    load_condition_sets,
)
from app.benchmark_contracts.scenario import (
    ScenarioValidationError,
    finalize_scenario,
    scenario_identity,
    scenario_identity_payload,
    validate_scenario,
)


TOOL_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = TOOL_ROOT.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "stage2"


def _json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _golden_rows() -> list[dict[str, object]]:
    specs = _json(FIXTURES / "golden_manifest_source.json")
    assert isinstance(specs, list)
    return [
        manifest_row(item["record"], **item["manifest"])
        for item in specs
    ]


def _scenario_source() -> dict[str, object]:
    value = _json(FIXTURES / "golden_scenario_source.json")
    assert isinstance(value, dict)
    return value


def _rehash_manifest_source(row: dict[str, object]) -> None:
    row["source_metadata_hash"] = canonical_sha256(
        {
            "dataset": row["dataset"],
            "recording_id": row["recording_id"],
            "source_recording_id": row["source_recording_id"],
            "utt_id": row["utt_id"],
            "source_utterance_id": row["source_utterance_id"],
            "audio_path_project_relative": row["audio_path_project_relative"],
            "start_sec": row["start_sec"],
            "end_sec": row["end_sec"],
            "reference_text": row["reference_text"],
            "speaker_id": row["speaker_id"],
        }
    )


def test_stable_selection_rank_does_not_depend_on_input_order() -> None:
    records = [
        {"recording": f"recording-{index}", "utt": f"utt-{index}"}
        for index in range(100)
    ]
    shuffled = records.copy()
    random.Random(99).shuffle(shuffled)

    def selected(values: list[dict[str, str]]) -> list[str]:
        return [
            item["recording"]
            for item in sorted(
                values,
                key=lambda item: stable_rank(
                    3800,
                    "fixture",
                    item["recording"],
                    item["utt"],
                ),
            )[:20]
        ]

    assert selected(records) == selected(shuffled)


def test_golden_manifest_is_byte_stable_and_valid(tmp_path: Path) -> None:
    regenerated = tmp_path / "golden_manifest.parquet"
    identity = write_manifest(regenerated, _golden_rows())
    golden = FIXTURES / "golden_manifest.parquet"

    assert regenerated.read_bytes() == golden.read_bytes()
    assert identity["sha256"] == (FIXTURES / "golden_manifest.sha256").read_text().strip()
    assert file_sha256(golden) == identity["sha256"]
    assert read_manifest(golden) == read_manifest(regenerated)


def test_golden_manifest_parquet_metadata_declares_public_contract() -> None:
    table = pq.read_table(FIXTURES / "golden_manifest.parquet")
    validate_manifest_table(table)
    metadata = table.schema.metadata or {}
    assert metadata[b"manifest_schema_version"] == b"benchmark-manifest.v1"
    assert metadata[b"authoritative_representation"] == b"parquet"


def test_golden_scenario_hash_and_canonical_bytes_are_reproducible() -> None:
    expected = _json(FIXTURES / "golden_scenario.json")
    scenario = finalize_scenario(_scenario_source())

    assert scenario == expected
    assert scenario["scenario_hash"] == (
        FIXTURES / "golden_scenario_hash.txt"
    ).read_text().strip()
    assert canonical_json_bytes(scenario_identity_payload(scenario)) + b"\n" == (
        FIXTURES / "golden_scenario_canonical.json"
    ).read_bytes()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("condition", "snr_db"), 5.0),
        (("resource_policy", "collect_gpu"), False),
        (("failure_policy", "max_item_retries"), 1),
    ],
)
def test_result_affecting_changes_create_new_scenario_ids(
    path: tuple[str, str],
    value: object,
) -> None:
    source = _scenario_source()
    original = scenario_identity(source)
    changed = deepcopy(source)
    changed[path[0]][path[1]] = value
    assert scenario_identity(changed) != original


def test_resolved_config_change_with_matching_hash_changes_scenario_id() -> None:
    source = _scenario_source()
    original = scenario_identity(source)
    changed = deepcopy(source)
    changed["pipeline"]["resolved_config_contents"]["runtime"]["num_threads"] = 2
    changed["runtime"]["settings"]["num_threads"] = 2
    changed["pipeline"]["resolved_config_sha256"] = canonical_sha256(
        changed["pipeline"]["resolved_config_contents"]
    )
    assert scenario_identity(changed) != original


def test_resolved_and_component_content_hash_mismatches_are_rejected() -> None:
    source = _scenario_source()
    source["pipeline"]["resolved_config_sha256"] = "1" * 64
    with pytest.raises(ScenarioValidationError, match="resolved config contents"):
        validate_scenario(source, require_identity=False)

    source = _scenario_source()
    source["pipeline"]["components"]["asr"]["config_contents_sha256"] = "2" * 64
    with pytest.raises(ScenarioValidationError, match="component asr contents"):
        validate_scenario(source, require_identity=False)


def test_machine_worker_output_and_retry_do_not_affect_scenario_id() -> None:
    source = _scenario_source()
    expected = scenario_identity(source)
    source.update(
        {
            "worker": "worker_friend",
            "machine": "gpu-24gb",
            "output_path": r"D:\different\output",
            "start_time": "2030-01-01T00:00:00Z",
            "retry_number": 7,
        }
    )
    assert scenario_identity(source) == expected


def test_collision_sanity_for_many_repetitions() -> None:
    source = _scenario_source()
    ids = set()
    for repetition in range(1, 501):
        source["repetition"] = repetition
        ids.add(scenario_identity(source)[1])
    assert len(ids) == 500


def test_windows_and_linux_relative_paths_normalize_identically() -> None:
    windows = (
        r"Raw Datasets (Not formatted)\MIT 271 RIRs\Audio\h025_Diningroom_8txts.wav"
    )
    posix = (
        "Raw Datasets (Not formatted)/MIT 271 RIRs/Audio/"
        "h025_Diningroom_8txts.wav"
    )
    assert normalize_project_relative_path(windows) == posix

    left = _scenario_source()
    right = deepcopy(left)
    left["condition"]["rir"]["relative_path"] = windows
    right["condition"]["rir"]["relative_path"] = posix
    assert scenario_identity(left) == scenario_identity(right)


@pytest.mark.parametrize(
    "path",
    [r"C:\absolute\file.wav", "/absolute/file.wav", "../outside.wav"],
)
def test_absolute_or_traversing_paths_are_rejected(path: str) -> None:
    with pytest.raises(CanonicalizationError):
        normalize_project_relative_path(path)


@pytest.mark.parametrize(
    ("panel", "dataset", "metadata", "expected"),
    [
        ("controlled_clean", "cmu_arctic", {}, "allow"),
        ("controlled_clean", "librispeech", {"split": "dev-clean", "subset_group": "clean"}, "allow"),
        ("controlled_clean", "librispeech", {"split": "dev-other", "subset_group": "other"}, "native_only"),
        ("controlled_clean", "hifitts", {"audio_quality": "clean"}, "allow"),
        ("controlled_clean", "hifitts", {"audio_quality": "other"}, "native_only"),
        ("native_robustness", "ami", {}, "native_only"),
        ("native_robustness", "voices", {}, "native_only"),
        ("native_robustness", "chime6", {}, "native_only"),
        ("controlled_clean", "cmu_arctic", {"native_reverberant": True}, "native_only"),
    ],
)
def test_augmentation_policy_is_derived_from_panel_dataset_and_metadata(
    panel: str,
    dataset: str,
    metadata: dict[str, object],
    expected: str,
) -> None:
    assert augmentation_policy_for_record(panel, dataset, metadata) == expected


def test_native_and_other_rows_reject_synthetic_augmentation() -> None:
    condition = {
        "id": "white_10db",
        "augmentation": "noise",
        "noise_type": "white",
        "snr_db": 10.0,
        "rir": None,
    }
    for record in (
        {"panel": "native_robustness", "dataset": "ami", "augmentation_policy": "native_only"},
        {
            "panel": "controlled_clean",
            "dataset": "librispeech",
            "split": "dev-other",
            "subset_group": "other",
            "augmentation_policy": "native_only",
        },
        {
            "panel": "controlled_clean",
            "dataset": "hifitts",
            "audio_quality": "other",
            "augmentation_policy": "native_only",
        },
    ):
        with pytest.raises(AugmentationPolicyError):
            validate_augmentation_request(record, condition)


def test_enrollment_probe_source_overlap_is_rejected() -> None:
    rows = _golden_rows()
    probe = next(row for row in rows if row["role"] == "known_probe")
    enrollment = next(row for row in rows if row["role"] == "enrollment")
    probe["source_utterance_id"] = enrollment["source_utterance_id"]
    probe["speaker_id"] = enrollment["speaker_id"]
    _rehash_manifest_source(probe)
    with pytest.raises(ManifestValidationError, match="overlap"):
        validate_manifest_rows(rows)


def test_rir_registry_resolves_exact_files_and_preserves_discrepancies() -> None:
    registry = RIRRegistry.load()
    audit = registry.audit(PROJECT_ROOT)
    by_id = {row["rir_id"]: row for row in audit["records"]}

    assert audit["collection_label_expected_wav_count"] == 271
    assert audit["collection_wav_count"] == 270
    assert "contains 270" in audit["collection_count_discrepancy_note"]
    assert by_id["dining_room_h025"]["identity_matches"] is True
    assert by_id["restaurant_h093"]["identity_matches"] is True
    assert by_id["kitchen_h044_unresolved"]["resolved_identifier"] is None
    assert by_id["parking_lot_h044"]["environment"] == "ParkingLot"
    assert by_id["parking_lot_h044"]["status"] == "excluded"
    assert len(audit["bedroom_candidates"]) == 11


def test_condition_sets_use_only_approved_exact_rirs() -> None:
    registry = RIRRegistry.load()
    condition_sets = load_condition_sets(registry)
    approved = {record.rir_id for record in registry.approved()}
    observed = {
        condition["rir"]["rir_id"]
        for conditions in condition_sets.values()
        for condition in conditions
        if condition["rir"] is not None
    }
    assert observed == approved == {"dining_room_h025", "restaurant_h093"}
    with pytest.raises(RIRRegistryError):
        registry.get("bedroom_unresolved").identity()


def test_null_and_absent_fields_are_distinct_and_required_condition_fields_cannot_be_absent() -> None:
    assert canonical_sha256({"value": None}) != canonical_sha256({})
    source = _scenario_source()
    del source["condition"]["snr_db"]
    with pytest.raises(ScenarioValidationError, match="explicitly include"):
        validate_scenario(source, require_identity=False)


def test_float_normalization_is_explicit_and_stable() -> None:
    assert canonical_json_bytes({"value": 1.0}) == b'{"value":1.0}'
    assert canonical_json_bytes({"value": -0.0}) == b'{"value":0.0}'
    assert canonical_json_bytes({"value": 1e-7}) == b'{"value":1.0e-7}'
    assert canonical_sha256({"value": 1}) != canonical_sha256({"value": 1.0})
    with pytest.raises(CanonicalizationError):
        canonical_json_bytes({"value": float("nan")})


def test_unknown_schema_and_hash_versions_are_rejected() -> None:
    rows = _golden_rows()
    rows[0]["manifest_schema_version"] = "benchmark-manifest.v2"
    with pytest.raises(ManifestValidationError, match="unsupported"):
        validate_manifest_rows(rows)

    source = _scenario_source()
    source["hash_version"] = "scenario-hash.v2"
    with pytest.raises(ScenarioValidationError, match="hash version"):
        validate_scenario(source, require_identity=False)


def test_every_shortfall_requires_a_reason() -> None:
    row = selection_audit_row(
        tier="small",
        panel="controlled_clean",
        dataset="hifitts",
        stratum="clean_readers",
        requested=50,
        realized=15,
        shortfall_reason="only three readers are labelled clean",
    )
    assert row["shortfall_count"] == 35
    assert row["shortfall_reason"]
    with pytest.raises(BenchmarkBuildError, match="requires a reason"):
        selection_audit_row(
            tier="small",
            panel="controlled_clean",
            dataset="hifitts",
            stratum="clean_readers",
            requested=50,
            realized=15,
            shortfall_reason=None,
        )


def test_golden_manifest_rows_reject_illegal_policy_and_missing_paths() -> None:
    rows = _golden_rows()
    native = next(row for row in rows if row["dataset"] == "ami")
    native["augmentation_policy"] = "allow"
    with pytest.raises(ManifestValidationError, match="policy"):
        validate_manifest_rows(rows)


def test_manifest_source_identity_tampering_is_rejected() -> None:
    rows = _golden_rows()
    rows[0]["reference_text"] = "tampered reference"
    with pytest.raises(ManifestValidationError, match="source metadata hash mismatch"):
        validate_manifest_rows(rows)


def test_stored_scenario_identity_is_validated() -> None:
    scenario = finalize_scenario(_scenario_source())
    validate_scenario(scenario)
    scenario["scenario_id"] = "scenario_000000000000"
    with pytest.raises(ScenarioValidationError, match="does not match"):
        validate_scenario(scenario)
