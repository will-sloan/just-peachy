"""Narrow historical observer source/timer review; README_S6C_HISTORICAL_FAST_REVIEW_V1.md."""
from __future__ import annotations
import ast, hashlib, importlib.util, json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
EXPECTED='579963cb5e873a0a08504bb4f022ea8a92a158886d36abfd87ee4a0f9cd6d299'
def binding(path):
    p=Path(path).resolve();raw=p.read_bytes()
    return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def main():
    hp=HERE/'s6c_historical_fast_observer_v1.py'
    assert binding(hp)['sha256']==EXPECTED
    spec=importlib.util.spec_from_file_location('s6c_historical_fast_observer_v1',hp)
    H=importlib.util.module_from_spec(spec);sys.modules[spec.name]=H;spec.loader.exec_module(H)
    target=H.REPORT/'independent_review/HISTORICAL_FAST_OBSERVER_DESIGN_REVIEW_V1.json'
    if target.exists():raise ValueError('Preserve prior independent review')
    checks=[];sources={};reused=[];resolved=[]
    owner_delta,owner_binding=H.read_bound(H.REPORT/'historical_fast_observers/OWNER_RECEIPT_REPAIR_V1.json')
    assert owner_binding['sha256']=='e46b6a0bee2974d5545559457bf6f1a8eccb396657d5ab1357aba0420d45739e'
    preservation,_=H.read_bound(owner_delta['previous']['path'],owner_delta['previous'])
    def ok(name,value):
        if not value:raise AssertionError(name)
        checks.append(name)
    def verify(b):
        actual=binding(b['path'])
        if actual!=b:
            matches=[r for r in preservation['sources'] if r['original']==b]
            ok('exact preserved prior source resolver '+Path(b['path']).name,len(matches)==1)
            actual=binding(matches[0]['preserved']['path']);ok('preserved bytes match prior binding',actual==matches[0]['preserved'] and all(actual[k]==b[k] for k in ('bytes','sha256')))
            resolved.append(dict(original=b,preserved=actual))
        else:ok('exact source '+str(Path(b['path']).name),True)
        sources[actual['path']]=actual
    readiness,rb=H.read_bound(H.REPORT/'historical_fast_observers/READINESS_V2.json')
    ok('three declared historical variants',[r['variant'] for r in readiness['variants']]==['controls','b36','long_b36'])
    for b in (readiness['benchmark'],readiness['hardlink_diagnosis'],readiness['benchmark_scanner_continuity']):verify(b);reused.append(b)
    continuity,_=H.read_bound(readiness['benchmark_scanner_continuity']['path'],readiness['benchmark_scanner_continuity'])
    original=ast.parse(Path(continuity['original_source']['path']).read_bytes());current=ast.parse(hp.read_bytes())
    verify(continuity['original_source']);verify(continuity['current_source'])
    for name in continuity['exact_ast_names']:
        left=next(n for n in original.body if getattr(n,'name',None)==name);right=next(n for n in current.body if getattr(n,'name',None)==name)
        ok('benchmarked scanner AST exact '+name,ast.dump(left,include_attributes=False)==ast.dump(right,include_attributes=False))
    for b in (owner_delta['source'],owner_delta['readme'],owner_delta['previous'],*owner_delta['source_checks']):verify(b)
    reused.append(owner_binding)
    before_owner=ast.parse(next(r['preserved']['path'] for r in preservation['sources'] if r['original']['path']==str(hp.resolve())) and Path(next(r['preserved']['path'] for r in preservation['sources'] if r['original']['path']==str(hp.resolve()))).read_bytes())
    for name in owner_delta['unchanged_ast_names']:
        left=next(n for n in before_owner.body if getattr(n,'name',None)==name);right=next(n for n in current.body if getattr(n,'name',None)==name)
        ok('owner metadata leaves scanner/adaptation AST exact '+name,ast.dump(left,include_attributes=False)==ast.dump(right,include_attributes=False))
    variants=[]
    for row in readiness['variants']:
        kind=row['variant'];verify(row['receipt']);prior,_=H.read_bound(row['receipt']['path'],row['receipt']);reused.append(row['receipt'])
        ok('owner fixture count reused '+kind,prior['status']=='PASS_MODEL_FREE_SOURCE_CHECKS' and prior['check_count']==row['check_count'])
        for b in row['source_bindings']:
            if b['path'] not in sources:verify(b)
        api=H.adapt(kind);parent=api._original
        tree=ast.parse((HERE/H.VARIANTS[kind]['parent']).read_bytes())
        original_run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        run=deepcopy(original_run);timers=[n for n in ast.walk(run) if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='lastbeat' and isinstance(n.value,ast.Name) and n.value.id=='elapsed']
        ok('one periodic timer '+kind,len(timers)==1)
        timers[0].value=ast.parse('time.monotonic()-t0',mode='eval').body
        env=dict(vars(parent));exec(compile(ast.fix_missing_locations(ast.Module(body=[run],type_ignores=[])),'independent_timer_only','exec'),env)
        ok('run bytecode differs only completion timestamp '+kind,api.run.__code__.co_code==env['run'].__code__.co_code and api.run.__code__.co_consts==env['run'].__code__.co_consts)
        clock=dict(time=SimpleNamespace(monotonic=lambda:60.),t0=0.,elapsed=20.)
        exec(compile(ast.fix_missing_locations(ast.Module(body=[timers[0]],type_ignores=[])),'independent_clock','exec'),clock)
        ok('next periodic start waits 20s after scan '+kind,clock['lastbeat']==60. and 79.999-clock['lastbeat']<20<=80.-clock['lastbeat'])
        if kind=='long_b36':
            worker=deepcopy(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='worker'))
            original_env=dict(vars(parent));exec(compile(ast.fix_missing_locations(ast.Module(body=[worker],type_ignores=[])),'independent_untouched_worker','exec'),original_env)
            ok('untouched continuous worker compiled in same isolated context',api.worker.__code__.co_code==original_env['worker'].__code__.co_code and api.worker.__code__.co_consts==original_env['worker'].__code__.co_consts)
            ok('continuous scanner proxy is isolated',api.C is not parent.C and api.C.strict_bytes is not parent.C.strict_bytes)
            ok('continuous resource limits unchanged',api.LIMITS==parent.LIMITS)
        else:
            ok('paced scanner globals isolated '+kind,api.resources.__globals__ is not parent.resources.__globals__ and api.strict_bytes is not parent.strict_bytes)
            ok('paced only outer RAM raised '+kind,api.RESOURCE_LIMITS==dict(parent.RESOURCE_LIMITS,host_available_min_bytes=12*2**30))
        ok('actual prepared grid only reused '+kind,row['original_prepared_scope']['projected_jobs']=={'controls':80,'b36':40,'long_b36':1}[kind])
        variants.append(dict(kind=kind,metadata_ast_changed_functions=api._metadata_ast_changed_functions,existing_fixture_receipt=row['receipt'],native_execution=0))
    result=dict(status='PASS_BOUNDED_SOURCE_AND_TIMER_REVIEW',created_utc=H.utc(),readiness=rb,checks=checks,check_count=len(checks),
        sources=list(sources.values()),reused_evidence=reused,variants=variants,owner_metadata_addition=owner_binding,preserved_prior_source_resolvers=resolved,
        findings=['Fresh os.stat sizes resolve the documented hardlink-growth counterexample; original f725 bytes remain preserved.',
                  'Common and historical dangling/nonregular policies remain explicitly distinct; access and unsupported reparse traversal fail closed.',
                  'All three coordinator run bodies differ only by the authorized completion timestamp. Original historical worker, models and physical source semantics remain inherited.',
                  'Only historical paced outer RAM changes from 4 to 12 GiB; native/internal limits and all timeouts are preserved.',
                  'Scanner reports measure observed calls/time/errors, not native/quiet/process closure. No present arbitrary-reparse equivalence claim.'],
        scope='Source/AST/three tiny timer evaluations only. Reuses existing 47/47/48 owner fixtures, benchmark and previous native guard authority. No fixture suite repeated, tree scan, PCM/model/log read, real preparation, policy or native run.',
        preserved_review_attempt=binding(H.SIM/'staging/s6c'/H.RUN/'historical_fast_review_v1/before_compiler_context_guard/SOURCE_INDEX.json'),
        review_sources=[binding(__file__),binding(HERE/'README_S6C_HISTORICAL_FAST_REVIEW_V1.md')])
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(dict(status=result['status'],checks=len(checks),receipt=binding(target)),indent=2))
if __name__=='__main__':main()
