"""Verified public resume entry point. See README_s6a_probe_resume.md."""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

SCRIPT_DIR=Path(__file__).resolve().parent
DEFAULT_REPORT=SCRIPT_DIR.parent/"reports/S6A/20260909T202250Z"


class BindingMismatch(ValueError):
    pass


def stable(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False,default=str).encode()).hexdigest()


def uncached_binding(path):
    """Always read bytes, even if length and mtime equal an earlier read."""
    p=Path(path).resolve()
    before=p.stat(); h=hashlib.sha256()
    with p.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""):h.update(block)
    after=p.stat()
    if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise BindingMismatch("file changed during hash: "+str(p))
    return {"path":str(p),"sha256":h.hexdigest(),"bytes":after.st_size}


def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name("."+path.name+"."+uuid.uuid4().hex+".tmp")
    with temp.open("x",encoding="utf-8") as f:
        json.dump(value,f,indent=2,allow_nan=False);f.flush();os.fsync(f.fileno())
    os.replace(temp,path)


def verify_manifest(manifest_path):
    mp=Path(manifest_path).resolve()
    mb=uncached_binding(mp)
    manifest=json.loads(mp.read_text(encoding="utf-8"))
    if manifest.get("schema")!="jp_s6a_probe_jobs_v2":
        raise BindingMismatch("unsupported probe manifest schema")
    if not isinstance(manifest.get("jobs"),list) or not manifest["jobs"]:
        raise BindingMismatch("manifest has no jobs")
    if not isinstance(manifest.get("execution_code"),list) or not manifest["execution_code"]:
        raise BindingMismatch("manifest has no execution code bindings")
    for job in manifest["jobs"]:
        ident=job["identity"]
        if stable(ident)!=job["job_key"]:raise BindingMismatch("job key does not match complete supplied identity")
        for outer,inner in (("profile","profile"),("input_audio","audio"),("raw_audio","raw_audio"),("telemetry","telemetry")):
            if job.get(outer)!=ident.get(inner):raise BindingMismatch("job/identity binding differs: "+outer)
        if ident.get("code")!=manifest["execution_code"]:raise BindingMismatch("job code identity differs from manifest")
        for required in ("assets","provider","gain_once","process_lifecycle","schema"):
            if required not in ident:raise BindingMismatch("missing identity dependency: "+required)
        if not isinstance(ident["assets"],list) or not ident["assets"]:
            raise BindingMismatch("missing asset bindings")
    bindings={}
    declared=0
    def walk(value,where="$"):
        nonlocal declared
        if isinstance(value,dict):
            if "path" in value and "sha256" in value:
                declared+=1
                p=str(Path(value["path"]).resolve());key=os.path.normcase(p)
                expected=value["sha256"]
                if not isinstance(expected,str) or len(expected)!=64:
                    raise BindingMismatch("invalid expected SHA256: "+where)
                row=bindings.setdefault(key,{"path":p,"sha256":expected,"declared_bytes":set(),"locations":[]})
                if row["sha256"]!=expected:raise BindingMismatch("conflicting hashes for path: "+p)
                if "bytes" in value:row["declared_bytes"].add(value["bytes"])
                row["locations"].append(where)
            for key,item in value.items():walk(item,where+"."+key)
        elif isinstance(value,list):
            for i,item in enumerate(value):walk(item,where+"["+str(i)+"]")
    walk(manifest)
    verified=[]
    for row in bindings.values():
        actual=uncached_binding(row["path"])
        if actual["sha256"]!=row["sha256"]:raise BindingMismatch("content SHA256 mismatch: "+row["path"])
        if row["declared_bytes"] and row["declared_bytes"]!={actual["bytes"]}:
            raise BindingMismatch("declared byte length mismatch: "+row["path"])
        # Compact role paths avoid repeating the same binding hundreds of times.
        verified.append({**actual,"declaration_count":len(row["locations"]),"first_declaration":row["locations"][0]})
    if uncached_binding(mp)!=mb:raise BindingMismatch("manifest changed during verification")
    return {"status":"PASS","manifest":mb,"jobs":len(manifest["jobs"]),"declared_binding_occurrences":declared,
            "unique_files_verified":len(verified),"verified_bindings":verified,
            "hash_method":"uncached full SHA256 on each unique declared path; compare expected hashes and declared lengths",
            "scope":"invocation-boundary verification; all dependencies must remain immutable during execution"}


def guarded_dispatch(manifest_path,launch_receipt,callback,*,workers=2,limit=None):
    check=verify_manifest(manifest_path)
    import psutil
    proc=psutil.Process()
    receipt={"status":"VERIFIED_BEFORE_DISPATCH","created_utc":datetime.now(timezone.utc).isoformat(),
             "guard_source":uncached_binding(__file__),"verification":check,
             "pid":proc.pid,"creation_time":proc.create_time(),"workers":workers,"limit":limit,
             "native_job_identity_changed":False,"callback":"unchanged s6a_probes.run",
             "scope":"existing result identity preserved; byte verification precedes runner entry"}
    atomic(launch_receipt,receipt)
    print(json.dumps({"phase":"resume_dependencies_verified","files":check["unique_files_verified"],"jobs":check["jobs"],
                      "pid":proc.pid,"creation_time":proc.create_time(),"receipt":str(launch_receipt)}),flush=True)
    return callback(workers,limit)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workers",type=int,choices=range(1,5),default=2)
    p.add_argument("--limit",type=int)
    p.add_argument("--verify-only",action="store_true")
    args=p.parse_args()
    if args.limit is not None and args.limit<1:p.error("--limit must be positive")
    report=DEFAULT_REPORT;manifest=report/"PROBE_JOB_MANIFEST_V2.json"
    # Verify any already-declared code before importing the frozen runner.
    if manifest.exists():verify_manifest(manifest)
    import s6a_probes as probes
    if probes.REPORT.resolve()!=report.resolve():raise BindingMismatch("runner report does not match guard scope")
    if not manifest.exists():probes.prepare()  # Fresh creation remains the existing prepare authority.
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"_"+uuid.uuid4().hex[:8]
    receipt_path=report/"resume_guards"/stamp/"LAUNCH.json"
    if args.verify_only:
        def callback(workers,limit):return None
    else:
        callback=probes.run
    result=guarded_dispatch(manifest,receipt_path,callback,workers=args.workers,limit=args.limit)
    atomic(report/"PROBE_RESUME_GUARD_LATEST.json",{"mode":"VERIFY_ONLY" if args.verify_only else "RUN",
           "guard_launch":uncached_binding(receipt_path),"guard_source":uncached_binding(__file__),
           "completed_utc":datetime.now(timezone.utc).isoformat()})
    return result


if __name__=="__main__":main()

