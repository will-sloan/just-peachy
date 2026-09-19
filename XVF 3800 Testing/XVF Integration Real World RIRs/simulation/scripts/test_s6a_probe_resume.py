"""Isolated byte-mutation tests for the public resume guard. See README_s6a_probe_resume.md."""
from __future__ import annotations
import argparse
import copy
import json
import os
from pathlib import Path
import tempfile
import time
from s6a_probe_resume import BindingMismatch,atomic,guarded_dispatch,stable,uncached_binding


def run(report,output):
    output.mkdir(parents=True,exist_ok=False)
    sources=output/"isolated_sources";sources.mkdir()
    roles={"execution_code":("execution.py",b"frozen execution code A\n"),"profile":("profile.json",b'{"profile_id":"fixture"}\n'),
           "raw_audio":("raw.wav",b"R"*128),"gained_audio":("gained.wav",b"G"*128),
           "telemetry":("telemetry.jsonl",b'{"angle_deg":90,"available_at_sec":1}\n'),
           "asset":("asset.onnx",b"M"*128),"panel":("panel.json",b'{"cases":["fixture"]}\n')}
    files={}
    for role,(name,data) in roles.items():
        path=sources/name;path.write_bytes(data);files[role]=path
    bindings={role:uncached_binding(path) for role,path in files.items()}
    code=[bindings["execution_code"]]
    ident={"profile":bindings["profile"],"audio":bindings["gained_audio"],"raw_audio":bindings["raw_audio"],
           "telemetry":bindings["telemetry"],"code":code,"assets":[bindings["asset"]],"provider":"CPUExecutionProvider/cpu",
           "gain_once":1.4125375446227544,"process_lifecycle":"fresh full actual application","schema":"s6a_profile_run_v2"}
    job={"job_key":stable(ident),"identity":ident,"profile":ident["profile"],"input_audio":ident["audio"],
         "raw_audio":ident["raw_audio"],"telemetry":ident["telemetry"]}
    mp=output/"PROBE_JOB_MANIFEST_V2.json"
    atomic(mp,{"schema":"jp_s6a_probe_jobs_v2","jobs":[job],"execution_code":code,"panel":bindings["panel"]})
    manifest_before=uncached_binding(mp);input_before={k:uncached_binding(v) for k,v in files.items()}
    count={"callback":0}
    def callback(workers,limit):
        count["callback"]+=1
        return "SPY_ONLY_NO_MODEL"
    rows=[]
    got=guarded_dispatch(mp,output/"exact_launch.json",callback,workers=1)
    if got!="SPY_ONLY_NO_MODEL" or count["callback"]!=1:raise AssertionError("exact guard did not invoke spy once")
    rows.append({"test":"exact_unchanged_bindings_allow_callback","status":"PASS","callback_is_test_spy":True})
    for role,path in files.items():
        original=path.read_bytes();st=path.stat()
        changed=bytes([original[0]^1])+original[1:]
        launch=output/(role+"_must_not_launch.json")
        try:
            path.write_bytes(changed)
            os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns))
            if path.stat().st_size!=st.st_size or path.stat().st_mtime_ns!=st.st_mtime_ns:
                raise AssertionError("same-length/same-mtime mutation fixture unavailable")
            try:guarded_dispatch(mp,launch,callback,workers=1)
            except BindingMismatch as exc:
                if "content SHA256 mismatch" not in str(exc):raise
                rows.append({"test":role+"_changed_in_place","status":"PASS","same_length":True,"same_mtime_ns":True,
                             "unchanged_supplied_identity":uncached_binding(mp)==manifest_before,"result":"rejected before launch receipt or callback"})
            else:raise AssertionError("changed bytes accepted: "+role)
            if launch.exists() or count["callback"]!=1:raise AssertionError("mutation reached callback or launch receipt")
        finally:
            path.write_bytes(original);os.utime(path,ns=(st.st_atime_ns,st.st_mtime_ns))
    if uncached_binding(mp)!=manifest_before:raise AssertionError("fixture supplied identity changed")
    if {k:uncached_binding(v) for k,v in files.items()}!=input_before:raise AssertionError("fixture input restoration failed")
    exact_after=guarded_dispatch(mp,output/"restored_launch.json",callback,workers=1)
    if exact_after!="SPY_ONLY_NO_MODEL" or count["callback"]!=2:raise AssertionError("restored exact bytes did not pass")
    rows.append({"test":"restored_original_bytes_allow_callback","status":"PASS","callback_is_test_spy":True})
    receipt={"schema":"s6a_probe_resume_in_place_mutations_v1","status":"PASS","tests":len(rows),"rows":rows,
             "changed_in_place_cases":len(files),"model_launches":0,"test_spy_calls":count["callback"],
             "active_files_modified":False,"isolated_manifest_binding_unchanged":True,"isolated_source_files_restored":True,
             "guard_source":uncached_binding(Path(__file__).with_name("s6a_probe_resume.py")),"test_source":uncached_binding(__file__),
             "scope":"Real uncached byte-verification/dispatch function; isolated synthetic dependency files only. No neural inference, active dependency mutation or native identity rewrite.",
             "created_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime())}
    atomic(output/"PROBE_RESUME_GUARD_TESTS.json",receipt)
    atomic(report/"PROBE_RESUME_GUARD_TESTS.json",receipt)
    print(json.dumps({"status":"PASS","tests":len(rows),"changed_in_place_cases":len(files),"model_launches":0}),flush=True)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--report",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();run(a.report,a.output)

