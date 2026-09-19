"""Paced physical lineage adapter; README_S6C_EXECUTION_INVENTORY_V4.md."""
from __future__ import annotations
import argparse, ast, hashlib, importlib, json, math, re, sys, tempfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
PINS={'s6c_execution_inventory_v3.py':'8820bc19d88b6706aed93cdf5c879688f66f5b96e9d910124f94d1bebfc39d58',
      'README_S6C_EXECUTION_INVENTORY_V3.md':'8d61796da304d72632607bbee7fca5f4d5651fd4b52a1d3454a4658e189806ce',
      's6c_paced_epoch4.py':'b4b0dc48190654edbdcb6259cf2b8abc08d8675d49367863ff539f7eb54df8a3',
      's6c_paced_controls.py':'abacc5db48137a808a9417c26e44b921be817dda4e6271efe7a9fb7dfd7bf6a9',
      's6c_paced_b36_v1.py':'8d60474f0517b5f43dbdb64a5194829241ded8d5acdbd622ec3bef6851152abd'}
for name,digest in PINS.items():
    if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=digest:raise ValueError('Held dependency changed: '+name)
v3=importlib.import_module('s6c_execution_inventory_v3');base=v3.base
if Path(v3.__file__).resolve()!=HERE/'s6c_execution_inventory_v3.py':raise ValueError('Wrong V3 import')
REPORT=base.REPORT;PAYLOAD=base.PAYLOAD
SCHEMA='s6c-execution-inventory-paced-adapter.v4'
CANONICAL='s6c-canonical-paired-paced.v1'
HISTORICAL={'s6c-historical-paced-controls.v1':('B00','B01'),'s6c-historical-paced-b36.v1':('B36',)}


def require(ok,message):
    if not ok:raise ValueError(message)


def pure_native_guards():
    """Compile only exact pinned pure guard functions, never import/run the driver."""
    names={'validate_source_rows','source_record','candidate_routes','grid','selected_panel','native_folder','valid_owner','validate_native_identity'}
    tree=ast.parse((HERE/'s6c_paced_epoch4.py').read_bytes())
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names]
    require(len(nodes)==len(names),'Held pure guard inventory differs')
    gates=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GATE_CASES' for t in n.targets))
    ns=dict(Path=Path,math=math,GATE_CASES=gates)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(HERE/'s6c_paced_epoch4.py'),'exec'),ns)
    return ns


GUARDS=pure_native_guards()


def bound(reader,b):return reader.read(b['path'],b)


def owner(value):
    require(v3.finite_owner(value.get('pid'),value.get('creation_time')),'Finite actual process owner required')
    return value


def digest_guard(value,field):
    copied=dict(value);expected=copied.pop(field)
    require(base.digest(copied)==expected,'Manifest/job digest differs')


def expected_worker_argv(job,plan,pb):
    py=str(base.SIM.parents[2]/'.edge-speech-env/python.exe')
    if plan['schema']==CANONICAL:return [py,str(HERE/'s6c_paced_epoch4.py'),'worker','--manifest',pb['path'],'--job-id',job['job_id'],'--owner-lease',str(REPORT/'PACED_QUIET_OWNER.json')]
    return [py,plan['driver']['path'],'--mode','worker','--manifest',pb['path'],'--job-id',job['job_id'],'--timeout',str(plan['timeout_sec'])]


def validate_launch(launch,job,plan,pb):
    require(launch['job_key']==job['job_key'],'Wrong launched job')
    wanted=expected_worker_argv(job,plan,pb);actual=launch['argv']
    require(isinstance(actual,list) and len(actual)==len(wanted),'Worker argv shape/duplicate switches differ')
    paths={0,1,4,8} if plan['schema']==CANONICAL else {0,1,5}
    for i,(a,b) in enumerate(zip(actual,wanted)):
        require(base.canonical(a)==base.canonical(b) if i in paths else a==b,'Worker argv changes native driver/action/input/job')
    if plan['schema']==CANONICAL:require(launch['manifest']==pb,'Canonical launch manifest differs')


def native_result_metadata(reader,b,job,source,spec,o):
    native,nb=bound(reader,b)
    require(Path(nb['path'])==GUARDS['native_folder'](job)/'RESULT.json','Native result path differs')
    GUARDS['validate_native_identity'](native,job,source,spec,o)
    closures=[x for x in native['native_artifacts'] if Path(x['path']).name=='session_finalization_v3.json'];require(len(closures)==1,'One bound native finalization required')
    closure,kb=bound(reader,closures[0]);require(closure['state']=='COMPLETED' and closure['finalization_error'] is None and not closure['live_lanes_at_finalization'] and not closure['resident_bundle_lease_retained'] and closure['event_and_transcript_handles_closed'] is True,'Native finalization failed')
    return native,nb,kb


def admit_plan(reader,b):
    plan,pb=bound(reader,b);digest_guard(plan,'manifest_key')
    require(plan['schema'] in (CANONICAL,*HISTORICAL),'Unsupported paced schema')
    jobs=plan['jobs'];require(jobs and len({j['job_id'] for j in jobs})==len(jobs),'Unique paced job IDs required')
    for j in jobs:digest_guard(j,'job_key')
    if plan['schema']==CANONICAL:
        root=REPORT/'paced_candidates'/plan['namespace']
        require(re.fullmatch(r'[A-Za-z0-9_-]{1,60}',plan['namespace']) and Path(pb['path'])==root/'MANIFEST.json','Canonical namespace differs')
        require(plan['report_root']==str(root) and plan['payload_root']==str(PAYLOAD/'paced_candidates'/plan['namespace']),'Canonical roots differ')
        eb=plan['execution_manifest'];v3.expected_binding(eb,REPORT/'EPOCH4_EXECUTION_MANIFEST.json',v3.EPOCH4_SHA)
        spec,_=bound(reader,eb);require(spec['epoch']=='epoch4','Actual execution epoch differs')
        require(spec['execution_digest']==base.digest({k:spec[k] for k in ('execution_files','assets','versions','state_policy')}),'Execution digest differs')
        require(plan['input_index']==spec['input_index'],'Canonical input authority differs')
        inputs,_=bound(reader,plan['input_index']);lookup={}
        for r in inputs['rows']:
            k=(r['case_id'],r['stream']);require(k not in lookup,'Duplicate canonical input');lookup[k]=r
        panel,_=bound(reader,plan['panel'])
        require(plan['panel']['sha256']=='f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da','Unreviewed paced panel')
        selected=GUARDS['selected_panel'](panel,plan['panel_mode'],plan['candidates']);routes=GUARDS['candidate_routes'](spec,plan['candidates'])
        actual=[(j['candidate_id'],j['case_id'],j['asr_tap'],j['repetition']) for j in jobs]
        require(actual==GUARDS['grid'](plan['candidates'],selected) and len(jobs)==plan['requested'],'Paced product differs')
        require(plan['source_case_ids']==selected['case_ids'] and plan['repeat_case_ids']==selected['repeated_case_ids'],'Panel repeat population differs')
        sources=[x for x in plan['sources'] if Path(x['path']).name=='s6c_paced_epoch4.py']
        require(len(sources)==1 and sources[0]['sha256']==PINS['s6c_paced_epoch4.py'],'Canonical driver is not held source')
        for j in jobs:
            r=routes[j['candidate_id'],j['asr_tap']]
            require(j['profile_row']==r and j['profile_sha256']==base.digest(r) and j['identity_tap']==r['identity_tap'],'Exact registered paced profile differs')
            require(j['report_root']==str(root/'jobs'/j['job_id']) and j['payload_root']==str(Path(plan['payload_root'])/'jobs'/j['job_id']),'Cell namespace differs')
            source,sb=bound(reader,j['source'])
            require(source==GUARDS['source_record']({t:lookup[j['case_id'],t] for t in ('O0','O1')},plan['input_index']),'Whole canonical source differs')
            require(Path(sb['path'])==root/'sources'/(j['case_id']+'.json'),'Canonical source path differs')
            if j['gallery'] is None:
                require(j['gallery_row'] is None and r['gallery_condition']=='NONE' and r['profile']['identity']['mode']=='none','Empty identity route differs')
            else:
                gi,_=bound(reader,spec['gallery_index']);matches=[x for x in gi['rows'] if x['case_id'] is None and x['gallery_condition']==r['gallery_condition'] and x['enrollment_tier']==r['enrollment_tier']]
                require(len(matches)==1 and matches[0]==j['gallery_row'] and matches[0]['manifest']==j['gallery'],'Actual fixed roster differs')
        return plan,pb,spec
    root=PAYLOAD/'paced_controls'/Path(plan['output_root']).name
    require(Path(plan['output_root'])==root and Path(pb['path'])==root/'MANIFEST.json','Historical paced root differs')
    expected=HISTORICAL[plan['schema']];require(tuple(plan['profiles'])==expected,'Historical candidate scope differs')
    coordinator='s6c_paced_b36_v1.py' if expected==('B36',) else 's6c_paced_controls.py'
    require(plan['coordinator']['sha256']==PINS[coordinator],'Unreviewed historical coordinator')
    require(plan['driver']['sha256']=='e755867e703bc6f4dc457db8ad6e98b078af8cf3abcf15fce8adf58efd10fcd9','Historical native source changed')
    require(plan['source_sealed_index']['sha256']=='2ce021fccd0cff0d60d699c2a56e541949fd1348bf529b6f12ba8ca796336c8e','Historical authority differs')
    require(plan['historical_epoch']['sha256']=='ea0d57f0af68c2b7fd8ac4298154d3d460c804e0a6650887383a804709864673','Exact historical epoch authority differs')
    sealed,_=bound(reader,plan['source_sealed_index'])
    members=[{k:r[k] for k in ('path','bytes','sha256')} for r in sealed['artifacts'] if base.canonical(r['path'])==base.canonical(plan['historical_epoch']['path'])]
    require(members==[plan['historical_epoch']],'Historical epoch is not the exact sealed member')
    spec,_=bound(reader,plan['historical_epoch']);require(spec['epoch']=='epoch2','Historical S6B epoch differs')
    registry,_=bound(reader,spec['effective_profile_registry']);entries={x['profile_id']:x for x in registry['profiles']}
    require(plan['panel']['sha256']=='f303d7e80bc9dd8fa8b7ba7444216d1e6b29f75a0cce8762c40d92ce5201c6da','Exact historical panel authority differs')
    panel,_=bound(reader,plan['panel'])
    require(plan['cases']==panel['case_ids'] and plan['repeat_case_sets']==[dict(repetition=1,case_ids=panel['case_ids']),dict(repetition=2,case_ids=panel['repeated_case_ids'])] and plan['streams']==['O0','O1'],'Historical panel identifiers/repeats differ')
    require(spec['input_index']['sha256']=='97b20d821c671794b24b1f8a4a9d4049fd192767bd0a093309887c279b48e70d','Historical canonical input authority differs')
    inputs,_=bound(reader,spec['input_index']);lookup={}
    for r in inputs['rows']:
        k=r['case_id'],r['stream'];require(k not in lookup,'Duplicate historical input');lookup[k]=r
    wanted=[(p,c,t,s['repetition']) for s in plan['repeat_case_sets'] for c in s['case_ids'] for t in ('O0','O1') for p in (expected if s['repetition']%2 else tuple(reversed(expected)))]
    require([(j['profile_id'],j['case_id'],j['stream'],j['repetition']) for j in jobs]==wanted,'Historical job product differs')
    for j in jobs:
        source=lookup[j['case_id'],j['stream']]
        require(j['input']==source['audio'] and j['input_pcm_sha256']==source['audio_pcm_sha256'] and j['duration_sec']==source['duration_sec'] and j['gain_context']==source['historical_gain_applied_once'] and j['source_sample_rate']==16000,'Exact historical source/tap/gain differs')
        require(j['realtime'] is True and j['telemetry'] is None and j['assets']==spec['assets'],'Historical actual settings differ')
        require((j['profile'] is None)==(j['profile_id']=='B00'),'Historical default/profile route differs')
        if j['profile_id']=='B00':
            require(Path(j['app_path'])==base.SIM/'staging/s6a/20260909T202250Z/baseline_app' and j['mode']=='EXACT_IMMUTABLE_B0_DEFAULT','Exact historical B00 source differs')
            require(plan['historical_baseline_authority']['execution_contract']['sha256']=='4be1e8cdd342124c36716e7267f5e28ae5f3d0655c1685696af56cab8057148a','Exact B00 contract differs')
        else:require(j['profile']==entries[j['profile_id']]['profile'] and j['recipe_id']==entries[j['profile_id']]['recipe_id'] and Path(j['app_path'])==Path(spec['root'])/'app','Exact historical research profile differs')
    return plan,pb,spec


def metadata_chain(reader,job,plan,pb,spec):
    """Validate small authoritative metadata; payload bindings are declarations only."""
    folder=Path(job['report_root']);cell,cb=reader.read(folder/'CELL_RESULT.json');o=owner(cell['owner'])
    source,sb=bound(reader,job['source'])
    require(cell['schema']=='s6c-canonical-paced-cell-result.v1' and cell['status']=='COMPLETE','Actual canonical result required')
    for k,v in dict(manifest=pb,job=job,source=sb,source_kind='CANONICAL_SINGLE_SCENE_PAIR',actual_execution_epoch='epoch4',execution_manifest=plan['execution_manifest'],source_offset_samples=0,inserted_gap_samples=0,original_native_function_unchanged=True).items():require(cell[k]==v,'Canonical result lineage differs: '+k)
    native,nb,kb=native_result_metadata(reader,cell['native_result'],job,source,spec,o)
    admission,ab=reader.read(folder/'CELL_ADMISSION.json');launch,lb=reader.read(folder/'LAUNCH.json');outcome,ob=reader.read(folder/'CELL_OUTCOME.json')
    for k in ('owner','manifest','job','source','source_kind','actual_execution_epoch','execution_manifest'):require(admission[k]==cell[k],'Cell admission differs: '+k)
    require(admission['status']=='STARTED','Actual started admission required')
    validate_launch(launch,job,plan,pb);require(launch['argv']==o['argv'],'Actual launch/owner argv differs')
    v3.same_owner(o,launch)
    require(outcome['owner']==o and outcome['manifest']==pb and outcome['job_key']==job['job_key'] and outcome['native_result']==nb and outcome['status']=='NATIVE_RETURNED' and outcome['error'] is None and outcome['protected_functions_restored'] is True,'Cell outcome differs')
    refs=[cb,nb,ab,lb,ob,kb];complete=None
    if (folder/'COMPLETE.json').exists():
        complete,db=reader.read(folder/'COMPLETE.json');refs.append(db)
        require(complete['status']=='COMPLETE' and complete['job_key']==job['job_key'] and complete['job_id']==job['job_id'] and complete['cell_result']==cb and complete['native_result']==nb and complete['source_kind']=='CANONICAL_SINGLE_SCENE_PAIR' and complete['all_owned_processes_closed'] is True,'Coordinator completion differs')
        for b in [cb,nb,ab,lb,ob]+native['native_artifacts']+[native['process_samples']]:require(b in complete['artifacts'],'Completed artifact chain omits binding')
        external=[b for b in complete['artifacts'] if Path(b['path'])==folder/'PROCESS_TREE_SAMPLES.jsonl']
        require(len(external)==1,'One declared external trajectory required')
        require(complete['artifacts']==[cb,nb,external[0],ob,ab,lb]+native['native_artifacts']+[native['process_samples']],'Exact completed artifact list differs')
        require(len({base.canonical(b['path']) for b in complete['artifacts']})==len(complete['artifacts']),'Duplicate completed artifact path')
        own=complete['owned_processes'];require(any((r['pid'],r['creation_time'])==(o['pid'],o['creation_time']) for r in own),'Completed owner omitted')
        require(len({(r['pid'],r['creation_time']) for r in own})==len(own),'Duplicate completed owner')
        for r in own:owner(r)
    return cell,native,refs,complete


def admit_complete_cell(reader,job,plan,pb,spec,state=None):
    """Public closed-cell metadata API; does not rehash declared native payloads."""
    cell,native,refs,complete=metadata_chain(reader,job,plan,pb,spec)
    require(complete is not None,'Coordinator COMPLETE is required')
    state=state or v3.process_state
    states=[dict(**o,process_state=state(o['pid'],o['creation_time'])) for o in complete['owned_processes']]
    require(all(o['process_state']['alive'] is False for o in states),'Recorded native owners live or unverified')
    def get(name):return next(b for b in refs if Path(b['path']).name==name)
    return dict(job=job,complete=complete,complete_binding=get('COMPLETE.json'),cell=cell,cell_binding=get('CELL_RESULT.json'),native=native,native_binding=get('RESULT.json'),artifacts=complete['artifacts'],owner_observations=states,scope='JSON authority chain and current recorded-owner closure; declared payload bytes require downstream exact reads.')


def admit_paced_index(reader,b,plan,pb):
    value,ib=bound(reader,b);jobs={j['job_id']:j for j in plan['jobs']}
    require(Path(ib['path'])==Path(plan['report_root'])/'PACED_INDEX.json','Paced index namespace differs')
    require(value['schema']==CANONICAL and value['status']=='COMPLETE' and value['manifest']==pb and value['requested']==value['completed']==len(jobs),'Complete paced index identity differs')
    refs=value['rows'];require(len(refs)==len(jobs) and {r['job_id'] for r in refs}==set(jobs),'Exact paced index product differs')
    for r in refs:
        require(r['status'] in ('COMPLETE','COMPLETE_REUSED'),'Invalid paced index reference status')
        c,cb=bound(reader,r['completion']);j=jobs[r['job_id']]
        require(Path(cb['path'])==Path(j['report_root'])/'COMPLETE.json' and c['status']=='COMPLETE' and c['job_key']==j['job_key'],'Indexed completed job differs')
    return value,ib


def row_base(job,launch,lb,pb,canonical):
    o=owner(launch);pid=job['candidate_id'] if canonical else job['profile_id'];tap=job['asr_tap'] if canonical else job['stream'];it=job['identity_tap'] if canonical else tap
    return dict(physical_id=base.digest(['paced_launch',lb['path'],o['pid'],o['creation_time']]),branch='CANONICAL_SINGLE_SCENE_PACED_NATIVE' if canonical else 'HISTORICAL_PACED_CONTROL',status='STARTED',epoch='epoch4' if canonical else 'S6B_EPOCH2_WITH_EXACT_S6A_B00_BRANCH',candidate_id=pid,profile_id=pid,recipe_id=job['profile_row']['recipe_id'] if canonical else job['recipe_id'],case_id=job['case_id'],asr_tap=tap,identity_tap=it,repetition=job['repetition'],execution_mode='PACED_NATIVE_SINGLE_SCENE',job_key=job['job_key'],inference_dependency_key=None,pid=o['pid'],creation_time=o['creation_time'],process_state=v3.process_state(o['pid'],o['creation_time']),session_dir=None,session_evidence='LAUNCH_ONLY_NOT_PROVEN_MODEL_SESSION',started_utc=launch.get('created_utc'),finished_utc=None,elapsed_sec=None,native_elapsed_sec=None,process_cpu_sec=None,audio_duration_sec=None,worker_model_bundle_loads=None,bundle_admission_sec=None,gallery_manifest=None,gallery_cache_hit=None,gallery_admission_sec=None,real_gallery_load_observed=False,actual_counts=None,output_bindings={},declared_output_bytes=None,bindings_missing_byte_counts=0,receipt_bindings=[pb,lb],error=None,native_session_complete=False,source_kind='CANONICAL_SINGLE_SCENE_PAIR' if canonical else 'HISTORICAL_CANONICAL_SINGLE_SCENE',source_composition_epoch=None)


def collect_job(reader,job,plan,pb,spec):
    canonical=plan['schema']==CANONICAL;folder=Path(job['report_root']) if canonical else Path(plan['output_root'])/'jobs'/job['job_id']
    if not (folder/'LAUNCH.json').exists():
        require(not any((folder/n).exists() for n in ('CELL_ADMISSION.json','CELL_RESULT.json','CELL_OUTCOME.json','FAILURE.json','WORKER_RESULT.json','COMPLETE.json')),'Native artifacts exist without launch authority')
        return None
    launch,lb=reader.read(folder/'LAUNCH.json');validate_launch(launch,job,plan,pb)
    row=row_base(job,launch,lb,pb,canonical)
    if canonical and (folder/'CELL_RESULT.json').exists():
        cell,native,refs,complete=metadata_chain(reader,job,plan,pb,spec);v3.same_owner(launch,cell['owner'])
        row.update(status='COMPLETE' if complete else 'NATIVE_COMPLETE_OBSERVER_PARTIAL',native_session_complete=True,epoch_manifest=plan['execution_manifest'],execution_digest=spec['execution_digest'],source=job['source'],source_asr=None,source_identity=None,profile_sha256=job['profile_sha256'],gallery_manifest=job['gallery'],gallery_cache_hit=False if job['gallery'] else None,real_gallery_load_observed=bool(job['gallery']) and bool(native.get('gallery_load_receipt')),actual_counts=native.get('event_counts'),audio_duration_sec=native['source_duration_sec'],worker_model_bundle_loads=native['resident_bundle_loads'],bundle_admission_sec=native['model_load_sec'],native_elapsed_sec=native['native_elapsed_sec'],elapsed_sec=native['total_observed_worker_sec'],output_bindings=dict(native_artifacts=native['native_artifacts'],process_samples=native['process_samples']),session_dir=base.canonical(Path(next(iter(native['native_journals'].values()))['path']).parent),session_evidence='BOUND_CANONICAL_NATIVE_RESULT',finished_utc=cell.get('created_utc'))
        row['receipt_bindings']+=refs
        row['recorded_owned_processes']=(complete or {}).get('owned_processes',[cell['owner']])
    elif not canonical and (folder/'WORKER_RESULT.json').exists():
        n,nb=reader.read(folder/'WORKER_RESULT.json');v3.same_owner(launch,n)
        require(n['job_key']==job['job_key'] and n['status']=='COMPLETE' and n['native_pcm_exact'] is True and n['asr_cursor_complete'] is True,'Historical native completion differs')
        require(n['journal']['sha256']==job['input_pcm_sha256'] and n['journal']['bytes']==round(job['duration_sec']*16000)*2 and n['source_duration_sec']==job['duration_sec'],'Historical whole journal differs')
        require(n['empty_gallery'] is True and n['hardware_calls']==0 and n['truth_passed_to_predictor'] is False,'Historical native input scope differs')
        row.update(status='NATIVE_COMPLETE_OBSERVER_PARTIAL',native_session_complete=True,epoch='S6A_B0_EXACT_SNAPSHOT' if job['profile_id']=='B00' else 'S6B_epoch2',epoch_manifest=None if job['profile_id']=='B00' else plan['historical_epoch'],historical_asset_epoch=plan['historical_epoch'],historical_native_driver=plan['driver'],historical_baseline_authority=plan['historical_baseline_authority'] if job['profile_id']=='B00' else None,actual_app_path=job['app_path'],actual_profile=job['profile'],source_asr=job['input'],source_identity=job['input'],audio_duration_sec=n['source_duration_sec'],session_dir=base.canonical(n['session_dir']),session_evidence='BOUND_HISTORICAL_PACED_WORKER',elapsed_sec=n.get('full_worker_elapsed_sec'),process_cpu_sec=n.get('process_cpu_sec_at_end'),bundle_admission_sec=n.get('bundle_admission_sec'),actual_counts=n.get('event_counts'),output_bindings=base.payloads(n),finished_utc=n.get('created_utc'))
        row['receipt_bindings'].append(nb)
        if (folder/'COMPLETE.json').exists():
            c,cb=reader.read(folder/'COMPLETE.json');require(c['status']=='COMPLETE' and c['job_key']==job['job_key'] and c['worker']==n and c['all_owned_processes_closed'] is True,'Historical coordinator completion differs')
            for b in [nb,n['events'],n['journal'],n['display_events'],n['summary_binding']]:require(b in c['artifacts'],'Historical completed binding omitted')
            for o in c['owned_processes']:owner(o)
            require(any((o['pid'],o['creation_time'])==(n['pid'],n['creation_time']) for o in c['owned_processes']),'Historical completed owner omitted')
            row['recorded_owned_processes']=c['owned_processes'];row['status']='COMPLETE';row['receipt_bindings'].append(cb)
    else:
        failure=folder/('CELL_OUTCOME.json' if canonical else 'FAILURE.json')
        if failure.exists():
            f,fb=reader.read(failure);require(f['job_key']==job['job_key'],'Failed job identity differs')
            if canonical:v3.same_owner(launch,f['owner'])
            require(f['status']=='FAILED','Unrecognized partial native outcome')
            row.update(status='FAILED',error=f.get('error',f.get('traceback')),recorded_owned_processes=f.get('owned_processes',[]));row['receipt_bindings'].append(fb)
            if canonical and f.get('native_result'):
                require(f['manifest']==pb and f['protected_functions_restored'] is True,'Failed outer native lineage differs')
                source,_=bound(reader,job['source']);n,nb,kb=native_result_metadata(reader,f['native_result'],job,source,spec,f['owner'])
                require(f['owner']['argv']==launch['argv'],'Failed owner argv differs')
                row.update(status='FAILED_OUTER_NATIVE_COMPLETE',native_session_complete=True,epoch_manifest=plan['execution_manifest'],session_dir=base.canonical(Path(next(iter(n['native_journals'].values()))['path']).parent),session_evidence='BOUND_NATIVE_COMPLETE_UNDER_FAILED_OUTER',audio_duration_sec=n['source_duration_sec'],worker_model_bundle_loads=n['resident_bundle_loads'],bundle_admission_sec=n['model_load_sec'],native_elapsed_sec=n['native_elapsed_sec'],elapsed_sec=n['total_observed_worker_sec'],actual_counts=n.get('event_counts'),output_bindings=dict(native_artifacts=n['native_artifacts'],process_samples=n['process_samples']))
                row['receipt_bindings']+=[nb,kb]
    if row['status']=='STARTED' and row['process_state']['alive'] is False:row['status']='PARTIAL_CLOSED_WITHOUT_FINAL_RESULT'
    if row['output_bindings']:row['declared_output_bytes'],row['bindings_missing_byte_counts']=base.count_bytes(row['output_bindings'])
    return row


def invocation_rows(reader,plan,pb):
    root=Path(plan['report_root'] if plan['schema']==CANONICAL else plan['output_root']);canonical=plan['schema']==CANONICAL
    jobs={j['job_id']:j for j in plan['jobs']};records=[];owners=[]
    for path in sorted((root/'invocations').glob('*/LAUNCH.json')):
        launch,lb=reader.read(path);o=owner(launch['owner'] if canonical else launch);require(launch['manifest']==pb,'Coordinator manifest differs')
        owners.append(dict(branch='PACED_COORDINATOR',pid=o['pid'],creation_time=o['creation_time'],process_state=v3.process_state(o['pid'],o['creation_time']),source=lb))
        end=path.with_name('OUTCOME.json' if canonical else 'COMPLETION.json');record=dict(launch=lb,status='STARTED',row_reference_counts=None,completed_references=None,closure=None)
        if end.exists():
            value,vb=reader.read(end);require(value['manifest']==pb and value['requested']==len(jobs),'Coordinator outcome grid differs')
            record.update(outcome=vb,status=value['status'],reported_completed=value['completed'])
            if canonical:
                v3.same_owner(o,value['owner']);refs=value['rows'];require(len(refs)==value['completed'] and len({x['job_id'] for x in refs})==len(refs),'Repeated/wrong index count')
                for x in refs:
                    require(x['job_id'] in jobs and x['status'] in ('COMPLETE','COMPLETE_REUSED'),'Invalid paced index reference')
                    c,cb=bound(reader,x['completion']);require(c['job_key']==jobs[x['job_id']]['job_key'] and c['status']=='COMPLETE' and Path(cb['path'])==Path(jobs[x['job_id']]['report_root'])/'COMPLETE.json','Reference points to another cell')
                record['row_reference_counts']=dict(Counter(x['status'] for x in refs));record['completed_references']=len(refs)
                cp=path.with_name('CLOSURE.json')
                if cp.exists():
                    c,cb=reader.read(cp);v3.same_owner(o,c['owner']);require(c['manifest']==pb and c['outcome']==vb,'Coordinator closure lineage differs');record['closure']=cb;record['closure_status']=c['status']
                    if c['status']=='QUIET_LEASE_RELEASED':
                        release=c['lease_release'];require(release['released'] is True and release['status']=='RELEASED','Quiet release flag differs')
                        lease,_=bound(reader,release['archived_binding']);v3.same_owner(o,lease);require(lease['manifest']==pb and lease['launch']==lb,'Released lease differs')
                    else:owners.append(dict(branch='PACED_QUIET_RELEASE_UNVERIFIED',pid=None,creation_time=None,process_state=dict(alive=None,state='RELEASE_UNVERIFIED'),source=cb))
                for r in value['remaining_owned']:
                    owner(r);owners.append(dict(branch='PACED_REMAINING_OWNER',pid=r['pid'],creation_time=r['creation_time'],process_state=v3.process_state(r['pid'],r['creation_time']),source=vb))
            else:
                # Historical completion only records a count, not reused/fresh row identities.
                record['reuse_reference_status']='UNAVAILABLE_IN_ORIGINAL_HISTORICAL_SCHEMA'
                archived=path.with_name('QUIET_OWNER_CLOSED.json')
                if archived.exists():
                    lease,cb=reader.read(archived);v3.same_owner(o,lease);require(lease['manifest']==pb,'Historical released lease differs');record['closure']=cb
        records.append(record)
    return records,owners


def add_physical(rows,bysession,row):
    existing=next((r for r in rows if r['physical_id']==row['physical_id']),None)
    if existing:
        require(existing['job_key']==row['job_key'] and existing['session_dir']==row['session_dir'],'Conflicting physical lineage')
        return False
    if row['session_dir']:
        key=base.canonical(row['session_dir']);require(key not in bysession,'Session already counted under another attempt/branch');bysession[key]=row['physical_id']
    rows.append(row);return True


def paced_adapter(original,admissions,reader,declared,issues,rows,bysession,discovered):
    # Skip only base historical-paced parsing; V3 retains original long/enrollment/prefix collection.
    result=original(reader,declared,issues,rows,bysession,[]);summaries=[];new=[];issue_start=len(issues)
    supplied={base.canonical(b['path']) for b in admissions}
    found={base.canonical(p) for p in discovered}|{base.canonical(p) for p in (REPORT/'paced_candidates').glob('*/MANIFEST.json')}
    missing=sorted(found-supplied)
    if missing:issues.append(dict(scope='PACED_MANIFESTS_NOT_ADMITTED',paths=missing))
    for b in admissions:
        try:
            plan,pb,spec=admit_plan(reader,b);counts=Counter();inv,owners=invocation_rows(reader,plan,pb);result['owner_observations']+=owners
            for j in plan['jobs']:
                try:
                    row=collect_job(reader,j,plan,pb,spec)
                    if row is None:counts['NOT_LAUNCHED']+=1;continue
                    counts[row['status']]+=1
                    if add_physical(rows,bysession,row):new.append(row)
                    declared.add(row['output_bindings'],row['receipt_bindings'][-1],'PACED_NATIVE_OUTPUT_TRANSITIVE')
                    for o in row.get('recorded_owned_processes',[]):
                        owner(o);result['owner_observations'].append(dict(branch='PACED_RECORDED_CHILD',pid=o['pid'],creation_time=o['creation_time'],process_state=v3.process_state(o['pid'],o['creation_time']),sources=row['receipt_bindings']))
                except (KeyError,ValueError,OSError,RuntimeError) as exc:
                    counts['UNVERIFIED_CELL_LINEAGE']+=1;issues.append(dict(manifest=pb,job_id=j['job_id'],error=repr(exc)))
                    # A known launched owner remains an attempted execution even
                    # when later completion metadata fails admission.
                    folder=Path(j['report_root']) if plan['schema']==CANONICAL else Path(plan['output_root'])/'jobs'/j['job_id']
                    if (folder/'LAUNCH.json').exists():
                        try:
                            launch,lb=reader.read(folder/'LAUNCH.json');require(launch['job_key']==j['job_key'],'Wrong fallback launch')
                            row=row_base(j,launch,lb,pb,plan['schema']==CANONICAL);row.update(status='UNVERIFIED_CELL_LINEAGE',error=repr(exc))
                            if add_physical(rows,bysession,row):new.append(row)
                        except (KeyError,ValueError,OSError,RuntimeError) as fallback:issues.append(dict(job_id=j['job_id'],launch_error=repr(fallback)))
            declared.add(plan,pb,'PACED_EXPLICIT_ADMISSION_AND_NATIVE_SOURCE')
            index=None
            index_path=Path(plan.get('report_root',plan.get('output_root')))/'PACED_INDEX.json'
            if plan['schema']==CANONICAL and index_path.exists():
                _,ib=reader.read(index_path);value,ib=admit_paced_index(reader,ib,plan,pb)
                index=dict(binding=ib,row_references=len(value['rows']),status_counts=dict(Counter(r['status'] for r in value['rows'])),not_new_inference=True)
            summaries.append(dict(manifest=pb,requested_cells=len(plan['jobs']),observed_status_counts=dict(counts),invocations=inv,paced_index=index,actual_epoch='epoch4' if plan['schema']==CANONICAL else 'S6B_EPOCH2_NATIVE_OR_EXACT_S6A_B00',physical_attempts=sum(r['receipt_bindings'][0]==pb for r in new)))
        except (KeyError,ValueError,OSError,RuntimeError) as exc:issues.append(dict(manifest=b,error=repr(exc)))
    if len(issues)>issue_start:result['owner_observations'].append(dict(branch='PACED_LINEAGE_INCOMPLETE',pid=None,creation_time=None,process_state=dict(alive=None,state='UNVERIFIED_PACED_LINEAGE')))
    result['paced_v4']=dict(schema=SCHEMA,plans=summaries,physical_attempts=len(new),complete_logical_cells=sum(r['status']=='COMPLETE' for r in new),native_sessions_with_complete_receipts=sum(r['native_session_complete'] for r in new),unadmitted_manifests=missing,source_bindings=source_bindings(),scope='Manifest/index references are not new sessions. Single-scene paired receipts are never classified as long compositions. Historical schemas do not report per-invocation reused rows; unavailable stays null.')
    for b in source_bindings():
        raw=Path(b['path']).read_bytes();target=reader.output/'source_snapshots'/Path(b['path']).name;target.write_bytes(raw);declared.add(b,b,'PACED_INVENTORY_ADAPTER_SOURCE')
    return result


def source_bindings():return [base.binding(p,p.read_bytes()) for p in (Path(__file__),HERE/'README_S6C_EXECUTION_INVENTORY_V4.md')]


def collect(args):
    require(args.paced_manifest,'Explicit paced manifests required; this is not automatic admission')
    require(re.fullmatch(r'[A-Za-z0-9_-]{1,80}',args.version or ''),'Fresh simple inventory version required')
    admissions=[]
    for path,sha in args.paced_manifest:
        require(re.fullmatch('[a-f0-9]{64}',sha),'Exact manifest SHA required');raw=Path(path).read_bytes();b=base.binding(path,raw);require(b['sha256']==sha,'Supplied paced manifest changed');admissions.append(b)
    require(len({b['path'] for b in admissions})==len(admissions),'Duplicate manifest arguments')
    before=source_bindings()
    with v3.patched_base():
        original=base.collect_auxiliary
        base.collect_auxiliary=lambda *a:paced_adapter(original,admissions,*a)
        try:result=base.collect(args)
        finally:base.collect_auxiliary=original
    require(source_bindings()==before,'Adapter changed during collection')
    return base.write_new(Path(result['snapshot']['path']).parent/'INVENTORY_V4_RECEIPT.json',dict(schema=SCHEMA,status='COMPLETE_SCOPED_ADAPTER_COLLECTION',sources=before,admitted_paced_manifests=admissions,inventory=result['snapshot'],result=result,model_calls=0,scope='Inherits base snapshot active/unverified flags; not whole-study completion.'))


def checks():
    count=0
    for p,t in ((True,1),(1,True),(1,float('nan')),(0,1),(1,-1)):
        try:owner(dict(pid=p,creation_time=t))
        except ValueError:count+=1
        else:raise AssertionError('Invalid owner admitted')
    x=dict(a=1);x['key']=base.digest(x);digest_guard(x,'key');count+=1
    try:digest_guard(dict(x,a=2),'key')
    except ValueError:count+=1
    else:raise AssertionError('Changed identity admitted')
    row=dict(physical_id='p',job_key='k',session_dir='G:/session');rows=[];sessions={}
    assert add_physical(rows,sessions,row) and not add_physical(rows,sessions,dict(row)) and len(rows)==1;count+=1
    for bad in (dict(row,physical_id='q'),dict(row,job_key='other')):
        try:add_physical(rows,sessions,bad)
        except ValueError:count+=1
        else:raise AssertionError('Conflicting/double physical session admitted')
    return dict(status='PASS_MODEL_FREE',checks=count,scope='Pure guard checks; schema-chain fixtures are supplied by the companion test script.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('checks','collect'));p.add_argument('--version');p.add_argument('--paced-manifest',nargs=2,action='append',metavar=('PATH','SHA256'));a=p.parse_args()
    print(json.dumps(checks() if a.action=='checks' else collect(a),indent=2))
