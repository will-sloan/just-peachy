"""Transactional state for the full-pipeline evaluation controller.

The store is deliberately independent from model code.  A controller process may
exit at any point; the next invocation can reclaim an expired lease while every
attempt directory remains available for diagnosis.
"""

from __future__ import annotations

from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Iterable, Iterator, Mapping, Sequence


JOB_STATES = (
    "pending",
    "running",
    "complete",
    "failed",
    "partial",
    "stopped",
)
TERMINAL_JOB_STATES = frozenset({"complete", "failed", "partial", "stopped"})
MEASUREMENT_MODES = ("accuracy", "resources")


class EvaluationStateCorruptionError(RuntimeError):
    """The durable campaign queue failed its SQLite integrity check."""


class _DatabaseRuntimeState:
    """Process-local coordination shared by every store for one database."""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.initialized = False


_DATABASE_RUNTIME_STATES: dict[str, _DatabaseRuntimeState] = {}
_DATABASE_RUNTIME_STATES_LOCK = threading.Lock()


def _database_runtime_state(path: Path) -> _DatabaseRuntimeState:
    key = os.path.normcase(str(path))
    with _DATABASE_RUNTIME_STATES_LOCK:
        state = _DATABASE_RUNTIME_STATES.get(key)
        if state is None:
            state = _DatabaseRuntimeState()
            _DATABASE_RUNTIME_STATES[key] = state
        return state


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class EvaluationJobSpec:
    job_id: str
    pipeline_id: str
    protocol_id: str
    split: str
    source_key: str
    measurement_mode: str
    seed: int
    case_count: int
    audio_duration_sec: float
    protocol_identity: str
    pipeline_identity: str
    reuse_identity: Mapping[str, object]
    case_ids: tuple[str, ...]
    result_relative_path: str

    def __post_init__(self) -> None:
        if self.measurement_mode not in MEASUREMENT_MODES:
            raise ValueError(
                f"unsupported measurement mode: {self.measurement_mode}"
            )
        if self.split not in {"development", "evaluation", "synthetic"}:
            raise ValueError(f"unsupported evaluation split: {self.split}")
        if self.case_count != len(self.case_ids):
            raise ValueError("case_count must equal the number of case IDs")
        if self.case_count < 1 or self.audio_duration_sec < 0:
            raise ValueError("jobs need at least one case and non-negative audio")

    def to_jsonable(self) -> dict[str, object]:
        value = asdict(self)
        value["case_ids"] = list(self.case_ids)
        value["reuse_identity"] = dict(self.reuse_identity)
        return value

    @classmethod
    def from_jsonable(cls, value: Mapping[str, object]) -> "EvaluationJobSpec":
        return cls(
            job_id=str(value["job_id"]),
            pipeline_id=str(value["pipeline_id"]),
            protocol_id=str(value["protocol_id"]),
            split=str(value["split"]),
            source_key=str(value["source_key"]),
            measurement_mode=str(value["measurement_mode"]),
            seed=int(value["seed"]),
            case_count=int(value["case_count"]),
            audio_duration_sec=float(value["audio_duration_sec"]),
            protocol_identity=str(value["protocol_identity"]),
            pipeline_identity=str(value["pipeline_identity"]),
            reuse_identity=dict(value["reuse_identity"]),  # type: ignore[arg-type]
            case_ids=tuple(str(item) for item in value.get("case_ids", [])),
            result_relative_path=str(value["result_relative_path"]),
        )


@dataclass(frozen=True)
class EvaluationJobState:
    spec: EvaluationJobSpec
    state: str
    attempt_count: int
    completed_cases: int
    completed_audio_sec: float
    started_at_utc: str | None
    updated_at_utc: str
    completed_at_utc: str | None
    lease_owner: str | None
    lease_expires_at_utc: str | None
    current_case_id: str | None
    latest_activity: str | None
    last_error: str | None
    rolling_rtf: float | None
    cpu_percent: float | None
    rss_mb: float | None
    queue_depth: int | None
    cache_hits: int
    retry_count: int
    result_sha256: str | None

    def to_jsonable(self) -> dict[str, object]:
        return {
            "spec": self.spec.to_jsonable(),
            "state": self.state,
            "attempt_count": self.attempt_count,
            "completed_cases": self.completed_cases,
            "completed_audio_sec": self.completed_audio_sec,
            "started_at_utc": self.started_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "completed_at_utc": self.completed_at_utc,
            "lease_owner": self.lease_owner,
            "lease_expires_at_utc": self.lease_expires_at_utc,
            "current_case_id": self.current_case_id,
            "latest_activity": self.latest_activity,
            "last_error": self.last_error,
            "rolling_rtf": self.rolling_rtf,
            "cpu_percent": self.cpu_percent,
            "rss_mb": self.rss_mb,
            "queue_depth": self.queue_depth,
            "cache_hits": self.cache_hits,
            "retry_count": self.retry_count,
            "result_sha256": self.result_sha256,
        }


class EvaluationStateStore:
    """SQLite-backed job state with leases and immutable attempt history."""

    SCHEMA_VERSION = "full-pipeline-evaluation-database.v1"

    def __init__(self, database_path: Path) -> None:
        self.database_path = Path(database_path).resolve()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._runtime_state = _database_runtime_state(self.database_path)
        with self._runtime_state.lock:
            if not self._runtime_state.initialized:
                bootstrap = (
                    not self.database_path.exists()
                    or self.database_path.stat().st_size == 0
                )
                self._initialize(bootstrap=bootstrap)
                self._runtime_state.initialized = True

    def prepare(
        self,
        jobs: Iterable[EvaluationJobSpec],
        *,
        campaign_id: str,
        manifest_sha256: str,
    ) -> dict[str, int]:
        inserted = 0
        unchanged = 0
        with self._transaction() as connection:
            self._bind_metadata(connection, "schema_version", self.SCHEMA_VERSION)
            self._bind_metadata(connection, "campaign_id", campaign_id)
            self._bind_metadata(connection, "manifest_sha256", manifest_sha256)
            for spec in jobs:
                payload = json.dumps(
                    spec.to_jsonable(), sort_keys=True, separators=(",", ":")
                )
                existing = connection.execute(
                    "SELECT spec_json FROM jobs WHERE job_id = ?", (spec.job_id,)
                ).fetchone()
                if existing is not None:
                    if str(existing["spec_json"]) != payload:
                        raise ValueError(
                            f"prepared job identity changed for {spec.job_id}"
                        )
                    unchanged += 1
                    continue
                connection.execute(
                    """
                    INSERT INTO jobs(
                        job_id, spec_json, pipeline_id, protocol_id, split,
                        source_key, measurement_mode, state, updated_at_utc
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
                    """,
                    (
                        spec.job_id,
                        payload,
                        spec.pipeline_id,
                        spec.protocol_id,
                        spec.split,
                        spec.source_key,
                        spec.measurement_mode,
                        utc_now(),
                    ),
                )
                inserted += 1
        return {"inserted": inserted, "unchanged": unchanged}

    def metadata(self) -> dict[str, str]:
        with self._runtime_state.lock:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    "SELECT key, value FROM metadata"
                ).fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

    def set_runtime_metadata(self, key: str, value: str | None) -> None:
        """Set mutable controller metadata without changing identity bindings."""

        if key in {"schema_version", "campaign_id", "manifest_sha256"}:
            raise ValueError(f"immutable metadata key: {key}")
        with self._transaction() as connection:
            if value is None:
                connection.execute("DELETE FROM metadata WHERE key = ?", (key,))
            else:
                connection.execute(
                    """
                    INSERT INTO metadata(key, value) VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, value),
                )

    def list_jobs(
        self,
        *,
        split: str | None = None,
        pipeline_ids: Sequence[str] = (),
        protocol_ids: Sequence[str] = (),
        source_keys: Sequence[str] = (),
        measurement_mode: str | None = None,
        states: Sequence[str] = (),
    ) -> tuple[EvaluationJobState, ...]:
        clauses: list[str] = []
        values: list[object] = []
        for column, single in (
            ("split", split),
            ("measurement_mode", measurement_mode),
        ):
            if single is not None:
                clauses.append(f"{column} = ?")
                values.append(single)
        for column, choices in (
            ("pipeline_id", pipeline_ids),
            ("protocol_id", protocol_ids),
            ("source_key", source_keys),
            ("state", states),
        ):
            if choices:
                clauses.append(
                    f"{column} IN ({','.join('?' for _ in choices)})"
                )
                values.extend(choices)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        query = "SELECT * FROM jobs" + where + " ORDER BY job_id"
        with self._runtime_state.lock:
            with closing(self._connect()) as connection:
                rows = connection.execute(query, tuple(values)).fetchall()
        return tuple(self._state(row) for row in rows)

    def reclaim_expired_leases(self) -> int:
        now = utc_now()
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET state = 'partial', lease_owner = NULL,
                    lease_expires_at_utc = NULL, updated_at_utc = ?,
                    latest_activity = 'expired lease reclaimed',
                    retry_count = retry_count + 1
                WHERE state = 'running' AND lease_expires_at_utc < ?
                """,
                (now, now),
            )
            return int(cursor.rowcount)

    def claim(
        self,
        job_id: str,
        *,
        owner: str,
        lease_seconds: int = 120,
    ) -> EvaluationJobState | None:
        now = datetime.now(timezone.utc)
        expiry = (now + timedelta(seconds=lease_seconds)).isoformat().replace(
            "+00:00", "Z"
        )
        now_text = now.isoformat().replace("+00:00", "Z")
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs
                SET state = 'running', attempt_count = attempt_count + 1,
                    started_at_utc = COALESCE(started_at_utc, ?),
                    updated_at_utc = ?, lease_owner = ?,
                    lease_expires_at_utc = ?, latest_activity = 'attempt claimed',
                    last_error = NULL
                WHERE job_id = ? AND state IN ('pending','failed','partial','stopped')
                """,
                (now_text, now_text, owner, expiry, job_id),
            )
            if cursor.rowcount != 1:
                return None
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
        return self._state(row)

    def heartbeat(
        self,
        job_id: str,
        *,
        owner: str,
        completed_cases: int,
        completed_audio_sec: float,
        current_case_id: str | None,
        latest_activity: str,
        rolling_rtf: float | None = None,
        cpu_percent: float | None = None,
        rss_mb: float | None = None,
        queue_depth: int | None = None,
        cache_hits: int | None = None,
        lease_seconds: int = 120,
    ) -> None:
        now = datetime.now(timezone.utc)
        expiry = (now + timedelta(seconds=lease_seconds)).isoformat().replace(
            "+00:00", "Z"
        )
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET
                    completed_cases = ?, completed_audio_sec = ?,
                    current_case_id = ?, latest_activity = ?, rolling_rtf = ?,
                    cpu_percent = ?, rss_mb = ?, queue_depth = ?,
                    cache_hits = COALESCE(?, cache_hits), updated_at_utc = ?,
                    lease_expires_at_utc = ?
                WHERE job_id = ? AND state = 'running' AND lease_owner = ?
                """,
                (
                    completed_cases,
                    completed_audio_sec,
                    current_case_id,
                    latest_activity,
                    rolling_rtf,
                    cpu_percent,
                    rss_mb,
                    queue_depth,
                    cache_hits,
                    now.isoformat().replace("+00:00", "Z"),
                    expiry,
                    job_id,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"lost evaluation-job lease: {job_id}")

    def finish(
        self,
        job_id: str,
        *,
        owner: str,
        state: str,
        completed_cases: int,
        completed_audio_sec: float,
        latest_activity: str,
        result_sha256: str | None = None,
        last_error: str | None = None,
    ) -> None:
        if state not in TERMINAL_JOB_STATES:
            raise ValueError(f"job cannot finish in state {state}")
        now = utc_now()
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET state = ?, completed_cases = ?,
                    completed_audio_sec = ?, updated_at_utc = ?,
                    completed_at_utc = ?, lease_owner = NULL,
                    lease_expires_at_utc = NULL, current_case_id = NULL,
                    latest_activity = ?, result_sha256 = ?, last_error = ?
                WHERE job_id = ? AND state = 'running' AND lease_owner = ?
                """,
                (
                    state,
                    completed_cases,
                    completed_audio_sec,
                    now,
                    now,
                    latest_activity,
                    result_sha256,
                    last_error,
                    job_id,
                    owner,
                ),
            )
            if cursor.rowcount != 1:
                raise RuntimeError(f"cannot finish unowned evaluation job: {job_id}")

    def mark_reused(self, job_id: str, *, result_sha256: str) -> None:
        now = utc_now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT spec_json FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if row is None:
                raise KeyError(job_id)
            spec = EvaluationJobSpec.from_jsonable(json.loads(row["spec_json"]))
            connection.execute(
                """
                UPDATE jobs SET state = 'complete', completed_cases = ?,
                    completed_audio_sec = ?, updated_at_utc = ?,
                    completed_at_utc = ?, lease_owner = NULL,
                    lease_expires_at_utc = NULL, current_case_id = NULL,
                    latest_activity = 'checksum-bound result reused',
                    result_sha256 = ?, last_error = NULL
                WHERE job_id = ?
                """,
                (
                    spec.case_count,
                    spec.audio_duration_sec,
                    now,
                    now,
                    result_sha256,
                    job_id,
                ),
            )

    def request_stop(self) -> None:
        with self._transaction() as connection:
            self._bind_metadata(connection, "stop_requested_at_utc", utc_now())

    def clear_stop(self) -> None:
        with self._transaction() as connection:
            connection.execute(
                "DELETE FROM metadata WHERE key = 'stop_requested_at_utc'"
            )

    def stop_requested(self) -> bool:
        return "stop_requested_at_utc" in self.metadata()

    def stop_not_running(self) -> int:
        now = utc_now()
        with self._transaction() as connection:
            cursor = connection.execute(
                """
                UPDATE jobs SET state = 'stopped', updated_at_utc = ?,
                    latest_activity = 'graceful stop requested'
                WHERE state IN ('pending','partial')
                """,
                (now,),
            )
            return int(cursor.rowcount)

    def record_attempt(
        self,
        *,
        job_id: str,
        attempt_number: int,
        state: str,
        attempt_path: Path,
        started_at_utc: str,
        ended_at_utc: str,
        error: str | None = None,
    ) -> None:
        with self._transaction() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO attempts(
                    job_id, attempt_number, state, attempt_path,
                    started_at_utc, ended_at_utc, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    attempt_number,
                    state,
                    str(Path(attempt_path)),
                    started_at_utc,
                    ended_at_utc,
                    error,
                ),
            )

    def attempt_rows(self) -> tuple[dict[str, object], ...]:
        with self._runtime_state.lock:
            with closing(self._connect()) as connection:
                rows = connection.execute(
                    "SELECT * FROM attempts ORDER BY job_id, attempt_number"
                ).fetchall()
        return tuple(dict(row) for row in rows)

    def assert_integrity(self) -> None:
        """Fail closed unless SQLite reports a fully readable queue."""

        with self._runtime_state.lock:
            with closing(self._connect()) as connection:
                self._assert_connection_integrity(connection)

    def _initialize(self, *, bootstrap: bool) -> None:
        try:
            with closing(self._connect()) as connection:
                try:
                    self._assert_connection_integrity(connection)
                    if bootstrap:
                        journal_mode = str(
                            connection.execute(
                                "PRAGMA journal_mode=DELETE"
                            ).fetchone()[0]
                        ).lower()
                        if journal_mode != "delete":
                            raise RuntimeError(
                                "campaign database refused rollback-journal mode: "
                                f"{journal_mode}"
                            )
                        connection.executescript(
                            """
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS jobs(
                    job_id TEXT PRIMARY KEY,
                    spec_json TEXT NOT NULL,
                    pipeline_id TEXT NOT NULL,
                    protocol_id TEXT NOT NULL,
                    split TEXT NOT NULL,
                    source_key TEXT NOT NULL,
                    measurement_mode TEXT NOT NULL,
                    state TEXT NOT NULL,
                    attempt_count INTEGER NOT NULL DEFAULT 0,
                    completed_cases INTEGER NOT NULL DEFAULT 0,
                    completed_audio_sec REAL NOT NULL DEFAULT 0,
                    started_at_utc TEXT,
                    updated_at_utc TEXT NOT NULL,
                    completed_at_utc TEXT,
                    lease_owner TEXT,
                    lease_expires_at_utc TEXT,
                    current_case_id TEXT,
                    latest_activity TEXT,
                    last_error TEXT,
                    rolling_rtf REAL,
                    cpu_percent REAL,
                    rss_mb REAL,
                    queue_depth INTEGER,
                    cache_hits INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    result_sha256 TEXT
                );
                CREATE TABLE IF NOT EXISTS attempts(
                    job_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    attempt_path TEXT NOT NULL,
                    started_at_utc TEXT NOT NULL,
                    ended_at_utc TEXT NOT NULL,
                    error TEXT,
                    PRIMARY KEY(job_id, attempt_number)
                );
                CREATE INDEX IF NOT EXISTS jobs_filters
                    ON jobs(split, pipeline_id, protocol_id, measurement_mode, state);
                COMMIT;
                """
                        )
                    else:
                        journal_mode = str(
                            connection.execute("PRAGMA journal_mode").fetchone()[0]
                        ).lower()
                        if journal_mode != "delete":
                            raise RuntimeError(
                                "existing campaign database uses unsupported "
                                f"journal mode {journal_mode!r}; expected 'delete'"
                            )
                    self._assert_required_schema(connection)
                    self._assert_connection_integrity(connection)
                except Exception:
                    if connection.in_transaction:
                        connection.rollback()
                    raise
        except EvaluationStateCorruptionError:
            raise
        except sqlite3.OperationalError as exc:
            if any(token in str(exc).lower() for token in ("busy", "locked")):
                raise
            raise EvaluationStateCorruptionError(
                f"campaign database is unreadable: {self.database_path}: {exc}"
            ) from exc
        except sqlite3.DatabaseError as exc:
            raise EvaluationStateCorruptionError(
                f"campaign database is unreadable: {self.database_path}: {exc}"
            ) from exc

    def _assert_required_schema(self, connection: sqlite3.Connection) -> None:
        required_tables = {"attempts", "jobs", "metadata"}
        present_tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        missing = sorted(required_tables - present_tables)
        if missing:
            raise EvaluationStateCorruptionError(
                f"campaign database schema is incomplete: {self.database_path}: "
                f"missing {', '.join(missing)}"
            )

    def _assert_connection_integrity(self, connection: sqlite3.Connection) -> None:
        try:
            rows = tuple(
                str(row[0]) for row in connection.execute("PRAGMA quick_check")
            )
        except sqlite3.DatabaseError as exc:
            raise EvaluationStateCorruptionError(
                f"campaign database integrity query failed: "
                f"{self.database_path}: {exc}"
            ) from exc
        if rows != ("ok",):
            detail = "; ".join(rows) if rows else "no integrity result"
            raise EvaluationStateCorruptionError(
                f"campaign database quick_check failed: "
                f"{self.database_path}: {detail}"
            )

    @staticmethod
    def _bind_metadata(
        connection: sqlite3.Connection, key: str, value: str
    ) -> None:
        existing = connection.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        if existing is not None and str(existing["value"]) != value:
            raise ValueError(f"campaign metadata changed for {key}")
        connection.execute(
            "INSERT OR IGNORE INTO metadata(key, value) VALUES (?, ?)",
            (key, value),
        )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._runtime_state.lock:
            connection = self._connect()
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=30.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA busy_timeout=30000")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
        except Exception:
            connection.close()
            raise
        return connection

    @staticmethod
    def _state(row: sqlite3.Row) -> EvaluationJobState:
        return EvaluationJobState(
            spec=EvaluationJobSpec.from_jsonable(json.loads(row["spec_json"])),
            state=str(row["state"]),
            attempt_count=int(row["attempt_count"]),
            completed_cases=int(row["completed_cases"]),
            completed_audio_sec=float(row["completed_audio_sec"]),
            started_at_utc=row["started_at_utc"],
            updated_at_utc=str(row["updated_at_utc"]),
            completed_at_utc=row["completed_at_utc"],
            lease_owner=row["lease_owner"],
            lease_expires_at_utc=row["lease_expires_at_utc"],
            current_case_id=row["current_case_id"],
            latest_activity=row["latest_activity"],
            last_error=row["last_error"],
            rolling_rtf=(
                float(row["rolling_rtf"])
                if row["rolling_rtf"] is not None
                else None
            ),
            cpu_percent=(
                float(row["cpu_percent"])
                if row["cpu_percent"] is not None
                else None
            ),
            rss_mb=float(row["rss_mb"]) if row["rss_mb"] is not None else None,
            queue_depth=(
                int(row["queue_depth"])
                if row["queue_depth"] is not None
                else None
            ),
            cache_hits=int(row["cache_hits"]),
            retry_count=int(row["retry_count"]),
            result_sha256=row["result_sha256"],
        )
