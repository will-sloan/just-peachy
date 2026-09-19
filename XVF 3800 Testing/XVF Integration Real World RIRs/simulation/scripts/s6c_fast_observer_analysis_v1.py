"""Observer-aware private post-analysis contexts; README_S6C_FAST_OBSERVER_ANALYSIS_V1.md."""
from __future__ import annotations
import argparse, hashlib, importlib, json, marshal, re, sys, types
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/"reports/S6C/20260910T123540Z"
EDGE=HERE.parent.parents[2]/".edge-speech-env/python.exe"
V7_SHA="fc23ff6650a34c927211d142e61b9dcf7afe7ee07e832c51573ae2da0dc3c7a3"
PINS={
"s6c_paced_analysis_v1.py":"936b5973091d677b4eb24847e7e3e2d84df614340d3984f10ff31283096b880a",
"s6c_paced_sentinel_analysis_v1.py":"d3bc720b6c93849a0a518cd4623a938e13e949d5f3f916f54c6232cbb08af866",
"s6c_paced_cross_analysis_v1.py":"f7d7280e6b4eb2a84a1d79e6752c902373657a1658c8a46682ce50c02646cf70",
"s6c_historical_paced_analysis_v1.py":"982e1c7b2bf38fdc7a92a023cff0e73e2cbccf2072233924e6eaa5e84657a712",
"s6c_long_diagnostics_v1.py":"2e37e9b5c3cbb6021afbbf8768ed1e822fd20b7d9df6838e86c47ff590457d71",
"s6c_long_b36_diagnostics_v1.py":"f84dd4d2a45969db7b74acc94ec8a8a0b7e1ace396da205bfa2cf870835650a2"}
MODES={
"canonical":("s6c_paced_analysis_v1","paced_analysis",("canonical",)),
"sentinel":("s6c_paced_sentinel_analysis_v1","paced_arrival_analysis",("sentinel",)),
"cross":("s6c_paced_cross_analysis_v1","paced_cross_analysis",("cross",)),
"historical":("s6c_historical_paced_analysis_v1","historical_paced_analysis",("controls","b36")),
"long_c":("s6c_long_diagnostics_v1","long_diagnostics",("long_c",)),
"long_b36":("s6c_long_b36_diagnostics_v1","long_b36_diagnostics",("long_b36",))}
SCIENCE={
"canonical":("native_prediction","convert_closed_cell","active_context_observations","native_event_observations","trajectory_observations","paced_name_observations","validate_gallery_load","validate_provider","load_frozen_modules"),
"historical":("convert","research_prediction","baseline_features","emitted_observations","process_observations","pure_adapters","authority_code","research_classes"),
"long_c":("run_one","final_native_checks","stream_jsonl","trajectory","Events"),
"long_b36":("EventFacts","stream","validate_summary","trajectory","observer","pure_api","stats","require_closed")}
CAP=32*2**20

def require(value,message):
    if not value:raise ValueError(message)

def exact(path,sha=None):
    p=Path(path).resolve();require(p.stat().st_size<=CAP,"Bounded code/metadata input")
    raw=p.read_bytes();require(len(raw)<=CAP,"Input grew beyond cap")
    b=dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    require(sha is None or b["sha256"]==sha,"Exact input bytes differ: "+str(p))
    return raw,b

def bind(path):return exact(path)[1]

def code_signature(fn):
    return hashlib.sha256(marshal.dumps(fn.__code__)).hexdigest()

def load_module(name,sha):
    path=HERE/(name+".py");exact(path,sha)
    module=importlib.import_module(name)
    require(Path(module.__file__).resolve()==path.resolve(),"Import origin differs")
    return module

def sources():
    return [bind(Path(__file__)),bind(HERE/"README_S6C_FAST_OBSERVER_ANALYSIS_V1.md"),bind(HERE/"s6c_execution_inventory_v7.py")]

def name_ok(namespace):
    require(isinstance(namespace,str) and re.fullmatch(r"[A-Za-z0-9_-]{1,60}",namespace),"Simple fresh namespace required")
    require(namespace.endswith(("_fast_v1","_fast_v2")),"Explicit fast output suffix required")
    return namespace

def strict_family(inventory,kind,plan):
    require(inventory.kind_of(plan) in MODES[kind][2],"Fast analysis family differs or legacy source supplied")

def reader_factory(inventory,observer_index):
    original=inventory.base.MetadataReader
    def factory(*args,**kwargs):
        reader=original(*args,**kwargs)
        inventory.admit_observer_index(reader,observer_index)
        require(getattr(reader,"fast_observer_index",None)==observer_index,"Reader lacks exact observer context")
        return reader
    return factory

def private_function(fn,namespace):
    require(isinstance(fn,types.FunctionType),"Function expected")
    clone=types.FunctionType(fn.__code__,namespace,fn.__name__,fn.__defaults__,fn.__closure__)
    clone.__kwdefaults__=None if fn.__kwdefaults__ is None else dict(fn.__kwdefaults__);clone.__annotations__=dict(fn.__annotations__);clone.__dict__.update(fn.__dict__)
    require(clone.__code__ is fn.__code__,"Function code changed")
    return clone

def bound_wrapper(original,expected):
    """Keep original binding arithmetic; reject replacement of explicit inputs."""
    bypath={str(Path(b["path"]).resolve()).casefold():b for b in expected}
    def wrapped(*args,**kwargs):
        result=original(*args,**kwargs)
        key=str(Path(result["path"]).resolve()).casefold()
        if key in bypath:require(result==bypath[key],"Explicit admitted input changed")
        return result
    return wrapped

def unique_bindings(rows):
    out={}
    for b in rows:
        k=str(Path(b["path"]).resolve()).casefold()
        require(k not in out or out[k]==b,"Conflicting provenance source")
        out[k]=b
    return list(out.values())

def make_adapter(kind,observer_index,request_binding,explicit_inputs,inventory=None):
    require(kind in MODES,"Unknown converter kind")
    v=inventory or load_module("s6c_execution_inventory_v7",V7_SHA)
    module_name,family,_=MODES[kind]
    mod=load_module(module_name,PINS[module_name+".py"])
    original=getattr(mod,"adapter",mod) if kind in ("sentinel","cross") else mod
    # Existing sentinel/cross namespace adaptations are reused, not rebuilt.
    anchor=original.run;old=anchor.__globals__;ns=dict(old)
    metadata_factory=reader_factory(v,observer_index)
    base=types.SimpleNamespace(**vars(v.base));base.MetadataReader=metadata_factory
    if hasattr(base,"binding"):base.binding=bound_wrapper(base.binding,explicit_inputs)
    inv=types.SimpleNamespace(**vars(v));inv.base=base
    inv.CANONICAL=v.CANONICAL if kind=="canonical" else v.v5.SENTINEL if kind=="sentinel" else v.v6.CROSS if kind=="cross" else v.CANONICAL
    def admit_plan(reader,b):
        plan,pb,spec=v.admit_plan(reader,b);strict_family(v,kind,plan);return plan,pb,spec
    def admit_long(reader,b):
        result=v.admit_long(reader,b);strict_family(v,kind,result[0]);return result
    def validate_outer(reader,path,**kwargs):
        result=v.validate_outer(reader,path,**kwargs);strict_family(v,kind,result["plan"]);return result
    inv.admit_plan=admit_plan;inv.admit_long=admit_long;inv.validate_outer=validate_outer
    if kind in ("canonical","sentinel","cross"):
        names=("safe_output","prepare","run");source_name="source_bindings";ns["inventory_module"]=lambda:inv
    elif kind=="historical":
        names=("output","prepare","run");source_name="sources";ns["inventory"]=lambda:inv
    elif kind=="long_c":
        names=("output_root","admit_closed","prepare","run");source_name="sources";ns.update(V=inv,B=base)
    else:
        names=("output","load_json","read_small","prepare","run");source_name="own_sources";ns["inventory"]=lambda:inv
    expected=explicit_inputs+[observer_index,request_binding]
    for field in ("file_binding","binding"):
        if field in old:ns[field]=bound_wrapper(old[field],expected)
    original_sources=old[source_name]
    def context_sources():
        exact(HERE/"s6c_execution_inventory_v7.py",V7_SHA)
        exact(observer_index["path"],observer_index["sha256"])
        exact(request_binding["path"],request_binding["sha256"])
        return unique_bindings(original_sources()+v.source_bindings()+sources()+[observer_index,request_binding])
    ns[source_name]=context_sources
    originals={n:old[n] for n in names}
    for n,fn in originals.items():ns[n]=private_function(fn,ns)
    protected=SCIENCE["canonical" if kind in ("canonical","sentinel","cross") else kind]
    for n in protected:require(ns[n] is old[n],"Scientific function or class changed: "+n)
    proof=dict(kind=kind,namespace_family=family,cloned_metadata_or_orchestration={n:code_signature(f) for n,f in originals.items()},
        identical_function_code_objects=all(ns[n].__code__ is f.__code__ for n,f in originals.items()),
        scientific_objects_unchanged=list(protected),original_globals_unchanged=True,
        inventory_reader_factory="Per-invocation V7 explicit observer-index context; no module/global mutation.")
    require(all(old[n] is f for n,f in originals.items()),"Original function binding mutated")
    return types.SimpleNamespace(prepare=ns["prepare"],run=ns["run"],namespace=ns,inventory=inv,proof=proof),mod

def write_new(path,value):
    p=Path(path);raw=(json.dumps(value,indent=2,allow_nan=False)+"\n").encode()
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("xb") as f:f.write(raw)
    return bind(p)

def input_binding(pair):
    require(pair is not None and len(pair)==2,"Explicit PATH SHA256 pair required")
    raw,b=exact(*pair);json.loads(raw)
    return b

def prepare(args):
    require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Quiet lease remains; defer post-analysis")
    kind=args.kind;namespace=name_ok(args.namespace)
    require(not (REPORT/MODES[kind][1]/namespace).exists(),"Preserve original/previous analysis namespace")
    observer=input_binding(args.observer_index)
    inputs={}
    if kind=="long_c":
        require(args.admission and not args.manifest and not args.index,"C-long requires explicit outer admissions only")
        inputs["admissions"]=[input_binding(pair) for pair in args.admission]
        require(len({b["path"] for b in inputs["admissions"]})==len(inputs["admissions"]),"Duplicate C-long admission")
    else:
        require(not args.admission,"Outer continuous admissions are C-long only")
        inputs["manifest"]=input_binding(args.manifest)
        if kind in ("canonical","sentinel","cross"):inputs["index"]=input_binding(args.index)
        else:require(args.index is None,"This original converter has no paced-index input")
    if kind=="historical":require(args.generation in ("baseline","research"),"Explicit historical generation")
    else:require(args.generation is None,"Generation flag is historical only")
    request=dict(schema="s6c-fast-post-analysis-inputs.v1",status="EXPLICIT_INPUTS_FOR_CLOSED_ANALYSIS",
        kind=kind,namespace=namespace,generation=args.generation,observer_index=observer,inputs=inputs,sources=sources(),
        created_utc=datetime.now(timezone.utc).isoformat(),
        scope="Observer admission only. Original science/generation/repetitions retained; no native execution.")
    rp=REPORT/"fast_post_analysis_admission"/kind/namespace/"REQUEST.json"
    require(not rp.parent.exists(),"Preserve prior fast request namespace")
    rb=write_new(rp,request)
    explicit=[b for val in inputs.values() for b in (val if isinstance(val,list) else [val])]
    adapter,_=make_adapter(kind,observer,rb,explicit)
    if kind in ("canonical","sentinel","cross"):
        native=argparse.Namespace(namespace=namespace,manifest=Path(inputs["manifest"]["path"]),index=Path(inputs["index"]["path"]))
    elif kind=="long_c":
        native=argparse.Namespace(namespace=namespace,admission=[[b["path"],b["sha256"]] for b in inputs["admissions"]])
    else:
        native=argparse.Namespace(name=namespace,manifest=Path(inputs["manifest"]["path"]),manifest_sha256=inputs["manifest"]["sha256"],generation=args.generation)
    try:
        pb=adapter.prepare(native)
        # The original prepared plan binds context_sources(), including the exact
        # request/index. Original preparation/failure artifacts remain untouched.
        return dict(request=rb,original_prepared_plan=pb,adaptation=adapter.proof)
    except Exception as exc:
        write_new(rp.parent/"PREPARATION_FAILURE.json",dict(status="FAILED_PRESERVED",request=rb,error=repr(exc)))
        raise

def run(args):
    require(not (REPORT/"PACED_QUIET_OWNER.json").exists(),"Quiet lease remains; defer analysis")
    require(Path(sys.executable).resolve()==EDGE.resolve(),"Exact existing EDGE interpreter required")
    raw,rb=exact(*args.request);request=json.loads(raw);pb=input_binding(args.plan)
    require(request["schema"]=="s6c-fast-post-analysis-inputs.v1" and request["status"]=="EXPLICIT_INPUTS_FOR_CLOSED_ANALYSIS","Fast request schema/status")
    kind=request["kind"];namespace=name_ok(request["namespace"]);require(kind in MODES,"Request family")
    require(request["sources"]==sources(),"Fast adapter/inventory sources changed")
    require(Path(rb["path"])==REPORT/"fast_post_analysis_admission"/kind/namespace/"REQUEST.json","Exact request namespace")
    require(Path(pb["path"])==REPORT/MODES[kind][1]/namespace/"PLAN.json","Cross-family plan rejected")
    inputs=request["inputs"];explicit=[b for val in inputs.values() for b in (val if isinstance(val,list) else [val])]+[pb]
    adapter,_=make_adapter(kind,request["observer_index"],rb,explicit)
    if kind=="long_c":native=argparse.Namespace(plan=[pb["path"],pb["sha256"]])
    else:native=argparse.Namespace(plan=Path(pb["path"]),plan_sha256=pb["sha256"])
    return adapter.run(native)

def checks():
    passed=[]
    def ok(name,v):require(v,name);passed.append(name)
    def rejects(name,fn):
        try:fn()
        except (ValueError,KeyError,TypeError):passed.append(name);return
        raise AssertionError(name)
    v=load_module("s6c_execution_inventory_v7",V7_SHA)
    b=dict(path=str(REPORT/"UNREAD_FIXTURE_INDEX.json"),bytes=0,sha256="0"*64)
    rb=dict(path=str(REPORT/"UNREAD_FIXTURE_REQUEST.json"),bytes=0,sha256="1"*64)
    for kind in MODES:
        adapter,mod=make_adapter(kind,b,rb,[],v)
        ok(kind+" exact orchestration code",adapter.proof["identical_function_code_objects"])
        ok(kind+" scientific objects untouched",bool(adapter.proof["scientific_objects_unchanged"]))
        ok(kind+" reader factory is private",adapter.inventory.base is not v.base and adapter.inventory.base.MetadataReader is not v.base.MetadataReader)
        ok(kind+" base reader unchanged",v.base.MetadataReader is v.v6.base.MetadataReader)
    # Tiny substitute reader/index backend tests context plumbing only. Real V7
    # observer schema/binding/closure semantics remain its independently reviewed API.
    class Reader:
        def __init__(self,out):self.out=out
    calls=[]
    def admit(reader,index):calls.append((reader,index));reader.fast_observer_index=index;reader.fast_observer_receipts=[index]
    fake=types.SimpleNamespace(base=types.SimpleNamespace(MetadataReader=Reader),admit_observer_index=admit)
    factory=reader_factory(fake,b);a=factory("a");c=factory("c")
    ok("independent reader contexts",a is not c and len(calls)==2 and a.fast_observer_index==b)
    ok("no global reader mutation",fake.base.MetadataReader is Reader)
    bad=types.SimpleNamespace(base=fake.base,admit_observer_index=lambda reader,index:None)
    rejects("missing attached context",lambda:reader_factory(bad,b)("x"))
    rejects("ordinary namespace rejected",lambda:name_ok("old_analysis"))
    rejects("path escape namespace rejected",lambda:name_ok("../wrong_fast_v1"))
    yeskind=types.SimpleNamespace(kind_of=lambda p:p["kind"])
    for kind in MODES:
        strict_family(yeskind,kind,dict(kind=MODES[kind][2][0]))
        rejects(kind+" wrong family rejected",lambda k=kind:strict_family(yeskind,k,dict(kind="not_matching")))
    original=lambda p:dict(b)
    ok("exact explicit binding retained",bound_wrapper(original,[b])(None)==b)
    rejects("changed explicit input rejected",lambda:bound_wrapper(lambda p:dict(b,sha256="2"*64),[b])(None))
    ok("every legacy converter source pinned",all(bind(HERE/n)["sha256"]==h for n,h in PINS.items()))
    return dict(schema="s6c-fast-post-analysis-source-checks.v1",status="PASS_SOURCE_AND_CONTEXT_ONLY",check_count=len(passed),checks=passed,
        sources=sources(),original_scientific_sources=[bind(HERE/n) for n in PINS],
        actual_observer_index_read=False,actual_analysis_prepared=False,actual_analysis_run=False,new_model_calls=0)

def main():
    ap=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    sub=ap.add_subparsers(dest="action",required=True);sub.add_parser("checks")
    p=sub.add_parser("prepare");p.add_argument("--kind",choices=tuple(MODES),required=True);p.add_argument("--namespace",required=True)
    p.add_argument("--observer-index",nargs=2,required=True,metavar=("PATH","SHA256"))
    p.add_argument("--manifest",nargs=2,metavar=("PATH","SHA256"));p.add_argument("--index",nargs=2,metavar=("PATH","SHA256"))
    p.add_argument("--admission",nargs=2,action="append",metavar=("PATH","SHA256"));p.add_argument("--generation",choices=("baseline","research"))
    p=sub.add_parser("run");p.add_argument("--request",nargs=2,required=True,metavar=("PATH","SHA256"));p.add_argument("--plan",nargs=2,required=True,metavar=("PATH","SHA256"))
    args=ap.parse_args();value=checks() if args.action=="checks" else prepare(args) if args.action=="prepare" else run(args)
    print(json.dumps(value,indent=2,allow_nan=False))

if __name__=="__main__":main()
