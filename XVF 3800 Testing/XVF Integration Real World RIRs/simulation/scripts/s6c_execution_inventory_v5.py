"""Additive sentinel/B36 continuous metadata; README_S6C_EXECUTION_INVENTORY_V5.md."""
from __future__ import annotations
import argparse, ast, hashlib, importlib, json, math, re, types
from collections import Counter
from copy import deepcopy
from datetime import datetime
from pathlib import Path

HERE=Path(__file__).resolve().parent
PINS={'s6c_execution_inventory_v4.py':'426a4eaada68e51d0e6af6decd8b9b56fa3c9660b3cca005f959862c03177876',
      's6c_paced_arrival_sentinel_v1.py':'e7114b8bf898c3eb5f6ed7baae6c7c1df7065a256396e99eaeaac4bbf24f42aa',
      's6c_long_b36_v1.py':'09b809f6301e696054c4563fdad0d48072ae22716bafcf9002a33bdffd866c66'}
for name,sha in PINS.items():
    if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=sha:raise ValueError('Held additive dependency changed: '+name)
v4=importlib.import_module('s6c_execution_inventory_v4');v3=v4.v3;base=v4.base
if Path(v4.__file__).resolve()!=HERE/'s6c_execution_inventory_v4.py':raise ValueError('Wrong V4 import')
REPORT=v4.REPORT;PAYLOAD=v4.PAYLOAD
SCHEMA='s6c-execution-inventory-additive.v5'
SENTINEL='s6c-paced-arrival-sentinel.v1'
LONG='s6c-exact-historical-b36-continuous.v1'
LONG_RESULT='s6c-exact-historical-b36-continuous-result.v1'
require=v4.require;bound=v4.bound;owner=v4.owner

def source_bindings():
    return [base.binding(p,p.read_bytes()) for p in (Path(__file__),HERE/'README_S6C_EXECUTION_INVENTORY_V5.md',*(HERE/n for n in PINS))]

def compile_functions(path,names,namespace,replacements=None):
    tree=ast.parse(Path(path).read_bytes());nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    require(len(nodes)==len(names),'Exact admitted metadata function inventory differs')
    class LiteralAdapter(ast.NodeTransformer):
        def visit_Constant(self,node):
            if isinstance(node.value,str) and node.value in (replacements or {}):return ast.copy_location(ast.Constant(replacements[node.value]),node)
            return node
    body=ast.fix_missing_locations(LiteralAdapter().visit(ast.Module(body=nodes,type_ignores=[])))
    exec(compile(body,str(path),'exec'),namespace)
    return namespace

SENTINEL_REPLACEMENTS={'s6c_paced_epoch4.py':'s6c_paced_arrival_sentinel_v1.py',
    's6c-canonical-paced-cell-result.v1':'s6c-paced-arrival-sentinel-cell-result.v1',
    'paced_candidates':'paced_arrival_sentinel','paced_v4':'sentinel_v5',
    'f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da':'13490a4773b5be366b6a7d7e47013f8cd3ab9a8d34a3f9d99f33c539a24f2d4b'}

def sentinel_api():
    """Isolated globals/literal metadata adaptation; never patches held V4."""
    guard_names={'validate_source_rows','source_record','candidate_routes','grid','selected_panel','native_folder','valid_owner','validate_native_identity'}
    guards=compile_functions(HERE/'s6c_paced_arrival_sentinel_v1.py',guard_names,dict(Path=Path,math=math,deepcopy=deepcopy))
    names={'admit_plan','expected_worker_argv','validate_launch','native_result_metadata','metadata_chain','admit_complete_cell','admit_paced_index','row_base','collect_job','invocation_rows','paced_adapter'}
    ns={**vars(v4),'CANONICAL':SENTINEL,'SCHEMA':SCHEMA,'PINS':{**v4.PINS,**PINS},'GUARDS':guards,'source_bindings':source_bindings}
    compile_functions(HERE/'s6c_execution_inventory_v4.py',names,ns,SENTINEL_REPLACEMENTS)
    original=ns['admit_plan']
    def admit(reader,b):
        plan,pb,spec=original(reader,b)
        require(plan['schema']==SENTINEL and plan['candidates']==['C088','C105'] and len(plan['jobs'])==12,'Exact exploratory sentinel required')
        require(plan['panel_mode']=='arrival_sentinel' and plan['worker_limit']==1 and plan['inner_threads']==1,'Sentinel route/budget differs')
        total=0.
        for job in plan['jobs']:
            source,_=bound(reader,job['source']);total+=source['duration_sec']
            require(job['timeout_sec']==max(720.,source['duration_sec']*1.75+job['profile_row']['profile']['runtime']['lane_drain_timeout_sec']+120.),'Sentinel timeout differs')
        require(total==plan['total_source_sec'],'Sentinel source denominator differs')
        return plan,pb,spec
    ns['admit_plan']=admit
    return types.SimpleNamespace(**{n:ns[n] for n in names},GUARDS=guards,base=base,HERE=HERE,CANONICAL=SENTINEL)

S=sentinel_api()

def dt(value):
    result=datetime.fromisoformat(value.replace('Z','+00:00'));require(result.tzinfo is not None,'Timezone required');return result

def long_guards(reader):
    path=HERE/'s6c_long_b36_v1.py';tree=ast.parse(path.read_bytes());constants={}
    names={'SCHEMA','RESULT_SCHEMA','KIND','COMPOSITION_SHA','EPOCH_SHA','SEALED_SHA','DURATION','FRAMES','TIMEOUT','CLEANUP_MAX_SEC','LIMIT_NOTES'}
    for node in tree.body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name) and node.targets[0].id in names:
            try:constants[node.targets[0].id]=ast.literal_eval(node.value)
            except ValueError:pass
    # Explicit reviewed declaration expressions; no source module import.
    constants.update(TIMEOUT=1827.426625+120.,LIMITS=dict(c_free_min_bytes=50*2**30,g_free_min_bytes=75*2**30,host_available_min_bytes=12*2**30,new_output_cap_bytes=120*2**30,pending_cell_reserve_bytes=4*2**30),
        LIMIT_NOTES=dict(native_lane_drain_timeout_sec=30,native_final_join_sec=65,scheduler_max_pending_events=20000,scheduler_max_events=1000000,scheduler_max_utterances=4096,tracker_max_tracks=256,
        scope='Original historical limits unchanged. Native observer stores display/events in memory and scans session bytes; saturation/timeout is an outcome, not repaired by this wrapper. The outer source+120 s execution deadline has up to25 s additional owned cleanup, reported separately.'))
    ns=dict(constants,Path=Path,deepcopy=deepcopy,re=re,require=require,digest=base.digest,HERE=HERE,REPORT=REPORT,PAYLOAD=PAYLOAD,
        OLD=base.SIM/'reports/S6B/20260909T230840Z',COMPOSITION=REPORT/'long_session/v1/COMPOSITION.json',PINS={'s6b_paced.py':'e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9'},
        DEADLINE=dt('2026-09-13T11:35:40+00:00'),L=types.SimpleNamespace(dt=dt),small=lambda b:{k:b[k] for k in ('path','bytes','sha256')},read_bound=lambda p,b=None:reader.read(p,b))
    functions={'roots','authorities','make_job','asset_bindings','validate_plan','validate_worker_result'}
    return compile_functions(path,functions,ns)

def admit_long(reader,b):
    plan,pb=bound(reader,b);g=long_guards(reader);a=g['authorities']();g['validate_plan'](plan,a)
    require(Path(pb['path'])==Path(plan['report_root'])/'MANIFEST.json','Continuous manifest path differs')
    held=[x for x in plan['sources'] if Path(x['path']).name=='s6c_long_b36_v1.py'];require(len(held)==1 and held[0]['sha256']==PINS['s6c_long_b36_v1.py'],'Unreviewed continuous source')
    require(plan['driver']['sha256']=='e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9','Exact native worker source required')
    require(plan['original_worker_ast_sha256']=='2ba2cac603b8302797a7b99b7c44f8f50a67b4692d1718e92391ea542a1f2d3f','Original worker function declaration differs')
    g['asset_bindings'](a['spec'])
    return plan,pb,a,g

def admit_plan(reader,b):
    plan,_=bound(reader,b)
    if plan['schema']==SENTINEL:return S.admit_plan(reader,b)
    if plan['schema']==LONG:return admit_long(reader,b)
    return v4.admit_plan(reader,b)

def admit_complete_cell(reader,job,plan,pb,spec,state=None):
    require(plan['schema']!=LONG,'Continuous historical session has a distinct API/source schema')
    return (S.admit_complete_cell if plan['schema']==SENTINEL else v4.admit_complete_cell)(reader,job,plan,pb,spec,state)

def admit_paced_index(reader,b,plan,pb):return (S.admit_paced_index if plan['schema']==SENTINEL else v4.admit_paced_index)(reader,b,plan,pb)

def long_argv(plan,pb):
    return [str(base.SIM.parents[2]/'.edge-speech-env/python.exe'),str(HERE/'s6c_long_b36_v1.py'),'worker','--manifest',pb['path'],'--owner-lease',str(REPORT/'PACED_QUIET_OWNER.json')]

def check_argv(actual,wanted):
    require(isinstance(actual,list) and len(actual)==len(wanted),'Exact original child argv shape required')
    for i,(a,b) in enumerate(zip(actual,wanted)):require(base.canonical(a)==base.canonical(b) if i in (0,1,4,6) else a==b,'Original child argv differs')

def long_row(job,plan,pb,launch,lb):
    o=owner(launch);row=v4.row_base(job,launch,lb,pb,False)
    row.update(branch='HISTORICAL_B36_CONTINUOUS_NATIVE',epoch='S6B_epoch2',epoch_manifest=plan['historical_epoch'],case_id=None,execution_mode='PACED_NATIVE_CONTINUOUS',source_kind='EXISTING_CONTINUOUS_COMPOSITION',source_composition_epoch='S6C_epoch2',source_composition=plan['composition'],actual_app_path=job['app_path'],actual_profile=job['profile'],source_asr=job['input'],source_identity=job['input'])
    return row

def admit_long_native(reader,plan,pb,a,g):
    job=plan['jobs'][0];out=Path(plan['output_root'])/'jobs'/job['job_id'];launch,lb=reader.read(out/'LAUNCH.json');o=owner(launch)
    require(launch['manifest']==pb and launch['job_key']==job['job_key'],'Continuous launch identity differs');check_argv(launch['argv'],long_argv(plan,pb))
    row=long_row(job,plan,pb,launch,lb);refs=[pb,lb]
    nb=None;native=None;ab=None;ob=None
    if (out/'CONTINUOUS_ADMISSION.json').exists():
        admission,ab=reader.read(out/'CONTINUOUS_ADMISSION.json');refs.append(ab);v3.same_owner(o,admission['owner']);check_argv(admission['owner']['argv'],long_argv(plan,pb))
        require(admission['schema']==LONG and admission['status']=='STARTED' and admission['manifest']==pb and admission['job']==job and admission['actual_execution_epoch']=='S6B_epoch2' and admission['historical_epoch']==plan['historical_epoch'] and admission['source_composition_epoch']=='S6C_epoch2' and admission['composition']==plan['composition'],'Continuous native admission differs')
    if (out/'WORKER_RESULT.json').exists():
        require(ab is not None,'Native result without continuous admission');native,nb=reader.read(out/'WORKER_RESULT.json');g['validate_worker_result'](native,job,o,out);refs.append(nb)
        row.update(status='NATIVE_COMPLETE_OBSERVER_PARTIAL',native_session_complete=True,session_dir=base.canonical(native['session_dir']),session_evidence='BOUND_EXACT_HISTORICAL_B36_CONTINUOUS_WORKER',audio_duration_sec=native['source_duration_sec'],elapsed_sec=native['full_worker_elapsed_sec'],process_cpu_sec=native['process_cpu_sec_at_end'],bundle_admission_sec=native['bundle_admission_sec'],actual_counts=native['event_counts'],output_bindings=base.payloads(native),finished_utc=native['created_utc'])
    if (out/'WORKER_FAILURE.json').exists():
        failure,fb=reader.read(out/'WORKER_FAILURE.json');require(failure['status']=='FAILED' and failure['job_key']==job['job_key'] and isinstance(failure['traceback'],str) and failure['traceback'],'Original worker failure identity differs');refs.append(fb);row.update(status='FAILED_OUTER_NATIVE_COMPLETE' if nb else 'FAILED',error=failure['traceback'])
    if (out/'CONTINUOUS_OUTCOME.json').exists():
        outcome,ob=reader.read(out/'CONTINUOUS_OUTCOME.json');refs.append(ob);v3.same_owner(o,outcome['owner']);check_argv(outcome['owner']['argv'],long_argv(plan,pb))
        require(outcome['schema']==LONG_RESULT and outcome['manifest']==pb and outcome['job_key']==job['job_key'] and outcome['native_result']==nb and outcome['historical_epoch']==plan['historical_epoch'] and outcome['composition']==plan['composition'] and outcome['actual_execution_epoch']=='S6B_epoch2' and outcome['source_composition_epoch']=='S6C_epoch2','Continuous outcome lineage differs')
        if outcome['status']=='NATIVE_COMPLETE':require(nb is not None and outcome['error'] is None and outcome['original_worker_function_unchanged'] is True,'Native success outcome differs')
        else:require(outcome['status']=='FAILED' and outcome['error'] is not None,'Failure outcome must remain explicit');row.update(status='FAILED_OUTER_NATIVE_COMPLETE' if nb else 'FAILED',error=outcome['error'])
    if (Path(plan['report_root'])/'RESULT.json').exists():
        require(nb is not None and ob is not None,'Complete continuous result lacks actual worker/outcome');result,rb=reader.read(Path(plan['report_root'])/'RESULT.json');refs.append(rb)
        require(outcome['status']=='NATIVE_COMPLETE' and outcome['error'] is None and outcome['original_worker_function_unchanged'] is True,'Completed RESULT contradicts failed/changed original native outcome')
        require(result['schema']==LONG_RESULT and result['status']=='COMPLETE_NATIVE_AND_OWNED_CHILD_CLOSED' and result['manifest']==pb and result['job']==job and result['native_result']==nb and result['native_outcome']==ob and result['source_kind']=='EXISTING_CONTINUOUS_COMPOSITION' and result['actual_execution_epoch']=='S6B_epoch2' and result['historical_epoch']==plan['historical_epoch'] and result['source_composition_epoch']=='S6C_epoch2' and result['composition']==plan['composition'],'Outer completed continuous source differs')
        v3.same_owner(o,result['native_owner']);require(result['source_duration_sec']==1827.426625 and result['source_duration_samples']==29238826 and result['all_owned_processes_closed'] is True and result['original_worker_unchanged'] is True,'Continuous completion differs')
        require(result['periodic_process_samples']>=0 and result['terminal_process_samples']==1 and result['process_samples']==result['periodic_process_samples']+1,'Periodic/terminal/total sample denominator differs')
        trajectory=[b for b in result['artifacts'] if Path(b['path'])==out/'PROCESS_SAMPLES.jsonl'];require(len(trajectory)==1,'One continuous process trajectory required')
        require(result['artifacts']==[nb,ob,ab,lb,trajectory[0],native['events'],native['journal'],native['display_events'],native['summary_binding']],'Continuous artifact lineage differs')
        own=result['owned_processes'];require(any((x['pid'],x['creation_time'])==(o['pid'],o['creation_time']) for x in own),'Native owner omitted');require(len({(x['pid'],x['creation_time']) for x in own})==len(own),'Duplicate native owner')
        for x in own:owner(x);require(x['alive'] is False,'Completed recorded child not closed')
        row.update(status='COMPLETE',recorded_owned_processes=own,output_bindings=dict(native=row['output_bindings'],artifacts=result['artifacts']),continuous_result=rb,observer_stats=result['observer_stats'],trajectory_counts={k:result[k] for k in ('periodic_process_samples','terminal_process_samples','process_samples')})
    if native is None and row['status']=='STARTED' and row['process_state']['alive'] is False:row['status']='PARTIAL_CLOSED_WITHOUT_FINAL_RESULT'
    row['receipt_bindings']=refs
    return row

def long_invocations(reader,plan,pb):
    records=[];owners=[];spawns=[];job=plan['jobs'][0]
    for path in sorted((Path(plan['report_root'])/'invocations').glob('*/ADMISSION.json')):
        admission,ab=reader.read(path);o=owner(admission['owner']);require(admission['status']=='STARTED' and admission['manifest']==pb,'Continuous coordinator admission differs')
        owners.append(dict(branch='B36_CONTINUOUS_COORDINATOR',pid=o['pid'],creation_time=o['creation_time'],process_state=v3.process_state(o['pid'],o['creation_time']),source=ab));record=dict(admission=ab,status='STARTED')
        spawn=path.with_name('CHILD_SPAWN.json')
        if spawn.exists():
            value,sb=reader.read(spawn);require(value['status']=='POPEN_SUCCEEDED_IDENTITY_PENDING' and value['manifest']==pb and value['job_key']==job['job_key'] and isinstance(value['pid'],int) and not isinstance(value['pid'],bool) and value['pid']>0 and value['creation_time'] is None,'Successful spawn declaration differs');check_argv(value['argv'],long_argv(plan,pb));spawns.append((value,sb));record['spawn']=sb
        op=path.with_name('NATIVE_OUTCOME.json');cp=path.with_name('CLOSURE.json')
        if op.exists():
            outcome,ob=reader.read(op);v3.same_owner(o,outcome['owner']);require(outcome['schema']==LONG and outcome['manifest']==pb,'Coordinator outcome differs');record.update(outcome=ob,status=outcome['status'])
            require(outcome['status'] in ('NATIVE_COMPLETE','FAILED'),'Unknown continuous coordinator outcome')
            if outcome['continuous_result'] is not None:
                complete,rb=bound(reader,outcome['continuous_result']);v3.same_owner(o,complete['owner'])
                require(Path(rb['path'])==Path(plan['report_root'])/'RESULT.json' and complete['schema']==LONG_RESULT and complete['status']=='COMPLETE_NATIVE_AND_OWNED_CHILD_CLOSED' and complete['manifest']==pb and outcome['native_result']==complete['native_result'],'Coordinator/result binding differs')
                cell_admissions=[b for b in complete['artifacts'] if Path(b['path'])==Path(plan['output_root'])/'jobs'/job['job_id']/'CONTINUOUS_ADMISSION.json'];require(len(cell_admissions)==1,'One exact bound native continuous admission required')
                cell,cellb=bound(reader,cell_admissions[0]);v3.same_owner(cell['owner'],complete['native_owner'])
                require(cell['manifest']==pb and cell['job']==job and cell['quiet_lease']==admission['quiet_lease'],'Native/coordinator quiet lease differs')
                identity_sets=[]
                for owned in (complete['owned_processes'],outcome['owned_processes']):
                    for member in owned:owner(member);require(member['alive'] is False,'Successful continuous owned process must be closed')
                    identities={(member['pid'],member['creation_time']) for member in owned};require(len(identities)==len(owned),'Duplicate successful owned identity');identity_sets.append(identities)
                require(identity_sets[0]==identity_sets[1] and (complete['native_owner']['pid'],complete['native_owner']['creation_time']) in identity_sets[0],'Native/coordinator complete owner sets differ')
            if outcome['status']=='NATIVE_COMPLETE':require(outcome['continuous_result'] is not None and outcome['error'] is None,'Native completion lacks exact result')
            for x in outcome['owned_processes']:
                if x['creation_time'] is None:owners.append(dict(branch='B36_UNVERIFIED_SPAWN',pid=x['pid'],creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_PROCESS_IDENTITY'),source=ob))
                else:owner(x);owners.append(dict(branch='B36_RECORDED_CHILD',pid=x['pid'],creation_time=x['creation_time'],process_state=v3.process_state(x['pid'],x['creation_time']),source=ob))
            if cp.exists():
                c,cb=reader.read(cp);v3.same_owner(o,c['owner']);require(c['schema']==LONG and c['manifest']==pb and c['pre_release_outcome']==ob and c['continuous_result']==outcome['continuous_result'] and c['owned_processes']==outcome['owned_processes'] and c['error']==outcome['error'],'Continuous closure lineage differs');record['closure']=cb;record['closure_status']=c['status']
                release=c['lease_release']
                if c['status']=='NATIVE_COMPLETE_QUIET_RELEASED':require(outcome['status']=='NATIVE_COMPLETE' and outcome['error'] is None and outcome['continuous_result'] is not None and release['status']=='RELEASED' and release['released'] is True,'Complete closure lacks native result or actual lease release')
                if release['status']=='RELEASED':
                    require(release['released'] is True,'Lease release flag differs');lease,kb=bound(reader,release['archived_binding']);v3.same_owner(o,lease)
                    require(lease['kind']=='S6C_EXACT_HISTORICAL_B36_CONTINUOUS' and lease['manifest']==pb and lease['quiet_admission']==admission['quiet_admission'] and release['source']==admission['quiet_lease'],'Released original quiet lease differs')
                    require(all(x['alive'] is False and x['creation_time'] is not None for x in c['owned_processes']),'Released quiet lease with unknown/alive recorded child')
                else:owners.append(dict(branch='B36_QUIET_RELEASE_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='LEASE_RELEASE_UNVERIFIED'),source=cb))
        records.append(record)
    return records,owners,spawns

def unverified_spawn_row(plan,pb,value,sb):
    job=plan['jobs'][0];fake=dict(pid=value['pid'],creation_time=1.,argv=value['argv']);row=v4.row_base(job,fake,sb,pb,False)
    row.update(physical_id=base.digest(['successful_popen_unverified_creation',sb['path'],value['pid']]),branch='HISTORICAL_B36_CONTINUOUS_NATIVE',status='UNVERIFIED_SPAWN_IDENTITY',creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_PROCESS_IDENTITY'),epoch='S6B_epoch2',epoch_manifest=plan['historical_epoch'],source_kind='EXISTING_CONTINUOUS_COMPOSITION',source_composition_epoch='S6C_epoch2',source_composition=plan['composition'],case_id=None,execution_mode='PACED_NATIVE_CONTINUOUS',session_evidence='SUCCESSFUL_POPEN_ONLY_NOT_PROVEN_MODEL_SESSION',error='Popen occurred but finite process creation identity was not recorded')
    return row

def additive(original,admissions,reader,declared,issues,rows,bysession,discovered):
    groups=dict(ordinary=[],sentinel=[],long=[])
    for b in admissions:
        value,_=bound(reader,b);groups['sentinel' if value['schema']==SENTINEL else 'long' if value['schema']==LONG else 'ordinary'].append(b)
    result=v4.paced_adapter(original,groups['ordinary'],reader,declared,issues,rows,bysession,discovered)
    result=S.paced_adapter(lambda *args:result,groups['sentinel'],reader,declared,issues,rows,bysession,[])
    summaries=[];new=[];before=len(issues);found={base.canonical(p) for p in (REPORT/'long_b36').glob('*/MANIFEST.json')};supplied={base.canonical(b['path']) for b in groups['long']}
    if found-supplied:issues.append(dict(scope='CONTINUOUS_MANIFEST_NOT_ADMITTED',paths=sorted(found-supplied)))
    for b in groups['long']:
        try:
            plan,pb,a,g=admit_long(reader,b);job=plan['jobs'][0];out=Path(plan['output_root'])/'jobs'/job['job_id'];row=None
            try:inv,owners,spawns=long_invocations(reader,plan,pb);result['owner_observations']+=owners
            except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:
                issues.append(dict(manifest=pb,coordinator_lineage_error=repr(exc)));inv=[];spawns=[]
                result['owner_observations'].append(dict(branch='B36_COORDINATOR_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_COORDINATOR_LINEAGE')))
                for path in sorted((Path(plan['report_root'])/'invocations').glob('*/CHILD_SPAWN.json')):
                    value,sb=reader.read(path)
                    require(value['manifest']==pb and value['job_key']==job['job_key'] and value['status']=='POPEN_SUCCEEDED_IDENTITY_PENDING','Unverified coordinator spawn differs');spawns.append((value,sb))
            if (out/'LAUNCH.json').exists():
                try:row=admit_long_native(reader,plan,pb,a,g)
                except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:
                    launch,lb=reader.read(out/'LAUNCH.json');require(launch['job_key']==job['job_key'],'Unverified launch key differs');row=long_row(job,plan,pb,launch,lb);row.update(status='UNVERIFIED_CONTINUOUS_LINEAGE',error=repr(exc));issues.append(dict(manifest=pb,error=repr(exc)))
                require(len(spawns)==1 and spawns[0][0]['pid']==row['pid'],'Continuous launch does not reconcile to one successful Popen')
            elif spawns:
                require(len(spawns)==1,'Multiple successful spawns under one continuous attempt namespace');row=unverified_spawn_row(plan,pb,*spawns[0]);issues.append(dict(manifest=pb,error='Unverified successful child spawn'))
            else:require(not any((out/n).exists() for n in ('WORKER_RESULT.json','CONTINUOUS_ADMISSION.json','CONTINUOUS_OUTCOME.json','WORKER_FAILURE.json')),'Native artifacts without a recorded physical launch')
            if row:
                if v4.add_physical(rows,bysession,row):new.append(row)
                declared.add(row['output_bindings'],row['receipt_bindings'][-1],'EXACT_HISTORICAL_CONTINUOUS_NATIVE_DECLARATIONS')
            summaries.append(dict(manifest=pb,requested_sessions=1,status=row['status'] if row else 'NOT_LAUNCHED',invocations=inv,physical_attempts=int(row is not None),source_composition_epoch='S6C_epoch2',actual_native_epoch='S6B_epoch2',native_session_complete=bool(row and row['native_session_complete'])))
            declared.add(plan,pb,'EXACT_HISTORICAL_CONTINUOUS_ADMISSION')
        except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:issues.append(dict(manifest=b,error=repr(exc)))
    if len(issues)>before:result['owner_observations'].append(dict(branch='CONTINUOUS_LINEAGE_INCOMPLETE',pid=None,creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_CONTINUOUS_LINEAGE')))
    result['continuous_b36_v5']=dict(schema=SCHEMA,plans=summaries,physical_attempts=len(new),native_sessions_with_complete_receipts=sum(r['native_session_complete'] for r in new),completed_sessions=sum(r['status']=='COMPLETE' for r in new),scope='One successful Popen is an attempt even when PID creation could not be admitted. Successful source/index references are not additional inference. Native completion and coordinator/lease closure remain distinct.')
    return result

def collect(args):
    require(args.paced_manifest,'Explicit manifests required');require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.version or ''),'Fresh simple version required');admissions=[]
    for p,sha in args.paced_manifest:
        raw=Path(p).read_bytes();b=base.binding(p,raw);require(b['sha256']==sha,'Explicit manifest SHA differs');admissions.append(b)
    require(len({b['path'] for b in admissions})==len(admissions),'Duplicate manifest argument');before=source_bindings()
    with v3.patched_base():
        original=base.collect_auxiliary;base.collect_auxiliary=lambda *a:additive(original,admissions,*a)
        try:result=base.collect(args)
        finally:base.collect_auxiliary=original
    require(source_bindings()==before,'Additive sources changed during collection')
    return base.write_new(Path(result['snapshot']['path']).parent/'INVENTORY_V5_RECEIPT.json',dict(schema=SCHEMA,status='COMPLETE_SCOPED_ADAPTER_COLLECTION',sources=before,admitted_manifests=admissions,inventory=result['snapshot'],result=result,model_calls=0,scope='Metadata-only extension; inherits active/unverified coverage flags and does not declare the whole study complete.'))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__,allow_abbrev=False);p.add_argument('action',choices=('collect',));p.add_argument('--version',required=True);p.add_argument('--paced-manifest',nargs=2,action='append',required=True,metavar=('PATH','SHA256'));print(json.dumps(collect(p.parse_args()),indent=2))
