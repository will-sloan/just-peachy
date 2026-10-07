"""Read-only injected production-unit metadata action; README_NORMAL_MANUAL_INSPECTION.md."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import stat
import subprocess
import time
import zlib

SCHEMA = "just-peachy.normal-manual-unit-inspection.v1"
HOME = Path("/home/peachyprototype/JustPeachy")
MAX_METADATA_BYTES = 2*1024**2


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate metadata key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda value:(_ for _ in ()).throw(ValueError("Nonfinite metadata")))


def sha(value):
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ValueError("Explicit actual SHA256 required")
    return value


def ordinary(path, maximum=MAX_METADATA_BYTES):
    path = Path(path)
    info = path.lstat()
    if (path.is_symlink() or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or not 0 <= info.st_size <= maximum or path.resolve(strict=True) != path):
        raise ValueError("Canonical ordinary bounded metadata required")
    raw = path.read_bytes()
    after = path.stat()
    if (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns) != (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):
        raise ValueError("Metadata changed during read")
    return raw


def identity(pid, boot):
    if type(pid) is not int or pid < 1:
        raise ValueError("Exact positive PID required")
    fields = Path("/proc",str(pid),"stat").read_text().rsplit(")",1)[1].split()
    return dict(pid=pid,start_ticks=int(fields[19]),boot_id=boot)


def owner(value, boot):
    if (type(value) is not dict or set(value) != {"pid","start_ticks","boot_id"}
            or type(value["pid"]) is not int or value["pid"] < 1
            or type(value["start_ticks"]) is not int or value["start_ticks"] < 1
            or value["boot_id"] != boot):
        raise ValueError("Exact native owner identity required")
    return value


def properties(unit):
    names=("ActiveState","MainPID","InvocationID","ControlGroup","RuntimeMaxUSec",
           "AllowedCPUs","CPUQuotaPerSecUSec","TasksMax")
    result=subprocess.run(["systemctl","--user","show",unit,"--property="+",".join(names)],
        check=True,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5)
    if len(result.stdout)+len(result.stderr)>65536:
        raise ValueError("Systemd metadata exceeds bounded parser allocation")
    values=dict(line.split("=",1) for line in result.stdout.splitlines() if "=" in line)
    if set(values)!=set(names):
        raise ValueError("Complete actual systemd state required")
    return values


def in_group(pid, group):
    return any(line.endswith(":"+group) for line in Path("/proc",str(pid),"cgroup").read_text().splitlines())


def read_health(row):
    if row is None:
        return None
    raw, encoding, size, digest = row
    if type(size) is not int or not 0<=size<=MAX_METADATA_BYTES:
        raise ValueError("Bounded health metadata required")
    if encoding=="json":
        data=raw.encode() if isinstance(raw,str) else bytes(raw)
    elif encoding=="zlib-json-v1":
        decoder=zlib.decompressobj()
        data=decoder.decompress(raw,MAX_METADATA_BYTES+1)
        if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
            raise ValueError("Incomplete or trailing compressed health metadata")
    else:
        raise ValueError("Unsupported actual health encoding")
    if len(data)>MAX_METADATA_BYTES or (size and len(data)!=size) or (digest and hashlib.sha256(data).hexdigest()!=digest):
        raise ValueError("Actual health size/hash differs")
    value=strict(data)
    names=("source_samples","speaker_cursor_seconds","speaker_analyzed_through_seconds",
        "asr_cursor_seconds","speaker_lag_seconds","asr_lag_seconds","backlog_seconds",
        "dropped_audio","available_ram","virtual_bytes","rss","state")
    result={}
    for name in names:
        item=value.get(name)
        if item is None or (type(item) in (int,float) and math.isfinite(item)) or (name=="state" and type(item) is str):
            result[name]=item
        else:
            raise ValueError("Unexpected scalar health field")
    return result


def database_snapshot(root, session_id):
    """Bounded consistent read-only counts/health; never recovery or quick_check on active DB."""
    path=root/"recordings/history.sqlite3"
    if path.is_symlink() or path.resolve(strict=True)!=path:
        raise ValueError("Canonical existing history database required")
    deadline=time.monotonic()+3
    db=sqlite3.connect(path.as_uri()+"?mode=ro",uri=True,timeout=.2)
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA cache_size=-256")
        db.set_progress_handler(lambda:1 if time.monotonic()>deadline else 0,1000)
        db.execute("BEGIN")
        session=db.execute("SELECT status,processed_samples,raw_samples FROM sessions WHERE id=?",(session_id,)).fetchone()
        counts={name:db.execute("SELECT COUNT(*) FROM "+name+" WHERE session_id=?",(session_id,)).fetchone()[0]
                for name in ("captions","segments","events","artifacts","caption_projections")}
        health=db.execute("SELECT payload,payload_encoding,payload_bytes,payload_sha256 FROM events "
            "WHERE session_id=? AND event_type='health' ORDER BY seq DESC LIMIT 1",(session_id,)).fetchone()
        return dict(session=None if session is None else dict(status=session[0],processed_samples=session[1],raw_samples=session[2]),
                    counts=counts,health=read_health(health))
    finally:
        db.rollback()
        db.close()


def inspect_manual_unit(p, baseline):
    required={"schema","package","package_manifest_sha256","boot_id","expires_unix","data_root",
        "unit_ownership","unit_ownership_sha256","expected_app_owner","expected_worker_owner",
        "phase","launch_id","session_id"}
    if type(p) is not dict or set(p)!=required or p["schema"]!=SCHEMA:
        raise ValueError("One exact sealed inspection payload required")
    if type(p["expires_unix"]) not in (int,float) or not time.time()<p["expires_unix"]<=time.time()+600:
        raise ValueError("Fresh finite read-only admission window required")
    boot=Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    if p["boot_id"]!=boot:
        raise ValueError("Current boot changed")
    if p["phase"] not in ("idle","running","stopped","discarded"):
        raise ValueError("Explicit actual application phase required")
    root=Path(p["data_root"])
    package=Path(p["package"])
    if (root!=HOME/"data/runtime-v29" or root.resolve(strict=True)!=root
            or not package.is_absolute() or package.resolve(strict=True)!=package or HOME not in package.parents):
        raise ValueError("Exact canonical production root/package required")
    manifest_raw=ordinary(package/"PACKAGE_MANIFEST.json")
    if hashlib.sha256(manifest_raw).hexdigest()!=sha(p["package_manifest_sha256"]):
        raise ValueError("Activated actual package manifest differs")
    manifest=strict(manifest_raw)
    for row in manifest["files"]:
        relative=PurePosixPath(row["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix()!=row["path"] or "\\" in row["path"]:
            raise ValueError("Unsafe inventoried package path")
        raw=ordinary(package.joinpath(*relative.parts))
        if len(raw)!=row["bytes"] or hashlib.sha256(raw).hexdigest()!=row["sha256"]:
            raise ValueError("Actual package member differs")
    receipt_path=Path(p["unit_ownership"])
    if (receipt_path.name!="UNIT_OWNERSHIP.json" or receipt_path.parent.parent!=root/"unit-owners"
            or re.fullmatch("[0-9a-f]{32}",receipt_path.parent.name) is None):
        raise ValueError("Actual production unit-owner path required")
    receipt_raw=ordinary(receipt_path)
    if hashlib.sha256(receipt_raw).hexdigest()!=sha(p["unit_ownership_sha256"]):
        raise ValueError("Actual unit receipt differs")
    receipt=strict(receipt_raw)
    app=owner(p["expected_app_owner"],boot)
    if (receipt["owner"]!=app or receipt["main_pid"]!=app["pid"]
            or receipt["lifetime_policy"]!="manual_stop_storage_guarded"
            or receipt["runtime_max_seconds"] is not None or receipt["deadline_monotonic"] is not None):
        raise ValueError("Actual production manual lifetime/owner required")
    unit=receipt["unit"]
    if type(unit) is not str or re.fullmatch("jp-v29-[a-z0-9-]+(?:\\.service)?",unit) is None:
        raise ValueError("Exact owned production unit required")
    state=properties(unit)
    if (state["ActiveState"]!="active" or state["RuntimeMaxUSec"]!="infinity"
            or state["MainPID"]!=str(app["pid"]) or state["InvocationID"]!=receipt["invocation_id"]
            or state["ControlGroup"]!=receipt["control_group"] or state["AllowedCPUs"] not in ("2-3","2,3")
            or state["CPUQuotaPerSecUSec"]!="2s" or state["TasksMax"]!="64"
            or identity(app["pid"],boot)!=app or not in_group(app["pid"],state["ControlGroup"])):
        raise ValueError("Actual unit envelope or exact app identity differs")
    argv=Path("/proc",str(app["pid"]),"cmdline").read_bytes().split(b"\0")
    if os.fsencode(package/"native_scope.py") not in argv or os.fsencode(package/"BINDING.json") not in argv:
        raise ValueError("Actual application does not execute the bound production package")
    facts=dict(schema=SCHEMA,phase=p["phase"],boot_id=boot,package_manifest_sha256=p["package_manifest_sha256"],
        unit=unit,app_owner=app,unit_state=state,manual_production_lifetime_verified=True,
        metadata_only=True,models_loaded_by_inspector=False,runtime_mutated=False,lease_acquired_by_inspector=False,
        native_quality_claimed=False,gui_actions_performed_by_inspector=False)
    if p["phase"]!="idle":
        if any(type(p[name]) is not str or re.fullmatch("[0-9a-f]{32}",p[name]) is None for name in ("launch_id","session_id")):
            raise ValueError("Exact already-observed launch/session IDs required")
        launch=root/"launches"/p["launch_id"]
        current=strict(ordinary(root/"CURRENT_LAUNCH.json"))
        if current.get("launch_id")!=p["launch_id"]:
            raise ValueError("Actual current launch differs")
        request_raw=ordinary(launch/"REQUEST.json")
        request=strict(request_raw)
        policy=request["policy"]
        duration=policy["maximum_session_seconds"]
        if (request["unit"]!=unit
                or request["binding"]!=str(package/"BINDING.json")
                or policy["manual_stop"] is not True or policy["max_backlog_seconds"] is not None
                or type(duration) is not int or duration<1 or policy["max_drain_seconds"]!=duration):
            raise ValueError("Actual worker request does not use normal capacity policy")
        worker=owner(p["expected_worker_owner"],boot)
        registration=strict(ordinary(launch/"worker/REGISTERED_OWNER.json"))
        session=strict(ordinary(launch/"worker/SESSION.json"))
        child=strict(ordinary(launch/"CHILD_LAUNCH.json"))
        if (registration!=worker or session["worker"]!=worker or session["session_id"]!=p["session_id"]
                or child["child_owner"]!=worker or child["manager"]!=app
                or child["request_sha256"]!=hashlib.sha256(request_raw).hexdigest()):
            raise ValueError("Exact worker/session/request ownership differs")
        try:
            observed=identity(worker["pid"],boot)
            worker_alive=observed==worker
        except FileNotFoundError:
            worker_alive=False
        if p["phase"]=="running" and (not worker_alive or not in_group(worker["pid"],state["ControlGroup"])):
            raise ValueError("Expected exact worker is not active in production unit")
        if p["phase"] in ("stopped","discarded") and worker_alive:
            raise ValueError("Worker remains alive after expected closure")
        facts.update(worker_owner=worker,exact_worker_alive=worker_alive,policy=policy,
            request_sha256=hashlib.sha256(request_raw).hexdigest(),
            database=database_snapshot(root,p["session_id"]),
            session_directory_exists=os.path.lexists(root/"recordings/sessions"/p["session_id"]))
        if p["phase"]=="discarded" and (facts["session_directory_exists"] or facts["database"]["session"] is not None
                or any(facts["database"]["counts"].values())):
            raise ValueError("Discard did not remove all selected audio/caption/event/projection content")
    elif any(p[name] is not None for name in ("expected_worker_owner","launch_id","session_id")):
        raise ValueError("Idle inspection does not invent a worker or session")
    if properties(unit)!=state or identity(app["pid"],boot)!=app:
        raise ValueError("Production unit changed during inspection; retry with fresh exact metadata")
    return facts


RESULT = inspect_manual_unit(PAYLOAD, BASELINE)
