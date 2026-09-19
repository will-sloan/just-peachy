"""Fresh legacy census then explicit fast append; README_S6C_INVENTORY_REFRESH_V1.md."""
from __future__ import annotations
import argparse, ast, hashlib, importlib, json, os, re, types
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
PIN = 'fc23ff6650a34c927211d142e61b9dcf7afe7ee07e832c51573ae2da0dc3c7a3'
if hashlib.sha256((HERE/'s6c_execution_inventory_v7.py').read_bytes()).hexdigest() != PIN:
    raise ValueError('Held V7 source differs')
V = importlib.import_module('s6c_execution_inventory_v7')
if Path(V.__file__).resolve() != HERE/'s6c_execution_inventory_v7.py':
    raise ValueError('Wrong V7 import path')
B, V3, V4, V5, V6 = V.base, V.v3, V.v4, V.v5, V.v6
require = V.require
REPORT, PAYLOAD = V.REPORT, V.PAYLOAD
ROLLUP = REPORT/'DELEGATED_NATIVE_QUEUE_COMPLETION_V1.json'
ROLLUP_SHA = 'ddc6ed906207a1551c0b229c7fa4354e7e87109c3a2b8f9b489feba6e833f6e3'
POOLS = {'epoch6_endpoint_advice_scan_v1':(224,224,0), 'epoch5_cadence_floor_scan_v1':(448,448,0),
         'full_N03_scan_v1':(480,368,112), 'full_N08_N10_scan_v1':(960,736,224),
         'full_N12_scan_v1':(480,368,112), 'full_cross_routes_scan_v1':(480,368,112)}
SCHEMA = 's6c-fresh-execution-inventory-refresh.v1'
LEGACY_PINS = {'s6c_execution_inventory.py':'655476f9ca94df06ed9df30c38191bef63e02d9323b9474ad26a79171d51b8ac',
 's6c_execution_inventory_v3.py':'8820bc19d88b6706aed93cdf5c879688f66f5b96e9d910124f94d1bebfc39d58',
 's6c_execution_inventory_v4.py':'426a4eaada68e51d0e6af6decd8b9b56fa3c9660b3cca005f959862c03177876',
 's6c_execution_inventory_v5.py':'aee67604429f12013058ed94c74c3d3965c1e8e55299c87dfb6760394513aad8',
 's6c_execution_inventory_v6.py':'9109a38c9f62ad6aca11a4e60ef57eb9e8712bb43dde10b08d485d03a068921f'}

def sources():
    for module in (B,V3,V4,V5,V6):
        p=Path(module.__file__);require(p.resolve()==HERE/p.name and hashlib.sha256(p.read_bytes()).hexdigest()==LEGACY_PINS[p.name],'Held legacy source/path differs')
    own = [B.binding(p,p.read_bytes()) for p in (Path(__file__),HERE/'README_S6C_INVENTORY_REFRESH_V1.md')]
    values = own + V.source_bindings() + V6.source_bindings() + V3.source_bindings() + V4.source_bindings()
    values += [B.binding(HERE/'README_S6C_EXECUTION_INVENTORY_V5.md',(HERE/'README_S6C_EXECUTION_INVENTORY_V5.md').read_bytes())]
    bypath = {}
    for b in values:
        key = B.canonical(b['path'])
        require(key not in bypath or bypath[key] == b, 'Conflicting source authority')
        bypath[key] = b
    return list(bypath.values())

def quiet():
    require(not (REPORT/'PACED_QUIET_OWNER.json').exists(), 'Active/preserved quiet lease blocks census')

def read_pair(reader, pair):
    d,b = reader.read(pair[0]); require(b['sha256'] == pair[1], 'Explicit SHA differs'); return d,b

def owned_roots(plan, pb):
    """Called only after held V7 admission. Never use a historical global budget root."""
    kind = V.kind_of(plan); require(kind in V.FAST, 'Only admitted fast plans can exclude roots')
    family = V.FAST[kind]['family']
    name = Path(plan['output_root']).name if kind in ('controls','b36') else plan['namespace']
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name) is not None, 'Simple owned namespace')
    if kind in ('controls','b36'):
        roots = [PAYLOAD/family/name]
        require(Path(plan['output_root']) == roots[0] and Path(pb['path']) == roots[0]/'MANIFEST.json', 'Exact historical owned output root')
    elif kind == 'long_b36':
        roots = [REPORT/family/name, PAYLOAD/family/name]
        require(Path(plan['report_root']) == roots[0] and Path(plan['payload_root']) == roots[1] and Path(plan['output_root']) == roots[1], 'Exact B36 long namespace')
        require(Path(pb['path']) == roots[0]/'MANIFEST.json','B36 long manifest namespace')
    elif kind == 'long_c':
        roots = [REPORT/family/name, REPORT/'long_session'/name, PAYLOAD/'long_session'/name]
        require(Path(pb['path']) == roots[0]/'MANIFEST.json' and Path(plan['report_root']) == roots[1] and Path(plan['payload_root']) == roots[2], 'Exact C long namespaces')
    else:
        roots = [REPORT/family/name, PAYLOAD/family/name]
        require(Path(pb['path']) == roots[0]/'MANIFEST.json' and Path(plan['report_root']) == roots[0] and Path(plan['payload_root']) == roots[1], 'Exact paired owned roots')
    for p in roots:
        anchor = REPORT if p.is_relative_to(REPORT) else PAYLOAD
        require(p.relative_to(anchor).parts == (p.parent.name,name), 'Never exclude budget/family/input/composition roots')
        require(p.resolve() == p.absolute(), 'Owned namespace resolves outside declared path')
    return [dict(path=B.canonical(p),manifest=pb,kind=kind,reason='ADMITTED_FAST_OWNED_OUTPUT_NAMESPACE_ONLY') for p in roots]

class Discovery:
    """Filters only admitted owned subtrees; all unlisted paths pass unchanged."""
    def __init__(self, exclusions, guard=quiet):
        self.exclusions = exclusions; self.guard = guard; self.hidden = []
        self.roots = [Path(x['path']) for x in exclusions]
        require(len(self.roots) == len(set(self.roots)), 'Duplicate owned exclusion roots')
        require(not any(a != b and a in b.parents for a in self.roots for b in self.roots), 'Overlapping owned roots')
    def excluded(self, path):
        p = Path(path).absolute()
        return any(p == root or root in p.parents for root in self.roots)
    def paths(self, iterator):
        self.guard()
        for p in iterator:
            if self.excluded(p): self.hidden.append(dict(path=str(p),discovery='glob'))
            else: yield p
    def walk(self, root):
        self.guard()
        def fail(error): raise error
        for parent, dirs, files in os.walk(root, onerror=fail):
            self.guard()
            if self.excluded(parent):
                self.hidden.append(dict(path=str(parent),discovery='walk')); dirs[:] = []; continue
            for d in list(dirs):
                if self.excluded(Path(parent)/d):
                    self.hidden.append(dict(path=str(Path(parent)/d),discovery='walk')); dirs.remove(d)
            yield parent,dirs,files

def adapted(module, name, discovery, pattern=None, walk=False, literals=None, overrides=None):
    """One exact discovery call changes. Other function AST nodes are retained."""
    source = Path(module.__file__); tree = ast.parse(source.read_bytes())
    node = deepcopy(next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == name))
    class Rewrite(ast.NodeTransformer):
        changed = 0
        def visit_Constant(self, n):
            if isinstance(n.value,str) and literals and n.value in literals: n.value = literals[n.value]
            return n
        def visit_Call(self, n):
            n = self.generic_visit(n)
            if walk and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id == 'os' and n.func.attr == 'walk':
                require(len(n.args)==1 and not n.keywords,'Original walk signature'); self.changed += 1
                return ast.copy_location(ast.Call(func=ast.Name(id='_discovery_walk',ctx=ast.Load()),args=n.args,keywords=[]),n)
            if pattern and isinstance(n.func,ast.Attribute) and n.func.attr == 'glob' and len(n.args)==1 and isinstance(n.args[0],ast.Constant) and n.args[0].value == pattern:
                self.changed += 1
                return ast.copy_location(ast.Call(func=ast.Name(id='_discovery_paths',ctx=ast.Load()),args=[n],keywords=[]),n)
            return n
    rewrite = Rewrite(); node = rewrite.visit(node)
    require(rewrite.changed == 1, 'Exactly one pinned discovery site required: '+name)
    ns = dict(vars(module)); ns.update(overrides or {})
    ns.update(_discovery_paths=discovery.paths,_discovery_walk=discovery.walk)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),str(source),'exec'),ns)
    return ns[name]

def legacy_context(discovery, admissions):
    # Seven private discovery sites. No process-wide Path/os/module patch.
    base_globals = dict(vars(B))
    for n,f in vars(B).items():
        if isinstance(f,types.FunctionType) and f.__globals__ is vars(B):
            clone=types.FunctionType(f.__code__,base_globals,f.__name__,f.__defaults__,f.__closure__)
            clone.__kwdefaults__=f.__kwdefaults__;base_globals[n]=clone
    base_globals['process_state']=V3.process_state
    original_aux = adapted(B,'collect_auxiliary',discovery,'*/native/*/*/*/STARTED.json',overrides=base_globals)
    outer = adapted(V3,'auxiliary_adapter',discovery,'*/invocations/*/ADMISSION.json')
    canonical = adapted(V4,'paced_adapter',discovery,'*/MANIFEST.json')
    sentinel = adapted(V4,'paced_adapter',discovery,'*/MANIFEST.json',literals=V5.SENTINEL_REPLACEMENTS,overrides=V5.S.paced_adapter.__globals__)
    fifth = adapted(V5,'additive',discovery,'*/MANIFEST.json',overrides=dict(v4=types.SimpleNamespace(**(vars(V4)|dict(paced_adapter=canonical))),S=types.SimpleNamespace(**(vars(V5.S)|dict(paced_adapter=sentinel)))))
    sixth = adapted(V6,'additive',discovery,'*/MANIFEST.json',overrides=dict(v5=types.SimpleNamespace(**(vars(V5)|dict(additive=fifth)))))
    def auxiliary(*args): return sixth(lambda *a:outer(original_aux,*a),admissions,*args)
    def validated(row,specs):
        require(V3.finite_owner(row.get('pid'),row.get('creation_time')),'Invalid native physical owner identity')
        return B.validate_native(row,specs)
    collector = adapted(B,'collect',discovery,walk=True,overrides=base_globals|dict(collect_auxiliary=auxiliary,validate_native=validated))
    return collector

def rollup_admission(reader):
    d,b = read_pair(reader,[str(ROLLUP),ROLLUP_SHA])
    require(d['schema']=='s6c.delegated-native-queue-completion.v1' and d['status']=='COMPLETE_NATIVE_AND_FROZEN_PARITY_OWNERSHIP_RETURNED', 'Exact closed six-pool rollup')
    require(len(d['rows'])==6 and {r['name'] for r in d['rows']}==set(POOLS), 'All six late pools required')
    for r in d['rows']:
        require(tuple(r[k] for k in ('requested','new_native_jobs','verified_reused_jobs')) == POOLS[r['name']], 'Late pool source/reuse counts differ')
    require(d['counts']==dict(requested=3072,new_native_jobs=2512,verified_reused_jobs=560), 'Six-pool totals differ')
    return d,b

def pool_coverage(reader, rollup, inventory, physical):
    """Index references must map to freshly enumerated receipts, not added sessions."""
    known = {(B.canonical(b['path']),b['sha256']) for r in physical for b in r['receipt_bindings']}
    indexes = {(B.canonical(x['binding']['path']),x['binding']['sha256']):x for x in inventory['prediction_indexes']}
    rows=[]; issues=[]
    for r in rollup['rows']:
        review,rb=V.bound(reader,r['review']); result,jb=V.bound(reader,r['results']); index,ib=V.bound(reader,r['prediction_index'])
        require(review['status']=='PASS_COMPLETE_NATIVE_GRID_AND_OWNERS_CLOSED' and review['orchestration']==r['name'], 'Exact late closure review')
        require(result['status']=='COMPLETE' and result['completed']==result['requested']==r['requested'] and result['worker_pool_joined'] is True and result['error'] is None, 'Exact late completed native grid')
        require(index['status']=='COMPLETE' and len(index['rows'])==r['requested'], 'Complete late prediction index')
        require(len(result['rows'])==r['requested'], 'All completed/reused result references required')
        refs={(B.canonical(x['receipt']['path']),x['receipt']['sha256']) for x in result['rows']}
        missing=sorted(refs-known)
        if missing: issues.append(dict(pool=r['name'],error='LATE_POOL_RECEIPTS_NOT_ENUMERATED',missing=missing))
        if (B.canonical(ib['path']),ib['sha256']) not in indexes: issues.append(dict(pool=r['name'],error='LATE_POOL_INDEX_NOT_ENUMERATED',binding=ib))
        rows.append(dict(name=r['name'],review=rb,results=jb,prediction_index=ib,parity_declared_not_reopened=r['parity'],requested=r['requested'],new_native_jobs=r['new_native_jobs'],verified_reused_jobs=r['verified_reused_jobs'],unique_receipt_references=len(refs),missing_receipt_references=missing,adds_physical_attempts=0))
    return rows,issues

def collect(args):
    quiet(); before=sources()
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,55}',args.version or ''),'Fresh short simple namespace')
    out=REPORT/'execution_inventory'/args.version; require(not out.exists(),'Preserve prior refresh'); out.mkdir(parents=True)
    reader=B.MetadataReader(out)
    try:
        spec,sb=read_pair(reader,args.spec); authority,ab=read_pair(reader,args.authority)
        require(spec['schema']=='s6c-inventory-refresh-spec.v1' and spec['status']=='REGISTERED_FINITE_REFRESH','Explicit finite refresh spec')
        require(authority['schema']=='s6c-inventory-refresh-authority.v1' and authority['status']=='AUTHORIZED_POST_CLOSURE_METADATA_CENSUS','Root post-closure authority required')
        require(authority['spec']==sb and authority['all_model_paced_long_work_closed'] is True and authority['no_concurrent_research_writers'] is True,'Authority/source/closure scope differs')
        require(authority['helper']==B.binding(__file__,Path(__file__).read_bytes()),'Authority must bind this helper')
        require(spec['late_pool_rollup']==dict(path=B.canonical(ROLLUP),bytes=13120,sha256=ROLLUP_SHA),'Exact six-pool authority required')
        rollup,rollup_binding=rollup_admission(reader)
        V.admit_observer_index(reader,spec['observer_index'])
        fast=spec['fast_manifests']; legacy=spec['legacy_manifests']
        require(fast and len({B.canonical(b['path']) for b in fast+legacy})==len(fast+legacy),'Explicit unique manifests')
        exclusions=[]
        for b in fast:
            quiet(); plan,pb,_=V.admit_plan(reader,b); require(V.kind_of(plan) is not None,'Fast list contains legacy plan')
            exclusions+=owned_roots(plan,pb)
        for b in legacy:
            plan,pb=V.bound(reader,b);require(V.kind_of(plan) is None,'Legacy list contains fast plan');V6.admit_plan(reader,pb)
        admission=B.write_new(out/'ADMISSION.json',dict(schema=SCHEMA,status='METADATA_ADMITTED_NOT_ENUMERATED',spec=sb,authority=ab,late_pool_rollup=rollup_binding,exclusions=exclusions,sources=before))
        discovery=Discovery(exclusions); collector=legacy_context(discovery,legacy)
        quiet(); result=collector(types.SimpleNamespace(version=args.version+'_legacy'))
        inv,ib=V.bound(reader,result['snapshot']); physical,_=V.bound(reader,inv['outputs']['physical_json'])
        coverage,gaps=pool_coverage(reader,rollup,inv,physical)
        refresh=B.write_new(out/'LEGACY_REFRESH_RECEIPT.json',dict(schema=SCHEMA,status='FRESH_ENUMERATION_WITH_FLAGS' if gaps or inv['audit_status']!='PASS_WITH_SCOPE_LIMITS' else 'FRESH_ENUMERATION_SCOPED_PASS',admission=admission,inventory=ib,late_pool_coverage=coverage,issues=gaps,explicit_exclusions=exclusions,excluded_discovery_paths=discovery.hidden,scope='Original epoch/attempt/index discovery remains fresh; only declared fast output namespaces deferred. No claim of final acceptance.'))
        # This same invocation passes only its own fresh inventory into held V7.
        quiet(); appended=V.collect(types.SimpleNamespace(version=args.version+'_fast',prior_inventory=[ib['path'],ib['sha256']],observer_index=[spec['observer_index']['path'],spec['observer_index']['sha256']],manifest=[[b['path'],b['sha256']] for b in fast]))
        final,_=V.bound(reader,appended); require(sources()==before,'Held source changed during refresh'); quiet()
        metadata=B.write_new(out/'METADATA_SOURCES.json',reader.sources)
        return B.write_new(out/'REFRESH_RECEIPT.json',dict(schema=SCHEMA,status='REFRESH_COMPLETE_WITH_FLAGS' if gaps or final['audit_status']!='PASS_WITH_SCOPE_LIMITS' else 'REFRESH_COMPLETE_WITH_SCOPE_LIMITS',admission=admission,legacy_refresh=refresh,fresh_legacy_inventory=ib,appended_inventory=appended,late_pool_coverage_issues=gaps,sources=before,metadata_sources=metadata,models=0,scope='Fresh legacy enumeration plus explicit V7 fast attempts, including failures and unknowns. All prior snapshot_v2 bytes remain historical only. No final S6C acceptance or payload validation is implied.'))
    except Exception as exc:
        B.write_new(out/'FAILURE.json',dict(schema=SCHEMA,status='FAILED_REFRESH_NO_FINAL_CENSUS',error=repr(exc),sources=before,metadata_sources=reader.sources,models=0)); raise

def main():
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False)
    p.add_argument('action',choices=['collect']);p.add_argument('--version',required=True)
    p.add_argument('--spec',nargs=2,required=True);p.add_argument('--authority',nargs=2,required=True)
    print(json.dumps(collect(p.parse_args()),indent=2))

if __name__=='__main__': main()
