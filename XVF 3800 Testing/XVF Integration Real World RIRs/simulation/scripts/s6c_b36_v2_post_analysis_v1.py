"""Private B36 V2 post-analysis/normalization; README_S6C_B36_V2_POST_ANALYSIS_V1.md."""
from __future__ import annotations
import argparse,json,types
from pathlib import Path
import s6c_fast_observer_analysis_v1 as A

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/"reports/S6C/20260910T123540Z"
MANIFEST=Path("G:/Just_Peachy_S6C/20260910T123540Z/paced_controls/b36_fast_v2/MANIFEST.json")
MANIFEST_SHA="a19d8b5bebdc425256f8f546072b018ff5c65665a23ffab3064e75fafe7294b1"
BASE_SHA="e5497ec28daa6c5f823fde53e7f1253cf655427cd30f8eab067de5e9a4c0f530"
NORMALIZER_SHA="d94507a8f7f4246b8f6a377b22fd50b9c2487761a3638e32bd650d49ac953b0b"
INVENTORY_SHA="7741c2207124d03a99327ba86b19cb1cb235aa01445643ba6654202beada234c"
NAME="b36_v2_analysis_fast_v2"
HELPER="s6c_b36_v2_post_analysis_v1.py"
README="README_S6C_B36_V2_POST_ANALYSIS_V1.md"

def require(v,m):
    if not v:raise ValueError(m)

def fixed_manifest(b):
    require(Path(b["path"]).resolve()==MANIFEST.resolve() and b["sha256"]==MANIFEST_SHA,
            "Only the exact B36 V2 manifest is supported")

def own_sources():
    return [A.bind(HERE/HELPER),A.bind(HERE/README),
            A.exact(HERE/"s6c_fast_observer_analysis_v1.py",BASE_SHA)[1],
            A.exact(HERE/"s6c_runtime_metadata_normalizer_v1.py",NORMALIZER_SHA)[1]]

def runtime():
    A.exact(HERE/"s6c_fast_observer_analysis_v1.py",BASE_SHA)
    require(len(INVENTORY_SHA)==64,"Inventory source pin is not held")
    I=A.load_module("s6c_b36_v2_inventory_v1",INVENTORY_SHA)
    N=A.load_module("s6c_runtime_metadata_normalizer_v1",NORMALIZER_SHA)
    return I.make_inventory(),N

def analysis_context(inv):
    old=A.prepare.__globals__;ns=dict(old)
    def sources():return A.unique_bindings(A.sources()+inv.source_bindings()+own_sources())
    ns["sources"]=sources
    private_make=A.private_function(A.make_adapter,ns)
    def make_adapter(kind,observer,request,inputs,inventory=None):
        require(kind=="historical" and inventory is None,"B36 V2 historical context only")
        result=private_make(kind,observer,request,inputs,inventory=inv)
        require(result[0].proof["identical_function_code_objects"],"Original conversion code changed")
        return result
    ns["make_adapter"]=make_adapter
    prepared=A.private_function(A.prepare,ns);run=A.private_function(A.run,ns)
    require(prepared.__code__ is A.prepare.__code__ and run.__code__ is A.run.__code__,"Original orchestration code")
    return types.SimpleNamespace(prepare=prepared,run=run,sources=sources,make_adapter=make_adapter,namespace=ns)

def normalization_context(N,analysis,inv):
    facade=types.SimpleNamespace(**vars(A));facade.sources=analysis.sources;facade.make_adapter=analysis.make_adapter
    ns=dict(N.run.__globals__)
    def module(name):
        if name=="s6c_fast_observer_analysis_v1":return facade
        if name=="s6c_execution_inventory_v7":return inv
        return N.module(name)
    def sources():return A.unique_bindings(N.sources()+analysis.sources()+own_sources())
    ns.update(module=module,sources=sources)
    run=A.private_function(N.run,ns)
    require(run.__code__ is N.run.__code__,"Original normalization code changed")
    for name in ("historical_rows","analysis_chain","runtime_row","historical_tail","historical_condition","owners_closed","require_distinct_runtime_sessions"):
        require(ns[name] is N.run.__globals__[name],"Scientific metadata function changed")
    return types.SimpleNamespace(run=run,namespace=ns,sources=sources)

def prepare(args):
    require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Shared quiet lease remains")
    fixed_manifest(A.input_binding(args.manifest))
    inv,N=runtime();ctx=analysis_context(inv)
    return ctx.prepare(argparse.Namespace(kind="historical",namespace=NAME,observer_index=args.observer_index,
        manifest=args.manifest,index=None,admission=None,generation="research"))

def run(args):
    require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Shared quiet lease remains")
    raw,rb=A.exact(*args.request);request=json.loads(raw)
    require(request["kind"]=="historical" and request["generation"]=="research" and request["namespace"]==NAME,
            "One exact B36 V2 research request")
    require(set(request["inputs"])=={"manifest"},"Unexpected request inputs")
    fixed_manifest(request["inputs"]["manifest"])
    inv,N=runtime();ctx=analysis_context(inv)
    require(request["sources"]==ctx.sources(),"Prepared source context changed")
    return ctx.run(argparse.Namespace(request=[rb["path"],rb["sha256"]],plan=args.plan))

def finite_normalization(spec):
    require("external_recovery" not in spec,"B36 V2 has its own native C archive; controls recovery is unrelated")
    require(not spec.get("physical_inventories"),"Separate whole-study physical inventory required")
    rows=spec["requests"];require(len(rows)==1,"Exactly one B36 V2 runtime request")
    row=rows[0]
    require(row["kind"]=="historical" and row["generation"]=="research","B36 V2 research generation only")
    fixed_manifest(row["manifest"])
    require(Path(row["analysis_receipt"]["path"]).resolve()==(REPORT/"historical_paced_analysis"/NAME/"RESULT.json").resolve(),
            "Exact completed B36 V2 analysis result")

def normalize(args):
    require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Shared quiet lease remains")
    inv,N=runtime();raw,b=N.exact(args.spec);require(b["sha256"]==args.spec_sha256,"Explicit normalization spec hash")
    finite_normalization(N.parse(raw))
    return normalization_context(N,analysis_context(inv),inv).run(args)

def checks():
    A.exact(HERE/"s6c_fast_observer_analysis_v1.py",BASE_SHA)
    N=A.load_module("s6c_runtime_metadata_normalizer_v1",NORMALIZER_SHA)
    inv=A.load_module("s6c_execution_inventory_v7",A.V7_SHA)
    done=[]
    def ok(name,value):require(value,name);done.append(name)
    def bad(name,f):
        try:f()
        except (ValueError,KeyError,TypeError):done.append(name);return
        raise AssertionError(name)
    held_inv,held_n=runtime()
    ok("Exact inventory source pin",A.bind(HERE/"s6c_b36_v2_inventory_v1.py")["sha256"]==INVENTORY_SHA)
    ok("New schema admitted by private inventory",held_inv.kind_of(dict(schema="s6c-historical-paced-b36-fast.v2"))=="b36")
    ctx=analysis_context(inv)
    for name in ("prepare","run"):
        ok(name+" exact held code",getattr(ctx,name).__code__ is getattr(A,name).__code__)
        ok(name+" private globals",getattr(ctx,name).__globals__ is not getattr(A,name).__globals__)
    b=dict(path=str(MANIFEST.resolve()),bytes=553498,sha256=MANIFEST_SHA)
    fixed_manifest(b);ok("Exact new manifest",True)
    bad("Old manifest path",lambda:fixed_manifest(dict(b,path=str(MANIFEST.parent.parent/"b36_fast_v1/MANIFEST.json"))))
    bad("Changed new manifest hash",lambda:fixed_manifest(dict(b,sha256="0"*64)))
    adapter,original=ctx.make_adapter("historical",b,b,[])
    ok("Original historical science",bool(adapter.proof["scientific_objects_unchanged"]))
    ok("Exact historical orchestration",adapter.proof["identical_function_code_objects"])
    bad("Canonical coercion",lambda:ctx.make_adapter("canonical",b,b,[]))
    bad("Inventory substitution",lambda:ctx.make_adapter("historical",b,b,[],inventory=inv))
    norm=normalization_context(N,ctx,inv)
    ok("Exact old normalization code",norm.run.__code__ is N.run.__code__)
    ok("Only normalizer module/source callbacks differ",{k for k,v in N.run.__globals__.items() if norm.namespace[k] is not v}=={"module","sources"})
    ok("Exact supplied inventory",norm.namespace["module"]("s6c_execution_inventory_v7") is inv)
    ok("Original output writer",norm.namespace["module"]("s6c_fast_observer_analysis_v1").write_new is A.write_new)
    spec=dict(requests=[dict(kind="historical",generation="research",manifest=b,analysis_receipt=dict(path=str(REPORT/"historical_paced_analysis"/NAME/"RESULT.json")))],physical_inventories=[])
    finite_normalization(spec);ok("One exact research normalization scope",True)
    import copy
    for name,change in [
        ("No controls recovery",lambda s:s.update(external_recovery={})),
        ("No physical inventory rewrite",lambda s:s.update(physical_inventories=[{}])),
        ("No repeated request",lambda s:s["requests"].append(s["requests"][0])),
        ("No B00 generation",lambda s:s["requests"][0].update(generation="baseline")),
        ("No foreign result",lambda s:s["requests"][0]["analysis_receipt"].update(path=str(REPORT/"OTHER/RESULT.json")))]:
        altered=copy.deepcopy(spec);change(altered);bad(name,lambda altered=altered:finite_normalization(altered))
    return dict(schema="s6c-b36-v2-post-analysis-checks.v1",status="PASS_SOURCE_AND_PRIVATE_CONTEXT_ONLY",
        check_count=len(done),checks=done,sources=own_sources()+[A.exact(HERE/"s6c_b36_v2_inventory_v1.py",INVENTORY_SHA)[1]],actual_native_admission=False,
        actual_prepare_or_analysis=False,model_calls=0,inventory_pin_held=len(INVENTORY_SHA)==64)

def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);s=p.add_subparsers(dest="action",required=True)
    s.add_parser("checks")
    q=s.add_parser("prepare")
    q.add_argument("--observer-index",nargs=2,required=True);q.add_argument("--manifest",nargs=2,required=True)
    q=s.add_parser("run");q.add_argument("--request",nargs=2,required=True);q.add_argument("--plan",nargs=2,required=True)
    q=s.add_parser("normalize");q.add_argument("--spec",type=Path,required=True);q.add_argument("--spec-sha256",required=True);q.add_argument("--namespace",required=True)
    a=p.parse_args();value=checks() if a.action=="checks" else prepare(a) if a.action=="prepare" else run(a) if a.action=="run" else normalize(a)
    print(json.dumps(value,indent=2,allow_nan=False))

if __name__=="__main__":main()
