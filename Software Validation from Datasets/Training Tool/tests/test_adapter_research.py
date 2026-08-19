"""Bounded tests for the Original-only Phase-5 adapter control plane."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


TRAINING_TOOL = Path(__file__).resolve().parents[1]
REPOSITORY = TRAINING_TOOL.parents[1]
sys.path.insert(0, str(TRAINING_TOOL))

from training_data.adapter_research import (  # noqa: E402
    CHECKPOINT_SHA256,
    EXPERIMENTS,
    PHASE4_ID,
    PHASE4_SHA256,
    REQUIRED_STATUS_FIELDS,
    SAMPLER_SEED,
    SAMPLER_VERSION,
    SOURCE_FILES,
    TOKENIZER_SHA256,
    AdapterPaths,
    AdapterResearchError,
    _completed_run,
    _verify_identity,
    _wsl_path,
    canonical_sha256,
    derive_budget,
    deterministic_view_index,
    estimate,
    initial_status,
    load_frozen_configs,
    normalize_training_text,
    phase6_input_block,
    recipe_source_text,
    request_stop,
    stable_u64,
)
from training_data.common_voice import sha256_file  # noqa: E402


def _paths(tmp_path: Path) -> AdapterPaths:
    return AdapterPaths(
        REPOSITORY, REPOSITORY / "Software Validation from Datasets", tmp_path
    )


def test_wsl_path_normalizes_windows_backslashes(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if args[-3:] == ["test", "-x", "/usr/bin/wslpath"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        captured.extend(args)
        return subprocess.CompletedProcess(args, 0, "/mnt/c/work/queue.json\n", "")

    monkeypatch.setattr("training_data.adapter_research.subprocess.run", fake_run)
    assert _wsl_path(Path(r"C:\work\queue.json"), distro="TestDistro") == "/mnt/c/work/queue.json"
    assert captured == [
        "wsl.exe",
        "-d",
        "TestDistro",
        "--",
        "wslpath",
        "-u",
        "-a",
        "C:/work/queue.json",
    ]


def test_wsl_path_preserves_spaces_as_one_argument(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if args[-3:] == ["test", "-x", "/usr/bin/wslpath"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        captured.extend(args)
        return subprocess.CompletedProcess(args, 0, "/mnt/c/Training Tool/queue.json\n", "")

    monkeypatch.setattr("training_data.adapter_research.subprocess.run", fake_run)
    assert _wsl_path(Path(r"C:\Training Tool\queue.json"), distro="TestDistro") == (
        "/mnt/c/Training Tool/queue.json"
    )
    assert captured[-1] == "C:/Training Tool/queue.json"
    assert len(captured) == 8


def test_wsl_path_reports_conversion_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if args[-3:] == ["test", "-x", "/usr/bin/wslpath"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        raise subprocess.CalledProcessError(1, args, stderr="wslpath: bad path")

    monkeypatch.setattr("training_data.adapter_research.subprocess.run", fake_run)
    with pytest.raises(AdapterResearchError, match="wslpath: bad path"):
        _wsl_path(Path(r"C:\missing\queue.json"), distro="TestDistro")


def test_wsl_path_converts_current_queue_without_splitting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[list[str]] = []

    def fake_run(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if args[-3:] == ["test", "-x", "/usr/bin/wslpath"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        observed.append(args)
        return subprocess.CompletedProcess(args, 0, "/mnt/c/queue.json\n", "")

    monkeypatch.setattr("training_data.adapter_research.subprocess.run", fake_run)
    queue = (
        REPOSITORY
        / "training"
        / "successors"
        / "phase5a_original_adapter_training_v1"
        / "registries"
        / "original_adapter_queue.json"
    )
    assert _wsl_path(queue, distro="TestDistro") == "/mnt/c/queue.json"
    assert len(observed) == 1
    assert observed[0][-1].endswith(
        "training/successors/phase5a_original_adapter_training_v1/registries/original_adapter_queue.json"
    )


def test_phase4_parent_identity_is_frozen() -> None:
    assert PHASE4_ID == "training_manifest_freeze_phase4_cc2909f344d0"
    assert PHASE4_SHA256 == (
        "CC2909F344D01E9007EF648BA71277188DF26741CBEA5D1D2B0933116CE6DF92"
    )


def test_checkpoint_and_tokenizer_hashes_when_local_assets_are_present() -> None:
    root = REPOSITORY / "models" / "Original Trainable Checkpoint"
    if not root.is_dir():
        pytest.skip("machine-local Phase-5 initialization cache is absent")
    assert sha256_file(root / "pretrained.pt") == CHECKPOINT_SHA256
    assert sha256_file(root / "bpe.model") == TOKENIZER_SHA256


def test_frozen_configuration_documents_self_verify() -> None:
    configs = load_frozen_configs(
        AdapterPaths(
            REPOSITORY,
            REPOSITORY / "Software Validation from Datasets",
            REPOSITORY / "training",
        )
    )
    assert configs["recipe"]["implementation"]["adapter_dim"] == 16
    assert configs["recipe"]["optimization"]["precision"] == "fp16"
    assert configs["environment"]["icefall_commit"].startswith("3f848bb6")
    assert configs["provenance"]["baseline_continuity"] == (
        "strong_lineage_requires_reconstructed_baseline"
    )


def test_identity_verifier_rejects_mutation(tmp_path: Path) -> None:
    payload = {"schema_version": "fixture.v1", "value": 1}
    digest = canonical_sha256(payload)
    path = tmp_path / "identity.json"
    path.write_text(
        json.dumps(
            {
                **payload,
                "thing_id": f"fixture_{digest[:12].lower()}",
                "thing_sha256": digest,
            }
        ),
        encoding="utf-8",
    )
    _verify_identity(path, id_key="thing_id", sha_key="thing_sha256", prefix="fixture")
    changed = json.loads(path.read_text(encoding="utf-8"))
    changed["value"] = 2
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(Exception, match="Identity verification failed"):
        _verify_identity(
            path, id_key="thing_id", sha_key="thing_sha256", prefix="fixture"
        )


def test_training_text_normalization_is_deterministic_and_bpe_safe() -> None:
    assert normalize_training_text("T_F_I_D_F_ – déjà vu [laughs]") == (
        "T F I D F DEJA VU LAUGHS"
    )
    assert normalize_training_text("...") == ""
    assert normalize_training_text("King’s") == "KINGS"


def test_common_voice_embedded_tsv_tail_is_audibly_repaired() -> None:
    text, correction = recipe_source_text(
        "Their relationship is intense.\t\t2\tmale\nsha256-tail", "common_voice"
    )
    assert text == "Their relationship is intense."
    assert correction == "common_voice_embedded_tsv_tail_removed"
    untouched, correction = recipe_source_text("ordinary transcript", "ami")
    assert untouched == "ordinary transcript"
    assert correction is None


def test_sampler_rank_is_cross_call_deterministic() -> None:
    assert stable_u64("bundle", 42) == stable_u64("bundle", 42)
    assert stable_u64("bundle", 42) != stable_u64("bundle", 43)
    assert SAMPLER_VERSION == "dataset_group_source_rotating_view.v1"


def test_ami_and_voices_view_rotation_is_deterministic() -> None:
    first = deterministic_view_index("bundle", 3, "source", 9)
    assert first == deterministic_view_index("bundle", 3, "source", 9)
    assert 0 <= first < 9
    assert (
        len(
            {
                deterministic_view_index("bundle", epoch, "source", 9)
                for epoch in range(40)
            }
        )
        > 1
    )


def test_view_rotation_rejects_bad_bounds() -> None:
    with pytest.raises(ValueError):
        deterministic_view_index("bundle", -1, "source", 9)
    with pytest.raises(ValueError):
        deterministic_view_index("bundle", 0, "source", 0)


def test_source_mapping_uses_only_phase4_sources() -> None:
    assert set(SOURCE_FILES) == {
        "common_voice",
        "ami",
        "chime6",
        "voices",
        "cmu_arctic",
    }
    assert "gigaspeech" not in SOURCE_FILES
    assert "librispeech" not in SOURCE_FILES


def test_budget_rule_is_deterministic_and_bounded() -> None:
    bundle = {
        "train_sources": [
            {"dataset_id": "common_voice", "probability": "0.75"},
            {"dataset_id": "voices", "probability": "0.25"},
        ]
    }
    sidecars = {
        "train:common_voice": {"effective_unique_audio_hours": 100.0},
        "train:voices": {"effective_unique_audio_hours": 4.0},
    }
    policy = {
        "source_passes": 4,
        "effective_audio_seconds_per_optimizer_step": 90,
        "minimum_optimizer_steps": 1500,
        "maximum_optimizer_steps": 20000,
    }
    first = derive_budget(bundle, sidecars, policy)
    assert first == derive_budget(bundle, sidecars, policy)
    assert first[0] == 12160
    assert first[1] == 76.0


def test_budget_rule_protects_tiny_and_large_bundles() -> None:
    policy = {
        "source_passes": 4,
        "effective_audio_seconds_per_optimizer_step": 90,
        "minimum_optimizer_steps": 1500,
        "maximum_optimizer_steps": 20000,
    }
    tiny = {"train_sources": [{"dataset_id": "cmu_arctic", "probability": "1"}]}
    huge = {"train_sources": [{"dataset_id": "ami", "probability": "1"}]}
    assert (
        derive_budget(
            tiny, {"train:cmu_arctic": {"effective_unique_audio_hours": 1}}, policy
        )[0]
        == 1500
    )
    assert (
        derive_budget(
            huge, {"train:ami": {"effective_unique_audio_hours": 1000}}, policy
        )[0]
        == 20000
    )


def test_queue_spec_is_exactly_eight_original_jobs_in_order() -> None:
    ids = [item[0] for item in EXPERIMENTS]
    assert ids == [
        "O-AGE",
        "O-AMI",
        "O-CHIME",
        "O-VOICES",
        "O-ROBUST",
        "O-AGE-ROBUST",
        "O-CMU",
        "O-AGE-ROBUST-CMU",
    ]
    assert all(value.startswith("O-") for value in ids)


def test_queue_classes_and_chime_release_gates() -> None:
    by_id = {item[0]: item for item in EXPERIMENTS}
    assert by_id["O-CMU"][2] == "exploratory"
    assert by_id["O-AGE-ROBUST-CMU"][2] == "exploratory"
    assert by_id["O-CHIME"][3]
    assert by_id["O-ROBUST"][3]
    assert by_id["O-AGE-ROBUST"][3]
    assert by_id["O-AGE-ROBUST-CMU"][3]


def test_initial_status_has_complete_progress_and_eta_schema() -> None:
    value = initial_status({"queue_id": "adapter_queue_fixture"})
    assert set(value) == REQUIRED_STATUS_FIELDS
    assert value["TOTAL_EXPERIMENTS"] == 8
    assert value["MODEL_ETA_SECONDS"] is None
    assert value["QUEUE_ETA_SECONDS"] is None


def test_stop_request_is_restart_safe_metadata(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    payload = request_stop(paths, "test stop")
    assert paths.stop_path.is_file()
    assert json.loads(paths.stop_path.read_text())["reason"] == "test stop"
    assert payload["reason"] == "test stop"


def test_successful_queue_job_is_skippable(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    job = {"run_id": "run-fixture"}
    result = paths.runs / "run-fixture" / "result.json"
    result.parent.mkdir(parents=True)
    result.write_text(
        json.dumps({"STATE": "completed", "EXPORT_READY": True}), encoding="utf-8"
    )
    assert _completed_run(paths, job)
    result.write_text(
        json.dumps({"STATE": "failed", "EXPORT_READY": False}), encoding="utf-8"
    )
    assert not _completed_run(paths, job)


def test_eta_is_not_fabricated_without_canaries(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    queue = {
        "queue_id": "adapter_queue_fixture",
        "jobs": [
            {
                "experiment_id": "O-AGE",
                "derived_training_budget_optimizer_steps": 100,
            }
        ],
    }
    paths.queue_path.parent.mkdir(parents=True)
    paths.queue_path.write_text(json.dumps(queue), encoding="utf-8")
    value = estimate(paths)
    assert not value["CALIBRATED"]
    assert value["ESTIMATED_TOTAL_QUEUE_TIME_SECONDS"] is None


def test_eta_uses_measured_canary_throughput(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    queue = {
        "queue_id": "adapter_queue_fixture",
        "jobs": [
            {
                "experiment_id": "O-AGE",
                "derived_training_budget_optimizer_steps": 100,
            }
        ],
    }
    paths.queue_path.parent.mkdir(parents=True)
    paths.queue_path.write_text(json.dumps(queue), encoding="utf-8")
    summary = {
        "ready_to_run_original_adapter_queue": True,
        "canaries": [
            {"passed": True, "seconds_per_optimizer_step": 2.0},
            {"passed": True, "seconds_per_optimizer_step": 4.0},
        ],
    }
    paths.qualification.mkdir(parents=True)
    (paths.qualification / "canary_summary.json").write_text(
        json.dumps(summary), encoding="utf-8"
    )
    value = estimate(paths)
    assert value["CALIBRATED"]
    assert value["MEASURED_SECONDS_PER_STEP"] == 3.0
    assert value["ESTIMATED_TOTAL_QUEUE_TIME_SECONDS"] == 300.0


def test_phase6_input_block_uses_exact_yes_no_handoff_values() -> None:
    completion = {
        key: "fixture"
        for key in (
            "PARENT_PHASE4_FREEZE_ID",
            "PARENT_PHASE4_FREEZE_SHA256",
            "PHASE5_TRAINING_SYSTEM_COMMIT",
            "ORIGINAL_BASELINE_CONTINUITY",
            "ORIGINAL_TRAINABLE_CHECKPOINT_ID",
            "ORIGINAL_TRAINABLE_CHECKPOINT_PATH",
            "ORIGINAL_TRAINABLE_CHECKPOINT_SHA256",
            "TOKENIZER_ID",
            "TOKENIZER_PATH",
            "TOKENIZER_SHA256",
            "ICEFALL_COMMIT",
            "ADAPTER_IMPLEMENTATION_ID",
            "ADAPTER_TRAINING_RECIPE_ID",
            "ORIGINAL_ADAPTER_QUEUE_ID",
            "ORIGINAL_ADAPTER_QUEUE_SHA256",
            "GIGA_FUTURE_OPTION",
            "CURRENT_GIT_COMMIT",
            "CURRENT_BRANCH",
        )
    }
    completion.update(
        {
            "RECONSTRUCTED_ORIGINAL_BASELINE_EXPORT_REQUIRED": True,
            "SUCCESSFUL_EXPERIMENT_IDS": ["O-AGE"],
            "FAILED_OR_INCOMPLETE_EXPERIMENTS": [],
            "GIGA_ADAPTATION_ATTEMPTED": False,
            "ONNX_EXPORTED": False,
            "LARGE_CAMPAIGN_CREATED": False,
            "COMMON_VOICE_HELDOUT_EVALUATED": False,
            "experiments": [
                {
                    "EXPERIMENT_ID": "O-AGE",
                    "BEST_CHECKPOINT_ID": "checkpoint",
                    "BEST_CHECKPOINT_PATH": "JP_TRAINING_ROOT:runs/checkpoint.pt",
                    "BEST_CHECKPOINT_SHA256": "A" * 64,
                    "BEST_CHECKPOINT_STEP": 10,
                    "BUNDLE_ID": "bundle",
                    "CMU_EXPERIMENT_CLASS": "strict",
                    "COMMERCIAL_MODEL_RELEASE_REVIEW_REQUIRED": False,
                    "EXPORT_READY": True,
                }
            ],
        }
    )
    block = phase6_input_block(completion)
    assert "RECONSTRUCTED_ORIGINAL_BASELINE_EXPORT_REQUIRED = YES" in block
    assert "EXPORT_READY = YES" in block
    assert "GIGA_ADAPTATION_ATTEMPTED = NO" in block
    assert "FAILED_OR_INCOMPLETE_EXPERIMENTS = NONE" in block


def test_powershell_front_door_has_every_required_action() -> None:
    source = (TRAINING_TOOL / "scripts" / "run_adapter_research.ps1").read_text(
        encoding="utf-8"
    )
    for action in (
        "Plan",
        "Estimate",
        "Run",
        "RunOne",
        "Status",
        "Watch",
        "Stop",
        "Resume",
        "Validate",
        "Results",
    ):
        assert f"'{action}'" in source
    assert "wsl.exe" not in source


def test_runtime_has_no_large_or_giga_training_surface() -> None:
    source = (TRAINING_TOOL / "training_data" / "adapter_runtime.py").read_text(
        encoding="utf-8"
    )
    assert "GigaSpeech" not in source
    assert "gigaspeech" not in source.lower()
    assert "large_source_manifest" not in source
    # Result evidence may name the forbidden panel while proving it was not used;
    # the runtime itself must never reference an executable heldout manifest.
    assert "common_voice_older_heldout" not in source
    assert "heldout.parquet" not in source


def test_live_materialized_queue_and_manifest_audit_when_present() -> None:
    root = (
        REPOSITORY / "training" / "successors" / "phase5_original_adapter_training_v1"
    )
    queue_path = root / "registries" / "original_adapter_queue.json"
    audit_path = root / "audits" / "framework_manifest_audit.json"
    if not queue_path.is_file() or not audit_path.is_file():
        pytest.skip("machine-local Phase-5 materialization is absent")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert queue["total_jobs"] == 8
    assert queue["giga_jobs"] == 0
    assert [item["experiment_id"] for item in queue["jobs"]] == [
        item[0] for item in EXPERIMENTS
    ]
    chime_jobs = {
        "O-CHIME",
        "O-ROBUST",
        "O-AGE-ROBUST",
        "O-AGE-ROBUST-CMU",
    }
    for job in queue["jobs"]:
        expected = job["experiment_id"] in chime_jobs
        assert job["chime_used_in_training"] is expected
        assert job["commercial_model_release_review_required"] is expected
    assert (
        canonical_sha256(
            {k: v for k, v in queue.items() if k not in {"queue_id", "queue_sha256"}}
        )
        == queue["queue_sha256"]
    )
    assert audit["all_memberships_preserved"]
    assert audit["total_missing_audio"] == 0
    assert audit["total_invalid_segments"] == 0
    assert audit["total_tokenization_failures"] == 0
    assert audit["total_unknown_token_occurrences"] == 0
    assert audit["total_transcript_repairs"] == 2
    assert not audit["common_voice_heldout_included"]
    assert not audit["large_accessed"]
    assert audit["manifests"]["train:common_voice"]["maximum_bpe_tokens"] <= 100
    for manifest in audit["manifests"].values():
        assert manifest["source_manifest_id"]
        assert manifest["bundle_bindings"]
        assert manifest["sampler_policy_id"] == SAMPLER_VERSION
        assert manifest["sampler_seed"] == SAMPLER_SEED
    for name in ("chime_train.parquet", "cmu_relaxed_exploratory_train.parquet"):
        columns = [
            "source_registry_row_id",
            "license_id",
            "commercial_training_status",
            "commercial_release_review_status",
            "attribution_required",
            "sharealike_flag",
        ]
        source = pd.read_parquet(
            REPOSITORY
            / "training"
            / "successors"
            / "phase4_training_manifests_v1"
            / "source_manifests"
            / name,
            columns=columns,
        ).sort_values("source_registry_row_id")
        derived = pd.read_parquet(
            root / "framework_manifests" / "train" / name,
            columns=columns,
        ).sort_values("source_registry_row_id")
        pd.testing.assert_frame_equal(
            source.reset_index(drop=True), derived.reset_index(drop=True)
        )
    derived_columns = pd.read_parquet(
        root / "framework_manifests" / "train" / "age_train.parquet"
    ).columns
    assert "resolved_audio_path" not in derived_columns
    assert "bpe_token_count" in derived_columns
    assert "model_input_duration_seconds" in derived_columns


def test_scientific_run_identities_are_portable_when_materialized() -> None:
    queue_path = (
        REPOSITORY
        / "training"
        / "successors"
        / "phase5_original_adapter_training_v1"
        / "registries"
        / "original_adapter_queue.json"
    )
    if not queue_path.is_file():
        pytest.skip("machine-local Phase-5 materialization is absent")
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    for job in queue["jobs"]:
        encoded = json.dumps(job["run_identity"])
        assert "C:\\" not in encoded
        assert "/mnt/" not in encoded
        assert "timestamp" not in encoded.lower()
        assert "gpu serial" not in encoded.lower()
