"""Transactional SQLite state for restart-safe campaign execution."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
from typing import Callable, Iterable, Iterator, Mapping, Sequence


DATABASE_SCHEMA_VERSION = "campaign-database.v1"
EXECUTION_STATE_VERSION = "campaign-execution-state.v1"

STATES = frozenset(
    {
        "pending",
        "assigned",
        "running",
        "succeeded",
        "succeeded_with_warnings",
        "failed_retryable",
        "failed_terminal",
        "timeout",
        "out_of_memory",
        "interrupted",
        "stopped",
        "invalid",
    }
)
SUCCESS_STATES = frozenset({"succeeded", "succeeded_with_warnings"})
TERMINAL_STATES = frozenset(
    {"succeeded", "succeeded_with_warnings", "failed_terminal", "stopped", "invalid"}
)
RETRY_SOURCE_STATES = frozenset(
    {"failed_retryable", "timeout", "out_of_memory", "interrupted"}
)
LEASED_STATES = frozenset({"assigned", "running"})

ALLOWED_TRANSITIONS: Mapping[str, frozenset[str]] = {
    "pending": frozenset({"assigned", "stopped", "invalid", "succeeded", "succeeded_with_warnings"}),
    "assigned": frozenset({"running", "interrupted", "stopped", "invalid"}),
    "running": frozenset(
        {
            "succeeded",
            "succeeded_with_warnings",
            "failed_retryable",
            "failed_terminal",
            "timeout",
            "out_of_memory",
            "interrupted",
            "stopped",
            "invalid",
        }
    ),
    "failed_retryable": frozenset({"pending", "assigned", "stopped", "invalid"}),
    "timeout": frozenset({"pending", "assigned", "stopped", "invalid"}),
    "out_of_memory": frozenset({"pending", "assigned", "stopped", "invalid"}),
    "interrupted": frozenset({"pending", "assigned", "stopped", "invalid"}),
    "succeeded": frozenset({"invalid"}),
    "succeeded_with_warnings": frozenset({"invalid"}),
    "failed_terminal": frozenset({"invalid"}),
    "stopped": frozenset(),
    "invalid": frozenset(),
}


class CampaignStateError(RuntimeError):
    """Raised when persistent campaign state is invalid or cannot transition."""


@dataclass(frozen=True)
class ScenarioState:
    campaign_id: str
    scenario_id: str
    scenario_hash: str
    ordinal: int
    state: str
    worker_id: str | None
    hostname: str | None
    attempt_count: int
    max_attempts: int
    started_at_utc: str | None
    ended_at_utc: str | None
    heartbeat_at_utc: str | None
    lease_owner: str | None
    lease_expires_at_utc: str | None
    exit_code: int | None
    exception_category: str | None
    concise_error: str | None
    expected_artifacts: tuple[str, ...]
    output_completeness: str | None
    retry_eligible: bool
    stop_requested: bool
    stop_reason: str | None


@dataclass(frozen=True)
class ExecutionLease:
    campaign_id: str
    scenario_id: str
    scenario_hash: str
    owner: str
    worker_id: str
    hostname: str
    attempt_number: int
    max_attempts: int
    expires_at_utc: str
    expected_artifacts: tuple[str, ...]


class CampaignStateStore:
    """SQLite-backed source of truth for one campaign's execution state."""

    def __init__(
        self,
        database_path: Path,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.database_path = database_path.resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def register_campaign(self, campaign_id: str, manifest_sha256: str) -> None:
        now = self._now_text()
        with self._transaction() as connection:
            existing = connection.execute(
                "SELECT manifest_sha256 FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if existing is not None and existing[0] != manifest_sha256:
                raise CampaignStateError(
                    "campaign ID already exists with a different immutable manifest"
                )
            connection.execute(
                """
                INSERT INTO campaigns(
                    campaign_id, manifest_sha256, created_at_utc, updated_at_utc,
                    stop_requested, stop_reason
                ) VALUES (?, ?, ?, ?, 0, NULL)
                ON CONFLICT(campaign_id) DO UPDATE SET updated_at_utc = excluded.updated_at_utc
                """,
                (campaign_id, manifest_sha256, now, now),
            )

    def register_scenarios(
        self,
        campaign_id: str,
        scenarios: Iterable[Mapping[str, object]],
    ) -> None:
        now = self._now_text()
        with self._transaction() as connection:
            for ordinal, scenario in enumerate(scenarios):
                scenario_id = str(scenario["scenario_id"])
                scenario_hash = str(scenario["scenario_hash"])
                expected = tuple(str(item) for item in scenario.get("expected_artifacts", ()))
                max_attempts = int(scenario.get("max_attempts", 1))
                if max_attempts < 1:
                    raise CampaignStateError("max_attempts must be at least one")
                existing = connection.execute(
                    """
                    SELECT scenario_hash, ordinal, max_attempts, expected_artifacts_json
                    FROM scenarios WHERE campaign_id = ? AND scenario_id = ?
                    """,
                    (campaign_id, scenario_id),
                ).fetchone()
                encoded_expected = json.dumps(sorted(expected), separators=(",", ":"))
                if existing is not None:
                    if existing[0] != scenario_hash:
                        raise CampaignStateError(
                            f"scenario ID {scenario_id} is already bound to another hash"
                        )
                    if (
                        int(existing[1]) != ordinal
                        or int(existing[2]) != max_attempts
                        or existing[3] != encoded_expected
                    ):
                        raise CampaignStateError(
                            f"scenario registration changed for existing campaign: {scenario_id}"
                        )
                    continue
                connection.execute(
                    """
                    INSERT INTO scenarios(
                        campaign_id, scenario_id, scenario_hash, ordinal, state,
                        attempt_count, max_attempts, expected_artifacts_json,
                        retry_eligible, stop_requested, created_at_utc, updated_at_utc
                    ) VALUES (?, ?, ?, ?, 'pending', 0, ?, ?, 1, 0, ?, ?)
                    """,
                    (
                        campaign_id,
                        scenario_id,
                        scenario_hash,
                        ordinal,
                        max_attempts,
                        encoded_expected,
                        now,
                        now,
                    ),
                )
                self._insert_event(
                    connection,
                    campaign_id,
                    scenario_id,
                    "scenario_registered",
                    {"ordinal": ordinal, "max_attempts": max_attempts},
                    now,
                )

    def acquire_next(
        self,
        campaign_id: str,
        *,
        worker_id: str,
        hostname: str,
        lease_seconds: float,
        scenario_ids: Sequence[str] | None = None,
    ) -> ExecutionLease | None:
        if lease_seconds <= 0:
            raise CampaignStateError("lease_seconds must be positive")
        now_value = self._now()
        now = _timestamp(now_value)
        expiry = _timestamp(now_value + timedelta(seconds=lease_seconds))
        owner = f"{worker_id}@{hostname}"
        with self._transaction() as connection:
            campaign = connection.execute(
                "SELECT stop_requested FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if campaign is None:
                raise CampaignStateError(f"unknown campaign {campaign_id}")
            if bool(campaign[0]):
                return None
            clauses = [
                "campaign_id = ?",
                "stop_requested = 0",
                "((state = 'pending' AND attempt_count < max_attempts) OR "
                "(state IN ('failed_retryable','timeout','out_of_memory') AND retry_eligible = 1 AND attempt_count < max_attempts) OR "
                "(state = 'interrupted' AND retry_eligible = 1))",
            ]
            parameters: list[object] = [campaign_id]
            if scenario_ids:
                placeholders = ",".join("?" for _ in scenario_ids)
                clauses.append(f"scenario_id IN ({placeholders})")
                parameters.extend(scenario_ids)
            row = connection.execute(
                f"""
                SELECT scenario_id, scenario_hash, state, attempt_count,
                       max_attempts, expected_artifacts_json
                FROM scenarios
                WHERE {' AND '.join(clauses)}
                ORDER BY ordinal, scenario_id
                LIMIT 1
                """,
                parameters,
            ).fetchone()
            if row is None:
                return None
            scenario_id = str(row[0])
            previous_state = str(row[2])
            self._require_transition(previous_state, "assigned")
            attempt_number = int(row[3]) + 1
            updated = connection.execute(
                """
                UPDATE scenarios
                SET state = 'assigned', worker_id = ?, hostname = ?,
                    attempt_count = ?, lease_owner = ?, lease_expires_at_utc = ?,
                    heartbeat_at_utc = ?, started_at_utc = COALESCE(started_at_utc, ?),
                    ended_at_utc = NULL, exit_code = NULL, exception_category = NULL,
                    concise_error = NULL, output_completeness = NULL,
                    updated_at_utc = ?
                WHERE campaign_id = ? AND scenario_id = ? AND state = ?
                """,
                (
                    worker_id,
                    hostname,
                    attempt_number,
                    owner,
                    expiry,
                    now,
                    now,
                    now,
                    campaign_id,
                    scenario_id,
                    previous_state,
                ),
            ).rowcount
            if updated != 1:
                return None
            connection.execute(
                """
                INSERT INTO attempts(
                    campaign_id, scenario_id, attempt_number, state,
                    worker_id, hostname, lease_owner, started_at_utc
                ) VALUES (?, ?, ?, 'assigned', ?, ?, ?, ?)
                """,
                (
                    campaign_id,
                    scenario_id,
                    attempt_number,
                    worker_id,
                    hostname,
                    owner,
                    now,
                ),
            )
            self._insert_event(
                connection,
                campaign_id,
                scenario_id,
                "lease_acquired",
                {"owner": owner, "attempt": attempt_number, "expires_at_utc": expiry},
                now,
            )
            expected = tuple(json.loads(str(row[5])))
            return ExecutionLease(
                campaign_id=campaign_id,
                scenario_id=scenario_id,
                scenario_hash=str(row[1]),
                owner=owner,
                worker_id=worker_id,
                hostname=hostname,
                attempt_number=attempt_number,
                max_attempts=int(row[4]),
                expires_at_utc=expiry,
                expected_artifacts=expected,
            )

    def mark_running(self, lease: ExecutionLease, *, process_id: int | None = None) -> None:
        now = self._now_text()
        with self._transaction() as connection:
            row = self._lease_row(connection, lease)
            self._require_transition(str(row[0]), "running")
            connection.execute(
                """
                UPDATE scenarios SET state = 'running', updated_at_utc = ?
                WHERE campaign_id = ? AND scenario_id = ? AND lease_owner = ?
                """,
                (now, lease.campaign_id, lease.scenario_id, lease.owner),
            )
            connection.execute(
                """
                UPDATE attempts SET state = 'running', process_id = ?
                WHERE campaign_id = ? AND scenario_id = ? AND attempt_number = ?
                """,
                (
                    process_id,
                    lease.campaign_id,
                    lease.scenario_id,
                    lease.attempt_number,
                ),
            )
            self._insert_event(
                connection,
                lease.campaign_id,
                lease.scenario_id,
                "scenario_started",
                {"attempt": lease.attempt_number, "process_id": process_id},
                now,
            )

    def mark_running_process(self, lease: ExecutionLease, process_id: int) -> None:
        """Record the supervised child PID after process creation."""

        with self._transaction() as connection:
            row = self._lease_row(connection, lease)
            if str(row[0]) != "running":
                raise CampaignStateError("child process requires a running lease")
            connection.execute(
                """
                UPDATE attempts SET process_id = ?
                WHERE campaign_id = ? AND scenario_id = ? AND attempt_number = ?
                """,
                (
                    int(process_id),
                    lease.campaign_id,
                    lease.scenario_id,
                    lease.attempt_number,
                ),
            )

    def heartbeat(self, lease: ExecutionLease, *, lease_seconds: float) -> str:
        now_value = self._now()
        now = _timestamp(now_value)
        expiry = _timestamp(now_value + timedelta(seconds=lease_seconds))
        with self._transaction() as connection:
            row = self._lease_row(connection, lease)
            if str(row[0]) not in LEASED_STATES:
                raise CampaignStateError("heartbeat requires an assigned or running lease")
            connection.execute(
                """
                UPDATE scenarios
                SET heartbeat_at_utc = ?, lease_expires_at_utc = ?, updated_at_utc = ?
                WHERE campaign_id = ? AND scenario_id = ? AND lease_owner = ?
                """,
                (now, expiry, now, lease.campaign_id, lease.scenario_id, lease.owner),
            )
        return expiry

    def finalize(
        self,
        lease: ExecutionLease,
        *,
        state: str,
        exit_code: int | None,
        exception_category: str | None,
        concise_error: str | None,
        output_completeness: str | None,
        retry_eligible: bool,
    ) -> None:
        if state not in STATES:
            raise CampaignStateError(f"unknown execution state {state!r}")
        now = self._now_text()
        with self._transaction() as connection:
            row = self._lease_row(connection, lease)
            previous = str(row[0])
            self._require_transition(previous, state)
            if retry_eligible and state not in RETRY_SOURCE_STATES:
                raise CampaignStateError(f"state {state} cannot be retry eligible")
            if lease.attempt_number >= lease.max_attempts and state != "interrupted":
                retry_eligible = False
            connection.execute(
                """
                UPDATE scenarios
                SET state = ?, ended_at_utc = ?, exit_code = ?,
                    exception_category = ?, concise_error = ?,
                    output_completeness = ?, retry_eligible = ?,
                    lease_owner = NULL, lease_expires_at_utc = NULL,
                    heartbeat_at_utc = ?, updated_at_utc = ?
                WHERE campaign_id = ? AND scenario_id = ? AND lease_owner = ?
                """,
                (
                    state,
                    now,
                    exit_code,
                    exception_category,
                    _concise(concise_error),
                    output_completeness,
                    int(retry_eligible),
                    now,
                    now,
                    lease.campaign_id,
                    lease.scenario_id,
                    lease.owner,
                ),
            )
            connection.execute(
                """
                UPDATE attempts
                SET state = ?, ended_at_utc = ?, exit_code = ?,
                    exception_category = ?, concise_error = ?,
                    output_completeness = ?
                WHERE campaign_id = ? AND scenario_id = ? AND attempt_number = ?
                """,
                (
                    state,
                    now,
                    exit_code,
                    exception_category,
                    _concise(concise_error),
                    output_completeness,
                    lease.campaign_id,
                    lease.scenario_id,
                    lease.attempt_number,
                ),
            )
            self._insert_event(
                connection,
                lease.campaign_id,
                lease.scenario_id,
                "scenario_finalized",
                {
                    "attempt": lease.attempt_number,
                    "state": state,
                    "exit_code": exit_code,
                    "exception_category": exception_category,
                    "output_completeness": output_completeness,
                    "retry_eligible": retry_eligible,
                },
                now,
            )

    def recover_stale_leases(self, campaign_id: str) -> tuple[str, ...]:
        now = self._now_text()
        recovered: list[str] = []
        with self._transaction() as connection:
            rows = connection.execute(
                """
                SELECT scenario_id, state, attempt_count, max_attempts
                FROM scenarios
                WHERE campaign_id = ? AND state IN ('assigned','running')
                  AND lease_expires_at_utc IS NOT NULL AND lease_expires_at_utc < ?
                ORDER BY ordinal, scenario_id
                """,
                (campaign_id, now),
            ).fetchall()
            for row in rows:
                scenario_id = str(row[0])
                retry = True
                self._require_transition(str(row[1]), "interrupted")
                connection.execute(
                    """
                    UPDATE scenarios
                    SET state = 'interrupted', ended_at_utc = ?,
                        exception_category = 'stale_lease',
                        concise_error = 'execution lease expired before completion',
                        retry_eligible = ?, lease_owner = NULL,
                        lease_expires_at_utc = NULL, updated_at_utc = ?
                    WHERE campaign_id = ? AND scenario_id = ?
                    """,
                    (now, int(retry), now, campaign_id, scenario_id),
                )
                connection.execute(
                    """
                    UPDATE attempts
                    SET state = 'interrupted', ended_at_utc = ?,
                        exception_category = 'stale_lease',
                        concise_error = 'execution lease expired before completion'
                    WHERE campaign_id = ? AND scenario_id = ? AND ended_at_utc IS NULL
                    """,
                    (now, campaign_id, scenario_id),
                )
                self._insert_event(
                    connection,
                    campaign_id,
                    scenario_id,
                    "stale_lease_recovered",
                    {"retry_eligible": retry},
                    now,
                )
                recovered.append(scenario_id)
        return tuple(recovered)

    def mark_recovered_success(
        self,
        campaign_id: str,
        scenario_id: str,
        *,
        warnings: bool,
        output_completeness: str = "complete",
    ) -> None:
        target = "succeeded_with_warnings" if warnings else "succeeded"
        now = self._now_text()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state FROM scenarios WHERE campaign_id = ? AND scenario_id = ?",
                (campaign_id, scenario_id),
            ).fetchone()
            if row is None:
                raise CampaignStateError(f"unknown scenario {scenario_id}")
            current = str(row[0])
            if current in SUCCESS_STATES:
                return
            if current in LEASED_STATES:
                connection.execute(
                    """
                    UPDATE scenarios SET state = 'interrupted', lease_owner = NULL,
                        lease_expires_at_utc = NULL, retry_eligible = 0,
                        updated_at_utc = ?
                    WHERE campaign_id = ? AND scenario_id = ?
                    """,
                    (now, campaign_id, scenario_id),
                )
                current = "interrupted"
            if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
                if current in RETRY_SOURCE_STATES:
                    connection.execute(
                        "UPDATE scenarios SET state = 'pending' WHERE campaign_id = ? AND scenario_id = ?",
                        (campaign_id, scenario_id),
                    )
                    current = "pending"
                else:
                    raise CampaignStateError(
                        f"cannot recover completed artifacts from state {current}"
                    )
            self._require_transition(current, target)
            connection.execute(
                """
                UPDATE scenarios SET state = ?, ended_at_utc = ?,
                    output_completeness = ?, retry_eligible = 0,
                    lease_owner = NULL, lease_expires_at_utc = NULL,
                    concise_error = NULL, exception_category = NULL,
                    updated_at_utc = ?
                WHERE campaign_id = ? AND scenario_id = ?
                """,
                (target, now, output_completeness, now, campaign_id, scenario_id),
            )
            self._insert_event(
                connection,
                campaign_id,
                scenario_id,
                "completed_artifacts_recovered",
                {"state": target},
                now,
            )

    def invalidate_success(
        self,
        campaign_id: str,
        scenario_id: str,
        *,
        completeness: str,
        concise_error: str,
    ) -> None:
        now = self._now_text()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT state FROM scenarios WHERE campaign_id = ? AND scenario_id = ?",
                (campaign_id, scenario_id),
            ).fetchone()
            if row is None:
                raise CampaignStateError(f"unknown scenario {scenario_id}")
            current = str(row[0])
            if current not in SUCCESS_STATES:
                return
            self._require_transition(current, "invalid")
            connection.execute(
                """
                UPDATE scenarios SET state = 'invalid', output_completeness = ?,
                    exception_category = 'artifact_validation', concise_error = ?,
                    retry_eligible = 0, updated_at_utc = ?
                WHERE campaign_id = ? AND scenario_id = ?
                """,
                (
                    completeness,
                    _concise(concise_error),
                    now,
                    campaign_id,
                    scenario_id,
                ),
            )
            self._insert_event(
                connection,
                campaign_id,
                scenario_id,
                "completed_artifacts_invalidated",
                {"completion_state": completeness},
                now,
            )

    def request_stop(
        self,
        campaign_id: str,
        *,
        scenario_id: str | None = None,
        reason: str = "operator request",
    ) -> None:
        now = self._now_text()
        with self._transaction() as connection:
            if scenario_id is None:
                updated = connection.execute(
                    """
                    UPDATE campaigns SET stop_requested = 1, stop_reason = ?, updated_at_utc = ?
                    WHERE campaign_id = ?
                    """,
                    (_concise(reason), now, campaign_id),
                ).rowcount
                if updated != 1:
                    raise CampaignStateError(f"unknown campaign {campaign_id}")
                self._insert_event(
                    connection,
                    campaign_id,
                    None,
                    "campaign_stop_requested",
                    {"reason": _concise(reason)},
                    now,
                )
                return
            updated = connection.execute(
                """
                UPDATE scenarios SET stop_requested = 1, stop_reason = ?, updated_at_utc = ?
                WHERE campaign_id = ? AND scenario_id = ?
                """,
                (_concise(reason), now, campaign_id, scenario_id),
            ).rowcount
            if updated != 1:
                raise CampaignStateError(f"unknown scenario {scenario_id}")
            current_row = connection.execute(
                "SELECT state FROM scenarios WHERE campaign_id = ? AND scenario_id = ?",
                (campaign_id, scenario_id),
            ).fetchone()
            current = str(current_row[0])
            if current == "pending" or current in RETRY_SOURCE_STATES:
                self._require_transition(current, "stopped")
                connection.execute(
                    """
                    UPDATE scenarios
                    SET state = 'stopped', ended_at_utc = ?, retry_eligible = 0,
                        updated_at_utc = ?
                    WHERE campaign_id = ? AND scenario_id = ?
                    """,
                    (now, now, campaign_id, scenario_id),
                )
            self._insert_event(
                connection,
                campaign_id,
                scenario_id,
                "scenario_stop_requested",
                {"reason": _concise(reason)},
                now,
            )

    def stop_requested(self, campaign_id: str, scenario_id: str) -> tuple[bool, str | None]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT c.stop_requested, c.stop_reason, s.stop_requested, s.stop_reason
                FROM campaigns c JOIN scenarios s ON s.campaign_id = c.campaign_id
                WHERE c.campaign_id = ? AND s.scenario_id = ?
                """,
                (campaign_id, scenario_id),
            ).fetchone()
        if row is None:
            raise CampaignStateError(f"unknown scenario {scenario_id}")
        if bool(row[2]):
            return True, str(row[3] or "scenario stop requested")
        if bool(row[0]):
            return True, str(row[1] or "campaign stop requested")
        return False, None

    def reset_retry_eligible(
        self,
        campaign_id: str,
        *,
        scenario_ids: Sequence[str] | None = None,
    ) -> tuple[str, ...]:
        now = self._now_text()
        reset: list[str] = []
        with self._transaction() as connection:
            clauses = [
                "campaign_id = ?",
                "state IN ('failed_retryable','timeout','out_of_memory','interrupted')",
                "retry_eligible = 1",
                "(state = 'interrupted' OR attempt_count < max_attempts)",
                "stop_requested = 0",
            ]
            parameters: list[object] = [campaign_id]
            if scenario_ids:
                placeholders = ",".join("?" for _ in scenario_ids)
                clauses.append(f"scenario_id IN ({placeholders})")
                parameters.extend(scenario_ids)
            rows = connection.execute(
                f"SELECT scenario_id, state FROM scenarios WHERE {' AND '.join(clauses)} ORDER BY ordinal, scenario_id",
                parameters,
            ).fetchall()
            for scenario_id, current in rows:
                self._require_transition(str(current), "pending")
                connection.execute(
                    """
                    UPDATE scenarios SET state = 'pending', updated_at_utc = ?
                    WHERE campaign_id = ? AND scenario_id = ?
                    """,
                    (now, campaign_id, scenario_id),
                )
                self._insert_event(
                    connection,
                    campaign_id,
                    str(scenario_id),
                    "retry_queued",
                    {},
                    now,
                )
                reset.append(str(scenario_id))
        return tuple(reset)

    def record_event(
        self,
        campaign_id: str,
        scenario_id: str | None,
        event_type: str,
        payload: Mapping[str, object] | None = None,
    ) -> None:
        with self._transaction() as connection:
            self._insert_event(
                connection,
                campaign_id,
                scenario_id,
                event_type,
                payload or {},
                self._now_text(),
            )

    def scenario(self, campaign_id: str, scenario_id: str) -> ScenarioState:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM scenarios WHERE campaign_id = ? AND scenario_id = ?",
                (campaign_id, scenario_id),
            ).fetchone()
        if row is None:
            raise CampaignStateError(f"unknown scenario {scenario_id}")
        return _scenario_state(row)

    def scenarios(
        self,
        campaign_id: str,
        *,
        states: Sequence[str] | None = None,
    ) -> tuple[ScenarioState, ...]:
        clauses = ["campaign_id = ?"]
        parameters: list[object] = [campaign_id]
        if states:
            invalid = set(states) - STATES
            if invalid:
                raise CampaignStateError(f"unknown states: {sorted(invalid)}")
            placeholders = ",".join("?" for _ in states)
            clauses.append(f"state IN ({placeholders})")
            parameters.extend(states)
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM scenarios WHERE {' AND '.join(clauses)} ORDER BY ordinal, scenario_id",
                parameters,
            ).fetchall()
        return tuple(_scenario_state(row) for row in rows)

    def summary(self, campaign_id: str) -> dict[str, object]:
        with self._connect() as connection:
            campaign = connection.execute(
                "SELECT manifest_sha256, stop_requested, stop_reason FROM campaigns WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()
            if campaign is None:
                raise CampaignStateError(f"unknown campaign {campaign_id}")
            rows = connection.execute(
                """
                SELECT state, COUNT(*) FROM scenarios
                WHERE campaign_id = ? GROUP BY state ORDER BY state
                """,
                (campaign_id,),
            ).fetchall()
        counts = {str(state): int(count) for state, count in rows}
        return {
            "schema_version": "campaign-status-summary.v1",
            "campaign_id": campaign_id,
            "manifest_sha256": str(campaign[0]),
            "stop_requested": bool(campaign[1]),
            "stop_reason": campaign[2],
            "total_scenarios": sum(counts.values()),
            "state_counts": counts,
        }

    def events(
        self,
        campaign_id: str,
        *,
        scenario_id: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        query = "SELECT timestamp_utc, scenario_id, event_type, payload_json FROM events WHERE campaign_id = ?"
        parameters: list[object] = [campaign_id]
        if scenario_id is not None:
            query += " AND scenario_id = ?"
            parameters.append(scenario_id)
        query += " ORDER BY event_id"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return tuple(
            {
                "timestamp_utc": row[0],
                "scenario_id": row[1],
                "event_type": row[2],
                "payload": json.loads(row[3]),
            }
            for row in rows
        )

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode = WAL;
                PRAGMA synchronous = FULL;
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS artifact_schema_version(
                    version TEXT PRIMARY KEY
                );
                CREATE TABLE IF NOT EXISTS campaigns(
                    campaign_id TEXT PRIMARY KEY,
                    manifest_sha256 TEXT NOT NULL,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    stop_requested INTEGER NOT NULL DEFAULT 0 CHECK(stop_requested IN (0,1)),
                    stop_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS scenarios(
                    campaign_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    scenario_hash TEXT NOT NULL,
                    ordinal INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    worker_id TEXT,
                    hostname TEXT,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL,
                    started_at_utc TEXT,
                    ended_at_utc TEXT,
                    heartbeat_at_utc TEXT,
                    lease_owner TEXT,
                    lease_expires_at_utc TEXT,
                    exit_code INTEGER,
                    exception_category TEXT,
                    concise_error TEXT,
                    expected_artifacts_json TEXT NOT NULL,
                    output_completeness TEXT,
                    retry_eligible INTEGER NOT NULL DEFAULT 1 CHECK(retry_eligible IN (0,1)),
                    stop_requested INTEGER NOT NULL DEFAULT 0 CHECK(stop_requested IN (0,1)),
                    stop_reason TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY(campaign_id, scenario_id),
                    UNIQUE(campaign_id, ordinal),
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
                );
                CREATE TABLE IF NOT EXISTS attempts(
                    campaign_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    worker_id TEXT NOT NULL,
                    hostname TEXT NOT NULL,
                    lease_owner TEXT NOT NULL,
                    process_id INTEGER,
                    started_at_utc TEXT NOT NULL,
                    ended_at_utc TEXT,
                    exit_code INTEGER,
                    exception_category TEXT,
                    concise_error TEXT,
                    output_completeness TEXT,
                    PRIMARY KEY(campaign_id, scenario_id, attempt_number),
                    FOREIGN KEY(campaign_id, scenario_id)
                        REFERENCES scenarios(campaign_id, scenario_id)
                );
                CREATE TABLE IF NOT EXISTS events(
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    scenario_id TEXT,
                    timestamp_utc TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(campaign_id) REFERENCES campaigns(campaign_id)
                );
                CREATE INDEX IF NOT EXISTS idx_scenarios_queue
                    ON scenarios(campaign_id, state, retry_eligible, ordinal);
                CREATE INDEX IF NOT EXISTS idx_scenarios_lease
                    ON scenarios(campaign_id, lease_expires_at_utc);
                CREATE INDEX IF NOT EXISTS idx_events_campaign
                    ON events(campaign_id, scenario_id, event_id);
                """
            )
            rows = connection.execute(
                "SELECT version FROM artifact_schema_version"
            ).fetchall()
            if not rows:
                connection.execute(
                    "INSERT INTO artifact_schema_version(version) VALUES (?)",
                    (DATABASE_SCHEMA_VERSION,),
                )
            elif [str(row[0]) for row in rows] != [DATABASE_SCHEMA_VERSION]:
                raise CampaignStateError("unsupported campaign database schema")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 30000")
        return connection

    def _lease_row(
        self,
        connection: sqlite3.Connection,
        lease: ExecutionLease,
    ) -> sqlite3.Row:
        row = connection.execute(
            """
            SELECT state, lease_owner, attempt_count, scenario_hash
            FROM scenarios WHERE campaign_id = ? AND scenario_id = ?
            """,
            (lease.campaign_id, lease.scenario_id),
        ).fetchone()
        if row is None:
            raise CampaignStateError(f"unknown scenario {lease.scenario_id}")
        if row[1] != lease.owner or int(row[2]) != lease.attempt_number:
            raise CampaignStateError("execution lease is no longer owned by this worker")
        if row[3] != lease.scenario_hash:
            raise CampaignStateError("scenario hash changed after lease acquisition")
        return row

    def _insert_event(
        self,
        connection: sqlite3.Connection,
        campaign_id: str,
        scenario_id: str | None,
        event_type: str,
        payload: Mapping[str, object],
        timestamp_utc: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO events(campaign_id, scenario_id, timestamp_utc, event_type, payload_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                campaign_id,
                scenario_id,
                timestamp_utc,
                event_type,
                json.dumps(dict(payload), sort_keys=True, separators=(",", ":")),
            ),
        )

    def _require_transition(self, current: str, target: str) -> None:
        if current not in STATES or target not in STATES:
            raise CampaignStateError(f"unknown state transition {current!r} -> {target!r}")
        if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
            raise CampaignStateError(f"invalid state transition {current!r} -> {target!r}")

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None:
            raise CampaignStateError("campaign clock must return an aware datetime")
        return value.astimezone(timezone.utc)

    def _now_text(self) -> str:
        return _timestamp(self._now())


def _scenario_state(row: sqlite3.Row) -> ScenarioState:
    return ScenarioState(
        campaign_id=str(row["campaign_id"]),
        scenario_id=str(row["scenario_id"]),
        scenario_hash=str(row["scenario_hash"]),
        ordinal=int(row["ordinal"]),
        state=str(row["state"]),
        worker_id=row["worker_id"],
        hostname=row["hostname"],
        attempt_count=int(row["attempt_count"]),
        max_attempts=int(row["max_attempts"]),
        started_at_utc=row["started_at_utc"],
        ended_at_utc=row["ended_at_utc"],
        heartbeat_at_utc=row["heartbeat_at_utc"],
        lease_owner=row["lease_owner"],
        lease_expires_at_utc=row["lease_expires_at_utc"],
        exit_code=row["exit_code"],
        exception_category=row["exception_category"],
        concise_error=row["concise_error"],
        expected_artifacts=tuple(json.loads(row["expected_artifacts_json"])),
        output_completeness=row["output_completeness"],
        retry_eligible=bool(row["retry_eligible"]),
        stop_requested=bool(row["stop_requested"]),
        stop_reason=row["stop_reason"],
    )


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _concise(value: str | None, limit: int = 2000) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit] or None
