"""Final observer metadata/source admissions; README_S6C_OBSERVER_FINAL_ADMISSIONS_V2.md."""
from __future__ import annotations
import argparse,ast,hashlib,json
from copy import deepcopy
from pathlib import Path
import sys
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
import s6c_long_native_epoch4_fast_v2 as L
import s6c_paced_epoch4_fast_v2 as P
PINS={'s6c_long_native_epoch4_fast_v2.py':'079642ba24d59f625a6ae0c4342d9a26f51e56221f29b5a50f54830adfa22d67','s6c_paced_epoch4_fast_v2.py':'a8776724003fa2a642575892327b7c3e88eaddf29606881b302b05157c12b270'}
MAIN=['C065','C088','C091','C067','C122','C121','C079','C117','C118','C076']
CHECKS=[]
def ok(name,value):
    if not value:raise AssertionError(name)
    CHECKS.append(name)
def functions(path):
    return {n.name:n for n in ast.parse(Path(path).read_bytes()).body if isinstance(n,ast.FunctionDef)}
def dump(n):return ast.dump(n,include_attributes=False)
def publish(name,body):
    p=L.REPORT/'observer_fast_v2'/name
    if p.exists():raise ValueError('Preserve previous admission')
    result=dict(status='PASS_BOUNDED_METADATA_SOURCE_ADMISSION',created_utc=L.utc(),checks=CHECKS,check_count=len(CHECKS),
                audit_source=L.bind(__file__),readme=L.bind(HERE/'README_S6C_OBSERVER_FINAL_ADMISSIONS_V2.md'),**body)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2,allow_nan=False);f.write('\n')
    print(json.dumps(L.bind(p),indent=2))
def prepared():
    acceptance=L.bind(L.REPORT/'independent_review/guard_v2_component_v1/REVIEW_RECEIPT.json')
    ok('independent source acceptance',acceptance['sha256']=='5094195880893daea81d9d2aab6890bba58b6951028c863ed9e97b0216ab3f1e')
    epoch,eb=L.read_bound(L.REPORT/'EPOCH4_EXECUTION_MANIFEST.json')
    ok('exact epoch4',eb['sha256']=='720a6cc6c1f9a11ea5d39c3c7f2ab52452aad507ea3d0e0a56fa2c3074af9945')
    index,ib=L.read_bound(epoch['input_index']['path'],epoch['input_index'])
    lookup={(r['case_id'],r['stream']):r for r in index['rows']}
    panel,pb=P.panel();policy=L.observer_policy();guard=L.protected_guard_policy();rows=[];manifest_hashes=set()
    specs=[(c.lower()+'_main_fast_v2',[c],'full16_plus4',40) for c in MAIN]+[('uncertainty_gate6_fast_v2',['C071','C082'],'gate6_diagnostic',24)]
    for namespace,candidates,mode,count in specs:
        p=L.REPORT/'paced_candidates'/namespace/'MANIFEST.json';plan,mb=L.read_bound(p)
        root,payload=P.namespace_roots(namespace);selected=P.selected_panel(panel,mode,candidates);routes=P.candidate_routes(epoch,candidates)
        copy=dict(plan);key=copy.pop('manifest_key');ok('manifest key '+namespace,L.digest(copy)==key)
        ok('prepared exact scope '+namespace,plan['status']=='PREPARED_NO_MODELS_STARTED' and plan['candidates']==candidates and plan['requested']==len(plan['jobs'])==count and plan['panel_mode']==mode)
        ok('source/policy/epoch '+namespace,plan['sources']==P.source_bindings() and plan['observer_policy']==policy and plan['protected_guard_policy']==guard and plan['original_native_function']==guard['original_structural_code_sha256']['native'] and plan['execution_manifest']==eb and plan['input_index']==ib and plan['panel']==pb)
        ok('limits retained '+namespace,plan['worker_limit']==plan['inner_threads']==1 and plan['max_run_sec']==28800 and plan['pending_cell_bytes']==512*2**20)
        ok('exact ordered grid '+namespace,[(j['candidate_id'],j['case_id'],j['asr_tap'],j['repetition']) for j in plan['jobs']]==P.grid(candidates,selected))
        oldpath=p.parent.with_name(namespace.replace('_fast_v2','_fast_v1'))/'MANIFEST.json'
        oldplan,oldbinding=L.read_bound(oldpath)
        ok('V1 requested scope unchanged '+namespace,all(plan[k]==oldplan[k] for k in ('requested','candidates','panel_mode','source_case_ids','repeat_case_ids','total_source_sec','deadline_utc','worker_limit','inner_threads','pending_cell_bytes','max_run_sec','execution_manifest','input_index','panel')))
        oldjobs={j['job_id']:j for j in oldplan['jobs']}
        for j in plan['jobs']:
            oldjob=oldjobs[j['job_id']]
            fields=('candidate_id','case_id','asr_tap','identity_tap','repetition','profile_row','profile_sha256','gallery','gallery_row','timeout_sec')
            ok('V1 scientific job exact '+j['job_id'],all(j[k]==oldjob[k] for k in fields))
            copy=dict(j);key=copy.pop('job_key');ok('exact job '+j['job_id'],L.digest(copy)==key and j['profile_row']==routes[j['candidate_id'],j['asr_tap']] and j['profile_sha256']==L.digest(j['profile_row']))
            source,sb=L.read_bound(j['source']['path'],j['source']);expected=P.source_record({tap:lookup[j['case_id'],tap] for tap in ('O0','O1')},ib)
            ok('unaltered canonical source '+j['job_id'],source==expected and j['identity_tap']==j['profile_row']['identity_tap'])
        ok('no actual cell/native namespace '+namespace,not (root/'jobs').exists() and not (root/'invocations').exists() and not payload.exists())
        rows.append(dict(previous_manifest=oldbinding,kind='canonical',candidates=candidates,namespace=namespace,manifest=mb,cells=count,source_sec=plan['total_source_sec'],models_started=0,native_sessions=0));manifest_hashes.add(mb['sha256'])
    for candidate in ('C065','C088','C091'):
        namespace='epoch4_long_'+candidate.lower()+'_o0_fast_v2';p=L.REPORT/'long_native_epoch4'/namespace/'MANIFEST.json';plan,mb=L.read_bound(p)
        oldplan,oldbinding=L.read_bound(p.parent.with_name(namespace.replace('_fast_v2','_fast_v1'))/'MANIFEST.json')
        exact=('profile_row','profile_sha256','gallery','gallery_row','gallery_index','composition','execution_manifest','audio','pcm_sha256','telemetry','duration_sec','duration_samples','pending_output_reserve_bytes','max_wall_sec','worker_limit','deadline_utc','allowed_overrides')
        ok('V1 continuous scientific/limit fields exact '+candidate,all(plan[k]==oldplan[k] for k in exact))
        ok('continuous exact structural guard '+candidate,plan['protected_guard_policy']==guard and plan['native_function_code_sha256']==guard['original_structural_code_sha256']['native'])
        L.validate_plan(plan);copy=dict(plan);key=copy.pop('plan_key');ok('long key '+candidate,L.digest(copy)==key)
        expected=[r for r in epoch['profiles'] if r['candidate_id']==candidate and r['asr_tap']==r['identity_tap']=='O0']
        ok('exact long profile/source '+candidate,len(expected)==1 and plan['profile_row']==expected[0] and plan['execution_manifest']==eb and plan['observer_policy']==policy and plan['composition']['sha256']==L.COMPOSITION_SHA)
        ok('long unexecuted '+candidate,plan['status']=='PREPARED_NO_MODELS_STARTED' and not (p.parent/'invocations').exists() and not Path(plan['report_root']).exists() and not Path(plan['payload_root']).exists())
        rows.append(dict(previous_manifest=oldbinding,kind='continuous',candidates=[candidate],namespace=namespace,manifest=mb,cells=1,source_sec=plan['duration_sec'],models_started=0,native_sessions=0));manifest_hashes.add(mb['sha256'])
    exits=[]
    for p in (L.REPORT/'observer_fast_v2/attempts').glob('*.json'):
        value,b=L.read_bound(p)
        if value.get('manifest',{}).get('sha256') in manifest_hashes:
            ok('actual preparation restoration '+p.name,value['entry']=='prepare' and value['status']=='RESTORED' and value['error'] is None and all(x['restored'] and x['protected_admission_unchanged'] for x in value['installations']))
            exits.append(b)
    ok('one exit per preparation',len(exits)==14)
    publish('PREPARATION_BINDINGS_V1.json',dict(independent_source_acceptance=acceptance,manifests=rows,canonical_cells=424,continuous_conditions=3,preparation_exit_receipts=exits,
        guard_source_checks=L.bind(L.REPORT/'observer_fast_v2/GUARD_CHECKS_V2.json'),preparation_commands=L.bind(L.REPORT/'observer_fast_v2/PREPARATIONS_README_V1.md'),
        scope='Actual metadata preparations only. Exact frozen canonical source/profile rows and continuous composition reviewed without rehashing PCM/assets or native logs. No quiet admissions or actual paced/long sessions created; counts are requested cells/conditions, not execution or final selection.'))

if __name__=='__main__':
    for name,sha in PINS.items():ok('held source '+name,L.bind(HERE/name)['sha256']==sha)
    prepared()
