"""Exact historical post-analysis with explicit external archive recovery.
See README_S6C_CONTROLS_RECOVERY_ANALYSIS_V1.md.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import json
import sys
import types
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/"reports/S6C/20260910T123540Z"
PAYLOAD=Path("G:/Just_Peachy_S6C/20260910T123540Z")
BASE_SHA="e5497ec28daa6c5f823fde53e7f1253cf655427cd30f8eab067de5e9a4c0f530"
OVERLAY_SHA="e2f6dece6c9062e35f8cdeece73376a670e4ba3d390059a8b04de85548afadf8"
MANIFEST=PAYLOAD/"paced_controls/controls_fast_v1/MANIFEST.json"
MANIFEST_SHA="8fb281fe4788e549cfb294bdcfb6adf326144cfeefbb1d09c76cf22f7b26c044"
HELPER="s6c_controls_recovery_analysis_v1.py"
README="README_S6C_CONTROLS_RECOVERY_ANALYSIS_V1.md"
OVERLAY="s6c_controls_recovery_inventory_v1"
NAMES={"baseline":"controls_b00_recovered_fast_v1","research":"controls_b01_recovered_fast_v1"}

def require(value,message):
    if not value:raise ValueError(message)

def exact(path,sha=None):
    p=Path(path).resolve()
    require(p.stat().st_size<=32*2**20,"Small explicit code/metadata inputs only")
    raw=p.read_bytes();require(len(raw)<=32*2**20,"Input grew beyond metadata cap")
    b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    require(sha is None or b["sha256"]==sha,"Exact source/input bytes changed: "+str(p))
    return raw,b

def load(name,sha):
    path=HERE/(name+".py");exact(path,sha)
    module=importlib.import_module(name)
    require(Path(module.__file__).resolve()==path.resolve(),"Imported source origin differs")
    return module

def own_sources():
    return [exact(HERE/HELPER)[1],exact(HERE/README)[1]]

def runtime():
    require(len(OVERLAY_SHA)==64,"Recovery overlay pin is not held")
    return load("s6c_fast_observer_analysis_v1",BASE_SHA),load(OVERLAY,OVERLAY_SHA)

def pair(value):
    require(value is not None and len(value)==2,"Explicit PATH SHA256 required")
    raw,b=exact(*value);json.loads(raw);return b

def selected(generation,namespace,manifest):
    require(generation in NAMES,"One original historical generation required")
    require(namespace==NAMES[generation],"Use the explicit fresh recovery analysis namespace")
    require(Path(manifest["path"]).resolve()==MANIFEST.resolve() and manifest["sha256"]==MANIFEST_SHA,
            "Recovery is limited to the exact original controls_fast_v1 manifest")

def build_context(base,inventory,recovery_binding):
    """Private globals only; the scientific converter retains its exact code."""
    old=dict(base.prepare.__globals__)
    ns=dict(old)
    def source_bindings():
        exact(HERE/"s6c_fast_observer_analysis_v1.py",BASE_SHA)
        exact(recovery_binding["path"],recovery_binding["sha256"])
        return base.unique_bindings(base.sources()+inventory.source_bindings()+own_sources()+[recovery_binding])
    ns["sources"]=source_bindings
    private_make=base.private_function(base.make_adapter,ns)
    def make_adapter(kind,observer_index,request_binding,explicit_inputs,inventory_override=None):
        require(kind=="historical","Recovery adapter admits only historical controls")
        require(inventory_override is None or inventory_override is inventory,"Inventory context replacement rejected")
        adapter,mod=private_make(kind,observer_index,request_binding,explicit_inputs,inventory=inventory)
        require(adapter.proof["identical_function_code_objects"],"Scientific adapter code identity failed")
        return adapter,mod
    ns["make_adapter"]=make_adapter
    prepare=base.private_function(base.prepare,ns)
    run=base.private_function(base.run,ns)
    require(prepare.__code__ is base.prepare.__code__ and run.__code__ is base.run.__code__,
            "Original request/preparation/run code changed")
    require(all(base.prepare.__globals__.get(k) is v for k,v in old.items()),"Original globals mutated")
    proof=dict(
        schema="s6c-controls-recovery-analysis-context.v1",
        original_prepare_code=base.code_signature(base.prepare),
        original_run_code=base.code_signature(base.run),
        original_make_adapter_code=base.code_signature(base.make_adapter),
        exact_code_objects=True,original_globals_unchanged=True,
        inventory_context="Explicit external recovery binding attached per reader; no global mutation.",
        scientific_converter="Held historical converter; generation, clocks, repeats, parity and arithmetic unchanged.",
        failure_semantics="Original failed observer exit remains failed history; external archive recovery is a separate authority.")
    return types.SimpleNamespace(prepare=prepare,run=run,sources=source_bindings,proof=proof,
                                 namespace=ns,make_adapter=make_adapter)

def context(recovery_pair):
    base,overlay=runtime()
    recovery=pair(recovery_pair)
    inv=overlay.make_inventory(recovery)
    return base,build_context(base,inv,recovery),recovery

def prepare(args):
    require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Shared quiet lease remains; no analysis admission")
    base,adapter,recovery=context(args.recovery)
    manifest=pair(args.manifest)
    selected(args.generation,args.namespace,manifest)
    original=argparse.Namespace(kind="historical",namespace=args.namespace,
        observer_index=args.observer_index,manifest=args.manifest,index=None,admission=None,generation=args.generation)
    result=adapter.prepare(original)
    return dict(schema="s6c-controls-recovery-analysis-preparation.v1",status="PREPARED",
                recovery=recovery,context=adapter.proof,**result)

def run(args):
    require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Shared quiet lease remains; no analysis run")
    base,adapter,recovery=context(args.recovery)
    raw,rb=exact(*args.request);request=json.loads(raw)
    require(request["kind"]=="historical","Recovered request family differs")
    require(set(request["inputs"])=={"manifest"},"Recovered request has unrelated inputs")
    selected(request["generation"],request["namespace"],request["inputs"]["manifest"])
    require(request["sources"]==adapter.sources(),"Recovery/source context differs from prepared request")
    # The unchanged base run rereads and binds this exact PATH+SHA request, its
    # observer index, original plan and source list before calling the converter.
    result=adapter.run(argparse.Namespace(request=[rb["path"],rb["sha256"]],plan=args.plan))
    return dict(schema="s6c-controls-recovery-analysis-result.v1",status="COMPLETE",
                recovery=recovery,original_result=result,context=adapter.proof)

def checks():
    base,overlay=runtime()
    checks=[]
    def ok(name,value):
        require(value,name);checks.append(name)
    def bad(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):checks.append(name);return
        raise AssertionError(name+" accepted")
    ok("exact held recovery overlay source",exact(HERE/(OVERLAY+".py"))[1]["sha256"]==OVERLAY_SHA)
    ok("explicit recovery inventory factory",callable(overlay.make_inventory))
    fake_recovery=dict(path=str(REPORT/"UNREAD_RECOVERY_FIXTURE.json"),bytes=0,sha256="0"*64)
    inv=base.load_module("s6c_execution_inventory_v7",base.V7_SHA)
    originals={n:getattr(base,n) for n in ("prepare","run","make_adapter","sources")}
    private=build_context(base,inv,fake_recovery)
    for n in ("prepare","run"):
        ok(n+" exact held code",getattr(private,n).__code__ is originals[n].__code__)
        ok(n+" private globals",getattr(private,n).__globals__ is not originals[n].__globals__)
    for n,f in originals.items():ok(n+" original binding unchanged",getattr(base,n) is f)
    b=dict(path=str(MANIFEST.resolve()),sha256=MANIFEST_SHA,bytes=835211)
    for gen,name in NAMES.items():selected(gen,name,b);ok(gen+" exact namespace",True)
    bad("mixed generation rejected",lambda:selected("mixed",NAMES["baseline"],b))
    bad("wrong generation namespace rejected",lambda:selected("baseline",NAMES["research"],b))
    bad("wrong manifest hash rejected",lambda:selected("baseline",NAMES["baseline"],dict(b,sha256="1"*64)))
    bad("wrong manifest path rejected",lambda:selected("baseline",NAMES["baseline"],dict(b,path=str(MANIFEST.parent/"OTHER.json"))))
    bad("ordinary canonical conversion rejected",lambda:private.make_adapter("canonical",b,b,[]))
    bad("inventory replacement rejected",lambda:private.make_adapter("historical",b,b,[],types.SimpleNamespace()))
    adapter,mod=private.make_adapter("historical",b,b,[])
    ok("original historical science unchanged",bool(adapter.proof["scientific_objects_unchanged"]))
    ok("historical orchestration code exact",adapter.proof["identical_function_code_objects"])
    ok("reader factory private",adapter.inventory.base.MetadataReader is not inv.base.MetadataReader)
    old=mod.selected_jobs
    jobs=dict(jobs=[dict(profile_id=p,telemetry=None,realtime=True) for p in ("B00","B01")])
    ok("B00 selected separately",[j["profile_id"] for j in old(jobs,"baseline")]==["B00"])
    ok("B01 selected separately",[j["profile_id"] for j in old(jobs,"research")]==["B01"])
    # Actual V7/recovery schema and closure are the overlay's separately tested
    # boundary. These fixtures never read an actual recovery/index/native result.
    return dict(schema="s6c-controls-recovery-analysis-checks.v1",status="PASS_SOURCE_AND_TINY_CONTEXT_ONLY",
        check_count=len(checks),checks=checks,sources=own_sources()+[exact(HERE/"s6c_fast_observer_analysis_v1.py",BASE_SHA)[1],exact(HERE/(OVERLAY+".py"),OVERLAY_SHA)[1]],
        actual_recovery_read=False,actual_observer_index_read=False,actual_analysis_prepared=False,
        actual_analysis_run=False,new_model_calls=0,overlay_pin_held=len(OVERLAY_SHA)==64)

def main():
    ap=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    sub=ap.add_subparsers(dest="action",required=True)
    sub.add_parser("checks")
    p=sub.add_parser("prepare")
    p.add_argument("--recovery",nargs=2,required=True,metavar=("PATH","SHA256"))
    p.add_argument("--observer-index",nargs=2,required=True,metavar=("PATH","SHA256"))
    p.add_argument("--manifest",nargs=2,required=True,metavar=("PATH","SHA256"))
    p.add_argument("--generation",choices=tuple(NAMES),required=True)
    p.add_argument("--namespace",choices=tuple(NAMES.values()),required=True)
    p=sub.add_parser("run")
    for n in ("recovery","request","plan"):p.add_argument("--"+n,nargs=2,required=True,metavar=("PATH","SHA256"))
    args=ap.parse_args()
    result=checks() if args.action=="checks" else prepare(args) if args.action=="prepare" else run(args)
    print(json.dumps(result,indent=2,allow_nan=False))

if __name__=="__main__":main()
