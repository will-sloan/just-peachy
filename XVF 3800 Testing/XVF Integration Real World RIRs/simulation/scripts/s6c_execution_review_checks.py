"""Independent model-free S6C job admission checks. See README_S6C_EXECUTION_REVIEW_CHECKS.md."""
from __future__ import annotations
import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

SIM = Path(__file__).resolve().parents[1]
REPORT = SIM / "reports/S6C/20260910T123540Z"
sys.dont_write_bytecode = True

def binding(path):
    p=Path(path).resolve(); raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8") as f:
        json.dump(value,f,indent=2,allow_nan=False); f.write("\n")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,required=True)
    args=ap.parse_args()
    output=args.output.resolve()
    if REPORT.resolve() not in output.parents or output.exists():
        raise ValueError("Require a fresh child of this S6C report")
    output.mkdir(parents=True)
    snapshots=output/"reviewed_source"; snapshots.mkdir()
    source_inputs=[]
    for name in ("s6c_common.py","s6c_execution.py"):
        src=SIM/"scripts"/name
        shutil.copyfile(src,snapshots/name)
        source_inputs.append(dict(original=binding(src),snapshot=binding(snapshots/name)))
    os.environ["JP_S6C_SIM"]=str(SIM)
    sys.path.insert(0,str(snapshots))
    import s6c_execution as ex
    fixtures=output/"synthetic_fixtures"; fixtures.mkdir()
    ex.PAYLOAD=fixtures/"payload"; ex.PAYLOAD.mkdir()
    checks=[]
    def check(name,fn):
        try:
            detail=fn()
            checks.append(dict(name=name,status="PASS",detail=detail))
        except Exception as exc:
            checks.append(dict(name=name,status="FAIL",error=repr(exc)))
    def rejects(fn):
        try: fn()
        except (ValueError,RuntimeError,KeyError,AssertionError):
            return "rejected before native entrypoint"
        raise AssertionError("Invalid mutation was admitted")
    def blob(name,raw):
        p=fixtures/name; p.write_bytes(raw); return binding(p)
    a=blob("source_O0.bin",b"admitted synthetic O0")
    b=blob("source_O1.bin",b"admitted synthetic O1")
    cue=blob("real_cue.json",b'{"synthetic_real_cue":true}')
    asset=blob("asset.bin",b"synthetic asset identity, not a model")
    rows=[dict(case_id="TEST_SCENE",stream=tap,audio=audio,
               audio_pcm_sha256=hashlib.sha256(tap.encode()).hexdigest(),
               telemetry=cue,duration_sec=1.)
          for tap,audio in (("O0",a),("O1",b))]
    index=fixtures/"input_index.json";write(index,dict(rows=rows))
    profile=dict(candidate_id="TEST_C",recipe_id="TEST_N",asr_tap="O0",identity_tap="O1",
                 profile=dict(schema_version="synthetic_schema_for_guard_only"),
                 gallery_condition="NONE",cue_condition="CUES_OFF",enrollment_tier=None)
    spec=dict(epoch="synthetic_epoch",execution_digest="fixed_test_epoch",
              profiles=[profile],input_index=binding(index),
              assets=[dict(component_id="redimnet2_b2_fp32",path=asset["path"],sha256=asset["sha256"])])
    job=ex.make_job(spec,profile,"TEST_SCENE","test",attempt="one")
    def admit(j=None,s=None): return ex.validate_job(spec if s is None else s,job if j is None else j)
    check("exact isolated job admitted",lambda: (admit(),"only fake files were hashed")[1])
    mutations=[
        ("job key",lambda j:j.update(job_key="changed")),
        ("top-level profile",lambda j:j["profile"].update(changed=True)),
        ("candidate identity",lambda j:j.update(candidate_id="wrong")),
        ("recipe identity",lambda j:j.update(recipe_id="wrong")),
        ("tap declaration",lambda j:j.update(identity_tap="O0")),
        ("PCM expectation",lambda j:j.update(asr_pcm_sha256="bad")),
        ("duration",lambda j:j.update(duration_sec=2.)),
        ("outside output namespace",lambda j:j.update(folder=str(fixtures/"outside"))),
        ("hidden telemetry",lambda j:j.update(telemetry=cue)),
        ("top-level realtime",lambda j:j.update(realtime=True)),
    ]
    for name,mutate in mutations:
        def exercise(mutate=mutate):
            j=deepcopy(job); mutate(j)
            return rejects(lambda:admit(j))
        check("reject changed "+name,exercise)
    def epoch():
        j=deepcopy(job);j["identity"]["execution_digest"]="wrong";j["job_key"]=ex.digest(j["identity"])
        return rejects(lambda:admit(j))
    check("reject self-consistent wrong epoch",epoch)
    def profile_consistent():
        j=deepcopy(job);j["profile"]["changed"]=True;j["identity"]["profile"]=deepcopy(j["profile"]);j["job_key"]=ex.digest(j["identity"])
        return rejects(lambda:admit(j))
    check("reject self-consistent unregistered profile",profile_consistent)
    for role,path in (("asr source",Path(a["path"])),("identity source",Path(b["path"])),("asset",Path(asset["path"]))):
        def mutate_bytes(path=path):
            raw=path.read_bytes(); path.write_bytes(raw+b"changed")
            try:return rejects(admit)
            finally:path.write_bytes(raw)
        check("reject in-place "+role+" byte change",mutate_bytes)
    def bad_index():
        raw=index.read_bytes();index.write_bytes(raw+b" ")
        try:return rejects(lambda:ex.make_job(spec,profile,"TEST_SCENE","test"))
        finally:index.write_bytes(raw)
    check("make_job verifies exact input index",bad_index)
    def valid_cue():
        p=deepcopy(profile);p["candidate_id"]="TEST_REAL";p["cue_condition"]="REAL_ALIGNED_CUES"
        s=deepcopy(spec);s["profiles"]=[p]
        j=ex.make_job(s,p,"TEST_SCENE","test");ex.validate_job(s,j)
        return s,j
    check("real cue job admitted",lambda: (valid_cue(),"admitted")[1])
    def changed_cue():
        s,j=valid_cue();path=Path(cue["path"]);raw=path.read_bytes();path.write_bytes(raw+b" ")
        try:return rejects(lambda:ex.validate_job(s,j))
        finally:path.write_bytes(raw)
    check("reject in-place cue mutation",changed_cue)
    def wrong_real_cue():
        s,j=valid_cue();other=blob("other_cue.json",b"{}")
        j["telemetry"]=other;j["identity"]["telemetry"]=other;j["job_key"]=ex.digest(j["identity"])
        return rejects(lambda:ex.validate_job(s,j))
    check("reject different real-cue capture",wrong_real_cue)
    # Cache route tests use only small synthetic receipt/artifact records. They
    # invoke the actual verify_job guard, not a replacement implementation.
    folder=Path(job["folder"]);folder.mkdir(parents=True)
    artifacts={key:blob("cache_"+key+".bin",key.encode()) for key in ("evidence","vectors","events","summary")}
    aj=blob("audio_spool.pcm16",b"a"*32000);ij=blob("identity_audio_spool.pcm16",b"b"*32000)
    cache_job=deepcopy(job);cache_job["asr_pcm_sha256"]=aj["sha256"];cache_job["identity_pcm_sha256"]=ij["sha256"]
    receipt=dict(status="COMPLETE",job_key=cache_job["job_key"],identity=cache_job["identity"],
                 journals={"audio_spool.pcm16":aj,"identity_audio_spool.pcm16":ij},elapsed_sec=.01,**artifacts)
    receipt_path=folder/"run_receipt.json";write(receipt_path,receipt)
    def replace_receipt(value):
        receipt_path.write_text(json.dumps(value),encoding="utf-8")
    check("exact synthetic cached artifacts admitted",lambda:ex.verify_job(cache_job)["status"])
    for label,mutator in (
        ("swapped named PCM",lambda r:r.update(journals={"audio_spool.pcm16":ij,"identity_audio_spool.pcm16":aj})),
        ("missing journal",lambda r:r["journals"].pop("identity_audio_spool.pcm16")),
        ("unexpected journal",lambda r:r["journals"].update(extra=aj)),
        ("failed cache",lambda r:r.update(status="FAILED")),
        ("cache job identity",lambda r:r.update(job_key="wrong")),
    ):
        def bad_cache(mutator=mutator):
            r=deepcopy(receipt);mutator(r);replace_receipt(r)
            try:return rejects(lambda:ex.verify_job(cache_job))
            finally:replace_receipt(receipt)
        check("reject "+label,bad_cache)
    def corrupt_cached():
        p=Path(artifacts["evidence"]["path"]);raw=p.read_bytes();p.write_bytes(raw+b"changed")
        try:return rejects(lambda:ex.verify_job(cache_job))
        finally:p.write_bytes(raw)
    check("reject changed cached evidence bytes",corrupt_cached)
    # Assert execution ownership indirectly only: no code path below called
    # freeze, worker_init, worker_job, run, or any app/model API.
    unchanged=all(binding(x["original"]["path"])==x["original"] for x in source_inputs)
    result=dict(schema="s6c.independent_execution_guard_checks.v1",
                status="PASS" if unchanged and all(x["status"]=="PASS" for x in checks) else "FAIL",
                checks=checks,passed=sum(x["status"]=="PASS" for x in checks),total=len(checks),
                source_inputs=source_inputs,source_unchanged_during_check=unchanged,
                code=binding(Path(__file__)),
                readme=binding(Path(__file__).with_name("README_S6C_EXECUTION_REVIEW_CHECKS.md")),
                scope="Synthetic metadata/bytes and real job/cache guard functions only. No model, audio decode, worker/coordinator launch, actual campaign cache or hardware call. Does not certify real artifacts or runtime closure.",
                exclusions=["Gallery condition-to-roster admission awaits the separately frozen gallery registry.",
                            "Actual named PCM routing must additionally pass the native smoke.",
                            "Pure guard fixtures do not measure throughput, memory, or native accuracy."])
    write(output/"CHECK_RECEIPT.json",result)
    print(json.dumps({k:result[k] for k in ("status","passed","total","source_unchanged_during_check")}))
    raise SystemExit(0 if result["status"]=="PASS" else 1)

if __name__=="__main__":main()
