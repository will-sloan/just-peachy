"""Frozen-queue S6D code-only supervisor. Read s6d_runner_README.md first."""
from __future__ import annotations
import argparse
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
import psutil

sys.dont_write_bytecode = True
ACTIONS = {"WAIT", "ADVANCE_CHECKPOINT", "REPORT_BLOCKED", "REVIEW_FAILURE", "FINISH"}
HEALTH_SECONDS = 15
HEARTBEAT_SECONDS = 30
INTERPRETATION = {"sensitive": 600, "normal": 900, "cached": 1800}
CAMPAIGN_STARTED_UTC = "2026-09-13T19:53:57+00:00"
CAMPAIGN_MAX_SECONDS = 72 * 3600
CLOSEOUT_MIN_SECONDS = 45 * 60


def utc():
    return datetime.now(timezone.utc).isoformat()


def finite_number(value, minimum=0, strict=False):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > minimum if strict else value >= minimum))


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("campaign times require explicit timezone")
    return parsed.timestamp()


def work_deadline(queue):
    if queue.get("fixture_only") is True:
        return None
    campaign = queue["campaign"]
    return timestamp(campaign["deadline_utc"]) - campaign["closeout_reserve_s"]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def binding(path, expected=None):
    path = Path(path).resolve()
    before = path.stat()
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("source changed during binding")
    if expected is not None and h.hexdigest() != expected:
        raise ValueError("source SHA256 mismatch: " + str(path))
    return {"path": str(path), "bytes": before.st_size, "sha256": h.hexdigest()}


def load(path, retries=3, delay=.05):
    last = None
    for attempt in range(retries):
        try:
            return json.loads(Path(path).read_text(encoding="utf-8-sig"))
        except (FileNotFoundError, json.JSONDecodeError, PermissionError, UnicodeDecodeError) as exc:
            last = exc
            if attempt + 1 < retries:
                time.sleep(delay)
    raise ValueError("missing, partial, locked or invalid JSON after bounded reads: " + str(path)) from last


def save(path, value, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open("x", encoding="utf-8") as f:
            json.dump(value, f, indent=2, allow_nan=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        return
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    with temporary.open("x", encoding="utf-8") as f:
        json.dump(value, f, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def append(path, value):
    with Path(path).open("a", encoding="utf-8") as f:
        f.write(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def within(path, roots):
    path = Path(path).resolve()
    return any(path.is_relative_to(Path(root).resolve()) for root in roots)


def process_matches(pid, creation_time):
    try:
        p = psutil.Process(int(pid))
        return p.is_running() and abs(p.create_time() - float(creation_time)) < .001
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, TypeError):
        return False


class OwnerLock:
    def __init__(self, directory, run_id, queue_sha256):
        self.path = Path(directory) / "SUPERVISOR_LOCK.json"
        self.identity = {"run_id": run_id, "queue_sha256": queue_sha256, "pid": os.getpid(),
            "creation_time": psutil.Process().create_time(), "owner_nonce": uuid.uuid4().hex, "created_utc": utc()}
        self.keep_unresolved = False

    def acquire(self):
        if self.path.exists():
            prior = load(self.path)
            if prior.get("unresolved_hardware"):
                raise ValueError("unresolved hardware restoration lock requires explicit recovery")
            if process_matches(prior.get("pid"), prior.get("creation_time")):
                raise ValueError("another supervisor owner is alive")
            stale = self.path.with_name("STALE_LOCK_" + uuid.uuid4().hex + ".json")
            os.rename(self.path, stale)
        save(self.path, self.identity, exclusive=True)

    def retain_for_hardware(self, job_identity):
        self.keep_unresolved = True
        save(self.path, {**self.identity, "unresolved_hardware": job_identity, "blocked_utc": utc()})

    def close(self):
        if self.keep_unresolved:
            return "RETAINED_UNRESOLVED_HARDWARE"
        current = load(self.path)
        if current.get("owner_nonce") != self.identity["owner_nonce"]:
            raise ValueError("supervisor lock ownership changed")
        closed = self.path.with_name("CLOSED_LOCK_" + self.identity["owner_nonce"] + ".json")
        os.rename(self.path, closed)
        return "RELEASED_TO_IMMUTABLE_CLOSED_RECEIPT"


class KeepAwake:
    def __init__(self, requested=False, api=None):
        self.requested, self.owned = requested, False
        self.api = api
        self.receipt = {"requested": requested, "owned": False, "restored": None}

    def acquire(self):
        if not self.requested:
            self.receipt["status"] = "NOT_USED"
            return
        if self.api is None:
            if os.name != "nt":
                raise ValueError("keep-awake is Windows-only")
            self.api = ctypes.windll.kernel32.SetThreadExecutionState
        if not self.api(0x80000001):
            raise ValueError("keep-awake acquisition failed")
        self.owned = True
        self.receipt.update(owned=True, status="OWNED")

    def close(self):
        if self.owned:
            restored = bool(self.api(0x80000000))
            self.receipt.update(restored=restored, status="RESTORED" if restored else "RESTORATION_FAILED")
            if restored:
                self.owned = False
        return self.receipt


def validate_queue(queue, approval, queue_hash):
    if queue.get("schema") != "s6d_approved_job_queue_v1" or approval.get("schema") != "s6d_queue_approval_v1":
        raise ValueError("unsupported queue/approval schema")
    if approval.get("queue_sha256") != queue_hash or approval.get("run_id") != queue.get("run_id"):
        raise ValueError("queue not bound to approval")
    for key in ("run_id", "owner_thread_id", "owner_session_id"):
        if not isinstance(queue.get(key), str) or not queue[key]:
            raise ValueError("explicit run/thread/session identity required")
    if not approval.get("authorization_ref"):
        raise ValueError("authorization evidence reference required")
    binding(__file__, queue["runner_sha256"])
    approved_jobs = set(approval["approved_job_sha256"])
    allowed_executables = {str(Path(b["path"]).resolve()): b for b in approval["executable_bindings"]}
    allowed_cwds = {str(Path(p).resolve()) for p in approval["allowed_working_directories"]}
    roots = approval["allowed_output_roots"]
    payload = queue["payload_policy"]
    if not finite_number(payload["max_new_payload_bytes"], strict=True) or payload["max_new_payload_bytes"] > 40 * 1024 ** 3:
        raise ValueError("new-payload ceiling must be at most40GiB")
    if not payload["new_payload_roots"] or not all(within(p, roots) for p in payload["new_payload_roots"]):
        raise ValueError("new-payload roots must be explicit approved roots")
    for policy in queue.get("disk_policy", []):
        if not finite_number(policy["minimum_free_bytes"]):
            raise ValueError("disk floor must be finite and nonnegative")
    if queue.get("fixture_only") is not True:
        campaign = queue.get("campaign")
        if not isinstance(campaign, dict):
            raise ValueError("production queue requires fixed campaign deadline")
        start, end = timestamp(campaign["started_utc"]), timestamp(campaign["deadline_utc"])
        if start != timestamp(CAMPAIGN_STARTED_UTC) or not 0 < end - start <= CAMPAIGN_MAX_SECONDS:
            raise ValueError("campaign start/deadline disagrees with fixed72hour authorization")
        reserve = campaign["closeout_reserve_s"]
        if not finite_number(reserve, CLOSEOUT_MIN_SECONDS) or end - reserve <= start:
            raise ValueError("at least45minutes of bounded closeout reserve required")
        floors = {}
        for policy in queue.get("disk_policy", []):
            drive = Path(policy["path"]).drive.upper()
            floors[drive] = max(floors.get(drive, 0), policy["minimum_free_bytes"])
        if floors.get("C:", 0) < 50 * 1024 ** 3 or floors.get("G:", 0) < 75 * 1024 ** 3:
            raise ValueError("production must enforce C>=50GiB and G>=75GiB floors")
    identifiers, all_outputs = set(), set()
    for job in queue["jobs"]:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", job["job_id"]):
            raise ValueError("unsafe job identifier")
        if job["job_id"] in identifiers or digest(job) not in approved_jobs:
            raise ValueError("duplicate or unapproved job")
        identifiers.add(job["job_id"])
        argv = job["argv"]
        if not isinstance(argv, list) or len(argv) < 2 or any(not isinstance(v, str) or "\x00" in v for v in argv):
            raise ValueError("argv must be a literal string array")
        if any(v.lower() in ("-c", "-command", "-encodedcommand", "/c", "--eval", "-e") for v in argv):
            raise ValueError("inline shell/code execution is forbidden")
        executable = str(Path(argv[0]).resolve())
        if not Path(argv[0]).is_absolute() or executable not in allowed_executables:
            raise ValueError("executable is not in frozen allowlist")
        if Path(executable).stem.lower() in {"cmd", "powershell", "pwsh", "bash", "sh", "wscript", "cscript"}:
            raise ValueError("shell interpreters are forbidden")
        binding(executable, allowed_executables[executable]["sha256"])
        if str(Path(job["cwd"]).resolve()) not in allowed_cwds or not Path(job["cwd"]).is_dir():
            raise ValueError("working directory not allowed")
        script = Path(argv[1]).resolve()
        declared = {str(Path(b["path"]).resolve()): b for b in job["source_bindings"]}
        if not Path(argv[1]).is_absolute() or str(script) not in declared:
            raise ValueError("literal entry script must be frozen and hash-bound")
        for path, bound in declared.items():
            observed = binding(path, bound["sha256"])
            if observed["bytes"] > 16 * 1024 ** 2:
                raise ValueError("repeated source checks accept small code only; bind model assets once in child")
        if sum(Path(p).stat().st_size for p in declared) > 64 * 1024 ** 2:
            raise ValueError("periodically checked source epoch exceeds64MiB")
        if job["workload"] not in INTERPRETATION or job["kind"] not in ("offline", "hardware"):
            raise ValueError("unknown workload/kind")
        if job["kind"] == "hardware" and job.get("allow_owned_termination", False):
            raise ValueError("hardware termination forbidden")
        for field in ("timeout_s", "stall_after_s", "heartbeat_stale_s", "stop_grace_s"):
            if not finite_number(job[field], strict=True):
                raise ValueError("positive bounded timing policy required")
        for key, value in job.get("environment", {}).items():
            if not isinstance(key, str) or not isinstance(value, str) or "\x00" in key + value:
                raise ValueError("environment overrides must be literal strings")
            if key.upper() in {"HOME", "CODEX_HOME", "USERPROFILE"} or key.upper().startswith("S6D_"):
                raise ValueError("case-insensitive system/run identity environment override forbidden")
        outputs = [job["heartbeat_path"], job["completion_path"], job["stop_request_path"]]
        if job["kind"] == "hardware":
            outputs.append(job["restoration_path"])
        if not job.get("expected_artifacts"):
            raise ValueError("explicit scientific artifact validators required")
        for item in job["expected_artifacts"]:
            if not finite_number(item.get("min_bytes", 1)):
                raise ValueError("artifact minimum length must be finite and nonnegative")
            outputs.append(item["path"])
            if item["format"] == "json":
                if not item.get("expected_fields"):
                    raise ValueError("JSON validator must declare expected fields")
            elif item["format"] == "exact_file":
                if len(item.get("sha256", "")) != 64:
                    raise ValueError("opaque artifact requires expected SHA256")
            else:
                raise ValueError("unsupported artifact validator")
        for value in outputs:
            path = str(Path(value).resolve())
            if not Path(value).is_absolute() or not within(path, roots):
                raise ValueError("output escapes declared roots")
        # Heartbeat/completion paths are job-unique; artifact paths can intentionally equal completion.
        for value in (job["heartbeat_path"], job["completion_path"]):
            path = str(Path(value).resolve())
            if path in all_outputs:
                raise ValueError("jobs share heartbeat/completion path")
            all_outputs.add(path)
    if len(identifiers) != len(queue["jobs"]):
        raise ValueError("invalid queue cardinality")
    return True


def identity_matches(document, identity):
    return all(document.get(k) == identity[k] for k in ("run_id", "job_id", "child_run_id"))


def validate_completion(job, identity):
    doc = load(job["completion_path"])
    if not identity_matches(doc, identity) or doc.get("status") != "COMPLETE":
        raise ValueError("completion identity/status mismatch")
    result = []
    for artifact in job["expected_artifacts"]:
        path = Path(artifact["path"])
        bound = binding(path, artifact.get("sha256"))
        if bound["bytes"] < artifact.get("min_bytes", 1):
            raise ValueError("artifact too small")
        if artifact["format"] == "json":
            value = load(path)
            for dotted, expected in artifact["expected_fields"].items():
                actual = value
                for key in dotted.split("."):
                    actual = actual[key]
                if actual != expected:
                    raise ValueError("artifact expected field mismatch: " + dotted)
        result.append(bound)
    return {"completion": binding(job["completion_path"]), "artifacts": result,
            "scientific_scope": "Only declared artifact predicates validated; no aggregate S6D PASS inferred"}


def classify(*, alive, exit_code, heartbeat_valid, heartbeat_age, progress_age, elapsed,
             heartbeat_stale, stall_after, timeout, completion_ok, interruption=None):
    if interruption in ("AUTH_REQUIRED", "QUOTA_EXHAUSTED"):
        return "REPORT_BLOCKED", interruption + "; no automatic retry"
    if not alive:
        if exit_code not in (0, None):
            return "REVIEW_FAILURE", "child exited nonzero"
        if completion_ok:
            return "ADVANCE_CHECKPOINT", "declared completion artifacts verified"
        return "REPORT_BLOCKED", "child exited without valid bound completion artifacts"
    if elapsed >= timeout:
        return "REVIEW_FAILURE", "declared overall timeout exceeded"
    if progress_age >= stall_after:
        return "REVIEW_FAILURE", "declared progress-stall threshold exceeded; liveness remains separate"
    if not heartbeat_valid or heartbeat_age >= heartbeat_stale:
        return "WAIT", "alive with stale/missing heartbeat; not assumed dead or hung"
    return "WAIT", "healthy progress"


def bounded_delta(value):
    result = {k: value.get(k) for k in ("run_id", "stage", "action", "reason", "done", "total", "job_id", "elapsed_s",
        "eta_range_s", "resource_maxima", "next_command", "checkpoint_path", "log_path", "continuation")}
    for key in ("reason", "next_command", "checkpoint_path", "log_path"):
        if isinstance(result[key], str):
            result[key] = result[key][:350]
    encoded = json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > 2048:
        result["resource_maxima"] = {"rss_bytes": (result["resource_maxima"] or {}).get("rss_bytes")}
        for key in ("reason", "next_command", "checkpoint_path", "log_path"):
            if isinstance(result[key], str):
                result[key] = result[key][:200]
        encoded = json.dumps(result, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    if len(encoded) > 2048:
        raise ValueError("status delta exceeds2048byte policy")
    return result


def restored(job, identity):
    try:
        value = load(job["restoration_path"])
        return identity_matches(value, identity) and value.get("status") == "RESTORED" and value.get("verified") is True
    except ValueError:
        return False


def terminate_owned_offline(job, identity):
    if job["kind"] != "offline" or not job.get("allow_owned_termination", False):
        return "TERMINATION_NOT_AUTHORIZED"
    if not process_matches(identity["pid"], identity["creation_time"]):
        return "PID_NOT_OWNED_NO_ACTION"
    # Only this exact child process is terminated; never taskkill, killall or inferred unrelated descendants.
    psutil.Process(identity["pid"]).terminate()
    try:
        psutil.Process(identity["pid"]).wait(timeout=2)
        return "OWNED_OFFLINE_CHILD_TERMINATION_VERIFIED"
    except psutil.NoSuchProcess:
        return "OWNED_OFFLINE_CHILD_TERMINATION_VERIFIED"
    except psutil.TimeoutExpired:
        return "OWNED_OFFLINE_CHILD_TERMINATION_UNCONFIRMED"


class Supervisor:
    def __init__(self, queue_path, approval_path, queue_sha256, approval_sha256, state_dir,
                 keep_awake=False, test_interval=None):
        self.queue_path, self.approval_path = Path(queue_path).resolve(), Path(approval_path).resolve()
        self.queue_binding = binding(self.queue_path, queue_sha256)
        self.approval_binding = binding(self.approval_path, approval_sha256)
        self.queue, self.approval = load(self.queue_path), load(self.approval_path)
        validate_queue(self.queue, self.approval, queue_sha256)
        self.directory = Path(state_dir).resolve()
        if not within(self.directory, self.approval["allowed_output_roots"]):
            raise ValueError("state directory outside approved outputs")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = OwnerLock(self.directory, self.queue["run_id"], queue_sha256)
        self.awake = KeepAwake(keep_awake)
        self.health_seconds = HEALTH_SECONDS if test_interval is None else test_interval
        if test_interval is not None and not self.queue.get("fixture_only"):
            raise ValueError("accelerated interval reserved for fixture-only queues")
        self.state_path = self.directory / "CHECKPOINT.json"
        self.state = {"run_id": self.queue["run_id"], "queue_sha256": queue_sha256, "completed": {},
            "active": None, "status": "READY", "resource_maxima": {}, "started_utc": utc()}
        if self.state_path.exists():
            prior = load(self.state_path)
            if (prior.get("run_id"), prior.get("queue_sha256")) != (self.queue["run_id"], queue_sha256):
                raise ValueError("checkpoint belongs to another run/queue")
            self.state = prior
        self.last_heartbeat = 0
        self.last_interpretation = 0
        self.last_signature = None
        self.last_payload_scan = 0
        self.payload_bytes = 0

    def persist(self):
        self.state["updated_utc"] = utc()
        save(self.state_path, self.state)

    def emit(self, action, reason, job=None, elapsed=0, meaningful=False):
        if action not in ACTIONS:
            raise ValueError("non-allowlisted decision")
        self.state.update(status=action, reason=reason)
        self.persist()
        delta = bounded_delta({"run_id": self.queue["run_id"], "stage": "CODE_ONLY_SUPERVISION", "action": action,
            "reason": reason, "done": len(self.state["completed"]), "total": len(self.queue["jobs"]),
            "job_id": job["job_id"] if job else None, "elapsed_s": round(elapsed, 3), "eta_range_s": None,
            "resource_maxima": self.state["resource_maxima"], "next_command": "Resume only the explicit approved queue and checkpoint; see RESUME_REQUEST.json",
            "checkpoint_path": str(self.state_path), "log_path": str(self.directory / "HEALTH.jsonl"),
            "continuation": "MANUAL_RESUME_REQUEST_FALLBACK; unattended model interpretation unavailable"})
        save(self.directory / "STATUS_DELTA.json", delta)
        if meaningful:
            save(self.directory / "RESUME_REQUEST.json", {"run_id": self.queue["run_id"],
                "owner_thread_id": self.queue["owner_thread_id"], "owner_session_id": self.queue["owner_session_id"],
                "action": action, "reason": reason, "created_utc": utc(), "automatic_model_resume_installed": False,
                "no_chat_reminder_installed": True, "no_model_retry_loop": True,
                "queue": self.queue_binding, "approval": self.approval_binding, "state_dir": str(self.directory),
                "resume_argv": [sys.executable, str(Path(__file__).resolve()), "--queue", str(self.queue_path),
                    "--approval", str(self.approval_path), "--queue-sha256", self.queue_binding["sha256"],
                    "--approval-sha256", self.approval_binding["sha256"], "--state-dir", str(self.directory)],
                "checkpoint": binding(self.state_path), "delta": delta})
        return delta

    def resources(self, identity):
        sample = {"utc": utc(), "rss_bytes": 0, "uss_bytes": 0, "pss_bytes": None,
            "process_count": 0, "system_available_bytes": psutil.virtual_memory().available,
            "queue_age_s": None, "disk_free_bytes": {}}
        if process_matches(identity["pid"], identity["creation_time"]):
            try:
                parent = psutil.Process(identity["pid"])
                processes = [parent] + parent.children(recursive=True)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                processes = []
            for p in processes:
                try:
                    memory = p.memory_full_info()
                    sample["rss_bytes"] += memory.rss
                    sample["uss_bytes"] += getattr(memory, "uss", 0)
                    if hasattr(memory, "pss"):
                        sample["pss_bytes"] = (sample["pss_bytes"] or 0) + memory.pss
                    sample["process_count"] += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
        for policy in self.queue.get("disk_policy", []):
            free = psutil.disk_usage(policy["path"]).free
            sample["disk_free_bytes"][policy["path"]] = free
            if free < policy["minimum_free_bytes"]:
                sample["disk_violation"] = policy["path"]
        if time.time() - self.last_payload_scan >= 60:
            seen = set()
            total = 0
            for root in self.queue["payload_policy"]["new_payload_roots"]:
                for directory, subdirectories, files in os.walk(root, followlinks=False):
                    subdirectories[:] = [d for d in subdirectories if not Path(directory, d).is_symlink()]
                    for name in files:
                        path = Path(directory, name)
                        try:
                            resolved = str(path.resolve())
                            if resolved not in seen and not path.is_symlink():
                                total += path.stat().st_size
                                seen.add(resolved)
                        except FileNotFoundError:
                            pass
            self.payload_bytes, self.last_payload_scan = total, time.time()
        sample["new_payload_bytes"] = self.payload_bytes
        sample["payload_accounting_age_s"] = time.time() - self.last_payload_scan
        if self.payload_bytes >= self.queue["payload_policy"]["max_new_payload_bytes"]:
            sample["payload_violation"] = True
        for key in ("rss_bytes", "uss_bytes", "process_count"):
            self.state["resource_maxima"][key] = max(self.state["resource_maxima"].get(key, 0), sample[key])
        return sample

    def stop_child(self, job, identity, reason):
        save(job["stop_request_path"], {**identity, "reason": reason, "created_utc": utc(), "request": "STOP_AND_RESTORE"})
        deadline = time.monotonic() + job["stop_grace_s"]
        while time.monotonic() < deadline:
            alive = process_matches(identity["pid"], identity["creation_time"])
            if job["kind"] == "hardware":
                if restored(job, identity) and not alive:
                    return "HARDWARE_RESTORATION_VERIFIED_AND_OWNER_EXITED"
            elif not alive:
                return "OFFLINE_CHILD_EXITED_AFTER_STOP"
            time.sleep(min(self.health_seconds, .25))
        if job["kind"] == "hardware":
            self.lock.retain_for_hardware(identity)
            save(self.directory / "HARDWARE_RESTORATION_PENDING.json", {**identity,
                "status": "REPORT_BLOCKED", "stop_request_path": job["stop_request_path"],
                "restoration_path": job["restoration_path"], "termination_attempted": False,
                "independent_owner_watchdog_remains_required": True})
            return "HARDWARE_RESTORATION_PENDING_NO_TERMINATION"
        return terminate_owned_offline(job, identity)

    def run_job(self, job):
        binding(self.queue_path, self.queue_binding["sha256"])
        binding(self.approval_path, self.approval_binding["sha256"])
        for source in job["source_bindings"]:
            binding(source["path"], source["sha256"])
        active = self.state.get("active")
        process = None
        if active is not None:
            if active["job_id"] != job["job_id"]:
                raise ValueError("checkpoint active job disagrees with queue")
            identity = active
        else:
            deadline = work_deadline(self.queue)
            if deadline is not None and time.time() + job["timeout_s"] + job["stop_grace_s"] > deadline:
                return self.emit("REPORT_BLOCKED", "next job does not fit fixed campaign work deadline and closeout reserve", job, meaningful=True)
            resource_preflight = self.resources({"pid": None, "creation_time": None})
            if resource_preflight.get("disk_violation") or resource_preflight.get("payload_violation"):
                return self.emit("REPORT_BLOCKED", "resource preflight failed before child launch", job, meaningful=True)
            for path in (job["heartbeat_path"], job["completion_path"], job["stop_request_path"]):
                if Path(path).exists():
                    raise ValueError("fresh job output already exists; explicit new attempt required")
            identity = {"run_id": self.queue["run_id"], "job_id": job["job_id"], "child_run_id": uuid.uuid4().hex,
                "started_unix": time.time(), "last_progress_unix": time.time(), "progress_count": None,
                "pid": None, "creation_time": None, "launch_state": "INTENT_PERSISTED"}
            self.state["active"] = identity
            self.persist()
            env = os.environ.copy()
            for key, value in job.get("environment", {}).items():
                if key.upper() in {"HOME", "CODEX_HOME", "USERPROFILE"} or key.upper().startswith("S6D_"):
                    raise ValueError("system identity environment override forbidden")
                env[key] = value
            env.update(S6D_RUN_ID=identity["run_id"], S6D_JOB_ID=identity["job_id"], S6D_CHILD_RUN_ID=identity["child_run_id"],
                       S6D_HEARTBEAT_PATH=job["heartbeat_path"], S6D_COMPLETION_PATH=job["completion_path"],
                       S6D_STOP_REQUEST_PATH=job["stop_request_path"])
            if job["kind"] == "hardware":
                env["S6D_RESTORATION_PATH"] = job["restoration_path"]
            log = (self.directory / (job["job_id"] + "_" + identity["child_run_id"] + ".log")).open("xb")
            try:
                process = subprocess.Popen(job["argv"], cwd=job["cwd"], env=env, shell=False,
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            finally:
                log.close()
            identity.update(pid=process.pid, creation_time=psutil.Process(process.pid).create_time(), launch_state="LAUNCHED")
            self.state["active"] = identity
            self.persist()
            save(self.directory / ("LAUNCH_" + identity["child_run_id"] + ".json"), {
                **identity, "job_sha256": digest(job), "argv": job["argv"], "cwd": job["cwd"],
                "queue": self.queue_binding, "shell": False}, exclusive=True)
        while True:
            if identity.get("pid") is None:
                return self.emit("REPORT_BLOCKED", "incomplete launch intent requires reconciliation; no automatic relaunch", job, meaningful=True)
            binding(self.queue_path, self.queue_binding["sha256"])
            binding(self.approval_path, self.approval_binding["sha256"])
            for source in job["source_bindings"]:
                binding(source["path"], source["sha256"])
            now = time.time()
            alive = process_matches(identity["pid"], identity["creation_time"])
            exit_code = process.poll() if process else None
            heartbeat, heartbeat_valid, heartbeat_age = {}, False, float("inf")
            try:
                heartbeat = load(job["heartbeat_path"])
                heartbeat_valid = identity_matches(heartbeat, identity)
                heartbeat_valid = heartbeat_valid and heartbeat.get("pid") == identity["pid"] and abs(heartbeat.get("creation_time", 0) - identity["creation_time"]) < .001
                if heartbeat_valid:
                    heartbeat_age = max(0, now - Path(job["heartbeat_path"]).stat().st_mtime)
                    progress = heartbeat.get("progress_count")
                    if finite_number(progress) and (identity.get("progress_count") is None or progress > identity["progress_count"]):
                        identity["progress_count"], identity["last_progress_unix"] = progress, now
            except ValueError:
                pass
            completion_ok, completion = False, None
            if not alive:
                try:
                    completion = validate_completion(job, identity)
                    completion_ok = True
                except (ValueError, KeyError, FileNotFoundError, TypeError):
                    pass
            action, reason = classify(alive=alive, exit_code=exit_code, heartbeat_valid=heartbeat_valid,
                heartbeat_age=heartbeat_age, progress_age=now - identity["last_progress_unix"],
                elapsed=now - identity["started_unix"], heartbeat_stale=job["heartbeat_stale_s"],
                stall_after=job["stall_after_s"], timeout=job["timeout_s"], completion_ok=completion_ok,
                interruption=heartbeat.get("interruption") if heartbeat_valid else None)
            sample = self.resources(identity)
            sample.update(job_id=job["job_id"], child_run_id=identity["child_run_id"], alive=alive,
                exit_code=exit_code, heartbeat_valid=heartbeat_valid,
                heartbeat_age_s=heartbeat_age if heartbeat_age != float("inf") else None,
                progress_age_s=now - identity["last_progress_unix"], action=action, reason=reason)
            if heartbeat_valid and isinstance(heartbeat.get("queue_age_s"), (int, float)):
                sample["queue_age_s"] = heartbeat["queue_age_s"]
            if sample.get("disk_violation"):
                action, reason = "REPORT_BLOCKED", "declared disk free-space floor violated"
            if sample.get("payload_violation"):
                action, reason = "REPORT_BLOCKED", "declared new-payload budget reached"
            deadline = work_deadline(self.queue)
            if deadline is not None and now >= deadline:
                action, reason = "REPORT_BLOCKED", "fixed campaign work deadline reached; reserve closeout/restoration"
            sample.update(action=action, reason=reason)
            append(self.directory / "HEALTH.jsonl", sample)
            if action == "ADVANCE_CHECKPOINT":
                if job["kind"] == "hardware" and not restored(job, identity):
                    self.lock.retain_for_hardware(identity)
                    return self.emit("REPORT_BLOCKED", "hardware completion lacks verified restoration", job, meaningful=True)
                self.state["completed"][job["job_id"]] = {"identity": identity, "validation": completion,
                    "exit_code": exit_code, "status": "DECLARED_ARTIFACTS_VERIFIED", "completed_utc": utc()}
                self.state["active"] = None
                return self.emit(action, reason, job, now - identity["started_unix"], meaningful=True)
            if action != "WAIT":
                if alive or job["kind"] == "hardware":
                    reason += "; " + self.stop_child(job, identity, reason)
                return self.emit(action, reason, job, now - identity["started_unix"], meaningful=True)
            if now - self.last_heartbeat >= HEARTBEAT_SECONDS:
                save(self.directory / "HEARTBEAT.json", {"utc": utc(), **self.lock.identity,
                    "job_id": job["job_id"], "child_run_id": identity["child_run_id"], "status": "WAIT", "model_turn_requested": False})
                self.emit("WAIT", reason, job, now - identity["started_unix"])
                self.last_heartbeat = now
            if now - self.last_interpretation >= INTERPRETATION[job["workload"]]:
                signature = (job["job_id"], action, reason)
                append(self.directory / "CHECKIN_OPPORTUNITIES.jsonl", {"utc": utc(), "job_id": job["job_id"],
                    "interval_s": INTERPRETATION[job["workload"]], "unchanged": signature == self.last_signature,
                    "model_turn_requested": False, "usage": None,
                    "continuation": "MANUAL_FALLBACK; no automatic model channel qualified"})
                self.last_signature, self.last_interpretation = signature, now
            time.sleep(self.health_seconds)

    def run(self):
        self.lock.acquire()
        result = None
        try:
            self.awake.acquire()
            for job in self.queue["jobs"]:
                if job["job_id"] in self.state["completed"]:
                    saved = self.state["completed"][job["job_id"]]
                    current = validate_completion(job, saved["identity"])
                    if current != saved["validation"]:
                        raise ValueError("completed artifacts changed; refusing rerun or silent reuse")
                    continue
                result = self.run_job(job)
                if result["action"] != "ADVANCE_CHECKPOINT":
                    break
            else:
                result = self.emit("FINISH", "all approved queue jobs have declared artifact receipts; broader S6D scope remains separate", meaningful=True)
        except Exception as exc:
            reason = type(exc).__name__ + ": " + str(exc)
            active = self.state.get("active")
            if active and active.get("pid"):
                active_job = next(j for j in self.queue["jobs"] if j["job_id"] == active["job_id"])
                if active_job["kind"] == "hardware" or process_matches(active["pid"], active["creation_time"]):
                    reason += "; " + self.stop_child(active_job, active, reason)
            result = self.emit("REPORT_BLOCKED", reason, meaningful=True)
        finally:
            awake = self.awake.close()
            if awake.get("restored") is False:
                result = self.emit("REPORT_BLOCKED", "owned keep-awake restoration failed", meaningful=True)
            lock_status = self.lock.close()
            save(self.directory / ("SUPERVISOR_CLOSURE_" + self.lock.identity["owner_nonce"] + ".json"), {
                "run_id": self.queue["run_id"], "utc": utc(), "result": result,
                "owner_lock": lock_status, "keep_awake": awake, "automatic_model_resume_installed": False,
                "model_usage": None, "hardware_restoration_unresolved": self.lock.keep_unresolved}, exclusive=True)
        return result


def cli():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--queue-sha256", required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--keep-awake", action="store_true")
    args = parser.parse_args()
    runner = Supervisor(args.queue, args.approval, args.queue_sha256, args.approval_sha256, args.state_dir, args.keep_awake)
    result = {"status": "APPROVED_QUEUE_VALID", "production_jobs_launched": 0} if args.validate_only else runner.run()
    print(json.dumps(result), flush=True)
    return 0 if result.get("action") == "FINISH" or args.validate_only else 2


if __name__ == "__main__":
    raise SystemExit(cli())
