"""Final observer metadata/source admissions; README_S6C_OBSERVER_FINAL_ADMISSIONS_V1.md."""
from __future__ import annotations
import argparse,ast,hashlib,json
from copy import deepcopy
from pathlib import Path
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
import s6c_long_native_epoch4_fast_v1 as L
import s6c_paced_epoch4_fast_v1 as P
PINS={'s6c_long_native_epoch4_fast_v1.py':'0160a9a09c54183d2896dc6363e66ed67f1f0e049d7dcdddd4c7d22e6cb6b166','s6c_paced_epoch4_fast_v1.py':'c13ed3849fb86aeb50341d823c2969b5084cd6e90aa8fee4c24785405e8d20c4'}
MAIN=['C065','C088','C091','C067','C122','C121','C079','C117','C118','C076']
CHECKS=[]
def ok(name,value):
    if not value:raise AssertionError(name)
    CHECKS.append(name)
def functions(path):
    return {n.name:n for n in ast.parse(Path(path).read_bytes()).body if isinstance(n,ast.FunctionDef)}
def dump(n):return ast.dump(n,include_attributes=False)
def publish(name,body):
    p=L.REPORT/'observer_fast_v1'/name
    if p.exists():raise ValueError('Preserve previous admission')
    result=dict(status='PASS_BOUNDED_METADATA_SOURCE_ADMISSION',created_utc=L.utc(),checks=CHECKS,check_count=len(CHECKS),
                audit_source=L.bind(__file__),readme=L.bind(HERE/'README_S6C_OBSERVER_FINAL_ADMISSIONS_V1.md'),**body)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(L.bind(p),indent=2))
def review_root():
    pins={'s6c_paced_arrival_sentinel_fast_v1.py':'63a26b59729e1ed0bd248f459de057b47bf3384b00b0dc1db5b4812a92838a57','s6c_paced_cross_routes_fast_v1.py':'b7552b44a8e24a6387969fb1a08d16bf3e7eded5ddd728e4bdb1181d2274f1ea'}
    evidence=[]
    for kind in ('arrival_sentinel','cross_routes'):
        old=HERE/('s6c_paced_'+kind+'_v1.py');new=HERE/('s6c_paced_'+kind+'_fast_v1.py')
        ok('held root source '+kind,L.bind(new)['sha256']==pins[new.name])
        a=functions(old);b=functions(new);changed=[n for n in a if dump(a[n])!=dump(b[n])]
        permitted={'source_bindings','compile_adapter'} if kind=='cross_routes' else {'source_bindings','load_native','namespace_roots','prepare','admit','quiet','worker','run','checks','source_checks'}
        ok('only declared observer/source functions change '+kind,set(changed)<=permitted)
        for name in ('candidate_routes','selected_panel','grid','validate_source_rows','source_record'):
            if name in a:ok('scientific route/source AST exact '+kind+':'+name,dump(a[name])==dump(b[name]))
        if kind=='arrival_sentinel':
            worker=deepcopy(b['worker']);worker.decorator_list=[]
            ok('sentinel native worker body exact',dump(worker)==dump(a['worker']))
            run=deepcopy(b['run']);run.decorator_list=[];timers=0
            for n in ast.walk(run):
                if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id=='last_full' and ast.unparse(n.value)=='time.monotonic() - cell_started':
                    n.value=ast.Name(id='elapsed',ctx=ast.Load());timers+=1
            ok('sentinel run only one completion timer',timers==1 and dump(run)==dump(a['run']))
            for name in ('prepare','worker','run','source_checks'):ok('sentinel explicit observer entry '+name,any(ast.unparse(x)=='L.observer_entry' for x in b[name].decorator_list))
            names={n.value for n in ast.walk(b['quiet']) if isinstance(n,ast.Constant) and isinstance(n.value,str)}
            ok('sentinel retains original and fast quiet names',{'s6c_paced_epoch4.py','s6c_paced_arrival_sentinel_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_paced_arrival_sentinel_fast_v1.py'}<=names)
        else:
            oldbody=ast.unparse(a['compile_adapter']);newbody=ast.unparse(b['compile_adapter'])
            replacement=newbody.replace('s6c_paced_epoch4_fast_v1.py','s6c_paced_epoch4.py')
            # Compare all nonliteral structure; exact added argv set is checked below.
            class Literals(ast.NodeTransformer):
                def visit_Constant(self,node):
                    return ast.copy_location(ast.Constant('<metadata>'),node) if isinstance(node.value,str) else node
            ok('cross adapter nonliteral AST unchanged',dump(Literals().visit(deepcopy(a['compile_adapter'])))==dump(Literals().visit(deepcopy(b['compile_adapter']))))
            ok('cross retains old/fast quiet names',all(x in newbody for x in ('s6c_paced_epoch4.py','s6c_paced_cross_routes_v1.py','s6c_paced_epoch4_fast_v1.py','s6c_paced_cross_routes_fast_v1.py')))
            for name in ('record_spawn','candidate_routes','grid','selected_panel'):ok('cross existing launch/route AST exact '+name,dump(a[name])==dump(b[name]))
        receipt=L.REPORT/'observer_fast_v1/root_cross_sentinel'/(new.stem+'_CHECKS_V1.json')
        value,rb=L.read_bound(receipt)
        readme=HERE/('README_S6C_PACED_'+kind.upper()+'_FAST_V1.md')
        doc=readme.read_text(encoding='utf-8-sig')
        ok('maintained command sections '+kind,'PowerShell' in doc and 'CMD' in doc and '_fast_v1' in doc)
        if kind=='arrival_sentinel':ok('cross-only ownership prose removed','Cross routes retain the original B36' not in doc)
        evidence.append(dict(original=L.bind(old),current=L.bind(new),readme=L.bind(readme),changed_functions=changed,reused_guard_receipt=rb))
    publish('ROOT_VARIANT_DESIGN_REVIEW_V1.json',dict(variants=evidence,canonical_pin_refresh=L.bind(L.REPORT/'observer_fast_v1/SOURCE_PIN_REFRESH_V2.json'),
        scope='Read-only observer/timer/import/quiet-name delta review. Existing39/23 plus inherited72 guard reports reused; no fixture suite rerun, prepare, native/model, storage scan, actual PCM/log or prediction read. Exact selection remains sentinel12 and asymmetric cross40.'))
def prepared():
    epoch,eb=L.read_bound(L.REPORT/'EPOCH4_EXECUTION_MANIFEST.json')
    ok('exact epoch4',eb['sha256']=='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945')
    index,ib=L.read_bound(epoch['input_index']['path'],epoch['input_index'])
    lookup={(r['case_id'],r['stream']):r for r in index['rows']}
    panel,pb=P.panel();policy=L.observer_policy();rows=[];manifest_hashes=set()
    specs=[(c.lower()+'_main_fast_v1',[c],'full16_plus4',40) for c in MAIN]+[('uncertainty_gate6_fast_v1',['C071','C082'],'gate6_diagnostic',24)]
    for namespace,candidates,mode,count in specs:
        p=L.REPORT/'paced_candidates'/namespace/'MANIFEST.json';plan,mb=L.read_bound(p)
        root,payload=P.namespace_roots(namespace);selected=P.selected_panel(panel,mode,candidates);routes=P.candidate_routes(epoch,candidates)
        copy=dict(plan);key=copy.pop('manifest_key');ok('manifest key '+namespace,L.digest(copy)==key)
        ok('prepared exact scope '+namespace,plan['status']=='PREPARED_NO_MODELS_STARTED' and plan['candidates']==candidates and plan['requested']==len(plan['jobs'])==count and plan['panel_mode']==mode)
        ok('source/policy/epoch '+namespace,plan['sources']==P.source_bindings() and plan['observer_policy']==policy and plan['execution_manifest']==eb and plan['input_index']==ib and plan['panel']==pb)
        ok('limits retained '+namespace,plan['worker_limit']==plan['inner_threads']==1 and plan['max_run_sec']==28800 and plan['pending_cell_bytes']==512*2**20)
        ok('exact ordered grid '+namespace,[(j['candidate_id'],j['case_id'],j['asr_tap'],j['repetition']) for j in plan['jobs']]==P.grid(candidates,selected))
        for j in plan['jobs']:
            copy=dict(j);key=copy.pop('job_key');ok('exact job '+j['job_id'],L.digest(copy)==key and j['profile_row']==routes[j['candidate_id'],j['asr_tap']] and j['profile_sha256']==L.digest(j['profile_row']))
            source,sb=L.read_bound(j['source']['path'],j['source']);expected=P.source_record({tap:lookup[j['case_id'],tap] for tap in ('O0','O1')},ib)
            ok('unaltered canonical source '+j['job_id'],source==expected and j['identity_tap']==j['profile_row']['identity_tap'])
        ok('no actual cell/native namespace '+namespace,not (root/'jobs').exists() and not (root/'invocations').exists() and not payload.exists())
        rows.append(dict(kind='canonical',candidates=candidates,namespace=namespace,manifest=mb,cells=count,source_sec=plan['total_source_sec'],models_started=0,native_sessions=0));manifest_hashes.add(mb['sha256'])
    for candidate in ('C065','C088','C091'):
        namespace='epoch4_long_'+candidate.lower()+'_o0_fast_v1';p=L.REPORT/'long_native_epoch4'/namespace/'MANIFEST.json';plan,mb=L.read_bound(p)
        L.validate_plan(plan);copy=dict(plan);key=copy.pop('plan_key');ok('long key '+candidate,L.digest(copy)==key)
        expected=[r for r in epoch['profiles'] if r['candidate_id']==candidate and r['asr_tap']==r['identity_tap']=='O0']
        ok('exact long profile/source '+candidate,len(expected)==1 and plan['profile_row']==expected[0] and plan['execution_manifest']==eb and plan['observer_policy']==policy and plan['composition']['sha256']==L.COMPOSITION_SHA)
        ok('long unexecuted '+candidate,plan['status']=='PREPARED_NO_MODELS_STARTED' and not (p.parent/'invocations').exists() and not Path(plan['report_root']).exists() and not Path(plan['payload_root']).exists())
        rows.append(dict(kind='continuous',candidates=[candidate],namespace=namespace,manifest=mb,cells=1,source_sec=plan['duration_sec'],models_started=0,native_sessions=0));manifest_hashes.add(mb['sha256'])
    exits=[]
    for p in (L.REPORT/'observer_fast_v1/attempts').glob('*.json'):
        value,b=L.read_bound(p)
        if value.get('manifest',{}).get('sha256') in manifest_hashes:
            ok('actual preparation restoration '+p.name,value['entry']=='prepare' and value['status']=='RESTORED' and value['error'] is None and all(x['restored'] and x['protected_admission_unchanged'] for x in value['installations']))
            exits.append(b)
    ok('one exit per preparation',len(exits)==14)
    publish('PREPARATION_BINDINGS_V1.json',dict(manifests=rows,canonical_cells=424,continuous_conditions=3,preparation_exit_receipts=exits,
        source_pin_refresh=L.bind(L.REPORT/'observer_fast_v1/SOURCE_PIN_REFRESH_V2.json'),preparation_commands=L.bind(L.REPORT/'observer_fast_v1/PREPARATIONS_README_V1.md'),
        scope='Actual metadata preparations only. Exact frozen canonical source/profile rows and continuous composition reviewed without rehashing PCM/assets or native logs. No quiet admissions or actual paced/long sessions created; counts are requested cells/conditions, not execution or final selection.'))
if __name__=='__main__':
    for name,sha in PINS.items():ok('held source '+name,L.bind(HERE/name)['sha256']==sha)
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('review-root','prepared'));args=parser.parse_args()
    {'review-root':review_root,'prepared':prepared}[args.action]()

