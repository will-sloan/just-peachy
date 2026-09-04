from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from app.full_pipeline_evaluation.controller import (
    EvaluationQueueInfrastructureError,
    _memory_gated_parallelism,
    _require_reusable_complete_results,
    _run_locked,
)
from app.full_pipeline_evaluation.io import sha256_file, write_json_atomic
from app.full_pipeline_evaluation.monitor import progress_snapshot
from app.full_pipeline_evaluation.planning import (
    build_campaign_manifest,
    filter_jobs,
)
from app.full_pipeline_evaluation.smoke import run_infrastructure_smoke
from app.full_pipeline_evaluation.store import (
    EvaluationStateCorruptionError,
    EvaluationStateStore,
    utc_now,
)
from app.full_pipeline_evaluation.synthetic import publish_synthetic_result
from app.full_pipeline_evaluation import controller as controller_module
from app.full_pipeline_evaluation import store as store_module


def _cases() -> list[dict[str, object]]:
    return [
        {
            "case_id": "dev_case",
            "split": "development",
            "source_key": "controlled_v1",
            "source_protocol_id": "controlled_diarization_v1_test",
            "duration_sec": 2.0,
            "source_hashes": {"audio": "1" * 64},
        },
        {
            "case_id": "eval_case",
            "split": "evaluation",
            "source_key": "controlled_v2",
            "source_protocol_id": "diarization_product_v2_test",
            "duration_sec": 3.0,
            "source_hashes": {"audio": "2" * 64},
        },
    ]


def test_plan_is_deterministic_and_covers_18_by_two_modes() -> None:
    left, left_jobs = build_campaign_manifest(
        _cases(),
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        seed=5107,
    )
    right, right_jobs = build_campaign_manifest(
        reversed(_cases()),
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        seed=5107,
    )
    assert left == right
    assert left_jobs == right_jobs
    assert len(left_jobs) == 18 * 2 * 2
    assert len({job.pipeline_id for job in left_jobs}) == 18
    assert {job.measurement_mode for job in left_jobs} == {"accuracy", "resources"}
    assert all(job.reuse_identity["identity_sha256"] for job in left_jobs)


def test_exact_filters_reject_unknown_identity() -> None:
    _, jobs = build_campaign_manifest(
        _cases(),
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
    )
    selected = filter_jobs(
        jobs,
        split="development",
        measurement_mode="accuracy",
        pipeline_ids=("fullpipe_v1_ag_dr_ie",),
        protocol_ids=("controlled_diarization_v1_test",),
    )
    assert len(selected) == 1
    with pytest.raises(ValueError, match="unknown exact pipeline"):
        filter_jobs(jobs, pipeline_ids=("fullpipe_v1_not_real",))
    with pytest.raises(ValueError, match="unknown exact protocol"):
        filter_jobs(jobs, protocol_ids=("not_a_protocol",))


def test_development_stage_registry_and_selection_are_bound_into_reuse() -> None:
    pipeline_id = "fullpipe_v1_ag_dr_ie"
    base, _ = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=(pipeline_id,),
        measurement_modes=("accuracy",),
        campaign_stage="prompt4_calibration",
    )
    frozen, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=(pipeline_id,),
        measurement_modes=("accuracy",),
        campaign_stage="prompt4_development_accuracy",
        decision_policy_registry_sha256="c" * 64,
    )

    assert frozen["pipeline_count"] == 1
    assert frozen["measurement_modes"] == ["accuracy"]
    assert frozen["selected_pipeline_ids"] == [pipeline_id]
    assert frozen["decision_policy_registry"]["sha256"] == "c" * 64
    assert len(jobs) == 1
    assert base["campaign_id"] != frozen["campaign_id"]
    assert base["jobs"][0]["reuse_identity"]["identity_sha256"] != (
        frozen["jobs"][0]["reuse_identity"]["identity_sha256"]
    )


def test_native_reference_support_strata_are_separate_jobs() -> None:
    cases = [
        {
            "case_id": "ami_cpwer",
            "split": "evaluation",
            "source_key": "native_standard",
            "source_protocol_id": "native_diarization_test",
            "scoring_stratum": "ami_cpwer_and_diarization",
            "duration_sec": 2.0,
        },
        {
            "case_id": "ami_der",
            "split": "evaluation",
            "source_key": "native_standard",
            "source_protocol_id": "native_diarization_test",
            "scoring_stratum": "ami_diarization_only",
            "duration_sec": 3.0,
        },
        {
            "case_id": "chime_der",
            "split": "evaluation",
            "source_key": "native_standard",
            "source_protocol_id": "native_diarization_test",
            "scoring_stratum": "chime6_diarization_only",
            "duration_sec": 4.0,
        },
    ]

    manifest, jobs = build_campaign_manifest(
        cases,
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
    )

    assert manifest["case_count"] == 3
    implementation = manifest["implementation_identity"]
    assert set(implementation) == {
        "development_policy_package_sha256",
        "evaluation_package_sha256",
        "streaming_runtime_package_sha256",
    }
    assert all(len(value) == 64 for value in implementation.values())
    assert len(jobs) == 18 * 2 * 3
    source_keys = {job.source_key for job in jobs}
    assert source_keys == {
        "native_standard__ami_cpwer_and_diarization",
        "native_standard__ami_diarization_only",
        "native_standard__chime6_diarization_only",
    }
    assert all(job.case_count == 1 for job in jobs)


def test_sqlite_state_retries_and_measured_progress(tmp_path: Path) -> None:
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
    )
    job = jobs[0]
    store = EvaluationStateStore(tmp_path / "campaign.sqlite3")
    assert store.prepare(
        [job], campaign_id=str(manifest["campaign_id"]), manifest_sha256="c" * 64
    ) == {"inserted": 1, "unchanged": 0}
    claimed = store.claim(job.job_id, owner="test")
    assert claimed is not None and claimed.attempt_count == 1
    store.heartbeat(
        job.job_id,
        owner="test",
        completed_cases=1,
        completed_audio_sec=1.0,
        current_case_id=job.case_ids[0],
        latest_activity="halfway",
        rolling_rtf=0.5,
        cpu_percent=50,
        rss_mb=1000,
        queue_depth=2,
        cache_hits=3,
    )
    store.finish(
        job.job_id,
        owner="test",
        state="failed",
        completed_cases=1,
        completed_audio_sec=1.0,
        latest_activity="expected failure",
        last_error="expected failure",
    )
    store.record_attempt(
        job_id=job.job_id,
        attempt_number=1,
        state="failed",
        attempt_path=tmp_path / "attempt_1",
        started_at_utc=utc_now(),
        ended_at_utc=utc_now(),
        error="expected failure",
    )
    retried = store.claim(job.job_id, owner="retry")
    assert retried is not None and retried.attempt_count == 2
    store.set_runtime_metadata("progress_baseline_utc", utc_now())
    store.set_runtime_metadata("progress_baseline_audio_sec", "0")
    snapshot = progress_snapshot(store, campaign_id=str(manifest["campaign_id"]))
    assert snapshot["eta_basis"]["kind"] == "measured_completed_audio_over_wall_time"
    assert snapshot["completed_audio_sec"] == 1.0
    assert snapshot["failures"] == 1
    assert snapshot["retries"] == 1
    assert snapshot["resource_measurement_serial"] is True
    store.finish(
        job.job_id,
        owner="retry",
        state="stopped",
        completed_cases=1,
        completed_audio_sec=1.0,
        latest_activity="stopped for monitor test",
    )
    inactive = progress_snapshot(store, campaign_id=str(manifest["campaign_id"]))
    assert inactive["eta_sec"] is None
    assert inactive["estimated_finish_utc"] is None


def test_read_connections_are_closed_explicitly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read helpers must not leave SQLite/WAL handles to garbage collection."""

    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=("fullpipe_v1_ag_dr_ie",),
        measurement_modes=("accuracy",),
    )
    store = EvaluationStateStore(tmp_path / "campaign.sqlite3")
    store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )

    class TrackingConnection(sqlite3.Connection):
        closed_by_store = False

        def close(self) -> None:
            self.closed_by_store = True
            super().close()

    connections: list[TrackingConnection] = []
    original_connect = sqlite3.connect

    def tracked_connect(*args: object, **kwargs: object) -> TrackingConnection:
        connection = original_connect(
            *args, **kwargs, factory=TrackingConnection
        )
        connections.append(connection)
        return connection

    monkeypatch.setattr(store_module.sqlite3, "connect", tracked_connect)
    assert store.metadata()["campaign_id"] == manifest["campaign_id"]
    assert len(store.list_jobs()) == 1
    assert store.attempt_rows() == ()

    assert len(connections) == 3
    assert all(connection.closed_by_store for connection in connections)


def test_malformed_queue_fails_closed_without_rewriting_source_bytes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "campaign.sqlite3"
    original = b"not a sqlite database"
    database.write_bytes(original)

    with pytest.raises(EvaluationStateCorruptionError, match="unreadable"):
        EvaluationStateStore(database)

    assert database.read_bytes() == original
    database.rename(database.with_suffix(".forensics.sqlite3"))


def test_existing_queue_open_validates_without_ddl_or_journal_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=("fullpipe_v1_ag_dr_ie",),
        measurement_modes=("accuracy",),
    )
    database = tmp_path / "campaign.sqlite3"
    store = EvaluationStateStore(database)
    store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )

    statements: list[str] = []
    original_connect = sqlite3.connect

    def traced_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        connection = original_connect(*args, **kwargs)
        connection.set_trace_callback(statements.append)
        return connection

    monkeypatch.setattr(store_module, "_DATABASE_RUNTIME_STATES", {})
    monkeypatch.setattr(store_module.sqlite3, "connect", traced_connect)

    reopened = EvaluationStateStore(database)

    assert reopened.metadata()["campaign_id"] == manifest["campaign_id"]
    normalized = [" ".join(statement.upper().split()) for statement in statements]
    assert not any(statement.startswith("CREATE ") for statement in normalized)
    assert "BEGIN IMMEDIATE" not in normalized
    assert not any(
        statement.startswith("PRAGMA JOURNAL_MODE=") for statement in normalized
    )
    assert "PRAGMA JOURNAL_MODE" in normalized


def test_sqlite_queue_serializes_store_instances_and_uses_rollback_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline_ids = ("fullpipe_v1_ag_dr_ie", "fullpipe_v1_ao_dr_ie")
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=pipeline_ids,
        measurement_modes=("accuracy",),
    )
    database = tmp_path / "campaign.sqlite3"
    first_store = EvaluationStateStore(database)
    first_store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )
    second_store = EvaluationStateStore(database)
    owners = ("owner-1", "owner-2")
    assert first_store.claim(jobs[0].job_id, owner=owners[0]) is not None
    assert second_store.claim(jobs[1].job_id, owner=owners[1]) is not None

    original_connect = sqlite3.connect
    counter_lock = threading.Lock()
    active_transactions = 0
    maximum_active_transactions = 0

    class TransactionTrackingConnection(sqlite3.Connection):
        tracked_transaction = False

        def execute(self, sql: str, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
            nonlocal active_transactions, maximum_active_transactions
            if sql.strip().upper() == "BEGIN IMMEDIATE":
                with counter_lock:
                    active_transactions += 1
                    maximum_active_transactions = max(
                        maximum_active_transactions, active_transactions
                    )
                self.tracked_transaction = True
                time.sleep(0.003)
                try:
                    return super().execute(sql, *args, **kwargs)
                except Exception:
                    self._end_tracked_transaction()
                    raise
            return super().execute(sql, *args, **kwargs)

        def commit(self) -> None:
            try:
                super().commit()
            finally:
                self._end_tracked_transaction()

        def rollback(self) -> None:
            try:
                super().rollback()
            finally:
                self._end_tracked_transaction()

        def close(self) -> None:
            self._end_tracked_transaction()
            super().close()

        def _end_tracked_transaction(self) -> None:
            nonlocal active_transactions
            if self.tracked_transaction:
                with counter_lock:
                    active_transactions -= 1
                self.tracked_transaction = False

    def tracked_connect(*args: object, **kwargs: object) -> sqlite3.Connection:
        return original_connect(
            *args, **kwargs, factory=TransactionTrackingConnection
        )

    monkeypatch.setattr(store_module.sqlite3, "connect", tracked_connect)
    start = threading.Barrier(2)

    def churn(
        store: EvaluationStateStore, job_index: int, owner: str
    ) -> None:
        start.wait()
        job = jobs[job_index]
        for heartbeat_index in range(20):
            store.heartbeat(
                job.job_id,
                owner=owner,
                completed_cases=0,
                completed_audio_sec=heartbeat_index / 20,
                current_case_id=job.case_ids[0],
                latest_activity=f"heartbeat-{heartbeat_index}",
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (
            pool.submit(churn, first_store, 0, owners[0]),
            pool.submit(churn, second_store, 1, owners[1]),
        )
        for future in futures:
            future.result()

    assert maximum_active_transactions == 1
    with closing(original_connect(database)) as connection:
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_runtime_stop_callback_uses_controller_event_not_database_polling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline_id = "fullpipe_v1_ag_dr_ie"
    protocol_id = "controlled_diarization_v1_test"
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=(pipeline_id,),
        measurement_modes=("accuracy",),
    )
    store = EvaluationStateStore(tmp_path / "campaign.sqlite3")
    store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )
    monkeypatch.setattr(
        controller_module, "validate", lambda **_kwargs: {"valid": True}
    )
    monkeypatch.setattr(controller_module, "_manifest", lambda _workspace: manifest)
    monkeypatch.setattr(
        controller_module,
        "_memory_gated_parallelism",
        lambda **_kwargs: (1, {"reason": "test"}),
    )
    stop_database_reads = 0
    count_lock = threading.Lock()
    original_stop_requested = EvaluationStateStore.stop_requested

    def counted_stop_requested(self: EvaluationStateStore) -> bool:
        nonlocal stop_database_reads
        with count_lock:
            stop_database_reads += 1
        return original_stop_requested(self)

    monkeypatch.setattr(
        EvaluationStateStore, "stop_requested", counted_stop_requested
    )

    def executor(
        _job: object,
        _cases_arg: object,
        _output_root: object,
        _progress: object,
        stop_requested: object,
    ) -> dict[str, object]:
        callback = stop_requested
        assert callable(callback)
        for _ in range(250):
            assert callback() is False
        return {
            "state": "failed",
            "completed_cases": 0,
            "completed_audio_sec": 0.0,
            "error": "bounded test failure",
        }

    result = _run_locked(
        workspace_root=tmp_path,
        split="development",
        measurement_mode="accuracy",
        pipeline_ids=(pipeline_id,),
        protocol_ids=(protocol_id,),
        parallel_jobs=1,
        job_executor=executor,
    )

    assert result["status"] == "FAILED"
    assert stop_database_reads <= 2


def test_scheduler_does_not_submit_after_queue_infrastructure_exception(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline_ids = ("fullpipe_v1_ag_dr_ie", "fullpipe_v1_ao_dr_ie")
    protocol_id = "controlled_diarization_v1_test"
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=pipeline_ids,
        measurement_modes=("accuracy",),
    )
    store = EvaluationStateStore(tmp_path / "campaign.sqlite3")
    store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )
    monkeypatch.setattr(
        controller_module, "validate", lambda **_kwargs: {"valid": True}
    )
    monkeypatch.setattr(controller_module, "_manifest", lambda _workspace: manifest)
    monkeypatch.setattr(
        controller_module,
        "_memory_gated_parallelism",
        lambda **_kwargs: (1, {"reason": "test"}),
    )
    submitted: list[str] = []

    def fail_queue(*args: object, **_kwargs: object) -> dict[str, object]:
        job = args[2]
        submitted.append(job.job_id)  # type: ignore[attr-defined]
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(controller_module, "_run_one", fail_queue)

    with pytest.raises(
        EvaluationQueueInfrastructureError, match="database disk image is malformed"
    ):
        _run_locked(
            workspace_root=tmp_path,
            split="development",
            measurement_mode="accuracy",
            pipeline_ids=pipeline_ids,
            protocol_ids=(protocol_id,),
            parallel_jobs=1,
            job_executor=lambda *_args: {"state": "complete"},
        )

    assert submitted == [jobs[0].job_id]
    state = json.loads((tmp_path / "controller_state.json").read_text("utf-8"))
    assert state["status"] == "FAILED"
    assert state["detail"] == (
        "Queue infrastructure failed; no further jobs were scheduled"
    )
    assert state["infrastructure_errors"][0]["phase"] == "job_future"


def test_terminal_queue_integrity_failure_prevents_next_job_submission(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline_ids = ("fullpipe_v1_ag_dr_ie", "fullpipe_v1_ao_dr_ie")
    protocol_id = "controlled_diarization_v1_test"
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=pipeline_ids,
        measurement_modes=("accuracy",),
    )
    store = EvaluationStateStore(tmp_path / "campaign.sqlite3")
    store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )
    monkeypatch.setattr(
        controller_module, "validate", lambda **_kwargs: {"valid": True}
    )
    monkeypatch.setattr(controller_module, "_manifest", lambda _workspace: manifest)
    monkeypatch.setattr(
        controller_module,
        "_memory_gated_parallelism",
        lambda **_kwargs: (1, {"reason": "test"}),
    )
    submitted: list[str] = []

    def executor(
        job: object, *_args: object, **_kwargs: object
    ) -> dict[str, object]:
        submitted.append(job.job_id)  # type: ignore[attr-defined]
        return {
            "state": "failed",
            "completed_cases": 0,
            "completed_audio_sec": 0.0,
            "error": "bounded test failure",
        }

    def fail_integrity(_store: EvaluationStateStore) -> None:
        raise EvaluationStateCorruptionError("injected terminal quick_check failure")

    monkeypatch.setattr(EvaluationStateStore, "assert_integrity", fail_integrity)

    with pytest.raises(
        EvaluationQueueInfrastructureError,
        match="injected terminal quick_check failure",
    ):
        _run_locked(
            workspace_root=tmp_path,
            split="development",
            measurement_mode="accuracy",
            pipeline_ids=pipeline_ids,
            protocol_ids=(protocol_id,),
            parallel_jobs=1,
            job_executor=executor,
        )

    assert submitted == [jobs[0].job_id]


def test_resource_parallelism_is_forced_serial() -> None:
    effective, reason = _memory_gated_parallelism(
        requested=2, measurement_mode="resources"
    )
    assert effective == 1
    assert "serial" in str(reason["reason"])


def test_unexpired_preclaimed_job_cannot_report_campaign_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline_id = "fullpipe_v1_ag_dr_ie"
    protocol_id = "controlled_diarization_v1_test"
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
        pipeline_ids=(pipeline_id,),
        measurement_modes=("accuracy",),
    )
    job = jobs[0]
    store = EvaluationStateStore(tmp_path / "campaign.sqlite3")
    store.prepare(
        jobs,
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )
    assert store.claim(job.job_id, owner="still-alive", lease_seconds=120) is not None

    monkeypatch.setattr(
        "app.full_pipeline_evaluation.controller.validate",
        lambda **_kwargs: {"valid": True},
    )
    monkeypatch.setattr(
        "app.full_pipeline_evaluation.controller._manifest",
        lambda _workspace: manifest,
    )
    monkeypatch.setattr(
        "app.full_pipeline_evaluation.controller._memory_gated_parallelism",
        lambda **_kwargs: (1, {"reason": "test"}),
    )

    result = _run_locked(
        workspace_root=tmp_path,
        split="development",
        measurement_mode="accuracy",
        pipeline_ids=(pipeline_id,),
        protocol_ids=(protocol_id,),
        parallel_jobs=1,
        job_executor=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("an unexpired preclaimed job must not execute")
        ),
    )

    assert result["status"] == "FAILED"
    assert result["failures"] == [job.job_id]
    assert result["incomplete_states"] == {job.job_id: "running"}


def test_tiny_infrastructure_smoke_runs_without_models(tmp_path: Path) -> None:
    result = run_infrastructure_smoke(output_root=tmp_path / "smoke")
    assert result["status"] == "PASS"
    assert result["model_inference_performed"] is False
    assert result["dataset_downloads_performed"] is False
    assert result["long_scientific_campaign_started"] is False
    assert result["perfect_result_reusable"] is True
    assert result["failure_result_reusable"] is False


def _completed_synthetic_result(tmp_path: Path) -> tuple[dict[str, object], object, Path]:
    manifest, jobs = build_campaign_manifest(
        [_cases()[0]],
        protocol_id="full_speech_pipeline_v1_test",
        development_identity="a" * 64,
        evaluation_identity="b" * 64,
    )
    job = next(
        value
        for value in jobs
        if value.measurement_mode == "accuracy"
        and value.pipeline_id == "fullpipe_v1_ag_dr_ie"
    )
    results_root = tmp_path / "results"
    write_json_atomic(
        tmp_path / "campaign_paths.json",
        {"results_root": str(results_root)},
    )
    result_root = results_root / job.result_relative_path
    assert publish_synthetic_result(
        result_root, reuse_identity=job.reuse_identity
    ).reusable
    checksum = sha256_file(result_root / "checksums.json")
    store = EvaluationStateStore(tmp_path / "campaign.sqlite3")
    store.prepare(
        [job],
        campaign_id=str(manifest["campaign_id"]),
        manifest_sha256="c" * 64,
    )
    assert store.claim(job.job_id, owner="integrity") is not None
    store.finish(
        job.job_id,
        owner="integrity",
        state="complete",
        completed_cases=job.case_count,
        completed_audio_sec=job.audio_duration_sec,
        latest_activity="complete",
        result_sha256=checksum,
    )
    return manifest, store.list_jobs()[0], result_root


def test_complete_result_integrity_requires_tree_and_db_checksum(
    tmp_path: Path,
) -> None:
    manifest, row, result_root = _completed_synthetic_result(tmp_path)

    validated = _require_reusable_complete_results(tmp_path, manifest, [row])

    assert validated == {
        row.spec.job_id: sha256_file(result_root / "checksums.json")
    }


def test_complete_result_integrity_rejects_post_completion_mutation(
    tmp_path: Path,
) -> None:
    manifest, row, result_root = _completed_synthetic_result(tmp_path)
    summary = result_root / "metrics/summary.json"
    summary.write_bytes(summary.read_bytes() + b" ")

    with pytest.raises(RuntimeError, match="not checksum-reusable"):
        _require_reusable_complete_results(tmp_path, manifest, [row])


def test_complete_result_integrity_rejects_missing_result_tree(
    tmp_path: Path,
) -> None:
    manifest, row, result_root = _completed_synthetic_result(tmp_path)
    result_root.rename(result_root.with_name("removed-result-tree"))

    with pytest.raises(RuntimeError, match="missing_root.*result root is missing"):
        _require_reusable_complete_results(tmp_path, manifest, [row])
