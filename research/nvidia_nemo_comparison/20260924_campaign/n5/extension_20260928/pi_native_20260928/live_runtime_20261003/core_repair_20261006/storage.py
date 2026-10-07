"""Capacity-governed, restart-persistent audio sessions. See README_STORAGE.md.

No native audio, network, NumPy, model, or GUI imports. Processed audio is mono
little-endian float32; each sealed segment also has a PCM16 replay WAV. Callers
must stop capture and drain their bounded queue before calling ``stop``.
"""
from __future__ import annotations

import array
import base64
import contextlib
from dataclasses import dataclass
import json
import itertools
import hashlib
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import threading
import time
import uuid
import wave
import zipfile
import zlib

from storage_support import annotate_error, ensure_sqlite_file_limit


class StorageError(RuntimeError):
    pass


class CapacityError(StorageError):
    pass


class ActiveSessionError(StorageError):
    pass


class UnsafePathError(StorageError):
    pass


@dataclass(frozen=True)
class StoragePolicy:
    reserve_bytes: int = 5 * 1024 * 1024 * 1024
    reserve_fraction: float = 0.05
    segment_samples: int = 160000
    max_append_bytes: int = 4 * 1024 * 1024
    max_page_size: int = 100
    max_export_sessions: int = 1000
    metadata_allowance_bytes: int = 1024 * 1024
    max_export_entries: int = 16384

    def __post_init__(self):
        if self.reserve_bytes < 0 or not 0 <= self.reserve_fraction < 1:
            raise ValueError("invalid free-space reserve")
        for name in ("segment_samples", "max_append_bytes", "max_page_size",
                     "max_export_sessions", "max_export_entries", "metadata_allowance_bytes"):
            if getattr(self, name) <= 0:
                raise ValueError(name + " must be positive")

    def reserve(self, total_bytes: int) -> int:
        return max(self.reserve_bytes, math.ceil(total_bytes * self.reserve_fraction))

    def estimate_bytes(self, spec: dict) -> int:
        """Conservative logical disk allocation, including replay and metadata."""
        spec = _validate_spec(spec)
        frames = math.ceil(spec["duration_seconds"] * spec["sample_rate"])
        segments = math.ceil(frames / self.segment_samples)
        # Exact f32 plus PCM16, headers, per-file allocation and SQLite rows.
        size = frames * 6 + segments * (44 + 3 * 4096)
        if spec["mode"] == "raw_processed":
            raw = spec["raw"]
            raw_frames = math.ceil(spec["duration_seconds"] * raw["sample_rate"])
            size += raw_frames * raw["channels"] * raw["sample_width_bytes"]
            size += math.ceil(raw_frames / self.segment_samples) * 2 * 4096
        return (size + self.metadata_allowance_bytes + spec.get("metadata_reserve_bytes", 0)
                + metadata_limits(spec, self.metadata_allowance_bytes)["terminal_sqlite_bytes"])


def metadata_limits(spec, metadata_allowance_bytes):
    """Disjoint text/SQLite allocations; absent version preserves legacy policy."""
    reserve = spec.get('metadata_reserve_bytes', 0)
    if type(reserve) is not int or reserve < 0:
        raise ValueError('metadata_reserve_bytes must be a nonnegative integer')
    if type(metadata_allowance_bytes) is not int or metadata_allowance_bytes < 0:
        raise ValueError('metadata_allowance_bytes must be a nonnegative integer')
    terminal = spec.get('terminal_metadata_reserve_bytes', 0)
    if type(terminal) is not int or terminal not in (0, 256*1024):
        raise ValueError('Explicit independent terminal metadata reserve must be 0 or 256 KiB')
    if 'metadata_split' not in spec:
        sqlite_reserve = reserve // 6
    elif spec['metadata_split'] == 'text3_sqlite1_v1':
        sqlite_reserve = reserve // 4
    elif spec['metadata_split'] == 'text1_sqlite1_v2':
        sqlite_reserve = reserve // 2
    else:
        raise ValueError('Unknown explicit metadata_split')
    return dict(text_bytes=reserve-sqlite_reserve,
                sqlite_bytes=sqlite_reserve+metadata_allowance_bytes,
                terminal_sqlite_bytes=terminal)


def _validate_spec(spec):
    # JSON copy prevents later mutation by a caller and rejects opaque objects.
    result = json.loads(json.dumps(spec, allow_nan=False))
    result.setdefault("sample_rate", 16000)
    result.setdefault("mode", "processed")
    if not isinstance(result["sample_rate"], int) or not 1 <= result["sample_rate"] <= 384000:
        raise ValueError("sample_rate must be an integer in 1..384000")
    duration = result.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("duration_seconds must be a finite positive allocation")
    if result["mode"] not in ("processed", "raw_processed"):
        raise ValueError("mode must be processed or raw_processed")
    metadata_limits(result, 0)
    if result["mode"] == "raw_processed":
        raw = result.get("raw", {})
        if not isinstance(raw, dict):
            raise ValueError("raw specification is required")
        for key in ("sample_rate", "channels", "sample_width_bytes"):
            if not isinstance(raw.get(key), int) or isinstance(raw.get(key), bool) or raw[key] <= 0:
                raise ValueError("raw." + key + " must be a positive integer")
        if raw["sample_rate"] > 384000 or raw["channels"] > 64 or raw["sample_width_bytes"] > 8:
            raise ValueError("raw format exceeds supported metadata bounds")
        if not isinstance(raw.get("encoding"), str) or not raw["encoding"]:
            raise ValueError("raw.encoding is required")
        qualification = raw.get("qualification", {})
        experimental = (result.get('raw_qualification') is True and isinstance(qualification, dict)
                        and qualification.get('qualified') is False and qualification.get('qualification_run') is True
                        and bool(qualification.get('evidence')))
        if not isinstance(qualification, dict) or (qualification.get("qualified") is not True and not experimental) or len(qualification) < 2:
            raise ValueError("qualified raw requires qualification evidence metadata")
    if len(json.dumps(result).encode("utf-8")) > 65536:
        raise ValueError("session specification exceeds 64 KiB")
    return result


def _safe(path: Path):
    """Reject symlinks and Windows junction/reparse points along the entire path."""
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise UnsafePathError("symlink/reparse path refused: " + str(item))
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            raise UnsafePathError("hard-linked file refused: " + str(item))
    return path


def _sync_dir(path):
    # Windows file fsync is supported; directory fsync is not exposed by Python.
    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _atomic_json(path, value):
    _safe(path)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, sort_keys=True, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _sync_dir(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _pack_event(raw):
    """Independent fast lossless rows; only bounded64KiB JSON is compressed."""
    data=raw.encode('utf-8')
    compressed=zlib.compress(data,1) if len(data)<=65536 else data
    if len(compressed)+128<len(data):payload,encoding=compressed,'zlib-json-v1'
    else:payload,encoding=raw,'json'
    return payload,encoding,len(data),hashlib.sha256(data).hexdigest()


def _unpack_event(row):
    encoding=row.get('payload_encoding','json')
    length=row.get('payload_bytes',0)
    payload=row['payload']
    if encoding=='zlib-json-v1':
        if type(length) is not int or not 0<length<=65536 or not isinstance(payload,bytes) or len(payload)>65536:
            raise StorageError('Compressed event length/type bound')
        decoder=zlib.decompressobj()
        try:raw=decoder.decompress(payload,length+1)
        except zlib.error as error:raise StorageError('Corrupt compressed event') from error
        if len(raw)!=length or not decoder.eof or decoder.unconsumed_tail or decoder.unused_data:
            raise StorageError('Compressed event length/trailing-data integrity failed')
    elif encoding=='json':
        if not isinstance(payload,str):raise StorageError('Plain event must be JSON text')
        raw=payload.encode('utf-8')
        if len(raw)>262144 or length and length!=len(raw):raise StorageError('Plain event length bound')
    else:raise StorageError('Unknown event encoding')
    digest=row.get('payload_sha256')
    if encoding=='zlib-json-v1' and (not isinstance(digest,str) or not re.fullmatch(r'[0-9a-f]{64}',digest)):
        raise StorageError('Compressed event requires its exact SHA256')
    if digest is not None and hashlib.sha256(raw).hexdigest()!=digest:
        raise StorageError('Event payload SHA256 differs')
    return json.loads(raw)


class _Lease:
    """Kernel-held, nonblocking lease; death releases it without guessing PIDs."""
    def __init__(self, path, *, shared=False):
        _safe(path)
        self.file = open(path, "rb" if shared else "a+b")
        try:
            if os.name == "nt":
                import ctypes
                import msvcrt
                from ctypes import wintypes
                class Overlapped(ctypes.Structure):
                    _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                                ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD), ('hEvent', wintypes.HANDLE)]
                self._overlapped = Overlapped()
                self._kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                self._kernel.LockFileEx.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(Overlapped)]
                self._kernel.UnlockFileEx.argtypes = [wintypes.HANDLE,wintypes.DWORD,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(Overlapped)]
                self._handle = msvcrt.get_osfhandle(self.file.fileno())
                # CRT LK_NBRLCK behaves exclusively on Windows; LockFileEx
                # supplies actual shared reads against the same byte-zero lease.
                if not self._kernel.LockFileEx(self._handle, 1 | (0 if shared else 2), 0, 1, 0, ctypes.byref(self._overlapped)):
                    raise ctypes.WinError(ctypes.get_last_error())
            else:
                import fcntl
                fcntl.flock(self.file.fileno(), (fcntl.LOCK_SH if shared else fcntl.LOCK_EX) | fcntl.LOCK_NB)
        except OSError as error:
            self.file.close()
            self.file = None
            raise ActiveSessionError("session/store is in use") from error

    def close(self):
        if self.file is not None:
            try:
                if os.name == "nt":
                    import ctypes
                    if not self._kernel.UnlockFileEx(self._handle, 0, 1, 0, ctypes.byref(self._overlapped)):
                        raise ctypes.WinError(ctypes.get_last_error())
                else:
                    import fcntl
                    fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            finally:
                self.file.close()
                self.file = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class SessionStore:
    """An owned local directory with SQLite-indexed history and bounded reads."""
    def __init__(self, root, policy=None, *, read_only=False):
        self.root = _safe(Path(root).absolute())
        self.policy = policy or StoragePolicy()
        self._mutex = threading.RLock()
        self._spool = None
        self.read_only = read_only
        if read_only:
            if not self.root.is_dir():
                raise UnsafePathError('Existing owned read-only store required')
        else:
            self.root.mkdir(parents=True, exist_ok=True)
        marker = self.root / "store.json"
        if not marker.exists():
            if read_only:
                raise UnsafePathError('Existing store marker required')
            # Never adopt an existing nonempty, unrelated data directory.
            if next(self.root.iterdir(), None) is not None:
                raise UnsafePathError("store root must be empty or already owned")
            owner = {"schema": 1, "store_id": uuid.uuid4().hex}
            with marker.open("x", encoding="utf-8") as output:
                json.dump(owner, output)
                output.flush()
                os.fsync(output.fileno())
            _sync_dir(self.root)
        _safe(marker)
        self.owner = json.loads(marker.read_text(encoding="utf-8"))
        if self.owner.get("schema") != 1 or not re.fullmatch(r"[0-9a-f]{32}", self.owner.get("store_id", "")):
            raise UnsafePathError("unrecognized store marker")
        for name in ("sessions", "locks"):
            path = _safe(self.root / name)
            if read_only:
                if not path.is_dir():
                    raise UnsafePathError('Existing store directories required')
            else:
                path.mkdir(exist_ok=True)
        self.db_path = _safe(self.root / "history.sqlite3")
        if read_only:
            if not self.db_path.is_file():
                raise UnsafePathError('Existing history database required')
            return
        with self._db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL, status TEXT NOT NULL,
                    created REAL NOT NULL, updated REAL NOT NULL,
                    spec TEXT NOT NULL, processed_samples INTEGER NOT NULL DEFAULT 0,
                    raw_samples INTEGER NOT NULL DEFAULT 0,
                    include_raw INTEGER NOT NULL DEFAULT 0, reason TEXT);
                CREATE INDEX IF NOT EXISTS sessions_status ON sessions(status, seq);
                CREATE TABLE IF NOT EXISTS segments (
                    session_id TEXT NOT NULL, kind TEXT NOT NULL,
                    idx INTEGER NOT NULL, start_sample INTEGER NOT NULL,
                    samples INTEGER NOT NULL, data_name TEXT NOT NULL,
                    replay_name TEXT, PRIMARY KEY(session_id,kind,idx));
                CREATE INDEX IF NOT EXISTS segments_samples ON segments(session_id,kind,start_sample);
                CREATE TABLE IF NOT EXISTS captions (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    caption_id TEXT NOT NULL, revision INTEGER NOT NULL,
                    start_sample INTEGER NOT NULL, end_sample INTEGER NOT NULL,
                    text TEXT NOT NULL, speaker TEXT, provisional INTEGER NOT NULL,
                    provenance TEXT NOT NULL, UNIQUE(session_id,caption_id));
                CREATE INDEX IF NOT EXISTS captions_page ON captions(session_id,seq);
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
                    created REAL NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL,
                    payload_encoding TEXT NOT NULL DEFAULT 'json',payload_bytes INTEGER NOT NULL DEFAULT 0,
                    payload_sha256 TEXT);
                CREATE INDEX IF NOT EXISTS events_page ON events(session_id,seq);
                CREATE INDEX IF NOT EXISTS events_type_page ON events(session_id,event_type,seq);
                CREATE TABLE IF NOT EXISTS artifacts (
                    session_id TEXT NOT NULL, path TEXT NOT NULL, role TEXT NOT NULL,
                    bytes INTEGER NOT NULL, PRIMARY KEY(session_id,path));
                CREATE TABLE IF NOT EXISTS metadata_usage (
                    session_id TEXT PRIMARY KEY, used_bytes INTEGER NOT NULL,
                    limit_bytes INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS terminal_metadata_usage (
                    session_id TEXT PRIMARY KEY, used_bytes INTEGER NOT NULL,
                    limit_bytes INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS terminal_events (
                    session_id TEXT NOT NULL, event_type TEXT NOT NULL,
                    seq INTEGER NOT NULL, payload_sha256 TEXT NOT NULL,
                    PRIMARY KEY(session_id,event_type));
                CREATE TABLE IF NOT EXISTS caption_projections (
                    session_id TEXT NOT NULL, parent_key TEXT NOT NULL,
                    revision INTEGER NOT NULL, payload_sha256 TEXT NOT NULL,
                    source_start_sample INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY(session_id,parent_key));
            """)
            columns={row['name'] for row in db.execute('PRAGMA table_info(events)')}
            for name,declaration in (('payload_encoding',"TEXT NOT NULL DEFAULT 'json'"),
                                     ('payload_bytes','INTEGER NOT NULL DEFAULT 0'),('payload_sha256','TEXT')):
                if name not in columns:db.execute('ALTER TABLE events ADD COLUMN '+name+' '+declaration)
            caption_columns={row['name'] for row in db.execute('PRAGMA table_info(captions)')}
            if 'projection_parent' not in caption_columns:
                db.execute('ALTER TABLE captions ADD COLUMN projection_parent TEXT')
            if 'projection_order' not in caption_columns:
                db.execute('ALTER TABLE captions ADD COLUMN projection_order INTEGER NOT NULL DEFAULT 0')
            if 'projection_source_start' not in caption_columns:
                db.execute('ALTER TABLE captions ADD COLUMN projection_source_start INTEGER')
            projection_columns={row['name'] for row in db.execute('PRAGMA table_info(caption_projections)')}
            if 'source_start_sample' not in projection_columns:
                db.execute('ALTER TABLE caption_projections ADD COLUMN source_start_sample INTEGER NOT NULL DEFAULT 0')
            db.execute('CREATE INDEX IF NOT EXISTS caption_projection_parent ON captions(session_id,projection_parent)')
            db.execute('CREATE INDEX IF NOT EXISTS caption_source_order ON captions(session_id,start_sample,COALESCE(projection_parent,caption_id),projection_order,caption_id)')
            db.execute('CREATE INDEX IF NOT EXISTS caption_frozen_parent ON captions(session_id,COALESCE(projection_parent,caption_id),start_sample,projection_order,caption_id)')
            db.execute('CREATE INDEX IF NOT EXISTS caption_projection_source_order ON captions(session_id,COALESCE(projection_source_start,start_sample),COALESCE(projection_parent,caption_id),projection_order,caption_id)')
            db.execute('CREATE INDEX IF NOT EXISTS caption_projection_frozen_order ON captions(session_id,COALESCE(projection_parent,caption_id),COALESCE(projection_source_start,start_sample),projection_order,caption_id)')
        for name in ('deletions', 'deletion_receipts'):
            _safe(self.root / name).mkdir(exist_ok=True)
        self.recover_deletions()

    def _charge_metadata(self, db, session_id, amount, *, closing=False):
        """Cumulative metadata accounting; historical quota fields are evidence.

        Ordinary use is governed by actual free space, not a duration-derived
        logical metadata quota. Retained limit_bytes values are not rewritten.
        """
        prior=db.execute('SELECT used_bytes,limit_bytes FROM metadata_usage WHERE session_id=?',(session_id,)).fetchone()
        if prior is None:
            spec=json.loads(db.execute('SELECT spec FROM sessions WHERE id=?',(session_id,)).fetchone()[0])
            limit=metadata_limits(spec,self.policy.metadata_allowance_bytes)['sqlite_bytes']
            # Migrate only the explicitly written session, using indexed sums;
            # startup never scans historical sessions or loads their payloads.
            used=db.execute('SELECT COALESCE(SUM(2*LENGTH(CAST(payload AS BLOB))+1024),0) FROM events AS e WHERE session_id=? AND NOT EXISTS (SELECT 1 FROM terminal_events AS t WHERE t.session_id=e.session_id AND t.seq=e.seq)',(session_id,)).fetchone()[0]
            used+=db.execute('SELECT COALESCE(SUM(2*(LENGTH(CAST(text AS BLOB))+LENGTH(CAST(provenance AS BLOB)))+1024),0) FROM captions WHERE session_id=?',(session_id,)).fetchone()[0]
            used+=db.execute('SELECT COALESCE(SUM(2*(LENGTH(CAST(path AS BLOB))+LENGTH(CAST(role AS BLOB)))+1024),0) FROM artifacts WHERE session_id=?',(session_id,)).fetchone()[0]
        else:used,limit=prior
        db.execute('INSERT INTO metadata_usage VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE SET used_bytes=excluded.used_bytes',
                   (session_id,used+amount,limit))

    @contextlib.contextmanager
    def _db(self, operation='SQLite transaction'):
        db = primary = None
        try:
            for name in ("history.sqlite3", "history.sqlite3-journal", "history.sqlite3-wal", "history.sqlite3-shm"):
                _safe(self.root / name)
            if not self.read_only:
                ensure_sqlite_file_limit(self.root, self.policy)
            db = sqlite3.connect(self.db_path.as_uri()+'?mode=ro', uri=True, timeout=10) if self.read_only else sqlite3.connect(self.db_path, timeout=10)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON" if self.read_only else "PRAGMA synchronous=FULL")
            with db:
                yield db
        except BaseException as error:
            primary = error
            annotate_error(error, operation=operation, database=self.db_path)
            raise
        finally:
            if db is not None:
                try:
                    db.close()
                except BaseException as error:
                    if primary is None:
                        annotate_error(error, operation='SQLite connection close', database=self.db_path)
                        raise
                    primary.add_note('SQLite connection close also failed: '+repr(error))

    def _session_dir(self, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[0-9a-f]{32}", session_id):
            raise UnsafePathError("invalid session identifier")
        path = _safe(self.root / "sessions" / session_id)
        if path.exists():
            marker = _safe(path / "owner.json")
            owner = json.loads(marker.read_text(encoding="utf-8"))
            if owner != {"store_id": self.owner["store_id"], "session_id": session_id}:
                raise UnsafePathError("session does not belong to this store")
        return path

    def _session_lease(self, session_id, *, shared=False):
        if self.read_only and not shared:
            raise StorageError('Read-only store requires a shared session lease')
        self._session_dir(session_id)
        return _Lease(self.root / "locks" / (session_id + ".lock"), shared=shared)

    def _audio_path(self, session_id, name):
        if not isinstance(name, str) or not re.fullmatch(r"(?:processed|raw)-\d{8}\.(?:f32|wav|bin)(?:\.part)?", name):
            raise UnsafePathError("invalid audio filename")
        return _safe(self._session_dir(session_id) / name)

    def _artifact_path(self, session_id, relative_path):
        if not isinstance(relative_path, str) or not 1 <= len(relative_path) <= 1024 or "\\" in relative_path or ":" in relative_path:
            raise UnsafePathError("artifact path must be a relative POSIX path")
        parts = relative_path.split("/")
        if any(part in ("", ".", "..") for part in parts) or parts[0] != "work":
            raise UnsafePathError("artifacts must be descendants of the owned work directory")
        return _safe(self._session_dir(session_id).joinpath(*parts))

    def register_artifact(self, session_id, relative_path, role="native"):
        """Register one completed metadata file beneath this session's work/."""
        self.read(session_id)
        path = self._artifact_path(session_id, relative_path)
        if not path.is_file() or not isinstance(role, str) or not 1 <= len(role) <= 128:
            raise ValueError("artifact must be a completed file with a bounded role")
        size = path.stat().st_size
        self._capacity(65536)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT role,bytes FROM artifacts WHERE session_id=? AND path=?',(session_id,relative_path)).fetchone()
            if prior is None or tuple(prior)!=(role,size):
                self._charge_metadata(db,session_id,2*len(json.dumps(dict(path=relative_path,role=role,bytes=size)).encode())+1024,closing=True)
            db.execute("INSERT INTO artifacts VALUES(?,?,?,?) ON CONFLICT(session_id,path) DO UPDATE SET role=excluded.role,bytes=excluded.bytes",
                       (session_id, relative_path, role, size))
        return {"path": relative_path, "role": role, "bytes": size}

    def _artifacts(self, session_id):
        after=''
        while True:
            with self._db() as db:
                rows=db.execute('SELECT path,role,bytes FROM artifacts WHERE session_id=? AND path>? ORDER BY path LIMIT 32',
                                (session_id,after)).fetchall()
            if not rows:break
            for row in rows:yield dict(row)
            after=rows[-1]['path']

    def _capacity(self, required=0, path=None):
        usage = shutil.disk_usage(path or self.root)
        reserve = self.policy.reserve(usage.total)
        if usage.free - required < reserve:
            raise CapacityError("insufficient free space: need %d bytes plus %d reserve, have %d" % (required, reserve, usage.free))
        return {"total_bytes": usage.total, "free_bytes": usage.free,
                "reserve_bytes": reserve, "available_bytes": max(0, usage.free - reserve),
                "required_bytes": required}

    def capacity(self, spec=None):
        return self._capacity(self.policy.estimate_bytes(spec) if spec else 0)

    def begin(self, spec):
        if self.read_only:
            raise StorageError('Read-only store cannot begin a recording')
        spec = _validate_spec(spec)
        lease = _Lease(self.root / "active.lock")
        session_id = uuid.uuid4().hex
        directory = self._session_dir(session_id)
        try:
            with self._mutex:
                # Only an active row can be abandoned. No filesystem history scan.
                with self._db() as db:
                    stale = db.execute("SELECT id FROM sessions WHERE status='active' LIMIT 1").fetchone()
                if stale:
                    self._fail_abandoned(stale["id"])
                required = self.policy.estimate_bytes(spec)
                self._capacity(required)
                directory.mkdir()
                _atomic_json(directory / "owner.json", {"store_id": self.owner["store_id"], "session_id": session_id})
                _atomic_json(directory / "spec.json", spec)
                now = time.time()
                with self._db() as db:
                    db.execute("INSERT INTO sessions(id,status,created,updated,spec) VALUES(?,?,?,?,?)",
                               (session_id, "active", now, now, json.dumps(spec, sort_keys=True)))
                spool = SessionSpool(self, session_id, spec, lease, required)
                self._spool = spool
                return spool
        except BaseException as error:
            try:
                lease.close()
            except BaseException as secondary:
                error.add_note('Begin failure lease cleanup also failed: '+repr(secondary))
            raise

    def _fail_abandoned(self, session_id):
        # Crash receipts count only indexed, durably sealed segments.
        with self._session_lease(session_id):
            with self._db() as db:
                db.execute("UPDATE sessions SET status='failed',reason=?,updated=? WHERE id=?",
                           ("owner exited before stop/drain publication", time.time(), session_id))
            self._publish(session_id)

    def read(self, session_id):
        self._session_dir(session_id)
        with self._db() as db:
            row = db.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if row is None:
            raise KeyError(session_id)
        return self._metadata(row)

    @staticmethod
    def _metadata(row):
        value = dict(row)
        value["session_id"] = value.pop("id")
        value["spec"] = json.loads(value["spec"])
        value["include_raw"] = bool(value["include_raw"])
        value["duration_seconds"] = value["processed_samples"] / value["spec"]["sample_rate"]
        return value

    def history(self, limit=25, before=None):
        if not isinstance(limit, int) or not 1 <= limit <= self.policy.max_page_size:
            raise ValueError("history limit exceeds bounded page size")
        if before is not None and (not isinstance(before, int) or before <= 0):
            raise ValueError("before must be a positive sequence cursor")
        with self._db() as db:
            rows = db.execute("SELECT * FROM sessions WHERE seq<? ORDER BY seq DESC LIMIT ?",
                              (before or 9223372036854775807, limit + 1)).fetchall()
        items = [self._metadata(row) for row in rows[:limit]]
        return {"items": items, "next_cursor": items[-1]["seq"] if len(rows) > limit else None}

    def write_caption(self, session_id, caption_id, start_sample, end_sample,
                      text, speaker=None, provisional=True, provenance=None):
        """Upsert a stable source-time caption and preserve every revision event."""
        self.read(session_id)
        if not isinstance(caption_id, str) or not 1 <= len(caption_id) <= 128:
            raise ValueError("caption_id must be 1..128 characters")
        if not isinstance(start_sample, int) or not isinstance(end_sample, int) or not 0 <= start_sample <= end_sample:
            raise ValueError("invalid caption sample interval")
        if not isinstance(text, str) or len(text.encode("utf-8")) > 65536:
            raise ValueError("caption text exceeds 64 KiB")
        if speaker is not None and (not isinstance(speaker, str) or len(speaker) > 256):
            raise ValueError("invalid speaker label")
        provenance_json = self._payload(provenance or {})
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            prior = db.execute("SELECT * FROM captions WHERE session_id=? AND caption_id=?", (session_id, caption_id)).fetchone()
            same=prior is not None and all(prior[key]==value for key,value in dict(start_sample=start_sample,
                end_sample=end_sample,text=text,speaker=speaker,provisional=int(bool(provisional)),provenance=provenance_json).items())
            revision = prior['revision'] + (not same) if prior else 1
            value = {"caption_id": caption_id, "revision": revision, "start_sample": start_sample,
                     "end_sample": end_sample, "text": text, "speaker": speaker,
                     "provisional": bool(provisional), "provenance": json.loads(provenance_json)}
            if same:return value
            self._capacity(len(text.encode("utf-8")) * 8 + len(provenance_json.encode()) * 3 + 65536)
            event_json=json.dumps(value,allow_nan=False)
            packed=_pack_event(event_json)
            packed_size=len(packed[0].encode()) if isinstance(packed[0],str) else len(packed[0])
            self._charge_metadata(db,session_id,2*(packed_size+len(text.encode())+len(provenance_json.encode()))+2048)
            db.execute("""INSERT INTO captions(session_id,caption_id,revision,start_sample,end_sample,text,speaker,provisional,provenance)
                          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(session_id,caption_id) DO UPDATE SET
                          revision=excluded.revision,start_sample=excluded.start_sample,end_sample=excluded.end_sample,
                          text=excluded.text,speaker=excluded.speaker,provisional=excluded.provisional,provenance=excluded.provenance""",
                       (session_id, caption_id, revision, start_sample, end_sample, text, speaker, int(bool(provisional)), provenance_json))
            db.execute("INSERT INTO events(session_id,created,event_type,payload,payload_encoding,payload_bytes,payload_sha256) VALUES(?,?,?,?,?,?,?)",
                       (session_id, time.time(), "caption_revision", *packed))
        return value

    def replace_caption_projection(self, session_id, parent_key, parts, *, projection_revision=None,
                                   projection_source_start_sample=None):
        """Atomically replace one parent's visible spans; preserve revision events.

        An identical delivery spends no metadata and emits no event. Explicit
        revisions are monotonic presentation revisions, independent of ASR text
        revisions; delayed speaker changes can therefore revise the same words.
        """
        self.read(session_id)
        if type(parent_key) is not str or not 1 <= len(parent_key) <= 128:
            raise ValueError('Bounded projection parent required')
        if projection_revision is not None and (type(projection_revision) is not int or projection_revision < 1):
            raise ValueError('Positive projection revision required')
        if projection_source_start_sample is not None and (type(projection_source_start_sample) is not int or projection_source_start_sample < 0):
            raise ValueError('Nonnegative native parent source sample required')
        normalized, identifiers, bytes_total = [], set(), 0
        for order, part in enumerate(parts):
            if order >= 256 or type(part) is not dict:
                raise ValueError('At most 256 bounded caption parts required')
            value = json.loads(json.dumps(part, allow_nan=False))
            required = {'caption_id','start_sample','end_sample','text','speaker','provisional','provenance'}
            if set(value) != required:
                raise ValueError('Projection part fields differ from the caption contract')
            identifier = value['caption_id']
            if type(identifier) is not str or not 1 <= len(identifier) <= 128 or identifier in identifiers:
                raise ValueError('Unique bounded caption identifiers required')
            identifiers.add(identifier)
            if (type(value['start_sample']) is not int or type(value['end_sample']) is not int
                or not 0 <= value['start_sample'] <= value['end_sample']):
                raise ValueError('Invalid projection sample interval')
            if type(value['text']) is not str or len(value['text'].encode()) > 65536:
                raise ValueError('Bounded projection text required')
            if value['speaker'] is not None and (type(value['speaker']) is not str or len(value['speaker']) > 256):
                raise ValueError('Invalid projection speaker')
            if type(value['provisional']) is not bool:
                raise ValueError('Explicit projection provisional flag required')
            provenance = value['provenance']
            self._payload(provenance)
            if provenance.get('supersedes_parent') not in (None, parent_key):
                raise ValueError('Projection provenance parent differs')
            provenance['supersedes_parent'] = parent_key
            value['projection_order'] = order
            bytes_total += len(json.dumps(value, sort_keys=True).encode())
            if bytes_total > 262144:
                raise ValueError('Projection exceeds 256 KiB')
            normalized.append(value)
        with self._db(operation='replace caption projection') as db:
            db.execute('BEGIN IMMEDIATE')
            prior_projection = db.execute('SELECT revision,payload_sha256,source_start_sample FROM caption_projections WHERE session_id=? AND parent_key=?',
                                          (session_id,parent_key)).fetchone()
            raw_parent = db.execute('SELECT start_sample FROM captions WHERE session_id=? AND caption_id=? AND projection_parent IS NULL',
                                    (session_id,parent_key)).fetchone()
            anchors = [value['start_sample'] for value in normalized]
            if prior_projection is not None:
                anchors.append(prior_projection['source_start_sample'])
            if raw_parent is not None:
                anchors.append(raw_parent['start_sample'])
            if projection_source_start_sample is not None:
                anchors.append(projection_source_start_sample)
            source_anchor = min(anchors) if anchors else 0
            digest = hashlib.sha256(json.dumps(dict(parts=normalized,source_start_sample=source_anchor),
                                                sort_keys=True,allow_nan=False).encode()).hexdigest()
            old_revision = prior_projection['revision'] if prior_projection else 0
            incoming = projection_revision if projection_revision is not None else old_revision + 1
            if incoming < old_revision:
                return dict(parent_key=parent_key, projection_revision=old_revision, changed=False, stale=True)
            same = prior_projection is not None and prior_projection['payload_sha256'] == digest
            if same:
                if projection_revision is None:
                    incoming = old_revision
                if incoming > old_revision:
                    db.execute('UPDATE caption_projections SET revision=? WHERE session_id=? AND parent_key=?',
                               (incoming,session_id,parent_key))
                return dict(parent_key=parent_key,projection_revision=max(incoming,old_revision),changed=False)
            if prior_projection is not None and incoming == old_revision:
                raise StorageError('One projection revision cannot describe different spans')
            old = db.execute('SELECT caption_id FROM captions WHERE session_id=? AND (projection_parent=? OR (caption_id=? AND projection_parent IS NULL)) LIMIT 258',
                             (session_id,parent_key,parent_key)).fetchall()
            if len(old) > 257:
                raise StorageError('Stored projection exceeds its bounded part contract')
            retired = [row['caption_id'] for row in old if row['caption_id'] not in identifiers]
            self._capacity(bytes_total * 3 + 65536)
            for value in normalized:
                previous = db.execute('SELECT * FROM captions WHERE session_id=? AND caption_id=?',
                                      (session_id,value['caption_id'])).fetchone()
                if previous is not None and previous['projection_parent'] not in (None,parent_key):
                    raise StorageError('Caption belongs to a different projection parent')
                if (previous is not None and previous['projection_parent'] is None and value['caption_id'] != parent_key
                    and json.loads(previous['provenance']).get('supersedes_parent') != parent_key):
                    raise StorageError('Projection cannot adopt an unrelated caption')
                provenance_json = self._payload(value['provenance'])
                fields = dict(start_sample=value['start_sample'],end_sample=value['end_sample'],text=value['text'],
                              speaker=value['speaker'],provisional=int(value['provisional']),provenance=provenance_json,
                              projection_parent=parent_key,projection_order=value['projection_order'],
                              projection_source_start=source_anchor)
                unchanged = previous is not None and all(previous[key] == field for key,field in fields.items())
                if unchanged:
                    continue
                revision = previous['revision'] + 1 if previous is not None else 1
                event = {key:item for key,item in value.items() if key != 'projection_order'}
                event['revision'] = revision
                packed = _pack_event(json.dumps(event,sort_keys=True,allow_nan=False))
                packed_bytes = len(packed[0].encode()) if isinstance(packed[0],str) else len(packed[0])
                self._charge_metadata(db,session_id,2*(packed_bytes+len(value['text'].encode())+len(provenance_json.encode()))+2048)
                db.execute('''INSERT INTO captions(session_id,caption_id,revision,start_sample,end_sample,text,speaker,provisional,provenance,projection_parent,projection_order,projection_source_start)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(session_id,caption_id) DO UPDATE SET
                    revision=excluded.revision,start_sample=excluded.start_sample,end_sample=excluded.end_sample,text=excluded.text,
                    speaker=excluded.speaker,provisional=excluded.provisional,provenance=excluded.provenance,
                    projection_parent=excluded.projection_parent,projection_order=excluded.projection_order,
                    projection_source_start=excluded.projection_source_start''',
                    (session_id,value['caption_id'],revision,value['start_sample'],value['end_sample'],value['text'],value['speaker'],
                     int(value['provisional']),provenance_json,parent_key,value['projection_order'],source_anchor))
                db.execute('INSERT INTO events(session_id,created,event_type,payload,payload_encoding,payload_bytes,payload_sha256) VALUES(?,?,?,?,?,?,?)',
                           (session_id,time.time(),'caption_revision',*packed))
            for identifier in retired:
                db.execute('DELETE FROM captions WHERE session_id=? AND caption_id=? AND (projection_parent=? OR caption_id=?)',
                           (session_id,identifier,parent_key,parent_key))
            packed = _pack_event(self._payload(dict(parent_key=parent_key,projection_revision=incoming,source_start_sample=source_anchor,retired=retired,
                                                   visible_caption_ids=[value['caption_id'] for value in normalized])))
            packed_bytes = len(packed[0].encode()) if isinstance(packed[0],str) else len(packed[0])
            self._charge_metadata(db,session_id,2*packed_bytes+1024)
            db.execute('INSERT INTO events(session_id,created,event_type,payload,payload_encoding,payload_bytes,payload_sha256) VALUES(?,?,?,?,?,?,?)',
                       (session_id,time.time(),'caption_projection',*packed))
            db.execute('INSERT INTO caption_projections(session_id,parent_key,revision,payload_sha256,source_start_sample) VALUES(?,?,?,?,?) ON CONFLICT(session_id,parent_key) DO UPDATE SET revision=excluded.revision,payload_sha256=excluded.payload_sha256,source_start_sample=excluded.source_start_sample',
                       (session_id,parent_key,incoming,digest,source_anchor))
        return dict(parent_key=parent_key,projection_revision=incoming,changed=True,retired=retired)

    @staticmethod
    def _payload(value):
        if not isinstance(value, dict):
            raise ValueError("metadata payload must be an object")
        result = json.dumps(value, sort_keys=True, allow_nan=False)
        if len(result.encode("utf-8")) > 65536:
            raise ValueError("metadata payload exceeds 64 KiB")
        return result

    def write_event(self, session_id, event_type, payload):
        self.read(session_id)
        if not isinstance(event_type, str) or not 1 <= len(event_type) <= 128:
            raise ValueError("invalid event type")
        encoded = self._payload(payload)
        packed=_pack_event(encoded)
        packed_size=len(packed[0].encode()) if isinstance(packed[0],str) else len(packed[0])
        self._capacity(packed_size * 2 + 65536)
        now = time.time()
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            self._charge_metadata(db,session_id,2*packed_size+1024)
            cursor = db.execute("INSERT INTO events(session_id,created,event_type,payload,payload_encoding,payload_bytes,payload_sha256) VALUES(?,?,?,?,?,?,?)",
                                (session_id, now, event_type, *packed))
            seq = cursor.lastrowid
        return {"seq": seq, "session_id": session_id, "created": now,
                "event_type": event_type, "payload": json.loads(encoded)}

    def write_terminal_event(self, session_id, event_type, payload):
        """One bounded terminal fact per kind, independently of metadata quotas.

        This records facts after cleanup attempts; it is not process-death proof.
        Historical reservation fields remain accounting evidence. A missing or
        exhausted logical pool cannot block cleanup facts; actual free-space
        checks and immutable terminal-fact consistency still apply.
        """
        metadata = self.read(session_id)
        if event_type not in ('source_closure', 'session_cleanup',
                              'saved_spatial_closed', 'session_failure'):
            raise ValueError('Only the four reviewed terminal fact kinds are allowed')
        limit = metadata_limits(metadata['spec'], self.policy.metadata_allowance_bytes)['terminal_sqlite_bytes']
        encoded = self._payload(payload)
        if len(encoded.encode('utf-8')) > 16384:
            raise ValueError('Terminal facts must be compact and at most 16 KiB')
        packed = _pack_event(encoded)
        packed_size = len(packed[0].encode()) if isinstance(packed[0], str) else len(packed[0])
        charge = 2*packed_size+1024
        self._capacity(charge+65536)
        with self._db() as db:
            db.execute('BEGIN IMMEDIATE')
            prior = db.execute('SELECT seq,payload_sha256 FROM terminal_events WHERE session_id=? AND event_type=?',
                               (session_id,event_type)).fetchone()
            if prior is not None:
                if prior['payload_sha256'] != packed[3]:
                    raise StorageError('A terminal fact cannot be replaced or contradicted')
                row = db.execute('SELECT created FROM events WHERE seq=? AND session_id=?',
                                 (prior['seq'],session_id)).fetchone()
                if row is None:
                    raise StorageError('Terminal event index is inconsistent')
                return dict(seq=prior['seq'],session_id=session_id,created=row['created'],
                            event_type=event_type,payload=json.loads(encoded))
            usage = db.execute('SELECT used_bytes,limit_bytes FROM terminal_metadata_usage WHERE session_id=?',
                               (session_id,)).fetchone()
            used, recorded_limit = tuple(usage) if usage is not None else (0,limit)
            now = time.time()
            cursor = db.execute('INSERT INTO events(session_id,created,event_type,payload,payload_encoding,payload_bytes,payload_sha256) VALUES(?,?,?,?,?,?,?)',
                                (session_id,now,event_type,*packed))
            db.execute('INSERT INTO terminal_metadata_usage VALUES(?,?,?) ON CONFLICT(session_id) DO UPDATE SET used_bytes=excluded.used_bytes',
                       (session_id,used+charge,recorded_limit))
            db.execute('INSERT INTO terminal_events VALUES(?,?,?,?)',
                       (session_id,event_type,cursor.lastrowid,packed[3]))
            seq = cursor.lastrowid
        return dict(seq=seq,session_id=session_id,created=now,event_type=event_type,payload=json.loads(encoded))

    def _metadata_page(self, table, session_id, limit, after):
        self.read(session_id)
        if not isinstance(limit, int) or not 1 <= limit <= self.policy.max_page_size or not isinstance(after, int) or after < 0:
            raise ValueError("invalid bounded metadata page")
        with self._db() as db:
            rows = db.execute("SELECT * FROM " + table + " WHERE session_id=? AND seq>? ORDER BY seq LIMIT ?",
                              (session_id, after, limit + 1)).fetchall()
        items = []
        for row in rows[:limit]:
            item = dict(row)
            if table == "captions":
                item["provenance"] = json.loads(item["provenance"])
                item["provisional"] = bool(item["provisional"])
            else:
                item["payload"] = _unpack_event(item)
                for key in ('payload_encoding','payload_bytes','payload_sha256'):item.pop(key,None)
            items.append(item)
        return {"items": items, "next_cursor": items[-1]["seq"] if len(rows) > limit else None}

    def captions(self, session_id, limit=25, after=0):
        return self._metadata_page("captions", session_id, limit, after)

    def _caption_source_sql(self, db):
        """Read legacy Saved stores without modifying their schema or content."""
        if not self.read_only:
            return '*','COALESCE(projection_parent,caption_id)','projection_order','COALESCE(projection_source_start,start_sample)'
        columns = {row['name'] for row in db.execute('PRAGMA table_info(captions)')}
        selection = '*'
        parent = 'COALESCE(projection_parent,caption_id)' if 'projection_parent' in columns else 'caption_id'
        order = 'projection_order' if 'projection_order' in columns else 'CAST(0 AS INTEGER)'
        source = 'COALESCE(projection_source_start,start_sample)' if 'projection_source_start' in columns else 'start_sample'
        if 'projection_parent' not in columns:
            selection += ',NULL AS projection_parent'
        if 'projection_order' not in columns:
            selection += ',0 AS projection_order'
        if 'projection_source_start' not in columns:
            selection += ',NULL AS projection_source_start'
        return selection,parent,order,source

    def latest_captions(self, session_id, limit=40, after_revision=None):
        """Indexed tail for live UI; revision cursor notices edits to stable IDs."""
        self.read(session_id)
        if not isinstance(limit, int) or not 1 <= limit <= self.policy.max_page_size:
            raise ValueError("invalid bounded caption tail size")
        if after_revision is not None and (not isinstance(after_revision, int) or after_revision < 0):
            raise ValueError("invalid caption revision cursor")
        with self._db() as db:
            revision = db.execute("SELECT COALESCE(MAX(seq),0) FROM events WHERE session_id=? AND event_type IN ('caption_revision','caption_projection')", (session_id,)).fetchone()[0]
            if revision == after_revision:
                return {"items": [], "revision_cursor": revision, "changed": False}
            selection,parent,order,source = self._caption_source_sql(db)
            rows = db.execute('SELECT '+selection+' FROM captions WHERE session_id=? ORDER BY '+source+' DESC,'+parent+' DESC,'+order+' DESC,caption_id DESC LIMIT ?', (session_id, limit)).fetchall()
        items = []
        for row in reversed(rows):
            item = dict(row)
            item["provenance"] = json.loads(item["provenance"])
            item["provisional"] = bool(item["provisional"])
            items.append(item)
        return {"items": items, "revision_cursor": revision, "changed": True}

    def caption_page(self, session_id, limit=40, before=None):
        """A bounded older page in source/parent/span order, without a live cursor."""
        self.read(session_id)
        if type(limit) is not int or not 1 <= limit <= self.policy.max_page_size:
            raise ValueError('Bounded caption page required')
        cursor = None
        if before is not None:
            if type(before) is not str or len(before) > 1024:
                raise ValueError('Bounded caption source cursor required')
            try:
                cursor = json.loads(base64.b64decode(before.encode('ascii'),altchars=b'-_',validate=True))
            except (ValueError,UnicodeError) as error:
                raise ValueError('Invalid caption source cursor') from error
            if (type(cursor) is not list or len(cursor) != 4 or type(cursor[0]) is not int or cursor[0] < 0
                or type(cursor[2]) is not int or not 0 <= cursor[2] < 256
                or any(type(cursor[i]) is not str or not 1 <= len(cursor[i]) <= 128 for i in (1,3))):
                raise ValueError('Invalid caption source cursor fields')
        with self._db(operation='page caption source history') as db:
            selection,parent,order,source = self._caption_source_sql(db)
            query = 'SELECT '+selection+' FROM captions WHERE session_id=?'
            parameters = [session_id]
            if cursor is not None:
                query += ' AND ('+source+','+parent+','+order+',caption_id)<(?,?,?,?)'
                parameters.extend(cursor)
            query += ' ORDER BY '+source+' DESC,'+parent+' DESC,'+order+' DESC,caption_id DESC LIMIT ?'
            parameters.append(limit + 1)
            rows = db.execute(query,parameters).fetchall()
        selected = rows[:limit]
        items = []
        for row in reversed(selected):
            item = dict(row)
            item['provenance'] = json.loads(item['provenance'])
            item['provisional'] = bool(item['provisional'])
            items.append(item)
        next_cursor = None
        if len(rows) > limit:
            oldest = selected[-1]
            key = [oldest['projection_source_start'] if oldest['projection_source_start'] is not None else oldest['start_sample'],oldest['projection_parent'] or oldest['caption_id'],oldest['projection_order'],oldest['caption_id']]
            next_cursor = base64.urlsafe_b64encode(json.dumps(key,separators=(',',':')).encode()).decode('ascii')
        return dict(items=items,next_cursor=next_cursor)

    def caption_parents(self, session_id, parent_keys, limit=120):
        """Refresh a bounded frozen window's labels without appending live parents."""
        self.read(session_id)
        keys = list(itertools.islice(iter(parent_keys),81))
        if (len(keys) > 80 or any(type(key) is not str or not 1 <= len(key) <= 128 for key in keys)
            or len(set(keys)) != len(keys)
            or type(limit) is not int or not 1 <= limit <= 120):
            raise ValueError('At most 80 unique parents and 120 caption parts required')
        if not keys:
            return dict(items=[],truncated=False)
        placeholders = ','.join('?' for _ in keys)
        with self._db(operation='refresh frozen caption parents') as db:
            selection,parent,order,source = self._caption_source_sql(db)
            rows = db.execute('SELECT '+selection+' FROM captions WHERE session_id=? AND '+parent+' IN ('+placeholders+') '
                              'ORDER BY '+source+','+parent+','+order+',caption_id LIMIT ?',
                              [session_id,*keys,limit+1]).fetchall()
        items = []
        for row in rows[:limit]:
            value = dict(row)
            value['provenance'] = json.loads(value['provenance'])
            value['provisional'] = bool(value['provisional'])
            items.append(value)
        return dict(items=items,truncated=len(rows)>limit)

    def events(self, session_id, limit=25, after=0):
        return self._metadata_page("events", session_id, limit, after)

    def _segments(self, session_id, kind=None):
        after_kind,after_idx='',-1
        while True:
            with self._db() as db:
                if kind is None:
                    rows=db.execute('SELECT * FROM segments WHERE session_id=? AND (kind,idx)>(?,?) ORDER BY kind,idx LIMIT 32',
                                    (session_id,after_kind,after_idx)).fetchall()
                else:
                    rows=db.execute('SELECT * FROM segments WHERE session_id=? AND kind=? AND idx>? ORDER BY idx LIMIT 32',
                                    (session_id,kind,after_idx)).fetchall()
            if not rows:break
            # Release the SQLite read transaction before slow export/replay I/O.
            for row in rows:yield dict(row)
            after_kind,after_idx=rows[-1]['kind'],rows[-1]['idx']

    def processed_segment_page(self, session_id, *, after=-1, limit=32):
        """Bounded read-only pages; release SQLite readers before audio pacing."""
        self._session_dir(session_id)
        if type(after) is not int or after < -1 or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('Bounded segment cursor/page required')
        with self._db() as db:
            rows = db.execute('SELECT * FROM segments WHERE session_id=? AND kind=? AND idx>? ORDER BY idx LIMIT ?',
                (session_id, 'processed', after, limit)).fetchall()
        return [dict(row) for row in rows]

    def _publish(self, session_id):
        metadata = self.read(session_id)
        # Metadata is fixed size; segment rows remain in SQLite, exported as JSONL.
        metadata["audio"] = {"processed_encoding": "FLOAT32_LE", "processed_channels": 1,
                             "replay_encoding": "PCM_S16LE", "segment_index": "segments.jsonl"}
        _atomic_json(self._session_dir(session_id) / "session.json", metadata)
        return metadata

    def rename(self, session_id, title):
        if type(title) is not str or not title.strip() or len(title.encode('utf-8')) > 256 or any(ord(c)<32 for c in title):
            raise StorageError("recording name must be 1..256 UTF-8 bytes without control characters")
        with self._mutex, self._session_lease(session_id):
            metadata = self.read(session_id)
            if metadata['status'] != 'kept':
                raise StorageError("only a saved recording can be renamed")
            spec = dict(metadata['spec'], title=title.strip())
            with self._db() as db:
                db.execute("UPDATE sessions SET spec=?,updated=? WHERE id=?", (json.dumps(spec, sort_keys=True, allow_nan=False), time.time(), session_id))
            return self._publish(session_id)

    def keep(self, session_id, include_raw=False):
        with self._mutex, self._session_lease(session_id):
            metadata = self.read(session_id)
            if metadata["status"] not in ("stopped", "kept"):
                raise StorageError("only a stopped/drained session may be kept")
            if include_raw:
                if metadata["spec"]["mode"] != "raw_processed" or not metadata["raw_samples"]:
                    raise StorageError("qualified raw samples are unavailable")
                raw = metadata["spec"]["raw"]
                with self._db() as db:
                    retained_raw = db.execute("SELECT COALESCE(SUM(samples),0) FROM segments WHERE session_id=? AND kind='raw'", (session_id,)).fetchone()[0]
                if retained_raw != metadata["raw_samples"]:
                    raise StorageError("raw samples have already been discarded")
                if metadata["raw_samples"] * metadata["spec"]["sample_rate"] != metadata["processed_samples"] * raw["sample_rate"]:
                    raise StorageError("raw/processed timelines do not cover the same duration")
            if not include_raw:
                self._remove_audio(session_id, kind="raw")
            with self._db() as db:
                db.execute("UPDATE sessions SET status='kept',include_raw=?,updated=? WHERE id=?",
                           (int(include_raw), time.time(), session_id))
            return self._publish(session_id)

    def _remove_audio(self, session_id, kind=None):
        directory = self._session_dir(session_id)
        for segment in self._segments(session_id, kind):
            self._audio_path(session_id, segment["data_name"])
            if segment["replay_name"]:
                self._audio_path(session_id, segment["replay_name"])
        # Two streaming passes validate before deleting; no session-sized list.
        prefix = kind if kind else "(?:processed|raw)"
        for path in directory.iterdir():
            if re.fullmatch(prefix + r"-\d{8}\.(?:f32|wav|bin)(?:\.part)?", path.name):
                _safe(path)
                if not path.is_file():
                    raise UnsafePathError("non-file in audio spool")
        for path in directory.iterdir():
            if re.fullmatch(prefix + r"-\d{8}\.(?:f32|wav|bin)(?:\.part)?", path.name):
                _safe(path).unlink()
        self._purge_session_table('segments',session_id,kind=kind)
        _sync_dir(directory)

    def discard(self, session_id):
        """Remove explicitly discarded temporary content; keep only a small receipt."""
        return self._request_deletion(session_id, 'discard')

    def delete(self, session_id, *, confirm=False):
        """Explicit, retry-safe individual deletion. README_STORAGE_RECOVERY.md."""
        if confirm is not True:
            raise StorageError("delete requires confirm=True for this session")
        return self._request_deletion(session_id, 'delete')

    def _deletion_path(self, session_id, *, completed=False):
        if type(session_id) is not str or not re.fullmatch(r'[0-9a-f]{32}',session_id):
            raise UnsafePathError('Invalid deletion session identifier')
        return _safe(self.root / ('deletion_receipts' if completed else 'deletions') / (session_id+'.json'))

    def deletion_pending(self, session_id):
        """A verified explicit intent, usable by a failed Discard's Retry control."""
        path = self._deletion_path(session_id)
        if not path.exists():
            return False
        self._read_deletion_record(path,session_id)
        return True

    def _read_deletion_record(self, path, session_id, *, completed=False):
        _safe(path)
        if not path.is_file() or path.stat().st_size > 65536:
            raise UnsafePathError('Bounded regular deletion record required')
        def pairs(values):
            result = {}
            for key,value in values:
                if key in result:
                    raise UnsafePathError('Duplicate deletion record key')
                result[key] = value
            return result
        value = json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=pairs,
                           parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)))
        required = {'schema','store_id','session_id','request_kind','requested_unix','origin_status'}
        if completed:
            required |= {'completed_unix','status'}
        else:
            required.add('directories')
        if (type(value) is not dict or set(value) != required or value.get('schema') != 'just-peachy.session-deletion.v1'
            or value.get('store_id') != self.owner['store_id'] or value.get('session_id') != session_id
            or value.get('request_kind') not in ('discard','delete')
            or value.get('origin_status') not in ('stopped','failed','cancelled','discarded','kept')
            or type(value.get('requested_unix')) not in (int,float) or not math.isfinite(value['requested_unix'])
            or type(value.get('directories',[])) is not list or len(value.get('directories',[])) > 128):
            raise UnsafePathError('Deletion record ownership/contract differs')
        if value['request_kind'] == 'discard' and value['origin_status'] == 'kept':
            raise UnsafePathError('Temporary Discard cannot authorize a kept recording')
        for relative in value.get('directories',[]):
            # The same path validator checks all parents without adopting content.
            self._artifact_path_unowned(session_id,relative+'/sentinel')
        if len(set(value.get('directories',[]))) != len(value.get('directories',[])):
            raise UnsafePathError('Duplicate deletion directory')
        if completed and (value.get('status') != ('discarded' if value['request_kind']=='discard' else 'deleted')
                          or type(value.get('completed_unix')) not in (int,float) or not math.isfinite(value['completed_unix'])):
            raise UnsafePathError('Deletion completion contract differs')
        return value

    def _artifact_path_unowned(self, session_id, relative):
        if type(relative) is not str or not 1 <= len(relative) <= 1024 or '\\' in relative or ':' in relative:
            raise UnsafePathError('Bounded deletion artifact path required')
        parts = relative.split('/')
        if parts[0] != 'work' or any(part in ('','.','..') for part in parts):
            raise UnsafePathError('Deletion artifacts must stay inside this session work directory')
        return _safe(self.root/'sessions'/session_id/Path(*parts))

    def _validate_deletion_tree(self, session_id, intent=None):
        """Preflight all children before the first unlink; retain exact ownership."""
        directory = _safe(self.root/'sessions'/session_id)
        if not directory.exists():
            return []
        owner_path = _safe(directory/'owner.json')
        if owner_path.exists():
            if json.loads(owner_path.read_text(encoding='utf-8')) != {'store_id':self.owner['store_id'],'session_id':session_id}:
                raise UnsafePathError('Deletion session ownership differs')
        elif intent is None or next(directory.iterdir(),None) is not None:
            raise UnsafePathError('Missing owner proof for a nonempty deletion directory')
        directories = []
        for parent,dirs,files in os.walk(directory,followlinks=False):
            for name in dirs:
                path = _safe(Path(parent)/name)
                relative = path.relative_to(directory).as_posix()
                self._artifact_path_unowned(session_id,relative+'/sentinel')
                with self._db(operation='validate deletion directory') as db:
                    known = db.execute('SELECT 1 FROM artifacts WHERE session_id=? AND substr(path,1,?)=? LIMIT 1',
                                       (session_id,len(relative)+1,relative+'/')).fetchone()
                if not known and (intent is None or relative not in intent['directories']):
                    raise UnsafePathError('Unrelated artifact directory prevents deletion')
                directories.append(relative)
                if len(directories) > 128:
                    raise UnsafePathError('Deletion directory inventory exceeds its bound')
            for name in files:
                path = _safe(Path(parent)/name)
                relative = path.relative_to(directory).as_posix()
                generated = path.parent == directory and (
                    name in ('owner.json','spec.json','session.json')
                    or re.fullmatch(r'(?:owner|spec|session)\.json\.tmp-[0-9a-f]{32}',name)
                    or re.fullmatch(r'(?:processed|raw)-\d{8}\.(?:f32|wav|bin)(?:\.part)?',name))
                with self._db(operation='validate deletion child') as db:
                    known = db.execute('SELECT 1 FROM artifacts WHERE session_id=? AND path=?',(session_id,relative)).fetchone()
                if not path.is_file() or not (generated or known):
                    raise UnsafePathError('Unrelated session child prevents deletion: '+relative)
        return sorted(directories)

    def _request_deletion(self, session_id, kind):
        if self.read_only:
            raise StorageError('Read-only store cannot delete a recording')
        pending = self._deletion_path(session_id)
        completed = self._deletion_path(session_id,completed=True)
        with self._mutex, _Lease(self.root/'locks'/(session_id+'.lock')):
            if completed.exists():
                return self._read_deletion_record(completed,session_id,completed=True)
            if pending.exists():
                intent = self._read_deletion_record(pending,session_id)
                if kind == 'discard' and intent['origin_status'] == 'kept':
                    raise StorageError('A kept recording requires deliberate Delete')
            else:
                metadata = self.read(session_id)
                if metadata['status'] == 'active' or kind == 'discard' and metadata['status'] == 'kept':
                    raise StorageError('Stop first; kept recordings require deliberate Delete')
                if metadata['status'] not in ('stopped','failed','cancelled','discarded','kept'):
                    raise StorageError('This session has no admitted deletion state')
                directories = self._validate_deletion_tree(session_id)
                intent = dict(schema='just-peachy.session-deletion.v1',store_id=self.owner['store_id'],session_id=session_id,
                              request_kind=kind,requested_unix=time.time(),origin_status=metadata['status'],directories=directories)
                if len(json.dumps(intent).encode()) > 65536:
                    raise StorageError('Deletion intent exceeds 64 KiB')
                _atomic_json(pending,intent)
            return self._continue_deletion(intent)

    def _purge_session_table(self, table, session_id, *, kind=None):
        # 128 rows bound each journal transaction. Only reviewed table names enter.
        if table not in ('segments','artifacts','captions','events','metadata_usage',
                         'terminal_events','terminal_metadata_usage','caption_projections'):
            raise ValueError('Unreviewed deletion table')
        if kind is not None and (table != 'segments' or kind not in ('raw','processed')):
            raise ValueError('Only an admitted segment kind may filter deletion')
        predicate = 'session_id=?'+(' AND kind=?' if kind is not None else '')
        parameters = (session_id,kind) if kind is not None else (session_id,)
        while True:
            with self._db(operation='delete session '+table) as db:
                db.execute('BEGIN IMMEDIATE')
                changed = db.execute('DELETE FROM '+table+' WHERE '+predicate+' AND rowid IN '
                                     '(SELECT rowid FROM '+table+' WHERE '+predicate+' LIMIT 128)',
                                     parameters+parameters).rowcount
            if changed == 0:
                break

    def _continue_deletion(self, intent):
        session_id = intent['session_id']
        directory = _safe(self.root/'sessions'/session_id)
        self._validate_deletion_tree(session_id,intent)
        with self._db(operation='mark explicitly requested deletion') as db:
            db.execute("UPDATE sessions SET status='deleting',include_raw=0,updated=? WHERE id=?",(time.time(),session_id))
        if directory.exists() and (directory/'owner.json').exists():
            self._remove_audio(session_id)
            self._remove_artifacts(session_id)
            for relative in sorted(intent['directories'],key=lambda value:value.count('/'),reverse=True):
                path = self._artifact_path_unowned(session_id,relative+'/sentinel').parent
                if path.exists():
                    path.rmdir()  # Unexpected new content is refused, never recursively erased.
            _sync_dir(directory)
        for table in ('segments','artifacts','captions','events','metadata_usage',
                      'terminal_events','terminal_metadata_usage','caption_projections'):
            self._purge_session_table(table,session_id)
        with self._db(operation='delete selected session index') as db:
            db.execute('DELETE FROM sessions WHERE id=?',(session_id,))
        if directory.exists():
            # Owner proof survives until every media/index deletion has committed.
            for path in directory.iterdir():
                if path.name == 'owner.json':
                    continue
                if path.name in ('session.json','spec.json') or re.fullmatch(r'(?:owner|spec|session)\.json\.tmp-[0-9a-f]{32}',path.name):
                    _safe(path).unlink(missing_ok=True)
                else:
                    raise UnsafePathError('Unexpected final deletion child: '+path.name)
            _sync_dir(directory)
            _safe(directory/'owner.json').unlink(missing_ok=True)
            directory.rmdir()
            _sync_dir(directory.parent)
        receipt = {key:value for key,value in intent.items() if key != 'directories'}
        receipt.update(completed_unix=time.time(),status='discarded' if intent['request_kind']=='discard' else 'deleted')
        _atomic_json(self._deletion_path(session_id,completed=True),receipt)
        pending = self._deletion_path(session_id)
        pending.unlink(missing_ok=True)
        _sync_dir(pending.parent)
        return receipt

    def recover_deletions(self, limit=64):
        """Resume explicit persisted intents only; never scan/adopt orphan sessions."""
        if self.read_only:
            return []
        completed = []
        with self._mutex:
            for path in _safe(self.root/'deletions').glob('*.json'):
                if len(completed) >= limit:
                    raise StorageError('Pending deletion recovery exceeds bounded startup batch')
                session_id = path.stem
                self._deletion_path(session_id)
                intent = self._read_deletion_record(path,session_id)
                with _Lease(self.root/'locks'/(session_id+'.lock')):
                    receipt_path = self._deletion_path(session_id,completed=True)
                    if receipt_path.exists():
                        receipt = self._read_deletion_record(receipt_path,session_id,completed=True)
                        if any(receipt[key] != value for key,value in intent.items() if key != 'directories'):
                            raise UnsafePathError('Pending/completed deletion intents differ')
                        path.unlink()
                        _sync_dir(path.parent)
                        completed.append(receipt)
                    else:
                        completed.append(self._continue_deletion(intent))
        return completed

    def _remove_artifacts(self, session_id):
        directory = self._session_dir(session_id)
        for artifact in self._artifacts(session_id):
            self._artifact_path(session_id, artifact["path"])
        for artifact in self._artifacts(session_id):
            path = self._artifact_path(session_id, artifact["path"])
            path.unlink(missing_ok=True)
            parent = path.parent
            while parent != directory:
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        self._purge_session_table('artifacts',session_id)

    def iter_processed(self, session_id, block_samples=16384):
        """Yield (start_sample, exact_float32_bytes) in bounded, contiguous blocks."""
        if not 1 <= block_samples <= self.policy.max_append_bytes // 4:
            raise ValueError("invalid bounded read size")
        with self._session_lease(session_id):
            metadata = self.read(session_id)
            if metadata["status"] not in ("kept", "stopped"):
                raise StorageError("session has no complete readable timeline")
            expected = 0
            directory = self._session_dir(session_id)
            for segment in self._segments(session_id, "processed"):
                if segment["start_sample"] != expected:
                    raise StorageError("segment timeline gap")
                path = self._audio_path(session_id, segment["data_name"])
                if path.stat().st_size != segment["samples"] * 4:
                    raise StorageError("processed segment size mismatch")
                with path.open("rb") as source:
                    while data := source.read(block_samples * 4):
                        yield expected, data
                        expected += len(data) // 4
            if expected != metadata["processed_samples"]:
                raise StorageError("authoritative sample count mismatch")

    def export(self, session_ids, destination):
        """Stream selected kept sessions to a new ZIP, atomically publishing it."""
        selected = []
        for session_id in session_ids:
            self._session_dir(session_id)
            if session_id in selected:
                raise ValueError("duplicate export session")
            selected.append(session_id)
            if len(selected) > self.policy.max_export_sessions:
                raise ValueError("selection exceeds bounded export batch size")
        if not selected:
            raise ValueError("select at least one session")
        destination = _safe(Path(destination).absolute())
        if destination.exists() or not destination.parent.is_dir():
            raise UnsafePathError("export requires a new file in an existing directory")
        temporary = destination.with_name(destination.name + ".part-" + uuid.uuid4().hex)
        try:
            with contextlib.ExitStack() as stack:
                for session_id in sorted(selected):
                    stack.enter_context(self._session_lease(session_id))
                required = 65536
                entries=0
                for session_id in selected:
                    metadata = self.read(session_id)
                    if metadata["status"] != "kept":
                        raise StorageError("export accepts kept sessions only")
                    required += len(json.dumps(metadata, sort_keys=True).encode("utf-8")) + 4096
                    entries+=6  #session, segment, caption, human transcript, event and artifact indices
                    directory = self._session_dir(session_id)
                    for segment in self._segments(session_id):
                        for name in (segment["data_name"], segment["replay_name"]):
                            if name:
                                required += self._audio_path(session_id, name).stat().st_size + 1024
                                entries+=1
                    with self._db() as db:
                        required += db.execute("SELECT COALESCE(SUM(LENGTH(text)*12+LENGTH(speaker)*6+LENGTH(provenance)+4096),0) FROM captions WHERE session_id=?", (session_id,)).fetchone()[0]
                        required += db.execute("SELECT COALESCE(SUM(CASE WHEN payload_bytes>0 THEN payload_bytes ELSE LENGTH(CAST(payload AS BLOB)) END+4096),0) FROM events WHERE session_id=?", (session_id,)).fetchone()[0]
                    for artifact in self._artifacts(session_id):
                        path = self._artifact_path(session_id, artifact["path"])
                        if path.stat().st_size != artifact["bytes"]:
                            raise StorageError("artifact changed after registration")
                        required += artifact["bytes"] + 1024
                        entries+=1
                    if entries>self.policy.max_export_entries:
                        raise CapacityError('Export ZIP metadata exceeds its bounded entry allocation; select a smaller batch')
                self._capacity(required, destination.parent)
                with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                    for session_id in selected:
                        directory = self._session_dir(session_id)
                        archive.writestr(session_id + "/session.json", json.dumps(self.read(session_id), sort_keys=True))
                        with archive.open(session_id + "/segments.jsonl", "w", force_zip64=True) as index:
                            for segment in self._segments(session_id):
                                index.write((json.dumps(segment, sort_keys=True) + "\n").encode("utf-8"))
                        for table in ("captions", "events"):
                            with archive.open(session_id + "/" + table + ".jsonl", "w", force_zip64=True) as output:
                                cursor = 0
                                while True:
                                    page = self._metadata_page(table, session_id, min(25, self.policy.max_page_size), cursor)
                                    for item in page["items"]:
                                        output.write((json.dumps(item, sort_keys=True) + "\n").encode("utf-8"))
                                    if page["next_cursor"] is None:
                                        break
                                    cursor = page["next_cursor"]
                        for segment in self._segments(session_id):
                            for name in (segment["data_name"], segment["replay_name"]):
                                if name:
                                    source_path = self._audio_path(session_id, name)
                                    self._capacity(source_path.stat().st_size, destination.parent)
                                    archive.write(source_path, session_id + "/" + name)
                        with archive.open(session_id + "/transcript.txt", "w", force_zip64=True) as output:
                            cursor = 0
                            sample_rate = self.read(session_id)["spec"]["sample_rate"]
                            while True:
                                page = self.captions(session_id, min(25, self.policy.max_page_size), cursor)
                                for item in page["items"]:
                                    line = "[%.3f–%.3f] %s%s: %s\n" % (
                                        item["start_sample"]/sample_rate, item["end_sample"]/sample_rate,
                                        item["speaker"], " (provisional)" if item["provisional"] else "", item["text"])
                                    output.write(line.encode("utf-8"))
                                if page["next_cursor"] is None: break
                                cursor = page["next_cursor"]
                        with archive.open(session_id + "/artifacts.jsonl", "w", force_zip64=True) as index:
                            for artifact in self._artifacts(session_id):
                                index.write((json.dumps(artifact, sort_keys=True) + "\n").encode("utf-8"))
                        for artifact in self._artifacts(session_id):
                            self._capacity(artifact["bytes"], destination.parent)
                            archive.write(self._artifact_path(session_id, artifact["path"]), session_id + "/" + artifact["path"])
                with temporary.open("r+b") as file:
                    os.fsync(file.fileno())
                # Atomic and no-clobber, unlike replace(). Same filesystem temp.
                os.link(temporary, destination)
                _sync_dir(destination.parent)
            return destination
        finally:
            temporary.unlink(missing_ok=True)

    def close(self):
        if self._spool is not None and not self._spool.closed:
            self._spool.fail("store closed before stop/drain")


class SessionSpool:
    def __init__(self, store, session_id, spec, lease, allocation):
        self.store, self.session_id, self.spec = store, session_id, spec
        self.directory = store._session_dir(session_id)
        self._lease = lease
        self._session_lock = store._session_lease(session_id)
        self._mutex = threading.RLock()
        self.closed = False
        self.processed_samples = self.raw_samples = 0
        self.allocation_bytes = allocation
        self._states = {"processed": None, "raw": None}
        self._indices = {"processed": 0, "raw": 0}

    def _open_segment(self, kind, start_sample):
        index = self._indices[kind]
        name = "%s-%08d.%s" % (kind, index, "f32" if kind == "processed" else "bin")
        data = _safe(self.directory / (name + ".part")).open("xb")
        replay_name = "processed-%08d.wav" % index if kind == "processed" else None
        replay_file = replay = None
        try:
            if replay_name:
                replay_file = _safe(self.directory / (replay_name + ".part")).open("xb")
                replay = wave.open(replay_file, "wb")
                replay.setnchannels(1)
                replay.setsampwidth(2)
                replay.setframerate(self.spec["sample_rate"])
        except BaseException:
            data.close()
            if replay_file:
                replay_file.close()
            raise
        state = {"data": data, "replay": replay, "replay_file": replay_file,
                 "name": name, "replay_name": replay_name, "samples": 0,
                 "start": start_sample,
                 "idx": index}
        self._states[kind] = state
        return state

    def _seal(self, kind):
        state = self._states[kind]
        if state is None:
            return
        state["data"].flush()
        os.fsync(state["data"].fileno())
        state["data"].close()
        if state["replay"]:
            state["replay"].close()
            state["replay_file"].flush()
            os.fsync(state["replay_file"].fileno())
            state["replay_file"].close()
        for name in (state["name"], state["replay_name"]):
            if name:
                os.replace(_safe(self.directory / (name + ".part")), _safe(self.directory / name))
        _sync_dir(self.directory)
        with self.store._db() as db:
            db.execute("INSERT INTO segments VALUES(?,?,?,?,?,?,?)",
                       (self.session_id, kind, state["idx"], state["start"], state["samples"], state["name"], state["replay_name"]))
        self._states[kind] = None
        self._indices[kind] += 1

    def _append(self, kind, start_sample, data):
        with self._mutex:
            if self.closed:
                raise StorageError("append after stop/failure is forbidden")
            if not isinstance(data, (bytes, bytearray, memoryview)):
                raise TypeError("audio must be bytes-like")
            if not isinstance(start_sample, int) or isinstance(start_sample, bool):
                raise ValueError("start_sample must be an integer")
            frame_bytes = 4 if kind == "processed" else self.spec["raw"]["channels"] * self.spec["raw"]["sample_width_bytes"]
            if not 0 < len(data) <= self.store.policy.max_append_bytes or len(data) % frame_bytes:
                raise ValueError("audio block has invalid alignment or bounded size")
            current = self.processed_samples if kind == "processed" else self.raw_samples
            if start_sample != current:
                raise StorageError("non-contiguous %s timeline: expected %d, got %d" % (kind, current, start_sample))
            rate = self.spec["sample_rate"] if kind == "processed" else self.spec["raw"]["sample_rate"]
            if current + len(data) // frame_bytes > math.ceil(self.spec["duration_seconds"] * rate):
                raise CapacityError("session duration allocation exhausted")
            if kind == "processed":
                values = array.array("f")
                values.frombytes(data)
                if sys.byteorder != "little":
                    values.byteswap()
                if any(not math.isfinite(value) for value in values):
                    raise ValueError("non-finite processed samples are forbidden")
            try:
                self.store._capacity(len(data) * (2 if kind == "processed" else 1) + 16384)
                offset = 0
                while offset < len(data):
                    state = self._states[kind] or self._open_segment(kind, current + offset // frame_bytes)
                    take_frames = min((len(data) - offset) // frame_bytes, self.store.policy.segment_samples - state["samples"])
                    block = memoryview(data)[offset:offset + take_frames * frame_bytes]
                    if state["data"].write(block) != len(block):
                        raise OSError("short audio spool write")
                    if kind == "processed":
                        first = offset // 4
                        pcm = array.array("h", (max(-32768, min(32767, round(value * 32768))) for value in values[first:first + take_frames]))
                        if sys.byteorder != "little":
                            pcm.byteswap()
                        state["replay"].writeframesraw(pcm.tobytes())
                    state["samples"] += take_frames
                    offset += len(block)
                    if state["samples"] == self.store.policy.segment_samples:
                        self._seal(kind)
                state = self._states[kind]
                if state:
                    state["data"].flush()
                    os.fsync(state["data"].fileno())
                    if state["replay_file"]:
                        state["replay_file"].flush()
                        os.fsync(state["replay_file"].fileno())
                committed = current + len(data) // frame_bytes
                with self.store._db() as db:
                    column = "processed_samples" if kind == "processed" else "raw_samples"
                    db.execute("UPDATE sessions SET " + column + "=?,updated=? WHERE id=?", (committed, time.time(), self.session_id))
                if kind == "processed":
                    self.processed_samples = committed
                else:
                    self.raw_samples = committed
            except BaseException as error:
                try:
                    self.fail("append failed: " + type(error).__name__ + ": " + str(error))
                except BaseException as secondary:
                    error.add_note('Append failure cleanup also failed: '+repr(secondary))
                raise

    def append_processed(self, start_sample, float32bytes):
        self._append("processed", start_sample, float32bytes)

    def append_raw(self, start_sample, raw_bytes):
        if self.spec["mode"] != "raw_processed":
            raise StorageError("raw was not qualified and allocated for this session")
        self._append("raw", start_sample, raw_bytes)

    def read_processed(self, start_sample, count):
        """Read committed exact samples, including the fsynced active segment."""
        with self._mutex:
            if not isinstance(start_sample, int) or not isinstance(count, int) or start_sample < 0 or count < 0:
                raise ValueError("invalid processed read interval")
            if count * 4 > self.store.policy.max_append_bytes or start_sample + count > self.processed_samples:
                raise ValueError("processed read exceeds bounded size or committed cursor")
            if count == 0:
                return b""
            end = start_sample + count
            with self.store._db() as db:
                rows = db.execute("""SELECT start_sample,samples,data_name FROM segments
                                     WHERE session_id=? AND kind='processed' AND start_sample>? AND start_sample<?
                                     ORDER BY start_sample""",
                                  (self.session_id, start_sample - self.store.policy.segment_samples, end))
                state = self._states["processed"]
                extra = []
                if state and state["start"] < end and state["start"] + state["samples"] > start_sample:
                    extra = [{"start_sample": state["start"], "samples": state["samples"], "data_name": state["name"] + ".part"}]
                result = bytearray()
                cursor = start_sample
                for row in itertools.chain(rows, extra):
                    take = min(end, row["start_sample"] + row["samples"]) - cursor
                    if take <= 0:
                        continue
                    if row["start_sample"] > cursor:
                        raise StorageError("committed processed timeline has a gap")
                    with self.store._audio_path(self.session_id, row["data_name"]).open("rb") as source:
                        source.seek((cursor - row["start_sample"]) * 4)
                        data = source.read(take * 4)
                    if len(data) != take * 4:
                        raise StorageError("committed processed segment is truncated")
                    result.extend(data)
                    cursor += take
                    if cursor == end:
                        break
            if cursor != end:
                raise StorageError("committed processed timeline is incomplete")
            return bytes(result)

    def raw_receipt(self):
        """Independently read back the committed raw spool with bounded buffers."""
        with self._mutex:
            if self.spec['mode'] != 'raw_processed':
                raise StorageError('This session has no raw stream')
            frame_bytes = self.spec['raw']['channels']*self.spec['raw']['sample_width_bytes']
            digest = hashlib.sha256()
            cursor = 0
            state = self._states['raw']
            tail = [] if state is None else [dict(start_sample=state['start'], samples=state['samples'], data_name=state['name']+'.part')]
            for segment in itertools.chain(self.store._segments(self.session_id, 'raw'), tail):
                if segment['start_sample'] != cursor:
                    raise StorageError('Raw spool timeline is non-contiguous')
                expected = segment['samples']*frame_bytes
                path = self.store._audio_path(self.session_id, segment['data_name'])
                if path.stat().st_size != expected:
                    raise StorageError('Raw spool segment extent changed')
                with path.open('rb') as source:
                    while data := source.read(65536):
                        digest.update(data)
                cursor += segment['samples']
            if cursor != self.raw_samples:
                raise StorageError('Raw spool sample count differs from committed cursor')
            return dict(samples=cursor, bytes=cursor*frame_bytes, sha256=digest.hexdigest(),
                        complete_source_readback=True, session_id=self.session_id)

    def stop(self, final_sample=None):
        """Seal after the caller has stopped input and drained all accepted data."""
        with self._mutex:
            if self.closed:
                raise StorageError("session is already closed")
            if final_sample is not None and final_sample != self.processed_samples:
                raise StorageError("stop boundary does not match drained processed sample count")
            try:
                self._seal("processed")
                self._seal("raw")
                with self.store._db() as db:
                    db.execute("UPDATE sessions SET status='stopped',processed_samples=?,raw_samples=?,updated=? WHERE id=?",
                               (self.processed_samples, self.raw_samples, time.time(), self.session_id))
                result = self.store._publish(self.session_id)
                self._release()
                return result
            except BaseException as error:
                try:
                    self.fail("stop publication failed: " + type(error).__name__ + ": " + str(error))
                except BaseException as secondary:
                    error.add_note('Stop publication cleanup also failed: '+repr(secondary))
                raise

    def _release(self):
        errors = []
        for lease in (self._session_lock, self._lease):
            try:
                lease.close()
            except BaseException as error:
                errors.append(error)
        self.closed = self._session_lock.file is None and self._lease.file is None
        if errors:
            for secondary in errors[1:]:
                errors[0].add_note('Additional spool lease release error: '+repr(secondary))
            raise errors[0]
        if not self.closed:
            raise StorageError('Spool lease close did not release both handles')

    def fail(self, reason, *, cancelled=False):
        with self._mutex:
            if self.closed:
                return self.store.read(self.session_id)
            for state in self._states.values():
                if state:
                    for name in ("replay", "replay_file", "data"):
                        try:
                            if state[name]:
                                state[name].close()
                        except OSError:
                            pass
            primary = None
            try:
                with self.store._db() as db:
                    db.execute("UPDATE sessions SET status=?,reason=?,updated=? WHERE id=?",
                               ("cancelled" if cancelled else "failed", str(reason)[:4096], time.time(), self.session_id))
                if self.spec.get('terminal_metadata_reserve_bytes', 0):
                    raw_reason = str(reason).encode('utf-8')
                    self.store.write_terminal_event(self.session_id, 'session_failure',
                        dict(reason=raw_reason[:2048].decode('utf-8',errors='replace'),reason_sha256=hashlib.sha256(raw_reason).hexdigest(),
                             processed_samples=self.processed_samples,raw_samples=self.raw_samples,
                             cancelled=cancelled,physical_process_closed=False))
                return self.store._publish(self.session_id)
            except BaseException as error:
                primary = error
                raise
            finally:
                try:
                    self._release()
                except BaseException as secondary:
                    if primary is None:
                        raise
                    primary.add_note('Failure publication lease cleanup also failed: '+repr(secondary))

    def cancel(self, reason="cancelled by operator"):
        return self.fail(reason, cancelled=True)

    def keep(self, include_raw=False):
        return self.store.keep(self.session_id, include_raw=include_raw)

    def discard(self):
        return self.store.discard(self.session_id)
