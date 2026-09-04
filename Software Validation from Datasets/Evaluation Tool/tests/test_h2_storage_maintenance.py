from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from scripts.augment_h2_final_package import (
    ARM64_REQUIREMENTS_MEMBER,
    ATTEMPT_HISTORY_FIELDS,
    REQUIRED_STORAGE_MEMBERS,
    RUNTIME_IDENTITY_MEMBER,
    STORAGE_ARM64_WHEEL_RECEIPT_MEMBER,
    STORAGE_ATOMIC_BOOTSTRAP_MEMBER,
    STORAGE_ATOMIC_CHILD_MEMBER,
    STORAGE_ATOMIC_EVENTS_MEMBER,
    STORAGE_ATOMIC_POLICY_MEMBER,
    STORAGE_ATTEMPT_HISTORY_MEMBER,
    STORAGE_PRUNE_PREFIX,
    _augmentation_source_payloads,
    _canonical_json,
    _csv_payload,
    _sha256,
    _storage_reproducibility_payloads,
    _validated_h2_v17_task_registration,
    _validate_augmentation_source_members,
    _validate_storage_reproducibility_members,
)

from scripts.maintain_h2_storage import (
    FORECAST_SCHEMA,
    GuardianLock,
    RECEIPT_SCHEMA,
    StorageSafetyError,
    _capacity_state,
    _compression_policy_decision,
    _guardian_sleep_interval,
    _is_relative_to,
    _projection_rates,
    _should_scan_live_inventory,
    _sign_document,
    _validate_signed_document,
)


def test_capacity_state_reserves_largest_job_before_classifying_risk() -> None:
    state = _capacity_state(
        free_gib=100.0,
        minimum_free_gib=35.0,
        target_free_gib=80.0,
        estimated_peak_gib=15.0,
    )
    assert state["risk"] == "OK"
    assert state["projected_free_after_largest_job_gib"] == 85.0
    assert state["controller_stop_expected_from_h2_growth"] is False


def test_capacity_state_calls_for_early_reclaim_before_hard_reserve() -> None:
    state = _capacity_state(
        free_gib=70.0,
        minimum_free_gib=35.0,
        target_free_gib=80.0,
        estimated_peak_gib=10.0,
    )
    assert state["risk"] == "EARLY_RECLAIM"
    assert state["reclaim_to_guardian_target_gib"] == 20.0
    assert state["controller_stop_expected_from_h2_growth"] is False


def test_compression_policy_allows_only_at_risk_long_session_accuracy() -> None:
    allowed, reason = _compression_policy_decision(
        job_kind="long_session_evaluation",
        measurement_mode="accuracy",
        capacity_risk="EARLY_RECLAIM",
    )
    assert allowed is True
    assert "capacity risk" in reason


@pytest.mark.parametrize("job_kind", ["long_session", "long_session_evaluation"])
def test_compression_policy_excludes_serial_resource_measurements(
    job_kind: str,
) -> None:
    allowed, reason = _compression_policy_decision(
        job_kind=job_kind,
        measurement_mode="resources",
        capacity_risk="CRITICAL_RECLAIM",
    )
    assert allowed is False
    assert "resource" in reason


def test_compression_policy_does_not_touch_ordinary_accuracy_jobs() -> None:
    allowed, _ = _compression_policy_decision(
        job_kind="runtime_accuracy",
        measurement_mode="accuracy",
        capacity_risk="CRITICAL_RECLAIM",
    )
    assert allowed is False


def test_compression_policy_waits_when_forecast_is_safe() -> None:
    allowed, _ = _compression_policy_decision(
        job_kind="long_session",
        measurement_mode="accuracy",
        capacity_risk="OK",
    )
    assert allowed is False


def test_projection_rates_prefer_complete_receipts_over_short_partial_outlier() -> None:
    per_audio, per_case, basis = _projection_rates(
        sealed_observations=[(10_000, 10, 100.0)],
        live_observations=[(3_000_000, 1, 1.0)],
    )
    assert per_audio == 100.0
    assert per_case == 1_000.0
    assert basis == "sealed_complete_job_receipts"


def test_projection_rates_use_live_data_before_first_seal() -> None:
    per_audio, per_case, basis = _projection_rates(
        sealed_observations=[],
        live_observations=[(3_000, 2, 10.0)],
    )
    assert per_audio == 300.0
    assert per_case == 1_500.0
    assert basis == "partial_live_fallback_no_sealed_receipts"


def test_live_inventory_is_used_before_first_sealed_receipt() -> None:
    assert _should_scan_live_inventory([]) is True


def test_live_inventory_is_skipped_after_sealed_projection_basis() -> None:
    assert _should_scan_live_inventory([(10_000, 10, 100.0)]) is False


def test_guardian_uses_requested_cadence_while_capacity_is_safe() -> None:
    assert _guardian_sleep_interval(300.0, "OK") == 300.0


@pytest.mark.parametrize("risk", ["EARLY_RECLAIM", "CRITICAL_RECLAIM"])
def test_guardian_polls_at_most_minutely_when_capacity_is_at_risk(risk: str) -> None:
    assert _guardian_sleep_interval(300.0, risk) == 60.0


def test_signed_storage_receipt_detects_tampering() -> None:
    receipt = _sign_document(
        {"schema_version": RECEIPT_SCHEMA, "status": "complete"},
        signature_key="receipt_sha256",
    )
    _validate_signed_document(
        receipt, signature_key="receipt_sha256", schema_version=RECEIPT_SCHEMA
    )
    receipt["status"] = "changed"
    with pytest.raises(StorageSafetyError, match="checksum differs"):
        _validate_signed_document(
            receipt,
            signature_key="receipt_sha256",
            schema_version=RECEIPT_SCHEMA,
        )


def test_signed_storage_receipt_rejects_wrong_schema() -> None:
    receipt = _sign_document(
        {"schema_version": FORECAST_SCHEMA, "status": "complete"},
        signature_key="receipt_sha256",
    )
    with pytest.raises(StorageSafetyError, match="invalid receipt schema"):
        _validate_signed_document(
            receipt,
            signature_key="receipt_sha256",
            schema_version=RECEIPT_SCHEMA,
        )


def test_path_containment_rejects_sibling_prefix(tmp_path: Path) -> None:
    parent = tmp_path / "campaign"
    sibling = tmp_path / "campaign-other" / "case_shards_v1"
    parent.mkdir()
    sibling.mkdir(parents=True)
    assert not _is_relative_to(sibling.resolve(), parent.resolve())


def test_guardian_lock_excludes_a_second_instance(tmp_path: Path) -> None:
    lock_path = tmp_path / "guardian.lock"
    with GuardianLock(lock_path):
        with pytest.raises(OSError):
            with GuardianLock(lock_path):
                raise AssertionError("a second guardian unexpectedly acquired the lock")


def _arm64_wheel_receipt_fixture(
    *, requirements_payload: bytes, runtime_identity_sha256: str, protocol_id: str
) -> dict[str, object]:
    direct_count = len(
        [
            line
            for line in requirements_payload.decode("utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
    )
    wheels = [
        {
            "filename": f"fixture_{index:02d}-1.0-py3-none-any.whl",
            "sha256": f"{index:064x}",
            "bytes": 100 + index,
        }
        for index in range(1, direct_count + 1)
    ]
    logical_bytes = sum(int(row["bytes"]) for row in wheels)
    return _sign_document(
        {
            "schema_version": "h2-arm64-wheel-resolution-receipt.v1",
            "status": "PASS_RESOLVED_EXACT_ARM64_BINARY_SET",
            "protocol_id": protocol_id,
            "runtime_implementation_sha256": runtime_identity_sha256,
            "scientific_runtime_or_configuration_edited": False,
            "source": {
                "requirements_path": (
                    "deployment/h2_arm64/requirements-linux-arm64.txt"
                ),
                "requirements_sha256": _sha256(requirements_payload),
                "index_url": "https://pypi.org/simple",
            },
            "target": {
                "operating_system": "Linux",
                "architecture": "aarch64",
                "python_version": "3.12",
                "implementation": "cp",
                "abis": ["cp312", "abi3", "none"],
                "platform_tags": [
                    "manylinux_2_28_aarch64",
                    "manylinux2014_aarch64",
                    "manylinux_2_17_aarch64",
                    "any",
                ],
                "binary_only": True,
            },
            "resolution": {
                "direct_pin_count": direct_count,
                "resolved_wheel_count": len(wheels),
                "resolved_logical_bytes": logical_bytes,
                "all_direct_and_transitive_dependencies_resolved": True,
                "source_distributions_used": False,
                "model_assets_downloaded": False,
                "wheels_retained_after_audit": False,
            },
            "wheels": wheels,
            "qualification_boundary": {
                "wheel_availability_and_target_tag_resolution": "PASS",
                "arm64_import_and_dynamic_link_validation": (
                    "NOT_RUN_REQUIRES_ARM64_LINUX"
                ),
                "arm64_numerical_parity": "NOT_RUN_REQUIRES_ARM64_LINUX",
                "raspberry_pi_hardware_ready_claimed": False,
                "candidate_classification": "PORT_REQUIRES_WORK",
            },
        },
        signature_key="receipt_sha256",
    )


def _valid_packaged_storage_members() -> dict[str, bytes]:
    terminal = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
    state_binding = {
        "program_id": "program",
        "protocol_id": "protocol",
        "protocol_sha256": "protocol-sha",
        "job_manifest_sha256": "manifest-sha",
        "workspace": "C:/fixture/workspace",
        "results_root": "C:/fixture/results",
        "summary_root": "C:/fixture/summary",
    }
    native_state = {**state_binding, "status": "RUNNING"}
    terminal_state = {**state_binding, "status": terminal}
    lifecycle = _sign_document(
        {
            "schema_version": "h2-storage-artifact-lifecycle.v1",
            "campaign_status": terminal,
        },
        signature_key="lifecycle_sha256",
    )
    forecast = {
        "schema_version": "h2-storage-forecast.v1",
        "program_status": terminal,
    }
    guardian = {
        "schema_version": "h2-storage-guardian-pass.v1",
        "forecast": forecast,
        "artifact_lifecycle_sha256": lifecycle["lifecycle_sha256"],
    }
    pending = _sign_document(
        {
            "schema_version": "h2-storage-prune-pending.v1",
            "regenerable_source": {"logical_bytes": 1234},
        },
        signature_key="pending_sha256",
    )
    receipt = _sign_document(
        {
            "schema_version": "h2-storage-prune-receipt.v1",
            "status": "PRUNED_REGENERABLE_CASE_SHARDS",
            "validation_receipt": pending,
        },
        signature_key="receipt_sha256",
    )
    requirements_payload = b"fixture==1.0\n"
    runtime_identity = {
        "schema_version": "h2-runtime-implementation-identity.v2",
        "identity_sha256": "b" * 64,
    }
    arm64_wheel_receipt = _arm64_wheel_receipt_fixture(
        requirements_payload=requirements_payload,
        runtime_identity_sha256=str(runtime_identity["identity_sha256"]),
        protocol_id=str(state_binding["protocol_id"]),
    )
    atomic_bootstrap_payload = b"bootstrap\n"
    atomic_child_payload = b"child-policy\n"
    atomic_events_payload = b""
    atomic_policy = _sign_document(
        {
            "schema_version": "h2-windows-atomic-publication-policy.v1",
            "launcher_sha256": _sha256(atomic_bootstrap_payload),
            "child_process_propagation": "PYTHONPATH_sitecustomize",
            "child_sitecustomize_sha256": _sha256(atomic_child_payload),
            "retryable_winerrors": [5, 32, 33],
            "retry_delays_sec": [0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 2.0, 2.0],
            "maximum_added_wait_sec": 7.15,
            "operation_scope": "os.replace only",
            "scientific_inference_or_metric_change": False,
            "frozen_runtime_source_tree_change": False,
        },
        signature_key="policy_sha256",
    )
    payloads = {
        **{name: b"support\n" for name in REQUIRED_STORAGE_MEMBERS[4:-2]},
        REQUIRED_STORAGE_MEMBERS[0]: _canonical_json(lifecycle),
        REQUIRED_STORAGE_MEMBERS[1]: _canonical_json(forecast),
        REQUIRED_STORAGE_MEMBERS[2]: _canonical_json(guardian),
        STORAGE_ARM64_WHEEL_RECEIPT_MEMBER: _canonical_json(arm64_wheel_receipt),
        STORAGE_ATOMIC_POLICY_MEMBER: _canonical_json(atomic_policy),
        STORAGE_ATOMIC_EVENTS_MEMBER: atomic_events_payload,
        STORAGE_ATOMIC_BOOTSTRAP_MEMBER: atomic_bootstrap_payload,
        STORAGE_ATOMIC_CHILD_MEMBER: atomic_child_payload,
        REQUIRED_STORAGE_MEMBERS[-2]: _canonical_json(terminal_state),
        f"{STORAGE_PRUNE_PREFIX}one.json": _canonical_json(receipt),
        "controller/program_state.json": _canonical_json(native_state),
        ARM64_REQUIREMENTS_MEMBER: requirements_payload,
        RUNTIME_IDENTITY_MEMBER: _canonical_json(runtime_identity),
    }
    attempt_database_sha256 = "queue-database-sha256"
    attempt_payload = _csv_payload(
        [
            {
                "schema_version": "h2-queue-attempt-history-row.v1",
                "queue_database_relative_path": "campaign.sqlite3",
                "queue_database_sha256": attempt_database_sha256,
                "job_id": "job_fixed",
                "attempt_number": 1,
                "attempt_state": "complete",
                "final_job_state": "complete",
                "recovered_after_attempt": False,
                "attempt_path_relative": "attempts/job_fixed/attempt_001",
                "started_at_utc": "2026-08-01T00:00:00Z",
                "ended_at_utc": "2026-08-01T00:01:00Z",
                "error": "",
            }
        ],
        ATTEMPT_HISTORY_FIELDS,
    )
    payloads[STORAGE_ATTEMPT_HISTORY_MEMBER] = attempt_payload
    provenance = {
        "schema_version": "h2-storage-reproducibility-provenance.v1",
        "status": "VALID",
        "controller_status": terminal,
        "native_packaged_controller_status": "RUNNING",
        "native_packaged_controller_state_sha256": _sha256(
            payloads["controller/program_state.json"]
        ),
        "terminal_controller_state_member": REQUIRED_STORAGE_MEMBERS[-2],
        "terminal_controller_state_sha256": _sha256(
            payloads[REQUIRED_STORAGE_MEMBERS[-2]]
        ),
        "controller_state_transition_preserved": True,
        "snapshot_after_terminal_guardian_pass": True,
        "artifact_lifecycle_sha256": lifecycle["lifecycle_sha256"],
        "storage_forecast_sha256": _sha256(payloads[REQUIRED_STORAGE_MEMBERS[1]]),
        "last_guardian_pass_sha256": _sha256(payloads[REQUIRED_STORAGE_MEMBERS[2]]),
        "arm64_wheel_resolution_member": STORAGE_ARM64_WHEEL_RECEIPT_MEMBER,
        "arm64_wheel_resolution_receipt_sha256": arm64_wheel_receipt[
            "receipt_sha256"
        ],
        "arm64_resolved_wheel_count": 1,
        "arm64_resolved_wheel_logical_bytes": arm64_wheel_receipt["resolution"][
            "resolved_logical_bytes"
        ],
        "arm64_wheel_payloads_embedded": False,
        "windows_atomic_publication_policy_member": STORAGE_ATOMIC_POLICY_MEMBER,
        "windows_atomic_publication_policy_sha256": atomic_policy["policy_sha256"],
        "windows_atomic_child_policy_member": STORAGE_ATOMIC_CHILD_MEMBER,
        "windows_atomic_child_policy_sha256": _sha256(atomic_child_payload),
        "windows_atomic_publication_events_member": STORAGE_ATOMIC_EVENTS_MEMBER,
        "windows_atomic_publication_events_sha256": _sha256(
            atomic_events_payload
        ),
        "scheduled_task_registration_member": None,
        "scheduled_task_registration_sha256": None,
        "scheduled_task_count": 0,
        "superseded_v16_task_count_disabled": 0,
        "event_count": 0,
        "retrying_count": 0,
        "recovered_count": 0,
        "exhausted_count": 0,
        "prune_receipt_count": 1,
        "compression_receipt_count": 0,
        "dynamic_execution_manifest_count": 0,
        "queue_database_count": 1,
        "queue_attempt_history_member": STORAGE_ATTEMPT_HISTORY_MEMBER,
        "queue_attempt_history_sha256": _sha256(attempt_payload),
        "queue_attempt_history_row_count": 1,
        "noncomplete_attempt_count": 0,
        "recovered_noncomplete_attempt_count": 0,
        "queue_databases": [
            {
                "relative_path": "campaign.sqlite3",
                "sha256": attempt_database_sha256,
                "attempt_count": 1,
                "noncomplete_attempt_count": 0,
                "recovered_noncomplete_attempt_count": 0,
            }
        ],
        "pruned_logical_bytes": 1234,
        "scientific_runtime_or_policy_changed": False,
        "removed_restart_payloads_embedded": False,
        "raw_audio_model_weights_and_biometric_caches_embedded": False,
        "source_members": [
            {"member": name, "sha256": _sha256(payload), "bytes": len(payload)}
            for name, payload in sorted(payloads.items())
            if name.startswith("reproducibility/storage/")
        ],
    }
    payloads[REQUIRED_STORAGE_MEMBERS[-1]] = _canonical_json(provenance)
    return payloads


def test_final_package_storage_snapshot_validates_signed_reproduction_map() -> None:
    provenance = _validate_storage_reproducibility_members(
        _valid_packaged_storage_members()
    )
    assert provenance["prune_receipt_count"] == 1
    assert provenance["pruned_logical_bytes"] == 1234


def test_final_package_storage_snapshot_rejects_tampered_receipt() -> None:
    payloads = _valid_packaged_storage_members()
    receipt_name = next(
        name for name in payloads if name.startswith(STORAGE_PRUNE_PREFIX)
    )
    receipt = json.loads(payloads[receipt_name])
    receipt["status"] = "TAMPERED"
    payloads[receipt_name] = _canonical_json(receipt)
    with pytest.raises(ValueError, match="signature differs"):
        _validate_storage_reproducibility_members(payloads)


def test_final_package_rejects_tampered_arm64_wheel_map() -> None:
    payloads = _valid_packaged_storage_members()
    receipt = json.loads(payloads[STORAGE_ARM64_WHEEL_RECEIPT_MEMBER])
    receipt["wheels"][0]["sha256"] = "0" * 64
    payloads[STORAGE_ARM64_WHEEL_RECEIPT_MEMBER] = _canonical_json(receipt)
    with pytest.raises(ValueError, match="signature differs"):
        _validate_storage_reproducibility_members(payloads)


def test_final_package_builder_copies_terminal_reproduction_evidence(
    tmp_path: Path,
) -> None:
    terminal = "COMPLETE_H2_PRODUCT_PIPELINE_PROGRAM"
    workspace = (tmp_path / "workspace").resolve()
    maintenance = workspace / "storage_maintenance"
    receipts = maintenance / "receipts"
    receipts.mkdir(parents=True)
    results = (tmp_path / "results").resolve()
    results.mkdir()
    job = {
        "job_id": "job_fixed",
        "identity_sha256": "job-identity",
        "job_kind": "runtime_accuracy",
    }
    manifest = {"job_manifest_sha256": "manifest-sha", "jobs": [job]}
    state = {
        "status": terminal,
        "program_id": "program",
        "protocol_id": "protocol",
        "protocol_sha256": "protocol-sha",
        "job_manifest_sha256": "manifest-sha",
        "workspace": str(workspace),
        "results_root": str(results),
        "summary_root": str((tmp_path / "summary").resolve()),
        "jobs": {"job_fixed": {"result_sha256": "result-sha"}},
    }
    lifecycle = _sign_document(
        {
            "schema_version": "h2-storage-artifact-lifecycle.v1",
            "campaign_status": terminal,
        },
        signature_key="lifecycle_sha256",
    )
    forecast = {
        "schema_version": "h2-storage-forecast.v1",
        "program_status": terminal,
    }
    guardian = {
        "schema_version": "h2-storage-guardian-pass.v1",
        "artifact_lifecycle_sha256": lifecycle["lifecycle_sha256"],
        "forecast": forecast,
    }
    pending = _sign_document(
        {
            "schema_version": "h2-storage-prune-pending.v1",
            "workspace": str(workspace),
            "queue_database_relative_path": "campaign.sqlite3",
            "job": job,
            "queue_completion": {"result_sha256": "result-sha"},
            "regenerable_source": {"logical_bytes": 4321},
            "retained_sealed_result": {
                "absolute_path": str(results / "jobs/job_fixed/result"),
                "checksums_sha256": "result-sha",
            },
        },
        signature_key="pending_sha256",
    )
    receipt = _sign_document(
        {
            "schema_version": "h2-storage-prune-receipt.v1",
            "status": "PRUNED_REGENERABLE_CASE_SHARDS",
            "validation_receipt": pending,
        },
        signature_key="receipt_sha256",
    )
    requirements_payload = (
        Path(__file__).resolve().parents[1]
        / "deployment/h2_arm64/requirements-linux-arm64.txt"
    ).read_bytes()
    runtime_identity = {
        "schema_version": "h2-runtime-implementation-identity.v2",
        "identity_sha256": "c" * 64,
    }
    arm64_wheel_receipt = _arm64_wheel_receipt_fixture(
        requirements_payload=requirements_payload,
        runtime_identity_sha256=str(runtime_identity["identity_sha256"]),
        protocol_id=str(state["protocol_id"]),
    )
    tool_root = Path(__file__).resolve().parents[1]
    atomic_bootstrap = tool_root / "scripts/h2_windows_atomic_retry_bootstrap.py"
    atomic_child = tool_root / "scripts/h2_atomic_retry_child/sitecustomize.py"
    atomic_event_log = workspace / "logs/windows_atomic_publication_events.jsonl"
    atomic_policy = _sign_document(
        {
            "schema_version": "h2-windows-atomic-publication-policy.v1",
            "platform_scope": "Windows only; other platforms use os.replace unchanged",
            "launcher_source": str(atomic_bootstrap.resolve()),
            "launcher_sha256": _sha256(atomic_bootstrap.read_bytes()),
            "child_process_propagation": "PYTHONPATH_sitecustomize",
            "child_sitecustomize_source": str(atomic_child.resolve()),
            "child_sitecustomize_sha256": _sha256(atomic_child.read_bytes()),
            "retryable_winerrors": [5, 32, 33],
            "retry_delays_sec": [0.05, 0.1, 0.2, 0.4, 0.8, 1.6, 2.0, 2.0],
            "maximum_added_wait_sec": 7.15,
            "operation_scope": "os.replace only",
            "event_log": str(atomic_event_log),
            "scientific_inference_or_metric_change": False,
            "frozen_runtime_source_tree_change": False,
            "purpose": (
                "Recover transient Windows sharing violations while publishing "
                "validation, progress, status, and other atomic JSON artifacts."
            ),
        },
        signature_key="policy_sha256",
    )
    for path, value in (
        (workspace / "program_state.json", state),
        (workspace / "runtime_implementation_identity.json", runtime_identity),
        (maintenance / "artifact_lifecycle.json", lifecycle),
        (maintenance / "storage_forecast.json", forecast),
        (maintenance / "last_guardian_pass.json", guardian),
        (
            maintenance / "arm64_wheel_resolution_receipt.json",
            arm64_wheel_receipt,
        ),
        (maintenance / "windows_atomic_publication_policy.json", atomic_policy),
        (receipts / "job_fixed.json", receipt),
    ):
        path.write_bytes(_canonical_json(value))
    atomic_event_log.parent.mkdir(parents=True, exist_ok=True)
    atomic_event_log.write_bytes(b"")
    with sqlite3.connect(workspace / "campaign.sqlite3") as connection:
        connection.executescript(
            """
            CREATE TABLE jobs(job_id TEXT PRIMARY KEY, state TEXT NOT NULL);
            CREATE TABLE attempts(
                job_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                state TEXT NOT NULL,
                attempt_path TEXT NOT NULL,
                started_at_utc TEXT NOT NULL,
                ended_at_utc TEXT NOT NULL,
                error TEXT,
                PRIMARY KEY(job_id, attempt_number)
            );
            """
        )
        connection.execute("INSERT INTO jobs VALUES (?, ?)", ("job_fixed", "complete"))
        connection.execute(
            "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "job_fixed",
                1,
                "complete",
                str(workspace / "attempts/job_fixed/attempt_001"),
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:01:00Z",
                None,
            ),
        )
    source_payloads = {
        "controller/program_state.json": _canonical_json(
            {**state, "status": "RUNNING"}
        ),
        "protocol/job_manifest.json": _canonical_json(manifest),
        ARM64_REQUIREMENTS_MEMBER: requirements_payload,
        RUNTIME_IDENTITY_MEMBER: _canonical_json(runtime_identity),
    }
    payloads, provenance = _storage_reproducibility_payloads(workspace, source_payloads)
    validated = _validate_storage_reproducibility_members(
        {**source_payloads, **payloads}
    )
    assert provenance["pruned_logical_bytes"] == 4321
    assert validated["prune_receipt_count"] == 1
    assert validated["arm64_resolved_wheel_count"] == len(
        arm64_wheel_receipt["wheels"]
    )
    assert any(name.startswith(STORAGE_PRUNE_PREFIX) for name in payloads)


def test_final_package_carries_its_augmentation_source_and_runbook() -> None:
    payloads, provenance = _augmentation_source_payloads()
    validated = _validate_augmentation_source_members(payloads)
    assert validated == provenance
    assert provenance["native_members_modified"] is False


@pytest.mark.skipif(os.name != "nt", reason="PowerShell supervisor is Windows-only")
def test_supervisor_recovery_budget_is_progress_reset_and_stop_aware() -> None:
    tool_root = Path(__file__).resolve().parents[1]
    supervisor = tool_root / "scripts/supervise_h2_product_program.ps1"
    source = supervisor.read_text(encoding="utf-8-sig")
    for required in (
        "HealthyProgressResetSeconds",
        "MaximumUnclassifiedRecoveries",
        "Read-H2JsonSharedDelete",
        "RECOVERY_BUDGET_RESET",
        "UNCLASSIFIED_RECOVERY_WAIT",
        "UNCLASSIFIED_RECOVERY_LIMIT_REACHED",
        "STOPPED_INTENTIONAL_OR_TERMINAL",
        "stop_request.json",
        "h2_windows_atomic_retry_bootstrap",
        "h2_prefreeze_selector_correction_bootstrap",
        "SELECTOR_CORRECTION_LAUNCHED",
        "correction-preflight-only",
        "SelectorCorrectionPreflightOnly",
        "SelectorCorrectionEnabled",
        "Name='python.exe' OR Name='pythonw.exe'",
        "Name='powershell.exe' OR Name='pwsh.exe' OR",
        "$ConsecutiveRecoveries -ge $MaximumConsecutiveRecoveries",
    ):
        assert required in source

    completed = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(supervisor),
            "-DryRun",
            "-HealthyProgressResetSeconds",
            "60",
            "-MaximumUnclassifiedRecoveries",
            "2",
        ],
        cwd=tool_root,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["Status"] == "DRY_RUN_PASS"
    assert payload["HealthyProgressResetSeconds"] == 60
    assert payload["MaximumUnclassifiedRecoveries"] == 2
    assert payload["SelectorCorrectionEnabled"] is True
    assert payload["SelectorCorrectionPreflightOnly"] is False
    assert payload["SelectorCorrectionStaged"] is True
    assert payload["SelectorCorrectionLauncher"].endswith(
        "h2_prefreeze_selector_correction_bootstrap.py"
    )


@pytest.mark.skipif(os.name != "nt", reason="Task Scheduler is Windows-only")
def test_v17_scheduled_task_installer_is_preview_first_and_non_destructive() -> None:
    tool_root = Path(__file__).resolve().parents[1]
    installer = tool_root / "scripts/register_h2_v17_scheduled_tasks.ps1"
    source = installer.read_text(encoding="utf-8-sig")
    for required in (
        "JustPeachy H2 v17 Supervisor",
        "JustPeachy H2 v17 Milestone Notifier",
        "JustPeachy H2 v17 Serial Resource Audit",
        "JustPeachy H2 v17 Post-Campaign Engineering",
        "JustPeachy H2 v17 Final Package Watcher",
        "h2_complete_product_pipeline_v17",
        "MultipleInstances IgnoreNew",
        "ExecutionTimeLimit ([TimeSpan]::Zero)",
        "Disable-ScheduledTask",
        "superseded_evidence_deleted = $false",
        "scientific_configuration_changed = $false",
    ):
        assert required in source
    assert "Unregister-ScheduledTask" not in source
    assert "if (-not $Apply)" in source


def test_final_package_requires_all_five_v17_persistence_tasks() -> None:
    workspace = r"C:\h2_complete_product_pipeline_v17"
    terminal_state = {
        "workspace": workspace,
        "results_root": r"C:\h2_results",
        "summary_root": r"C:\h2_summaries",
    }
    installer = b"bounded scheduled-task installer"
    task_names = (
        "JustPeachy H2 v17 Supervisor",
        "JustPeachy H2 v17 Milestone Notifier",
        "JustPeachy H2 v17 Serial Resource Audit",
        "JustPeachy H2 v17 Post-Campaign Engineering",
        "JustPeachy H2 v17 Final Package Watcher",
    )
    receipt = {
        "schema_version": "h2-v17-scheduled-task-registration.v1",
        "status": "APPLIED_AND_VERIFIED",
        "applied": True,
        **terminal_state,
        "scientific_configuration_changed": False,
        "superseded_evidence_deleted": False,
        "installer_sha256": _sha256(installer),
        "tasks": [
            {
                "task_name": name,
                "arguments": f'-Workspace "{workspace}"',
                "executable": r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            }
            for name in task_names
        ],
        "superseded_v16_tasks_disabled": [
            "JustPeachy H2 v16 Supervisor",
            "JustPeachy H2 v16 Milestone Notifier",
            "JustPeachy H2 v16 Serial Resource Audit",
            "JustPeachy H2 v16 Final Package Watcher",
        ],
    }
    validated = _validated_h2_v17_task_registration(
        _canonical_json(receipt),
        installer_payload=installer,
        terminal_state=terminal_state,
    )
    assert len(validated["tasks"]) == 5

    receipt["tasks"] = [
        row
        for row in receipt["tasks"]
        if row["task_name"] != "JustPeachy H2 v17 Post-Campaign Engineering"
    ]
    with pytest.raises(ValueError, match="registration binding differs"):
        _validated_h2_v17_task_registration(
            _canonical_json(receipt),
            installer_payload=installer,
            terminal_state=terminal_state,
        )
